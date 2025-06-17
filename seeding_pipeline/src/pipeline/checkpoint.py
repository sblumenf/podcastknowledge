"""Checkpoint system for pipeline fault tolerance.

This module provides checkpoint save/resume functionality to enable
the pipeline to recover from failures and resume processing.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import shutil

from src.core.interfaces import TranscriptSegment

logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    """Data structure for pipeline checkpoints."""
    episode_id: str
    last_completed_phase: str
    phase_results: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointData':
        """Create checkpoint from dictionary."""
        return cls(**data)


class CheckpointManager:
    """Manages checkpoint saving and loading for pipeline fault tolerance."""
    
    def __init__(self, checkpoint_dir: Path = Path("checkpoints")):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized CheckpointManager with directory: {checkpoint_dir}")
    
    def get_checkpoint_path(self, episode_id: str) -> Path:
        """Get checkpoint file path for an episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Path to checkpoint file
        """
        # Sanitize episode ID for filesystem
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in episode_id)
        return self.checkpoint_dir / safe_id / "state.json"
    
    def save_checkpoint(self, 
                       episode_id: str,
                       phase: str,
                       phase_results: Dict[str, Any],
                       metadata: Dict[str, Any]) -> bool:
        """Save checkpoint after phase completion.
        
        Args:
            episode_id: Episode identifier
            phase: Last completed phase
            phase_results: Results from all completed phases
            metadata: Episode metadata
            
        Returns:
            True if saved successfully
        """
        try:
            checkpoint_path = self.get_checkpoint_path(episode_id)
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create checkpoint data
            checkpoint = CheckpointData(
                episode_id=episode_id,
                last_completed_phase=phase,
                phase_results=self._serialize_phase_results(phase_results),
                metadata=metadata,
                timestamp=datetime.now().isoformat()
            )
            
            # Write to temporary file first (atomic write)
            temp_path = checkpoint_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            
            # Move to final location
            temp_path.replace(checkpoint_path)
            
            logger.info(f"Saved checkpoint for episode {episode_id} after phase {phase}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def load_checkpoint(self, episode_id: str) -> Optional[CheckpointData]:
        """Load checkpoint for an episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Checkpoint data if exists, None otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(episode_id)
            
            if not checkpoint_path.exists():
                return None
            
            with open(checkpoint_path, 'r') as f:
                data = json.load(f)
            
            checkpoint = CheckpointData.from_dict(data)
            logger.info(f"Loaded checkpoint for episode {episode_id} at phase {checkpoint.last_completed_phase}")
            
            # Deserialize phase results
            checkpoint.phase_results = self._deserialize_phase_results(checkpoint.phase_results)
            
            return checkpoint
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def delete_checkpoint(self, episode_id: str) -> bool:
        """Delete checkpoint after successful completion.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            checkpoint_path = self.get_checkpoint_path(episode_id)
            
            if checkpoint_path.exists():
                # Remove entire episode checkpoint directory
                shutil.rmtree(checkpoint_path.parent)
                logger.info(f"Deleted checkpoint for episode {episode_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all existing checkpoints.
        
        Returns:
            List of checkpoint summaries
        """
        checkpoints = []
        
        try:
            for episode_dir in self.checkpoint_dir.iterdir():
                if episode_dir.is_dir():
                    state_file = episode_dir / "state.json"
                    if state_file.exists():
                        with open(state_file, 'r') as f:
                            data = json.load(f)
                        
                        # Calculate age
                        timestamp = datetime.fromisoformat(data['timestamp'])
                        age = datetime.now() - timestamp
                        
                        checkpoints.append({
                            'episode_id': data['episode_id'],
                            'last_phase': data['last_completed_phase'],
                            'timestamp': data['timestamp'],
                            'age_hours': age.total_seconds() / 3600,
                            'path': str(state_file)
                        })
            
            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
        
        return checkpoints
    
    def _serialize_phase_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize phase results for JSON storage.
        
        Args:
            results: Phase results to serialize
            
        Returns:
            JSON-serializable results
        """
        serialized = {}
        
        for phase, data in results.items():
            if phase == "VTT_PARSING":
                # Serialize transcript segments
                if 'segments' in data:
                    segments = []
                    for seg in data['segments']:
                        if hasattr(seg, '__dict__'):
                            segments.append(seg.__dict__)
                        else:
                            segments.append(seg)
                    data = {**data, 'segments': segments}
            
            serialized[phase] = data
        
        return serialized
    
    def _deserialize_phase_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize phase results from JSON storage.
        
        Args:
            results: Serialized phase results
            
        Returns:
            Deserialized results
        """
        deserialized = {}
        
        for phase, data in results.items():
            if phase == "VTT_PARSING":
                # Deserialize transcript segments
                if 'segments' in data and isinstance(data['segments'], list):
                    segments = []
                    for seg_data in data['segments']:
                        if isinstance(seg_data, dict):
                            # Create TranscriptSegment from dict
                            segment = TranscriptSegment(
                                id=seg_data.get('id'),
                                text=seg_data['text'],
                                start_time=seg_data['start_time'],
                                end_time=seg_data['end_time'],
                                speaker=seg_data.get('speaker'),
                                confidence=seg_data.get('confidence', 1.0)
                            )
                            segments.append(segment)
                        else:
                            segments.append(seg_data)
                    data = {**data, 'segments': segments}
            
            deserialized[phase] = data
        
        return deserialized
    
    def checkpoint_exists(self, episode_id: str) -> bool:
        """Check if checkpoint exists for an episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if checkpoint exists
        """
        return self.get_checkpoint_path(episode_id).exists()
    
    def get_checkpoint_age(self, episode_id: str) -> Optional[float]:
        """Get age of checkpoint in hours.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Age in hours if checkpoint exists, None otherwise
        """
        checkpoint = self.load_checkpoint(episode_id)
        if checkpoint:
            timestamp = datetime.fromisoformat(checkpoint.timestamp)
            age = datetime.now() - timestamp
            return age.total_seconds() / 3600
        return None