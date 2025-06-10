"""Text utility functions for VTT knowledge extraction.

This module provides text utility functions that complement the main
preprocessing and extraction modules without duplicating their functionality.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import re

from difflib import SequenceMatcher
import unicodedata
logger = logging.getLogger(__name__)


def extract_urls(text: str) -> List[str]:
    """Extract URLs from text.
    
    Args:
        text: Text containing URLs
        
    Returns:
        List of URLs found
    """
    if not text:
        return []
    
    # URL pattern
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}'
        r'\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
    )
    
    return url_pattern.findall(text)


def extract_email_addresses(text: str) -> List[str]:
    """Extract email addresses from text.
    
    Args:
        text: Text containing email addresses
        
    Returns:
        List of email addresses found
    """
    if not text:
        return []
    
    # Email pattern
    email_pattern = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    return email_pattern.findall(text)


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    if not text:
        return []
    
    # More sophisticated sentence splitting that handles ellipsis
    # Split on sentence endings but not on ellipsis (...)
    # This regex looks for punctuation followed by space or end of string
    # but not multiple periods in a row
    sentences = re.split(r'(?<=[.!?])(?<!\.\.)(?:\s+|$)', text)
    
    # Clean and filter sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        # Remove trailing punctuation
        sentence = re.sub(r'[.!?]+$', '', sentence)
        if sentence and len(sentence) > 2:  # Filter very short sentences (2 chars or less)
            cleaned_sentences.append(sentence)
    
    return cleaned_sentences


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length while preserving word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    # Find the last space before max_length
    truncate_at = text.rfind(' ', 0, max_length - len(suffix))
    
    if truncate_at == -1:
        # No space found, just truncate at max_length
        truncate_length = max_length - len(suffix)
        return text[:truncate_length] + suffix
    
    return text[:truncate_at] + suffix


def calculate_text_statistics(text: str) -> Dict[str, Any]:
    """Calculate various statistics about text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary of statistics
    """
    if not text:
        return {
            'character_count': 0,
            'word_count': 0,
            'sentence_count': 0,
            'average_word_length': 0,
            'average_sentence_length': 0,
            'unique_word_count': 0,
            'lexical_diversity': 0
        }
    
    # Basic counts
    character_count = len(text)
    words = text.split()
    word_count = len(words)
    sentences = split_into_sentences(text)
    sentence_count = len(sentences)
    
    # Word statistics
    word_lengths = [len(word) for word in words]
    average_word_length = sum(word_lengths) / len(word_lengths) if word_lengths else 0
    
    # Sentence statistics
    sentence_lengths = [len(sentence.split()) for sentence in sentences]
    average_sentence_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    
    # Lexical diversity
    unique_words = set(word.lower() for word in words)
    unique_word_count = len(unique_words)
    lexical_diversity = unique_word_count / word_count if word_count > 0 else 0
    
    return {
        'character_count': character_count,
        'word_count': word_count,
        'sentence_count': sentence_count,
        'average_word_length': round(average_word_length, 2),
        'average_sentence_length': round(average_sentence_length, 2),
        'unique_word_count': unique_word_count,
        'lexical_diversity': round(lexical_diversity, 3)
    }


def clean_quote_text(quote: str) -> str:
    """Clean and format quote text.
    
    Args:
        quote: Raw quote text
        
    Returns:
        Cleaned quote
    """
    if not quote:
        return ""
    
    # Remove extra whitespace
    quote = ' '.join(quote.split())
    
    # Ensure proper quote marks
    if not quote.startswith('"') and not quote.startswith("'"):
        quote = f'"{quote}"'
    
    # Fix mismatched quotes
    if quote.count('"') % 2 != 0:
        quote = quote.replace('"', '') + '"'
    
    return quote


def extract_timestamps(text: str) -> List[float]:
    """Extract timestamp references from text.
    
    Args:
        text: Text containing timestamp references
        
    Returns:
        List of timestamps in seconds
    """
    if not text:
        return []
    
    timestamps = []
    found_positions = set()  # Track positions where we've found timestamps
    
    # Pattern for timestamps like "12:34", "1:23:45", "45s"
    # Process patterns in order of specificity (most specific first)
    patterns = [
        (r'(\d{1,2}):(\d{2}):(\d{2})', lambda h, m, s: int(h)*3600 + int(m)*60 + int(s)),
        (r'(\d{1,2}):(\d{2})', lambda m, s: int(m)*60 + int(s)),
        (r'(\d+)s\b', lambda s: int(s)),
        (r'(\d+)\s*seconds?', lambda s: int(s)),
        (r'(\d+)\s*minutes?', lambda m: int(m)*60),
    ]
    
    for pattern, converter in patterns:
        for match in re.finditer(pattern, text):
            # Check if this position overlaps with a previously found timestamp
            if any(match.start() < end and match.end() > start 
                   for start, end in found_positions):
                continue
                
            try:
                timestamp = converter(*match.groups())
                timestamps.append(float(timestamp))
                found_positions.add((match.start(), match.end()))
            except (ValueError, TypeError):
                continue
    
    return sorted(set(timestamps))  # Remove duplicates and sort


def extract_metadata_markers(text: str) -> Dict[str, Any]:
    """Extract metadata markers from preprocessed text.
    
    Args:
        text: Text with metadata markers
        
    Returns:
        Dictionary of extracted metadata
    """
    metadata = {}
    
    # Extract timestamps
    time_match = re.search(r'\[TIME:\s*([\d.]+)-([\d.]+)s\]', text)
    if time_match:
        metadata['start_time'] = float(time_match.group(1))
        metadata['end_time'] = float(time_match.group(2))
    
    # Extract speaker
    speaker_match = re.search(r'\[SPEAKER:\s*([^\]]+)\]', text)
    if speaker_match:
        metadata['speaker'] = speaker_match.group(1)
    
    # Extract segment ID
    segment_match = re.search(r'\[SEGMENT:\s*([^\]]+)\]', text)
    if segment_match:
        metadata['segment_id'] = segment_match.group(1)
    
    # Extract episode
    episode_match = re.search(r'\[EPISODE:\s*([^\]]+)\]', text)
    if episode_match:
        metadata['episode_title'] = episode_match.group(1)
    
    # Clean text (remove all markers)
    # First remove non-Note markers (preserve spacing)
    clean_text = re.sub(r'\[[^\]]+\]', '', text)
    # Then remove Note markers
    clean_text = re.sub(r'\[Note:.*?\]', '', clean_text)
    # Clean up any excessive spaces (but keep double spaces if they existed)
    clean_text = re.sub(r'  +', '  ', clean_text).strip()
    metadata['clean_text'] = clean_text
    
    return metadata


def is_question(text: str) -> bool:
    """Check if text is a question.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be a question
    """
    if not text:
        return False
    
    text = text.strip()
    
    # Check for question mark
    if text.endswith('?'):
        return True
    
    # Check for question words at the beginning
    question_words = ['what', 'when', 'where', 'who', 'why', 'how', 
                     'is', 'are', 'was', 'were', 'do', 'does', 'did',
                     'can', 'could', 'would', 'should', 'will']
    
    words = text.split()
    if not words:
        return False
        
    first_word = words[0].lower()
    
    # Special case: "what" followed by "a/an" is usually an exclamation
    if first_word == 'what' and len(words) > 1 and words[1].lower() in ['a', 'an']:
        return False
    
    return first_word in question_words


def extract_speaker_turns(text: str) -> List[Dict[str, str]]:
    """Extract speaker turns from dialogue text.
    
    Args:
        text: Text containing speaker markers
        
    Returns:
        List of speaker turns with speaker and text
    """
    turns = []
    
    # Pattern for speaker markers like "Speaker:" or "[SPEAKER: Name]"
    # First, handle bracket format speakers
    remaining_text = text
    bracket_pattern = r'\[SPEAKER:\s*([^\]]+)\]\s*([^[]+?)(?=\[SPEAKER:|$)'
    
    # Extract all bracket format speakers and their positions
    bracket_matches = []
    for match in re.finditer(bracket_pattern, text, re.DOTALL):
        bracket_matches.append((match.start(), match.end(), match))
    
    # Process bracket matches
    for start, end, match in bracket_matches:
        speaker = match.group(1).strip()
        content = match.group(2).strip()
        
        # Check if content contains colon format speakers
        # Make sure we only match at the beginning of a line or after a period and space
        colon_pattern = r'(?:^|\.\s+)([A-Z][^:.]+):\s*(.+?)(?=(?:\.\s+[A-Z][^:.]+:|$))'
        colon_matches = list(re.finditer(colon_pattern, content, re.DOTALL))
        
        if colon_matches:
            # The pattern matches ". Guest:" so we need to include the period in the first part
            first_match = colon_matches[0]
            match_text = first_match.group(0)
            
            # Find where the actual speaker name starts (after the period and space)
            if match_text.startswith('. '):
                # Include everything up to and including the period
                first_part = content[:first_match.start() + 1]  # +1 to include the period
            else:
                # Match starts at beginning, no period to include
                first_part = content[:first_match.start()]
            
            first_part = first_part.strip()
            if first_part:
                turns.append({
                    'speaker': speaker,
                    'text': first_part
                })
            
            # Process colon format speakers within
            for colon_match in colon_matches:
                turns.append({
                    'speaker': colon_match.group(1).strip(),
                    'text': colon_match.group(2).strip()
                })
        else:
            # No colon format in content
            if content:
                turns.append({
                    'speaker': speaker,
                    'text': content
                })
    
    # If no bracket format found, process entire text for colon format
    if not bracket_matches:
        # Split by lines and look for speaker patterns
        lines = text.split('\n')
        current_speaker = None
        current_text = []
        
        for line in lines:
            # Check if line starts with speaker name (capital letter followed by colon)
            speaker_match = re.match(r'^([A-Z][^:]+):\s*(.+)', line)
            if speaker_match:
                # Save previous speaker's text if any
                if current_speaker and current_text:
                    turns.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_text).strip()
                    })
                # Start new speaker
                current_speaker = speaker_match.group(1).strip()
                current_text = [speaker_match.group(2).strip()]
            elif current_speaker and line.strip():
                # Continue current speaker's text
                current_text.append(line.strip())
        
        # Don't forget the last speaker
        if current_speaker and current_text:
            turns.append({
                'speaker': current_speaker,
                'text': ' '.join(current_text).strip()
            })
    
    return turns


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name for comparison.
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Normalized name
    """
    if not name:
        return ""
    
    # Convert to lowercase
    name = name.lower()
    
    # Remove accents and special characters
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Remove punctuation except hyphens and apostrophes
    name = re.sub(r"[^\w\s'-]", '', name)
    
    # Normalize whitespace
    name = ' '.join(name.split())
    
    # Common abbreviations
    abbreviations = {
        'inc': 'incorporated',
        'corp': 'corporation',
        'ltd': 'limited',
        'llc': 'limited liability company',
        'co': 'company',
        'dr': 'doctor',
        'mr': 'mister',
        'ms': 'miss',
        'mrs': 'missus',
        'prof': 'professor'
    }
    
    words = name.split()
    normalized_words = []
    for word in words:
        if word in abbreviations:
            normalized_words.append(abbreviations[word])
        else:
            normalized_words.append(word)
    
    return ' '.join(normalized_words)


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names.
    
    Args:
        name1: First name
        name2: Second name
        
    Returns:
        Similarity score between 0 and 1
    """
    if not name1 or not name2:
        return 0.0
    
    # Normalize names
    norm1 = normalize_entity_name(name1)
    norm2 = normalize_entity_name(name2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    # Use sequence matcher for fuzzy matching
    matcher = SequenceMatcher(None, norm1, norm2)
    base_similarity = matcher.ratio()
    
    # Check for subset matches (one name contains the other)
    if norm1 in norm2 or norm2 in norm1:
        base_similarity = max(base_similarity, 0.8)
    
    # Check for word-level matches
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if words1 and words2:
        word_overlap = len(words1.intersection(words2))
        total_words = len(words1.union(words2))
        word_similarity = word_overlap / total_words if total_words > 0 else 0
        
        # Weight word similarity higher for multi-word names
        if len(words1) > 1 or len(words2) > 1:
            base_similarity = max(base_similarity, word_similarity * 0.9)
    
    return round(base_similarity, 3)