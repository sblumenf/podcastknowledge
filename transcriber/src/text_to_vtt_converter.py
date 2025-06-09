"""Text-to-VTT Converter for Podcast Transcription Pipeline.

This module converts raw transcript text with timestamps and speaker identification
into properly formatted WebVTT files for media player compatibility.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

from src.utils.logging import get_logger
from src.transcript_analyzer import TranscriptAnalyzer

logger = get_logger('text_to_vtt_converter')


class TextToVTTConverter:
    """Converts raw transcript text to WebVTT format."""
    
    def __init__(self, max_cue_duration: float = 7.0, max_chars_per_line: int = 80):
        """Initialize the text-to-VTT converter.
        
        Args:
            max_cue_duration: Maximum duration for each VTT cue in seconds
            max_chars_per_line: Maximum characters per line in VTT cues
        """
        self.max_cue_duration = max_cue_duration
        self.max_chars_per_line = max_chars_per_line
        self.analyzer = TranscriptAnalyzer()
        
        logger.info(f"Initialized TextToVTTConverter with {max_cue_duration}s max cue duration")
    
    def convert(self, raw_transcript: str, episode_metadata: Dict[str, Any]) -> str:
        """Convert raw transcript to WebVTT format.
        
        Args:
            raw_transcript: Raw transcript text with timestamps and speakers
            episode_metadata: Episode metadata for VTT header
            
        Returns:
            WebVTT-formatted transcript
        """
        if not raw_transcript:
            logger.warning("Empty transcript provided for conversion")
            return self._create_empty_vtt(episode_metadata)
        
        try:
            logger.info("Converting raw transcript to VTT format")
            
            # Parse the raw transcript
            parsed_data = self._parse_raw_transcript(raw_transcript)
            
            if not parsed_data["segments"]:
                logger.warning("No segments found in raw transcript")
                return self._create_empty_vtt(episode_metadata)
            
            # Generate VTT cues from parsed segments
            vtt_cues = self._generate_vtt_cues(parsed_data["segments"])
            
            # Build the complete VTT file
            vtt_content = self._build_vtt_file(vtt_cues, episode_metadata)
            
            # Validate the generated VTT
            validation = self._validate_vtt(vtt_content)
            logger.info(f"Generated VTT: {validation['cue_count']} cues, "
                       f"{validation['duration']:.1f}s total duration")
            
            return vtt_content
            
        except Exception as e:
            logger.error(f"Failed to convert transcript to VTT: {e}")
            return self._create_empty_vtt(episode_metadata)
    
    def _parse_raw_transcript(self, raw_transcript: str) -> Dict[str, Any]:
        """Parse raw transcript into structured segments.
        
        Args:
            raw_transcript: Raw transcript text
            
        Returns:
            Dictionary with parsed transcript data
        """
        parsed = {
            "segments": [],
            "speakers": set(),
            "total_duration": 0.0,
            "format_detected": "unknown"
        }
        
        lines = [line.strip() for line in raw_transcript.split('\n') if line.strip()]
        
        current_segment = None
        
        for line in lines:
            # Try to parse this line
            line_data = self._parse_transcript_line(line)
            
            if line_data["has_timestamp"]:
                # Start a new segment
                if current_segment:
                    parsed["segments"].append(current_segment)
                
                current_segment = {
                    "start_time": line_data["timestamp"],
                    "end_time": line_data["timestamp"] + self.max_cue_duration,  # Default end time
                    "speaker": line_data["speaker"],
                    "text_lines": [line_data["text"]] if line_data["text"] else [],
                    "raw_lines": [line]
                }
                
                if line_data["speaker"]:
                    parsed["speakers"].add(line_data["speaker"])
            
            elif current_segment and line_data["text"]:
                # Add text to current segment
                current_segment["text_lines"].append(line_data["text"])
                current_segment["raw_lines"].append(line)
                
                if line_data["speaker"]:
                    parsed["speakers"].add(line_data["speaker"])
                    # Update speaker if this line has speaker info
                    if not current_segment["speaker"]:
                        current_segment["speaker"] = line_data["speaker"]
        
        # Add the last segment
        if current_segment:
            parsed["segments"].append(current_segment)
        
        # Adjust end times based on next segment start times
        self._adjust_segment_end_times(parsed["segments"])
        
        # Calculate total duration
        if parsed["segments"]:
            parsed["total_duration"] = max(seg["end_time"] for seg in parsed["segments"])
        
        logger.info(f"Parsed transcript: {len(parsed['segments'])} segments, "
                   f"{len(parsed['speakers'])} speakers, {parsed['total_duration']:.1f}s duration")
        
        return parsed
    
    def _parse_transcript_line(self, line: str) -> Dict[str, Any]:
        """Parse a single line of transcript.
        
        Args:
            line: Single line of transcript text
            
        Returns:
            Dictionary with line parsing results
        """
        line_data = {
            "raw_line": line,
            "has_timestamp": False,
            "timestamp": None,
            "speaker": None,
            "text": "",
            "is_empty": len(line.strip()) == 0
        }
        
        if line_data["is_empty"]:
            return line_data
        
        # Extract timestamp
        timestamp = self._extract_timestamp_from_line(line)
        if timestamp is not None:
            line_data["has_timestamp"] = True
            line_data["timestamp"] = timestamp
        
        # Extract speaker
        speaker = self._extract_speaker_from_line(line)
        if speaker:
            line_data["speaker"] = speaker
        
        # Extract clean text content
        text = self._extract_text_content(line)
        line_data["text"] = text
        
        return line_data
    
    def _extract_timestamp_from_line(self, line: str) -> Optional[float]:
        """Extract timestamp from a line and convert to seconds.
        
        Args:
            line: Line of text that may contain a timestamp
            
        Returns:
            Timestamp in seconds or None if not found
        """
        # Timestamp patterns
        patterns = [
            # [HH:MM:SS] or [MM:SS]
            r'\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]',
            # (HH:MM:SS) or (MM:SS)
            r'\((\d{1,2}):(\d{2})(?::(\d{2}))?\)',
            # HH:MM:SS or MM:SS at start of line
            r'^(\d{1,2}):(\d{2})(?::(\d{2}))?',
            # At HH:MM:SS or At MM:SS
            r'[Aa]t\s+(\d{1,2}):(\d{2})(?::(\d{2}))?',
            # Time: HH:MM:SS or Time: MM:SS
            r'[Tt]ime:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    groups = [g for g in match.groups() if g is not None]
                    
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
        """Extract speaker identifier from a line.
        
        Args:
            line: Line of text that may contain speaker information
            
        Returns:
            Speaker identifier or None if not found
        """
        # First remove any timestamp from the beginning
        line_without_timestamp = line
        timestamp_patterns = [
            r'^\[\d{1,2}:\d{2}(?::\d{2})?\]\s*',  # [HH:MM:SS] or [MM:SS]
            r'^\(\d{1,2}:\d{2}(?::\d{2})?\)\s*',  # (HH:MM:SS) or (MM:SS)
            r'^\d{1,2}:\d{2}(?::\d{2})?\s+',      # HH:MM:SS or MM:SS
        ]
        
        for pattern in timestamp_patterns:
            line_without_timestamp = re.sub(pattern, '', line_without_timestamp)
        
        # Speaker patterns (now applied to line without timestamp)
        patterns = [
            r'^([A-Z][a-zA-Z\s\.]+?):\s*',        # Name: (e.g., "Mel Robbins:" or "Dr. Smith:")
            r'^(Speaker\s*\d+):\s*',               # Speaker 1:
            r'^(SPEAKER\s*\d+):\s*',               # SPEAKER 1:
            r'^(Host):\s*',                        # Host:
            r'^(Guest\s*(?:Expert)?):?\s*',       # Guest: or Guest Expert:
            r'^\[([A-Z][a-zA-Z\s\.]+?)\]\s*:\s*', # [Name]:
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line_without_timestamp)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_text_content(self, line: str) -> str:
        """Extract clean text content from a line.
        
        Args:
            line: Raw line text
            
        Returns:
            Clean text content
        """
        text = line
        
        # Remove timestamp patterns
        timestamp_patterns = [
            r'^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*',     # [HH:MM:SS] or HH:MM:SS at start
            r'^[Aa]t\s+\d{1,2}:\d{2}(?::\d{2})?\s*',   # At HH:MM:SS
            r'^[Tt]ime:\s*\d{1,2}:\d{2}(?::\d{2})?\s*', # Time: HH:MM:SS
        ]
        
        for pattern in timestamp_patterns:
            text = re.sub(pattern, '', text)
        
        # Remove speaker patterns (must match exactly how speakers appear)
        speaker_patterns = [
            r'^([A-Z][a-zA-Z\s\.]+?):\s*',        # Name: (e.g., "Mel Robbins:" or "Dr. Smith:")
            r'^(Speaker\s*\d+):\s*',               # Speaker 1:
            r'^(SPEAKER\s*\d+):\s*',               # SPEAKER 1:
            r'^(Host):\s*',                        # Host:
            r'^(Guest\s*(?:Expert)?):?\s*',       # Guest: or Guest Expert:
            r'^\[([A-Z][a-zA-Z\s\.]+?)\]\s*:\s*', # [Name]:
        ]
        
        for pattern in speaker_patterns:
            text = re.sub(pattern, '', text)
        
        return text.strip()
    
    def _adjust_segment_end_times(self, segments: List[Dict[str, Any]]):
        """Adjust segment end times based on next segment start times.
        
        Args:
            segments: List of segment dictionaries (modified in place)
        """
        for i in range(len(segments) - 1):
            current_segment = segments[i]
            next_segment = segments[i + 1]
            
            # Set end time to just before next segment starts
            time_gap = next_segment["start_time"] - current_segment["start_time"]
            
            if time_gap > 0:
                # Leave small gap (0.1s) before next segment
                current_segment["end_time"] = next_segment["start_time"] - 0.1
            else:
                # Fallback to max duration
                current_segment["end_time"] = current_segment["start_time"] + self.max_cue_duration
        
        # Last segment keeps its default end time or extends based on content
        if segments:
            last_segment = segments[-1]
            text_length = sum(len(line) for line in last_segment["text_lines"])
            # Estimate duration based on text length (rough: 150 chars per minute)
            estimated_duration = max(2.0, min(self.max_cue_duration, text_length / 150 * 60))
            last_segment["end_time"] = last_segment["start_time"] + estimated_duration
    
    def _generate_vtt_cues(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate VTT cues from parsed segments.
        
        Args:
            segments: List of parsed segment dictionaries
            
        Returns:
            List of VTT cue dictionaries
        """
        cues = []
        
        for i, segment in enumerate(segments):
            # Combine text lines into cue content
            text_content = " ".join(segment["text_lines"]).strip()
            
            if not text_content:
                continue  # Skip empty segments
            
            # Format speaker voice tag
            voice_tag = ""
            if segment["speaker"]:
                clean_speaker = segment["speaker"].replace(":", "").strip()
                voice_tag = f"<v {clean_speaker}>"
            
            # Split long text into multiple lines if needed
            formatted_text = self._format_cue_text(text_content, voice_tag)
            
            # Create VTT cue
            cue = {
                "index": i + 1,
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "text": formatted_text,
                "speaker": segment["speaker"]
            }
            
            cues.append(cue)
        
        logger.info(f"Generated {len(cues)} VTT cues from {len(segments)} segments")
        return cues
    
    def _format_cue_text(self, text: str, voice_tag: str = "") -> str:
        """Format text content for VTT cue with proper line breaks.
        
        Args:
            text: Raw text content
            voice_tag: Speaker voice tag (e.g., "<v Speaker>")
            
        Returns:
            Formatted VTT cue text
        """
        if not text:
            return ""
        
        # Check if we need to split the text
        if voice_tag:
            # Check total length including voice tag
            full_text = f"{voice_tag}{text}"
            if len(full_text) <= self.max_chars_per_line:
                return full_text
        else:
            if len(text) <= self.max_chars_per_line:
                return text
        
        # Split text into words and create lines
        words = text.split()
        lines = []
        current_line = voice_tag if voice_tag else ""
        
        for word in words:
            
            test_line = f"{current_line} {word}".strip()
            
            if len(test_line) <= self.max_chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return '\n'.join(lines)
    
    def _build_vtt_file(self, cues: List[Dict[str, Any]], episode_metadata: Dict[str, Any]) -> str:
        """Build complete VTT file from cues and metadata.
        
        Args:
            cues: List of VTT cue dictionaries
            episode_metadata: Episode metadata for header
            
        Returns:
            Complete VTT file content
        """
        lines = ["WEBVTT"]
        lines.append("")
        
        # Add metadata as NOTE
        podcast_name = episode_metadata.get('podcast_name', 'Unknown Podcast')
        episode_title = episode_metadata.get('title', 'Unknown Episode')
        lines.append(f"NOTE {podcast_name} - {episode_title}")
        lines.append(f"NOTE Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        
        # Add cues
        for cue in cues:
            # Add cue timestamp line
            start_vtt = self._seconds_to_vtt_timestamp(cue["start_time"])
            end_vtt = self._seconds_to_vtt_timestamp(cue["end_time"])
            lines.append(f"{start_vtt} --> {end_vtt}")
            
            # Add cue text
            lines.append(cue["text"])
            lines.append("")  # Empty line between cues
        
        return '\n'.join(lines)
    
    def _seconds_to_vtt_timestamp(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            VTT timestamp string (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds * 1000) % 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    def _create_empty_vtt(self, episode_metadata: Dict[str, Any]) -> str:
        """Create an empty VTT file with metadata.
        
        Args:
            episode_metadata: Episode metadata
            
        Returns:
            Empty VTT file content
        """
        podcast_name = episode_metadata.get('podcast_name', 'Unknown Podcast')
        episode_title = episode_metadata.get('title', 'Unknown Episode')
        
        return f"""WEBVTT

NOTE {podcast_name} - {episode_title}
NOTE Generated: {datetime.now(timezone.utc).isoformat()}
NOTE No transcript content available

00:00:00.000 --> 00:00:05.000
<v System>No transcript available for this episode.

"""
    
    def _validate_vtt(self, vtt_content: str) -> Dict[str, Any]:
        """Validate the generated VTT content.
        
        Args:
            vtt_content: VTT file content
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            "is_valid": False,
            "cue_count": 0,
            "duration": 0.0,
            "has_speaker_tags": False,
            "issues": []
        }
        
        if not vtt_content:
            validation["issues"].append("Empty VTT content")
            return validation
        
        lines = vtt_content.split('\n')
        
        # Check WEBVTT header
        if not lines[0].strip() == "WEBVTT":
            validation["issues"].append("Missing WEBVTT header")
        else:
            validation["is_valid"] = True
        
        # Count cues and check format
        cue_count = 0
        max_end_time = 0.0
        has_speaker_tags = False
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for timestamp line
            if "-->" in line:
                cue_count += 1
                
                # Parse timestamps
                try:
                    start_str, end_str = line.split(' --> ')
                    end_time = self._parse_vtt_timestamp(end_str)
                    max_end_time = max(max_end_time, end_time)
                except:
                    validation["issues"].append(f"Invalid timestamp format: {line}")
                
                # Check next line for cue content
                if i + 1 < len(lines):
                    cue_text = lines[i + 1].strip()
                    if "<v " in cue_text:
                        has_speaker_tags = True
            
            i += 1
        
        validation["cue_count"] = cue_count
        validation["duration"] = max_end_time
        validation["has_speaker_tags"] = has_speaker_tags
        
        if cue_count == 0:
            validation["issues"].append("No cues found")
            validation["is_valid"] = False
        
        return validation
    
    def _parse_vtt_timestamp(self, timestamp_str: str) -> float:
        """Parse VTT timestamp to seconds.
        
        Args:
            timestamp_str: VTT timestamp (HH:MM:SS.mmm)
            
        Returns:
            Time in seconds
        """
        try:
            # Remove any whitespace
            timestamp_str = timestamp_str.strip()
            
            # Split by : to get hours, minutes, seconds.milliseconds
            parts = timestamp_str.split(':')
            
            if len(parts) == 3:  # HH:MM:SS.mmm
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds_ms = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds_ms
            elif len(parts) == 2:  # MM:SS.mmm
                minutes = int(parts[0])
                seconds_ms = float(parts[1])
                return minutes * 60 + seconds_ms
            else:
                return 0.0
                
        except (ValueError, IndexError):
            return 0.0
    
    def save_vtt_file(self, vtt_content: str, output_path: Path) -> bool:
        """Save VTT content to file.
        
        Args:
            vtt_content: VTT file content
            output_path: Path where to save the VTT file
            
        Returns:
            True if saved successfully
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(vtt_content)
            
            logger.info(f"Saved VTT file: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save VTT file {output_path}: {e}")
            return False