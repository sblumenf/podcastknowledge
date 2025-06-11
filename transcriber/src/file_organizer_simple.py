"""Simplified file organization system for podcast transcripts.

This module provides minimal functionality for generating consistent output paths
for VTT transcript files. It removes all manifest tracking and complex features.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from src.utils.logging import get_logger
from src.config import Config

logger = get_logger('file_organizer')


class SimpleFileOrganizer:
    """Simplified organizer that only generates output paths for transcripts."""
    
    def __init__(self, base_output_dir: Optional[str] = None, config: Optional[Config] = None):
        """Initialize file organizer.
        
        Args:
            base_output_dir: Base directory for storing transcripts. 
                           Defaults to TRANSCRIPT_OUTPUT_DIR environment variable.
            config: Optional configuration object. If provided, settings from config are used.
        """
        # Store config for later use
        self.config = config
        
        # Use explicit output directory from parameter or environment
        if base_output_dir:
            self.base_dir = Path(base_output_dir)
        else:
            # First check for new TRANSCRIPT_OUTPUT_DIR variable
            env_dir = os.getenv('TRANSCRIPT_OUTPUT_DIR')
            if env_dir:
                self.base_dir = Path(env_dir)
            elif config:
                # Fall back to config if available
                self.base_dir = Path(config.output.default_dir)
            else:
                # Fall back to old env var or default
                self.base_dir = Path(os.getenv('PODCAST_OUTPUT_DIR', 'data/transcripts'))
        
        # Only create directory if it's not a test path
        if not str(self.base_dir).startswith('/test'):
            self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, name: str) -> str:
        """Sanitize a filename by removing or replacing special characters.
        
        Args:
            name: Original filename or component
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        if not name:
            return "unknown"
        
        # Check if sanitization is disabled in config
        if self.config and hasattr(self.config.output, 'sanitize_filenames'):
            if not self.config.output.sanitize_filenames:
                # If sanitization is disabled, only do minimal cleanup
                return name.strip()
        
        # Replace common problematic characters
        sanitized = name.strip()
        
        # Replace multiple whitespace with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Remove or replace special characters first
        sanitized = re.sub(r'[<>:"|?*\\]', '', sanitized)  # Windows forbidden chars
        sanitized = re.sub(r'[^\w\s\-_.,()&/]', '', sanitized)  # Keep safe chars only
        
        # Replace " / " pattern with double underscore first
        sanitized = re.sub(r'\s*/\s*', '__', sanitized)
        
        # Replace remaining spaces with underscores for consistency
        sanitized = sanitized.replace(' ', '_')
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Truncate if too long (use config value if available)
        max_length = 200
        if self.config:
            max_length = self.config.output.max_filename_length
        
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip('_.')
        
        # Ensure not empty after sanitization
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized
    
    def get_output_path(self, episode: 'Episode') -> Path:
        """Get the output path for an Episode object.
        
        Args:
            episode: Episode object from feed parser.
            
        Returns:
            Path object for the output VTT file.
        """
        # Extract podcast name from episode if available
        podcast_name = getattr(episode, 'podcast_name', 'Unknown_Podcast')
        
        # Format publication date
        if hasattr(episode, 'published_date') and episode.published_date:
            pub_date = episode.published_date.strftime('%Y-%m-%d')
        else:
            pub_date = datetime.now().strftime('%Y-%m-%d')
        
        # Sanitize components
        clean_podcast = self.sanitize_filename(podcast_name)
        clean_title = self.sanitize_filename(episode.title)
        
        # Create filename based on config pattern or default
        if self.config and hasattr(self.config.output, 'naming_pattern'):
            # Use config pattern
            pattern = self.config.output.naming_pattern
            filename = pattern.format(
                podcast_name=clean_podcast,
                date=pub_date,
                episode_title=clean_title
            )
        else:
            # Use default pattern: {podcast_name}/{date}_{episode_title}.vtt
            filename = f"{clean_podcast}/{pub_date}_{clean_title}.vtt"
        
        # Ensure .vtt extension
        if not filename.endswith('.vtt'):
            filename = filename + '.vtt'
        
        full_path = self.base_dir / filename
        
        # Create directory if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        return full_path