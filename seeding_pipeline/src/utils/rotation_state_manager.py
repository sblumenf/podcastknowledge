"""State management utilities for API key rotation.

This module provides utilities to ensure proper state persistence
and coordination between the key rotation system and the checkpoint system.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from src.core.env_config import env_config

logger = logging.getLogger(__name__)


class RotationStateManager:
    """Manages state persistence for API key rotation."""
    
    @staticmethod
    def get_state_directory() -> Path:
        """Get the directory for rotation state files.
        
        Returns:
            Path to state directory
        """
        # Priority order:
        # 1. STATE_DIR environment variable
        # 2. CHECKPOINT_DIR environment variable (for co-location)
        # 3. Default 'data' directory
        
        state_dir = env_config.get_optional('STATE_DIR')
        if state_dir:
            return Path(state_dir)
            
        checkpoint_dir = env_config.get_optional('CHECKPOINT_DIR')
        if checkpoint_dir:
            # Create a subdirectory for rotation state
            rotation_dir = Path(checkpoint_dir) / 'rotation_state'
            rotation_dir.mkdir(exist_ok=True, parents=True)
            return rotation_dir
            
        # Default to data directory
        default_dir = Path('data')
        default_dir.mkdir(exist_ok=True)
        return default_dir
    
    @staticmethod
    def ensure_state_persistence() -> bool:
        """Ensure state persistence is properly configured.
        
        Returns:
            True if state persistence is ready
        """
        try:
            state_dir = RotationStateManager.get_state_directory()
            
            # Ensure directory exists and is writable
            state_dir.mkdir(exist_ok=True, parents=True)
            
            # Test write access
            test_file = state_dir / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            
            logger.info(f"API key rotation state directory configured: {state_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure state persistence: {e}")
            return False
    
    @staticmethod
    def get_rotation_metrics() -> Dict[str, Any]:
        """Get metrics about the rotation state.
        
        Returns:
            Dictionary with rotation metrics
        """
        state_dir = RotationStateManager.get_state_directory()
        state_file = state_dir / '.key_rotation_state.json'
        
        metrics = {
            'state_directory': str(state_dir),
            'state_file_exists': state_file.exists(),
            'state_file_size': state_file.stat().st_size if state_file.exists() else 0,
            'directory_writable': os.access(state_dir, os.W_OK)
        }
        
        return metrics
    
    @staticmethod
    def cleanup_old_states(days: int = 30) -> int:
        """Clean up old rotation state files.
        
        Args:
            days: Remove state files older than this many days
            
        Returns:
            Number of files cleaned up
        """
        import time
        from datetime import datetime, timedelta
        
        state_dir = RotationStateManager.get_state_directory()
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        cleaned = 0
        for file_path in state_dir.glob('.key_rotation_state.*.backup'):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to clean up old state file {file_path}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old rotation state files")
            
        return cleaned