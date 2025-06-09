"""Transcript Stitching System for Podcast Transcription Pipeline.

This module provides tools to seamlessly combine multiple transcript segments
into a single coherent transcript, handling overlaps and maintaining consistency.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

from src.utils.logging import get_logger
from src.transcript_analyzer import TranscriptAnalyzer

logger = get_logger('transcript_stitcher')


class TranscriptStitcher:
    """Seamlessly combines initial and continuation transcript responses."""
    
    def __init__(self, overlap_tolerance: float = 10.0):
        """Initialize the transcript stitcher.
        
        Args:
            overlap_tolerance: Tolerance in seconds for detecting overlaps
        """
        self.overlap_tolerance = overlap_tolerance
        self.analyzer = TranscriptAnalyzer()
        
        logger.info(f"Initialized TranscriptStitcher with {overlap_tolerance}s overlap tolerance")
    
    def combine_segments(self, segments: List[str], episode_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Combine transcript segments into a single coherent transcript.
        
        Args:
            segments: List of transcript segments to combine
            episode_metadata: Optional episode metadata for debugging
            
        Returns:
            Combined transcript with duplicates removed and consistency maintained
        """
        if not segments:
            return ""
        
        if len(segments) == 1:
            return segments[0]
        
        try:
            logger.info(f"Stitching {len(segments)} transcript segments")
            
            # Parse all segments into structured data
            parsed_segments = []
            for i, segment in enumerate(segments):
                parsed = self._parse_segment(segment, i)
                parsed_segments.append(parsed)
                logger.debug(f"Segment {i+1}: {len(parsed['lines'])} lines, "
                           f"timestamps: {parsed['first_timestamp']:.1f}s - {parsed['last_timestamp']:.1f}s")
            
            # Remove overlapping content between segments
            deduplicated_segments = self._remove_overlaps(parsed_segments)
            
            # Maintain speaker continuity across segments
            speaker_normalized_segments = self._normalize_speakers(deduplicated_segments)
            
            # Handle timestamp gaps and overlaps
            timestamp_adjusted_segments = self._adjust_timestamps(speaker_normalized_segments)
            
            # Rebuild the final transcript
            final_transcript = self._rebuild_transcript(timestamp_adjusted_segments)
            
            # Validate the final result
            validation = self.analyzer.validate_transcript_format(final_transcript)
            logger.info(f"Stitched transcript: {validation['line_count']} lines, "
                       f"{validation['timestamp_count']} timestamps, "
                       f"format: {validation['estimated_format']}")
            
            return final_transcript
            
        except Exception as e:
            logger.error(f"Failed to stitch transcripts: {e}")
            # Fallback to simple concatenation
            return self._simple_concatenate(segments)
    
    def _parse_segment(self, segment: str, segment_index: int) -> Dict[str, Any]:
        """Parse a transcript segment into structured data.
        
        Args:
            segment: Raw transcript segment text
            segment_index: Index of this segment
            
        Returns:
            Dictionary with parsed segment data
        """
        parsed = {
            "index": segment_index,
            "raw_text": segment,
            "lines": [],
            "timestamps": [],
            "speakers": set(),
            "first_timestamp": 0.0,
            "last_timestamp": 0.0
        }
        
        if not segment:
            return parsed
        
        # Split into lines and analyze each
        lines = [line.strip() for line in segment.split('\n') if line.strip()]
        
        for line in lines:
            line_data = self._parse_line(line)
            if line_data:
                parsed["lines"].append(line_data)
                
                if line_data["timestamp"]:
                    parsed["timestamps"].append(line_data["timestamp"])
                
                if line_data["speaker"]:
                    parsed["speakers"].add(line_data["speaker"])
        
        # Set first and last timestamps
        if parsed["timestamps"]:
            parsed["first_timestamp"] = min(parsed["timestamps"])
            parsed["last_timestamp"] = max(parsed["timestamps"])
        
        return parsed
    
    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line of transcript.
        
        Args:
            line: Single line of transcript text
            
        Returns:
            Dictionary with line data or None if not parseable
        """
        if not line:
            return None
        
        line_data = {
            "raw_text": line,
            "timestamp": None,
            "speaker": None,
            "content": line,
            "is_timestamp_line": False,
            "is_speaker_line": False
        }
        
        # Try to extract timestamp
        timestamp = self._extract_timestamp_from_line(line)
        if timestamp:
            line_data["timestamp"] = timestamp
            line_data["is_timestamp_line"] = True
        
        # Try to extract speaker
        speaker = self._extract_speaker_from_line(line)
        if speaker:
            line_data["speaker"] = speaker
            line_data["is_speaker_line"] = True
        
        # Extract clean content (remove timestamp and speaker markers)
        clean_content = self._clean_line_content(line)
        line_data["content"] = clean_content
        
        return line_data
    
    def _extract_timestamp_from_line(self, line: str) -> Optional[float]:
        """Extract timestamp from a line of text.
        
        Args:
            line: Line of text that may contain a timestamp
            
        Returns:
            Timestamp in seconds or None if not found
        """
        # Use the same patterns as TranscriptAnalyzer
        patterns = [
            r'(\d{1,2}):(\d{2}):(\d{2})',  # HH:MM:SS
            r'(\d{1,2}):(\d{2})',          # MM:SS
            r'\[(\d{1,2}):(\d{2}):(\d{2})\]',  # [HH:MM:SS]
            r'\[(\d{1,2}):(\d{2})\]',          # [MM:SS]
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, groups)
                        return hours * 3600 + minutes * 60 + seconds
                    elif len(groups) == 2:  # MM:SS
                        minutes, seconds = map(int, groups)
                        return minutes * 60 + seconds
                except ValueError:
                    continue
        
        return None
    
    def _extract_speaker_from_line(self, line: str) -> Optional[str]:
        """Extract speaker identifier from a line of text.
        
        Args:
            line: Line of text that may contain speaker information
            
        Returns:
            Speaker identifier or None if not found
        """
        # Common speaker patterns
        patterns = [
            r'^([A-Z][a-zA-Z\s]+):\s*',  # Name: at start of line
            r'Speaker\s*(\d+)',          # Speaker 1, Speaker 2, etc.
            r'SPEAKER\s*(\d+)',          # SPEAKER 1, SPEAKER 2, etc.
            r'\[([A-Z][a-zA-Z\s]+)\]',   # [Name]
            r'Host:',                    # Host:
            r'Guest:',                   # Guest:
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        
        return None
    
    def _clean_line_content(self, line: str) -> str:
        """Clean line content by removing timestamp and speaker markers.
        
        Args:
            line: Raw line text
            
        Returns:
            Cleaned content text
        """
        cleaned = line
        
        # Remove timestamp patterns
        timestamp_patterns = [
            r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*',
            r'At\s+\d{1,2}:\d{2}(?::\d{2})?\s*',
            r'Time:\s*\d{1,2}:\d{2}(?::\d{2})?\s*',
        ]
        
        for pattern in timestamp_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove speaker patterns
        speaker_patterns = [
            r'^[A-Z][a-zA-Z\s]+:\s*',  # Name: at start
            r'^\[?Speaker\s*\d+\]?\s*:?\s*',  # Speaker N
            r'^\[?SPEAKER\s*\d+\]?\s*:?\s*',  # SPEAKER N
            r'^\[?Host\]?\s*:?\s*',     # Host
            r'^\[?Guest\]?\s*:?\s*',    # Guest
        ]
        
        for pattern in speaker_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def _remove_overlaps(self, parsed_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove overlapping content between segments.
        
        Args:
            parsed_segments: List of parsed segment dictionaries
            
        Returns:
            List of deduplicated segments
        """
        if len(parsed_segments) <= 1:
            return parsed_segments
        
        deduplicated = [parsed_segments[0]]  # Always keep first segment
        
        for current_segment in parsed_segments[1:]:
            last_segment = deduplicated[-1]
            
            # Check for overlap based on timestamps
            overlap_detected = self._detect_overlap(last_segment, current_segment)
            
            if overlap_detected:
                # Remove overlapping lines from current segment
                filtered_segment = self._filter_overlapping_lines(last_segment, current_segment)
                if filtered_segment["lines"]:  # Only add if there are remaining lines
                    deduplicated.append(filtered_segment)
            else:
                deduplicated.append(current_segment)
        
        logger.info(f"Overlap removal: {len(parsed_segments)} -> {len(deduplicated)} segments")
        return deduplicated
    
    def _detect_overlap(self, segment1: Dict[str, Any], segment2: Dict[str, Any]) -> bool:
        """Detect if two segments have overlapping content.
        
        Args:
            segment1: First segment data
            segment2: Second segment data
            
        Returns:
            True if overlap is detected
        """
        # Check timestamp overlap
        if (segment1["timestamps"] and segment2["timestamps"] and
            segment1["last_timestamp"] > 0 and segment2["first_timestamp"] > 0):
            
            overlap_seconds = segment1["last_timestamp"] - segment2["first_timestamp"]
            if -self.overlap_tolerance <= overlap_seconds <= self.overlap_tolerance:
                return True
        
        # Check content similarity (last lines of segment1 vs first lines of segment2)
        if segment1["lines"] and segment2["lines"]:
            last_lines = segment1["lines"][-3:]  # Last 3 lines
            first_lines = segment2["lines"][:3]   # First 3 lines
            
            for last_line in last_lines:
                for first_line in first_lines:
                    if self._are_lines_similar(last_line["content"], first_line["content"]):
                        return True
        
        return False
    
    def _are_lines_similar(self, line1: str, line2: str, threshold: float = 0.8) -> bool:
        """Check if two lines are similar enough to be considered duplicates.
        
        Args:
            line1: First line content
            line2: Second line content
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            True if lines are similar
        """
        if not line1 or not line2:
            return False
        
        # Simple similarity check
        clean1 = line1.lower().strip()
        clean2 = line2.lower().strip()
        
        if clean1 == clean2:
            return True
        
        # Check if one is contained in the other
        shorter, longer = (clean1, clean2) if len(clean1) < len(clean2) else (clean2, clean1)
        if shorter and shorter in longer:
            return len(shorter) / len(longer) > threshold
        
        return False
    
    def _filter_overlapping_lines(self, previous_segment: Dict[str, Any], 
                                 current_segment: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out overlapping lines from current segment.
        
        Args:
            previous_segment: Previous segment data
            current_segment: Current segment to filter
            
        Returns:
            Filtered segment with overlaps removed
        """
        filtered_segment = current_segment.copy()
        filtered_lines = []
        
        # Get last few lines from previous segment for comparison
        previous_lines = previous_segment["lines"][-5:] if previous_segment["lines"] else []
        previous_content = [line["content"].lower().strip() for line in previous_lines]
        
        # Filter current segment lines
        for line in current_segment["lines"]:
            line_content = line["content"].lower().strip()
            
            # Skip if this line is too similar to any recent previous line
            is_duplicate = any(
                self._are_lines_similar(line_content, prev_content)
                for prev_content in previous_content
            )
            
            if not is_duplicate:
                filtered_lines.append(line)
        
        filtered_segment["lines"] = filtered_lines
        
        # Recalculate timestamps
        timestamps = [line["timestamp"] for line in filtered_lines if line["timestamp"]]
        if timestamps:
            filtered_segment["timestamps"] = timestamps
            filtered_segment["first_timestamp"] = min(timestamps)
            filtered_segment["last_timestamp"] = max(timestamps)
        
        logger.debug(f"Filtered segment: {len(current_segment['lines'])} -> {len(filtered_lines)} lines")
        return filtered_segment
    
    def _normalize_speakers(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize speaker identifiers across segments.
        
        Args:
            segments: List of segment dictionaries
            
        Returns:
            List of segments with normalized speaker names
        """
        # For now, keep speakers as-is
        # This could be enhanced to map Speaker 1 -> actual names consistently
        logger.debug("Speaker normalization: maintaining original speaker labels")
        return segments
    
    def _adjust_timestamps(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adjust timestamps to handle gaps and overlaps.
        
        Args:
            segments: List of segment dictionaries
            
        Returns:
            List of segments with adjusted timestamps
        """
        # For now, keep timestamps as-is
        # This could be enhanced to smooth timestamp transitions
        logger.debug("Timestamp adjustment: maintaining original timestamps")
        return segments
    
    def _rebuild_transcript(self, segments: List[Dict[str, Any]]) -> str:
        """Rebuild transcript from processed segments.
        
        Args:
            segments: List of processed segment dictionaries
            
        Returns:
            Final combined transcript
        """
        lines = []
        
        for segment in segments:
            if segment["lines"]:
                # Add segment separator comment
                if lines:  # Not the first segment
                    lines.append("")  # Empty line between segments
                
                # Add all lines from this segment
                for line_data in segment["lines"]:
                    lines.append(line_data["raw_text"])
        
        return '\n'.join(lines)
    
    def _simple_concatenate(self, segments: List[str]) -> str:
        """Simple fallback concatenation of transcript segments.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Concatenated transcript
        """
        logger.warning("Using simple concatenation fallback")
        return "\n\n".join(segment.strip() for segment in segments if segment.strip())
    
    def validate_stitched_transcript(self, transcript: str, 
                                   original_segments: List[str]) -> Dict[str, Any]:
        """Validate the quality of a stitched transcript.
        
        Args:
            transcript: Final stitched transcript
            original_segments: Original segment list
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_segments_count": len(original_segments),
            "final_transcript_length": len(transcript),
            "format_validation": {},
            "issues": [],
            "quality_score": 0.0
        }
        
        # Use analyzer for format validation
        validation["format_validation"] = self.analyzer.validate_transcript_format(transcript)
        
        # Check for obvious stitching issues
        lines = transcript.split('\n')
        
        # Look for duplicate consecutive lines
        duplicate_count = 0
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i].strip() == lines[i-1].strip():
                duplicate_count += 1
        
        if duplicate_count > 0:
            validation["issues"].append(f"Found {duplicate_count} duplicate consecutive lines")
        
        # Calculate quality score
        score = validation["format_validation"].get("character_count", 0) / 1000 * 10  # Base score
        
        if validation["format_validation"]["has_timestamps"]:
            score += 30
        if validation["format_validation"]["has_speaker_identification"]:
            score += 30
        if duplicate_count == 0:
            score += 20
        
        validation["quality_score"] = min(100, score)
        
        logger.info(f"Stitching validation: score {validation['quality_score']:.1f}/100, "
                   f"{len(validation['issues'])} issues")
        
        return validation