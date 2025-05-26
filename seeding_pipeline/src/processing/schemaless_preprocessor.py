"""
Segment-aware text preprocessor for schemaless extraction.

This module enriches segment text with metadata before sending to SimpleKGPipeline,
ensuring temporal context, speaker information, and segment boundaries are preserved.

JUSTIFICATION: SimpleKGPipeline processes plain text without awareness of:
- Timestamps (when something was said)
- Speakers (who said it)
- Segment boundaries (conversation structure)
- Episode/podcast context

EVIDENCE: Phase 1 testing showed SimpleKGPipeline extracts entities and relationships
but loses all temporal and speaker context.

REMOVAL CRITERIA: This component can be removed if SimpleKGPipeline adds native support for:
- Temporal metadata in text
- Speaker attribution
- Segment boundary preservation
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker
from src.core.models import Segment

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for segment preprocessing."""
    inject_timestamps: bool = True
    inject_speakers: bool = True
    inject_segment_id: bool = True
    inject_episode_context: bool = True
    timestamp_format: str = "[TIME: {start:.1f}-{end:.1f}s]"
    speaker_format: str = "[SPEAKER: {speaker}]"
    segment_format: str = "[SEGMENT: {id}]"
    episode_format: str = "[EPISODE: {title}]"
    dry_run: bool = False  # Preview changes without applying


class SegmentPreprocessor:
    """
    Preprocesses segment text to inject metadata for schemaless extraction.
    
    This class enriches plain text with temporal, speaker, and contextual information
    that SimpleKGPipeline can extract as properties on entities and relationships.
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """Initialize the preprocessor with configuration."""
        self.config = config or PreprocessingConfig()
        self.markers_added = []  # Track what was injected
        
    @track_component_impact("segment_preprocessor", "1.0.0")
    def prepare_segment_text(
        self, 
        segment: Segment, 
        episode_metadata: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Enrich segment text with metadata for extraction.
        
        Args:
            segment: Segment to preprocess
            episode_metadata: Episode information (title, podcast name, etc.)
            **kwargs: Additional context (episode_id, segment_id)
            
        Returns:
            Dictionary with enriched text and preprocessing metrics
        """
        if self.config.dry_run:
            return self._preview_changes(segment, episode_metadata)
        
        # Start with original text
        enriched_text = segment.text
        self.markers_added = []
        
        # Inject various metadata based on configuration
        if self.config.inject_timestamps and segment.start_time is not None:
            enriched_text = self.inject_temporal_context(
                enriched_text, 
                segment.start_time, 
                segment.end_time
            )
        
        if self.config.inject_speakers and segment.speaker:
            enriched_text = self.inject_speaker_context(enriched_text, segment.speaker)
        
        if self.config.inject_segment_id and segment.id:
            enriched_text = self._inject_segment_id(enriched_text, segment.id)
        
        if self.config.inject_episode_context and episode_metadata:
            enriched_text = self._inject_episode_context(enriched_text, episode_metadata)
        
        # Format for optimal extraction
        final_text = self.format_for_extraction(enriched_text)
        
        # Calculate metrics
        preprocessing_metrics = self.get_preprocessing_metrics(segment.text, final_text)
        
        # Track contribution if enabled
        if self.markers_added:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="segment_preprocessor",
                contribution_type="metadata_injection",
                details={
                    "markers_added": self.markers_added,
                    "injection_types": list(set(m.split(':')[0].strip('[') for m in self.markers_added))
                },
                count=len(self.markers_added),
                timestamp=kwargs.get('timestamp', '')
            )
            tracker.track_contribution(contribution)
        
        return {
            "enriched_text": final_text,
            "original_text": segment.text,
            "metrics": preprocessing_metrics,
            "episode_id": kwargs.get('episode_id'),
            "segment_id": kwargs.get('segment_id')
        }
    
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
    
    def format_for_extraction(self, enriched_text: str) -> str:
        """
        Format enriched text optimally for LLM extraction.
        
        Args:
            enriched_text: Text with injected metadata
            
        Returns:
            Formatted text ready for extraction
        """
        # Ensure consistent spacing
        formatted = re.sub(r'\s+', ' ', enriched_text).strip()
        
        # Ensure markers are properly separated
        formatted = re.sub(r'\]\s*\[', '] [', formatted)
        
        # Add instruction hint for better extraction
        if self.markers_added:
            formatted = f"{formatted}\n[Note: Extract metadata from markers as properties]"
        
        return formatted
    
    def get_preprocessing_metrics(self, original: str, enriched: str) -> Dict[str, Any]:
        """
        Calculate preprocessing impact metrics.
        
        Args:
            original: Original text
            enriched: Enriched text
            
        Returns:
            Metrics about the preprocessing
        """
        return {
            "type": "preprocessing",
            "details": {
                "original_length": len(original),
                "enriched_length": len(enriched),
                "length_increase": len(enriched) - len(original),
                "markers_injected": len(self.markers_added),
                "marker_types": list(set(m.split(':')[0].strip('[') for m in self.markers_added))
            },
            "count": len(self.markers_added)
        }
    
    def _preview_changes(self, segment: Segment, episode_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Preview changes without applying them (dry run mode)."""
        preview = {
            "original_text": segment.text,
            "would_inject": []
        }
        
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
        
        preview["preview_text"] = ' '.join(preview["would_inject"]) + ' ' + segment.text
        
        return preview
    
    def extract_metadata_from_enriched(self, enriched_text: str) -> Dict[str, Any]:
        """
        Extract metadata back from enriched text (for validation).
        
        Args:
            enriched_text: Text with metadata markers
            
        Returns:
            Extracted metadata
        """
        metadata = {}
        
        # Extract timestamps
        time_match = re.search(r'\[TIME:\s*([\d.]+)-([\d.]+)s\]', enriched_text)
        if time_match:
            metadata['start_time'] = float(time_match.group(1))
            metadata['end_time'] = float(time_match.group(2))
        
        # Extract speaker
        speaker_match = re.search(r'\[SPEAKER:\s*([^\]]+)\]', enriched_text)
        if speaker_match:
            metadata['speaker'] = speaker_match.group(1)
        
        # Extract segment ID
        segment_match = re.search(r'\[SEGMENT:\s*([^\]]+)\]', enriched_text)
        if segment_match:
            metadata['segment_id'] = segment_match.group(1)
        
        # Extract episode
        episode_match = re.search(r'\[EPISODE:\s*([^\]]+)\]', enriched_text)
        if episode_match:
            metadata['episode_title'] = episode_match.group(1)
        
        # Clean text (remove all markers)
        clean_text = re.sub(r'\[[^\]]+\]\s*', '', enriched_text)
        clean_text = re.sub(r'\[Note:.*\]', '', clean_text).strip()
        metadata['clean_text'] = clean_text
        
        return metadata


# Utility functions for batch processing
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
    preprocessor = SegmentPreprocessor(config)
    results = []
    
    for i, segment in enumerate(segments):
        result = preprocessor.prepare_segment_text(
            segment,
            episode_metadata,
            episode_id=episode_metadata.get('id'),
            segment_id=f"seg_{i}"
        )
        results.append(result)
    
    return results