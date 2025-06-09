"""Integration between API key rotation and checkpoint system.

This module ensures coordination between the rotation state and 
the checkpoint system for consistent recovery.
"""

from typing import Dict, Any, Optional
import logging
from pathlib import Path

from src.seeding.components.checkpoint_manager import CheckpointManager
from src.utils.key_rotation_manager import KeyRotationManager
from src.utils.rotation_state_manager import RotationStateManager

logger = logging.getLogger(__name__)


class RotationCheckpointIntegration:
    """Manages integration between rotation state and checkpoints."""
    
    def __init__(self, checkpoint_manager: CheckpointManager, 
                 key_rotation_manager: Optional[KeyRotationManager] = None):
        """Initialize the integration.
        
        Args:
            checkpoint_manager: The checkpoint manager instance
            key_rotation_manager: Optional rotation manager instance
        """
        self.checkpoint_manager = checkpoint_manager
        self.key_rotation_manager = key_rotation_manager
        
    def save_rotation_state_with_checkpoint(self, episode_id: str, stage: str) -> bool:
        """Save rotation state alongside checkpoint data.
        
        Args:
            episode_id: Episode being processed
            stage: Processing stage
            
        Returns:
            True if saved successfully
        """
        if not self.key_rotation_manager:
            return True  # No rotation manager, nothing to save
            
        try:
            # Get current rotation state
            rotation_state = self.key_rotation_manager.get_status_summary()
            
            # Save as part of checkpoint metadata
            metadata = {
                'rotation_state': rotation_state,
                'state_directory': str(RotationStateManager.get_state_directory()),
                'rotation_metrics': RotationStateManager.get_rotation_metrics()
            }
            
            # Save to checkpoint
            return self.checkpoint_manager.save_progress(
                episode_id,
                f"{stage}_rotation_state",
                metadata
            )
            
        except Exception as e:
            logger.warning(f"Failed to save rotation state with checkpoint: {e}")
            return False
    
    def restore_rotation_state_from_checkpoint(self, episode_id: str, stage: str) -> bool:
        """Restore rotation state from checkpoint if needed.
        
        Args:
            episode_id: Episode being processed
            stage: Processing stage
            
        Returns:
            True if restored successfully or not needed
        """
        if not self.key_rotation_manager:
            return True  # No rotation manager, nothing to restore
            
        try:
            # Load rotation state from checkpoint
            metadata = self.checkpoint_manager.load_progress(
                episode_id,
                f"{stage}_rotation_state"
            )
            
            if not metadata:
                return True  # No saved state, use current
                
            # Log the restoration
            rotation_state = metadata.get('rotation_state', {})
            logger.info(
                f"Found rotation state from checkpoint: "
                f"{rotation_state.get('total_keys', 0)} keys, "
                f"{rotation_state.get('available_keys', 0)} available"
            )
            
            # The KeyRotationManager handles its own state persistence,
            # so we just log the information for debugging
            return True
            
        except Exception as e:
            logger.warning(f"Failed to restore rotation state from checkpoint: {e}")
            return False
    
    def get_rotation_checkpoint_summary(self) -> Dict[str, Any]:
        """Get summary of rotation state for checkpointing.
        
        Returns:
            Summary dictionary
        """
        summary = {
            'rotation_enabled': self.key_rotation_manager is not None,
            'state_directory': str(RotationStateManager.get_state_directory()),
            'metrics': RotationStateManager.get_rotation_metrics()
        }
        
        if self.key_rotation_manager:
            summary['rotation_status'] = self.key_rotation_manager.get_status_summary()
            
        return summary
    
    @staticmethod
    def ensure_consistent_state_directory(checkpoint_dir: Optional[str] = None) -> Path:
        """Ensure rotation state directory is consistent with checkpoint directory.
        
        Args:
            checkpoint_dir: Optional checkpoint directory path
            
        Returns:
            Path to state directory
        """
        if checkpoint_dir:
            # Create rotation state subdirectory in checkpoint directory
            rotation_dir = Path(checkpoint_dir) / 'rotation_state'
            rotation_dir.mkdir(exist_ok=True, parents=True)
            logger.info(f"Using rotation state directory: {rotation_dir}")
            return rotation_dir
        else:
            # Use default from RotationStateManager
            return RotationStateManager.get_state_directory()