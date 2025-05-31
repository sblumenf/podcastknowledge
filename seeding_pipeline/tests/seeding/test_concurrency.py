"""Tests for concurrency management utilities."""

from unittest.mock import Mock, patch, MagicMock
import asyncio
import os
import tempfile
import threading
import time

import pytest

from src.seeding.concurrency import (
    Priority,
    Job,
    ConnectionPool,
    FileLock,
    JobQueue,
    AsyncProviderWrapper,
    DeadlockDetector,
    run_async_jobs,
    synchronized
)


class TestConnectionPool:
    """Tests for ConnectionPool class."""
    
    def test_initialization(self):
        """Test connection pool initialization."""
        connection_count = 0
        
        def mock_connection_factory():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(
            mock_connection_factory,
            max_connections=5,
            min_connections=2
        )
        
        # Should create min_connections initially
        assert connection_count == 2
        assert pool.get_stats()['created'] == 2
        assert pool.get_stats()['available'] == 2
    
    def test_get_connection(self):
        """Test getting connections from pool."""
        connections_created = []
        
        def mock_factory():
            conn = Mock()
            conn.id = len(connections_created)
            connections_created.append(conn)
            return conn
        
        pool = ConnectionPool(mock_factory, max_connections=3, min_connections=1)
        
        # Get connection
        with pool.get_connection() as conn1:
            assert conn1 is not None
            assert pool.get_stats()['active'] == 1
        
        # Connection should be returned to pool
        assert pool.get_stats()['active'] == 0
        assert pool.get_stats()['available'] >= 1
    
    def test_concurrent_connections(self):
        """Test concurrent connection usage."""
        pool = ConnectionPool(
            lambda: Mock(),
            max_connections=3,
            min_connections=0
        )
        
        connections = []
        
        def get_connection():
            with pool.get_connection() as conn:
                connections.append(conn)
                time.sleep(0.1)  # Hold connection briefly
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=get_connection)
            t.start()
            threads.append(t)
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should have used up to max_connections
        assert len(set(connections)) <= 3
    
    def test_connection_exhaustion(self):
        """Test behavior when pool is exhausted."""
        pool = ConnectionPool(
            lambda: Mock(),
            max_connections=1,
            min_connections=0,
            timeout=0.1
        )
        
        # Hold a connection
        with pool.get_connection() as conn1:
            # Try to get another connection
            with pytest.raises(Exception):  # Should timeout
                with pool.get_connection() as conn2:
                    pass
    
    def test_close_all(self):
        """Test closing all connections."""
        closed_connections = []
        
        def mock_factory():
            conn = Mock()
            conn.close = Mock(side_effect=lambda: closed_connections.append(conn))
            return conn
        
        pool = ConnectionPool(mock_factory, max_connections=3, min_connections=2)
        
        # Get and return a connection
        with pool.get_connection():
            pass
        
        pool.close_all()
        
        # All connections should be closed
        assert len(closed_connections) >= 2


class TestFileLock:
    """Tests for FileLock class."""
    
    def test_acquire_release(self):
        """Test basic lock acquisition and release."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            lockfile = tmp.name
        
        try:
            lock = FileLock(lockfile)
            
            # Acquire lock
            assert lock.acquire()
            assert lock._lock_acquired is True
            
            # Release lock
            lock.release()
            assert lock._lock_acquired is False
            
        finally:
            os.unlink(lockfile)
    
    def test_context_manager(self):
        """Test file lock as context manager."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            lockfile = tmp.name
        
        try:
            with FileLock(lockfile) as lock:
                assert lock._lock_acquired is True
            
            # Lock should be released
            assert lock._lock_acquired is False
            
        finally:
            os.unlink(lockfile)
    
    def test_non_blocking_acquire(self):
        """Test non-blocking lock acquisition."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            lockfile = tmp.name
        
        try:
            lock1 = FileLock(lockfile)
            lock2 = FileLock(lockfile)
            
            # First lock succeeds
            assert lock1.acquire()
            
            # Second lock fails (non-blocking)
            assert not lock2.acquire(blocking=False)
            
            lock1.release()
            
        finally:
            os.unlink(lockfile)
    
    def test_timeout(self):
        """Test lock acquisition timeout."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            lockfile = tmp.name
        
        try:
            lock1 = FileLock(lockfile, timeout=0.1)
            lock2 = FileLock(lockfile, timeout=0.1)
            
            lock1.acquire()
            
            # Second lock should timeout
            with pytest.raises(TimeoutError):
                lock2.acquire()
            
            lock1.release()
            
        finally:
            os.unlink(lockfile)


class TestJob:
    """Tests for Job dataclass."""
    
    def test_job_creation(self):
        """Test creating a job."""
        def test_func(x, y):
            return x + y
        
        job = Job(
            id='job1',
            func=test_func,
            args=(1, 2),
            priority=Priority.HIGH
        )
        
        assert job.id == 'job1'
        assert job.func == test_func
        assert job.args == (1, 2)
        assert job.priority == Priority.HIGH


class TestJobQueue:
    """Tests for JobQueue class."""
    
    @pytest.fixture
    def job_queue(self):
        """Create job queue instance."""
        queue = JobQueue(max_workers=2)
        queue.start()
        yield queue
        queue.stop(wait=False)
    
    def test_submit_job(self, job_queue):
        """Test submitting and executing a job."""
        result_holder = {'result': None}
        
        def test_func(x):
            result_holder['result'] = x * 2
            return x * 2
        
        job = Job(id='test1', func=test_func, args=(5,))
        job_id = job_queue.submit(job)
        
        assert job_id == 'test1'
        
        # Wait for job to complete
        time.sleep(0.2)
        
        assert result_holder['result'] == 10
        
        stats = job_queue.get_stats()
        assert stats['completed'] >= 1
    
    def test_priority_execution(self, job_queue):
        """Test jobs are executed by priority."""
        execution_order = []
        
        def test_func(job_id):
            execution_order.append(job_id)
            time.sleep(0.1)
        
        # Submit jobs with different priorities
        jobs = [
            Job(id='low', func=test_func, args=('low',), priority=Priority.LOW),
            Job(id='critical', func=test_func, args=('critical',), priority=Priority.CRITICAL),
            Job(id='normal', func=test_func, args=('normal',), priority=Priority.NORMAL),
            Job(id='high', func=test_func, args=('high',), priority=Priority.HIGH),
        ]
        
        for job in jobs:
            job_queue.submit(job)
        
        # Wait for all jobs to complete
        time.sleep(0.5)
        
        # Critical and high priority should be executed first
        assert execution_order[0] in ['critical', 'high']
    
    def test_job_callback(self, job_queue):
        """Test job success callback."""
        callback_result = {'value': None}
        
        def test_func():
            return 42
        
        def callback(result):
            callback_result['value'] = result
        
        job = Job(id='test', func=test_func, callback=callback)
        job_queue.submit(job)
        
        time.sleep(0.2)
        
        assert callback_result['value'] == 42
    
    def test_job_error_callback(self, job_queue):
        """Test job error callback."""
        error_result = {'error': None}
        
        def test_func():
            raise ValueError("Test error")
        
        def error_callback(error):
            error_result['error'] = str(error)
        
        job = Job(id='test', func=test_func, error_callback=error_callback)
        job_queue.submit(job)
        
        time.sleep(0.2)
        
        assert "Test error" in error_result['error']
        
        stats = job_queue.get_stats()
        assert stats['failed'] >= 1
    
    def test_job_timeout(self, job_queue):
        """Test job timeout."""
        def slow_func():
            time.sleep(1.0)
            return "completed"
        
        job = Job(id='test', func=slow_func, timeout=0.1)
        job_queue.submit(job)
        
        time.sleep(0.3)
        
        stats = job_queue.get_stats()
        assert stats['failed'] >= 1


class TestAsyncProviderWrapper:
    """Tests for AsyncProviderWrapper."""
    
    def test_wrap_sync_method(self):
        """Test wrapping synchronous methods."""
        mock_provider = Mock()
        mock_provider.process = Mock(return_value="result")
        
        wrapper = AsyncProviderWrapper(mock_provider)
        
        # Get async version of method
        async_process = wrapper.process
        assert asyncio.iscoroutinefunction(async_process)
    
    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Test async execution of wrapped method."""
        mock_provider = Mock()
        mock_provider.process = Mock(return_value="processed")
        
        async with AsyncProviderWrapper(mock_provider) as wrapper:
            result = await wrapper.process("input")
            assert result == "processed"
            mock_provider.process.assert_called_once_with("input")
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(self):
        """Test multiple concurrent calls."""
        call_count = 0
        
        def slow_process(x):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)
            return x * 2
        
        mock_provider = Mock()
        mock_provider.process = slow_process
        
        async with AsyncProviderWrapper(mock_provider) as wrapper:
            # Run multiple calls concurrently
            results = await asyncio.gather(
                wrapper.process(1),
                wrapper.process(2),
                wrapper.process(3)
            )
            
            assert results == [2, 4, 6]
            assert call_count == 3


class TestDeadlockDetector:
    """Tests for DeadlockDetector."""
    
    def test_initialization(self):
        """Test deadlock detector initialization."""
        detector = DeadlockDetector(check_interval=1.0)
        detector.start()
        
        assert detector._running is True
        assert detector._checker_thread is not None
        
        detector.stop()
        assert detector._running is False
    
    def test_resource_tracking(self):
        """Test resource acquisition and release tracking."""
        detector = DeadlockDetector()
        
        thread_id = "thread1"
        resource_id = "resource1"
        
        detector.register_acquisition(thread_id, resource_id)
        assert thread_id in detector._resources
        assert resource_id in detector._resources[thread_id]
        
        detector.register_release(thread_id, resource_id)
        assert thread_id not in detector._resources
    
    @patch('src.seeding.concurrency.logger')
    def test_deadlock_detection(self, mock_logger):
        """Test detection of long-held resources."""
        detector = DeadlockDetector(check_interval=0.1)
        
        # Register a resource acquisition
        detector.register_acquisition("thread1", "resource1")
        
        # Modify acquisition time to simulate long hold
        with detector._lock:
            detector._resources["thread1"]["resource1"]["acquired_at"] = time.time() - 35
        
        # Run detection
        detector._check_for_deadlocks()
        
        # Should log warning
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Potential deadlock" in warning_msg


class TestHelperFunctions:
    """Tests for helper functions."""
    
    @pytest.mark.asyncio
    async def test_run_async_jobs(self):
        """Test running multiple async jobs."""
        async def async_func(x):
            await asyncio.sleep(0.1)
            return x * 2
        
        def sync_func(x):
            return x + 1
        
        jobs = [
            (async_func, (1,), {}),
            (sync_func, (2,), {}),
            (async_func, (3,), {})
        ]
        
        results = await run_async_jobs(jobs)
        assert results == [2, 3, 6]
    
    @pytest.mark.asyncio
    async def test_run_async_jobs_with_exceptions(self):
        """Test handling exceptions in async jobs."""
        async def failing_func():
            raise ValueError("Test error")
        
        def working_func():
            return "success"
        
        jobs = [
            (working_func, (), {}),
            (failing_func, (), {}),
            (working_func, (), {})
        ]
        
        results = await run_async_jobs(jobs)
        
        assert results[0] == "success"
        assert isinstance(results[1], ValueError)
        assert results[2] == "success"
    
    def test_synchronized_decorator(self):
        """Test synchronized decorator."""
        lock = threading.Lock()
        counter = {'value': 0}
        
        @synchronized(lock)
        def increment():
            # Simulate race condition scenario
            current = counter['value']
            time.sleep(0.001)  # Small delay
            counter['value'] = current + 1
        
        # Run multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # Should be exactly 10 due to synchronization
        assert counter['value'] == 10