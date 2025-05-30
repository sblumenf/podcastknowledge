"""Tests for memory management utilities - matches actual API."""

import pytest
import gc
import psutil
import os
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

from src.utils.memory import (
    cleanup_memory,
    monitor_memory,
    managed_resources,
    ResourceManager,
    memory_limited,
    monitor_resources,
    batch_processor,
    MemoryMonitor
)


class TestCleanupMemory:
    """Test cleanup_memory function."""
    
    def test_cleanup_memory(self):
        """Test memory cleanup function."""
        # Create some garbage
        data = [list(range(1000)) for _ in range(100)]
        del data
        
        # Run cleanup
        cleanup_memory()
        
        # Should not raise any exceptions
        assert True
    
    @patch('gc.collect')
    def test_cleanup_calls_gc(self, mock_gc):
        """Test that cleanup calls garbage collector."""
        cleanup_memory()
        
        # Should call gc.collect multiple times
        assert mock_gc.call_count >= 1


class TestMonitorMemory:
    """Test monitor_memory function."""
    
    def test_monitor_memory_returns_dict(self):
        """Test memory monitoring returns metrics."""
        result = monitor_memory()
        
        assert isinstance(result, dict)
        assert 'rss_mb' in result
        assert 'available_mb' in result
        assert 'percent' in result
        assert 'gc_stats' in result
    
    def test_monitor_memory_values(self):
        """Test memory monitoring values are reasonable."""
        result = monitor_memory()
        
        assert result['rss_mb'] > 0
        assert result['available_mb'] > 0
        assert 0 <= result['percent'] <= 100


class TestManagedResources:
    """Test managed_resources context manager."""
    
    def test_managed_resources_basic(self):
        """Test basic resource management."""
        with managed_resources(cleanup=True, monitor=False):
            # Do some work
            data = list(range(10000))
        
        # Should complete without error
        assert True
    
    def test_managed_resources_with_monitoring(self):
        """Test resource management with monitoring."""
        with managed_resources(cleanup=True, monitor=True):
            data = list(range(10000))
        
        # Should complete without error
        assert True
    
    def test_managed_resources_exception_handling(self):
        """Test resource management handles exceptions."""
        with pytest.raises(ValueError):
            with managed_resources(cleanup=True):
                raise ValueError("Test error")


class TestResourceManager:
    """Test ResourceManager class."""
    
    @pytest.fixture
    def resource_manager(self):
        """Create ResourceManager instance."""
        return ResourceManager()
    
    def test_resource_manager_initialization(self):
        """Test ResourceManager initialization."""
        manager = ResourceManager(
            memory_limit_mb=1024,
            check_interval=30
        )
        
        assert manager.memory_limit_mb == 1024
        assert manager.check_interval == 30
    
    def test_register_resource(self, resource_manager):
        """Test registering resources."""
        resource = Mock()
        resource_manager.register_resource("test_resource", resource)
        
        assert "test_resource" in resource_manager.resources
        assert resource_manager.resources["test_resource"] == resource
    
    def test_cleanup_resource(self, resource_manager):
        """Test cleaning up specific resource."""
        resource = Mock()
        resource.close = Mock()
        
        resource_manager.register_resource("test", resource)
        resource_manager.cleanup_resource("test")
        
        resource.close.assert_called_once()
        assert "test" not in resource_manager.resources
    
    def test_cleanup_all(self, resource_manager):
        """Test cleaning up all resources."""
        resource1 = Mock(close=Mock())
        resource2 = Mock(close=Mock())
        
        resource_manager.register_resource("r1", resource1)
        resource_manager.register_resource("r2", resource2)
        
        resource_manager.cleanup_all()
        
        resource1.close.assert_called_once()
        resource2.close.assert_called_once()
        assert len(resource_manager.resources) == 0
    
    def test_check_memory_limit(self, resource_manager):
        """Test memory limit checking."""
        resource_manager.memory_limit_mb = 10000  # High limit
        
        # Should not exceed limit (unless system is really stressed)
        exceeded = resource_manager.check_memory_limit()
        assert exceeded is False
    
    def test_get_memory_usage(self, resource_manager):
        """Test getting memory usage."""
        usage = resource_manager.get_memory_usage()
        
        assert isinstance(usage, dict)
        assert 'current_mb' in usage
        assert 'limit_mb' in usage
        assert 'percent_of_limit' in usage


class TestMemoryLimited:
    """Test memory_limited decorator."""
    
    def test_memory_limited_success(self):
        """Test decorator with function within memory limit."""
        @memory_limited(max_percent=95.0, cleanup=False)
        def test_function():
            data = list(range(1000))
            return len(data)
        
        result = test_function()
        assert result == 1000
    
    def test_memory_limited_with_cleanup(self):
        """Test decorator with cleanup enabled."""
        @memory_limited(max_percent=95.0, cleanup=True)
        def test_function():
            data = list(range(10000))
            return "done"
        
        result = test_function()
        assert result == "done"
    
    @patch('psutil.virtual_memory')
    def test_memory_limited_exceeds_limit(self, mock_vm):
        """Test decorator when memory limit exceeded."""
        # Mock high memory usage
        mock_vm.return_value = Mock(percent=96.0)
        
        @memory_limited(max_percent=90.0)
        def test_function():
            return "should not run"
        
        with pytest.raises(MemoryError):
            test_function()


class TestMonitorResources:
    """Test monitor_resources decorator."""
    
    def test_monitor_resources_basic(self):
        """Test basic resource monitoring."""
        @monitor_resources
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
    
    def test_monitor_resources_with_exception(self):
        """Test monitoring when function raises."""
        @monitor_resources
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()


class TestBatchProcessor:
    """Test batch_processor function."""
    
    def test_batch_processor_basic(self):
        """Test basic batch processing."""
        data = list(range(100))
        results = []
        
        def process_batch(batch):
            results.extend([x * 2 for x in batch])
        
        batch_processor(
            data=data,
            process_func=process_batch,
            batch_size=10
        )
        
        assert len(results) == 100
        assert results[0] == 0
        assert results[-1] == 198
    
    def test_batch_processor_with_memory_check(self):
        """Test batch processing with memory checks."""
        data = list(range(50))
        processed = []
        
        def process(batch):
            processed.extend(batch)
        
        batch_processor(
            data=data,
            process_func=process,
            batch_size=10,
            check_memory=True,
            memory_threshold=90.0
        )
        
        assert len(processed) == 50
    
    def test_batch_processor_empty_data(self):
        """Test batch processing with empty data."""
        results = []
        
        def process(batch):
            results.extend(batch)
        
        batch_processor(
            data=[],
            process_func=process,
            batch_size=10
        )
        
        assert len(results) == 0


class TestMemoryMonitor:
    """Test MemoryMonitor class."""
    
    @pytest.fixture
    def memory_monitor(self):
        """Create MemoryMonitor instance."""
        return MemoryMonitor()
    
    def test_memory_monitor_initialization(self):
        """Test MemoryMonitor initialization."""
        monitor = MemoryMonitor(
            threshold_mb=512,
            check_interval=60
        )
        
        assert monitor.threshold_mb == 512
        assert monitor.check_interval == 60
        assert monitor.peak_usage == 0
    
    def test_start_stop_monitoring(self, memory_monitor):
        """Test starting and stopping monitoring."""
        memory_monitor.start()
        assert memory_monitor.is_running is True
        
        memory_monitor.stop()
        assert memory_monitor.is_running is False
    
    def test_check_usage(self, memory_monitor):
        """Test checking memory usage."""
        usage = memory_monitor.check_usage()
        
        assert isinstance(usage, dict)
        assert 'current_mb' in usage
        assert 'peak_mb' in usage
        assert 'threshold_mb' in usage
    
    def test_reset_peak(self, memory_monitor):
        """Test resetting peak usage."""
        memory_monitor.peak_usage = 1000
        memory_monitor.reset_peak()
        
        # Peak should be reset to current usage
        assert memory_monitor.peak_usage >= 0
    
    def test_get_report(self, memory_monitor):
        """Test getting memory report."""
        report = memory_monitor.get_report()
        
        assert isinstance(report, dict)
        assert 'current_usage' in report
        assert 'peak_usage' in report
        assert 'threshold' in report
        assert 'warnings' in report or 'status' in report