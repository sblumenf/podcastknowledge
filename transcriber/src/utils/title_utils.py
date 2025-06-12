"""Title normalization utilities for consistent episode identification.

This module provides functions to normalize episode titles across different
components of the transcription pipeline, ensuring consistent matching
regardless of how titles are stored or processed.
"""

import re
import html
import unicodedata
from typing import Optional


def normalize_title(title: str) -> str:
    """Normalize an episode title for consistent comparison across the system.
    
    This function applies consistent transformations to episode titles to ensure
    that the same episode is recognized regardless of:
    - Punctuation differences (colons, semicolons, quotes)
    - HTML entity encoding (&amp; vs &)
    - Multiple spaces vs single spaces
    - Leading/trailing whitespace
    - Unicode normalization differences
    
    Args:
        title: Raw episode title from any source
        
    Returns:
        Normalized title string suitable for comparison and storage
        
    Examples:
        >>> normalize_title("Finally Feel Good in Your Body: 4 Expert Steps")
        "Finally Feel Good in Your Body 4 Expert Steps"
        
        >>> normalize_title("The Truth &amp; How To Deal")
        "The Truth and How To Deal"
        
        >>> normalize_title("  Multiple   Spaces   ")
        "Multiple Spaces"
    """
    if not title or not isinstance(title, str):
        return ""
    
    # Start with the original title
    normalized = title.strip()
    
    # Handle HTML entities first (e.g., &amp; -> &, &quot; -> ")
    normalized = html.unescape(normalized)
    
    # Normalize Unicode characters (e.g., different dash types, accented chars)
    normalized = unicodedata.normalize('NFKC', normalized)
    
    # Replace various dash types with standard hyphen
    normalized = re.sub(r'[—–]', '-', normalized)
    
    # Replace & with "and" for consistency
    normalized = re.sub(r'\s*&\s*', ' and ', normalized)
    
    # Remove problematic punctuation that causes mismatches
    # Keep: letters, numbers, spaces, periods, parentheses, hyphens, apostrophes
    # Remove: colons, semicolons, quotes, but handle slashes specially
    normalized = re.sub(r'[:<>;"\'\\|*?]', '', normalized)
    
    # Handle slashes specially - replace with space but avoid double spaces
    normalized = re.sub(r'\s*/\s*', ' ', normalized)
    normalized = re.sub(r'/', ' ', normalized)
    
    # Replace multiple whitespace (spaces, tabs, newlines) with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized


def title_matches(title1: str, title2: str) -> bool:
    """Check if two episode titles refer to the same episode.
    
    This function normalizes both titles and compares them for equality.
    
    Args:
        title1: First episode title
        title2: Second episode title
        
    Returns:
        True if the titles refer to the same episode, False otherwise
        
    Examples:
        >>> title_matches("Episode: Part 1", "Episode Part 1") 
        True
        
        >>> title_matches("Show &amp; Tell", "Show and Tell")
        True
    """
    return normalize_title(title1) == normalize_title(title2)


def extract_title_from_filename(filename: str) -> Optional[str]:
    """Extract and normalize episode title from a VTT filename.
    
    Expected filename format: YYYY-MM-DD_Episode_Title.vtt
    
    Args:
        filename: VTT filename (with or without .vtt extension)
        
    Returns:
        Normalized episode title, or None if format doesn't match
        
    Examples:
        >>> extract_title_from_filename("2022-10-06_Episode_Title.vtt")
        "Episode Title"
        
        >>> extract_title_from_filename("2022-10-06_The_Truth___How_To_Deal.vtt")
        "The Truth How To Deal"
    """
    if not filename:
        return None
    
    # Remove .vtt extension if present
    if filename.endswith('.vtt'):
        filename = filename[:-4]
    
    # Look for date pattern at start: YYYY-MM-DD_
    date_pattern = r'^(\d{4}-\d{2}-\d{2})_(.*)$'
    match = re.match(date_pattern, filename)
    
    if not match:
        # If no date pattern, treat entire filename as title
        raw_title = filename
    else:
        # Extract title part after date
        raw_title = match.group(2)
        
        # If raw_title is empty, return None
        if not raw_title:
            return None
    
    # Convert filesystem-safe format back to readable title
    # Handle triple underscores first (which represent " / " in the original)
    readable_title = raw_title.replace('___', ' / ')
    
    # Replace remaining underscores with spaces
    readable_title = readable_title.replace('_', ' ')
    
    # Return the readable title (don't normalize to preserve original structure)
    return readable_title.strip()


def make_filename_safe(title: str) -> str:
    """Convert a normalized title to a filesystem-safe filename component.
    
    This function should be used when creating filenames from episode titles.
    It preserves the ability to extract the original title later.
    
    Args:
        title: Normalized episode title
        
    Returns:
        Filesystem-safe string suitable for use in filenames
        
    Examples:
        >>> make_filename_safe("Episode Title Here")
        "Episode_Title_Here"
        
        >>> make_filename_safe("The Truth / How To Deal")
        "The_Truth___How_To_Deal"
    """
    if not title:
        return "untitled"
    
    # Start with the title (don't normalize yet to preserve slash structure)
    safe_title = title.strip()
    
    # Handle HTML entities first
    safe_title = html.unescape(safe_title)
    
    # Replace " / " pattern with triple underscore before other processing
    safe_title = re.sub(r'\s*/\s*', '___', safe_title)
    
    # Replace & with "and" for consistency  
    safe_title = re.sub(r'\s*&\s*', '_and_', safe_title)
    
    # Remove problematic punctuation
    safe_title = re.sub(r'[:<>;"\'\\|*?]', '', safe_title)
    
    # Replace any remaining slashes
    safe_title = re.sub(r'/', '___', safe_title)
    
    # Replace spaces with underscores
    safe_title = safe_title.replace(' ', '_')
    
    # Clean up multiple underscores (but preserve triple underscores)
    safe_title = re.sub(r'_{4,}', '___', safe_title)  # 4+ underscores become 3
    safe_title = re.sub(r'(?<!_)_{2}(?!_)', '_', safe_title)  # double underscores become single (except when part of triple)
    
    # Remove any remaining problematic characters for filesystems
    safe_title = re.sub(r'[<>:"|?*\\]', '', safe_title)
    
    # Remove leading/trailing underscores and dots
    safe_title = safe_title.strip('_.')
    
    # Ensure not empty
    if not safe_title:
        safe_title = "untitled"
    
    return safe_title