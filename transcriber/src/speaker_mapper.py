"""Speaker Mapping Module for Podcast Transcription.

This module handles mapping generic speaker labels (Speaker:0, Speaker:1)
to meaningful names (Host, Guest, etc.).
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import Counter
from dataclasses import dataclass

from src.utils.logging import get_logger

logger = get_logger('speaker_mapper')


@dataclass
class SpeakerStats:
    """Statistics for a single speaker."""
    
    speaker_id: int
    word_count: int
    speaking_time: float
    first_appearance: float
    last_appearance: float
    
    @property
    def total_duration(self) -> float:
        """Total speaking duration for this speaker."""
        return self.last_appearance - self.first_appearance


class SpeakerMapper:
    """Maps generic speaker IDs to meaningful names."""
    
    # Default speaker name templates
    DEFAULT_MAPPING = {
        0: "Host",
        1: "Guest",
        2: "Guest 2",
        3: "Guest 3",
        4: "Guest 4",
        5: "Guest 5"
    }
    
    def __init__(self, custom_mapping: Optional[Dict[int, str]] = None):
        """Initialize speaker mapper.
        
        Args:
            custom_mapping: Optional custom mapping of speaker IDs to names.
        """
        self.mapping = custom_mapping or self.DEFAULT_MAPPING.copy()
        logger.info(f"Initialized SpeakerMapper with mapping: {self.mapping}")
    
    def analyze_transcript(self, words: List[Dict]) -> Dict[int, SpeakerStats]:
        """Analyze transcript to gather speaker statistics.
        
        Args:
            words: List of word dictionaries from Deepgram response.
            
        Returns:
            Dictionary mapping speaker IDs to their statistics.
        """
        logger.info("Analyzing transcript for speaker statistics")
        
        speaker_stats = {}
        
        for word in words:
            speaker_id = word.get('speaker', 0)
            
            if speaker_id not in speaker_stats:
                speaker_stats[speaker_id] = SpeakerStats(
                    speaker_id=speaker_id,
                    word_count=0,
                    speaking_time=0.0,
                    first_appearance=word['start'],
                    last_appearance=word['end']
                )
            
            stats = speaker_stats[speaker_id]
            stats.word_count += 1
            stats.speaking_time += (word['end'] - word['start'])
            stats.first_appearance = min(stats.first_appearance, word['start'])
            stats.last_appearance = max(stats.last_appearance, word['end'])
        
        # Log speaker statistics
        for speaker_id, stats in speaker_stats.items():
            logger.info(
                f"Speaker {speaker_id}: {stats.word_count} words, "
                f"{stats.speaking_time:.1f}s speaking time, "
                f"first appearance at {stats.first_appearance:.1f}s"
            )
        
        return speaker_stats
    
    def determine_speaker_roles(self, speaker_stats: Dict[int, SpeakerStats]) -> Dict[int, str]:
        """Determine speaker roles based on statistics.
        
        Uses heuristics to identify host vs guests:
        - Host typically speaks first and has more speaking time
        - Guests join later in the conversation
        
        Args:
            speaker_stats: Dictionary of speaker statistics.
            
        Returns:
            Dictionary mapping speaker IDs to role names.
        """
        if not speaker_stats:
            return {}
        
        # Sort speakers by first appearance
        speakers_by_appearance = sorted(
            speaker_stats.items(),
            key=lambda x: x[1].first_appearance
        )
        
        # The first speaker is likely the host
        role_mapping = {}
        if speakers_by_appearance:
            first_speaker_id = speakers_by_appearance[0][0]
            role_mapping[first_speaker_id] = "Host"
            
            # Assign guest roles to other speakers
            guest_counter = 1
            for speaker_id, _ in speakers_by_appearance[1:]:
                if guest_counter == 1:
                    role_mapping[speaker_id] = "Guest"
                else:
                    role_mapping[speaker_id] = f"Guest {guest_counter}"
                guest_counter += 1
        
        logger.info(f"Determined speaker roles: {role_mapping}")
        return role_mapping
    
    def map_speakers(self, words: List[Dict], mapping: Optional[Dict[int, str]] = None) -> Tuple[List[Dict], Dict[int, str]]:
        """Map speaker IDs to names in word list.
        
        Args:
            words: List of word dictionaries from Deepgram response.
            mapping: Optional custom speaker mapping. If not provided, uses auto-detection.
            
        Returns:
            Tuple of (updated words list with speaker names, final mapping used).
        """
        # Determine mapping if not provided
        if mapping is None:
            speaker_stats = self.analyze_transcript(words)
            mapping = self.determine_speaker_roles(speaker_stats)
        
        # Apply mapping to words
        mapped_words = []
        for word in words:
            mapped_word = word.copy()
            speaker_id = word.get('speaker', 0)
            mapped_word['speaker_name'] = mapping.get(speaker_id, f"Speaker {speaker_id}")
            mapped_words.append(mapped_word)
        
        logger.info(f"Mapped {len(words)} words with speaker names")
        return mapped_words, mapping
    
    def get_speaker_segments(self, words: List[Dict]) -> List[Dict]:
        """Group words into continuous speaker segments.
        
        Args:
            words: List of word dictionaries with speaker information.
            
        Returns:
            List of speaker segments with start/end times and text.
        """
        if not words:
            return []
        
        segments = []
        current_segment = None
        
        for word in words:
            speaker = word.get('speaker', 0)
            speaker_name = word.get('speaker_name', f"Speaker {speaker}")
            
            # Start new segment if speaker changes
            if current_segment is None or current_segment['speaker'] != speaker:
                if current_segment:
                    segments.append(current_segment)
                
                current_segment = {
                    'speaker': speaker,
                    'speaker_name': speaker_name,
                    'start': word['start'],
                    'end': word['end'],
                    'text': word['word']
                }
            else:
                # Continue current segment
                current_segment['end'] = word['end']
                current_segment['text'] += ' ' + word['word']
        
        # Add final segment
        if current_segment:
            segments.append(current_segment)
        
        logger.info(f"Created {len(segments)} speaker segments")
        return segments