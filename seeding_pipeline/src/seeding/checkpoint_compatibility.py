"""
Checkpoint compatibility layer for handling different checkpoint versions.

This module provides functionality to detect checkpoint versions and migrate
old checkpoint formats to the current format.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from ..core.exceptions import CheckpointError


logger = logging.getLogger(__name__)


class CheckpointVersion:
    """Checkpoint version constants."""
    V1 = "1.0"  # Original format
    V2 = "2.0"  # Added extraction_mode
    V3 = "3.0"  # Added schema_discovery
    CURRENT = V3


class CheckpointMigrator:
    """
    Handles migration of checkpoint files between versions.
    
    Ensures backward compatibility when checkpoint format changes.
    """
    
    def __init__(self, checkpoint_dir: Path):
        """
        Initialize the migrator.
        
        Args:
            checkpoint_dir: Directory containing checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        
    def detect_version(self, checkpoint_data: Dict[str, Any]) -> str:
        """
        Detect the version of a checkpoint file.
        
        Args:
            checkpoint_data: Loaded checkpoint data
            
        Returns:
            Version string
        """
        # Explicit version field (v3+)
        if "version" in checkpoint_data:
            return checkpoint_data["version"]
            
        # Check for v2 fields
        if "extraction_mode" in checkpoint_data:
            return CheckpointVersion.V2
            
        # Default to v1
        return CheckpointVersion.V1
    
    def migrate_checkpoint(self, checkpoint_path: Path) -> bool:
        """
        Migrate a checkpoint file to the current version.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            True if migration was needed and successful
        """
        try:
            # Load checkpoint
            with open(checkpoint_path, 'r') as f:
                data = json.load(f)
                
            # Detect version
            current_version = self.detect_version(data)
            
            if current_version == CheckpointVersion.CURRENT:
                logger.debug(f"Checkpoint {checkpoint_path} is already current version")
                return False
                
            # Create backup
            backup_path = checkpoint_path.with_suffix('.bak')
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Created backup: {backup_path}")
            
            # Migrate based on version
            if current_version == CheckpointVersion.V1:
                data = self._migrate_v1_to_v2(data)
                current_version = CheckpointVersion.V2
                
            if current_version == CheckpointVersion.V2:
                data = self._migrate_v2_to_v3(data)
                current_version = CheckpointVersion.V3
                
            # Save migrated checkpoint
            with open(checkpoint_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Successfully migrated checkpoint to version {CheckpointVersion.CURRENT}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating checkpoint {checkpoint_path}: {e}")
            raise CheckpointError(f"Failed to migrate checkpoint: {e}")
    
    def _migrate_v1_to_v2(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from v1 to v2 format."""
        logger.info("Migrating checkpoint from v1 to v2")
        
        # Add extraction_mode field
        data["extraction_mode"] = "fixed"  # Default to fixed for old checkpoints
        
        # Add podcast_name if missing
        if "podcast_name" not in data:
            data["podcast_name"] = data.get("podcast_url", "Unknown Podcast").split('/')[-1]
            
        # Add timestamps if missing
        if "start_time" not in data:
            data["start_time"] = datetime.now().isoformat()
        if "last_update" not in data:
            data["last_update"] = datetime.now().isoformat()
            
        return data
    
    def _migrate_v2_to_v3(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from v2 to v3 format."""
        logger.info("Migrating checkpoint from v2 to v3")
        
        # Add version field
        data["version"] = CheckpointVersion.V3
        
        # Add schema_discovery section
        if "schema_discovery" not in data:
            data["schema_discovery"] = {
                "discovered_types": [],
                "evolution": []
            }
            
        # Add total_episodes if missing
        if "total_episodes" not in data:
            data["total_episodes"] = len(data.get("processed_episodes", []))
            
        return data
    
    def migrate_all_checkpoints(self) -> Dict[str, bool]:
        """
        Migrate all checkpoints in the directory.
        
        Returns:
            Dictionary mapping checkpoint files to migration status
        """
        results = {}
        
        if not self.checkpoint_dir.exists():
            logger.warning(f"Checkpoint directory does not exist: {self.checkpoint_dir}")
            return results
            
        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                migrated = self.migrate_checkpoint(checkpoint_file)
                results[str(checkpoint_file)] = migrated
            except Exception as e:
                logger.error(f"Failed to migrate {checkpoint_file}: {e}")
                results[str(checkpoint_file)] = False
                
        return results
    
    def validate_checkpoint(self, checkpoint_data: Dict[str, Any]) -> bool:
        """
        Validate that a checkpoint has all required fields.
        
        Args:
            checkpoint_data: Checkpoint data to validate
            
        Returns:
            True if valid
        """
        required_fields = [
            "podcast_url",
            "podcast_name",
            "processed_episodes",
            "extraction_mode",
            "version"
        ]
        
        for field in required_fields:
            if field not in checkpoint_data:
                logger.error(f"Checkpoint missing required field: {field}")
                return False
                
        return True


class CheckpointCompatibilityLayer:
    """
    Provides a compatibility layer for checkpoint operations.
    
    Ensures that checkpoint operations work across different versions.
    """
    
    def __init__(self, checkpoint_dir: Path):
        """
        Initialize the compatibility layer.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.migrator = CheckpointMigrator(checkpoint_dir)
        
    def load_checkpoint(self, podcast_url: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint with automatic migration if needed.
        
        Args:
            podcast_url: URL of the podcast
            
        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_file = self._get_checkpoint_path(podcast_url)
        
        if not checkpoint_file.exists():
            return None
            
        try:
            # Attempt migration if needed
            self.migrator.migrate_checkpoint(checkpoint_file)
            
            # Load checkpoint
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
                
            # Validate
            if not self.migrator.validate_checkpoint(data):
                logger.error(f"Invalid checkpoint: {checkpoint_file}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def save_checkpoint(self, podcast_url: str, checkpoint_data: Dict[str, Any]) -> bool:
        """
        Save a checkpoint in the current format.
        
        Args:
            podcast_url: URL of the podcast
            checkpoint_data: Data to save
            
        Returns:
            True if successful
        """
        checkpoint_file = self._get_checkpoint_path(podcast_url)
        
        # Ensure current version
        checkpoint_data["version"] = CheckpointVersion.CURRENT
        checkpoint_data["last_update"] = datetime.now().isoformat()
        
        try:
            # Create directory if needed
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Save checkpoint
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return False
    
    def _get_checkpoint_path(self, podcast_url: str) -> Path:
        """Get the checkpoint file path for a podcast URL."""
        # Sanitize URL for filename
        safe_name = podcast_url.replace('/', '_').replace(':', '_')
        return self.checkpoint_dir / f"checkpoint_{safe_name}.json"