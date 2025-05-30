"""
Consolidated text preprocessing for VTT knowledge extraction.

This module provides comprehensive text preprocessing including metadata injection,
cleaning, normalization, and enhancement for downstream knowledge extraction.
"""

import re
import string
import unicodedata
import difflib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker
from src.core.models import Segment

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for comprehensive text preprocessing."""
    # Metadata injection
    inject_timestamps: bool = True
    inject_speakers: bool = True
    inject_segment_id: bool = True
    inject_episode_context: bool = True
    
    # Formatting options
    timestamp_format: str = "[TIME: {start:.1f}-{end:.1f}s]"
    speaker_format: str = "[SPEAKER: {speaker}]"
    segment_format: str = "[SEGMENT: {id}]"
    episode_format: str = "[EPISODE: {title}]"
    
    # Text cleaning options
    clean_transcription_artifacts: bool = True
    normalize_whitespace: bool = True
    remove_special_chars: bool = True
    fix_common_errors: bool = True
    
    # Processing modes
    dry_run: bool = False  # Preview changes without applying
    extract_key_phrases: bool = False
    max_phrases: int = 10


class TextPreprocessor:
    """
    Comprehensive text preprocessor for VTT knowledge extraction.
    
    Combines metadata injection, text cleaning, normalization, and enhancement
    capabilities previously scattered across multiple components.
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """Initialize the preprocessor with configuration."""
        self.config = config or PreprocessingConfig()
        self.markers_added = []  # Track metadata injected
        
        # Common transcription artifacts to clean
        self.transcription_artifacts = {
            ' um ': ' ',
            ' uh ': ' ',
            ' uhm ': ' ',
            ' umm ': ' ',
            ' like ': ' ',  # Often overused in speech
            ' you know ': ' ',
            ' I mean ': ' ',
            '  ': ' ',  # Double spaces
        }
        
        # Common abbreviations to expand
        self.abbreviations = {
            "&": "and",
            "u.s.": "us",
            "u.k.": "uk",
            "dr.": "doctor",
            "mr.": "mister",
            "ms.": "miss",
            "prof.": "professor"
        }
        
        # Stop words for key phrase extraction
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under', 'is', 'are',
            'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must',
            'shall', 'can', 'need', 'dare', 'ought', 'used', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'them', 'their', 'this', 'that', 'these',
            'those', 'what', 'which', 'who', 'whom', 'whose', 'when', 'where',
            'why', 'how', 'all', 'each', 'every', 'some', 'any', 'many', 'much',
            'most', 'other', 'another', 'such', 'no', 'nor', 'not', 'only', 'own',
            'same', 'so', 'than', 'too', 'very', 's', 't', 'just', 'now'
        }
    
    @track_component_impact("text_preprocessor", "1.0.0")
    def preprocess_segment(
        self, 
        segment: Segment, 
        episode_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Comprehensive preprocessing of segment text.
        
        Args:
            segment: Segment to preprocess
            episode_metadata: Episode information (title, podcast name, etc.)
            **kwargs: Additional context (episode_id, segment_id)
            
        Returns:
            Dictionary with processed text and preprocessing metrics
        """
        if self.config.dry_run:
            return self._preview_changes(segment, episode_metadata or {})
        
        # Start with original text
        processed_text = segment.text
        self.markers_added = []
        
        # Phase 1: Text cleaning and normalization
        if self.config.clean_transcription_artifacts:
            processed_text = self.clean_transcription_text(processed_text)
        
        if self.config.normalize_whitespace:
            processed_text = self.normalize_whitespace(processed_text)
        
        if self.config.remove_special_chars:
            processed_text = self.clean_special_characters(processed_text)
        
        # Phase 2: Metadata injection (if enabled)
        if self.config.inject_timestamps and segment.start_time is not None:
            processed_text = self.inject_temporal_context(
                processed_text, 
                segment.start_time, 
                segment.end_time
            )
        
        if self.config.inject_speakers and segment.speaker:
            processed_text = self.inject_speaker_context(processed_text, segment.speaker)
        
        if self.config.inject_segment_id and segment.id:
            processed_text = self._inject_segment_id(processed_text, segment.id)
        
        if self.config.inject_episode_context and episode_metadata:
            processed_text = self._inject_episode_context(processed_text, episode_metadata)
        
        # Phase 3: Final formatting and optimization
        final_text = self.format_for_extraction(processed_text)
        
        # Phase 4: Extract key phrases if requested
        key_phrases = []
        if self.config.extract_key_phrases:
            key_phrases = self.extract_key_phrases(final_text, self.config.max_phrases)
        
        # Calculate metrics
        metrics = self.calculate_preprocessing_metrics(segment.text, final_text)
        
        # Track contribution if enabled
        if self.markers_added:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="text_preprocessor",
                contribution_type="metadata_injection",
                details={
                    "markers_added": self.markers_added,
                    "injection_types": list(set(m.split(':')[0].strip('[') for m in self.markers_added)),
                    "text_cleaned": self.config.clean_transcription_artifacts
                },
                count=len(self.markers_added),
                timestamp=kwargs.get('timestamp', '')
            )
            tracker.track_contribution(contribution)
        
        return {
            "processed_text": final_text,
            "original_text": segment.text,
            "key_phrases": key_phrases,
            "metrics": metrics,
            "episode_id": kwargs.get('episode_id'),
            "segment_id": kwargs.get('segment_id')
        }
    
    def clean_transcription_text(self, text: str) -> str:
        """
        Clean common transcription artifacts and speech patterns.
        
        Args:
            text: Raw transcription text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Strip whitespace
        text = text.strip()
        
        # Remove/replace transcription artifacts
        for artifact, replacement in self.transcription_artifacts.items():
            text = text.replace(artifact, replacement)
        
        # Remove control characters but keep punctuation
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # Handle abbreviations
        for abbr, full in self.abbreviations.items():
            text = text.replace(abbr, full)
        
        return text.strip()
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize all whitespace in text.
        
        Args:
            text: Text with irregular whitespace
            
        Returns:
            Text with normalized whitespace
        """
        if not text:
            return ""
        
        # Replace all whitespace characters with single spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        return text.strip()
    
    def clean_special_characters(self, text: str, keep_punctuation: bool = True) -> str:
        """
        Remove special characters from text.
        
        Args:
            text: Text to clean
            keep_punctuation: Whether to keep punctuation marks
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        if keep_punctuation:
            # Keep letters, numbers, spaces, and basic punctuation
            cleaned = re.sub(r'[^a-zA-Z0-9\s.,!?;:\-\'"()]', '', text)
        else:
            # Keep only letters, numbers, and spaces
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        
        # Remove multiple spaces
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def inject_temporal_context(self, text: str, start_time: float, end_time: float) -> str:
        """
        Add timestamp information to text.
        
        Args:
            text: Original text
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            Text with temporal markers
        """
        timestamp_marker = self.config.timestamp_format.format(
            start=start_time,
            end=end_time
        )
        
        self.markers_added.append(timestamp_marker)
        
        # Add at the beginning for better LLM attention
        return f"{timestamp_marker} {text}"
    
    def inject_speaker_context(self, text: str, speaker: str) -> str:
        """
        Add speaker identification to text.
        
        Args:
            text: Original text
            speaker: Speaker name or ID
            
        Returns:
            Text with speaker marker
        """
        speaker_marker = self.config.speaker_format.format(speaker=speaker)
        self.markers_added.append(speaker_marker)
        
        # Add after timestamp if present, otherwise at beginning
        if text.startswith("[TIME:"):
            # Find end of time marker
            time_end = text.find("]") + 1
            return f"{text[:time_end]} {speaker_marker} {text[time_end:].strip()}"
        else:
            return f"{speaker_marker} {text}"
    
    def _inject_segment_id(self, text: str, segment_id: str) -> str:
        """Add segment identifier for tracking."""
        segment_marker = self.config.segment_format.format(id=segment_id)
        self.markers_added.append(segment_marker)
        
        # Add at the very beginning
        return f"{segment_marker} {text}"
    
    def _inject_episode_context(self, text: str, metadata: Dict[str, Any]) -> str:
        """Add episode-level context."""
        if 'title' in metadata:
            episode_marker = self.config.episode_format.format(title=metadata['title'])
            self.markers_added.append(episode_marker)
            
            # Add after segment ID if present
            if text.startswith("[SEGMENT:"):
                segment_end = text.find("]") + 1
                return f"{text[:segment_end]} {episode_marker} {text[segment_end:].strip()}"
            else:
                return f"{episode_marker} {text}"
        
        return text
    
    def format_for_extraction(self, text: str) -> str:
        """
        Format text optimally for LLM extraction.
        
        Args:
            text: Text with injected metadata
            
        Returns:
            Formatted text ready for extraction
        """
        # Ensure consistent spacing
        formatted = re.sub(r'\s+', ' ', text).strip()
        
        # Ensure markers are properly separated
        formatted = re.sub(r'\]\s*\[', '] [', formatted)
        
        # Add instruction hint for better extraction if metadata was injected
        if self.markers_added:
            formatted = f"{formatted}\n[Note: Extract metadata from markers as properties]"
        
        return formatted
    
    def extract_key_phrases(self, text: str, max_phrases: int = 10) -> List[str]:
        """
        Extract key phrases from text using simple heuristics.
        
        Args:
            text: Text to extract phrases from
            max_phrases: Maximum number of phrases to return
            
        Returns:
            List of key phrases
        """
        if not text:
            return []
        
        # Remove metadata markers for phrase extraction
        clean_text = re.sub(r'\[[^\]]+\]', '', text)
        
        # Extract noun phrases using simple patterns
        sentences = clean_text.split('.')
        phrases = []
        
        for sentence in sentences:
            # Clean sentence
            sentence = sentence.strip().lower()
            if not sentence:
                continue
            
            # Remove punctuation except hyphens
            sentence = re.sub(r'[^\w\s-]', ' ', sentence)
            
            # Extract potential phrases (2-4 word combinations)
            words = sentence.split()
            
            for i in range(len(words)):
                # 2-word phrases
                if i < len(words) - 1:
                    phrase = f"{words[i]} {words[i+1]}"
                    if words[i] not in self.stop_words and words[i+1] not in self.stop_words:
                        phrases.append(phrase)
                
                # 3-word phrases
                if i < len(words) - 2:
                    phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
                    if (words[i] not in self.stop_words and 
                        words[i+2] not in self.stop_words):
                        phrases.append(phrase)
        
        # Count phrase frequency
        phrase_counts = {}
        for phrase in phrases:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        # Sort by frequency and return top phrases
        sorted_phrases = sorted(phrase_counts.items(), 
                              key=lambda x: x[1], 
                              reverse=True)
        
        return [phrase for phrase, _ in sorted_phrases[:max_phrases]]
    
    def calculate_preprocessing_metrics(self, original: str, processed: str) -> Dict[str, Any]:
        """
        Calculate preprocessing impact metrics.
        
        Args:
            original: Original text
            processed: Processed text
            
        Returns:
            Metrics about the preprocessing
        """
        return {
            "type": "preprocessing",
            "details": {
                "original_length": len(original),
                "processed_length": len(processed),
                "length_change": len(processed) - len(original),
                "markers_injected": len(self.markers_added),
                "marker_types": list(set(m.split(':')[0].strip('[') for m in self.markers_added)) if self.markers_added else [],
                "cleaning_applied": self.config.clean_transcription_artifacts,
                "metadata_injected": len(self.markers_added) > 0
            },
            "count": len(self.markers_added)
        }
    
    def _preview_changes(self, segment: Segment, episode_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Preview changes without applying them (dry run mode)."""
        preview = {
            "original_text": segment.text,
            "would_inject": [],
            "would_clean": []
        }
        
        # Preview cleaning
        if self.config.clean_transcription_artifacts:
            preview["would_clean"].append("transcription_artifacts")
        if self.config.normalize_whitespace:
            preview["would_clean"].append("whitespace_normalization")
        if self.config.remove_special_chars:
            preview["would_clean"].append("special_characters")
        
        # Preview metadata injection
        if self.config.inject_timestamps and segment.start_time is not None:
            preview["would_inject"].append(
                self.config.timestamp_format.format(
                    start=segment.start_time,
                    end=segment.end_time
                )
            )
        
        if self.config.inject_speakers and segment.speaker:
            preview["would_inject"].append(
                self.config.speaker_format.format(speaker=segment.speaker)
            )
        
        if self.config.inject_segment_id and segment.id:
            preview["would_inject"].append(
                self.config.segment_format.format(id=segment.id)
            )
        
        if self.config.inject_episode_context and episode_metadata.get('title'):
            preview["would_inject"].append(
                self.config.episode_format.format(title=episode_metadata['title'])
            )
        
        # Create preview text
        cleaned_text = segment.text
        if self.config.clean_transcription_artifacts:
            cleaned_text = self.clean_transcription_text(cleaned_text)
        
        preview["preview_text"] = ' '.join(preview["would_inject"]) + ' ' + cleaned_text
        
        return preview
    
    def extract_metadata_from_processed(self, processed_text: str) -> Dict[str, Any]:
        """
        Extract metadata back from processed text (for validation).
        
        Args:
            processed_text: Text with metadata markers
            
        Returns:
            Extracted metadata
        """
        metadata = {}
        
        # Extract timestamps
        time_match = re.search(r'\[TIME:\s*([\d.]+)-([\d.]+)s\]', processed_text)
        if time_match:
            metadata['start_time'] = float(time_match.group(1))
            metadata['end_time'] = float(time_match.group(2))
        
        # Extract speaker
        speaker_match = re.search(r'\[SPEAKER:\s*([^\]]+)\]', processed_text)
        if speaker_match:
            metadata['speaker'] = speaker_match.group(1)
        
        # Extract segment ID
        segment_match = re.search(r'\[SEGMENT:\s*([^\]]+)\]', processed_text)
        if segment_match:
            metadata['segment_id'] = segment_match.group(1)
        
        # Extract episode
        episode_match = re.search(r'\[EPISODE:\s*([^\]]+)\]', processed_text)
        if episode_match:
            metadata['episode_title'] = episode_match.group(1)
        
        # Clean text (remove all markers)
        clean_text = re.sub(r'\[[^\]]+\]\s*', '', processed_text)
        clean_text = re.sub(r'\[Note:.*\]', '', clean_text).strip()
        metadata['clean_text'] = clean_text
        
        return metadata


# Utility functions for backward compatibility and batch processing
def preprocess_segments_batch(
    segments: List[Segment], 
    episode_metadata: Dict[str, Any],
    config: Optional[PreprocessingConfig] = None
) -> List[Dict[str, Any]]:
    """
    Preprocess multiple segments efficiently.
    
    Args:
        segments: List of segments to preprocess
        episode_metadata: Episode information
        config: Preprocessing configuration
        
    Returns:
        List of preprocessing results
    """
    preprocessor = TextPreprocessor(config)
    results = []
    
    for i, segment in enumerate(segments):
        result = preprocessor.preprocess_segment(
            segment,
            episode_metadata,
            episode_id=episode_metadata.get('id'),
            segment_id=f"seg_{i}"
        )
        results.append(result)
    
    return results


# Legacy compatibility aliases
SegmentPreprocessor = TextPreprocessor  # For backward compatibility
prepare_segment_text = lambda self, segment, metadata, **kwargs: self.preprocess_segment(segment, metadata, **kwargs)