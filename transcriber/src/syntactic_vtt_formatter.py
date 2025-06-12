"""Syntactic VTT Formatter Module for Deepgram Transcription.

This module converts Deepgram JSON responses to WebVTT files using research-based
syntactic segmentation that reduces cognitive load and improves readability.

Based on academic research and industry standards (Netflix, BBC).
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import timedelta

from src.utils.logging import get_logger
from src.vtt_formatter import VTTFormatter

logger = get_logger('syntactic_vtt_formatter')


class SyntacticVTTFormatter(VTTFormatter):
    """Formats Deepgram responses as WebVTT files with syntactic segmentation.
    
    Based on research showing that syntactically segmented subtitles reduce
    reading time and cognitive effort compared to arbitrary segmentation.
    """
    
    # Industry-standard parameters based on Netflix and BBC guidelines
    CHARS_PER_LINE = 42  # Netflix standard: 42 characters per line
    MAX_LINES = 2  # Standard: maximum 2 lines per subtitle
    MIN_DURATION = 0.83  # ~20 frames at 24fps (Netflix minimum)
    MAX_DURATION = 7.0  # Netflix/BBC maximum duration
    READING_SPEED_WPM = 180  # Target reading speed in words per minute
    MIN_GAP = 0.083  # Minimum gap between subtitles (2 frames at 24fps)
    
    # Syntactic patterns for keeping phrases together
    # These patterns identify word pairs that should not be split
    KEEP_TOGETHER_PATTERNS = [
        # Articles and nouns
        (r'\b(a|an|the)\s+\w+', 'article_noun'),
        # Auxiliary verbs
        (r'\b(am|is|are|was|were|been|being|have|has|had|do|does|did|will|would|shall|should|may|might|must|can|could)\s+\w+', 'auxiliary_verb'),
        # Prepositions and objects
        (r'\b(in|on|at|to|for|with|by|from|of|about|over|under)\s+\w+', 'preposition_object'),
        # Compound numbers
        (r'\b\d+\s+(hundred|thousand|million|billion)', 'compound_number'),
        # Negations
        (r'\b(not|n\'t)\s+\w+', 'negation'),
        # Common phrases
        (r'\b(going\s+to|want\s+to|have\s+to|need\s+to|used\s+to)', 'common_phrase'),
    ]
    
    # Punctuation that indicates natural breaks
    MAJOR_BREAKS = re.compile(r'[.!?]+')
    MINOR_BREAKS = re.compile(r'[,;:—–-]')
    
    def __init__(self):
        """Initialize syntactic VTT formatter with research-based defaults."""
        # Initialize parent with syntactic-friendly defaults
        super().__init__(max_cue_duration=self.MAX_DURATION, max_chars_per_line=self.CHARS_PER_LINE * self.MAX_LINES)
        
        # Compile keep-together patterns
        self.keep_together_compiled = [
            (re.compile(pattern, re.IGNORECASE), name) 
            for pattern, name in self.KEEP_TOGETHER_PATTERNS
        ]
        
        logger.info(
            f"Initialized SyntacticVTTFormatter with research-based parameters: "
            f"chars_per_line={self.CHARS_PER_LINE}, max_lines={self.MAX_LINES}, "
            f"duration={self.MIN_DURATION}-{self.MAX_DURATION}s, "
            f"reading_speed={self.READING_SPEED_WPM}wpm"
        )
    
    def calculate_reading_time(self, text: str) -> float:
        """Calculate required reading time based on word count and reading speed.
        
        Args:
            text: Text to calculate reading time for.
            
        Returns:
            Required reading time in seconds.
        """
        word_count = len(text.split())
        reading_time = (word_count / self.READING_SPEED_WPM) * 60
        return max(reading_time, self.MIN_DURATION)
    
    def find_syntactic_break(self, text: str, max_length: int) -> int:
        """Find the best syntactic break point in text.
        
        Args:
            text: Text to find break point in.
            max_length: Maximum length before break.
            
        Returns:
            Index of best break point, or max_length if no good break found.
        """
        if len(text) <= max_length:
            return len(text)
        
        # Look for break points before max_length
        search_text = text[:max_length + 10]  # Look a bit beyond for better breaks
        
        # Priority 1: Major punctuation (. ! ?)
        major_breaks = list(self.MAJOR_BREAKS.finditer(search_text))
        if major_breaks:
            # Find the last major break before max_length
            for match in reversed(major_breaks):
                if match.end() <= max_length:
                    return match.end()
        
        # Priority 2: Minor punctuation (, ; : —)
        minor_breaks = list(self.MINOR_BREAKS.finditer(search_text))
        if minor_breaks:
            # Find the last minor break before max_length
            for match in reversed(minor_breaks):
                if match.end() <= max_length:
                    return match.end()
        
        # Priority 3: Find a space that doesn't break syntactic units
        words = text.split()
        current_length = 0
        best_break = 0
        
        for i, word in enumerate(words):
            word_length = len(word) + (1 if i > 0 else 0)  # Add space
            if current_length + word_length > max_length:
                break
            
            current_length += word_length
            
            # Check if breaking here would split a syntactic unit
            if i < len(words) - 1:
                remaining_text = ' '.join(words[i:i+2])
                is_good_break = True
                
                # Check against keep-together patterns
                for pattern, _ in self.keep_together_compiled:
                    if pattern.match(remaining_text):
                        is_good_break = False
                        break
                
                if is_good_break:
                    best_break = current_length
        
        return best_break if best_break > 0 else max_length
    
    def format_cue_text_multiline(self, text: str, speaker_name: str) -> str:
        """Format cue text with speaker identification, supporting multiple lines.
        
        Args:
            text: The cue text.
            speaker_name: Name of the speaker.
            
        Returns:
            Formatted cue text with proper line breaks.
        """
        # Clean up text
        text = text.strip()
        
        # If text fits on one line, return as single line
        if len(text) <= self.CHARS_PER_LINE:
            return f"<v {speaker_name}>{text}</v>"
        
        # For two-line subtitles, find the best break point
        if len(text) <= self.CHARS_PER_LINE * 2:
            # Try to balance lines
            target_length = len(text) // 2
            break_point = self.find_syntactic_break(text, target_length + 10)
            
            line1 = text[:break_point].strip()
            line2 = text[break_point:].strip()
            
            # If lines are very unbalanced, try a different approach
            if len(line1) > self.CHARS_PER_LINE or len(line2) > self.CHARS_PER_LINE:
                break_point = self.find_syntactic_break(text, self.CHARS_PER_LINE)
                line1 = text[:break_point].strip()
                line2 = text[break_point:].strip()
            
            return f"<v {speaker_name}>{line1}\n{line2}</v>"
        
        # Text is too long for two lines - truncate at syntactic boundary
        break_point = self.find_syntactic_break(text, self.CHARS_PER_LINE * 2)
        truncated = text[:break_point].strip()
        
        # Format as two lines
        if len(truncated) > self.CHARS_PER_LINE:
            mid_break = self.find_syntactic_break(truncated, len(truncated) // 2 + 10)
            line1 = truncated[:mid_break].strip()
            line2 = truncated[mid_break:].strip()
            return f"<v {speaker_name}>{line1}\n{line2}</v>"
        
        return f"<v {speaker_name}>{truncated}</v>"
    
    def create_cues_from_words(self, words: List[Dict]) -> List[Dict]:
        """Create VTT cues from word-level data using syntactic segmentation.
        
        Groups words into syntactically meaningful cues based on linguistic
        boundaries and reading speed requirements.
        
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
            word = words[current_idx]
            speaker_name = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
            cue_start_time = word['start']
            cue_text = ""
            cue_words = []
            
            # Build cue until we hit constraints
            while current_idx < len(words):
                word = words[current_idx]
                word_speaker = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
                
                # Check if speaker changed
                if word_speaker != speaker_name:
                    break
                
                # Check timing constraints
                duration = word['end'] - cue_start_time
                if duration > self.MAX_DURATION:
                    break
                
                # Add word to potential cue
                test_text = cue_text + (' ' if cue_text else '') + word.get('word', '')
                
                # Check character limit (2 lines worth)
                if len(test_text) > self.CHARS_PER_LINE * 2:
                    # Check if we're at a good break point
                    if self.MAJOR_BREAKS.search(cue_text):
                        break
                    # If we have at least minimum content, break here
                    if len(cue_words) > 3 and duration >= self.MIN_DURATION:
                        break
                
                # Add word to cue
                cue_text = test_text
                cue_words.append(word)
                current_idx += 1
                
                # Check if we've hit a natural break point
                if self.MAJOR_BREAKS.search(word.get('word', '')):
                    # Ensure minimum duration
                    if word['end'] - cue_start_time >= self.MIN_DURATION:
                        break
            
            # Ensure we have content
            if not cue_words:
                current_idx += 1
                continue
            
            # Calculate actual duration
            cue_end_time = cue_words[-1]['end']
            duration = cue_end_time - cue_start_time
            
            # Ensure minimum duration by looking ahead if needed
            if duration < self.MIN_DURATION and current_idx < len(words):
                # Try to add more words to meet minimum duration
                while current_idx < len(words) and duration < self.MIN_DURATION:
                    word = words[current_idx]
                    word_speaker = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
                    
                    if word_speaker != speaker_name:
                        break
                    
                    test_text = cue_text + ' ' + word.get('word', '')
                    if len(test_text) > self.CHARS_PER_LINE * 2:
                        break
                    
                    cue_text = test_text
                    cue_words.append(word)
                    cue_end_time = word['end']
                    duration = cue_end_time - cue_start_time
                    current_idx += 1
            
            # Verify reading time
            required_reading_time = self.calculate_reading_time(cue_text)
            if duration < required_reading_time:
                # Extend duration if possible
                cue_end_time = min(cue_start_time + required_reading_time, 
                                 cue_start_time + self.MAX_DURATION)
            
            # Create cue
            cue = {
                'start': cue_start_time,
                'end': cue_end_time,
                'text': cue_text.strip(),
                'speaker_name': speaker_name
            }
            cues.append(cue)
        
        # Ensure minimum gap between cues
        for i in range(1, len(cues)):
            gap = cues[i]['start'] - cues[i-1]['end']
            if gap < self.MIN_GAP:
                # Adjust previous cue end time
                cues[i-1]['end'] = cues[i]['start'] - self.MIN_GAP
        
        logger.info(f"Created {len(cues)} syntactic cues from {len(words)} words")
        return cues
    
    def format_cue_text(self, text: str, speaker_name: str) -> str:
        """Override parent method to use multi-line formatting."""
        return self.format_cue_text_multiline(text, speaker_name)
    
    def format_deepgram_response(self, 
                               deepgram_response: Dict,
                               speaker_mapping: Optional[Dict[int, str]] = None,
                               episode=None,
                               deepgram_metadata=None) -> str:
        """Convert Deepgram response to VTT format with syntactic segmentation.
        
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