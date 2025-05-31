"""File organization system for podcast transcripts.

This module provides functionality for organizing VTT transcript files with
consistent naming patterns, directory structure, and metadata tracking.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

from src.utils.logging import get_logger

logger = get_logger('file_organizer')


@dataclass
class EpisodeMetadata:
    """Metadata for a single episode."""
    title: str
    podcast_name: str
    publication_date: str  # YYYY-MM-DD format
    file_path: str
    speakers: List[str]
    duration: Optional[int] = None  # in seconds
    episode_number: Optional[int] = None
    description: Optional[str] = None
    processed_date: str = ""  # When transcription was completed
    
    def __post_init__(self):
        if not self.processed_date:
            self.processed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileOrganizer:
    """Organizes podcast transcript files with consistent naming and structure."""
    
    def __init__(self, base_dir: str = "data/transcripts"):
        """Initialize file organizer.
        
        Args:
            base_dir: Base directory for storing transcripts
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Track used filenames to handle duplicates
        self._used_filenames: Set[str] = set()
        
        # Load existing manifest if it exists
        self.manifest_file = self.base_dir / "manifest.json"
        self.episodes: List[EpisodeMetadata] = self._load_manifest()
        
        # Update used filenames from existing episodes
        for episode in self.episodes:
            self._used_filenames.add(episode.file_path)
    
    def sanitize_filename(self, name: str) -> str:
        """Sanitize a filename by removing or replacing special characters.
        
        Args:
            name: Original filename or component
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        if not name:
            return "unknown"
        
        # Replace common problematic characters
        sanitized = name.strip()
        
        # Replace multiple whitespace with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Remove or replace special characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)  # Windows forbidden chars
        sanitized = re.sub(r'[^\w\s\-_.,()&]', '', sanitized)  # Keep safe chars only
        
        # Replace spaces with underscores for consistency
        sanitized = sanitized.replace(' ', '_')
        
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Truncate if too long (keep under 200 chars as per config)
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rstrip('_.')
        
        # Ensure not empty after sanitization
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized
    
    def generate_filename(self, podcast_name: str, episode_title: str, 
                         publication_date: str) -> Tuple[str, str]:
        """Generate a consistent filename for an episode.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            publication_date: Publication date in YYYY-MM-DD format
            
        Returns:
            Tuple of (relative_path, full_path) for the VTT file
        """
        # Sanitize components
        clean_podcast = self.sanitize_filename(podcast_name)
        clean_title = self.sanitize_filename(episode_title)
        
        # Validate date format
        try:
            datetime.strptime(publication_date, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Invalid date format: {publication_date}, using current date")
            publication_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create base filename: {date}_{episode_title}.vtt
        base_filename = f"{publication_date}_{clean_title}.vtt"
        
        # Handle duplicate filenames
        counter = 1
        filename = base_filename
        podcast_dir = clean_podcast
        
        while True:
            relative_path = f"{podcast_dir}/{filename}"
            full_path = str(self.base_dir / relative_path)
            
            if relative_path not in self._used_filenames:
                break
            
            # Create unique filename by adding counter
            stem = base_filename[:-4]  # Remove .vtt extension
            filename = f"{stem}_{counter:03d}.vtt"
            counter += 1
            
            # Prevent infinite loop
            if counter > 1000:
                logger.error(f"Could not generate unique filename for {episode_title}")
                filename = f"{publication_date}_{clean_title}_{datetime.now().strftime('%H%M%S')}.vtt"
                relative_path = f"{podcast_dir}/{filename}"
                full_path = str(self.base_dir / relative_path)
                break
        
        return relative_path, full_path
    
    def create_episode_file(self, podcast_name: str, episode_title: str,
                           publication_date: str, speakers: List[str],
                           content: str, duration: Optional[int] = None,
                           episode_number: Optional[int] = None,
                           description: Optional[str] = None) -> EpisodeMetadata:
        """Create and save an episode VTT file with proper organization.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            publication_date: Publication date in YYYY-MM-DD format
            speakers: List of speaker names/roles
            content: VTT file content
            duration: Episode duration in seconds
            episode_number: Episode number if available
            description: Episode description
            
        Returns:
            EpisodeMetadata object for the created file
        """
        # Generate filename and path
        relative_path, full_path = self.generate_filename(
            podcast_name, episode_title, publication_date
        )
        
        # Create directory structure
        file_path = Path(full_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write VTT content to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created episode file: {relative_path}")
            
        except Exception as e:
            logger.error(f"Failed to write episode file {full_path}: {e}")
            raise
        
        # Create metadata object
        metadata = EpisodeMetadata(
            title=episode_title,
            podcast_name=podcast_name,
            publication_date=publication_date,
            file_path=relative_path,
            speakers=speakers,
            duration=duration,
            episode_number=episode_number,
            description=description
        )
        
        # Add to episodes list and update manifest
        self.episodes.append(metadata)
        self._used_filenames.add(relative_path)
        self._save_manifest()
        
        return metadata
    
    def _load_manifest(self) -> List[EpisodeMetadata]:
        """Load existing episode manifest.
        
        Returns:
            List of EpisodeMetadata objects
        """
        if not self.manifest_file.exists():
            return []
        
        try:
            with open(self.manifest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            episodes = []
            for item in data.get('episodes', []):
                episodes.append(EpisodeMetadata(**item))
            
            logger.info(f"Loaded {len(episodes)} episodes from manifest")
            return episodes
            
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return []
    
    def _save_manifest(self):
        """Save episode manifest to disk."""
        try:
            data = {
                'version': '1.0',
                'generated_at': datetime.now().isoformat(),
                'total_episodes': len(self.episodes),
                'episodes': [asdict(episode) for episode in self.episodes]
            }
            
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved manifest with {len(self.episodes)} episodes")
            
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
    
    def get_episodes_by_podcast(self, podcast_name: str) -> List[EpisodeMetadata]:
        """Get all episodes for a specific podcast.
        
        Args:
            podcast_name: Name of the podcast
            
        Returns:
            List of episodes for the podcast
        """
        clean_name = self.sanitize_filename(podcast_name)
        return [ep for ep in self.episodes 
                if self.sanitize_filename(ep.podcast_name) == clean_name]
    
    def get_episodes_by_date_range(self, start_date: str, end_date: str) -> List[EpisodeMetadata]:
        """Get episodes within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of episodes in the date range
        """
        return [ep for ep in self.episodes 
                if start_date <= ep.publication_date <= end_date]
    
    def get_episodes_by_speaker(self, speaker_name: str) -> List[EpisodeMetadata]:
        """Get episodes featuring a specific speaker.
        
        Args:
            speaker_name: Name or role of the speaker
            
        Returns:
            List of episodes featuring the speaker
        """
        return [ep for ep in self.episodes 
                if any(speaker_name.lower() in speaker.lower() 
                      for speaker in ep.speakers)]
    
    def get_directory_structure(self) -> Dict[str, List[str]]:
        """Get the current directory structure.
        
        Returns:
            Dictionary mapping podcast names to their episode files
        """
        structure = {}
        for episode in self.episodes:
            podcast_dir = episode.file_path.split('/')[0]
            if podcast_dir not in structure:
                structure[podcast_dir] = []
            structure[podcast_dir].append(episode.file_path)
        
        return structure
    
    def cleanup_empty_directories(self):
        """Remove empty podcast directories."""
        for item in self.base_dir.iterdir():
            if item.is_dir():
                try:
                    # Try to remove directory if empty
                    item.rmdir()
                    logger.info(f"Removed empty directory: {item.name}")
                except OSError:
                    # Directory not empty, which is expected
                    pass
    
    def validate_files(self) -> Dict[str, List[str]]:
        """Validate that all files in manifest actually exist.
        
        Returns:
            Dictionary with 'missing' and 'extra' file lists
        """
        missing_files = []
        existing_files = set()
        
        # Check manifest files
        for episode in self.episodes:
            file_path = self.base_dir / episode.file_path
            if file_path.exists():
                existing_files.add(episode.file_path)
            else:
                missing_files.append(episode.file_path)
        
        # Find extra files not in manifest
        extra_files = []
        for vtt_file in self.base_dir.rglob("*.vtt"):
            relative_path = str(vtt_file.relative_to(self.base_dir))
            if relative_path not in existing_files and relative_path != "manifest.json":
                extra_files.append(relative_path)
        
        return {
            'missing': missing_files,
            'extra': extra_files
        }
    
    def get_stats(self) -> Dict[str, any]:
        """Get statistics about the organized files.
        
        Returns:
            Dictionary with various statistics
        """
        if not self.episodes:
            return {'total_episodes': 0}
        
        podcasts = set(ep.podcast_name for ep in self.episodes)
        speakers = set()
        for ep in self.episodes:
            speakers.update(ep.speakers)
        
        # Date range
        dates = [ep.publication_date for ep in self.episodes if ep.publication_date]
        date_range = (min(dates), max(dates)) if dates else (None, None)
        
        # Total duration
        total_duration = sum(ep.duration for ep in self.episodes if ep.duration)
        
        return {
            'total_episodes': len(self.episodes),
            'total_podcasts': len(podcasts),
            'total_speakers': len(speakers),
            'date_range': date_range,
            'total_duration_seconds': total_duration,
            'total_duration_hours': round(total_duration / 3600, 2) if total_duration else 0,
            'average_episode_duration': round(total_duration / len(self.episodes), 2) 
                                      if self.episodes and total_duration else 0
        }