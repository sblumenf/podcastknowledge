"""Enhanced checkpoint management for resumable podcast processing."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union
import hashlib
import json
import logging
import os
import pickle
import shutil
import time

import gzip

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
    extraction_mode: str = "fixed"  # "fixed" or "schemaless"
    schema_info: Optional[Dict[str, Any]] = None  # For schemaless mode
    
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
            'checksum': self.checksum,
            'extraction_mode': self.extraction_mode,
            'schema_info': self.schema_info
        }


class ProgressCheckpoint(BaseProgressCheckpoint):
    """Enhanced checkpoint system for resumable processing with advanced features."""
    
    def __init__(self, 
                 checkpoint_dir: Optional[str] = None,
                 version: CheckpointVersion = CheckpointVersion.V3,
                 enable_compression: bool = True,
                 max_checkpoint_age_days: int = 30,
                 enable_distributed: bool = False,
                 extraction_mode: str = "fixed",
                 config: Optional[Dict[str, Any]] = None):
        """Initialize enhanced checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for storing checkpoints
            version: Checkpoint format version
            enable_compression: Whether to compress checkpoints
            max_checkpoint_age_days: Maximum age for checkpoints before cleanup
            enable_distributed: Enable distributed checkpoint support
            extraction_mode: "fixed" or "schemaless"
            config: Optional configuration dictionary
        """
        super().__init__(checkpoint_dir)
        self.version = version
        self.enable_compression = enable_compression
        self.max_checkpoint_age_days = max_checkpoint_age_days
        self.enable_distributed = enable_distributed
        self.extraction_mode = extraction_mode
        self.config = config or {}
        
        # Thread safety for distributed mode
        self._lock = Lock() if enable_distributed else None
        
        # Create subdirectories for organization
        self.episodes_dir = os.path.join(self.checkpoint_dir, 'episodes')
        self.segments_dir = os.path.join(self.checkpoint_dir, 'segments')
        self.metadata_dir = os.path.join(self.checkpoint_dir, 'metadata')
        self.schema_dir = os.path.join(self.checkpoint_dir, 'schema')  # For schemaless mode
        
        for dir_path in [self.episodes_dir, self.segments_dir, self.metadata_dir, self.schema_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Schema evolution tracking for schemaless mode
        self._discovered_types = set()
        self._schema_evolution_history = []
        
        logger.info(f"Initialized enhanced checkpoint manager at: {self.checkpoint_dir} "
                   f"(mode: {self.extraction_mode})")
    
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
            
            # Extract schema info for schemaless mode
            schema_info = None
            if self.extraction_mode == "schemaless" and isinstance(data, dict):
                if 'discovered_types' in data:
                    self._discovered_types.update(data['discovered_types'])
                schema_info = {
                    'discovered_types': data.get('discovered_types', []),
                    'entity_count': data.get('entities', 0),
                    'relationship_count': data.get('relationships', 0),
                    'extraction_metrics': data.get('metrics', {})
                }
            
            # Save metadata
            metadata = CheckpointMetadata(
                version=self.version.value,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                episode_id=episode_id,
                stage=stage,
                compressed=self.enable_compression,
                size_bytes=len(serialized_data),
                checksum=checksum,
                extraction_mode=self.extraction_mode,
                schema_info=schema_info
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
    
    # Schemaless mode support methods
    
    def save_schema_evolution(self, episode_id: str, discovered_types: List[str], 
                            timestamp: Optional[str] = None):
        """Save schema evolution information for schemaless mode.
        
        Args:
            episode_id: Episode where types were discovered
            discovered_types: List of newly discovered entity types
            timestamp: Optional timestamp (uses current time if None)
        """
        if self.extraction_mode != "schemaless":
            return
        
        timestamp = timestamp or datetime.now().isoformat()
        
        # Update discovered types
        new_types = set(discovered_types) - self._discovered_types
        if new_types:
            self._discovered_types.update(new_types)
            
            # Record evolution history
            evolution_entry = {
                'timestamp': timestamp,
                'episode_id': episode_id,
                'new_types': list(new_types),
                'total_types': len(self._discovered_types)
            }
            self._schema_evolution_history.append(evolution_entry)
            
            # Save to file
            schema_file = os.path.join(self.schema_dir, 'evolution_history.json')
            with open(schema_file, 'w') as f:
                json.dump({
                    'current_types': sorted(list(self._discovered_types)),
                    'history': self._schema_evolution_history
                }, f, indent=2)
            
            logger.info(f"Discovered {len(new_types)} new entity types in episode {episode_id}")
    
    def load_schema_evolution(self) -> Dict[str, Any]:
        """Load schema evolution history for schemaless mode.
        
        Returns:
            Schema evolution data
        """
        schema_file = os.path.join(self.schema_dir, 'evolution_history.json')
        if os.path.exists(schema_file):
            with open(schema_file, 'r') as f:
                data = json.load(f)
                self._discovered_types = set(data.get('current_types', []))
                self._schema_evolution_history = data.get('history', [])
                return data
        return {'current_types': [], 'history': []}
    
    def migrate_checkpoint_format(self, episode_id: str, stage: str, 
                                from_version: str = "fixed", to_version: str = "schemaless") -> bool:
        """Migrate checkpoint between formats.
        
        Args:
            episode_id: Episode ID to migrate
            stage: Processing stage
            from_version: Source format ("fixed" or "schemaless")
            to_version: Target format ("fixed" or "schemaless")
            
        Returns:
            True if migration successful
        """
        try:
            # Load existing checkpoint
            data = self.load_episode_progress(episode_id, stage)
            if not data:
                logger.warning(f"No checkpoint found for {episode_id} at stage {stage}")
                return False
            
            # Perform migration based on direction
            if from_version == "fixed" and to_version == "schemaless":
                # Add schemaless metadata
                if isinstance(data, dict):
                    data['mode'] = 'schemaless'
                    data['discovered_types'] = []  # Will be populated during reprocessing
            elif from_version == "schemaless" and to_version == "fixed":
                # Remove schemaless-specific fields
                if isinstance(data, dict):
                    data.pop('mode', None)
                    data.pop('discovered_types', None)
                    data.pop('metrics', None)
            
            # Save migrated checkpoint
            old_mode = self.extraction_mode
            self.extraction_mode = to_version
            success = self.save_episode_progress(episode_id, stage, data)
            self.extraction_mode = old_mode
            
            if success:
                logger.info(f"Successfully migrated checkpoint for {episode_id} from {from_version} to {to_version}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to migrate checkpoint: {e}")
            return False
    
    def get_schema_statistics(self) -> Dict[str, Any]:
        """Get statistics about discovered schema in schemaless mode.
        
        Returns:
            Schema statistics
        """
        if self.extraction_mode != "schemaless":
            return {'message': 'Schema statistics only available in schemaless mode'}
        
        # Load latest schema evolution data
        self.load_schema_evolution()
        
        stats = {
            'total_types_discovered': len(self._discovered_types),
            'entity_types': sorted(list(self._discovered_types)),
            'evolution_entries': len(self._schema_evolution_history),
            'first_discovery': self._schema_evolution_history[0]['timestamp'] if self._schema_evolution_history else None,
            'latest_discovery': self._schema_evolution_history[-1]['timestamp'] if self._schema_evolution_history else None,
            'discovery_timeline': self._get_discovery_timeline()
        }
        
        return stats
    
    def _get_discovery_timeline(self) -> List[Dict[str, Any]]:
        """Get timeline of type discoveries."""
        timeline = []
        for entry in self._schema_evolution_history[-10:]:  # Last 10 entries
            timeline.append({
                'date': entry['timestamp'][:10],  # Just date part
                'episode': entry['episode_id'],
                'new_types': entry['new_types'],
                'count': len(entry['new_types'])
            })
        return timeline
    
    # VTT File Tracking Methods
    def mark_vtt_processed(self, vtt_file: str, file_hash: str, segments_processed: int) -> None:
        """Mark a VTT file as processed with its hash for change detection.
        
        Args:
            vtt_file: Path to the VTT file
            file_hash: MD5 hash of the file content
            segments_processed: Number of segments processed from the file
        """
        vtt_checkpoint_file = os.path.join(self.checkpoint_dir, 'vtt_processed.json')
        
        # Load existing data
        vtt_data = {}
        if os.path.exists(vtt_checkpoint_file):
            try:
                with open(vtt_checkpoint_file, 'r') as f:
                    vtt_data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load VTT checkpoint: {e}")
                vtt_data = {}
        
        # Update with new file
        vtt_data[vtt_file] = {
            'hash': file_hash,
            'processed_at': datetime.now().isoformat(),
            'segments': segments_processed,
            'moved_to_processed': False  # Track if file has been moved
        }
        
        # Save updated data
        try:
            with open(vtt_checkpoint_file, 'w') as f:
                json.dump(vtt_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save VTT checkpoint: {e}")
    
    def is_vtt_processed(self, vtt_file: str, file_hash: str) -> bool:
        """Check if a VTT file has been processed with the same content.
        
        Args:
            vtt_file: Path to the VTT file
            file_hash: MD5 hash of the current file content
            
        Returns:
            True if file has been processed with same hash
        """
        vtt_checkpoint_file = os.path.join(self.checkpoint_dir, 'vtt_processed.json')
        
        if not os.path.exists(vtt_checkpoint_file):
            return False
        
        try:
            with open(vtt_checkpoint_file, 'r') as f:
                vtt_data = json.load(f)
                
            if vtt_file in vtt_data:
                # Check if hash matches (file unchanged)
                return vtt_data[vtt_file].get('hash') == file_hash
                
        except Exception as e:
            logger.warning(f"Failed to check VTT checkpoint: {e}")
        
        return False
    
    def get_processed_vtt_files(self) -> List[Dict[str, Any]]:
        """Get list of all processed VTT files.
        
        Returns:
            List of processed file information
        """
        vtt_checkpoint_file = os.path.join(self.checkpoint_dir, 'vtt_processed.json')
        
        if not os.path.exists(vtt_checkpoint_file):
            return []
        
        try:
            with open(vtt_checkpoint_file, 'r') as f:
                vtt_data = json.load(f)
                
            # Convert to list format
            processed_files = []
            for file_path, info in vtt_data.items():
                processed_files.append({
                    'file': file_path,
                    'hash': info.get('hash'),
                    'processed_at': info.get('processed_at'),
                    'segments': info.get('segments', 0)
                })
                
            return processed_files
            
        except Exception as e:
            logger.error(f"Failed to get VTT files: {e}")
            return []
    
    def mark_vtt_moved_to_processed(self, vtt_file: str, processed_path: str) -> None:
        """Mark a VTT file as moved to processed directory.
        
        Args:
            vtt_file: Original path to the VTT file
            processed_path: New path in processed directory
        """
        vtt_checkpoint_file = os.path.join(self.checkpoint_dir, 'vtt_processed.json')
        
        if not os.path.exists(vtt_checkpoint_file):
            return
        
        try:
            with open(vtt_checkpoint_file, 'r') as f:
                vtt_data = json.load(f)
            
            if vtt_file in vtt_data:
                vtt_data[vtt_file]['moved_to_processed'] = True
                vtt_data[vtt_file]['processed_path'] = processed_path
                vtt_data[vtt_file]['moved_at'] = datetime.now().isoformat()
                
                with open(vtt_checkpoint_file, 'w') as f:
                    json.dump(vtt_data, f, indent=2)
                    
                logger.info(f"Marked {vtt_file} as moved to processed directory")
                
        except Exception as e:
            logger.error(f"Failed to update VTT move status: {e}")
    
    def clear_vtt_checkpoint(self, vtt_file: Optional[str] = None) -> bool:
        """Clear VTT checkpoint data.
        
        Args:
            vtt_file: Specific file to clear, or None to clear all
            
        Returns:
            True if successful
        """
        vtt_checkpoint_file = os.path.join(self.checkpoint_dir, 'vtt_processed.json')
        
        if not os.path.exists(vtt_checkpoint_file):
            return True
        
        try:
            if vtt_file is None:
                # Clear all
                os.remove(vtt_checkpoint_file)
                logger.info("Cleared all VTT checkpoints")
            else:
                # Clear specific file
                with open(vtt_checkpoint_file, 'r') as f:
                    vtt_data = json.load(f)
                
                if vtt_file in vtt_data:
                    del vtt_data[vtt_file]
                    
                    with open(vtt_checkpoint_file, 'w') as f:
                        json.dump(vtt_data, f, indent=2)
                    
                    logger.info(f"Cleared checkpoint for {vtt_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear VTT checkpoint: {e}")
            return False
    
    def mark_episode_complete(self, episode_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark an episode as complete.
        
        Args:
            episode_id: Episode identifier
            metadata: Optional metadata about the completion
        """
        completion_data = {
            'episode_id': episode_id,
            'completed_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Save completion checkpoint
        self.save_episode_progress(episode_id, 'completed', completion_data)
        logger.info(f"Marked episode {episode_id} as complete")
    
    def get_completed_episodes(self) -> List[str]:
        """Get list of completed episode IDs.
        
        Returns:
            List of episode IDs that have been marked complete
        """
        completed_episodes = []
        
        # Check episodes directory for completed checkpoints
        if os.path.exists(self.episodes_dir):
            for filename in os.listdir(self.episodes_dir):
                if '_completed' in filename and (filename.endswith('.pkl') or filename.endswith('.pkl.gz') or filename.endswith('.ckpt.gz')):
                    # Extract episode ID from filename
                    # Handle different formats: episode_ID_completed.pkl, ID_completed.ckpt.gz, etc.
                    if filename.startswith('episode_'):
                        episode_id = filename.replace('episode_', '').split('_completed')[0]
                    else:
                        episode_id = filename.split('_completed')[0]
                    completed_episodes.append(episode_id)
        
        return completed_episodes