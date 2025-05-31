"""Audio Transcription Processor for Podcast Transcription Pipeline.

This module handles the core transcription logic, converting audio to
WebVTT format with speaker diarization using Gemini 2.5 Pro.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio

from gemini_client import RateLimitedGeminiClient
from key_rotation_manager import KeyRotationManager
from utils.logging import get_logger, log_progress

logger = get_logger('transcription_processor')


@dataclass
class TranscriptionSegment:
    """Represents a single segment of transcribed text."""
    start_time: timedelta
    end_time: timedelta
    speaker: str
    text: str
    
    def to_vtt_cue(self) -> str:
        """Convert segment to VTT cue format."""
        start = self._format_timestamp(self.start_time)
        end = self._format_timestamp(self.end_time)
        
        # Add speaker voice tag
        text_with_speaker = f"<v {self.speaker}>{self.text}"
        
        return f"{start} --> {end}\n{text_with_speaker}"
    
    def _format_timestamp(self, td: timedelta) -> str:
        """Format timedelta to VTT timestamp (HH:MM:SS.mmm)."""
        total_seconds = td.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds * 1000) % 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class TranscriptionProcessor:
    """Processes audio files to generate VTT transcripts with speaker diarization."""
    
    def __init__(self, gemini_client: RateLimitedGeminiClient, key_manager: KeyRotationManager):
        """Initialize transcription processor.
        
        Args:
            gemini_client: Rate-limited Gemini API client
            key_manager: API key rotation manager
        """
        self.gemini_client = gemini_client
        self.key_manager = key_manager
        self.vtt_pattern = re.compile(
            r'(\d{1,}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,}:\d{2}:\d{2}\.\d{3})\s*\n<v\s+([^>]+)>(.+?)(?=\n\d{1,}:\d{2}:\d{2}\.\d{3}|$)',
            re.DOTALL | re.MULTILINE
        )
    
    async def transcribe_episode(self, 
                               audio_url: str, 
                               episode_metadata: Dict[str, Any]) -> Optional[str]:
        """Transcribe a podcast episode to VTT format.
        
        Args:
            audio_url: URL of the audio file
            episode_metadata: Episode information including title, description, etc.
            
        Returns:
            VTT-formatted transcript or None if failed
        """
        try:
            # Get next API key
            api_key, key_index = self.key_manager.get_next_key()
            
            # Update Gemini client with selected key
            self.gemini_client.api_keys = [api_key]
            self.gemini_client.usage_trackers = [self.gemini_client.usage_trackers[key_index]]
            
            logger.info(f"Starting transcription for: {episode_metadata.get('title', 'Unknown')}")
            logger.info(f"Using API key index: {key_index + 1}")
            
            # Build enhanced prompt for VTT output
            prompt = self._build_transcription_prompt(episode_metadata)
            
            # Perform transcription
            transcript = await self.gemini_client.transcribe_audio(audio_url, episode_metadata)
            
            if not transcript:
                raise Exception("Transcription returned empty result")
            
            # Validate and clean transcript
            cleaned_transcript = self._validate_and_clean_transcript(transcript)
            
            # Mark key as successful
            self.key_manager.mark_key_success(key_index)
            
            logger.info("Transcription completed successfully")
            return cleaned_transcript
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Transcription failed: {error_msg}")
            
            # Mark key as failed if we have a key index
            if 'key_index' in locals():
                self.key_manager.mark_key_failure(key_index, error_msg)
            
            return None
    
    def _build_transcription_prompt(self, metadata: Dict[str, Any]) -> str:
        """Build enhanced prompt for VTT-formatted transcription."""
        return f"""Please transcribe this podcast episode into WebVTT (VTT) format with the following requirements:

1. **Format Requirements:**
   - Start with "WEBVTT" on the first line
   - Include a NOTE block with episode metadata
   - Use timestamps in HH:MM:SS.mmm format (hours:minutes:seconds.milliseconds)
   - Each cue should have start time --> end time
   - Use <v SPEAKER_N> tags for speaker identification
   - Keep segments 5-7 seconds long and under 2 lines of text

2. **Speaker Diarization:**
   - Identify different speakers as SPEAKER_1, SPEAKER_2, etc.
   - Be consistent with speaker numbering throughout
   - The host/interviewer is typically SPEAKER_1
   - Pay attention to speaking patterns and voice changes

3. **Episode Information:**
   - Podcast: {metadata.get('podcast_name', 'Unknown')}
   - Title: {metadata.get('title', 'Unknown')}
   - Date: {metadata.get('publication_date', 'Unknown')}
   - Host/Author: {metadata.get('author', 'Unknown')}

4. **Output Format Example:**
```
WEBVTT

NOTE
Podcast: {metadata.get('podcast_name', 'Unknown')}
Episode: {metadata.get('title', 'Unknown')}
Date: {metadata.get('publication_date', 'Unknown')}
Duration: {metadata.get('duration', 'Unknown')}

00:00:00.000 --> 00:00:05.500
<v SPEAKER_1>Welcome to {metadata.get('podcast_name', 'the podcast')}.
I'm your host.

00:00:05.500 --> 00:00:10.000
<v SPEAKER_1>Today we're discussing
{metadata.get('title', 'an interesting topic')[:50]}...

00:00:10.000 --> 00:00:15.000
<v SPEAKER_2>Thank you for having me.
It's great to be here.
```

Please transcribe the entire audio file following this format exactly."""
    
    def _validate_and_clean_transcript(self, transcript: str) -> str:
        """Validate and clean the VTT transcript.
        
        Args:
            transcript: Raw transcript from Gemini
            
        Returns:
            Cleaned and validated VTT transcript
        """
        lines = transcript.strip().split('\n')
        
        # Ensure it starts with WEBVTT
        if not lines or not lines[0].strip().upper().startswith('WEBVTT'):
            lines.insert(0, 'WEBVTT')
        
        # Clean up the transcript
        cleaned_lines = []
        in_cue = False
        current_cue_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines unless we're in a cue
            if not line:
                if in_cue and current_cue_lines:
                    # End of cue
                    cleaned_lines.extend(current_cue_lines)
                    cleaned_lines.append('')
                    current_cue_lines = []
                    in_cue = False
                elif not in_cue and cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')
                continue
            
            # Check if this is a timestamp line
            if '-->' in line:
                # Validate timestamp format
                if self._is_valid_timestamp_line(line):
                    if current_cue_lines:
                        # End previous cue
                        cleaned_lines.extend(current_cue_lines)
                        cleaned_lines.append('')
                    current_cue_lines = [line]
                    in_cue = True
                else:
                    logger.warning(f"Invalid timestamp line: {line}")
            elif in_cue:
                # Part of cue text
                current_cue_lines.append(line)
            else:
                # Header or NOTE content
                cleaned_lines.append(line)
        
        # Add any remaining cue
        if current_cue_lines:
            cleaned_lines.extend(current_cue_lines)
        
        # Ensure proper spacing
        result = '\n'.join(cleaned_lines)
        
        # Final validation
        if not self._validate_vtt_format(result):
            logger.warning("Generated transcript failed VTT validation")
        
        return result
    
    def _is_valid_timestamp_line(self, line: str) -> bool:
        """Check if a line contains valid VTT timestamps."""
        # Pattern: HH:MM:SS.mmm --> HH:MM:SS.mmm (optional cue settings)
        pattern = r'^\d{1,}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{1,}:\d{2}:\d{2}\.\d{3}'
        return bool(re.match(pattern, line))
    
    def _validate_vtt_format(self, vtt_content: str) -> bool:
        """Validate that the content follows WebVTT format.
        
        Args:
            vtt_content: VTT file content to validate
            
        Returns:
            True if valid, False otherwise
        """
        lines = vtt_content.strip().split('\n')
        
        # Must start with WEBVTT
        if not lines or not lines[0].strip().upper().startswith('WEBVTT'):
            logger.error("VTT must start with WEBVTT")
            return False
        
        # Check for at least one valid cue
        has_cue = False
        for i, line in enumerate(lines):
            if '-->' in line and self._is_valid_timestamp_line(line):
                has_cue = True
                # Verify timestamps are in order
                if not self._validate_timestamp_order(line):
                    logger.error(f"Invalid timestamp order: {line}")
                    return False
        
        if not has_cue:
            logger.error("VTT must contain at least one cue")
            return False
        
        return True
    
    def _validate_timestamp_order(self, timestamp_line: str) -> bool:
        """Validate that end time is after start time."""
        match = re.match(r'(\d{1,}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,}:\d{2}:\d{2}\.\d{3})', timestamp_line)
        if not match:
            return False
        
        start_str, end_str = match.groups()
        start_time = self._parse_timestamp(start_str)
        end_time = self._parse_timestamp(end_str)
        
        return end_time > start_time
    
    def _parse_timestamp(self, timestamp: str) -> timedelta:
        """Parse VTT timestamp to timedelta."""
        parts = timestamp.split(':')
        if len(parts) != 3:
            raise ValueError(f"Invalid timestamp format: {timestamp}")
        
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split('.')
        seconds = int(seconds_parts[0])
        milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
        
        return timedelta(
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=milliseconds
        )
    
    def parse_vtt_segments(self, vtt_content: str) -> List[TranscriptionSegment]:
        """Parse VTT content into TranscriptionSegment objects.
        
        Args:
            vtt_content: VTT-formatted transcript
            
        Returns:
            List of TranscriptionSegment objects
        """
        segments = []
        
        # Find all cues using regex
        matches = self.vtt_pattern.findall(vtt_content)
        
        for match in matches:
            start_str, end_str, speaker, text = match
            
            try:
                start_time = self._parse_timestamp(start_str)
                end_time = self._parse_timestamp(end_str)
                
                # Clean up text
                text = text.strip().replace('\n', ' ')
                
                segment = TranscriptionSegment(
                    start_time=start_time,
                    end_time=end_time,
                    speaker=speaker.strip(),
                    text=text
                )
                segments.append(segment)
                
            except Exception as e:
                logger.warning(f"Failed to parse segment: {e}")
        
        return segments