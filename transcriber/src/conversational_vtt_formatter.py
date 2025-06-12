"""Conversational VTT Formatter Module for Podcast Transcripts.

This module converts Deepgram JSON responses to WebVTT files optimized for
podcast transcripts with natural conversational segmentation.

Unlike subtitle formatters, this focuses on semantic coherence, complete thoughts,
and natural conversation boundaries rather than display constraints.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import timedelta

from src.utils.logging import get_logger
from src.vtt_formatter import VTTFormatter

logger = get_logger('conversational_vtt_formatter')


class ConversationalVTTFormatter(VTTFormatter):
    """Formats Deepgram responses as VTT files optimized for podcast transcripts.
    
    Creates segments based on natural conversation boundaries:
    - Speaker changes
    - Complete thoughts and stories
    - Topic shifts
    - Natural pauses
    """
    
    # Duration parameters (in seconds)
    MIN_SEGMENT_DURATION = 3.0  # Minimum segment length
    PREFERRED_SEGMENT_DURATION = 30.0  # Target segment length
    MAX_SEGMENT_DURATION = 180.0  # Maximum segment length (3 minutes)
    PAUSE_THRESHOLD = 2.0  # Pause duration that indicates topic shift
    
    # Short utterances to potentially merge
    SHORT_INTERJECTIONS = {
        'yeah', 'yes', 'no', 'okay', 'ok', 'right', 'exactly',
        'uh-huh', 'mm-hmm', 'hmm', 'oh', 'ah', 'wow', 'really',
        'sure', 'absolutely', 'definitely', 'totally', 'agreed'
    }
    
    # Discourse markers that indicate topic shifts
    TOPIC_SHIFT_MARKERS = {
        # Strong topic shifts
        'so': 'strong',
        'now': 'strong',
        'anyway': 'strong',
        'moving on': 'strong',
        'next': 'strong',
        'let me': 'strong',
        'here\'s the thing': 'strong',
        'the thing is': 'strong',
        
        # Medium topic shifts
        'but': 'medium',
        'however': 'medium',
        'although': 'medium',
        'well': 'medium',
        'actually': 'medium',
        'basically': 'medium',
        'essentially': 'medium',
        
        # Weak topic shifts (continuations)
        'and': 'weak',
        'also': 'weak',
        'additionally': 'weak',
        'furthermore': 'weak',
        'then': 'weak'
    }
    
    # Sentence-ending punctuation
    SENTENCE_END = re.compile(r'[.!?]+')
    
    def __init__(self,
                 min_segment_duration: float = MIN_SEGMENT_DURATION,
                 preferred_segment_duration: float = PREFERRED_SEGMENT_DURATION,
                 max_segment_duration: float = MAX_SEGMENT_DURATION,
                 pause_threshold: float = PAUSE_THRESHOLD,
                 merge_short_interjections: bool = True,
                 respect_sentences: bool = True,
                 use_discourse_markers: bool = True):
        """Initialize conversational VTT formatter.
        
        Args:
            min_segment_duration: Minimum segment duration in seconds.
            preferred_segment_duration: Target segment duration in seconds.
            max_segment_duration: Maximum segment duration in seconds.
            pause_threshold: Pause duration that indicates a topic shift.
            merge_short_interjections: Whether to merge short responses.
            respect_sentences: Whether to avoid breaking sentences.
            use_discourse_markers: Whether to use discourse markers for segmentation.
        """
        # Initialize parent with conversational defaults
        # No character limit for conversational transcripts
        super().__init__(max_cue_duration=max_segment_duration, max_chars_per_line=10000)
        
        self.min_segment_duration = min_segment_duration
        self.preferred_segment_duration = preferred_segment_duration
        self.max_segment_duration = max_segment_duration
        self.pause_threshold = pause_threshold
        self.merge_short_interjections = merge_short_interjections
        self.respect_sentences = respect_sentences
        self.use_discourse_markers = use_discourse_markers
        
        logger.info(
            f"Initialized ConversationalVTTFormatter with "
            f"duration={min_segment_duration}-{preferred_segment_duration}-{max_segment_duration}s, "
            f"pause_threshold={pause_threshold}s, "
            f"merge_interjections={merge_short_interjections}"
        )
    
    def calculate_pause_duration(self, word1: Dict, word2: Dict) -> float:
        """Calculate pause duration between two words.
        
        Args:
            word1: First word dictionary.
            word2: Second word dictionary.
            
        Returns:
            Pause duration in seconds.
        """
        return word2['start'] - word1['end']
    
    def is_short_interjection(self, text: str) -> bool:
        """Check if text is a short interjection that could be merged.
        
        Args:
            text: Text to check.
            
        Returns:
            True if text is a short interjection.
        """
        # Clean and lowercase the text
        clean_text = text.strip().lower().rstrip('.,!?')
        
        # Check if it's a single short interjection
        words = clean_text.split()
        if len(words) <= 2:
            return any(word in self.SHORT_INTERJECTIONS for word in words)
        return False
    
    def detect_discourse_marker(self, text: str) -> Optional[str]:
        """Detect discourse markers at the beginning of text.
        
        Args:
            text: Text to check for discourse markers.
            
        Returns:
            Strength of discourse marker ('strong', 'medium', 'weak') or None.
        """
        if not self.use_discourse_markers:
            return None
        
        # Clean and lowercase the beginning of text
        clean_text = text.strip().lower()
        
        # Check for discourse markers
        for marker, strength in self.TOPIC_SHIFT_MARKERS.items():
            if clean_text.startswith(marker + ' ') or clean_text.startswith(marker + ','):
                return strength
        
        return None
    
    def is_complete_sentence(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation.
        
        Args:
            text: Text to check.
            
        Returns:
            True if text appears to be a complete sentence.
        """
        text = text.strip()
        return bool(self.SENTENCE_END.search(text[-2:]) if len(text) >= 2 else False)
    
    def find_best_break_point(self, words: List[Dict], start_idx: int, 
                            target_duration: float, max_duration: float) -> Tuple[int, str]:
        """Find the best break point within duration constraints.
        
        Args:
            words: List of word dictionaries.
            start_idx: Starting index in words list.
            target_duration: Target duration from start word.
            max_duration: Maximum duration from start word.
            
        Returns:
            Tuple of (best_break_index, reason_for_break).
        """
        if start_idx >= len(words):
            return start_idx, "end_of_words"
        
        start_time = words[start_idx]['start']
        target_end_time = start_time + target_duration
        max_end_time = start_time + max_duration
        
        best_break_idx = start_idx
        best_break_reason = "no_break_found"
        current_text = ""
        
        # Look for natural break points
        for i in range(start_idx, len(words)):
            word = words[i]
            
            # Check if we've exceeded maximum duration
            if word['end'] > max_end_time:
                if best_break_idx > start_idx:
                    return best_break_idx, best_break_reason
                else:
                    # Force break at max duration
                    return i - 1 if i > start_idx else i, "max_duration"
            
            current_text += word.get('word', '') + ' '
            
            # Check for long pause
            if i < len(words) - 1:
                pause_duration = self.calculate_pause_duration(word, words[i + 1])
                if pause_duration >= self.pause_threshold:
                    best_break_idx = i
                    best_break_reason = "long_pause"
                    # If we're past target duration, break here
                    if word['end'] >= target_end_time:
                        return best_break_idx, best_break_reason
            
            # Check for sentence end
            if self.respect_sentences and self.is_complete_sentence(current_text):
                best_break_idx = i
                best_break_reason = "sentence_end"
                # If we're past target duration, break here
                if word['end'] >= target_end_time:
                    return best_break_idx, best_break_reason
            
            # Check for strong discourse marker at next word
            if i < len(words) - 1 and word['end'] >= target_end_time:
                next_text = ' '.join([w.get('word', '') for w in words[i+1:i+4]])
                marker_strength = self.detect_discourse_marker(next_text)
                if marker_strength == 'strong':
                    return i, "discourse_marker"
        
        # Return the last valid index
        return len(words) - 1, "end_of_segment"
    
    def create_cues_from_words(self, words: List[Dict]) -> List[Dict]:
        """Create VTT cues from word-level data using conversational segmentation.
        
        Groups words into natural conversational segments based on speaker changes,
        pauses, discourse markers, and semantic boundaries.
        
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
            # Start new segment
            segment_start_idx = current_idx
            word = words[current_idx]
            speaker_name = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
            segment_start_time = word['start']
            segment_text = ""
            segment_words = []
            
            # Build segment until we hit a boundary
            while current_idx < len(words):
                word = words[current_idx]
                word_speaker = word.get('speaker_name', f"Speaker {word.get('speaker', 0)}")
                
                # Always break on speaker change
                if word_speaker != speaker_name:
                    break
                
                # Add word to segment
                segment_text += word.get('word', '') + ' '
                segment_words.append(word)
                current_idx += 1
                
                # Check if we should look for a break point
                current_duration = word['end'] - segment_start_time
                
                if current_duration >= self.preferred_segment_duration:
                    # Look for a natural break point
                    if current_idx < len(words):
                        next_word = words[current_idx]
                        next_speaker = next_word.get('speaker_name', f"Speaker {next_word.get('speaker', 0)}")
                        
                        # If speaker is about to change, break here
                        if next_speaker != speaker_name:
                            break
                        
                        # Look for other natural breaks
                        break_idx, break_reason = self.find_best_break_point(
                            words, segment_start_idx, 
                            self.preferred_segment_duration, 
                            self.max_segment_duration
                        )
                        
                        # If we found a good break point, use it
                        if break_idx > current_idx - 1:
                            # Continue building until break point
                            while current_idx <= break_idx and current_idx < len(words):
                                word = words[current_idx]
                                segment_text += word.get('word', '') + ' '
                                segment_words.append(word)
                                current_idx += 1
                        break
            
            # Create segment if we have content
            if segment_words:
                segment_end_time = segment_words[-1]['end']
                segment_duration = segment_end_time - segment_start_time
                
                # Check if this is a short interjection that should be merged
                if (self.merge_short_interjections and 
                    segment_duration < self.min_segment_duration and
                    self.is_short_interjection(segment_text) and
                    len(cues) > 0):
                    
                    # Try to merge with previous cue if same speaker
                    prev_cue = cues[-1]
                    if prev_cue['speaker_name'] == speaker_name:
                        # Check gap between segments
                        gap = segment_start_time - prev_cue['end']
                        if gap < 1.0:  # Less than 1 second gap
                            # Merge with previous
                            prev_cue['end'] = segment_end_time
                            prev_cue['text'] += ' ' + segment_text.strip()
                            continue
                
                # Create the cue
                cue = {
                    'start': segment_start_time,
                    'end': segment_end_time,
                    'text': segment_text.strip(),
                    'speaker_name': speaker_name
                }
                cues.append(cue)
        
        # Post-process to ensure minimum durations
        final_cues = []
        for i, cue in enumerate(cues):
            duration = cue['end'] - cue['start']
            
            # If cue is too short and not the last one
            if duration < self.min_segment_duration and i < len(cues) - 1:
                next_cue = cues[i + 1]
                
                # If same speaker and close together, merge
                if (cue['speaker_name'] == next_cue['speaker_name'] and 
                    next_cue['start'] - cue['end'] < 1.0):
                    # Merge with next
                    next_cue['start'] = cue['start']
                    next_cue['text'] = cue['text'] + ' ' + next_cue['text']
                    continue
            
            final_cues.append(cue)
        
        logger.info(f"Created {len(final_cues)} conversational segments from {len(words)} words")
        return final_cues
    
    def format_deepgram_response(self, 
                               deepgram_response: Dict,
                               speaker_mapping: Optional[Dict[int, str]] = None,
                               episode=None,
                               deepgram_metadata=None) -> str:
        """Convert Deepgram response to VTT format with conversational segmentation.
        
        Overrides parent method to ensure episode and metadata parameters are passed through.
        
        Args:
            deepgram_response: Response from Deepgram API.
            speaker_mapping: Optional custom speaker name mapping.
            episode: Optional Episode object with metadata.
            deepgram_metadata: Optional metadata from Deepgram response.
            
        Returns:
            Formatted VTT content as string.
        """
        return super().format_deepgram_response(
            deepgram_response,
            speaker_mapping=speaker_mapping,
            episode=episode,
            deepgram_metadata=deepgram_metadata
        )