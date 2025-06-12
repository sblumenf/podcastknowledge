"""Tests for simplified memory management utilities."""

from unittest.mock import patch, MagicMock

import pytest

from src.utils.memory import cleanup_memory, get_memory_usage
class TestMemoryUtils:
    """Test simple memory management utilities."""
    
    @patch('gc.collect')
    def test_cleanup_memory(self, mock_gc):
        """Test that cleanup_memory calls garbage collection."""
        cleanup_memory()
        mock_gc.assert_called_once()
    
    def test_get_memory_usage_with_psutil(self):
        """Test memory usage reporting with psutil available."""
        # Should return a non-negative number
        usage = get_memory_usage()
        assert isinstance(usage, float)
        assert usage >= 0.0
    
    @patch('src.utils.memory.psutil', None)
    def test_get_memory_usage_without_psutil(self):
        """Test memory usage when psutil is not available."""
        usage = get_memory_usage()
        assert usage == 0.0
    
    @patch('psutil.Process')
    def test_get_memory_usage_with_error(self, mock_process_class):
        """Test memory usage when psutil raises an error."""
        mock_process_class.side_effect = Exception("Process error")
        usage = get_memory_usage()
        assert usage == 0.0