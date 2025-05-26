"""Concurrency management utilities for safe parallel processing."""

import asyncio
import threading
import queue
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from collections import defaultdict
import multiprocessing as mp
from enum import Enum

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Job priority levels."""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


@dataclass
class Job:
    """Job to be executed concurrently."""
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    timeout: Optional[float] = None
    callback: Optional[Callable[[Any], None]] = None
    error_callback: Optional[Callable[[Exception], None]] = None


class ConnectionPool:
    """Thread-safe connection pool for database connections."""
    
    def __init__(self, 
                 connection_factory: Callable[[], Any],
                 max_connections: int = 10,
                 min_connections: int = 2,
                 timeout: float = 30.0):
        """Initialize connection pool.
        
        Args:
            connection_factory: Function to create new connections
            max_connections: Maximum pool size
            min_connections: Minimum pool size
            timeout: Connection acquisition timeout
        """
        self.connection_factory = connection_factory
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.timeout = timeout
        
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._all_connections: List[Any] = []
        self._lock = threading.RLock()
        self._created_connections = 0
        self._active_connections = 0
        
        # Initialize minimum connections
        self._initialize_pool()
        
        logger.info(f"Initialized connection pool with min={min_connections}, max={max_connections}")
    
    def _initialize_pool(self):
        """Create initial connections."""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")
    
    def _create_connection(self) -> Any:
        """Create a new connection."""
        with self._lock:
            if self._created_connections >= self.max_connections:
                raise RuntimeError("Connection pool exhausted")
            
            conn = self.connection_factory()
            self._all_connections.append(conn)
            self._created_connections += 1
            
            logger.debug(f"Created connection {self._created_connections}/{self.max_connections}")
            return conn
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool.
        
        Yields:
            Connection object
        """
        connection = None
        acquired_from_pool = False
        
        try:
            # Try to get from pool
            try:
                connection = self._pool.get(timeout=self.timeout)
                acquired_from_pool = True
            except queue.Empty:
                # Pool empty, try to create new connection
                with self._lock:
                    if self._created_connections < self.max_connections:
                        connection = self._create_connection()
                    else:
                        # Wait for a connection to be released
                        connection = self._pool.get(timeout=self.timeout)
                        acquired_from_pool = True
            
            with self._lock:
                self._active_connections += 1
            
            yield connection
            
        finally:
            if connection:
                with self._lock:
                    self._active_connections -= 1
                
                # Return to pool if healthy
                if acquired_from_pool or self._pool.qsize() < self.max_connections:
                    try:
                        self._pool.put_nowait(connection)
                    except queue.Full:
                        # Pool full, close connection
                        self._close_connection(connection)
    
    def _close_connection(self, connection: Any):
        """Close a connection."""
        try:
            if hasattr(connection, 'close'):
                connection.close()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    def close_all(self):
        """Close all connections in the pool."""
        # Empty the pool
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
            except queue.Empty:
                break
        
        # Close any remaining connections
        for conn in self._all_connections:
            self._close_connection(conn)
        
        self._all_connections.clear()
        self._created_connections = 0
        
        logger.info("Closed all connections in pool")
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        return {
            'created': self._created_connections,
            'active': self._active_connections,
            'available': self._pool.qsize(),
            'max': self.max_connections
        }


class FileLock:
    """File-based locking for shared resource coordination."""
    
    def __init__(self, lockfile: str, timeout: float = 30.0):
        """Initialize file lock.
        
        Args:
            lockfile: Path to lock file
            timeout: Lock acquisition timeout
        """
        self.lockfile = lockfile
        self.timeout = timeout
        self._lock_acquired = False
        self._lock_file = None
    
    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the lock.
        
        Args:
            blocking: Whether to block waiting for lock
            
        Returns:
            True if lock acquired
        """
        import fcntl
        import errno
        
        start_time = time.time()
        
        while True:
            try:
                self._lock_file = open(self.lockfile, 'w')
                fcntl.flock(self._lock_file.fileno(), 
                          fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
                self._lock_acquired = True
                return True
                
            except IOError as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                
                if not blocking:
                    return False
                
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Failed to acquire lock after {self.timeout}s")
                
                time.sleep(0.1)
    
    def release(self):
        """Release the lock."""
        if self._lock_acquired and self._lock_file:
            import fcntl
            
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
            finally:
                self._lock_acquired = False
                self._lock_file = None
    
    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


class JobQueue:
    """Priority job queue with concurrent execution."""
    
    def __init__(self, 
                 max_workers: int = 4,
                 max_queue_size: int = 1000):
        """Initialize job queue.
        
        Args:
            max_workers: Maximum concurrent workers
            max_queue_size: Maximum queue size
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        self._queue = queue.PriorityQueue(maxsize=max_queue_size)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: Dict[str, Future] = {}
        self._running = False
        self._workers = []
        self._lock = threading.Lock()
        
        # Job statistics
        self._submitted_count = 0
        self._completed_count = 0
        self._failed_count = 0
        
        logger.info(f"Initialized job queue with {max_workers} workers")
    
    def start(self):
        """Start the job queue workers."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, name=f"JobWorker-{i}")
            worker.daemon = True
            worker.start()
            self._workers.append(worker)
        
        logger.info("Started job queue workers")
    
    def stop(self, wait: bool = True):
        """Stop the job queue.
        
        Args:
            wait: Whether to wait for pending jobs
        """
        self._running = False
        
        if wait:
            # Wait for queue to empty
            self._queue.join()
        
        # Stop executor
        self._executor.shutdown(wait=wait)
        
        logger.info("Stopped job queue")
    
    def submit(self, job: Job) -> str:
        """Submit a job to the queue.
        
        Args:
            job: Job to execute
            
        Returns:
            Job ID
        """
        # Priority queue uses negative priority for max heap
        priority_value = -job.priority.value
        self._queue.put((priority_value, time.time(), job))
        
        with self._lock:
            self._submitted_count += 1
        
        logger.debug(f"Submitted job {job.id} with priority {job.priority.name}")
        return job.id
    
    def _worker(self):
        """Worker thread for processing jobs."""
        while self._running:
            try:
                # Get job from queue
                priority, timestamp, job = self._queue.get(timeout=1.0)
                
                # Execute job
                self._execute_job(job)
                
                # Mark task as done
                self._queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _execute_job(self, job: Job):
        """Execute a single job."""
        logger.debug(f"Executing job {job.id}")
        
        try:
            # Submit to executor
            future = self._executor.submit(job.func, *job.args, **job.kwargs)
            
            with self._lock:
                self._futures[job.id] = future
            
            # Wait for completion with timeout
            result = future.result(timeout=job.timeout)
            
            # Call success callback
            if job.callback:
                try:
                    job.callback(result)
                except Exception as e:
                    logger.error(f"Error in job callback: {e}")
            
            with self._lock:
                self._completed_count += 1
                del self._futures[job.id]
            
            logger.debug(f"Completed job {job.id}")
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            
            # Call error callback
            if job.error_callback:
                try:
                    job.error_callback(e)
                except Exception as cb_error:
                    logger.error(f"Error in error callback: {cb_error}")
            
            with self._lock:
                self._failed_count += 1
                if job.id in self._futures:
                    del self._futures[job.id]
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: ID of job to cancel
            
        Returns:
            True if cancelled
        """
        with self._lock:
            if job_id in self._futures:
                future = self._futures[job_id]
                cancelled = future.cancel()
                if cancelled:
                    del self._futures[job_id]
                return cancelled
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        with self._lock:
            return {
                'submitted': self._submitted_count,
                'completed': self._completed_count,
                'failed': self._failed_count,
                'pending': self._queue.qsize(),
                'running': len(self._futures)
            }


class AsyncProviderWrapper:
    """Wrapper to make synchronous providers async-compatible."""
    
    def __init__(self, provider: Any):
        """Initialize async wrapper.
        
        Args:
            provider: Synchronous provider instance
        """
        self.provider = provider
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self._executor.shutdown(wait=False)
    
    async def _run_in_executor(self, func: Callable, *args, **kwargs) -> Any:
        """Run synchronous function in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            func,
            *args,
            **kwargs
        )
    
    def __getattr__(self, name: str) -> Callable:
        """Wrap provider methods to be async."""
        attr = getattr(self.provider, name)
        
        if callable(attr):
            async def async_wrapper(*args, **kwargs):
                return await self._run_in_executor(attr, *args, **kwargs)
            return async_wrapper
        
        return attr


class DeadlockDetector:
    """Detector for potential deadlocks in concurrent operations."""
    
    def __init__(self, check_interval: float = 5.0):
        """Initialize deadlock detector.
        
        Args:
            check_interval: Interval between deadlock checks
        """
        self.check_interval = check_interval
        self._resources: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._running = False
        self._checker_thread = None
    
    def start(self):
        """Start deadlock detection."""
        if self._running:
            return
        
        self._running = True
        self._checker_thread = threading.Thread(target=self._check_loop)
        self._checker_thread.daemon = True
        self._checker_thread.start()
        
        logger.info("Started deadlock detector")
    
    def stop(self):
        """Stop deadlock detection."""
        self._running = False
        if self._checker_thread:
            self._checker_thread.join()
        
        logger.info("Stopped deadlock detector")
    
    def register_acquisition(self, thread_id: str, resource_id: str):
        """Register resource acquisition by thread."""
        with self._lock:
            self._resources[thread_id][resource_id] = {
                'acquired_at': time.time(),
                'thread_name': threading.current_thread().name
            }
    
    def register_release(self, thread_id: str, resource_id: str):
        """Register resource release by thread."""
        with self._lock:
            if thread_id in self._resources:
                self._resources[thread_id].pop(resource_id, None)
                if not self._resources[thread_id]:
                    del self._resources[thread_id]
    
    def _check_loop(self):
        """Main deadlock detection loop."""
        while self._running:
            try:
                self._check_for_deadlocks()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in deadlock detection: {e}")
    
    def _check_for_deadlocks(self):
        """Check for potential deadlocks."""
        with self._lock:
            # Check for long-held resources
            current_time = time.time()
            long_held_threshold = 30.0  # 30 seconds
            
            for thread_id, resources in self._resources.items():
                for resource_id, info in resources.items():
                    held_duration = current_time - info['acquired_at']
                    
                    if held_duration > long_held_threshold:
                        logger.warning(
                            f"Potential deadlock: Thread {info['thread_name']} "
                            f"has held resource {resource_id} for {held_duration:.1f}s"
                        )
            
            # Could implement more sophisticated cycle detection here


async def run_async_jobs(jobs: List[Tuple[Callable, tuple, dict]]) -> List[Any]:
    """Run multiple async jobs concurrently.
    
    Args:
        jobs: List of (func, args, kwargs) tuples
        
    Returns:
        List of results
    """
    async def run_job(func, args, kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    tasks = [run_job(func, args, kwargs) for func, args, kwargs in jobs]
    return await asyncio.gather(*tasks, return_exceptions=True)


def synchronized(lock: threading.Lock):
    """Decorator for synchronized method execution.
    
    Args:
        lock: Lock to use for synchronization
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper
    return decorator