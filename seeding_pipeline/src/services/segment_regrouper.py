"""Segment regrouping service for semantic segmentation."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.core.interfaces import TranscriptSegment
from src.core.conversation_models.conversation import ConversationStructure, ConversationUnit
from src.core.monitoring import trace_operation
from src.core.exceptions import ProcessingError

logger = logging.getLogger(__name__)


@dataclass
class MeaningfulUnit:
    """Represents a semantically coherent unit of conversation."""
    
    id: str
    segments: List[TranscriptSegment]
    unit_type: str
    summary: str
    themes: List[str]
    start_time: float
    end_time: float
    primary_speaker: str  # DEPRECATED: Use speaker_distribution instead. Kept for compatibility only.
    speaker_distribution: Dict[str, float]  # New field: speaker percentages
    is_complete: bool
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def text(self) -> str:
        """Get concatenated text from all segments."""
        return " ".join(segment.text for segment in self.segments)
    
    @property
    def duration(self) -> float:
        """Get total duration of the unit."""
        return self.end_time - self.start_time
    
    @property
    def segment_count(self) -> int:
        """Get number of segments in this unit."""
        return len(self.segments)


class SegmentRegrouper:
    """Regroups transcript segments into meaningful conversation units."""
    
    def __init__(self):
        """Initialize segment regrouper."""
        self.logger = logger
        
    @trace_operation("regroup_segments")
    def regroup_segments(
        self, 
        segments: List[TranscriptSegment], 
        structure: ConversationStructure
    ) -> List[MeaningfulUnit]:
        """
        Regroup segments based on conversation structure analysis.
        
        Args:
            segments: Original VTT segments
            structure: Analyzed conversation structure
            
        Returns:
            List of meaningful units ready for knowledge extraction
            
        Raises:
            ProcessingError: If regrouping fails
        """
        if not segments:
            raise ProcessingError("No segments provided for regrouping")
        
        if not structure.units:
            raise ProcessingError("No conversation units found in structure")
            
        self.logger.info(
            f"Regrouping {len(segments)} segments into {len(structure.units)} meaningful units"
        )
        
        try:
            meaningful_units = []
            
            for idx, conv_unit in enumerate(structure.units):
                # Extract segments for this unit
                unit_segments = self._extract_unit_segments(segments, conv_unit)
                
                if not unit_segments:
                    self.logger.warning(
                        f"No segments found for unit {idx} "
                        f"(indices {conv_unit.start_index}-{conv_unit.end_index})"
                    )
                    continue
                
                # Create meaningful unit
                meaningful_unit = self._create_meaningful_unit(
                    unit_segments=unit_segments,
                    conv_unit=conv_unit,
                    unit_index=idx,
                    structure=structure
                )
                
                meaningful_units.append(meaningful_unit)
                
            self.logger.info(
                f"Created {len(meaningful_units)} meaningful units from {len(segments)} segments"
            )
            
            # Validate coverage
            self._validate_coverage(segments, meaningful_units)
            
            return meaningful_units
            
        except Exception as e:
            self.logger.error(f"Failed to regroup segments: {str(e)}")
            raise ProcessingError(f"Segment regrouping failed: {str(e)}")
    
    def _extract_unit_segments(
        self, 
        segments: List[TranscriptSegment], 
        conv_unit: ConversationUnit
    ) -> List[TranscriptSegment]:
        """Extract segments belonging to a conversation unit."""
        # Validate indices
        if conv_unit.start_index >= len(segments) or conv_unit.end_index >= len(segments):
            self.logger.warning(
                f"Unit indices out of range: {conv_unit.start_index}-{conv_unit.end_index}, "
                f"total segments: {len(segments)}"
            )
            # Adjust to valid range
            end_index = min(conv_unit.end_index, len(segments) - 1)
            start_index = min(conv_unit.start_index, end_index)
        else:
            start_index = conv_unit.start_index
            end_index = conv_unit.end_index
            
        # Extract segments (inclusive range)
        return segments[start_index:end_index + 1]
    
    def _create_meaningful_unit(
        self,
        unit_segments: List[TranscriptSegment],
        conv_unit: ConversationUnit,
        unit_index: int,
        structure: ConversationStructure
    ) -> MeaningfulUnit:
        """Create a meaningful unit from segments and conversation unit."""
        # Calculate speaker info (primary speaker and distribution)
        primary_speaker, speaker_distribution = self._calculate_speaker_info(unit_segments)
        
        # Find related themes
        related_themes = []
        for theme in structure.themes:
            if unit_index in theme.related_units:
                related_themes.append(theme.theme)
        
        # Determine if unit is complete
        is_complete = conv_unit.completeness == "complete"
        if not is_complete:
            self.logger.warning(f"Unit {unit_index} marked as incomplete: {conv_unit.completeness}")
        
        # Create unit ID
        unit_id = f"unit_{unit_index:03d}_{conv_unit.unit_type}"
        
        return MeaningfulUnit(
            id=unit_id,
            segments=unit_segments,
            unit_type=conv_unit.unit_type,
            summary=conv_unit.description,
            themes=related_themes,
            start_time=unit_segments[0].start_time,
            end_time=unit_segments[-1].end_time,
            primary_speaker=primary_speaker,
            speaker_distribution=speaker_distribution,
            is_complete=is_complete,
            metadata={
                "original_indices": {
                    "start": conv_unit.start_index,
                    "end": conv_unit.end_index
                },
                "completeness": conv_unit.completeness,
                "segment_count": len(unit_segments)
            }
        )
    
    # Removed _calculate_speaker_distribution - no longer needed with primary_speaker approach
    
    def _calculate_speaker_info(
        self,
        segments: List[TranscriptSegment]
    ) -> Tuple[str, Dict[str, float]]:
        """Calculate primary speaker and speaker distribution percentages.
        
        This method calculates how much each speaker talks within a meaningful unit
        by summing their speaking time and converting to percentages. The percentages
        are guaranteed to sum to exactly 100% through rounding adjustment.
        
        Args:
            segments: List of transcript segments containing speaker and timing info
            
        Returns:
            Tuple of (primary_speaker, speaker_distribution) where:
            - primary_speaker: Name of speaker with most speaking time
            - speaker_distribution: Dict mapping speaker names to percentage of speaking time
                                  e.g., {"Host": 65.5, "Guest": 34.5}
        
        Example:
            >>> segments = [segment1_host_60s, segment2_guest_40s]
            >>> primary, dist = _calculate_speaker_info(segments)
            >>> print(primary)  # "Host"
            >>> print(dist)     # {"Host": 60.0, "Guest": 40.0}
        """
        speaker_times = {}
        
        for segment in segments:
            # Handle both TranscriptSegment objects and dictionaries
            if isinstance(segment, dict):
                speaker = segment.get('speaker') or "Unknown"
                duration = segment['end_time'] - segment['start_time']
            else:
                speaker = segment.speaker or "Unknown"
                duration = segment.end_time - segment.start_time
            
            if speaker not in speaker_times:
                speaker_times[speaker] = 0.0
            speaker_times[speaker] += duration
        
        # Handle empty segments case
        if not speaker_times:
            return "Unknown", {"Unknown": 100.0}
        
        # Calculate total time
        total_time = sum(speaker_times.values())
        
        # Calculate percentages
        speaker_distribution = {}
        for speaker, time in speaker_times.items():
            percentage = round((time / total_time * 100), 1) if total_time > 0 else 0.0
            speaker_distribution[speaker] = percentage
        
        # Ensure percentages sum to 100% (adjust for rounding)
        total_percentage = sum(speaker_distribution.values())
        if total_percentage != 100.0 and speaker_distribution:
            # Adjust the largest percentage to make total exactly 100
            max_speaker = max(speaker_distribution.items(), key=lambda x: x[1])[0]
            speaker_distribution[max_speaker] += round(100.0 - total_percentage, 1)
        
        # Get primary speaker (with most time)
        primary_speaker = max(speaker_times.items(), key=lambda x: x[1])[0]
        
        return primary_speaker, speaker_distribution
    
    def _validate_coverage(
        self, 
        original_segments: List[TranscriptSegment], 
        meaningful_units: List[MeaningfulUnit]
    ):
        """Validate that meaningful units cover all segments appropriately."""
        # Check segment coverage
        covered_segments = set()
        for unit in meaningful_units:
            for segment in unit.segments:
                segment_id = segment['id'] if isinstance(segment, dict) else segment.id
                if segment_id in covered_segments:
                    self.logger.warning(f"Segment {segment_id} appears in multiple units")
                covered_segments.add(segment_id)
        
        # Check for missing segments
        all_segment_ids = {segment['id'] if isinstance(segment, dict) else segment.id for segment in original_segments}
        missing_segments = all_segment_ids - covered_segments
        
        if missing_segments:
            self.logger.warning(
                f"{len(missing_segments)} segments not included in any meaningful unit: "
                f"{list(missing_segments)[:5]}..."
            )
        
        # Log statistics
        total_original_duration = sum(
            (segment['end_time'] - segment['start_time']) if isinstance(segment, dict) else (segment.end_time - segment.start_time)
            for segment in original_segments
        )
        total_unit_duration = sum(unit.duration for unit in meaningful_units)
        
        self.logger.info(
            f"Coverage statistics: "
            f"{len(covered_segments)}/{len(original_segments)} segments covered, "
            f"{total_unit_duration:.1f}s/{total_original_duration:.1f}s duration covered"
        )
        
    def get_unit_statistics(self, units: List[MeaningfulUnit]) -> Dict[str, Any]:
        """Get statistics about meaningful units."""
        if not units:
            return {"error": "No units provided"}
            
        unit_types = {}
        durations = []
        segment_counts = []
        incomplete_count = 0
        
        for unit in units:
            # Count unit types
            if unit.unit_type not in unit_types:
                unit_types[unit.unit_type] = 0
            unit_types[unit.unit_type] += 1
            
            # Collect metrics
            durations.append(unit.duration)
            segment_counts.append(unit.segment_count)
            
            if not unit.is_complete:
                incomplete_count += 1
        
        return {
            "total_units": len(units),
            "unit_types": unit_types,
            "average_duration": sum(durations) / len(durations) if durations else 0,
            "average_segments_per_unit": sum(segment_counts) / len(segment_counts) if segment_counts else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "incomplete_units": incomplete_count,
            "completeness_rate": ((len(units) - incomplete_count) / len(units) * 100) if units else 0
        }