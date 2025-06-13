"""
Shared episode ID generation for consistent identification across modules.

This module provides the canonical episode ID generation logic used by both
the transcriber and seeding_pipeline to ensure episodes are consistently
identified regardless of which module processes them.
"""

import re
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional


def normalize_for_id(text: str) -> str:
    """
    Normalize text for use in episode IDs.
    
    This creates a consistent, filesystem-safe identifier component.
    
    Args:
        text: Text to normalize (typically episode title)
        
    Returns:
        Normalized text suitable for ID generation
    """
    if not text:
        return "unknown"
    
    # Start with Unicode normalization
    normalized = unicodedata.normalize('NFKC', text)
    
    # Convert to lowercase for consistency
    normalized = normalized.lower()
    
    # Remove all non-alphanumeric characters except spaces and hyphens
    normalized = re.sub(r'[^a-z0-9\s-]', '', normalized)
    
    # Replace multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Replace spaces with underscores
    normalized = normalized.replace(' ', '_')
    
    # Remove multiple underscores
    normalized = re.sub(r'_+', '_', normalized)
    
    # Strip leading/trailing underscores
    normalized = normalized.strip('_')
    
    # Ensure not empty
    return normalized or "untitled"


def extract_components_from_filename(filename: str) -> Tuple[Optional[str], str]:
    """
    Extract date and title components from a VTT filename.
    
    Expected format: YYYY-MM-DD_Episode_Title.vtt or variations
    
    Args:
        filename: VTT filename (with or without path and extension)
        
    Returns:
        Tuple of (date_str, title) where date_str may be None
    """
    # Get just the filename without path or extension
    if isinstance(filename, Path):
        filename = filename.name
    else:
        filename = Path(filename).name
    
    # Remove .vtt extension if present
    if filename.endswith('.vtt'):
        filename = filename[:-4]
    
    # Common date patterns in filenames
    date_patterns = [
        (r'^(\d{4}-\d{2}-\d{2})[\s_]+(.*)', None),           # YYYY-MM-DD_Title
        (r'^(\d{4}_\d{2}_\d{2})[\s_]+(.*)', '_'),           # YYYY_MM_DD_Title
        (r'^(\d{8})[\s_]+(.*)', 'compact'),                  # YYYYMMDD_Title
        (r'.*_(\d{4}-\d{2}-\d{2})$', None),                  # Title_YYYY-MM-DD
        (r'.*_(\d{8})$', 'compact'),                         # Title_YYYYMMDD
    ]
    
    date_str = None
    title = filename
    
    for pattern, date_format in date_patterns:
        match = re.match(pattern, filename)
        if match:
            if len(match.groups()) == 2:
                date_str = match.group(1)
                title = match.group(2)
            else:
                date_str = match.group(1)
                # Remove date from end of filename
                title = re.sub(pattern, '', filename)
            
            # Normalize date format
            if date_format == '_':
                date_str = date_str.replace('_', '-')
            elif date_format == 'compact' and len(date_str) == 8:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            break
    
    # Clean up the title
    title = title.strip('_- ')
    
    return date_str, title


def generate_episode_id(vtt_path: str, podcast_id: str) -> str:
    """
    Generate unique episode ID from VTT file path and podcast ID.
    
    This is the canonical implementation used by both transcriber and seeding_pipeline.
    
    Format: {podcast_id}_{date}_{normalized_title}
    
    Args:
        vtt_path: Path to VTT file (can be string or Path object)
        podcast_id: Podcast identifier
        
    Returns:
        Generated episode ID
    """
    # Ensure we have a Path object
    path = Path(vtt_path) if not isinstance(vtt_path, Path) else vtt_path
    
    # Extract date and title from filename
    date_str, title = extract_components_from_filename(path.name)
    
    # If no date found in filename, try file modification time
    if not date_str:
        try:
            mtime = path.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        except:
            # Fallback to current date if file doesn't exist or other error
            date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Normalize the podcast ID
    normalized_podcast_id = normalize_for_id(podcast_id)
    
    # Normalize the title
    normalized_title = normalize_for_id(title)
    
    # Construct the episode ID
    episode_id = f"{normalized_podcast_id}_{date_str}_{normalized_title}"
    
    return episode_id


def parse_episode_id(episode_id: str) -> Tuple[str, str, str]:
    """
    Parse an episode ID back into its components.
    
    Args:
        episode_id: Episode ID in format podcast_date_title
        
    Returns:
        Tuple of (podcast_id, date, title)
        
    Raises:
        ValueError: If episode ID format is invalid
    """
    parts = episode_id.split('_', 2)
    
    if len(parts) < 3:
        raise ValueError(f"Invalid episode ID format: {episode_id}")
    
    podcast_id = parts[0]
    
    # The date should be the second part
    date_match = re.match(r'^\d{4}-\d{2}-\d{2}$', parts[1])
    if date_match:
        date = parts[1]
        title = parts[2] if len(parts) > 2 else ""
    else:
        # Maybe date is missing, treat second part as title
        date = "unknown"
        title = '_'.join(parts[1:])
    
    return podcast_id, date, title