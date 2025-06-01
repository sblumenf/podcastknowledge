"""Speaker Identification Processor for Podcast Transcription Pipeline.

This module handles contextual speaker recognition, replacing generic
speaker labels with actual names or descriptive roles.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio

from gemini_client import RateLimitedGeminiClient
from key_rotation_manager import KeyRotationManager
from src.utils.logging import get_logger
from checkpoint_recovery import CheckpointManager

logger = get_logger('speaker_identifier')


@dataclass
class SpeakerMapping:
    """Represents a mapping from generic label to identified speaker."""
    generic_label: str  # e.g., "SPEAKER_1"
    identified_name: str  # e.g., "John Smith (Host)"
    confidence: float  # 0.0 to 1.0
    evidence: List[str]  # List of evidence supporting this identification
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'generic_label': self.generic_label,
            'identified_name': self.identified_name,
            'confidence': self.confidence,
            'evidence': self.evidence
        }


class SpeakerIdentifier:
    """Identifies speakers in transcripts using contextual analysis."""
    
    def __init__(self, gemini_client: RateLimitedGeminiClient, key_manager: KeyRotationManager,
                 checkpoint_manager: Optional[CheckpointManager] = None):
        """Initialize speaker identifier.
        
        Args:
            gemini_client: Rate-limited Gemini API client
            key_manager: API key rotation manager
            checkpoint_manager: Optional checkpoint manager for recovery
        """
        self.gemini_client = gemini_client
        self.key_manager = key_manager
        self.checkpoint_manager = checkpoint_manager
    
    async def identify_speakers(self, 
                              vtt_transcript: str, 
                              episode_metadata: Dict[str, Any]) -> Dict[str, str]:
        """Identify speakers in VTT transcript based on context.
        
        Args:
            vtt_transcript: VTT-formatted transcript with generic speaker labels
            episode_metadata: Episode information for context
            
        Returns:
            Dictionary mapping generic labels to identified names/roles
        """
        try:
            # Get next API key
            api_key, key_index = self.key_manager.get_next_key()
            
            # Update Gemini client with selected key
            self.gemini_client.api_keys = [api_key]
            self.gemini_client.usage_trackers = [self.gemini_client.usage_trackers[key_index]]
            
            logger.info("Starting speaker identification")
            logger.info(f"Using API key index: {key_index + 1}")
            
            # Extract speaker labels from transcript
            speaker_labels = self._extract_speaker_labels(vtt_transcript)
            logger.info(f"Found {len(speaker_labels)} unique speakers: {speaker_labels}")
            
            # Build analysis prompt
            prompt = self._build_identification_prompt(
                vtt_transcript, 
                episode_metadata, 
                speaker_labels
            )
            
            # Call Gemini for speaker identification
            mapping = await self.gemini_client.identify_speakers(vtt_transcript, episode_metadata)
            
            if not mapping:
                logger.warning("No speaker mapping returned from API")
                mapping = self._create_fallback_mapping(speaker_labels, episode_metadata)
            
            # Validate and enhance mapping
            validated_mapping = self._validate_mapping(mapping, speaker_labels, episode_metadata)
            
            # Save checkpoint if enabled
            if self.checkpoint_manager:
                self.checkpoint_manager.save_temp_data('speaker_mapping', json.dumps(validated_mapping))
                self.checkpoint_manager.complete_stage('speaker_identification')
            
            # Mark key as successful
            self.key_manager.mark_key_success(key_index)
            
            logger.info(f"Speaker identification completed: {validated_mapping}")
            return validated_mapping
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Speaker identification failed: {error_msg}")
            
            # Mark key as failed if we have a key index
            if 'key_index' in locals():
                self.key_manager.mark_key_failure(key_index, error_msg)
            
            # Return fallback mapping
            if 'speaker_labels' in locals():
                return self._create_fallback_mapping(speaker_labels, episode_metadata)
            return {}
    
    def _extract_speaker_labels(self, vtt_transcript: str) -> List[str]:
        """Extract unique speaker labels from VTT transcript.
        
        Args:
            vtt_transcript: VTT-formatted transcript
            
        Returns:
            List of unique speaker labels found
        """
        # Pattern to find speaker tags: <v SPEAKER_N>
        speaker_pattern = re.compile(r'<v\s+([^>]+)>')
        
        speakers = set()
        for match in speaker_pattern.finditer(vtt_transcript):
            speaker = match.group(1).strip()
            speakers.add(speaker)
        
        # Sort for consistent ordering
        return sorted(list(speakers))
    
    def _build_identification_prompt(self, 
                                   transcript: str, 
                                   metadata: Dict[str, Any],
                                   speaker_labels: List[str]) -> str:
        """Build enhanced prompt for speaker identification."""
        # Extract sample dialogue for each speaker
        speaker_samples = self._extract_speaker_samples(transcript, speaker_labels)
        
        # Build samples text
        samples_text = ""
        for label, samples in speaker_samples.items():
            samples_text += f"\n{label} sample dialogue:\n"
            for sample in samples[:3]:  # First 3 samples
                samples_text += f"- \"{sample}\"\n"
        
        return f"""Analyze this podcast transcript and identify the speakers based on context clues.

**Podcast Information:**
- Podcast Name: {metadata.get('podcast_name', 'Unknown')}
- Host/Author: {metadata.get('author', 'Unknown')}
- Episode Title: {metadata.get('title', 'Unknown')}
- Description: {metadata.get('description', '')[:500]}...
- Publication Date: {metadata.get('publication_date', 'Unknown')}

**Speaker Labels Found:** {', '.join(speaker_labels)}

**Sample Dialogue for Each Speaker:**
{samples_text}

**Instructions:**
1. Identify each speaker based on:
   - Self-introductions (e.g., "I'm John Smith")
   - Being introduced by others (e.g., "Our guest today is...")
   - References in conversation (e.g., "As Sarah mentioned...")
   - Speaking patterns and roles (hosts typically introduce the show)
   - Context from episode title and description

2. For each speaker, provide:
   - The most likely name or descriptive role
   - Consider the podcast format (interview, panel, solo, etc.)

3. If you cannot identify a specific name:
   - Use descriptive roles: "Host", "Guest", "Co-host", etc.
   - Number multiple guests: "Guest 1", "Guest 2", etc.

4. Consider common podcast patterns:
   - SPEAKER_1 is often the host (introduces show, asks questions)
   - Subsequent speakers are typically guests or co-hosts

**Return a JSON object mapping speaker labels to identified names/roles:**
{{
  "SPEAKER_1": "Name or Role (additional context)",
  "SPEAKER_2": "Name or Role (additional context)",
  ...
}}

Example response:
{{
  "SPEAKER_1": "Lisa Park (Host)",
  "SPEAKER_2": "Dr. Michael Chen (Guest - AI Researcher)",
  "SPEAKER_3": "Sarah Johnson (Co-host)"
}}"""
    
    def _extract_speaker_samples(self, 
                               transcript: str, 
                               speaker_labels: List[str],
                               max_samples: int = 5) -> Dict[str, List[str]]:
        """Extract sample dialogue for each speaker.
        
        Args:
            transcript: VTT transcript
            speaker_labels: List of speaker labels to extract
            max_samples: Maximum samples per speaker
            
        Returns:
            Dictionary mapping speaker labels to sample texts
        """
        samples = {label: [] for label in speaker_labels}
        
        # Parse VTT to extract cues
        cue_pattern = re.compile(
            r'\d{1,}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{1,}:\d{2}:\d{2}\.\d{3}\s*\n<v\s+([^>]+)>(.+?)(?=\n\d{1,}:\d{2}:\d{2}\.\d{3}|$)',
            re.DOTALL | re.MULTILINE
        )
        
        for match in cue_pattern.finditer(transcript):
            speaker = match.group(1).strip()
            text = match.group(2).strip().replace('\n', ' ')
            
            if speaker in samples and len(samples[speaker]) < max_samples:
                # Clean and limit text length
                text = re.sub(r'\s+', ' ', text)[:200]
                if text and len(text) > 20:  # Skip very short utterances
                    samples[speaker].append(text)
        
        return samples
    
    def _validate_mapping(self, 
                         mapping: Dict[str, str], 
                         expected_labels: List[str],
                         metadata: Dict[str, Any]) -> Dict[str, str]:
        """Validate and enhance speaker mapping.
        
        Args:
            mapping: Raw mapping from API
            expected_labels: Expected speaker labels
            metadata: Episode metadata for fallback
            
        Returns:
            Validated and enhanced mapping
        """
        validated = {}
        
        # Ensure all expected labels have mappings
        for label in expected_labels:
            if label in mapping and mapping[label]:
                # Clean and validate the identified name
                identified = mapping[label].strip()
                
                # Remove any JSON artifacts or quotes
                identified = identified.strip('"\'')
                
                # Ensure it's not just the generic label
                if identified and identified != label:
                    validated[label] = identified
                else:
                    validated[label] = self._get_fallback_name(label, metadata)
            else:
                validated[label] = self._get_fallback_name(label, metadata)
        
        return validated
    
    def _get_fallback_name(self, label: str, metadata: Dict[str, Any]) -> str:
        """Get fallback name for a speaker label.
        
        Args:
            label: Generic speaker label
            metadata: Episode metadata
            
        Returns:
            Fallback name/role
        """
        # Extract speaker number
        match = re.search(r'SPEAKER_(\d+)', label)
        if match:
            speaker_num = int(match.group(1))
            
            # First speaker is typically the host
            if speaker_num == 1:
                host_name = metadata.get('author', '').strip()
                if host_name:
                    return f"{host_name} (Host)"
                return "Host"
            
            # Other speakers are guests
            if speaker_num == 2:
                return "Guest"
            else:
                return f"Guest {speaker_num - 1}"
        
        return label
    
    def _create_fallback_mapping(self, 
                               speaker_labels: List[str],
                               metadata: Dict[str, Any]) -> Dict[str, str]:
        """Create fallback mapping when API fails.
        
        Args:
            speaker_labels: List of speaker labels
            metadata: Episode metadata
            
        Returns:
            Fallback mapping dictionary
        """
        mapping = {}
        for label in speaker_labels:
            mapping[label] = self._get_fallback_name(label, metadata)
        return mapping
    
    def apply_speaker_mapping(self, 
                            vtt_transcript: str, 
                            speaker_mapping: Dict[str, str]) -> str:
        """Apply speaker mapping to VTT transcript.
        
        Args:
            vtt_transcript: Original VTT with generic labels
            speaker_mapping: Mapping from generic to identified names
            
        Returns:
            Updated VTT transcript with identified speakers
        """
        updated_transcript = vtt_transcript
        
        # Sort by label length (descending) to avoid partial replacements
        sorted_mappings = sorted(
            speaker_mapping.items(), 
            key=lambda x: len(x[0]), 
            reverse=True
        )
        
        # Replace speaker tags
        for generic_label, identified_name in sorted_mappings:
            # Pattern to match speaker tags with this label
            pattern = f'<v {re.escape(generic_label)}>'
            replacement = f'<v {identified_name}>'
            
            updated_transcript = re.sub(
                pattern,
                replacement,
                updated_transcript
            )
        
        return updated_transcript
    
    def generate_speaker_metadata(self, 
                                speaker_mapping: Dict[str, str],
                                episode_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata about identified speakers.
        
        Args:
            speaker_mapping: Final speaker mapping
            episode_metadata: Episode information
            
        Returns:
            Speaker metadata dictionary
        """
        speakers = []
        
        for generic_label, identified_name in speaker_mapping.items():
            # Parse role from identified name if present
            role = "Unknown"
            name = identified_name
            
            # Check for role in parentheses
            role_match = re.search(r'\(([^)]+)\)$', identified_name)
            if role_match:
                role = role_match.group(1)
                name = identified_name[:role_match.start()].strip()
            
            speakers.append({
                'label': generic_label,
                'name': name,
                'role': role,
                'full_identification': identified_name
            })
        
        return {
            'speakers': speakers,
            'speaker_count': len(speakers),
            'identification_method': 'contextual_analysis',
            'podcast_format': self._infer_podcast_format(len(speakers))
        }
    
    def _infer_podcast_format(self, speaker_count: int) -> str:
        """Infer podcast format from speaker count.
        
        Args:
            speaker_count: Number of speakers identified
            
        Returns:
            Inferred podcast format
        """
        if speaker_count == 1:
            return "solo"
        elif speaker_count == 2:
            return "interview"
        elif speaker_count == 3:
            return "co-hosted_interview"
        else:
            return "panel"