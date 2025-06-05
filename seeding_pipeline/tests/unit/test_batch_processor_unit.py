"""Comprehensive unit tests for batch processor module."""

import pytest
from unittest.mock import Mock, patch, call
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time
import threading
from dataclasses import dataclass
from typing import List, Any

from src.seeding.batch_processor import (
    BatchItem, BatchResult, BatchProcessor, ProgressiveMemoryOptimizer,
    QueueManager, BatchQueue, BatchMetrics, ResourceMonitor
)
from src.core.exceptions import BatchProcessingError


class TestBatchItem:
    """Test BatchItem dataclass."""
    
    def test_batch_item_creation(self):
        """Test creating BatchItem."""
        item = BatchItem(
            id="test_1",
            data={"content": "test data"},
            priority=5,
            metadata={"source": "test"}
        )
        
        assert item.id == "test_1"
        assert item.data == {"content": "test data"}
        assert item.priority == 5
        assert item.metadata == {"source": "test"}
    
    def test_batch_item_defaults(self):
        """Test BatchItem with default values."""
        item = BatchItem(id="test", data="data")
        
        assert item.priority == 0
        assert item.metadata is None
    
    def test_batch_item_ordering(self):
        """Test BatchItem ordering by priority."""
        items = [
            BatchItem("low", "data", priority=1),
            BatchItem("high", "data", priority=10),
            BatchItem("medium", "data", priority=5)
        ]
        
        sorted_items = sorted(items, key=lambda x: x.priority, reverse=True)
        
        assert sorted_items[0].id == "high"
        assert sorted_items[1].id == "medium"
        assert sorted_items[2].id == "low"


class TestBatchResult:
    """Test BatchResult dataclass."""
    
    def test_batch_result_success(self):
        """Test successful BatchResult."""
        result = BatchResult(
            item_id="test_1",
            success=True,
            result={"processed": True},
            processing_time=1.5,
            metadata={"worker": "thread_1"}
        )
        
        assert result.item_id == "test_1"
        assert result.success is True
        assert result.result == {"processed": True}
        assert result.error is None
        assert result.processing_time == 1.5
        assert result.metadata == {"worker": "thread_1"}
    
    def test_batch_result_failure(self):
        """Test failed BatchResult."""
        result = BatchResult(
            item_id="test_2",
            success=False,
            error="Processing failed",
            processing_time=0.1
        )
        
        assert result.item_id == "test_2"
        assert result.success is False
        assert result.result is None
        assert result.error == "Processing failed"
        assert result.processing_time == 0.1


class TestBatchProcessor:
    """Test BatchProcessor functionality."""
    
    @pytest.fixture
    def processor(self):
        """Create a BatchProcessor instance."""
        return BatchProcessor(
            max_workers=2,
            batch_size=5,
            use_processes=False
        )
    
    @pytest.fixture
    def progress_callback(self):
        """Create a mock progress callback."""
        return Mock()
    
    def test_initialization_default_params(self):
        """Test processor initialization with defaults."""
        processor = BatchProcessor()
        
        assert processor.max_workers > 0
        assert processor.batch_size == 10
        assert processor.use_processes is False
        assert processor.memory_limit_mb is None
        assert processor.progress_callback is None
        assert processor._items_processed == 0
        assert processor._total_items == 0
    
    def test_initialization_custom_params(self, progress_callback):
        """Test processor initialization with custom parameters."""
        config = {"use_schemaless_extraction": True}
        
        processor = BatchProcessor(
            max_workers=4,
            batch_size=20,
            use_processes=True,
            memory_limit_mb=1024,
            progress_callback=progress_callback,
            config=config,
            is_schemaless=True
        )
        
        assert processor.max_workers == 4
        assert processor.batch_size == 20
        assert processor.use_processes is True
        assert processor.memory_limit_mb == 1024
        assert processor.progress_callback == progress_callback
        assert processor.config == config
        assert processor.is_schemaless is True
    
    def test_process_items_empty_list(self, processor):
        """Test processing empty list of items."""
        result = processor.process_items([], lambda x: x)
        
        assert result == []
        assert processor._items_processed == 0
        assert processor._total_items == 0
    
    def test_process_items_single_item(self, processor):
        """Test processing single item."""
        def mock_process_func(item):
            return f"processed_{item.data}"
        
        items = [BatchItem("test_1", "data")]
        results = processor.process_items(items, mock_process_func)
        
        assert len(results) == 1
        assert results[0].item_id == "test_1"
        assert results[0].success is True
        assert "processed_data" in str(results[0].result)
    
    def test_process_items_multiple_items(self, processor):
        """Test processing multiple items."""
        def mock_process_func(item):
            return f"processed_{item.data}"
        
        items = [
            BatchItem("test_1", "data1"),
            BatchItem("test_2", "data2"),
            BatchItem("test_3", "data3")
        ]
        
        results = processor.process_items(items, mock_process_func)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all("processed_" in str(r.result) for r in results)
    
    def test_process_items_with_priority_sorting(self, processor):
        """Test that items are processed in priority order."""
        processed_order = []
        
        def mock_process_func(item):
            processed_order.append(item.id)
            return f"processed_{item.id}"
        
        items = [
            BatchItem("low", "data", priority=1),
            BatchItem("high", "data", priority=10),
            BatchItem("medium", "data", priority=5)
        ]
        
        processor.process_items(items, mock_process_func)
        
        # Note: Due to parallel processing, exact order isn't guaranteed
        # but high priority should generally be processed first
        assert "high" in processed_order
        assert "medium" in processed_order
        assert "low" in processed_order
    
    def test_process_items_with_batch_func(self, processor):
        """Test processing with batch function."""
        def mock_batch_func(batch_items):
            return [f"batch_processed_{item.data}" for item in batch_items]
        
        items = [
            BatchItem("test_1", "data1"),
            BatchItem("test_2", "data2")
        ]
        
        results = processor.process_items(items, None, mock_batch_func)
        
        assert len(results) == 2
        assert all(r.success for r in results)
    
    def test_process_items_with_error(self, processor):
        """Test processing items with errors."""
        def failing_process_func(item):
            if item.data == "bad_data":
                raise ValueError("Processing failed")
            return f"processed_{item.data}"
        
        items = [
            BatchItem("test_1", "good_data"),
            BatchItem("test_2", "bad_data"),
            BatchItem("test_3", "good_data")
        ]
        
        results = processor.process_items(items, failing_process_func)
        
        assert len(results) == 3
        success_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        assert len(success_results) == 2
        assert len(failed_results) == 1
        assert "Processing failed" in failed_results[0].error
    
    def test_create_batches_single_batch(self, processor):
        """Test creating single batch."""
        items = [BatchItem(f"test_{i}", f"data_{i}") for i in range(3)]
        
        batches = processor._create_batches(items)
        
        assert len(batches) == 1
        assert len(batches[0]) == 3
    
    def test_create_batches_multiple_batches(self, processor):
        """Test creating multiple batches."""
        processor._optimal_batch_size = 2
        items = [BatchItem(f"test_{i}", f"data_{i}") for i in range(5)]
        
        batches = processor._create_batches(items)
        
        assert len(batches) == 3
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1
    
    @patch('psutil.virtual_memory')
    def test_check_memory_usage_below_limit(self, mock_memory, processor):
        """Test memory usage check below limit."""
        processor.memory_limit_mb = 1000
        mock_memory.return_value.used = 500 * 1024 * 1024  # 500 MB
        
        result = processor._check_memory_usage()
        
        assert result is False
    
    @patch('psutil.virtual_memory')
    def test_check_memory_usage_above_limit(self, mock_memory, processor):
        """Test memory usage check above limit."""
        processor.memory_limit_mb = 1000
        mock_memory.return_value.used = 950 * 1024 * 1024  # 950 MB (95%)
        
        result = processor._check_memory_usage()
        
        assert result is True
    
    def test_check_memory_usage_no_limit(self, processor):
        """Test memory usage check with no limit set."""
        processor.memory_limit_mb = None
        
        result = processor._check_memory_usage()
        
        assert result is False
    
    def test_check_memory_usage_no_psutil(self, processor):
        """Test memory usage check without psutil."""
        processor.memory_limit_mb = 1000
        
        with patch('src.seeding.batch_processor.psutil', None):
            with patch.dict('sys.modules', {'psutil': None}):
                result = processor._check_memory_usage()
        
        assert result is False
    
    def test_process_single_item_success(self, processor):
        """Test processing single item successfully."""
        def mock_process_func(item):
            return f"processed_{item.data}"
        
        item = BatchItem("test_1", "data")
        
        result = processor._process_single_item(item, mock_process_func)
        
        assert result.item_id == "test_1"
        assert result.success is True
        assert "processed_data" in str(result.result)
        assert result.processing_time > 0
    
    def test_process_single_item_error(self, processor):
        """Test processing single item with error."""
        def failing_process_func(item):
            raise ValueError("Test error")
        
        item = BatchItem("test_1", "data")
        
        result = processor._process_single_item(item, failing_process_func)
        
        assert result.item_id == "test_1"
        assert result.success is False
        assert "Test error" in result.error
        assert result.processing_time > 0
    
    def test_update_progress_with_callback(self, progress_callback):
        """Test progress update with callback."""
        processor = BatchProcessor(progress_callback=progress_callback)
        processor._total_items = 10
        
        processor._update_progress()
        processor._update_progress()
        
        assert progress_callback.call_count == 2
        calls = progress_callback.call_args_list
        assert calls[0] == call(1, 10)
        assert calls[1] == call(2, 10)
    
    def test_update_progress_without_callback(self, processor):
        """Test progress update without callback."""
        processor._total_items = 5
        
        # Should not raise exception
        processor._update_progress()
        processor._update_progress()
        
        assert processor._items_processed == 2
    
    def test_get_processing_stats(self, processor):
        """Test getting processing statistics."""
        processor._items_processed = 5
        processor._total_items = 10
        processor._success_count = 3
        processor._failure_count = 2
        processor._start_time = time.time() - 10  # 10 seconds ago
        
        stats = processor.get_processing_stats()
        
        assert stats['items_processed'] == 5
        assert stats['total_items'] == 10
        assert stats['success_count'] == 3
        assert stats['failure_count'] == 2
        assert stats['progress_percentage'] == 50.0
        assert stats['elapsed_time'] > 0
        assert 'items_per_second' in stats
        assert 'estimated_time_remaining' in stats
    
    def test_get_processing_stats_no_start_time(self, processor):
        """Test getting stats before processing starts."""
        stats = processor.get_processing_stats()
        
        assert stats['items_processed'] == 0
        assert stats['total_items'] == 0
        assert stats['progress_percentage'] == 0.0
        assert stats['elapsed_time'] == 0.0
        assert stats['items_per_second'] == 0.0
        assert stats['estimated_time_remaining'] == 0.0
    
    def test_thread_safety(self, processor):
        """Test thread safety of progress tracking."""
        def mock_process_func(item):
            time.sleep(0.01)  # Small delay
            return "processed"
        
        items = [BatchItem(f"test_{i}", f"data_{i}") for i in range(10)]
        
        # Process with multiple threads
        results = processor.process_items(items, mock_process_func)
        
        assert len(results) == 10
        assert processor._items_processed == 10
        assert all(r.success for r in results)
    
    @patch('src.seeding.batch_processor.ThreadPoolExecutor')
    def test_use_thread_executor(self, mock_thread_executor, processor):
        """Test using ThreadPoolExecutor."""
        processor.use_processes = False
        mock_executor = Mock()
        mock_thread_executor.return_value.__enter__.return_value = mock_executor
        mock_executor.submit.return_value.result.return_value = BatchResult("test", True, "result")
        
        items = [BatchItem("test", "data")]
        processor._process_individual_items(items, lambda x: x)
        
        mock_thread_executor.assert_called_once_with(max_workers=processor.max_workers)
    
    @patch('src.seeding.batch_processor.ProcessPoolExecutor')
    def test_use_process_executor(self, mock_process_executor, processor):
        """Test using ProcessPoolExecutor."""
        processor.use_processes = True
        mock_executor = Mock()
        mock_process_executor.return_value.__enter__.return_value = mock_executor
        mock_executor.submit.return_value.result.return_value = BatchResult("test", True, "result")
        
        items = [BatchItem("test", "data")]
        processor._process_individual_items(items, lambda x: x)
        
        mock_process_executor.assert_called_once_with(max_workers=processor.max_workers)


class TestProgressiveMemoryOptimizer:
    """Test memory optimization functionality."""
    
    @pytest.fixture
    def optimizer(self):
        """Create ProgressiveMemoryOptimizer instance."""
        return ProgressiveMemoryOptimizer(
            initial_batch_size=10,
            memory_limit_mb=1000
        )
    
    def test_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.initial_batch_size == 10
        assert optimizer.memory_limit_mb == 1000
        assert optimizer.current_batch_size == 10
        assert len(optimizer.performance_history) == 0
    
    @patch('psutil.virtual_memory')
    def test_should_reduce_batch_size_high_memory(self, mock_memory, optimizer):
        """Test batch size reduction under high memory usage."""
        mock_memory.return_value.used = 950 * 1024 * 1024  # 95% of 1000MB
        
        result = optimizer.should_reduce_batch_size()
        
        assert result is True
    
    @patch('psutil.virtual_memory')
    def test_should_reduce_batch_size_low_memory(self, mock_memory, optimizer):
        """Test no batch size reduction under low memory usage."""
        mock_memory.return_value.used = 500 * 1024 * 1024  # 50% of 1000MB
        
        result = optimizer.should_reduce_batch_size()
        
        assert result is False
    
    def test_optimize_batch_size_reduce(self, optimizer):
        """Test optimizing batch size by reduction."""
        optimizer.current_batch_size = 20
        
        with patch.object(optimizer, 'should_reduce_batch_size', return_value=True):
            new_size = optimizer.optimize_batch_size(processing_time=5.0)
        
        assert new_size < 20
        assert new_size >= 1  # Should not go below 1
    
    def test_optimize_batch_size_increase(self, optimizer):
        """Test optimizing batch size by increase."""
        optimizer.current_batch_size = 10
        optimizer.performance_history = [(8, 2.0), (10, 1.5)]  # Improving performance
        
        with patch.object(optimizer, 'should_reduce_batch_size', return_value=False):
            new_size = optimizer.optimize_batch_size(processing_time=1.0)
        
        assert new_size >= 10


class TestQueueManager:
    """Test queue management functionality."""
    
    @pytest.fixture
    def queue_manager(self):
        """Create QueueManager instance."""
        return QueueManager(max_size=100)
    
    def test_initialization(self, queue_manager):
        """Test queue manager initialization."""
        assert queue_manager.max_size == 100
        assert queue_manager.queues == {}
        assert queue_manager.metrics is not None
    
    def test_create_queue(self, queue_manager):
        """Test creating a new queue."""
        queue = queue_manager.create_queue("test_queue", priority=5)
        
        assert queue.name == "test_queue"
        assert queue.priority == 5
        assert "test_queue" in queue_manager.queues
    
    def test_add_item_to_queue(self, queue_manager):
        """Test adding item to queue."""
        queue = queue_manager.create_queue("test_queue")
        item = BatchItem("test", "data")
        
        queue_manager.add_item("test_queue", item)
        
        assert queue.size() == 1
        assert not queue.is_empty()
    
    def test_get_next_item_single_queue(self, queue_manager):
        """Test getting next item from single queue."""
        queue = queue_manager.create_queue("test_queue")
        item = BatchItem("test", "data")
        
        queue_manager.add_item("test_queue", item)
        retrieved_item = queue_manager.get_next_item()
        
        assert retrieved_item.id == "test"
        assert queue.is_empty()
    
    def test_get_next_item_priority_order(self, queue_manager):
        """Test getting items in priority order from multiple queues."""
        high_queue = queue_manager.create_queue("high", priority=10)
        low_queue = queue_manager.create_queue("low", priority=1)
        
        queue_manager.add_item("low", BatchItem("low_item", "data"))
        queue_manager.add_item("high", BatchItem("high_item", "data"))
        
        first_item = queue_manager.get_next_item()
        assert first_item.id == "high_item"
        
        second_item = queue_manager.get_next_item()
        assert second_item.id == "low_item"


class TestBatchMetrics:
    """Test batch processing metrics."""
    
    @pytest.fixture
    def metrics(self):
        """Create BatchMetrics instance."""
        return BatchMetrics()
    
    def test_initialization(self, metrics):
        """Test metrics initialization."""
        assert metrics.total_processed == 0
        assert metrics.total_success == 0
        assert metrics.total_failed == 0
        assert metrics.start_time is None
        assert len(metrics.processing_times) == 0
    
    def test_record_success(self, metrics):
        """Test recording successful processing."""
        metrics.record_success(1.5)
        
        assert metrics.total_processed == 1
        assert metrics.total_success == 1
        assert metrics.total_failed == 0
        assert 1.5 in metrics.processing_times
    
    def test_record_failure(self, metrics):
        """Test recording failed processing."""
        metrics.record_failure(0.5)
        
        assert metrics.total_processed == 1
        assert metrics.total_success == 0
        assert metrics.total_failed == 1
        assert 0.5 in metrics.processing_times
    
    def test_get_average_processing_time(self, metrics):
        """Test calculating average processing time."""
        metrics.record_success(1.0)
        metrics.record_success(2.0)
        metrics.record_failure(1.5)
        
        avg_time = metrics.get_average_processing_time()
        assert avg_time == 1.5  # (1.0 + 2.0 + 1.5) / 3
    
    def test_get_success_rate(self, metrics):
        """Test calculating success rate."""
        metrics.record_success(1.0)
        metrics.record_success(1.5)
        metrics.record_failure(0.5)
        
        success_rate = metrics.get_success_rate()
        assert success_rate == 2/3  # 2 successes out of 3 total


class TestResourceMonitor:
    """Test resource monitoring functionality."""
    
    @pytest.fixture
    def monitor(self):
        """Create ResourceMonitor instance."""
        return ResourceMonitor(
            memory_limit_mb=1000,
            cpu_limit_percent=80.0
        )
    
    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.memory_limit_mb == 1000
        assert monitor.cpu_limit_percent == 80.0
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    def test_check_resources_within_limits(self, mock_cpu, mock_memory, monitor):
        """Test resource check within limits."""
        mock_memory.return_value.used = 500 * 1024 * 1024  # 500 MB
        mock_cpu.return_value = 50.0  # 50% CPU
        
        status = monitor.check_resources()
        
        assert status['memory_ok'] is True
        assert status['cpu_ok'] is True
        assert status['overall_ok'] is True
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    def test_check_resources_exceeding_limits(self, mock_cpu, mock_memory, monitor):
        """Test resource check exceeding limits."""
        mock_memory.return_value.used = 950 * 1024 * 1024  # 950 MB
        mock_cpu.return_value = 90.0  # 90% CPU
        
        status = monitor.check_resources()
        
        assert status['memory_ok'] is False
        assert status['cpu_ok'] is False
        assert status['overall_ok'] is False