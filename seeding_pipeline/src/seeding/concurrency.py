"""Simplified concurrency management for VTT processing.

Provides basic thread pool functionality for parallel VTT file processing.
Removed complex job queuing, deadlock detection, and priority systems as part of Phase 3.3.2.
"""

from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from typing import Any, Callable, List, Optional
import logging
import threading
logger = logging.getLogger(__name__)


class SimpleThreadPool:
    """Basic thread pool for VTT processing tasks."""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        
    def start(self):
        """Start the thread pool."""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
                logger.info(f"Started thread pool with {self.max_workers} workers")
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool."""
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=wait)
                self._executor = None
                logger.info("Thread pool shutdown complete")
    
    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """
        Submit a task to the thread pool.
        
        Args:
            fn: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Future representing the task execution
        """
        if self._executor is None:
            self.start()
        
        return self._executor.submit(fn, *args, **kwargs)
    
    def map(self, fn: Callable, iterable) -> List[Any]:
        """
        Map a function over an iterable using the thread pool.
        
        Args:
            fn: Function to apply
            iterable: Items to process
            
        Returns:
            List of results
        """
        if self._executor is None:
            self.start()
        
        futures = [self._executor.submit(fn, item) for item in iterable]
        return [future.result() for future in futures]
    
    @contextmanager
    def batch_context(self):
        """Context manager for batch processing."""
        self.start()
        try:
            yield self
        finally:
            # Don't shutdown automatically - let caller control lifecycle
            pass


# Global thread pool instance for VTT processing
_vtt_thread_pool: Optional[SimpleThreadPool] = None


def get_vtt_thread_pool(max_workers: int = 4) -> SimpleThreadPool:
    """
    Get the global VTT processing thread pool.
    
    Args:
        max_workers: Maximum number of worker threads
        
    Returns:
        Global thread pool instance
    """
    global _vtt_thread_pool
    
    if _vtt_thread_pool is None:
        _vtt_thread_pool = SimpleThreadPool(max_workers)
    
    return _vtt_thread_pool


def cleanup_vtt_thread_pool():
    """Clean up the global thread pool."""
    global _vtt_thread_pool
    
    if _vtt_thread_pool is not None:
        _vtt_thread_pool.shutdown()
        _vtt_thread_pool = None


def process_vtt_files_parallel(vtt_files: List[Any], 
                              processor_func: Callable,
                              max_workers: int = 4) -> List[Any]:
    """
    Process VTT files in parallel using the simplified thread pool.
    
    Args:
        vtt_files: List of VTT files to process
        processor_func: Function to process each VTT file
        max_workers: Maximum number of worker threads
        
    Returns:
        List of processing results
    """
    pool = get_vtt_thread_pool(max_workers)
    
    with pool.batch_context():
        return pool.map(processor_func, vtt_files)


# Backward compatibility aliases for existing code
ThreadPoolManager = SimpleThreadPool  # Legacy alias
ConcurrencyManager = SimpleThreadPool  # Legacy alias