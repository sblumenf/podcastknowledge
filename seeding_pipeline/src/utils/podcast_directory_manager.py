"""Podcast-aware directory management utilities."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PodcastDirectoryManager:
    """Manages podcast-specific directory structures."""
    
    def __init__(self, base_data_dir: Optional[str] = None):
        """Initialize directory manager.
        
        Args:
            base_data_dir: Base data directory. Defaults to PODCAST_DATA_DIR env var.
        """
        self.base_data_dir = Path(base_data_dir or os.getenv('PODCAST_DATA_DIR', '/data'))
        self.podcasts_dir = self.base_data_dir / 'podcasts'
        
        # Ensure podcasts directory exists
        self.podcasts_dir.mkdir(parents=True, exist_ok=True)
        
    def get_podcast_directory(self, podcast_id: str) -> Path:
        """Get the base directory for a podcast.
        
        Args:
            podcast_id: Unique identifier for the podcast
            
        Returns:
            Path to podcast directory
        """
        return self.podcasts_dir / podcast_id
        
    def get_podcast_subdirectory(self, podcast_id: str, subdir: str) -> Path:
        """Get a specific subdirectory for a podcast.
        
        Args:
            podcast_id: Unique identifier for the podcast
            subdir: Subdirectory name (transcripts, processed, checkpoints)
            
        Returns:
            Path to podcast subdirectory
        """
        return self.get_podcast_directory(podcast_id) / subdir
        
    def ensure_podcast_structure(self, podcast_id: str) -> Dict[str, Path]:
        """Create podcast directory structure if it doesn't exist.
        
        Args:
            podcast_id: Unique identifier for the podcast
            
        Returns:
            Dictionary of created directories
        """
        podcast_dir = self.get_podcast_directory(podcast_id)
        
        # Create standard subdirectories
        dirs = {
            'base': podcast_dir,
            'transcripts': podcast_dir / 'transcripts',
            'processed': podcast_dir / 'processed',
            'checkpoints': podcast_dir / 'checkpoints',
            'logs': podcast_dir / 'logs',
            'metadata': podcast_dir / 'metadata'
        }
        
        for name, path in dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {path}")
            
        return dirs
        
    def list_podcasts(self) -> List[str]:
        """List all podcast IDs.
        
        Returns:
            List of podcast directory names
        """
        if not self.podcasts_dir.exists():
            return []
            
        return [d.name for d in self.podcasts_dir.iterdir() if d.is_dir()]
        
    def get_podcast_from_vtt_path(self, vtt_path: Path) -> Optional[str]:
        """Extract podcast ID from a VTT file path.
        
        Args:
            vtt_path: Path to VTT file
            
        Returns:
            Podcast ID if found, None otherwise
        """
        # Try to extract from path structure
        path_parts = vtt_path.parts
        
        # Look for 'podcasts' in path
        if 'podcasts' in path_parts:
            idx = path_parts.index('podcasts')
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]
                
        # Try legacy structure (direct under transcripts)
        if 'transcripts' in path_parts:
            idx = path_parts.index('transcripts')
            if idx + 1 < len(path_parts) and path_parts[idx + 1] != vtt_path.name:
                # There's a directory between transcripts and the file
                return path_parts[idx + 1]
                
        return None
        
    def migrate_to_podcast_structure(self, source_dir: Path, podcast_id: str) -> int:
        """Migrate files from flat structure to podcast-aware structure.
        
        Args:
            source_dir: Source directory containing files
            podcast_id: Target podcast ID
            
        Returns:
            Number of files migrated
        """
        if not source_dir.exists():
            return 0
            
        # Ensure target structure exists
        dirs = self.ensure_podcast_structure(podcast_id)
        
        # Map source subdirs to target subdirs
        subdir_mapping = {
            'transcripts': dirs['transcripts'],
            'processed': dirs['processed'],
            'checkpoints': dirs['checkpoints']
        }
        
        migrated = 0
        for subdir, target_dir in subdir_mapping.items():
            source_subdir = source_dir / subdir
            if source_subdir.exists() and source_subdir.is_dir():
                for file_path in source_subdir.rglob('*'):
                    if file_path.is_file():
                        # Calculate relative path
                        rel_path = file_path.relative_to(source_subdir)
                        target_path = target_dir / rel_path
                        
                        # Create target directory
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Move file
                        file_path.rename(target_path)
                        migrated += 1
                        logger.info(f"Migrated {file_path} to {target_path}")
                        
        return migrated
        
    def get_all_vtt_files(self, podcast_id: Optional[str] = None) -> List[Tuple[str, Path]]:
        """Get all VTT files across podcasts.
        
        Args:
            podcast_id: Optional specific podcast to filter by
            
        Returns:
            List of (podcast_id, vtt_path) tuples
        """
        vtt_files = []
        
        if podcast_id:
            # Single podcast
            transcripts_dir = self.get_podcast_subdirectory(podcast_id, 'transcripts')
            if transcripts_dir.exists():
                for vtt_path in transcripts_dir.rglob('*.vtt'):
                    vtt_files.append((podcast_id, vtt_path))
        else:
            # All podcasts
            for pid in self.list_podcasts():
                transcripts_dir = self.get_podcast_subdirectory(pid, 'transcripts')
                if transcripts_dir.exists():
                    for vtt_path in transcripts_dir.rglob('*.vtt'):
                        vtt_files.append((pid, vtt_path))
                        
        return vtt_files