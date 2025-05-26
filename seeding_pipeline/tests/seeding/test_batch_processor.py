"""Tests for batch processing utilities."""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from src.seeding.batch_processor import (
    BatchItem,
    BatchResult,
    BatchProcessor,
    PriorityBatchProcessor,
    create_batch_items,
    batch_with_timeout
)


class TestBatchItem:
    """Tests for BatchItem dataclass."""
    
    def test_batch_item_creation(self):
        """Test creating batch item."""
        item = BatchItem(id='item1', data={'key': 'value'}, priority=5)
        assert item.id == 'item1'
        assert item.data == {'key': 'value'}
        assert item.priority == 5
        assert item.metadata is None
    
    def test_batch_item_with_metadata(self):
        """Test batch item with metadata."""
        metadata = {'source': 'test', 'timestamp': '2023-01-01'}
        item = BatchItem(id='item1', data='data', metadata=metadata)
        assert item.metadata == metadata


class TestBatchResult:
    """Tests for BatchResult dataclass."""
    
    def test_successful_result(self):
        """Test successful batch result."""
        result = BatchResult(
            item_id='item1',
            success=True,
            result={'processed': 'data'},
            processing_time=1.5
        )
        assert result.item_id == 'item1'
        assert result.success is True
        assert result.result == {'processed': 'data'}
        assert result.error is None
        assert result.processing_time == 1.5
    
    def test_failed_result(self):
        """Test failed batch result."""
        result = BatchResult(
            item_id='item1',
            success=False,
            error='Processing failed'
        )
        assert result.success is False
        assert result.error == 'Processing failed'
        assert result.result is None


class TestBatchProcessor:
    """Tests for BatchProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create batch processor instance."""
        return BatchProcessor(
            max_workers=2,
            batch_size=3,
            use_processes=False
        )
    
    def test_initialization(self, processor):
        """Test processor initialization."""
        assert processor.max_workers == 2
        assert processor.batch_size == 3
        assert processor.use_processes is False
        assert processor._optimal_batch_size == 3
    
    def test_process_empty_items(self, processor):
        """Test processing empty item list."""
        results = processor.process_items([], lambda x: x)
        assert results == []
    
    def test_process_individual_items(self, processor):
        """Test processing items individually."""
        items = [
            BatchItem(id='1', data=1),
            BatchItem(id='2', data=2),
            BatchItem(id='3', data=3)
        ]
        
        def process_func(item):
            return item.data * 2
        
        results = processor.process_items(items, process_func)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        
        # Check results
        result_map = {r.item_id: r.result for r in results}
        assert result_map['1'] == 2
        assert result_map['2'] == 4
        assert result_map['3'] == 6
    
    def test_process_with_priorities(self, processor):
        """Test processing respects priorities."""
        items = [
            BatchItem(id='low', data=1, priority=1),
            BatchItem(id='high', data=2, priority=10),
            BatchItem(id='medium', data=3, priority=5)
        ]
        
        processed_order = []
        
        def process_func(item):
            processed_order.append(item.id)
            return item.data
        
        processor.process_items(items, process_func)
        
        # High priority should be processed first
        assert processed_order[0] == 'high'
    
    def test_process_with_errors(self, processor):
        """Test handling of processing errors."""
        items = [
            BatchItem(id='1', data=1),
            BatchItem(id='2', data='invalid'),
            BatchItem(id='3', data=3)
        ]
        
        def process_func(item):
            if isinstance(item.data, str):
                raise ValueError("Invalid data type")
            return item.data * 2
        
        results = processor.process_items(items, process_func)
        
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert 'Invalid data type' in results[1].error
        assert results[2].success is True
    
    def test_batch_creation(self, processor):
        """Test batch creation with optimization."""
        items = [BatchItem(id=str(i), data=i) for i in range(10)]
        
        batches = processor._create_batches(items)
        
        assert len(batches) == 4  # 10 items with batch_size=3
        assert len(batches[0]) == 3
        assert len(batches[-1]) == 1  # Last batch has remainder
    
    def test_progress_callback(self):
        """Test progress callback functionality."""
        progress_updates = []
        
        def progress_callback(current, total):
            progress_updates.append((current, total))
        
        processor = BatchProcessor(
            max_workers=1,
            progress_callback=progress_callback
        )
        
        items = [BatchItem(id=str(i), data=i) for i in range(5)]
        processor.process_items(items, lambda x: x.data)
        
        assert len(progress_updates) > 0
        assert progress_updates[-1][0] == 5  # All items processed
    
    @patch('src.seeding.batch_processor.psutil')
    def test_memory_limit(self, mock_psutil):
        """Test memory limit enforcement."""
        # Mock memory usage
        mock_memory = Mock()
        mock_memory.used = 900 * 1024 * 1024  # 900 MB
        mock_psutil.virtual_memory.return_value = mock_memory
        
        processor = BatchProcessor(
            batch_size=10,
            memory_limit_mb=1000  # 1 GB limit
        )
        
        items = [BatchItem(id=str(i), data=i) for i in range(20)]
        batches = processor._create_batches(items)
        
        # Should reduce batch size due to memory limit
        assert processor._optimal_batch_size < 10
    
    def test_batch_function_processing(self, processor):
        """Test processing with batch function."""
        items = [
            BatchItem(id='1', data=[1, 2, 3]),
            BatchItem(id='2', data=[4, 5, 6]),
            BatchItem(id='3', data=[7, 8, 9])
        ]
        
        def batch_func(batch_items):
            # Process entire batch at once
            return [sum(item.data) for item in batch_items]
        
        results = processor.process_items(items, None, batch_func)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        
        result_map = {r.item_id: r.result for r in results}
        assert result_map['1'] == 6  # sum([1,2,3])
        assert result_map['2'] == 15  # sum([4,5,6])
        assert result_map['3'] == 24  # sum([7,8,9])
    
    def test_statistics(self, processor):
        """Test statistics collection."""
        items = [BatchItem(id=str(i), data=i) for i in range(5)]
        processor.process_items(items, lambda x: x.data)
        
        stats = processor.get_statistics()
        
        assert stats['items_processed'] == 5
        assert stats['total_items'] == 5
        assert stats['elapsed_time'] > 0
        assert stats['average_rate'] > 0
        assert stats['optimal_batch_size'] > 0
        assert stats['worker_count'] == 2


class TestPriorityBatchProcessor:
    """Tests for PriorityBatchProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create priority processor instance."""
        return PriorityBatchProcessor(
            max_workers=2,
            batch_size=2
        )
    
    def test_start_stop(self, processor):
        """Test starting and stopping processor."""
        processor.start()
        assert processor._processing is True
        assert processor._worker_thread is not None
        assert processor._worker_thread.is_alive()
        
        processor.stop()
        assert processor._processing is False
    
    def test_add_items(self, processor):
        """Test adding items to priority queue."""
        processor.add_item(BatchItem(id='1', data='data1', priority=5))
        processor.add_item(BatchItem(id='2', data='data2', priority=10))
        
        assert not processor._priority_queue.empty()
        
        # Get items (highest priority first)
        priority1, item1 = processor._priority_queue.get()
        assert item1.id == '2'  # Higher priority
        
        priority2, item2 = processor._priority_queue.get()
        assert item2.id == '1'  # Lower priority


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_create_batch_items_default(self):
        """Test creating batch items with defaults."""
        data_list = ['a', 'b', 'c']
        items = create_batch_items(data_list)
        
        assert len(items) == 3
        assert items[0].id == '0'
        assert items[0].data == 'a'
        assert items[0].priority == 0
    
    def test_create_batch_items_custom(self):
        """Test creating batch items with custom functions."""
        data_list = [
            {'id': 'doc1', 'size': 100},
            {'id': 'doc2', 'size': 200}
        ]
        
        items = create_batch_items(
            data_list,
            id_func=lambda x: x['id'],
            priority_func=lambda x: x['size']
        )
        
        assert items[0].id == 'doc1'
        assert items[0].priority == 100
        assert items[1].id == 'doc2'
        assert items[1].priority == 200
    
    def test_batch_with_timeout(self):
        """Test batch processing with timeout."""
        def slow_process(x):
            if x == 2:
                time.sleep(0.5)  # Simulate slow processing
            return x * 2
        
        items = [1, 2, 3]
        results = batch_with_timeout(
            items,
            slow_process,
            timeout_seconds=0.3,
            max_workers=2
        )
        
        assert len(results) == 3
        assert results[0] == 2  # 1 * 2
        # results[1] might be None due to timeout
        assert results[2] == 6  # 3 * 2


class TestBatchOptimization:
    """Tests for batch size optimization."""
    
    def test_batch_performance_recording(self):
        """Test recording of batch performance."""
        processor = BatchProcessor(batch_size=5)
        
        # Record some performance data
        processor._record_batch_performance(5, 1.0)  # 5 items/sec
        processor._record_batch_performance(10, 1.0)  # 10 items/sec
        processor._record_batch_performance(10, 1.0)  # 10 items/sec
        
        assert len(processor._batch_performance_history) == 3
    
    def test_batch_size_optimization(self):
        """Test batch size optimization based on performance."""
        processor = BatchProcessor(batch_size=5)
        
        # Simulate better performance with larger batches
        for _ in range(10):
            processor._record_batch_performance(5, 1.0)  # 5 items/sec
        for _ in range(10):
            processor._record_batch_performance(10, 0.5)  # 20 items/sec
        
        # Should increase optimal batch size
        assert processor._optimal_batch_size > 5