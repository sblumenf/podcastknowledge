"""Progress Tracker Module for Podcast Transcription Pipeline.

This module manages episode processing state, tracking which episodes 
are completed, failed, or pending. Uses atomic file writes to prevent
corruption in case of interruptions.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.utils.logging import get_logger

logger = get_logger('progress_tracker')


class EpisodeStatus(Enum):
    """Enumeration of possible episode processing states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EpisodeProgress:
    """Tracks the processing progress of a single episode."""
    
    guid: str
    status: EpisodeStatus
    
    # Episode metadata for reference
    podcast_name: str = ""
    title: str = ""
    audio_url: str = ""
    publication_date: Optional[str] = None
    
    # Processing metadata
    attempt_count: int = 0
    last_attempt: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    
    # Output information
    output_file: Optional[str] = None
    
    # Error tracking
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    # API key tracking
    api_key_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'guid': self.guid,
            'status': self.status.value,
            'podcast_name': self.podcast_name,
            'title': self.title,
            'audio_url': self.audio_url,
            'publication_date': self.publication_date,
            'attempt_count': self.attempt_count,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'processing_time_seconds': self.processing_time_seconds,
            'output_file': self.output_file,
            'error': self.error,
            'error_type': self.error_type,
            'api_key_used': self.api_key_used
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpisodeProgress':
        """Create instance from dictionary."""
        # Convert status string to enum
        status = EpisodeStatus(data.get('status', 'pending'))
        
        # Parse datetime fields
        last_attempt = None
        if data.get('last_attempt'):
            last_attempt = datetime.fromisoformat(data['last_attempt'])
            
        completed_at = None
        if data.get('completed_at'):
            completed_at = datetime.fromisoformat(data['completed_at'])
        
        return cls(
            guid=data['guid'],
            status=status,
            podcast_name=data.get('podcast_name', ''),
            title=data.get('title', ''),
            audio_url=data.get('audio_url', ''),
            publication_date=data.get('publication_date'),
            attempt_count=data.get('attempt_count', 0),
            last_attempt=last_attempt,
            completed_at=completed_at,
            processing_time_seconds=data.get('processing_time_seconds'),
            output_file=data.get('output_file'),
            error=data.get('error'),
            error_type=data.get('error_type'),
            api_key_used=data.get('api_key_used')
        )


@dataclass
class ProgressState:
    """Overall progress tracking state."""
    
    # Metadata
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_processed: int = 0
    daily_quota_used: int = 0
    quota_reset_time: Optional[datetime] = None
    
    # Episode tracking
    episodes: Dict[str, EpisodeProgress] = field(default_factory=dict)
    
    # API key rotation state
    next_key_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'meta': {
                'last_updated': self.last_updated.isoformat(),
                'total_processed': self.total_processed,
                'daily_quota_used': self.daily_quota_used,
                'quota_reset_time': self.quota_reset_time.isoformat() if self.quota_reset_time else None,
                'next_key_index': self.next_key_index
            },
            'episodes': {
                guid: ep.to_dict() for guid, ep in self.episodes.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressState':
        """Create instance from dictionary."""
        meta = data.get('meta', {})
        
        # Parse metadata
        last_updated = datetime.now(timezone.utc)
        if meta.get('last_updated'):
            last_updated = datetime.fromisoformat(meta['last_updated'])
            
        quota_reset_time = None
        if meta.get('quota_reset_time'):
            quota_reset_time = datetime.fromisoformat(meta['quota_reset_time'])
        
        # Parse episodes
        episodes = {}
        for guid, ep_data in data.get('episodes', {}).items():
            episodes[guid] = EpisodeProgress.from_dict(ep_data)
        
        return cls(
            last_updated=last_updated,
            total_processed=meta.get('total_processed', 0),
            daily_quota_used=meta.get('daily_quota_used', 0),
            quota_reset_time=quota_reset_time,
            episodes=episodes,
            next_key_index=meta.get('next_key_index', 0)
        )


class ProgressTracker:
    """Manages episode processing progress with atomic file operations."""
    
    def __init__(self, progress_file: Path):
        """Initialize progress tracker.
        
        Args:
            progress_file: Path to the progress JSON file
        """
        self.progress_file = progress_file
        self.state = self._load_state()
        logger.info(f"Progress tracker initialized with {len(self.state.episodes)} episodes")
    
    def _load_state(self) -> ProgressState:
        """Load progress state from file, creating if doesn't exist."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                return ProgressState.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load progress file: {e}")
                logger.warning("Starting with empty progress state")
        
        return ProgressState()
    
    def _save_state(self):
        """Save progress state to file atomically."""
        # Ensure directory exists
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Use atomic write pattern
        try:
            # Create temporary file in same directory as target
            with tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                dir=self.progress_file.parent,
                prefix='.progress_',
                suffix='.json.tmp'
            ) as tmp_file:
                # Write JSON data
                json.dump(self.state.to_dict(), tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())  # Force write to disk
                temp_path = tmp_file.name
            
            # Atomic rename
            os.replace(temp_path, self.progress_file)
            logger.debug("Progress state saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save progress state: {e}")
            # Clean up temp file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise
    
    def mark_started(self, episode_data: Dict[str, Any], api_key_index: int = 0):
        """Mark an episode as started/in-progress.
        
        Args:
            episode_data: Episode information including guid, title, etc.
            api_key_index: Index of API key being used
        """
        guid = episode_data['guid']
        
        # Get or create episode progress
        if guid in self.state.episodes:
            episode = self.state.episodes[guid]
        else:
            episode = EpisodeProgress(guid=guid, status=EpisodeStatus.PENDING)
            self.state.episodes[guid] = episode
        
        # Update episode data
        episode.status = EpisodeStatus.IN_PROGRESS
        episode.podcast_name = episode_data.get('podcast_name', '')
        episode.title = episode_data.get('title', '')
        episode.audio_url = episode_data.get('audio_url', '')
        episode.publication_date = episode_data.get('publication_date')
        episode.attempt_count += 1
        episode.last_attempt = datetime.now(timezone.utc)
        episode.api_key_used = f"key_{api_key_index + 1}"
        
        # Clear any previous error
        episode.error = None
        episode.error_type = None
        
        # Update metadata
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Save state
        self._save_state()
        logger.info(f"Episode '{episode.title}' marked as in-progress (attempt #{episode.attempt_count})")
    
    def mark_completed(self, guid: str, output_file: str, processing_time: float):
        """Mark an episode as completed.
        
        Args:
            guid: Episode GUID
            output_file: Path to generated VTT file
            processing_time: Time taken to process in seconds
        """
        if guid not in self.state.episodes:
            logger.error(f"Episode {guid} not found in progress tracker")
            return
        
        episode = self.state.episodes[guid]
        episode.status = EpisodeStatus.COMPLETED
        episode.completed_at = datetime.now(timezone.utc)
        episode.output_file = output_file
        episode.processing_time_seconds = processing_time
        
        # Update counters
        self.state.total_processed += 1
        self.state.daily_quota_used += 2  # 2 API calls per episode
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Save state
        self._save_state()
        logger.info(f"Episode '{episode.title}' marked as completed in {processing_time:.1f}s")
    
    def mark_failed(self, guid: str, error: str, error_type: Optional[str] = None):
        """Mark an episode as failed.
        
        Args:
            guid: Episode GUID
            error: Error message
            error_type: Type of error (e.g., 'quota_exceeded', 'network_error')
        """
        if guid not in self.state.episodes:
            logger.error(f"Episode {guid} not found in progress tracker")
            return
        
        episode = self.state.episodes[guid]
        episode.status = EpisodeStatus.FAILED
        episode.error = error
        episode.error_type = error_type or 'unknown'
        
        # Update metadata
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Save state
        self._save_state()
        logger.warning(f"Episode '{episode.title}' marked as failed: {error}")
    
    def get_pending(self) -> List[EpisodeProgress]:
        """Get list of pending episodes (not yet processed).
        
        Returns:
            List of episodes with PENDING status
        """
        return [
            ep for ep in self.state.episodes.values()
            if ep.status == EpisodeStatus.PENDING
        ]
    
    def get_failed(self, max_attempts: int = 2) -> List[EpisodeProgress]:
        """Get list of failed episodes that can be retried.
        
        Args:
            max_attempts: Maximum number of attempts before giving up
            
        Returns:
            List of failed episodes with attempts < max_attempts
        """
        return [
            ep for ep in self.state.episodes.values()
            if ep.status == EpisodeStatus.FAILED and ep.attempt_count < max_attempts
        ]
    
    def get_in_progress(self) -> List[EpisodeProgress]:
        """Get list of episodes currently being processed.
        
        These might be from interrupted runs.
        
        Returns:
            List of episodes with IN_PROGRESS status
        """
        return [
            ep for ep in self.state.episodes.values()
            if ep.status == EpisodeStatus.IN_PROGRESS
        ]
    
    def add_episode(self, episode_data: Dict[str, Any]):
        """Add a new episode to track.
        
        Args:
            episode_data: Episode information including guid, title, etc.
        """
        guid = episode_data['guid']
        
        # Skip if already exists
        if guid in self.state.episodes:
            logger.debug(f"Episode {guid} already in tracker")
            return
        
        # Create new episode progress
        episode = EpisodeProgress(
            guid=guid,
            status=EpisodeStatus.PENDING,
            podcast_name=episode_data.get('podcast_name', ''),
            title=episode_data.get('title', ''),
            audio_url=episode_data.get('audio_url', ''),
            publication_date=episode_data.get('publication_date')
        )
        
        self.state.episodes[guid] = episode
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Save state
        self._save_state()
        logger.debug(f"Added episode '{episode.title}' to tracker")
    
    def get_next_key_index(self) -> int:
        """Get the next API key index to use for round-robin rotation.
        
        Returns:
            Index of next API key to use
        """
        return self.state.next_key_index
    
    def update_key_index(self, new_index: int):
        """Update the next API key index.
        
        Args:
            new_index: New index value
        """
        self.state.next_key_index = new_index
        self.state.last_updated = datetime.now(timezone.utc)
        self._save_state()
    
    def reset_daily_quota(self):
        """Reset daily quota counters (usually at midnight UTC)."""
        self.state.daily_quota_used = 0
        self.state.quota_reset_time = datetime.now(timezone.utc)
        self.state.last_updated = datetime.now(timezone.utc)
        self._save_state()
        logger.info("Daily quota counters reset")
    
    def cleanup_interrupted(self):
        """Clean up interrupted episodes (mark IN_PROGRESS as FAILED)."""
        interrupted = self.get_in_progress()
        for episode in interrupted:
            self.mark_failed(
                episode.guid,
                "Processing interrupted - marked for retry",
                "interrupted"
            )
        
        if interrupted:
            logger.info(f"Cleaned up {len(interrupted)} interrupted episodes")