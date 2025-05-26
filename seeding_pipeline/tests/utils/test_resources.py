"""Tests for resource management utilities."""

import os
import shutil
import tempfile
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.utils.resources import (
    TempFileManager,
    temp_file,
    temp_dir,
    ProgressCheckpoint,
    ResourcePool,
    ConnectionManager,
    file_lock
)


class TestTempFileManager:
    """Tests for TempFileManager class."""
    
    def test_create_temp_file(self):
        """Test temporary file creation."""
        manager = TempFileManager()
        
        # Create temp file
        filepath = manager.create_temp_file(suffix='.txt', prefix='test_')
        assert os.path.exists(filepath)
        assert filepath.endswith('.txt')
        assert 'test_' in os.path.basename(filepath)
        
        # Clean up
        manager.cleanup_file(filepath)
        assert not os.path.exists(filepath)
    
    def test_create_temp_dir(self):
        """Test temporary directory creation."""
        manager = TempFileManager()
        
        # Create temp directory
        dirpath = manager.create_temp_dir(prefix='testdir_')
        assert os.path.exists(dirpath)
        assert os.path.isdir(dirpath)
        assert 'testdir_' in os.path.basename(dirpath)
        
        # Add a file to the directory
        test_file = os.path.join(dirpath, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        
        # Clean up
        manager.cleanup_dir(dirpath)
        assert not os.path.exists(dirpath)
        assert not os.path.exists(test_file)
    
    def test_cleanup_all(self):
        """Test cleanup of all temporary resources."""
        manager = TempFileManager()
        
        # Create multiple files and directories
        files = [manager.create_temp_file() for _ in range(3)]
        dirs = [manager.create_temp_dir() for _ in range(2)]
        
        # Verify all exist
        for f in files:
            assert os.path.exists(f)
        for d in dirs:
            assert os.path.exists(d)
        
        # Clean up all
        manager.cleanup_all()
        
        # Verify all are removed
        for f in files:
            assert not os.path.exists(f)
        for d in dirs:
            assert not os.path.exists(d)
    
    def test_context_manager(self):
        """Test TempFileManager as context manager."""
        with TempFileManager() as manager:
            file1 = manager.create_temp_file()
            dir1 = manager.create_temp_dir()
            
            assert os.path.exists(file1)
            assert os.path.exists(dir1)
        
        # Should be cleaned up after context
        assert not os.path.exists(file1)
        assert not os.path.exists(dir1)
    
    def test_cleanup_nonexistent(self):
        """Test cleanup of non-existent files."""
        manager = TempFileManager()
        
        # Should not raise error
        assert manager.cleanup_file('/nonexistent/file.txt') is True
        assert manager.cleanup_dir('/nonexistent/dir') is True


class TestTempContextManagers:
    """Tests for temporary file/dir context managers."""
    
    def test_temp_file_context(self):
        """Test temp_file context manager."""
        content = b"test content"
        
        with temp_file(suffix='.bin') as f:
            filepath = f.name
            f.write(content)
            f.seek(0)
            assert f.read() == content
            assert os.path.exists(filepath)
        
        # File should be deleted after context
        assert not os.path.exists(filepath)
    
    def test_temp_file_text_mode(self):
        """Test temp_file with text mode."""
        with temp_file(mode='w+') as f:
            f.write("test text")
            f.seek(0)
            assert f.read() == "test text"
    
    def test_temp_dir_context(self):
        """Test temp_dir context manager."""
        with temp_dir(prefix='testdir_') as dirpath:
            assert os.path.exists(dirpath)
            assert os.path.isdir(dirpath)
            
            # Create file in temp dir
            test_file = os.path.join(dirpath, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            assert os.path.exists(test_file)
        
        # Directory and contents should be deleted
        assert not os.path.exists(dirpath)
        assert not os.path.exists(test_file)


class TestProgressCheckpoint:
    """Tests for ProgressCheckpoint class."""
    
    @pytest.fixture
    def checkpoint_dir(self):
        """Create a temporary checkpoint directory."""
        dirpath = tempfile.mkdtemp()
        yield dirpath
        shutil.rmtree(dirpath, ignore_errors=True)
    
    def test_save_and_load_checkpoint(self, checkpoint_dir):
        """Test saving and loading checkpoints."""
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        # Save checkpoint
        test_data = {'insights': ['insight1', 'insight2'], 'score': 0.95}
        success = checkpoint.save_episode_progress('ep123', 'analysis', test_data)
        assert success is True
        
        # Load checkpoint
        loaded_data = checkpoint.load_episode_progress('ep123', 'analysis')
        assert loaded_data == test_data
    
    def test_load_nonexistent_checkpoint(self, checkpoint_dir):
        """Test loading non-existent checkpoint."""
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        data = checkpoint.load_episode_progress('nonexistent', 'stage')
        assert data is None
    
    def test_get_completed_episodes(self, checkpoint_dir):
        """Test getting completed episodes."""
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        # Save some checkpoints
        checkpoint.save_episode_progress('ep1', 'complete', {'done': True})
        checkpoint.save_episode_progress('ep2', 'complete', {'done': True})
        checkpoint.save_episode_progress('ep3', 'partial', {'done': False})
        
        completed = checkpoint.get_completed_episodes()
        assert set(completed) == {'ep1', 'ep2'}
    
    def test_clean_episode_checkpoints(self, checkpoint_dir):
        """Test cleaning episode checkpoints."""
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        # Save multiple checkpoints for same episode
        checkpoint.save_episode_progress('ep123', 'stage1', {'data': 1})
        checkpoint.save_episode_progress('ep123', 'stage2', {'data': 2})
        checkpoint.save_episode_progress('ep456', 'stage1', {'data': 3})
        
        # Clean checkpoints for ep123
        checkpoint.clean_episode_checkpoints('ep123')
        
        # ep123 checkpoints should be gone
        assert checkpoint.load_episode_progress('ep123', 'stage1') is None
        assert checkpoint.load_episode_progress('ep123', 'stage2') is None
        
        # ep456 should still exist
        assert checkpoint.load_episode_progress('ep456', 'stage1') == {'data': 3}
    
    @patch('os.path.getmtime')
    def test_clean_old_checkpoints(self, mock_getmtime, checkpoint_dir):
        """Test cleaning old checkpoints."""
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        # Save checkpoints
        checkpoint.save_episode_progress('ep1', 'stage', {'data': 1})
        checkpoint.save_episode_progress('ep2', 'stage', {'data': 2})
        
        # Mock file times - ep1 is old, ep2 is recent
        current_time = time.time()
        old_time = current_time - (10 * 24 * 60 * 60)  # 10 days old
        recent_time = current_time - (2 * 24 * 60 * 60)  # 2 days old
        
        def mock_time(filepath):
            if 'ep1' in filepath:
                return old_time
            return recent_time
        
        mock_getmtime.side_effect = mock_time
        
        # Clean checkpoints older than 7 days
        checkpoint.clean_old_checkpoints(days=7)
        
        # Old checkpoint should be gone
        assert checkpoint.load_episode_progress('ep1', 'stage') is None
        # Recent checkpoint should remain
        assert checkpoint.load_episode_progress('ep2', 'stage') == {'data': 2}


class TestResourcePool:
    """Tests for ResourcePool class."""
    
    def test_acquire_and_release(self):
        """Test basic acquire and release."""
        created_count = 0
        
        def factory():
            nonlocal created_count
            created_count += 1
            return f"resource_{created_count}"
        
        pool = ResourcePool(factory, max_size=2)
        
        # Acquire resources
        r1 = pool.acquire()
        assert r1 == "resource_1"
        assert created_count == 1
        
        r2 = pool.acquire()
        assert r2 == "resource_2"
        assert created_count == 2
        
        # Release and reacquire
        pool.release(r1)
        r3 = pool.acquire()
        assert r3 == r1  # Should reuse
        assert created_count == 2  # No new resource created
    
    def test_reset_function(self):
        """Test resource reset on reuse."""
        reset_called = False
        
        def factory():
            return {'value': 'dirty'}
        
        def reset(resource):
            nonlocal reset_called
            reset_called = True
            resource['value'] = 'clean'
        
        pool = ResourcePool(factory, reset_func=reset)
        
        # Acquire and modify resource
        r1 = pool.acquire()
        r1['value'] = 'modified'
        
        # Release and reacquire
        pool.release(r1)
        r2 = pool.acquire()
        
        assert reset_called is True
        assert r2['value'] == 'clean'
    
    def test_context_manager(self):
        """Test resource pool context manager."""
        pool = ResourcePool(lambda: "resource")
        
        with pool.get_resource() as resource:
            assert resource == "resource"
            assert resource in pool._in_use
        
        # Should be released after context
        assert len(pool._in_use) == 0
        assert len(pool._available) == 1
    
    def test_max_pool_size(self):
        """Test pool size limiting."""
        pool = ResourcePool(lambda: object(), max_size=2)
        
        # Create and release 3 resources
        resources = [pool.acquire() for _ in range(3)]
        for r in resources:
            pool.release(r)
        
        # Only 2 should be kept in pool
        assert len(pool._available) == 2
    
    def test_clear_pool(self):
        """Test clearing the pool."""
        pool = ResourcePool(lambda: object())
        
        # Create and release resources
        for _ in range(3):
            r = pool.acquire()
            pool.release(r)
        
        assert len(pool._available) == 3
        
        # Clear pool
        pool.clear()
        assert len(pool._available) == 0


class TestConnectionManager:
    """Tests for ConnectionManager class."""
    
    def test_get_connection(self):
        """Test getting connection."""
        mock_conn = Mock()
        factory = Mock(return_value=mock_conn)
        
        manager = ConnectionManager(factory)
        
        # First call creates connection
        conn1 = manager.get_connection()
        assert conn1 is mock_conn
        assert factory.call_count == 1
        
        # Second call returns same connection
        conn2 = manager.get_connection()
        assert conn2 is mock_conn
        assert factory.call_count == 1  # No new connection
    
    def test_close_connection(self):
        """Test closing connection."""
        mock_conn = Mock()
        factory = Mock(return_value=mock_conn)
        
        manager = ConnectionManager(factory)
        conn = manager.get_connection()
        
        # Close connection
        manager.close()
        mock_conn.close.assert_called_once()
        
        # Getting connection again creates new one
        conn2 = manager.get_connection()
        assert factory.call_count == 2
    
    def test_custom_close_function(self):
        """Test custom close function."""
        mock_conn = Mock()
        custom_close = Mock()
        
        manager = ConnectionManager(
            lambda: mock_conn,
            close_func=custom_close
        )
        
        manager.get_connection()
        manager.close()
        
        custom_close.assert_called_once_with(mock_conn)
        mock_conn.close.assert_not_called()
    
    def test_context_manager(self):
        """Test ConnectionManager as context manager."""
        mock_conn = Mock()
        factory = Mock(return_value=mock_conn)
        
        manager = ConnectionManager(factory)
        
        with manager as conn:
            assert conn is mock_conn
        
        # Should be closed after context
        mock_conn.close.assert_called_once()
    
    def test_close_error_handling(self):
        """Test error handling during close."""
        mock_conn = Mock()
        mock_conn.close.side_effect = Exception("Close failed")
        
        manager = ConnectionManager(lambda: mock_conn)
        manager.get_connection()
        
        # Should not raise exception
        manager.close()
        assert manager._connection is None


class TestFileLock:
    """Tests for file_lock context manager."""
    
    def test_file_lock_basic(self):
        """Test basic file locking."""
        test_file = tempfile.mktemp()
        
        with file_lock(test_file):
            # Lock file should exist
            assert os.path.exists(f"{test_file}.lock")
        
        # Lock file should be removed
        assert not os.path.exists(f"{test_file}.lock")
    
    def test_file_lock_timeout(self):
        """Test lock timeout."""
        test_file = tempfile.mktemp()
        lock_file = f"{test_file}.lock"
        
        # Create lock file manually
        with open(lock_file, 'w') as f:
            f.write('locked')
        
        try:
            # Should timeout trying to acquire lock
            with pytest.raises(TimeoutError):
                with file_lock(test_file, timeout=0.1):
                    pass
        finally:
            # Clean up
            if os.path.exists(lock_file):
                os.remove(lock_file)
    
    def test_file_lock_cleanup_on_exception(self):
        """Test lock cleanup on exception."""
        test_file = tempfile.mktemp()
        
        with pytest.raises(ValueError):
            with file_lock(test_file):
                raise ValueError("Test error")
        
        # Lock should still be cleaned up
        assert not os.path.exists(f"{test_file}.lock")