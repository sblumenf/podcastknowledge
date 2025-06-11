"""VTT (WebVTT) file parser for processing transcript files with memory optimization."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator
import logging
import re
import gc
import json

try:
    import psutil
except ImportError:
    psutil = None

from src.core.exceptions import ValidationError
from src.core.interfaces import TranscriptSegment

logger = logging.getLogger(__name__)


@dataclass
class VTTCue:
    """Represents a single cue (caption) in a VTT file."""
    index: int
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    settings: Optional[Dict[str, str]] = None


class VTTParser:
    """Parser for WebVTT (Web Video Text Tracks) format files with memory optimization."""
    
    # Regex patterns for VTT parsing
    TIMESTAMP_PATTERN = re.compile(
        r'(\d+):(\d{2}):(\d{2})\.(\d{3})'
    )
    CUE_TIMING_PATTERN = re.compile(
        r'([\d:\.]+)\s*-->\s*([\d:\.]+)(?:\s+(.+))?'
    )
    SPEAKER_PATTERN = re.compile(
        r'<v\s*([^>]*)>'
    )
    
    def __init__(self, batch_size: int = 100, max_segment_buffer: int = 1000,
                 enable_memory_monitoring: bool = True) -> None:
        """Initialize VTT parser with memory optimization settings.
        
        Args:
            batch_size: Number of captions to process at once
            max_segment_buffer: Maximum segments to keep in memory
            enable_memory_monitoring: Log memory usage during processing
        """
        self.cues: List[VTTCue] = []
        self.batch_size = batch_size
        self.max_segment_buffer = max_segment_buffer
        self.enable_memory_monitoring = enable_memory_monitoring
        self._processed_segments = 0
    
    def _log_memory_usage(self, stage: str):
        """Log current memory usage."""
        if self.enable_memory_monitoring and psutil:
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory usage at {stage}: {memory_mb:.2f} MB")
            except:
                pass  # Error getting memory info
    
    def parse_file(self, file_path: Path) -> List[TranscriptSegment]:
        """Parse a VTT file and return transcript segments.
        
        Args:
            file_path: Path to the VTT file
            
        Returns:
            List of TranscriptSegment objects
            
        Raises:
            ValidationError: If file format is invalid
        """
        if not file_path.exists():
            raise ValidationError(f"VTT file not found: {file_path}")
        
        # For small files, use existing method
        file_size_mb = file_path.stat().st_size / 1024 / 1024
        if file_size_mb < 10:  # Less than 10MB, use regular parsing
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                raise ValidationError(f"Failed to read VTT file: {e}")
            
            return self.parse_content(content)
        else:
            # For large files, use streaming
            logger.info(f"Using streaming parser for large file ({file_size_mb:.1f} MB)")
            return list(self.parse_file_streaming(file_path))
    
    def parse_file_with_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Parse a VTT file and return both metadata and transcript segments.
        
        Args:
            file_path: Path to the VTT file
            
        Returns:
            Dict containing 'metadata' and 'segments' keys
            
        Raises:
            ValidationError: If file format is invalid
        """
        if not file_path.exists():
            raise ValidationError(f"VTT file not found: {file_path}")
        
        # For now, always use full parsing for metadata extraction
        # TODO: Implement streaming metadata extraction for large files
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise ValidationError(f"Failed to read VTT file: {e}")
        
        return self.parse_content_with_metadata(content)
    
    def parse_content(self, content: str) -> List[TranscriptSegment]:
        """Parse VTT content and return transcript segments.
        
        Args:
            content: VTT file content as string
            
        Returns:
            List of TranscriptSegment objects
            
        Raises:
            ValidationError: If content format is invalid
        """
        # Validate VTT header
        if not content.strip().startswith('WEBVTT'):
            raise ValidationError("Invalid VTT file: Missing WEBVTT header")
        
        # Parse cues
        self.cues = self._parse_cues(content)
        
        # Convert to transcript segments
        return self._convert_to_segments(self.cues)
    
    def parse_content_with_metadata(self, content: str) -> Dict[str, Any]:
        """Parse VTT content and return both metadata and transcript segments.
        
        Args:
            content: VTT file content as string
            
        Returns:
            Dict containing 'metadata' and 'segments' keys
            
        Raises:
            ValidationError: If content format is invalid
        """
        # Validate VTT header
        if not content.strip().startswith('WEBVTT'):
            raise ValidationError("Invalid VTT file: Missing WEBVTT header")
        
        # Extract metadata from NOTE blocks
        metadata = self._parse_note_blocks(content)
        
        # Parse cues
        self.cues = self._parse_cues(content)
        
        # Convert to transcript segments
        segments = self._convert_to_segments(self.cues)
        
        return {
            'metadata': metadata,
            'segments': segments
        }
    
    def _parse_cues(self, content: str) -> List[VTTCue]:
        """Parse VTT cues from content.
        
        Args:
            content: VTT file content
            
        Returns:
            List of VTTCue objects
        """
        cues = []
        lines = content.strip().split('\n')
        
        i = 0
        cue_index = 0
        
        # Skip header and any metadata
        while i < len(lines) and not self._is_timestamp_line(lines[i]):
            i += 1
        
        # Parse cues
        while i < len(lines):
            # Skip empty lines
            if not lines[i].strip():
                i += 1
                continue
            
            # Check if this is a cue identifier (optional)
            cue_id = None
            if i < len(lines) - 1 and self._is_timestamp_line(lines[i + 1]):
                cue_id = lines[i].strip()
                i += 1
            
            # Parse timestamp line
            if i < len(lines) and self._is_timestamp_line(lines[i]):
                timing_match = self.CUE_TIMING_PATTERN.match(lines[i].strip())
                if timing_match:
                    start_str = timing_match.group(1)
                    end_str = timing_match.group(2)
                    settings_str = timing_match.group(3)
                    
                    start_time = self._parse_timestamp(start_str)
                    end_time = self._parse_timestamp(end_str)
                    settings = self._parse_settings(settings_str) if settings_str else None
                    
                    i += 1
                    
                    # Collect cue text (can be multiple lines)
                    text_lines = []
                    while i < len(lines) and lines[i].strip() and not self._is_timestamp_line(lines[i]):
                        text_lines.append(lines[i])
                        i += 1
                    
                    if text_lines:
                        text = '\n'.join(text_lines)
                        speaker = self._extract_speaker(text)
                        # Remove speaker markup from text
                        text = self.SPEAKER_PATTERN.sub('', text).strip()
                        
                        cue = VTTCue(
                            index=cue_index,
                            start_time=start_time,
                            end_time=end_time,
                            text=text,
                            speaker=speaker,
                            settings=settings
                        )
                        cues.append(cue)
                        cue_index += 1
                else:
                    logger.warning(f"Invalid timestamp format at line {i}: {lines[i]}")
                    i += 1
            else:
                i += 1
        
        return cues
    
    def _is_timestamp_line(self, line: str) -> bool:
        """Check if a line contains a timestamp."""
        return '-->' in line
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse a VTT timestamp string to seconds.
        
        Args:
            timestamp_str: Timestamp in format HH:MM:SS.mmm or MM:SS.mmm
            
        Returns:
            Time in seconds as float
        """
        match = self.TIMESTAMP_PATTERN.match(timestamp_str.strip())
        if not match:
            raise ValidationError(f"Invalid timestamp format: {timestamp_str}")
        
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        milliseconds = int(match.group(4))
        
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
        return total_seconds
    
    def _parse_settings(self, settings_str: str) -> Dict[str, str]:
        """Parse VTT cue settings.
        
        Args:
            settings_str: Settings string from timing line
            
        Returns:
            Dictionary of settings
        """
        settings = {}
        if settings_str:
            # Parse settings like position:50% align:center
            parts = settings_str.split()
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    settings[key] = value
        return settings
    
    def _extract_speaker(self, text: str) -> Optional[str]:
        """Extract speaker name from VTT voice span.
        
        Args:
            text: Cue text that may contain <v Speaker> markup
            
        Returns:
            Speaker name if found, None otherwise
        """
        match = self.SPEAKER_PATTERN.search(text)
        if match:
            speaker = match.group(1).strip()
            # Return empty string for empty speaker tags
            return speaker if speaker else ""
        return None
    
    def _parse_note_blocks(self, content: str) -> Dict[str, Any]:
        """Parse NOTE blocks from VTT content to extract metadata.
        
        Args:
            content: VTT file content
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        lines = content.strip().split('\n')
        
        i = 0
        # Skip WEBVTT header
        while i < len(lines) and lines[i].strip().startswith('WEBVTT'):
            i += 1
        
        # Look for NOTE blocks
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop when we hit the first timestamp
            if self._is_timestamp_line(line):
                break
            
            # Look for NOTE blocks
            if line.startswith('NOTE'):
                note_type = line[4:].strip()  # Get text after "NOTE"
                i += 1
                
                # Collect NOTE content until empty line
                note_content = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('NOTE'):
                    note_content.append(lines[i])
                    i += 1
                
                # Process based on note type
                if note_type == 'JSON Metadata' and note_content:
                    # Parse JSON metadata block
                    try:
                        json_str = '\n'.join(note_content)
                        json_data = json.loads(json_str)
                        metadata.update(json_data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON metadata: {e}")
                
                elif note_content:
                    # Parse human-readable metadata
                    for content_line in note_content:
                        # Look for patterns like "YouTube URL: <url>"
                        if ':' in content_line:
                            key, value = content_line.split(':', 1)
                            key = key.strip().lower().replace(' ', '_')
                            value = value.strip()
                            
                            # Special handling for known fields
                            if key == 'youtube_url' and 'youtube_url' not in metadata:
                                metadata['youtube_url'] = value
                            elif key == 'description' and 'description' not in metadata:
                                metadata['description'] = value
                            elif key == 'original_url' and 'original_url' not in metadata:
                                metadata['original_url'] = value
                            elif key not in metadata:
                                metadata[key] = value
            else:
                i += 1
        
        return metadata
    
    def _convert_to_segments(self, cues: List[VTTCue]) -> List[TranscriptSegment]:
        """Convert VTT cues to transcript segments.
        
        Args:
            cues: List of VTT cues
            
        Returns:
            List of TranscriptSegment objects
        """
        segments = []
        
        for cue in cues:
            segment = TranscriptSegment(
                id=f"seg_{cue.index}",
                text=cue.text,
                start_time=cue.start_time,
                end_time=cue.end_time,
                speaker=cue.speaker,
                confidence=1.0  # VTT files don't have confidence scores
            )
            segments.append(segment)
        
        return segments
    
    def parse_file_streaming(self, file_path: Path) -> Iterator[TranscriptSegment]:
        """Parse a VTT file using streaming to minimize memory usage.
        
        Args:
            file_path: Path to the VTT file
            
        Yields:
            TranscriptSegment objects as they are parsed
            
        Raises:
            ValidationError: If file format is invalid
        """
        self._log_memory_usage("start_streaming")
        
        if not file_path.exists():
            raise ValidationError(f"VTT file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Check header
                first_line = f.readline().strip()
                if not first_line.startswith('WEBVTT'):
                    raise ValidationError("Invalid VTT file: Missing WEBVTT header")
                
                # Skip header metadata
                line = f.readline()
                while line and line.strip() and not self._is_timestamp_line(line):
                    line = f.readline()
                
                # Process cues in batches
                batch_cues = []
                cue_index = 0
                lines_buffer = []
                
                while True:
                    line = f.readline()
                    if not line:  # EOF
                        # Process any remaining buffer
                        if lines_buffer:
                            cue = self._parse_cue_from_lines(lines_buffer, cue_index)
                            if cue:
                                batch_cues.append(cue)
                                cue_index += 1
                        
                        # Yield final batch
                        if batch_cues:
                            for segment in self._convert_to_segments(batch_cues):
                                yield segment
                                self._processed_segments += 1
                        break
                    
                    line = line.rstrip('\n')
                    
                    # Empty line marks end of cue
                    if not line.strip() and lines_buffer:
                        cue = self._parse_cue_from_lines(lines_buffer, cue_index)
                        if cue:
                            batch_cues.append(cue)
                            cue_index += 1
                            
                            # Process batch when full
                            if len(batch_cues) >= self.batch_size:
                                for segment in self._convert_to_segments(batch_cues):
                                    yield segment
                                    self._processed_segments += 1
                                
                                # Clear batch and hint garbage collection
                                batch_cues = []
                                if self._processed_segments % 500 == 0:
                                    gc.collect()
                                    self._log_memory_usage(f"after_{self._processed_segments}_segments")
                        
                        lines_buffer = []
                    else:
                        lines_buffer.append(line)
                
                self._log_memory_usage("end_streaming")
                
        except Exception as e:
            raise ValidationError(f"Failed to parse VTT file: {e}")
    
    def _parse_cue_from_lines(self, lines: List[str], cue_index: int) -> Optional[VTTCue]:
        """Parse a single cue from buffered lines.
        
        Args:
            lines: Buffered lines for a cue
            cue_index: Current cue index
            
        Returns:
            VTTCue object or None if invalid
        """
        if not lines:
            return None
        
        i = 0
        
        # Skip cue identifier if present
        if i < len(lines) - 1 and self._is_timestamp_line(lines[i + 1]):
            i += 1
        
        # Find timestamp line
        while i < len(lines) and not self._is_timestamp_line(lines[i]):
            i += 1
        
        if i >= len(lines):
            return None
        
        # Parse timestamp
        timing_match = self.CUE_TIMING_PATTERN.match(lines[i].strip())
        if not timing_match:
            return None
        
        start_time = self._parse_timestamp(timing_match.group(1))
        end_time = self._parse_timestamp(timing_match.group(2))
        settings = self._parse_settings(timing_match.group(3)) if timing_match.group(3) else None
        
        i += 1
        
        # Collect text lines
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        
        if not text_lines:
            return None
        
        text = '\n'.join(text_lines)
        speaker = self._extract_speaker(text)
        text = self.SPEAKER_PATTERN.sub('', text).strip()
        
        return VTTCue(
            index=cue_index,
            start_time=start_time,
            end_time=end_time,
            text=text,
            speaker=speaker,
            settings=settings
        )
    
    def merge_short_segments(self, 
                           segments: List[TranscriptSegment], 
                           min_duration: float = 2.0) -> List[TranscriptSegment]:
        """Merge segments shorter than minimum duration with adjacent segments.
        
        Args:
            segments: List of transcript segments
            min_duration: Minimum segment duration in seconds
            
        Returns:
            List of merged segments
        """
        if not segments:
            return segments
        
        merged = []
        i = 0
        
        while i < len(segments):
            current = segments[i]
            current_duration = current.end_time - current.start_time
            
            # Start with current segment
            merged_text = current.text
            start_time = current.start_time
            end_time = current.end_time
            speaker = current.speaker
            min_confidence = current.confidence or 1.0
            
            # Look ahead to merge consecutive short segments with same speaker
            j = i + 1
            while j < len(segments):
                # Check if we can merge with next segment
                if (segments[j].speaker == speaker and
                    segments[j - 1].end_time == segments[j].start_time):  # Consecutive
                    
                    # Check if either current accumulated or next segment is short
                    accumulated_duration = end_time - start_time
                    next_duration = segments[j].end_time - segments[j].start_time
                    
                    if accumulated_duration < min_duration or next_duration < min_duration:
                        # Merge this segment
                        merged_text += f" {segments[j].text}"
                        end_time = segments[j].end_time
                        min_confidence = min(min_confidence, segments[j].confidence or 1.0)
                        j += 1
                    else:
                        # Both are long enough, stop merging
                        break
                else:
                    # Different speaker or not consecutive, stop merging
                    break
            
            # Create the merged segment
            merged_segment = TranscriptSegment(
                id=f"seg_{len(merged)}",
                text=merged_text,
                start_time=start_time,
                end_time=end_time,
                speaker=speaker,
                confidence=min_confidence
            )
            merged.append(merged_segment)
            
            # Move to next unprocessed segment
            i = j
        
        return merged
    
    def normalize_segment(self, segment: Dict[str, Any]) -> TranscriptSegment:
        """Normalize a segment dictionary to TranscriptSegment.
        
        Handles various input formats and field names.
        
        Args:
            segment: Dictionary with segment data
            
        Returns:
            Normalized TranscriptSegment
        """
        # Handle different field names for timestamps
        start_time = segment.get('start_time') or segment.get('start', 0.0)
        end_time = segment.get('end_time') or segment.get('end', 0.0)
        
        # Handle segment ID
        segment_id = segment.get('id', f"seg_{segment.get('index', 0)}")
        
        return TranscriptSegment(
            id=segment_id,
            text=segment.get('text', ''),
            start_time=float(start_time),
            end_time=float(end_time),
            speaker=segment.get('speaker'),
            confidence=segment.get('confidence', 1.0)
        )