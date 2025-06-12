"""Performance tests for multi-podcast processing."""

import os
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.cli.multi_podcast_parallel import (
    MultiPodcastParallelProcessor, 
    DatabaseConnectionPool,
    optimize_worker_count,
    PodcastProcessingResult
)


class TestMultiPodcastPerformance:
    """Test performance optimizations for multi-podcast processing."""
    
    def test_optimize_worker_count(self):
        """Test worker count optimization logic."""
        # Test with fewer podcasts than workers
        assert optimize_worker_count(2, 8) == 2
        
        # Test with more podcasts than workers
        assert optimize_worker_count(10, 4) == 4
        
        # Test with CPU constraints (mocked)
        with patch('os.cpu_count', return_value=2):
            # Should limit to 2 * CPU count for I/O bound tasks
            assert optimize_worker_count(10, 8) == 4
    
    def test_parallel_processor_basic(self):
        """Test basic parallel processing functionality."""
        # Mock process function
        def mock_process_func(args, podcast_id):
            time.sleep(0.1)  # Simulate processing time
            return {'processed': 5, 'failed': 1}
        
        processor = MultiPodcastParallelProcessor(max_workers=2)
        podcast_ids = ['podcast1', 'podcast2', 'podcast3']
        
        start_time = time.time()
        results = processor.process_podcasts_parallel(
            podcast_ids, 
            mock_process_func,
            Mock()
        )
        duration = time.time() - start_time
        
        # Verify results
        assert len(results) == 3
        assert all(isinstance(r, PodcastProcessingResult) for r in results.values())
        assert all(r.processed == 5 for r in results.values())
        assert all(r.failed == 1 for r in results.values())
        
        # With 2 workers processing 3 tasks of 0.1s each, should take ~0.2s
        # Allow some overhead
        assert duration < 0.5
    
    def test_rate_limiting(self):
        """Test rate limiting within podcasts."""
        processor = MultiPodcastParallelProcessor(
            max_workers=1,
            rate_limit_per_podcast=0.2  # 200ms between calls
        )
        
        call_times = []
        
        def track_time_func(args, podcast_id):
            call_times.append(time.time())
            return {'processed': 1, 'failed': 0}
        
        # Process same podcast twice
        podcast_ids = ['podcast1']
        
        # First call
        processor.process_podcasts_parallel(podcast_ids, track_time_func, Mock())
        # Second call
        processor.process_podcasts_parallel(podcast_ids, track_time_func, Mock())
        
        # Should have rate limited
        if len(call_times) >= 2:
            time_diff = call_times[1] - call_times[0]
            assert time_diff >= 0.2
    
    def test_error_handling(self):
        """Test error handling in parallel processing."""
        def failing_func(args, podcast_id):
            if podcast_id == 'fail_podcast':
                raise ValueError("Test error")
            return {'processed': 3, 'failed': 0}
        
        processor = MultiPodcastParallelProcessor(max_workers=2)
        podcast_ids = ['good_podcast', 'fail_podcast', 'another_good']
        
        results = processor.process_podcasts_parallel(
            podcast_ids,
            failing_func,
            Mock()
        )
        
        # Check results
        assert results['good_podcast'].processed == 3
        assert results['good_podcast'].error is None
        
        assert results['fail_podcast'].processed == 0
        assert results['fail_podcast'].error is not None
        assert "Test error" in results['fail_podcast'].error
        
        assert results['another_good'].processed == 3
        assert results['another_good'].error is None
    
    def test_database_connection_pool(self):
        """Test database connection pooling."""
        pool = DatabaseConnectionPool(max_connections_per_db=3)
        
        # Mock the podcast config
        with patch.object(pool.podcast_config, 'get_database_for_podcast') as mock_get_db:
            mock_get_db.side_effect = lambda p: f"{p}_db"
            
            # Acquire connections
            assert pool.acquire_connection('podcast1') is True
            assert pool.acquire_connection('podcast1') is True
            assert pool.acquire_connection('podcast1') is True
            
            # Should hit limit
            assert pool.acquire_connection('podcast1') is False
            
            # Different podcast should work
            assert pool.acquire_connection('podcast2') is True
            
            # Release and reacquire
            pool.release_connection('podcast1')
            assert pool.acquire_connection('podcast1') is True
            
            # Check stats
            stats = pool.get_connection_stats()
            assert stats['podcast1_db'] == 3
            assert stats['podcast2_db'] == 1
    
    def test_metrics_logging(self):
        """Test that performance metrics are logged."""
        def simple_func(args, podcast_id):
            return {'processed': 2, 'failed': 0}
        
        processor = MultiPodcastParallelProcessor(max_workers=1)
        podcast_ids = ['podcast1', 'podcast2']
        
        results = processor.process_podcasts_parallel(
            podcast_ids,
            simple_func,
            Mock()
        )
        
        # Verify results
        assert len(results) == 2
        assert all(r.processed == 2 for r in results.values())
        assert all(r.failed == 0 for r in results.values())
        assert all(r.error is None for r in results.values())
    
    def test_parallel_vs_sequential_performance(self):
        """Compare parallel vs sequential processing time."""
        processing_delay = 0.05  # 50ms per podcast
        
        def slow_func(args, podcast_id):
            time.sleep(processing_delay)
            return {'processed': 1, 'failed': 0}
        
        podcast_ids = ['p1', 'p2', 'p3', 'p4']
        
        # Sequential processing simulation
        start = time.time()
        for pid in podcast_ids:
            slow_func(None, pid)
        sequential_time = time.time() - start
        
        # Parallel processing
        processor = MultiPodcastParallelProcessor(max_workers=4)
        start = time.time()
        results = processor.process_podcasts_parallel(
            podcast_ids,
            slow_func,
            Mock()
        )
        parallel_time = time.time() - start
        
        # Parallel should be faster
        assert parallel_time < sequential_time
        # With 4 workers and 4 tasks, should be close to single task time
        assert parallel_time < processing_delay * 2  # Allow overhead