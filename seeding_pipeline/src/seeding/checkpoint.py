"""Enhanced checkpoint management for resumable podcast processing."""

import os
import pickle
import gzip
import json
import shutil
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import hashlib

from src.utils.resources import ProgressCheckpoint as BaseProgressCheckpoint

logger = logging.getLogger(__name__)


class CheckpointVersion(Enum):
    """Checkpoint format versions."""
    V1 = "1.0"  # Original format
    V2 = "2.0"  # Added compression and metadata
    V3 = "3.0"  # Added segment-level checkpoints


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    version: str
    created_at: str
    updated_at: str
    episode_id: str
    stage: str
    compressed: bool = False
    size_bytes: int = 0
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'episode_id': self.episode_id,
            'stage': self.stage,
            'compressed': self.compressed,
            'size_bytes': self.size_bytes,
            'checksum': self.checksum
        }


class ProgressCheckpoint(BaseProgressCheckpoint):
    """Enhanced checkpoint system for resumable processing with advanced features."""
    
    def __init__(self, 
                 checkpoint_dir: Optional[str] = None,
                 version: CheckpointVersion = CheckpointVersion.V3,
                 enable_compression: bool = True,
                 max_checkpoint_age_days: int = 30,
                 enable_distributed: bool = False):
        """Initialize enhanced checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for storing checkpoints
            version: Checkpoint format version
            enable_compression: Whether to compress checkpoints
            max_checkpoint_age_days: Maximum age for checkpoints before cleanup
            enable_distributed: Enable distributed checkpoint support
        """
        super().__init__(checkpoint_dir)
        self.version = version
        self.enable_compression = enable_compression
        self.max_checkpoint_age_days = max_checkpoint_age_days
        self.enable_distributed = enable_distributed
        
        # Thread safety for distributed mode
        self._lock = Lock() if enable_distributed else None
        
        # Create subdirectories for organization
        self.episodes_dir = os.path.join(self.checkpoint_dir, 'episodes')
        self.segments_dir = os.path.join(self.checkpoint_dir, 'segments')
        self.metadata_dir = os.path.join(self.checkpoint_dir, 'metadata')
        
        for dir_path in [self.episodes_dir, self.segments_dir, self.metadata_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        logger.info(f"Initialized enhanced checkpoint manager at: {self.checkpoint_dir}")
    
    def save_episode_progress(self, 
                            episode_id: str, 
                            stage: str, 
                            data: Any,
                            segment_index: Optional[int] = None) -> bool:
        """Save progress checkpoint for an episode with versioning and compression.
        
        Args:
            episode_id: Unique episode identifier
            stage: Processing stage name
            data: Data to checkpoint
            segment_index: Optional segment index for segment-level checkpoints
            
        Returns:
            True if save successful
        """
        if self._lock:
            with self._lock:
                return self._save_checkpoint(episode_id, stage, data, segment_index)
        else:
            return self._save_checkpoint(episode_id, stage, data, segment_index)
    
    def _save_checkpoint(self, 
                        episode_id: str, 
                        stage: str, 
                        data: Any,
                        segment_index: Optional[int]) -> bool:
        """Internal method to save checkpoint."""
        try:
            # Determine checkpoint path
            if segment_index is not None:
                checkpoint_file = os.path.join(
                    self.segments_dir,
                    f"{episode_id}_segment_{segment_index}_{stage}.ckpt"
                )
            else:
                checkpoint_file = os.path.join(
                    self.episodes_dir,
                    f"{episode_id}_{stage}.ckpt"
                )
            
            # Create checkpoint data with version
            checkpoint_data = {
                'version': self.version.value,
                'episode_id': episode_id,
                'stage': stage,
                'timestamp': datetime.now().isoformat(),
                'data': data,
                'segment_index': segment_index
            }
            
            # Serialize data
            serialized_data = pickle.dumps(checkpoint_data)
            
            # Calculate checksum
            checksum = hashlib.sha256(serialized_data).hexdigest()
            
            # Compress if enabled
            if self.enable_compression:
                serialized_data = gzip.compress(serialized_data)
                checkpoint_file += '.gz'
            
            # Write checkpoint
            with open(checkpoint_file, 'wb') as f:
                f.write(serialized_data)
            
            # Save metadata
            metadata = CheckpointMetadata(
                version=self.version.value,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                episode_id=episode_id,
                stage=stage,
                compressed=self.enable_compression,
                size_bytes=len(serialized_data),
                checksum=checksum
            )
            
            self._save_metadata(episode_id, stage, metadata, segment_index)
            
            logger.debug(f"Saved checkpoint: {stage} for episode {episode_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def _save_metadata(self, 
                      episode_id: str, 
                      stage: str, 
                      metadata: CheckpointMetadata,
                      segment_index: Optional[int] = None):
        """Save checkpoint metadata."""
        if segment_index is not None:
            metadata_file = os.path.join(
                self.metadata_dir,
                f"{episode_id}_segment_{segment_index}_{stage}.json"
            )
        else:
            metadata_file = os.path.join(
                self.metadata_dir,
                f"{episode_id}_{stage}.json"
            )
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
    
    def load_episode_progress(self, 
                            episode_id: str, 
                            stage: str,
                            segment_index: Optional[int] = None) -> Optional[Any]:
        """Load progress checkpoint for an episode with version handling.
        
        Args:
            episode_id: Unique episode identifier
            stage: Processing stage name
            segment_index: Optional segment index for segment-level checkpoints
            
        Returns:
            Checkpoint data or None if not found
        """
        if self._lock:
            with self._lock:
                return self._load_checkpoint(episode_id, stage, segment_index)
        else:
            return self._load_checkpoint(episode_id, stage, segment_index)
    
    def _load_checkpoint(self, 
                        episode_id: str, 
                        stage: str,
                        segment_index: Optional[int]) -> Optional[Any]:
        """Internal method to load checkpoint."""
        try:
            # Determine checkpoint path
            if segment_index is not None:
                checkpoint_file = os.path.join(
                    self.segments_dir,
                    f"{episode_id}_segment_{segment_index}_{stage}.ckpt"
                )
            else:
                checkpoint_file = os.path.join(
                    self.episodes_dir,
                    f"{episode_id}_{stage}.ckpt"
                )
            
            # Check for compressed version
            if not os.path.exists(checkpoint_file) and os.path.exists(checkpoint_file + '.gz'):
                checkpoint_file += '.gz'
                compressed = True
            else:
                compressed = False
            
            if not os.path.exists(checkpoint_file):
                return None
            
            # Read checkpoint
            with open(checkpoint_file, 'rb') as f:
                data = f.read()
            
            # Decompress if needed
            if compressed:
                data = gzip.decompress(data)
            
            # Deserialize
            checkpoint_data = pickle.loads(data)
            
            # Handle version compatibility
            checkpoint_version = checkpoint_data.get('version', CheckpointVersion.V1.value)
            if checkpoint_version != self.version.value:
                logger.warning(f"Loading checkpoint with different version: {checkpoint_version}")
                checkpoint_data = self._migrate_checkpoint(checkpoint_data, checkpoint_version)
            
            logger.debug(f"Loaded checkpoint: {stage} for episode {episode_id}")
            return checkpoint_data['data']
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def _migrate_checkpoint(self, checkpoint_data: Dict[str, Any], old_version: str) -> Dict[str, Any]:
        """Migrate checkpoint data from old version to current version.
        
        Args:
            checkpoint_data: Old checkpoint data
            old_version: Version of the checkpoint
            
        Returns:
            Migrated checkpoint data
        """
        # Implement version-specific migrations
        if old_version == CheckpointVersion.V1.value:
            # V1 to V2 migration
            checkpoint_data['segment_index'] = None
        
        if old_version in [CheckpointVersion.V1.value, CheckpointVersion.V2.value]:
            # V1/V2 to V3 migration
            # Add any necessary fields
            pass
        
        checkpoint_data['version'] = self.version.value
        return checkpoint_data
    
    def get_episode_checkpoints(self, episode_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for an episode.
        
        Args:
            episode_id: Episode ID
            
        Returns:
            List of checkpoint information
        """
        checkpoints = []
        
        # Check episode-level checkpoints
        for filename in os.listdir(self.episodes_dir):
            if filename.startswith(f"{episode_id}_"):
                stage = filename.split('_')[-1].replace('.ckpt', '').replace('.gz', '')
                checkpoints.append({
                    'episode_id': episode_id,
                    'stage': stage,
                    'type': 'episode',
                    'path': os.path.join(self.episodes_dir, filename)
                })
        
        # Check segment-level checkpoints
        for filename in os.listdir(self.segments_dir):
            if filename.startswith(f"{episode_id}_segment_"):
                parts = filename.split('_')
                segment_index = int(parts[2])
                stage = parts[-1].replace('.ckpt', '').replace('.gz', '')
                checkpoints.append({
                    'episode_id': episode_id,
                    'stage': stage,
                    'segment_index': segment_index,
                    'type': 'segment',
                    'path': os.path.join(self.segments_dir, filename)
                })
        
        return checkpoints
    
    def get_incomplete_episodes(self) -> List[Dict[str, Any]]:
        """Find episodes that have checkpoints but are not complete.
        
        Returns:
            List of incomplete episode information
        """
        incomplete = []
        completed = set(self.get_completed_episodes())
        
        # Check all episode checkpoints
        all_episodes = set()
        for filename in os.listdir(self.episodes_dir):
            if '_' in filename:
                episode_id = filename.split('_')[0]
                all_episodes.add(episode_id)
        
        # Find incomplete episodes
        for episode_id in all_episodes:
            if episode_id not in completed:
                checkpoints = self.get_episode_checkpoints(episode_id)
                if checkpoints:
                    # Find latest checkpoint
                    latest_stage = None
                    latest_time = None
                    
                    for checkpoint in checkpoints:
                        metadata_file = checkpoint['path'].replace('.ckpt', '.json').replace('.gz', '')
                        metadata_file = metadata_file.replace(self.episodes_dir, self.metadata_dir)
                        metadata_file = metadata_file.replace(self.segments_dir, self.metadata_dir)
                        
                        if os.path.exists(metadata_file):
                            with open(metadata_file, 'r') as f:
                                metadata = json.load(f)
                                updated_at = datetime.fromisoformat(metadata['updated_at'])
                                if latest_time is None or updated_at > latest_time:
                                    latest_time = updated_at
                                    latest_stage = checkpoint['stage']
                    
                    incomplete.append({
                        'episode_id': episode_id,
                        'latest_stage': latest_stage,
                        'last_updated': latest_time.isoformat() if latest_time else None,
                        'checkpoint_count': len(checkpoints)
                    })
        
        return incomplete
    
    def clean_old_checkpoints(self, days: Optional[int] = None) -> int:
        """Remove checkpoints older than specified days.
        
        Args:
            days: Number of days to keep checkpoints (uses max_checkpoint_age_days if None)
            
        Returns:
            Number of checkpoints removed
        """
        if days is None:
            days = self.max_checkpoint_age_days
        
        cutoff_time = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        # Clean all checkpoint directories
        for directory in [self.episodes_dir, self.segments_dir, self.metadata_dir]:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                
                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff_time:
                        os.remove(filepath)
                        removed_count += 1
                        logger.debug(f"Removed old checkpoint: {filename}")
                except Exception as e:
                    logger.error(f"Failed to remove checkpoint {filename}: {e}")
        
        logger.info(f"Cleaned {removed_count} old checkpoints")
        return removed_count
    
    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """Get statistics about checkpoints.
        
        Returns:
            Dictionary with checkpoint statistics
        """
        stats = {
            'total_checkpoints': 0,
            'episode_checkpoints': 0,
            'segment_checkpoints': 0,
            'total_size_mb': 0,
            'compressed_count': 0,
            'episodes_with_checkpoints': set(),
            'checkpoint_by_stage': {}
        }
        
        # Analyze episode checkpoints
        for filename in os.listdir(self.episodes_dir):
            if filename.endswith(('.ckpt', '.ckpt.gz')):
                stats['total_checkpoints'] += 1
                stats['episode_checkpoints'] += 1
                
                filepath = os.path.join(self.episodes_dir, filename)
                stats['total_size_mb'] += os.path.getsize(filepath) / (1024 * 1024)
                
                if filename.endswith('.gz'):
                    stats['compressed_count'] += 1
                
                # Extract episode ID and stage
                parts = filename.split('_')
                episode_id = parts[0]
                stage = parts[-1].replace('.ckpt', '').replace('.gz', '')
                
                stats['episodes_with_checkpoints'].add(episode_id)
                stats['checkpoint_by_stage'][stage] = stats['checkpoint_by_stage'].get(stage, 0) + 1
        
        # Analyze segment checkpoints
        for filename in os.listdir(self.segments_dir):
            if filename.endswith(('.ckpt', '.ckpt.gz')):
                stats['total_checkpoints'] += 1
                stats['segment_checkpoints'] += 1
                
                filepath = os.path.join(self.segments_dir, filename)
                stats['total_size_mb'] += os.path.getsize(filepath) / (1024 * 1024)
                
                if filename.endswith('.gz'):
                    stats['compressed_count'] += 1
        
        stats['episodes_with_checkpoints'] = len(stats['episodes_with_checkpoints'])
        stats['total_size_mb'] = round(stats['total_size_mb'], 2)
        
        return stats
    
    def export_checkpoints(self, export_path: str, episode_ids: Optional[List[str]] = None) -> str:
        """Export checkpoints to a compressed archive.
        
        Args:
            export_path: Path for the export archive
            episode_ids: Optional list of specific episodes to export
            
        Returns:
            Path to the created archive
        """
        import tempfile
        import zipfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy checkpoints to temp directory
            for directory, subdir in [(self.episodes_dir, 'episodes'), 
                                     (self.segments_dir, 'segments'),
                                     (self.metadata_dir, 'metadata')]:
                target_dir = os.path.join(tmpdir, subdir)
                os.makedirs(target_dir, exist_ok=True)
                
                for filename in os.listdir(directory):
                    # Filter by episode IDs if specified
                    if episode_ids:
                        episode_id = filename.split('_')[0]
                        if episode_id not in episode_ids:
                            continue
                    
                    src = os.path.join(directory, filename)
                    dst = os.path.join(target_dir, filename)
                    shutil.copy2(src, dst)
            
            # Create zip archive
            archive_path = export_path if export_path.endswith('.zip') else f"{export_path}.zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, tmpdir)
                        zipf.write(file_path, arcname)
            
            logger.info(f"Exported checkpoints to: {archive_path}")
            return archive_path
    
    def import_checkpoints(self, archive_path: str, overwrite: bool = False) -> int:
        """Import checkpoints from an archive.
        
        Args:
            archive_path: Path to the checkpoint archive
            overwrite: Whether to overwrite existing checkpoints
            
        Returns:
            Number of checkpoints imported
        """
        import zipfile
        
        imported_count = 0
        
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            for file_info in zipf.filelist:
                # Determine target directory
                if file_info.filename.startswith('episodes/'):
                    target_dir = self.episodes_dir
                elif file_info.filename.startswith('segments/'):
                    target_dir = self.segments_dir
                elif file_info.filename.startswith('metadata/'):
                    target_dir = self.metadata_dir
                else:
                    continue
                
                target_path = os.path.join(target_dir, os.path.basename(file_info.filename))
                
                # Check if file exists
                if os.path.exists(target_path) and not overwrite:
                    logger.debug(f"Skipping existing checkpoint: {file_info.filename}")
                    continue
                
                # Extract file
                zipf.extract(file_info, self.checkpoint_dir)
                imported_count += 1
        
        logger.info(f"Imported {imported_count} checkpoints")
        return imported_count