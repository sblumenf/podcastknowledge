"""Checkpoint management component for the pipeline."""

from typing import Any, Dict, List, Optional
import logging

from src.core.config import PipelineConfig
from src.seeding.checkpoint import ProgressCheckpoint
logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint operations for the pipeline."""
    
    def __init__(self, config: PipelineConfig):
        """Initialize checkpoint manager.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config
        
        # Initialize checkpoint with configuration
        checkpoint_dir = getattr(config, 'checkpoint_dir', 'checkpoints')
        extraction_mode = 'schemaless' if getattr(config, 'use_schemaless_extraction', False) else 'fixed'
        
        self.checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            enable_compression=getattr(config, 'enable_checkpoint_compression', True),
            max_checkpoint_age_days=getattr(config, 'max_checkpoint_age_days', 30),
            enable_distributed=getattr(config, 'enable_distributed_checkpoints', False),
            extraction_mode=extraction_mode,
            config=config.__dict__ if hasattr(config, '__dict__') else {}
        )
        
        logger.info(f"Initialized checkpoint manager (mode: {extraction_mode})")
    
    def is_completed(self, episode_id: str) -> bool:
        """Check if an episode has been completed.
        
        Args:
            episode_id: Episode ID to check
            
        Returns:
            True if episode is completed
        """
        completed_episodes = self.checkpoint.get_completed_episodes()
        return episode_id in completed_episodes
    
    def mark_completed(self, episode_id: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """Mark an episode as completed.
        
        Args:
            episode_id: Episode ID to mark as complete
            data: Optional completion data to save
            
        Returns:
            True if successfully marked
        """
        completion_data = data or {'status': 'complete'}
        return self.checkpoint.save_episode_progress(episode_id, 'complete', completion_data)
    
    def save_progress(self, episode_id: str, stage: str, data: Any, 
                     segment_index: Optional[int] = None) -> bool:
        """Save progress for an episode at a specific stage.
        
        Args:
            episode_id: Episode ID
            stage: Processing stage name
            data: Data to checkpoint
            segment_index: Optional segment index for segment-level checkpoints
            
        Returns:
            True if save successful
        """
        return self.checkpoint.save_episode_progress(episode_id, stage, data, segment_index)
    
    def load_progress(self, episode_id: str, stage: str, 
                     segment_index: Optional[int] = None) -> Optional[Any]:
        """Load progress for an episode at a specific stage.
        
        Args:
            episode_id: Episode ID
            stage: Processing stage name
            segment_index: Optional segment index for segment-level checkpoints
            
        Returns:
            Checkpoint data or None if not found
        """
        return self.checkpoint.load_episode_progress(episode_id, stage, segment_index)
    
    def get_schema_stats(self) -> Dict[str, Any]:
        """Get schema discovery statistics for schemaless mode.
        
        Returns:
            Schema statistics including discovered types
        """
        return self.checkpoint.get_schema_statistics()
    
    def get_incomplete_episodes(self) -> List[Dict[str, Any]]:
        """Find episodes that have checkpoints but are not complete.
        
        Returns:
            List of incomplete episode information
        """
        return self.checkpoint.get_incomplete_episodes()
    
    def save_schema_evolution(self, episode_id: str, discovered_types: List[str]):
        """Save schema evolution information for schemaless mode.
        
        Args:
            episode_id: Episode where types were discovered
            discovered_types: List of newly discovered entity types
        """
        self.checkpoint.save_schema_evolution(episode_id, discovered_types)
    
    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """Get overall checkpoint statistics.
        
        Returns:
            Dictionary with checkpoint statistics
        """
        return self.checkpoint.get_checkpoint_statistics()
    
    def cleanup_old_checkpoints(self, days: Optional[int] = None) -> int:
        """Remove checkpoints older than specified days.
        
        Args:
            days: Number of days to keep checkpoints
            
        Returns:
            Number of checkpoints removed
        """
        return self.checkpoint.clean_old_checkpoints(days)
    
    def cleanup_episode(self, episode_id: str):
        """Remove all checkpoints for a specific episode.
        
        Args:
            episode_id: Episode ID to clean up
        """
        self.checkpoint.clean_episode_checkpoints(episode_id)