"""Batch Progress Tracker for Podcast Transcription Pipeline.

This module provides real-time progress monitoring for batch podcast processing,
showing detailed progress information including current episode, ETA, and statistics.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.utils.progress import ProgressBar
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.utils.logging import get_logger

logger = get_logger('batch_progress')


@dataclass
class BatchStats:
    """Statistics for batch processing session."""
    
    total_episodes: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    in_progress: int = 0
    
    start_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None
    
    # Episode processing times for ETA calculation
    processing_times: List[float] = None
    
    def __post_init__(self):
        if self.processing_times is None:
            self.processing_times = []
    
    @property
    def pending(self) -> int:
        """Number of pending episodes."""
        return self.total_episodes - self.completed - self.failed - self.skipped - self.in_progress
    
    @property
    def elapsed_time(self) -> float:
        """Elapsed time in seconds since batch started."""
        if self.start_time is None:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def average_processing_time(self) -> float:
        """Average processing time per episode in seconds."""
        if not self.processing_times:
            return 300.0  # Default 5 minutes per episode
        return sum(self.processing_times) / len(self.processing_times)
    
    @property
    def estimated_time_remaining(self) -> float:
        """Estimated time remaining in seconds."""
        remaining_episodes = self.pending + self.in_progress
        if remaining_episodes <= 0:
            return 0.0
        return remaining_episodes * self.average_processing_time
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        total_processed = self.completed + self.failed
        if total_processed == 0:
            return 0.0
        return (self.completed / total_processed) * 100


class BatchProgressTracker:
    """Real-time progress monitoring for batch podcast processing."""
    
    def __init__(self, progress_tracker: ProgressTracker, total_episodes: int):
        """Initialize batch progress tracker.
        
        Args:
            progress_tracker: ProgressTracker instance for episode state
            total_episodes: Total number of episodes to process
        """
        self.progress_tracker = progress_tracker
        self.stats = BatchStats(total_episodes=total_episodes)
        self.current_episode_title = ""
        self.current_episode_start_time: Optional[datetime] = None
        
        # Detect if we're resuming from previous progress
        self.is_resume_session = self._detect_resume_session()
        
        # Progress bar for display
        prefix = "Resuming Batch" if self.is_resume_session else "Batch Processing"
        self.progress_bar = ProgressBar(
            total=total_episodes,
            prefix=prefix
        )
        
        # Threading for periodic updates
        self._update_thread: Optional[threading.Thread] = None
        self._stop_updates = threading.Event()
        self._last_display_update = 0.0
        
        # Initialize stats
        self._update_stats()
        
        if self.is_resume_session:
            logger.info(f"Resuming batch processing: {self.stats.completed} episodes already completed, "
                       f"{total_episodes} episodes to process")
        else:
            logger.info(f"Starting new batch processing for {total_episodes} episodes")
    
    def _detect_resume_session(self) -> bool:
        """Detect if this is a resume session based on existing progress.
        
        Returns:
            True if there are already completed episodes
        """
        completed_count = len([
            ep for ep in self.progress_tracker.state.episodes.values()
            if ep.status == EpisodeStatus.COMPLETED
        ])
        return completed_count > 0
    
    def start_batch(self):
        """Start batch processing and begin progress monitoring."""
        self.stats.start_time = datetime.now()
        self.stats.last_update_time = self.stats.start_time
        
        # Start periodic update thread
        self._stop_updates.clear()
        self._update_thread = threading.Thread(target=self._periodic_update_worker, daemon=True)
        self._update_thread.start()
        
        if self.is_resume_session:
            logger.info("Resuming batch processing from previous session")
            logger.info(f"Already completed: {self.stats.completed} episodes")
            logger.info(f"Remaining to process: {self.stats.pending} episodes")
        else:
            logger.info("Starting new batch processing session")
        
        self._display_progress()
    
    def update_current_episode(self, episode_title: str):
        """Update the currently processing episode.
        
        Args:
            episode_title: Title of the episode being processed
        """
        self.current_episode_title = episode_title
        self.current_episode_start_time = datetime.now()
        self._update_stats()
        self._display_progress()
    
    def episode_completed(self, processing_time: float):
        """Mark an episode as completed.
        
        Args:
            processing_time: Time taken to process episode in seconds
        """
        self.stats.processing_times.append(processing_time)
        self.current_episode_title = ""
        self.current_episode_start_time = None
        self._update_stats()
        self._display_progress()
    
    def episode_failed(self, error_msg: str):
        """Mark an episode as failed.
        
        Args:
            error_msg: Error message for the failure
        """
        logger.warning(f"Episode failed: {error_msg}")
        self.current_episode_title = ""
        self.current_episode_start_time = None
        self._update_stats()
        self._display_progress()
    
    def episode_skipped(self, reason: str):
        """Mark an episode as skipped.
        
        Args:
            reason: Reason for skipping the episode
        """
        logger.info(f"Episode skipped: {reason}")
        self.current_episode_title = ""
        self.current_episode_start_time = None
        self._update_stats()
        self._display_progress()
    
    def finish_batch(self, message: Optional[str] = None):
        """Finish batch processing and display final results.
        
        Args:
            message: Optional completion message
        """
        # Stop update thread
        if self._update_thread and self._update_thread.is_alive():
            self._stop_updates.set()
            self._update_thread.join(timeout=1.0)
        
        # Final stats update
        self._update_stats()
        
        # Display final results
        elapsed = self.stats.elapsed_time
        success_rate = self.stats.success_rate
        
        final_message = (
            f"Completed: {self.stats.completed}/{self.stats.total_episodes} episodes "
            f"({success_rate:.1f}% success) in {self._format_time(elapsed)}"
        )
        
        if message:
            final_message = f"{message} - {final_message}"
        
        self.progress_bar.finish(final_message)
        
        # Log detailed summary
        logger.info("Batch processing completed:")
        logger.info(f"  Total episodes: {self.stats.total_episodes}")
        logger.info(f"  Completed: {self.stats.completed}")
        logger.info(f"  Failed: {self.stats.failed}")
        logger.info(f"  Skipped: {self.stats.skipped}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Total time: {self._format_time(elapsed)}")
        if self.stats.processing_times:
            avg_time = self.stats.average_processing_time
            logger.info(f"  Average per episode: {self._format_time(avg_time)}")
    
    def _update_stats(self):
        """Update statistics from progress tracker."""
        # Count episodes by status
        self.stats.completed = len([
            ep for ep in self.progress_tracker.state.episodes.values()
            if ep.status == EpisodeStatus.COMPLETED
        ])
        
        self.stats.failed = len([
            ep for ep in self.progress_tracker.state.episodes.values()
            if ep.status == EpisodeStatus.FAILED
        ])
        
        self.stats.in_progress = len([
            ep for ep in self.progress_tracker.state.episodes.values()
            if ep.status == EpisodeStatus.IN_PROGRESS
        ])
        
        # Update last update time
        self.stats.last_update_time = datetime.now()
    
    def _display_progress(self):
        """Display current progress information."""
        # Throttle display updates to avoid overwhelming the terminal
        current_time = time.time()
        if current_time - self._last_display_update < 1.0:  # Max 1 update per second
            return
        self._last_display_update = current_time
        
        # Calculate progress
        total_processed = self.stats.completed + self.stats.failed + self.stats.skipped
        
        # Build suffix with current episode and ETA
        suffix_parts = []
        
        if self.current_episode_title:
            # Truncate long titles
            title = self.current_episode_title
            if len(title) > 30:
                title = title[:27] + "..."
            suffix_parts.append(f"Current: {title}")
        
        if self.stats.estimated_time_remaining > 0:
            eta_str = self._format_time(self.stats.estimated_time_remaining)
            suffix_parts.append(f"ETA: {eta_str}")
        
        # Add success rate if we have processed episodes
        if total_processed > 0:
            suffix_parts.append(f"Success: {self.stats.success_rate:.0f}%")
        
        suffix = " | ".join(suffix_parts)
        
        # Update progress bar
        self.progress_bar.update(total_processed, suffix)
    
    def _periodic_update_worker(self):
        """Worker thread for periodic progress updates."""
        while not self._stop_updates.wait(30.0):  # Update every 30 seconds
            try:
                self._update_stats()
                self._display_progress()
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human readable string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status summary for external monitoring.
        
        Returns:
            Dictionary with current batch status
        """
        return {
            'total_episodes': self.stats.total_episodes,
            'completed': self.stats.completed,
            'failed': self.stats.failed,
            'skipped': self.stats.skipped,
            'in_progress': self.stats.in_progress,
            'pending': self.stats.pending,
            'success_rate': self.stats.success_rate,
            'elapsed_time': self.stats.elapsed_time,
            'estimated_time_remaining': self.stats.estimated_time_remaining,
            'current_episode': self.current_episode_title,
            'average_processing_time': self.stats.average_processing_time
        }