"""Semantic VTT Formatter Module for Deepgram Transcription.

This module converts Deepgram JSON responses to WebVTT files with semantic segmentation
based on sentence boundaries and natural speech patterns.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import timedelta

from src.utils.logging import get_logger
from src.vtt_formatter import VTTFormatter

logger = get_logger('semantic_vtt_formatter')


class SemanticVTTFormatter(VTTFormatter):
    """Formats Deepgram responses as WebVTT files with semantic segmentation."""
    
    # Sentence-ending punctuation patterns
    SENTENCE_END_PATTERN = re.compile(r'[.!?]+')
    
    # Clause-ending punctuation patterns for softer breaks
    CLAUSE_END_PATTERN = re.compile(r'[,;:]')
    
    # Default parameters for semantic segmentation
    DEFAULT_MIN_CUE_DURATION = 2.0  # Minimum duration for a cue in seconds
    DEFAULT_MAX_CUE_DURATION = 10.0  # Maximum duration for a cue in seconds
    DEFAULT_PREFER_SENTENCE_BREAKS = True  # Prefer breaking at sentence boundaries
    DEFAULT_ALLOW_CLAUSE_BREAKS = True  # Allow breaking at clause boundaries if needed
    
    def __init__(self, 
                 min_cue_duration: float = DEFAULT_MIN_CUE_DURATION,
                 max_cue_duration: float = DEFAULT_MAX_CUE_DURATION,
                 prefer_sentence_breaks: bool = DEFAULT_PREFER_SENTENCE_BREAKS,
                 allow_clause_breaks: bool = DEFAULT_ALLOW_CLAUSE_BREAKS,
                 max_chars_per_line: int = 120):  # Increased for semantic chunks
        """Initialize semantic VTT formatter.
        
        Args:
            min_cue_duration: Minimum duration for a single cue in seconds.
            max_cue_duration: Maximum duration for a single cue in seconds.
            prefer_sentence_breaks: Whether to prefer breaking at sentence boundaries.
            allow_clause_breaks: Whether to allow breaking at clause boundaries.
            max_chars_per_line: Maximum characters per cue line.
        """
        # Initialize parent with semantic-friendly defaults
        super().__init__(max_cue_duration=max_cue_duration, max_chars_per_line=max_chars_per_line)
        
        self.min_cue_duration = min_cue_duration
        self.prefer_sentence_breaks = prefer_sentence_breaks
        self.allow_clause_breaks = allow_clause_breaks
        
        logger.info(
            f"Initialized SemanticVTTFormatter with min_cue_duration={min_cue_duration}s, "
            f"max_cue_duration={max_cue_duration}s, prefer_sentence_breaks={prefer_sentence_breaks}, "
            f"allow_clause_breaks={allow_clause_breaks}, max_chars_per_line={max_chars_per_line}"
        )
    
    def is_sentence_boundary(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation.
        
        Args:
            text: Text to check.
            
        Returns:
            True if text ends with sentence boundary.
        """
        text = text.strip()
        return bool(self.SENTENCE_END_PATTERN.search(text[-2:]) if len(text) >= 2 else False)
    
    def is_clause_boundary(self, text: str) -> bool:
        """Check if text ends with clause-ending punctuation.
        
        Args:
            text: Text to check.
            
        Returns:
            True if text ends with clause boundary.
        """
        text = text.strip()
        return bool(self.CLAUSE_END_PATTERN.search(text[-1:]) if text else False)
    
    def find_best_break_point(self, words: List[Dict], start_idx: int, max_duration: float) -> int:
        """Find the best semantic break point within duration constraints.
        
        Args:
            words: List of word dictionaries.
            start_idx: Starting index in words list.
            max_duration: Maximum duration from start word.
            
        Returns:
            Index of the best break point.
        """
        if start_idx >= len(words):
            return start_idx
        
        start_time = words[start_idx]['start']
        max_end_time = start_time + max_duration
        
        # Find all possible break points within time constraint
        sentence_breaks = []
        clause_breaks = []
        last_valid_idx = start_idx
        
        current_text = ""
        for i in range(start_idx, len(words)):
            word = words[i]
            
            # Stop if we exceed max duration
            if word['end'] > max_end_time:
                break
            
            current_text += word.get('word', '') + ' '
            last_valid_idx = i
            
            # Check for sentence boundary
            if self.is_sentence_boundary(current_text):
                sentence_breaks.append(i)
            # Check for clause boundary
            elif self.is_clause_boundary(current_text):
                clause_breaks.append(i)
        
        # Prefer sentence breaks if available and enabled
        if self.prefer_sentence_breaks and sentence_breaks:
            # Return the last sentence break within constraints
            return sentence_breaks[-1]
        
        # Use clause breaks if available and enabled
        if self.allow_clause_breaks and clause_breaks:
            # Return the last clause break within constraints
            return clause_breaks[-1]
        
        # If no semantic breaks found, return the last valid index
        return last_valid_idx
    
    def create_cues_from_words(self, words: List[Dict]) -> List[Dict]:
        """Create VTT cues from word-level data using semantic segmentation.
        
        Groups words into semantically meaningful cues based on punctuation
        and natural speech patterns.
        
        Args:
            words: List of word dictionaries with timing and speaker info.
            
        Returns:
            List of cue dictionaries.
        """
        if not words:
            return []
        
        cues = []
        current_idx = 0
        
        while current_idx < len(words):
            # Start new cue
            cue_start_idx = current_idx
            word = words[current_idx]
            speaker_name = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
            cue_start_time = word['start']
            
            # Build cue text until we hit a semantic boundary or constraints
            cue_text = ""
            cue_end_idx = current_idx
            cue_end_time = word['end']
            
            # Find semantic break point
            if current_idx < len(words) - 1:
                # Look for the best break point within max duration
                best_break_idx = self.find_best_break_point(words, current_idx, self.max_cue_duration)
                
                # Build text up to break point, checking for speaker changes
                for i in range(current_idx, min(best_break_idx + 1, len(words))):
                    word = words[i]
                    word_speaker = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
                    
                    # Break on speaker change
                    if word_speaker != speaker_name:
                        break
                    
                    # Check duration constraints
                    if word['end'] - cue_start_time > self.max_cue_duration:
                        break
                    
                    # Add word to cue
                    cue_text += word.get('word', '') + ' '
                    cue_end_time = word['end']
                    cue_end_idx = i
                    
                    # Check if we've reached a semantic boundary
                    if i == best_break_idx:
                        break
            else:
                # Last word
                cue_text = word.get('word', '')
                cue_end_time = word['end']
                cue_end_idx = current_idx
            
            # Check minimum duration constraint
            cue_duration = cue_end_time - cue_start_time
            if cue_duration < self.min_cue_duration and cue_end_idx < len(words) - 1:
                # Try to extend the cue if it's too short
                for i in range(cue_end_idx + 1, len(words)):
                    word = words[i]
                    word_speaker = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
                    
                    # Stop on speaker change
                    if word_speaker != speaker_name:
                        break
                    
                    # Stop if we exceed max duration
                    if word['end'] - cue_start_time > self.max_cue_duration:
                        break
                    
                    cue_text += word.get('word', '') + ' '
                    cue_end_time = word['end']
                    cue_end_idx = i
                    
                    # Stop if we've reached minimum duration
                    if word['end'] - cue_start_time >= self.min_cue_duration:
                        break
            
            # Create cue
            cue = {
                'start': cue_start_time,
                'end': cue_end_time,
                'text': cue_text.strip(),
                'speaker_name': speaker_name
            }
            cues.append(cue)
            
            # Move to next unprocessed word
            current_idx = cue_end_idx + 1
        
        logger.info(f"Created {len(cues)} semantic cues from {len(words)} words")
        return cues
    
    def format_deepgram_response(self, 
                               deepgram_response: Dict,
                               speaker_mapping: Optional[Dict[int, str]] = None,
                               episode=None,
                               deepgram_metadata=None) -> str:
        """Convert Deepgram response to VTT format with semantic segmentation.
        
        Overrides parent method to ensure episode parameter is passed through.
        
        Args:
            deepgram_response: Response from Deepgram API.
            speaker_mapping: Optional custom speaker name mapping.
            episode: Optional Episode object with metadata.
            
        Returns:
            Formatted VTT content as string.
        """
        return super().format_deepgram_response(
            deepgram_response,
            speaker_mapping=speaker_mapping,
            episode=episode,
            deepgram_metadata=deepgram_metadata
        )