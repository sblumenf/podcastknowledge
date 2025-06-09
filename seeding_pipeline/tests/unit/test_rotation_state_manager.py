"""Unit tests for rotation state manager."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.utils.rotation_state_manager import RotationStateManager


class TestRotationStateManager:
    """Test RotationStateManager functionality."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for testing."""
        return tmp_path
    
    def test_get_state_directory_default(self):
        """Test getting state directory with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            state_dir = RotationStateManager.get_state_directory()
            assert state_dir == Path('data')
    
    def test_get_state_directory_from_env(self):
        """Test getting state directory from STATE_DIR env var."""
        with patch.dict(os.environ, {'STATE_DIR': '/custom/state'}, clear=True):
            state_dir = RotationStateManager.get_state_directory()
            assert state_dir == Path('/custom/state')
    
    def test_get_state_directory_from_checkpoint_dir(self):
        """Test getting state directory from CHECKPOINT_DIR env var."""
        with patch.dict(os.environ, {'CHECKPOINT_DIR': '/custom/checkpoint'}, clear=True):
            state_dir = RotationStateManager.get_state_directory()
            assert state_dir == Path('/custom/checkpoint/rotation_state')
    
    def test_ensure_state_persistence_success(self, temp_dir):
        """Test successful state persistence setup."""
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            result = RotationStateManager.ensure_state_persistence()
            assert result is True
            assert temp_dir.exists()
            # Test file should have been created and deleted
            assert not (temp_dir / '.write_test').exists()
    
    def test_ensure_state_persistence_failure(self):
        """Test state persistence setup failure."""
        with patch.dict(os.environ, {'STATE_DIR': '/invalid/path/that/does/not/exist'}, clear=True):
            result = RotationStateManager.ensure_state_persistence()
            assert result is False
    
    def test_get_rotation_metrics(self, temp_dir):
        """Test getting rotation metrics."""
        # Create state file
        state_file = temp_dir / '.key_rotation_state.json'
        state_file.write_text('{"test": "data"}')
        
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            metrics = RotationStateManager.get_rotation_metrics()
            
            assert metrics['state_directory'] == str(temp_dir)
            assert metrics['state_file_exists'] is True
            assert metrics['state_file_size'] > 0
            assert metrics['directory_writable'] is True
    
    def test_get_rotation_metrics_no_file(self, temp_dir):
        """Test getting rotation metrics when state file doesn't exist."""
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            metrics = RotationStateManager.get_rotation_metrics()
            
            assert metrics['state_directory'] == str(temp_dir)
            assert metrics['state_file_exists'] is False
            assert metrics['state_file_size'] == 0
            assert metrics['directory_writable'] is True
    
    def test_cleanup_old_states(self, temp_dir):
        """Test cleaning up old state files."""
        # Create old backup files
        import time
        old_time = time.time() - (35 * 24 * 60 * 60)  # 35 days ago
        
        old_file1 = temp_dir / '.key_rotation_state.2024-01-01.backup'
        old_file1.touch()
        os.utime(old_file1, (old_time, old_time))
        
        old_file2 = temp_dir / '.key_rotation_state.2024-01-02.backup'
        old_file2.touch()
        os.utime(old_file2, (old_time, old_time))
        
        # Create recent backup
        recent_file = temp_dir / '.key_rotation_state.recent.backup'
        recent_file.touch()
        
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            cleaned = RotationStateManager.cleanup_old_states(days=30)
            
            assert cleaned == 2
            assert not old_file1.exists()
            assert not old_file2.exists()
            assert recent_file.exists()
    
    def test_cleanup_old_states_no_files(self, temp_dir):
        """Test cleanup when no old files exist."""
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            cleaned = RotationStateManager.cleanup_old_states(days=30)
            assert cleaned == 0
    
    def test_cleanup_old_states_permission_error(self, temp_dir):
        """Test cleanup with permission errors."""
        # Create old file
        import time
        old_time = time.time() - (35 * 24 * 60 * 60)
        
        old_file = temp_dir / '.key_rotation_state.old.backup'
        old_file.touch()
        os.utime(old_file, (old_time, old_time))
        
        # Mock unlink to raise permission error
        with patch.dict(os.environ, {'STATE_DIR': str(temp_dir)}, clear=True):
            with patch.object(Path, 'unlink', side_effect=PermissionError("No permission")):
                cleaned = RotationStateManager.cleanup_old_states(days=30)
                assert cleaned == 0  # Failed to clean