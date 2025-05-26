"""Tests for memory management utilities."""

import gc
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.utils.memory import (
    cleanup_memory,
    monitor_memory,
    managed_resources,
    ResourceManager,
    memory_limited,
    monitor_resources,
    batch_processor
)


class TestMemoryCleanup:
    """Tests for memory cleanup functionality."""
    
    @patch('src.utils.memory.gc.collect')
    def test_cleanup_memory_basic(self, mock_gc):
        """Test basic garbage collection."""
        cleanup_memory()
        assert mock_gc.call_count == 2  # Called twice
    
    @patch('src.utils.memory.torch')
    @patch('src.utils.memory.HAS_TORCH', True)
    @patch('src.utils.memory.gc.collect')
    def test_cleanup_memory_with_gpu(self, mock_gc, mock_torch):
        """Test GPU memory cleanup when torch is available."""
        mock_torch.cuda.is_available.return_value = True
        
        cleanup_memory()
        
        mock_torch.cuda.empty_cache.assert_called_once()
        assert mock_gc.call_count == 2
    
    @patch('src.utils.memory.plt')
    @patch('src.utils.memory.HAS_MATPLOTLIB', True)
    @patch('src.utils.memory.gc.collect')
    def test_cleanup_memory_with_matplotlib(self, mock_gc, mock_plt):
        """Test matplotlib figure cleanup."""
        cleanup_memory()
        
        mock_plt.close.assert_called_once_with('all')
        assert mock_gc.call_count == 2


class TestMemoryMonitoring:
    """Tests for memory monitoring functionality."""
    
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_monitor_memory_cpu(self, mock_psutil):
        """Test CPU memory monitoring."""
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_memory.used = 8 * (1024**3)  # 8 GB
        mock_memory.total = 16 * (1024**3)  # 16 GB
        mock_memory.available = 8 * (1024**3)  # 8 GB
        mock_psutil.virtual_memory.return_value = mock_memory
        
        stats = monitor_memory()
        
        assert 'cpu_memory' in stats
        assert stats['cpu_memory']['percent'] == 50.0
        assert stats['cpu_memory']['used_gb'] == 8.0
        assert stats['cpu_memory']['total_gb'] == 16.0
        assert stats['cpu_memory']['available_gb'] == 8.0
    
    @patch('src.utils.memory.torch')
    @patch('src.utils.memory.HAS_TORCH', True)
    @patch('src.utils.memory.HAS_PSUTIL', False)
    def test_monitor_memory_gpu(self, mock_torch):
        """Test GPU memory monitoring."""
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.return_value = 4 * (1024**3)  # 4 GB
        mock_torch.cuda.memory_reserved.return_value = 6 * (1024**3)  # 6 GB
        
        mock_device = Mock()
        mock_device.total_memory = 8 * (1024**3)  # 8 GB
        mock_torch.cuda.get_device_properties.return_value = mock_device
        
        stats = monitor_memory()
        
        assert 'gpu_memory' in stats
        assert stats['gpu_memory']['allocated_gb'] == 4.0
        assert stats['gpu_memory']['reserved_gb'] == 6.0
        assert stats['gpu_memory']['total_gb'] == 8.0
        assert stats['gpu_memory']['percent'] == 50.0
    
    @patch('src.utils.memory.HAS_PSUTIL', False)
    @patch('src.utils.memory.HAS_TORCH', False)
    def test_monitor_memory_no_dependencies(self):
        """Test monitoring when dependencies are not available."""
        stats = monitor_memory()
        assert stats == {}


class TestManagedResources:
    """Tests for managed resources context manager."""
    
    @patch('src.utils.memory.cleanup_memory')
    def test_managed_resources_cleanup(self, mock_cleanup):
        """Test resource cleanup on exit."""
        with managed_resources(cleanup=True):
            pass
        
        mock_cleanup.assert_called_once()
    
    @patch('src.utils.memory.cleanup_memory')
    def test_managed_resources_no_cleanup(self, mock_cleanup):
        """Test skipping cleanup when disabled."""
        with managed_resources(cleanup=False):
            pass
        
        mock_cleanup.assert_not_called()
    
    @patch('src.utils.memory.monitor_memory')
    @patch('src.utils.memory.cleanup_memory')
    def test_managed_resources_monitoring(self, mock_cleanup, mock_monitor):
        """Test resource monitoring."""
        mock_monitor.return_value = {
            'cpu_memory': {'used_gb': 4.0, 'total_gb': 16.0}
        }
        
        with managed_resources(cleanup=True, monitor=True):
            pass
        
        assert mock_monitor.call_count == 2  # Before and after
        mock_cleanup.assert_called_once()
    
    @patch('src.utils.memory.cleanup_memory')
    def test_managed_resources_exception_handling(self, mock_cleanup):
        """Test cleanup happens even with exceptions."""
        with pytest.raises(ValueError):
            with managed_resources(cleanup=True):
                raise ValueError("Test error")
        
        mock_cleanup.assert_called_once()


class TestResourceManager:
    """Tests for ResourceManager class."""
    
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_resource_manager_within_limits(self, mock_psutil):
        """Test when memory is within limits."""
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        manager = ResourceManager(max_memory_percent=80.0)
        assert manager.check_memory() is True
    
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_resource_manager_exceeds_limits(self, mock_psutil):
        """Test when memory exceeds limits."""
        mock_memory = Mock()
        mock_memory.percent = 90.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        manager = ResourceManager(max_memory_percent=80.0)
        assert manager.check_memory() is False
    
    @patch('src.utils.memory.cleanup_memory')
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_resource_manager_auto_cleanup(self, mock_psutil, mock_cleanup):
        """Test automatic cleanup when threshold is reached."""
        # First call returns high memory, second call (after cleanup) returns lower
        mock_memory1 = Mock(percent=85.0)
        mock_memory2 = Mock(percent=60.0)
        mock_psutil.virtual_memory.side_effect = [mock_memory1, mock_memory2]
        
        manager = ResourceManager(
            cleanup_threshold=80.0,
            auto_cleanup=True
        )
        
        assert manager.check_memory() is True
        mock_cleanup.assert_called_once()
        assert manager.cleanup_count == 1
    
    @patch('src.utils.memory.cleanup_memory')
    def test_resource_manager_context(self, mock_cleanup):
        """Test ResourceManager as context manager."""
        manager = ResourceManager(auto_cleanup=True)
        
        with manager:
            pass
        
        mock_cleanup.assert_called_once()
    
    @patch('src.utils.memory.HAS_PSUTIL', False)
    def test_resource_manager_no_psutil(self):
        """Test ResourceManager when psutil is not available."""
        manager = ResourceManager(max_memory_percent=80.0)
        assert manager.check_memory() is True  # Always returns True without psutil


class TestMemoryDecorators:
    """Tests for memory-related decorators."""
    
    @patch('src.utils.memory.cleanup_memory')
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_memory_limited_decorator(self, mock_psutil, mock_cleanup):
        """Test memory_limited decorator."""
        mock_memory = Mock(percent=50.0)
        mock_psutil.virtual_memory.return_value = mock_memory
        
        @memory_limited(max_percent=80.0, cleanup=True)
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
        mock_cleanup.assert_called_once()
    
    @patch('src.utils.memory.psutil')
    @patch('src.utils.memory.HAS_PSUTIL', True)
    def test_memory_limited_exceeds(self, mock_psutil):
        """Test memory_limited when memory exceeds limit."""
        mock_memory = Mock(percent=95.0)
        mock_psutil.virtual_memory.return_value = mock_memory
        
        @memory_limited(max_percent=80.0)
        def test_func():
            return "success"
        
        with pytest.raises(MemoryError):
            test_func()
    
    @patch('src.utils.memory.monitor_memory')
    def test_monitor_resources_decorator(self, mock_monitor):
        """Test monitor_resources decorator."""
        mock_monitor.return_value = {
            'cpu_memory': {'used_gb': 4.0}
        }
        
        @monitor_resources
        def test_func(x):
            return x * 2
        
        result = test_func(5)
        assert result == 10
        assert mock_monitor.call_count == 2  # Before and after


class TestBatchProcessor:
    """Tests for batch processor decorator."""
    
    @patch('src.utils.memory.cleanup_memory')
    def test_batch_processor_basic(self, mock_cleanup):
        """Test basic batch processing."""
        @batch_processor(batch_size=3, cleanup_interval=2)
        def process_items(batch):
            for item in batch:
                yield item * 2
        
        items = list(range(10))
        results = list(process_items(items))
        
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
        # Should cleanup after 2 batches and at the end
        assert mock_cleanup.call_count >= 2
    
    @patch('src.utils.memory.cleanup_memory')
    def test_batch_processor_exact_batches(self, mock_cleanup):
        """Test when items divide evenly into batches."""
        @batch_processor(batch_size=2, cleanup_interval=10)
        def process_items(batch):
            for item in batch:
                yield item + 1
        
        items = [1, 2, 3, 4]
        results = list(process_items(items))
        
        assert results == [2, 3, 4, 5]
        # Only cleanup at the end
        mock_cleanup.assert_called_once()
    
    def test_batch_processor_empty_input(self):
        """Test batch processor with empty input."""
        @batch_processor(batch_size=5)
        def process_items(batch):
            for item in batch:
                yield item
        
        results = list(process_items([]))
        assert results == []
    
    @patch('src.utils.memory.managed_resources')
    def test_batch_processor_monitoring(self, mock_managed):
        """Test batch processor with monitoring enabled."""
        mock_context = MagicMock()
        mock_managed.return_value.__enter__ = Mock(return_value=mock_context)
        mock_managed.return_value.__exit__ = Mock(return_value=None)
        
        @batch_processor(batch_size=2, monitor=True)
        def process_items(batch):
            yield from batch
        
        list(process_items([1, 2, 3]))
        
        mock_managed.assert_called_once_with(cleanup=False, monitor=True)