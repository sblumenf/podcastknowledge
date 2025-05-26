"""Text processing utilities for cleaning and normalizing text data."""

import re
import string
import unicodedata
import difflib
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def clean_segment_text(text: str) -> str:
    """Clean and normalize segment text.
    
    Args:
        text: Raw segment text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Strip whitespace
    text = text.strip()
    
    # Remove multiple spaces
    text = ' '.join(text.split())
    
    # Remove special characters but keep punctuation
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Fix common transcription errors
    replacements = {
        ' um ': ' ',
        ' uh ': ' ',
        ' uhm ': ' ',
        ' umm ': ' ',
        '  ': ' ',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text.strip()


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for comparison and deduplication.
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Normalized name (lowercase, stripped, common variations handled)
    """
    if not name:
        return ""
    
    # Convert to lowercase and strip
    normalized = name.lower().strip()
    
    # Remove common suffixes
    suffixes_to_remove = [
        ", inc.", ", inc", " inc.", " inc",
        ", llc", " llc",
        ", ltd", " ltd",
        ", corp", " corp",
        " corporation",
        " company",
        " & co",
        " & company"
    ]
    
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
    
    # Handle common abbreviations
    abbreviations = {
        "&": "and",
        "u.s.": "us",
        "u.k.": "uk",
        "dr.": "doctor",
        "mr.": "mister",
        "ms.": "miss",
        "prof.": "professor"
    }
    
    for abbr, full in abbreviations.items():
        normalized = normalized.replace(abbr, full)
    
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    
    return normalized


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two entity names.
    
    Args:
        name1: First entity name
        name2: Second entity name
        
    Returns:
        Similarity score between 0 and 1
    """
    norm1 = normalize_entity_name(name1)
    norm2 = normalize_entity_name(name2)
    
    # Use sequence matcher for fuzzy matching
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def extract_entity_aliases(entity_name: str, entity_description: str) -> List[str]:
    """Extract potential aliases from entity description.
    
    Args:
        entity_name: Main entity name
        entity_description: Entity description that might contain aliases
        
    Returns:
        List of potential aliases
    """
    aliases = []
    
    if not entity_description:
        return aliases
    
    # Common patterns for aliases
    alias_patterns = [
        r'also known as ([^,\.]+)',
        r'formerly ([^,\.]+)',
        r'aka ([^,\.]+)',
        r'\(([^)]+)\)',  # Names in parentheses
        r'or "([^"]+)"',  # Names in quotes
        r"or '([^']+)'",  # Names in single quotes
    ]
    
    for pattern in alias_patterns:
        matches = re.findall(pattern, entity_description, re.IGNORECASE)
        aliases.extend(matches)
    
    # Clean up aliases
    cleaned_aliases = []
    for alias in aliases:
        alias = alias.strip()
        # Don't include the main name as an alias
        if alias.lower() != entity_name.lower() and alias:
            cleaned_aliases.append(alias)
    
    return cleaned_aliases


def extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
    """Extract key phrases from text using simple heuristics.
    
    Args:
        text: Text to extract phrases from
        max_phrases: Maximum number of phrases to return
        
    Returns:
        List of key phrases
    """
    if not text:
        return []
    
    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'under', 'is', 'are',
        'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
        'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must',
        'shall', 'can', 'need', 'dare', 'ought', 'used', 'i', 'you', 'he',
        'she', 'it', 'we', 'they', 'them', 'their', 'this', 'that', 'these',
        'those', 'what', 'which', 'who', 'whom', 'whose', 'when', 'where',
        'why', 'how', 'all', 'each', 'every', 'some', 'any', 'many', 'much',
        'most', 'other', 'another', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 's', 't', 'just', 'now'
    }
    
    # Extract noun phrases using simple patterns
    # This is a simplified approach - for production, consider using spaCy or NLTK
    sentences = text.split('.')
    phrases = []
    
    for sentence in sentences:
        # Clean sentence
        sentence = sentence.strip().lower()
        if not sentence:
            continue
        
        # Remove punctuation except hyphens
        sentence = re.sub(r'[^\w\s-]', ' ', sentence)
        
        # Extract potential phrases (2-4 word combinations)
        words = sentence.split()
        
        for i in range(len(words)):
            # 2-word phrases
            if i < len(words) - 1:
                phrase = f"{words[i]} {words[i+1]}"
                if words[i] not in stop_words and words[i+1] not in stop_words:
                    phrases.append(phrase)
            
            # 3-word phrases
            if i < len(words) - 2:
                phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
                if (words[i] not in stop_words and 
                    words[i+2] not in stop_words):
                    phrases.append(phrase)
    
    # Count phrase frequency
    phrase_counts = {}
    for phrase in phrases:
        phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    
    # Sort by frequency and return top phrases
    sorted_phrases = sorted(phrase_counts.items(), 
                          key=lambda x: x[1], 
                          reverse=True)
    
    return [phrase for phrase, _ in sorted_phrases[:max_phrases]]


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
        return text[:max_length - len(suffix)] + suffix
    
    return text[:truncate_at] + suffix


def remove_special_characters(text: str, keep_punctuation: bool = True) -> str:
    """Remove special characters from text.
    
    Args:
        text: Text to clean
        keep_punctuation: Whether to keep punctuation marks
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    if keep_punctuation:
        # Keep letters, numbers, spaces, and basic punctuation
        cleaned = re.sub(r'[^a-zA-Z0-9\s.,!?;:\-\'"()]', '', text)
    else:
        # Keep only letters, numbers, and spaces
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    
    # Remove multiple spaces
    cleaned = ' '.join(cleaned.split())
    
    return cleaned


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
    
    # Simple sentence splitting
    # For production, consider using NLTK or spaCy
    sentences = re.split(r'[.!?]+', text)
    
    # Clean and filter sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and len(sentence) > 10:  # Filter very short sentences
            cleaned_sentences.append(sentence)
    
    return cleaned_sentences


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


def normalize_whitespace(text: str) -> str:
    """Normalize all whitespace in text.
    
    Args:
        text: Text with irregular whitespace
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    # Replace all whitespace characters with single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text