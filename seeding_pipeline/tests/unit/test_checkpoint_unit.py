"""Unit tests for checkpoint management."""

import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from src.seeding.checkpoint import (
    CheckpointVersion,
    CheckpointMetadata,
    ProgressCheckpoint
)


class TestCheckpointVersion:
    """Test CheckpointVersion enum."""
    
    def test_versions(self):
        """Test checkpoint versions."""
        assert CheckpointVersion.V1.value == "1.0"
        assert CheckpointVersion.V2.value == "2.0"
        assert CheckpointVersion.V3.value == "3.0"


class TestCheckpointMetadata:
    """Test CheckpointMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating checkpoint metadata."""
        metadata = CheckpointMetadata(
            version="3.0",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            episode_id="test_episode",
            stage="processing",
            compressed=True,
            size_bytes=1024,
            checksum="abc123",
            extraction_mode="schemaless"
        )
        
        assert metadata.version == "3.0"
        assert metadata.episode_id == "test_episode"
        assert metadata.stage == "processing"
        assert metadata.compressed is True
        assert metadata.extraction_mode == "schemaless"
        
    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        now = datetime.now().isoformat()
        metadata = CheckpointMetadata(
            version="3.0",
            created_at=now,
            updated_at=now,
            episode_id="test_episode",
            stage="processing"
        )
        
        data = metadata.to_dict()
        assert data['version'] == "3.0"
        assert data['created_at'] == now
        assert data['episode_id'] == "test_episode"
        assert data['stage'] == "processing"


class TestProgressCheckpoint:
    """Test ProgressCheckpoint class."""
    
    def test_checkpoint_initialization(self):
        """Test initializing progress checkpoint."""
        checkpoint = ProgressCheckpoint(
            episode_id="test_episode",
            stage="processing",
            checkpoint_dir="./test_checkpoints"
        )
        
        assert checkpoint.episode_id == "test_episode"
        assert checkpoint.stage == "processing"
        assert checkpoint.state == {}
        
    def test_update_state(self):
        """Test updating checkpoint state."""
        checkpoint = ProgressCheckpoint(
            episode_id="test_episode",
            stage="processing",
            checkpoint_dir="./test_checkpoints"
        )
        
        checkpoint.update({"progress": 50, "status": "running"})
        assert checkpoint.state["progress"] == 50
        assert checkpoint.state["status"] == "running"
        
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_checkpoint(self, mock_makedirs, mock_file):
        """Test saving checkpoint."""
        checkpoint = ProgressCheckpoint(
            episode_id="test_episode",
            stage="processing",
            checkpoint_dir="./test_checkpoints"
        )
        
        checkpoint.update({"progress": 100})
        checkpoint.save()
        
        mock_makedirs.assert_called()
        mock_file.assert_called()
        
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"progress": 75}')
    def test_load_checkpoint(self, mock_file, mock_exists):
        """Test loading checkpoint."""
        mock_exists.return_value = True
        
        checkpoint = ProgressCheckpoint(
            episode_id="test_episode",
            stage="processing",
            checkpoint_dir="./test_checkpoints"
        )
        
        checkpoint.load()
        assert checkpoint.state["progress"] == 75