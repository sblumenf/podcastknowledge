"""Progress tracking for podcast transcription.

This module provides functionality to track which episodes have been transcribed
to avoid duplicate processing.
"""

import json
import os
import sys
import threading
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from enum import Enum

# Add shared module to path
repo_root = Path(__file__).parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.utils.logging import get_logger
from src.utils.title_utils import normalize_title

# Import shared tracking bridge for Neo4j checking
try:
    from shared import get_tracker
    tracking_bridge = get_tracker()
except ImportError:
    # Fallback if shared module not available
    tracking_bridge = None
    
logger = get_logger(__name__)


class EpisodeStatus(Enum):
    """Status of an episode in the transcription pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProgressTracker:
    """Tracks transcription progress to avoid duplicate processing."""
    
    def __init__(self, tracking_file_path: str = "data/transcribed_episodes.json"):
        """Initialize progress tracker.
        
        Args:
            tracking_file_path: Path to JSON file storing progress data
        """
        self.tracking_file_path = tracking_file_path
        self._lock = threading.Lock()
        self._progress_data: Dict[str, List[str]] = {}
        
        # Ensure data directory exists
        Path(self.tracking_file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing progress
        self.load_progress()
    
    def load_progress(self) -> Dict[str, List[str]]:
        """Load progress data from tracking file.
        
        Returns:
            Dictionary mapping podcast names to lists of transcribed episode titles
        """
        with self._lock:
            if os.path.exists(self.tracking_file_path):
                try:
                    with open(self.tracking_file_path, 'r', encoding='utf-8') as f:
                        self._progress_data = json.load(f)
                    logger.info(f"Loaded progress data for {len(self._progress_data)} podcasts")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Error loading progress file: {e}")
                    self._progress_data = {}
            else:
                logger.info("No existing progress file found, starting fresh")
                self._progress_data = {}
            
            return self._progress_data.copy()
    
    def save_progress(self, progress: Optional[Dict[str, List[str]]] = None) -> None:
        """Save progress data to tracking file.
        
        Args:
            progress: Optional progress data to save (uses internal data if not provided)
        """
        with self._lock:
            if progress is not None:
                self._progress_data = progress
            
            try:
                # Write to temporary file first for atomic operation
                temp_path = f"{self.tracking_file_path}.tmp"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._progress_data, f, indent=2, ensure_ascii=False)
                
                # Rename temporary file to actual file (atomic on most systems)
                os.replace(temp_path, self.tracking_file_path)
                logger.debug(f"Saved progress data for {len(self._progress_data)} podcasts")
            except IOError as e:
                logger.error(f"Error saving progress file: {e}")
                # Clean up temp file if it exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
    
    def is_episode_transcribed(self, podcast_name: str, episode_title: str, date: Optional[str] = None) -> bool:
        """Check if an episode has already been transcribed.
        
        Also checks Neo4j when available to ensure we don't miss episodes that
        were processed through the seeding pipeline.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode (will be normalized before comparison)
            date: Optional date string for Neo4j checking (format: YYYY-MM-DD)
            
        Returns:
            True if episode has been transcribed, False otherwise
        """
        # First check file-based tracking
        normalized_title = normalize_title(episode_title)
        
        with self._lock:
            if podcast_name in self._progress_data and normalized_title in self._progress_data[podcast_name]:
                logger.debug(f"Episode found in file-based tracking: {podcast_name} - {normalized_title}")
                return True
        
        # Also check Neo4j if available and date provided
        if tracking_bridge and date:
            try:
                # Generate podcast ID (matching seeding pipeline format)
                podcast_id = podcast_name.lower().replace(' ', '_')
                
                # Check if episode exists in knowledge graph
                if not tracking_bridge.should_transcribe(podcast_id, episode_title, date):
                    logger.info(f"Episode found in Neo4j knowledge graph: {podcast_name} - {episode_title}")
                    return True
            except Exception as e:
                logger.debug(f"Neo4j check failed, continuing with file-based tracking only: {e}")
        
        return False
    
    def mark_episode_transcribed(self, podcast_name: str, episode_title: str, date: str) -> None:
        """Mark an episode as transcribed.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode (will be normalized before storage)
            date: Date string (for logging purposes, not stored)
        """
        # Normalize the title for consistent storage
        normalized_title = normalize_title(episode_title)
        
        with self._lock:
            if podcast_name not in self._progress_data:
                self._progress_data[podcast_name] = []
            
            if normalized_title not in self._progress_data[podcast_name]:
                self._progress_data[podcast_name].append(normalized_title)
                logger.info(f"Marked as transcribed: {podcast_name} - {normalized_title} ({date})")
                
                # Save immediately to persist progress
                self.save_progress()
    
    def get_transcribed_episodes(self, podcast_name: str) -> List[str]:
        """Get list of transcribed episodes for a podcast.
        
        Args:
            podcast_name: Name of the podcast
            
        Returns:
            List of transcribed episode titles
        """
        with self._lock:
            return self._progress_data.get(podcast_name, []).copy()
    
    def get_all_podcasts(self) -> List[str]:
        """Get list of all podcasts with transcribed episodes.
        
        Returns:
            List of podcast names
        """
        with self._lock:
            return list(self._progress_data.keys())
    
    def get_total_transcribed_count(self) -> int:
        """Get total number of transcribed episodes across all podcasts.
        
        Returns:
            Total count of transcribed episodes
        """
        with self._lock:
            return sum(len(episodes) for episodes in self._progress_data.values())
    
    def remove_episode(self, podcast_name: str, episode_title: str) -> bool:
        """Remove an episode from the transcribed list.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode (will be normalized before removal)
            
        Returns:
            True if episode was removed, False if not found
        """
        # Normalize the title for consistent lookup
        normalized_title = normalize_title(episode_title)
        
        with self._lock:
            if podcast_name in self._progress_data and normalized_title in self._progress_data[podcast_name]:
                self._progress_data[podcast_name].remove(normalized_title)
                
                # Remove podcast if no episodes left
                if not self._progress_data[podcast_name]:
                    del self._progress_data[podcast_name]
                
                self.save_progress()
                logger.info(f"Removed from progress: {podcast_name} - {normalized_title}")
                return True
            return False
    
    def clear_podcast(self, podcast_name: str) -> bool:
        """Clear all transcribed episodes for a podcast.
        
        Args:
            podcast_name: Name of the podcast
            
        Returns:
            True if podcast was cleared, False if not found
        """
        with self._lock:
            if podcast_name in self._progress_data:
                episode_count = len(self._progress_data[podcast_name])
                del self._progress_data[podcast_name]
                self.save_progress()
                logger.info(f"Cleared {episode_count} episodes for podcast: {podcast_name}")
                return True
            return False


# For compatibility with batch_progress.py which expects a state attribute
class ProgressState:
    """Progress state container for compatibility."""
    def __init__(self):
        self.episodes = {}
        

# Extend ProgressTracker for compatibility
class ExtendedProgressTracker(ProgressTracker):
    """Extended progress tracker with state attribute for batch progress."""
    
    def __init__(self, tracking_file_path: str = "data/transcribed_episodes.json"):
        super().__init__(tracking_file_path)
        self.state = ProgressState()