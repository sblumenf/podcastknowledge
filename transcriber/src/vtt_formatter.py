"""VTT Formatter Module for Deepgram Transcription.

This module converts Deepgram JSON responses to properly formatted WebVTT files
with speaker identification.
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from datetime import timedelta

from src.utils.logging import get_logger
from src.speaker_mapper import SpeakerMapper

logger = get_logger('vtt_formatter')


class VTTFormatter:
    """Formats Deepgram responses as WebVTT files."""
    
    # VTT header
    VTT_HEADER = "WEBVTT\nNOTE Transcription powered by Deepgram\n\n"
    
    # Maximum duration for a single cue in seconds
    DEFAULT_MAX_CUE_DURATION = 7.0
    
    # Maximum characters per cue line
    DEFAULT_MAX_CHARS_PER_LINE = 80
    
    def __init__(self, 
                 max_cue_duration: float = DEFAULT_MAX_CUE_DURATION,
                 max_chars_per_line: int = DEFAULT_MAX_CHARS_PER_LINE):
        """Initialize VTT formatter.
        
        Args:
            max_cue_duration: Maximum duration for a single cue in seconds.
            max_chars_per_line: Maximum characters per cue line.
        """
        self.max_cue_duration = max_cue_duration
        self.max_chars_per_line = max_chars_per_line
        logger.info(
            f"Initialized VTTFormatter with max_cue_duration={max_cue_duration}s, "
            f"max_chars_per_line={max_chars_per_line}"
        )
    
    def format_timestamp(self, seconds: float) -> str:
        """Format seconds as VTT timestamp (HH:MM:SS.mmm).
        
        Args:
            seconds: Time in seconds.
            
        Returns:
            Formatted timestamp string.
        """
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = int((td.total_seconds() - total_seconds) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def create_cues_from_words(self, words: List[Dict]) -> List[Dict]:
        """Create VTT cues from word-level data.
        
        Groups words into appropriately sized cues based on timing and length.
        
        Args:
            words: List of word dictionaries with timing and speaker info.
            
        Returns:
            List of cue dictionaries.
        """
        if not words:
            return []
        
        cues = []
        current_cue = None
        
        for word in words:
            word_text = word.get('word', '')
            speaker_name = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
            
            # Check if we need to start a new cue
            start_new_cue = False
            
            if current_cue is None:
                start_new_cue = True
            else:
                # Start new cue if speaker changes
                if current_cue['speaker_name'] != speaker_name:
                    start_new_cue = True
                # Start new cue if duration exceeds maximum
                elif word['end'] - current_cue['start'] > self.max_cue_duration:
                    start_new_cue = True
                # Start new cue if text would be too long
                elif len(current_cue['text'] + ' ' + word_text) > self.max_chars_per_line:
                    start_new_cue = True
            
            if start_new_cue:
                # Save current cue if exists
                if current_cue:
                    cues.append(current_cue)
                
                # Start new cue
                current_cue = {
                    'start': word['start'],
                    'end': word['end'],
                    'text': word_text,
                    'speaker_name': speaker_name
                }
            else:
                # Extend current cue
                current_cue['end'] = word['end']
                current_cue['text'] += ' ' + word_text
        
        # Add final cue
        if current_cue:
            cues.append(current_cue)
        
        logger.info(f"Created {len(cues)} cues from {len(words)} words")
        return cues
    
    def format_cue_text(self, text: str, speaker_name: str) -> str:
        """Format cue text with speaker identification.
        
        Args:
            text: The cue text.
            speaker_name: Name of the speaker.
            
        Returns:
            Formatted cue text with speaker prefix.
        """
        # Add speaker tag as voice span (standard VTT speaker identification)
        return f"<v {speaker_name}>{text}</v>"
    
    def format_deepgram_response(self, 
                               deepgram_response: Dict,
                               speaker_mapping: Optional[Dict[int, str]] = None) -> str:
        """Convert Deepgram response to VTT format.
        
        Args:
            deepgram_response: Response from Deepgram API.
            speaker_mapping: Optional custom speaker name mapping.
            
        Returns:
            Formatted VTT content as string.
        """
        logger.info("Formatting Deepgram response to VTT")
        
        # Extract words from response
        words = []
        # Check if this is the results dict directly or the full response
        if 'channels' in deepgram_response:
            # We received the results dict directly
            channels = deepgram_response.get('channels', [])
        elif 'results' in deepgram_response:
            # We received the full response
            channels = deepgram_response['results'].get('channels', [])
        else:
            channels = []
            
        if channels:
            alternatives = channels[0].get('alternatives', [])
            if alternatives:
                words = alternatives[0].get('words', [])
        
        if not words:
            logger.warning("No words found in Deepgram response")
            return self.VTT_HEADER + "NOTE No transcript available\n"
        
        # Apply speaker mapping if enabled
        if os.getenv('SPEAKER_MAPPING_ENABLED', 'true').lower() == 'true':
            mapper = SpeakerMapper()
            words, final_mapping = mapper.map_speakers(words, speaker_mapping)
            logger.info(f"Applied speaker mapping: {final_mapping}")
        else:
            # Add default speaker names
            for word in words:
                word['speaker_name'] = f"Speaker {word.get('speaker', 0)}"
        
        # Create cues from words
        cues = self.create_cues_from_words(words)
        
        # Build VTT content
        vtt_content = self.VTT_HEADER
        
        for i, cue in enumerate(cues, 1):
            # Add cue identifier (optional but helpful)
            vtt_content += f"{i}\n"
            
            # Add timestamp line
            start_time = self.format_timestamp(cue['start'])
            end_time = self.format_timestamp(cue['end'])
            vtt_content += f"{start_time} --> {end_time}\n"
            
            # Add cue text with speaker
            cue_text = self.format_cue_text(cue['text'].strip(), cue['speaker_name'])
            vtt_content += f"{cue_text}\n\n"
        
        logger.info(f"Generated VTT content with {len(cues)} cues")
        return vtt_content
    
    def validate_vtt(self, vtt_content: str) -> Tuple[bool, Optional[str]]:
        """Validate VTT content.
        
        Args:
            vtt_content: VTT content to validate.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if not vtt_content.startswith("WEBVTT"):
            return False, "VTT file must start with 'WEBVTT'"
        
        lines = vtt_content.strip().split('\n')
        if len(lines) < 3:
            return False, "VTT file must contain at least one cue"
        
        # Check for at least one timestamp arrow
        has_timestamp = any('-->' in line for line in lines)
        if not has_timestamp:
            return False, "VTT file must contain timestamp lines with '-->'"
        
        return True, None