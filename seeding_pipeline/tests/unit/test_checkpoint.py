"""Unit tests for checkpoint management."""

import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from src.seeding.checkpoint import (
    CheckpointManager,
    CheckpointState,
    SegmentCheckpoint,
    EpisodeCheckpoint,
    CheckpointError,
    create_checkpoint_manager
)


class TestCheckpointState:
    """Test CheckpointState enum."""
    
    def test_checkpoint_state_values(self):
        """Test CheckpointState values."""
        assert CheckpointState.NOT_STARTED == "not_started"
        assert CheckpointState.IN_PROGRESS == "in_progress"
        assert CheckpointState.COMPLETED == "completed"
        assert CheckpointState.FAILED == "failed"
        assert CheckpointState.PARTIAL == "partial"


class TestSegmentCheckpoint:
    """Test SegmentCheckpoint dataclass."""
    
    def test_segment_checkpoint_creation(self):
        """Test creating SegmentCheckpoint."""
        checkpoint = SegmentCheckpoint(
            segment_id="seg123",
            episode_id="ep456",
            state=CheckpointState.COMPLETED,
            start_time="2023-12-25T10:00:00",
            end_time="2023-12-25T10:05:00",
            error=None,
            data={"entities": [], "insights": []}
        )
        
        assert checkpoint.segment_id == "seg123"
        assert checkpoint.episode_id == "ep456"
        assert checkpoint.state == CheckpointState.COMPLETED
        assert checkpoint.error is None
        assert "entities" in checkpoint.data
    
    def test_segment_checkpoint_with_error(self):
        """Test SegmentCheckpoint with error."""
        checkpoint = SegmentCheckpoint(
            segment_id="seg789",
            episode_id="ep123",
            state=CheckpointState.FAILED,
            start_time="2023-12-25T10:00:00",
            end_time="2023-12-25T10:01:00",
            error="Processing failed",
            data=None
        )
        
        assert checkpoint.state == CheckpointState.FAILED
        assert checkpoint.error == "Processing failed"
        assert checkpoint.data is None
    
    def test_segment_checkpoint_to_dict(self):
        """Test converting SegmentCheckpoint to dictionary."""
        checkpoint = SegmentCheckpoint(
            segment_id="seg123",
            episode_id="ep456",
            state=CheckpointState.IN_PROGRESS,
            start_time="2023-12-25T10:00:00"
        )
        
        result = checkpoint.to_dict()
        
        assert result["segment_id"] == "seg123"
        assert result["episode_id"] == "ep456"
        assert result["state"] == "in_progress"
        assert result["start_time"] == "2023-12-25T10:00:00"
    
    def test_segment_checkpoint_from_dict(self):
        """Test creating SegmentCheckpoint from dictionary."""
        data = {
            "segment_id": "seg123",
            "episode_id": "ep456",
            "state": "completed",
            "start_time": "2023-12-25T10:00:00",
            "end_time": "2023-12-25T10:05:00",
            "error": None,
            "data": {"test": "value"}
        }
        
        checkpoint = SegmentCheckpoint.from_dict(data)
        
        assert checkpoint.segment_id == "seg123"
        assert checkpoint.state == CheckpointState.COMPLETED
        assert checkpoint.data["test"] == "value"


class TestEpisodeCheckpoint:
    """Test EpisodeCheckpoint dataclass."""
    
    def test_episode_checkpoint_creation(self):
        """Test creating EpisodeCheckpoint."""
        checkpoint = EpisodeCheckpoint(
            episode_id="ep123",
            state=CheckpointState.IN_PROGRESS,
            start_time="2023-12-25T10:00:00",
            segments_total=10,
            segments_completed=5,
            segments_failed=1
        )
        
        assert checkpoint.episode_id == "ep123"
        assert checkpoint.state == CheckpointState.IN_PROGRESS
        assert checkpoint.segments_total == 10
        assert checkpoint.segments_completed == 5
        assert checkpoint.segments_failed == 1
    
    def test_episode_checkpoint_completion(self):
        """Test EpisodeCheckpoint completion status."""
        # All segments completed
        checkpoint = EpisodeCheckpoint(
            episode_id="ep123",
            state=CheckpointState.COMPLETED,
            segments_total=10,
            segments_completed=10,
            segments_failed=0
        )
        
        assert checkpoint.is_complete()
        
        # Some segments failed
        checkpoint.segments_failed = 2
        checkpoint.segments_completed = 8
        assert not checkpoint.is_complete()
    
    def test_episode_checkpoint_progress(self):
        """Test EpisodeCheckpoint progress calculation."""
        checkpoint = EpisodeCheckpoint(
            episode_id="ep123",
            state=CheckpointState.IN_PROGRESS,
            segments_total=10,
            segments_completed=7,
            segments_failed=1
        )
        
        progress = checkpoint.get_progress()
        assert progress == 0.7  # 7/10 = 0.7


class TestCheckpointManager:
    """Test CheckpointManager class."""
    
    def test_checkpoint_manager_initialization(self):
        """Test CheckpointManager initialization."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        assert manager.checkpoint_dir == Path("/tmp/checkpoints")
        assert manager.episode_dir == Path("/tmp/checkpoints/episodes")
        assert manager.segment_dir == Path("/tmp/checkpoints/segments")
    
    @patch('pathlib.Path.mkdir')
    def test_checkpoint_manager_init_directories(self, mock_mkdir):
        """Test checkpoint directory initialization."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        manager._init_directories()
        
        # Should create directories
        assert mock_mkdir.call_count >= 2
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_segment_checkpoint(self, mock_json_dump, mock_file):
        """Test saving segment checkpoint."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        checkpoint = SegmentCheckpoint(
            segment_id="seg123",
            episode_id="ep456",
            state=CheckpointState.COMPLETED,
            data={"entities": []}
        )
        
        with patch('pathlib.Path.mkdir'):
            manager.save_segment_checkpoint(checkpoint)
        
        # Should open file and dump JSON
        mock_file.assert_called()
        mock_json_dump.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"segment_id": "seg123", "state": "completed"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_segment_checkpoint(self, mock_exists, mock_file):
        """Test loading segment checkpoint."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        checkpoint = manager.load_segment_checkpoint("seg123", "ep456")
        
        assert checkpoint is not None
        assert checkpoint.segment_id == "seg123"
        assert checkpoint.state == CheckpointState.COMPLETED
    
    @patch('pathlib.Path.exists', return_value=False)
    def test_load_segment_checkpoint_not_found(self, mock_exists):
        """Test loading non-existent segment checkpoint."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        checkpoint = manager.load_segment_checkpoint("seg999", "ep999")
        
        assert checkpoint is None
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_episode_checkpoint(self, mock_json_dump, mock_file):
        """Test saving episode checkpoint."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        checkpoint = EpisodeCheckpoint(
            episode_id="ep123",
            state=CheckpointState.IN_PROGRESS,
            segments_total=10,
            segments_completed=5
        )
        
        with patch('pathlib.Path.mkdir'):
            manager.save_episode_checkpoint(checkpoint)
        
        mock_file.assert_called()
        mock_json_dump.assert_called_once()
    
    @patch('pathlib.Path.glob')
    def test_get_incomplete_episodes(self, mock_glob):
        """Test getting incomplete episodes."""
        # Mock checkpoint files
        mock_files = [
            Mock(stem="ep1"),
            Mock(stem="ep2"),
            Mock(stem="ep3")
        ]
        mock_glob.return_value = mock_files
        
        # Mock loading checkpoints
        checkpoints = [
            EpisodeCheckpoint(episode_id="ep1", state=CheckpointState.COMPLETED),
            EpisodeCheckpoint(episode_id="ep2", state=CheckpointState.IN_PROGRESS),
            EpisodeCheckpoint(episode_id="ep3", state=CheckpointState.FAILED)
        ]
        
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        with patch.object(manager, 'load_episode_checkpoint', side_effect=checkpoints):
            incomplete = manager.get_incomplete_episodes()
        
        assert len(incomplete) == 2
        assert incomplete[0].episode_id == "ep2"
        assert incomplete[1].episode_id == "ep3"
    
    @patch('pathlib.Path.glob')
    def test_get_failed_segments(self, mock_glob):
        """Test getting failed segments."""
        mock_files = [
            Mock(stem="seg1_ep1"),
            Mock(stem="seg2_ep1"),
            Mock(stem="seg3_ep2")
        ]
        mock_glob.return_value = mock_files
        
        # Mock loading checkpoints
        checkpoints = [
            SegmentCheckpoint(segment_id="seg1", episode_id="ep1", state=CheckpointState.COMPLETED),
            SegmentCheckpoint(segment_id="seg2", episode_id="ep1", state=CheckpointState.FAILED),
            SegmentCheckpoint(segment_id="seg3", episode_id="ep2", state=CheckpointState.FAILED)
        ]
        
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        with patch.object(manager, 'load_segment_checkpoint') as mock_load:
            # Configure mock to return appropriate checkpoints
            def side_effect(seg_id, ep_id):
                for cp in checkpoints:
                    if cp.segment_id == seg_id and cp.episode_id == ep_id:
                        return cp
                return None
            
            mock_load.side_effect = side_effect
            
            # Get failed segments for ep1
            failed = manager.get_failed_segments("ep1")
        
        assert len(failed) == 1
        assert failed[0].segment_id == "seg2"
    
    @patch('pathlib.Path.unlink')
    @patch('pathlib.Path.exists', return_value=True)
    def test_clear_checkpoint(self, mock_exists, mock_unlink):
        """Test clearing checkpoint."""
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        manager.clear_checkpoint("ep123")
        
        # Should attempt to delete file
        mock_unlink.assert_called()
    
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.unlink')
    def test_clear_all_checkpoints(self, mock_unlink, mock_glob):
        """Test clearing all checkpoints."""
        mock_files = [Mock(), Mock(), Mock()]
        mock_glob.return_value = mock_files
        
        manager = CheckpointManager(checkpoint_dir="/tmp/checkpoints")
        
        manager.clear_all_checkpoints()
        
        # Should delete all files
        assert mock_unlink.call_count == len(mock_files) * 2  # Episodes and segments
    
    def test_checkpoint_error(self):
        """Test CheckpointError exception."""
        with pytest.raises(CheckpointError) as exc_info:
            raise CheckpointError("Test checkpoint error")
        
        assert str(exc_info.value) == "Test checkpoint error"


class TestCreateCheckpointManager:
    """Test create_checkpoint_manager function."""
    
    @patch.dict(os.environ, {"CHECKPOINT_DIR": "/custom/checkpoints"})
    def test_create_checkpoint_manager_with_env(self):
        """Test creating checkpoint manager with environment variable."""
        manager = create_checkpoint_manager()
        
        assert str(manager.checkpoint_dir) == "/custom/checkpoints"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_create_checkpoint_manager_default(self):
        """Test creating checkpoint manager with default directory."""
        manager = create_checkpoint_manager()
        
        assert "checkpoints" in str(manager.checkpoint_dir)