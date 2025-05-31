"""Tests for enhanced checkpoint management."""

from datetime import datetime, timedelta
import json
import os
import pickle
import tempfile
import time

import gzip
import pytest

from src.seeding.checkpoint import ProgressCheckpoint, CheckpointVersion, CheckpointMetadata
class TestProgressCheckpoint:
    """Tests for enhanced ProgressCheckpoint."""
    
    @pytest.fixture
    def checkpoint_dir(self):
        """Create temporary checkpoint directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def checkpoint_manager(self, checkpoint_dir):
        """Create checkpoint manager instance."""
        return ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            version=CheckpointVersion.V3,
            enable_compression=True,
            max_checkpoint_age_days=30
        )
    
    def test_initialization(self, checkpoint_manager, checkpoint_dir):
        """Test checkpoint manager initialization."""
        assert checkpoint_manager.checkpoint_dir == checkpoint_dir
        assert checkpoint_manager.version == CheckpointVersion.V3
        assert checkpoint_manager.enable_compression is True
        
        # Check subdirectories created
        assert os.path.exists(os.path.join(checkpoint_dir, 'episodes'))
        assert os.path.exists(os.path.join(checkpoint_dir, 'segments'))
        assert os.path.exists(os.path.join(checkpoint_dir, 'metadata'))
    
    def test_save_and_load_episode_checkpoint(self, checkpoint_manager):
        """Test saving and loading episode-level checkpoint."""
        episode_id = 'test_episode_1'
        stage = 'extraction'
        data = {
            'insights': ['insight1', 'insight2'],
            'entities': ['entity1', 'entity2']
        }
        
        # Save checkpoint
        success = checkpoint_manager.save_episode_progress(episode_id, stage, data)
        assert success is True
        
        # Load checkpoint
        loaded_data = checkpoint_manager.load_episode_progress(episode_id, stage)
        assert loaded_data == data
    
    def test_save_and_load_segment_checkpoint(self, checkpoint_manager):
        """Test saving and loading segment-level checkpoint."""
        episode_id = 'test_episode_1'
        stage = 'processing'
        segment_index = 5
        data = {
            'text': 'Segment text',
            'metrics': {'score': 0.95}
        }
        
        # Save segment checkpoint
        success = checkpoint_manager.save_episode_progress(
            episode_id, stage, data, segment_index=segment_index
        )
        assert success is True
        
        # Load segment checkpoint
        loaded_data = checkpoint_manager.load_episode_progress(
            episode_id, stage, segment_index=segment_index
        )
        assert loaded_data == data
    
    def test_compression(self, checkpoint_dir):
        """Test checkpoint compression."""
        # Create manager with compression enabled
        manager = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            enable_compression=True
        )
        
        large_data = {'data': 'x' * 10000}  # Large data to compress
        manager.save_episode_progress('ep1', 'test', large_data)
        
        # Check that compressed file exists
        checkpoint_file = os.path.join(
            checkpoint_dir, 'episodes', 'ep1_test.ckpt.gz'
        )
        assert os.path.exists(checkpoint_file)
        
        # Verify it's compressed
        with open(checkpoint_file, 'rb') as f:
            data = f.read()
            # Should be gzip magic number
            assert data[:2] == b'\x1f\x8b'
        
        # Verify we can load it
        loaded_data = manager.load_episode_progress('ep1', 'test')
        assert loaded_data == large_data
    
    def test_no_compression(self, checkpoint_dir):
        """Test checkpoint without compression."""
        manager = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            enable_compression=False
        )
        
        data = {'test': 'data'}
        manager.save_episode_progress('ep1', 'test', data)
        
        # Check that uncompressed file exists
        checkpoint_file = os.path.join(
            checkpoint_dir, 'episodes', 'ep1_test.ckpt'
        )
        assert os.path.exists(checkpoint_file)
        assert not os.path.exists(checkpoint_file + '.gz')
    
    def test_metadata_saving(self, checkpoint_manager):
        """Test metadata is saved correctly."""
        episode_id = 'test_ep'
        stage = 'metadata_test'
        data = {'key': 'value'}
        
        checkpoint_manager.save_episode_progress(episode_id, stage, data)
        
        # Check metadata file exists
        metadata_file = os.path.join(
            checkpoint_manager.metadata_dir,
            f'{episode_id}_{stage}.json'
        )
        assert os.path.exists(metadata_file)
        
        # Load and verify metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['version'] == CheckpointVersion.V3.value
        assert metadata['episode_id'] == episode_id
        assert metadata['stage'] == stage
        assert metadata['compressed'] is True
        assert metadata['size_bytes'] > 0
        assert metadata['checksum'] is not None
    
    def test_version_migration(self, checkpoint_dir):
        """Test checkpoint version migration."""
        # Create old version checkpoint manually
        old_checkpoint = {
            'version': CheckpointVersion.V1.value,
            'episode_id': 'ep1',
            'stage': 'test',
            'timestamp': datetime.now().isoformat(),
            'data': {'old': 'data'}
        }
        
        checkpoint_file = os.path.join(checkpoint_dir, 'episodes', 'ep1_test.ckpt')
        os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
        
        with open(checkpoint_file, 'wb') as f:
            pickle.dump(old_checkpoint, f)
        
        # Load with new version manager
        manager = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            version=CheckpointVersion.V3
        )
        
        loaded_data = manager.load_episode_progress('ep1', 'test')
        assert loaded_data == {'old': 'data'}
    
    def test_get_episode_checkpoints(self, checkpoint_manager):
        """Test getting all checkpoints for an episode."""
        episode_id = 'ep1'
        
        # Save multiple checkpoints
        checkpoint_manager.save_episode_progress(episode_id, 'stage1', {'data': 1})
        checkpoint_manager.save_episode_progress(episode_id, 'stage2', {'data': 2})
        checkpoint_manager.save_episode_progress(episode_id, 'segment', {'data': 3}, segment_index=0)
        
        checkpoints = checkpoint_manager.get_episode_checkpoints(episode_id)
        
        assert len(checkpoints) == 3
        stages = [cp['stage'] for cp in checkpoints]
        assert 'stage1' in stages
        assert 'stage2' in stages
        assert 'segment' in stages
        
        # Check segment checkpoint
        segment_cp = [cp for cp in checkpoints if cp['type'] == 'segment'][0]
        assert segment_cp['segment_index'] == 0
    
    def test_get_incomplete_episodes(self, checkpoint_manager):
        """Test finding incomplete episodes."""
        # Save checkpoints for incomplete episode
        checkpoint_manager.save_episode_progress('ep1', 'transcription', {'data': 1})
        checkpoint_manager.save_episode_progress('ep1', 'extraction', {'data': 2})
        
        # Save complete episode
        checkpoint_manager.save_episode_progress('ep2', 'complete', True)
        
        incomplete = checkpoint_manager.get_incomplete_episodes()
        
        assert len(incomplete) == 1
        assert incomplete[0]['episode_id'] == 'ep1'
        assert incomplete[0]['checkpoint_count'] == 2
    
    def test_clean_old_checkpoints(self, checkpoint_manager):
        """Test cleaning old checkpoints."""
        # Save checkpoint
        checkpoint_manager.save_episode_progress('old_ep', 'test', {'data': 'old'})
        
        # Modify file time to be old
        checkpoint_file = os.path.join(
            checkpoint_manager.episodes_dir,
            'old_ep_test.ckpt.gz'
        )
        old_time = time.time() - (40 * 24 * 60 * 60)  # 40 days ago
        os.utime(checkpoint_file, (old_time, old_time))
        
        # Clean checkpoints older than 30 days
        removed_count = checkpoint_manager.clean_old_checkpoints(days=30)
        
        assert removed_count > 0
        assert not os.path.exists(checkpoint_file)
    
    def test_checkpoint_statistics(self, checkpoint_manager):
        """Test getting checkpoint statistics."""
        # Create various checkpoints
        checkpoint_manager.save_episode_progress('ep1', 'stage1', {'data': 1})
        checkpoint_manager.save_episode_progress('ep1', 'stage2', {'data': 2})
        checkpoint_manager.save_episode_progress('ep2', 'stage1', {'data': 3})
        checkpoint_manager.save_episode_progress('ep1', 'segment', {'data': 4}, segment_index=0)
        
        stats = checkpoint_manager.get_checkpoint_statistics()
        
        assert stats['total_checkpoints'] == 4
        assert stats['episode_checkpoints'] == 3
        assert stats['segment_checkpoints'] == 1
        assert stats['episodes_with_checkpoints'] == 2
        assert stats['compressed_count'] == 4  # All compressed
        assert stats['checkpoint_by_stage']['stage1'] == 2
        assert stats['checkpoint_by_stage']['stage2'] == 1
    
    def test_export_checkpoints(self, checkpoint_manager, tmp_path):
        """Test exporting checkpoints."""
        # Create checkpoints
        checkpoint_manager.save_episode_progress('ep1', 'test', {'data': 1})
        checkpoint_manager.save_episode_progress('ep2', 'test', {'data': 2})
        
        # Export
        export_path = os.path.join(tmp_path, 'export.zip')
        created_path = checkpoint_manager.export_checkpoints(export_path)
        
        assert os.path.exists(created_path)
        assert created_path.endswith('.zip')
        
        # Verify zip contents
        import zipfile
        with zipfile.ZipFile(created_path, 'r') as zipf:
            names = zipf.namelist()
            assert any('episodes/' in name for name in names)
            assert any('metadata/' in name for name in names)
    
    def test_export_specific_episodes(self, checkpoint_manager, tmp_path):
        """Test exporting specific episodes only."""
        # Create checkpoints for multiple episodes
        checkpoint_manager.save_episode_progress('ep1', 'test', {'data': 1})
        checkpoint_manager.save_episode_progress('ep2', 'test', {'data': 2})
        checkpoint_manager.save_episode_progress('ep3', 'test', {'data': 3})
        
        # Export only ep1 and ep3
        export_path = os.path.join(tmp_path, 'selective_export.zip')
        created_path = checkpoint_manager.export_checkpoints(
            export_path, 
            episode_ids=['ep1', 'ep3']
        )
        
        # Verify only selected episodes exported
        import zipfile
        with zipfile.ZipFile(created_path, 'r') as zipf:
            names = zipf.namelist()
            ep_names = [n for n in names if 'episodes/' in n]
            
            assert any('ep1_' in name for name in ep_names)
            assert not any('ep2_' in name for name in ep_names)
            assert any('ep3_' in name for name in ep_names)
    
    def test_import_checkpoints(self, checkpoint_dir, tmp_path):
        """Test importing checkpoints from archive."""
        # Create source manager and add checkpoints
        source_manager = ProgressCheckpoint(checkpoint_dir=str(tmp_path / 'source'))
        source_manager.save_episode_progress('ep1', 'test', {'data': 1})
        source_manager.save_episode_progress('ep2', 'test', {'data': 2})
        
        # Export from source
        export_path = tmp_path / 'export.zip'
        source_manager.export_checkpoints(str(export_path))
        
        # Import to new manager
        target_manager = ProgressCheckpoint(checkpoint_dir=checkpoint_dir)
        imported_count = target_manager.import_checkpoints(str(export_path))
        
        assert imported_count > 0
        
        # Verify imported data
        data1 = target_manager.load_episode_progress('ep1', 'test')
        assert data1 == {'data': 1}
        
        data2 = target_manager.load_episode_progress('ep2', 'test')
        assert data2 == {'data': 2}
    
    def test_distributed_locking(self, checkpoint_dir):
        """Test distributed checkpoint support with locking."""
        manager = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            enable_distributed=True
        )
        
        # Verify lock was created
        assert manager._lock is not None
        
        # Test concurrent access (simplified)
        data = {'test': 'data'}
        success = manager.save_episode_progress('ep1', 'test', data)
        assert success is True
        
        loaded = manager.load_episode_progress('ep1', 'test')
        assert loaded == data


class TestCheckpointMetadata:
    """Tests for CheckpointMetadata."""
    
    def test_metadata_creation(self):
        """Test creating checkpoint metadata."""
        metadata = CheckpointMetadata(
            version='3.0',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            episode_id='ep1',
            stage='test',
            compressed=True,
            size_bytes=1024,
            checksum='abc123'
        )
        
        assert metadata.version == '3.0'
        assert metadata.episode_id == 'ep1'
        assert metadata.compressed is True
        assert metadata.size_bytes == 1024
        assert metadata.checksum == 'abc123'
    
    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = CheckpointMetadata(
            version='3.0',
            created_at='2023-01-01T00:00:00',
            updated_at='2023-01-01T00:00:00',
            episode_id='ep1',
            stage='test'
        )
        
        data = metadata.to_dict()
        
        assert data['version'] == '3.0'
        assert data['episode_id'] == 'ep1'
        assert data['stage'] == 'test'
        assert 'compressed' in data
        assert 'size_bytes' in data
        assert 'checksum' in data