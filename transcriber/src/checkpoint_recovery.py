"""Checkpoint and Recovery System for Podcast Transcription Pipeline.

This module implements checkpoint and resume functionality to handle
interruptions and recover from partial processing.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import shutil

from src.utils.logging import get_logger

logger = get_logger('checkpoint_recovery')


@dataclass
class EpisodeCheckpoint:
    """Represents a checkpoint for an episode's processing state."""
    episode_id: str
    audio_url: str
    title: str
    status: str  # 'transcribing', 'identifying_speakers', 'generating_vtt', 'completed'
    stage_completed: List[str]  # List of completed stages
    temporary_files: Dict[str, str]  # Map of stage to temp file path
    start_time: datetime
    last_update: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['last_update'] = self.last_update.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpisodeCheckpoint':
        """Create from dictionary."""
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        data['last_update'] = datetime.fromisoformat(data['last_update'])
        return cls(**data)


class CheckpointManager:
    """Manages checkpoints for crash recovery."""
    
    def __init__(self, data_dir: Path = Path("data")):
        """Initialize checkpoint manager.
        
        Args:
            data_dir: Directory for storing checkpoint data
        """
        self.data_dir = data_dir
        self.checkpoint_dir = data_dir / "checkpoints"
        self.checkpoint_file = self.checkpoint_dir / "active_checkpoint.json"
        self.temp_dir = self.checkpoint_dir / "temp"
        self.completed_dir = self.checkpoint_dir / "completed"
        
        # Create directories
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        self.completed_dir.mkdir(exist_ok=True)
        
        # Load existing checkpoint
        self.current_checkpoint: Optional[EpisodeCheckpoint] = None
        self._load_checkpoint()
    
    def _load_checkpoint(self):
        """Load existing checkpoint if present."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    self.current_checkpoint = EpisodeCheckpoint.from_dict(data)
                    logger.info(f"Loaded checkpoint for episode: {self.current_checkpoint.title}")
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
                # Archive corrupted checkpoint
                backup_path = self.checkpoint_dir / f"corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                shutil.move(str(self.checkpoint_file), str(backup_path))
                self.current_checkpoint = None
    
    def _save_checkpoint(self):
        """Save current checkpoint atomically."""
        if not self.current_checkpoint:
            return
        
        try:
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                dir=self.checkpoint_dir,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(self.current_checkpoint.to_dict(), tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())  # Force write to disk
                temp_path = tmp_file.name
            
            # Atomically replace the checkpoint file
            os.replace(temp_path, self.checkpoint_file)
            logger.debug("Checkpoint saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            # Clean up temp file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def start_episode(self, episode_id: str, audio_url: str, 
                     title: str, metadata: Dict[str, Any]) -> EpisodeCheckpoint:
        """Start processing a new episode.
        
        Args:
            episode_id: Unique episode identifier
            audio_url: URL of the audio file
            title: Episode title
            metadata: Episode metadata
            
        Returns:
            New checkpoint instance
        """
        # Check for existing checkpoint
        if self.current_checkpoint:
            error_msg = "New episode started before previous completed"
            self.mark_failed(error_msg)
            raise RuntimeError(f"Cannot start new episode: {error_msg}")
        
        # Create new checkpoint
        self.current_checkpoint = EpisodeCheckpoint(
            episode_id=episode_id,
            audio_url=audio_url,
            title=title,
            status='transcribing',
            stage_completed=[],
            temporary_files={},
            start_time=datetime.now(),
            last_update=datetime.now(),
            metadata=metadata
        )
        
        self._save_checkpoint()
        logger.info(f"Started checkpoint for episode: {title}")
        return self.current_checkpoint
    
    def update_stage(self, stage: str, temp_file_path: Optional[str] = None):
        """Update processing stage.
        
        Args:
            stage: Current processing stage
            temp_file_path: Path to temporary file for this stage
        """
        if not self.current_checkpoint:
            logger.warning("No active checkpoint to update")
            return
        
        self.current_checkpoint.status = stage
        self.current_checkpoint.last_update = datetime.now()
        
        if temp_file_path:
            self.current_checkpoint.temporary_files[stage] = temp_file_path
        
        self._save_checkpoint()
        logger.info(f"Updated checkpoint: stage={stage}")
    
    def complete_stage(self, stage: str):
        """Mark a stage as completed.
        
        Args:
            stage: Stage that was completed
        """
        if not self.current_checkpoint:
            return
        
        if stage not in self.current_checkpoint.stage_completed:
            self.current_checkpoint.stage_completed.append(stage)
            self.current_checkpoint.last_update = datetime.now()
            self._save_checkpoint()
            logger.info(f"Completed stage: {stage}")
    
    def save_temp_data(self, stage: str, data: str) -> str:
        """Save temporary data for a stage.
        
        Args:
            stage: Processing stage
            data: Data to save
            
        Returns:
            Path to temporary file
        """
        if not self.current_checkpoint:
            raise ValueError("No active checkpoint")
        
        # Create temp file
        temp_file = self.temp_dir / f"{self.current_checkpoint.episode_id}_{stage}.tmp"
        
        # Write data atomically
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            dir=self.temp_dir,
            suffix='.tmp'
        ) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            temp_path = f.name
        
        # Move to final location
        os.replace(temp_path, temp_file)
        
        # Update checkpoint
        self.current_checkpoint.temporary_files[stage] = str(temp_file)
        self._save_checkpoint()
        
        return str(temp_file)
    
    def load_temp_data(self, stage: str) -> Optional[str]:
        """Load temporary data for a stage.
        
        Args:
            stage: Processing stage
            
        Returns:
            Data from temporary file or None
        """
        if not self.current_checkpoint:
            return None
        
        temp_file_path = self.current_checkpoint.temporary_files.get(stage)
        if not temp_file_path or not os.path.exists(temp_file_path):
            return None
        
        try:
            with open(temp_file_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load temp data for {stage}: {e}")
            return None
    
    def mark_completed(self, final_output_path: str):
        """Mark episode as completed.
        
        Args:
            final_output_path: Path to final VTT file
        """
        if not self.current_checkpoint:
            return
        
        # Archive checkpoint
        completed_file = self.completed_dir / f"{self.current_checkpoint.episode_id}.json"
        self.current_checkpoint.status = 'completed'
        self.current_checkpoint.last_update = datetime.now()
        
        # Save to completed directory
        episode_title = self.current_checkpoint.title
        with open(completed_file, 'w') as f:
            data = self.current_checkpoint.to_dict()
            data['final_output'] = final_output_path
            json.dump(data, f, indent=2)
        
        # Clean up temporary files
        self._cleanup_temp_files()
        
        # Remove active checkpoint
        if self.checkpoint_file.exists():
            os.unlink(self.checkpoint_file)
        
        logger.info(f"Episode completed: {episode_title}")
        # Note: current_checkpoint is already set to None by _cleanup_temp_files()
    
    def mark_failed(self, error: str):
        """Mark episode as failed.
        
        Args:
            error: Error message
        """
        if not self.current_checkpoint:
            return
        
        # Archive failed checkpoint
        failed_file = self.completed_dir / f"{self.current_checkpoint.episode_id}_failed.json"
        self.current_checkpoint.status = 'failed'
        self.current_checkpoint.last_update = datetime.now()
        
        # Save to completed directory with error
        with open(failed_file, 'w') as f:
            data = self.current_checkpoint.to_dict()
            data['error'] = error
            json.dump(data, f, indent=2)
        
        # Don't clean up temporary files on failure - preserve for debugging
        # They should be cleaned up manually or by mark_complete
        
        # Remove active checkpoint
        if self.checkpoint_file.exists():
            os.unlink(self.checkpoint_file)
        
        logger.error(f"Episode failed: {self.current_checkpoint.title} - {error}")
        # Don't clear current_checkpoint yet - needed for manual cleanup
        # self.current_checkpoint = None
    
    def _cleanup_temp_files(self):
        """Clean up temporary files for current checkpoint."""
        if not self.current_checkpoint:
            return
        
        for temp_file in self.current_checkpoint.temporary_files.values():
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {temp_file}: {e}")
        
        # Clear current checkpoint after cleanup
        self.current_checkpoint = None
    
    def can_resume(self) -> bool:
        """Check if there's a checkpoint to resume from.
        
        Returns:
            True if resumable checkpoint exists
        """
        return self.current_checkpoint is not None
    
    def get_resume_info(self) -> Optional[Dict[str, Any]]:
        """Get information about resumable checkpoint.
        
        Returns:
            Resume information or None
        """
        if not self.current_checkpoint:
            return None
        
        # Calculate time since last update
        time_since = datetime.now() - self.current_checkpoint.last_update
        hours_since = time_since.total_seconds() / 3600
        
        return {
            'episode_title': self.current_checkpoint.title,
            'current_stage': self.current_checkpoint.status,
            'completed_stages': self.current_checkpoint.stage_completed,
            'hours_since_update': round(hours_since, 1),
            'can_resume': hours_since < 24,  # Don't resume if too old
            'temp_files_available': list(self.current_checkpoint.temporary_files.keys()),
            'metadata': self.current_checkpoint.metadata
        }
    
    def resume_processing(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Resume processing from checkpoint.
        
        Returns:
            Tuple of (resume_stage, checkpoint_data) or None
        """
        if not self.can_resume():
            return None
        
        info = self.get_resume_info()
        if not info['can_resume']:
            logger.warning("Checkpoint too old, starting fresh")
            self.mark_failed("Checkpoint expired")
            return None
        
        # Determine where to resume
        completed = set(self.current_checkpoint.stage_completed)
        
        if 'transcription' not in completed:
            resume_stage = 'transcription'
        elif 'speaker_identification' not in completed:
            resume_stage = 'speaker_identification'
        elif 'vtt_generation' not in completed:
            resume_stage = 'vtt_generation'
        else:
            # All stages completed, just need to finalize
            resume_stage = 'finalization'
        
        checkpoint_data = {
            'checkpoint': self.current_checkpoint,
            'temp_data': {}
        }
        
        # Load available temporary data
        for stage, file_path in self.current_checkpoint.temporary_files.items():
            data = self.load_temp_data(stage)
            if data:
                checkpoint_data['temp_data'][stage] = data
        
        logger.info(f"Resuming from stage: {resume_stage}")
        return resume_stage, checkpoint_data
    
    def cleanup_old_checkpoints(self, days: int = 7):
        """Clean up old completed checkpoints.
        
        Args:
            days: Keep checkpoints newer than this many days
        """
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)
        
        for file_path in self.completed_dir.glob("*.json"):
            try:
                if file_path.stat().st_mtime < cutoff_date:
                    os.unlink(file_path)
                    logger.info(f"Cleaned up old checkpoint: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get checkpoint statistics.
        
        Returns:
            Statistics about checkpoints
        """
        completed_count = len(list(self.completed_dir.glob("*[!_failed].json")))
        failed_count = len(list(self.completed_dir.glob("*_failed.json")))
        
        return {
            'active_checkpoint': self.current_checkpoint is not None,
            'completed_episodes': completed_count,
            'failed_episodes': failed_count,
            'temp_files': len(list(self.temp_dir.glob("*.tmp"))),
            'checkpoint_dir_size_mb': sum(
                f.stat().st_size for f in self.checkpoint_dir.rglob("*") if f.is_file()
            ) / 1024 / 1024
        }