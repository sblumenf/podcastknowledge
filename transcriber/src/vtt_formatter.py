"""VTT Formatter Module for Deepgram Transcription.

This module converts Deepgram JSON responses to properly formatted WebVTT files
with speaker identification.
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from datetime import timedelta

from src.utils.logging import get_logger

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
    
    def generate_metadata_header(self, episode=None, word_count=0, duration_seconds=0, 
                                deepgram_metadata=None, speaker_count=0) -> str:
        """Generate VTT metadata header with comprehensive episode information.
        
        Args:
            episode: Episode object with metadata (optional).
            word_count: Total number of words in transcript.
            duration_seconds: Total duration in seconds.
            deepgram_metadata: Metadata from Deepgram response (optional).
            speaker_count: Number of unique speakers detected.
            
        Returns:
            Formatted metadata header as string.
        """
        from datetime import datetime
        
        header = "WEBVTT\n"
        
        if episode:
            # Episode Information NOTE block
            header += "\nNOTE Episode Information\n"
            
            if hasattr(episode, 'podcast_name') and episode.podcast_name:
                header += f"Podcast: {episode.podcast_name}\n"
            
            if hasattr(episode, 'title') and episode.title:
                header += f"Episode: {episode.title}\n"
            
            if hasattr(episode, 'episode_number') and episode.episode_number:
                header += f"Episode Number: {episode.episode_number}\n"
            
            if hasattr(episode, 'season_number') and episode.season_number:
                header += f"Season: {episode.season_number}\n"
            
            if hasattr(episode, 'author') and episode.author:
                header += f"Author: {episode.author}\n"
            
            if hasattr(episode, 'published_date') and episode.published_date:
                header += f"Published: {episode.published_date}\n"
            
            if duration_seconds > 0:
                duration_str = str(timedelta(seconds=int(duration_seconds)))
                header += f"Duration: {duration_str}\n"
            
            # Content Details NOTE block
            header += "\nNOTE Content Details\n"
            
            if hasattr(episode, 'description') and episode.description:
                # Truncate description if too long and clean it up
                description = episode.description.strip()
                if len(description) > 500:
                    description = description[:497] + "..."
                # Replace newlines with spaces for VTT format
                description = description.replace('\n', ' ').replace('\r', ' ')
                header += f"Description: {description}\n"
            
            if hasattr(episode, 'keywords') and episode.keywords:
                keywords_str = ", ".join(episode.keywords[:10])  # Limit to first 10 keywords
                if keywords_str:
                    header += f"Keywords: {keywords_str}\n"
            
            if hasattr(episode, 'link') and episode.link:
                header += f"Original URL: {episode.link}\n"
            
            if hasattr(episode, 'youtube_url') and episode.youtube_url:
                header += f"YouTube URL: {episode.youtube_url}\n"
            
            # Transcription Details NOTE block
            header += "\nNOTE Transcription Details\n"
            header += "Service: Deepgram\n"
            
            if deepgram_metadata:
                if 'model_info' in deepgram_metadata:
                    models = deepgram_metadata['model_info']
                    if models:
                        model_key = list(models.keys())[0]
                        model_info = models[model_key]
                        header += f"Model: {model_info.get('arch', 'unknown')} ({model_info.get('version', 'unknown')})\n"
                
                if 'request_id' in deepgram_metadata:
                    header += f"Request ID: {deepgram_metadata['request_id']}\n"
            
            header += f"Transcribed: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            
            if deepgram_metadata and 'duration' in deepgram_metadata:
                header += f"Audio Duration: {deepgram_metadata['duration']:.2f} seconds\n"
            
            if word_count > 0:
                header += f"Words: {word_count:,}\n"
            
            if speaker_count > 0:
                header += f"Speakers: {speaker_count} detected\n"
            
            # Add confidence if available from deepgram results
            # This will be added by the calling method if available
            
        else:
            # Minimal header if no episode metadata
            header += "\nNOTE Transcription Details\n"
            header += "Service: Deepgram\n"
            header += f"Transcribed: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        
        header += "\n"
        return header
    
    def format_deepgram_response(self, 
                               deepgram_response: Dict,
                               speaker_mapping: Optional[Dict[int, str]] = None,
                               episode=None,
                               deepgram_metadata=None) -> str:
        """Convert Deepgram response to VTT format.
        
        Args:
            deepgram_response: Response from Deepgram API (results dict).
            speaker_mapping: Optional custom speaker name mapping.
            episode: Optional Episode object with metadata.
            deepgram_metadata: Optional metadata from Deepgram response.
            
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
        
        # Use Deepgram's speaker IDs directly
        for word in words:
            speaker_id = word.get('speaker', 0)
            word['speaker_name'] = f"Speaker {speaker_id}"
        
        # Create cues from words
        cues = self.create_cues_from_words(words)
        
        # Calculate total duration and count unique speakers
        total_duration = 0
        unique_speakers = set()
        
        if cues:
            total_duration = cues[-1]['end'] - cues[0]['start']
            for cue in cues:
                unique_speakers.add(cue.get('speaker_name', 'Unknown'))
        
        # Build VTT content with comprehensive metadata header
        vtt_content = self.generate_metadata_header(
            episode=episode,
            word_count=len(words),
            duration_seconds=total_duration,
            deepgram_metadata=deepgram_metadata,
            speaker_count=len(unique_speakers)
        )
        
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