"""Memory management utilities for efficient resource handling."""

import gc
import functools
import warnings
from contextlib import contextmanager
from typing import Optional, Callable, Any, Dict
import logging

# Optional imports
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None


logger = logging.getLogger(__name__)


def cleanup_memory() -> None:
    """Clean up memory after processing operations.
    
    This function performs garbage collection and clears various caches
    including GPU memory and matplotlib figures.
    """
    # Force garbage collection
    gc.collect()
    
    # Clear GPU memory if available
    if HAS_TORCH and torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("GPU memory cleared")
    
    # Clear matplotlib figures if available
    if HAS_MATPLOTLIB:
        plt.close('all')
        logger.debug("Matplotlib figures cleared")
    
    # Force another garbage collection
    gc.collect()
    logger.debug("Memory cleanup completed")


def monitor_memory() -> Dict[str, Any]:
    """Monitor current memory usage.
    
    Returns:
        Dict containing memory usage statistics
    """
    stats = {}
    
    if HAS_PSUTIL:
        try:
            memory = psutil.virtual_memory()
            stats['cpu_memory'] = {
                'percent': memory.percent,
                'used_gb': memory.used / (1024**3),
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3)
            }
            
            logger.info(f"Memory usage: {memory.percent:.1f}% "
                       f"({stats['cpu_memory']['used_gb']:.1f}GB / "
                       f"{stats['cpu_memory']['total_gb']:.1f}GB)")
            
        except Exception as e:
            logger.error(f"Error monitoring CPU memory: {e}")
    else:
        logger.warning("psutil not available for memory monitoring")
    
    # GPU memory monitoring
    if HAS_TORCH and torch.cuda.is_available():
        try:
            gpu_memory = torch.cuda.memory_allocated() / (1024**3)
            gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            gpu_reserved = torch.cuda.memory_reserved() / (1024**3)
            
            stats['gpu_memory'] = {
                'allocated_gb': gpu_memory,
                'reserved_gb': gpu_reserved,
                'total_gb': gpu_total,
                'percent': (gpu_memory / gpu_total) * 100
            }
            
            logger.info(f"GPU usage: {gpu_memory:.1f}GB / {gpu_total:.1f}GB")
            
        except Exception as e:
            logger.error(f"Error monitoring GPU memory: {e}")
    
    return stats


@contextmanager
def managed_resources(cleanup: bool = True, monitor: bool = False):
    """Context manager for automatic resource cleanup.
    
    Args:
        cleanup: Whether to perform cleanup on exit
        monitor: Whether to monitor memory before and after
        
    Example:
        with managed_resources(monitor=True):
            # Process large data
            data = load_large_dataset()
            results = process_data(data)
    """
    if monitor:
        logger.info("=== Resource usage before ===")
        initial_stats = monitor_memory()
    
    try:
        yield
    finally:
        if cleanup:
            cleanup_memory()
        
        if monitor:
            logger.info("=== Resource usage after ===")
            final_stats = monitor_memory()
            
            # Calculate differences
            if initial_stats and final_stats:
                if 'cpu_memory' in initial_stats and 'cpu_memory' in final_stats:
                    cpu_diff = (final_stats['cpu_memory']['used_gb'] - 
                               initial_stats['cpu_memory']['used_gb'])
                    logger.info(f"CPU memory change: {cpu_diff:+.2f} GB")
                
                if 'gpu_memory' in initial_stats and 'gpu_memory' in final_stats:
                    gpu_diff = (final_stats['gpu_memory']['allocated_gb'] - 
                               initial_stats['gpu_memory']['allocated_gb'])
                    logger.info(f"GPU memory change: {gpu_diff:+.2f} GB")


class ResourceManager:
    """Manager for tracking and limiting resource usage."""
    
    def __init__(self, 
                 max_memory_percent: Optional[float] = None,
                 cleanup_threshold: float = 80.0,
                 auto_cleanup: bool = True):
        """Initialize resource manager.
        
        Args:
            max_memory_percent: Maximum memory usage percentage allowed
            cleanup_threshold: Memory percentage that triggers cleanup
            auto_cleanup: Whether to automatically cleanup when threshold is reached
        """
        self.max_memory_percent = max_memory_percent
        self.cleanup_threshold = cleanup_threshold
        self.auto_cleanup = auto_cleanup
        self._cleanup_count = 0
    
    def check_memory(self) -> bool:
        """Check if memory usage is within limits.
        
        Returns:
            True if memory is within limits, False otherwise
        """
        if not HAS_PSUTIL:
            return True
        
        try:
            memory = psutil.virtual_memory()
            current_percent = memory.percent
            
            # Trigger cleanup if threshold exceeded
            if self.auto_cleanup and current_percent >= self.cleanup_threshold:
                logger.warning(f"Memory usage {current_percent:.1f}% exceeds threshold "
                             f"{self.cleanup_threshold:.1f}%, triggering cleanup")
                cleanup_memory()
                self._cleanup_count += 1
                
                # Re-check after cleanup
                memory = psutil.virtual_memory()
                current_percent = memory.percent
            
            # Check if within max limit
            if self.max_memory_percent and current_percent > self.max_memory_percent:
                logger.error(f"Memory usage {current_percent:.1f}% exceeds maximum "
                           f"{self.max_memory_percent:.1f}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking memory: {e}")
            return True
    
    def __enter__(self):
        """Enter context manager."""
        self.check_memory()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager with cleanup."""
        if self.auto_cleanup:
            cleanup_memory()
    
    @property
    def cleanup_count(self) -> int:
        """Get number of automatic cleanups performed."""
        return self._cleanup_count


def memory_limited(max_percent: float = 90.0, cleanup: bool = True):
    """Decorator to limit memory usage for a function.
    
    Args:
        max_percent: Maximum memory percentage allowed
        cleanup: Whether to cleanup after function execution
        
    Example:
        @memory_limited(max_percent=80.0)
        def process_large_data(data):
            # Function that uses lots of memory
            return heavy_computation(data)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Check memory before execution
            if HAS_PSUTIL:
                memory = psutil.virtual_memory()
                if memory.percent > max_percent:
                    raise MemoryError(f"Memory usage {memory.percent:.1f}% exceeds "
                                    f"limit {max_percent:.1f}% before executing {func.__name__}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                return result
            finally:
                if cleanup:
                    cleanup_memory()
        
        return wrapper
    return decorator


def monitor_resources(func: Callable) -> Callable:
    """Decorator to monitor resource usage of a function.
    
    Example:
        @monitor_resources
        def expensive_operation():
            # Some memory-intensive operation
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        logger.info(f"=== Starting {func.__name__} ===")
        initial_stats = monitor_memory()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            logger.info(f"=== Completed {func.__name__} ===")
            final_stats = monitor_memory()
            
            # Log differences
            if initial_stats and final_stats:
                if 'cpu_memory' in initial_stats and 'cpu_memory' in final_stats:
                    cpu_diff = (final_stats['cpu_memory']['used_gb'] - 
                               initial_stats['cpu_memory']['used_gb'])
                    logger.info(f"{func.__name__} CPU memory change: {cpu_diff:+.2f} GB")
    
    return wrapper


def batch_processor(batch_size: int = 100, 
                   cleanup_interval: int = 10,
                   monitor: bool = False):
    """Decorator for processing data in batches with memory management.
    
    Args:
        batch_size: Size of each batch
        cleanup_interval: Cleanup memory every N batches
        monitor: Whether to monitor memory usage
        
    The decorated function should accept an iterable and process items one at a time.
    
    Example:
        @batch_processor(batch_size=50, cleanup_interval=5)
        def process_items(items):
            for item in items:
                # Process single item
                yield transform(item)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(items, *args, **kwargs):
            batch = []
            batch_count = 0
            
            with managed_resources(cleanup=False, monitor=monitor):
                for i, item in enumerate(items):
                    batch.append(item)
                    
                    if len(batch) >= batch_size:
                        # Process batch
                        logger.debug(f"Processing batch {batch_count + 1} "
                                   f"(items {i - batch_size + 1} to {i})")
                        
                        for result in func(batch, *args, **kwargs):
                            yield result
                        
                        batch.clear()
                        batch_count += 1
                        
                        # Periodic cleanup
                        if batch_count % cleanup_interval == 0:
                            logger.debug(f"Performing cleanup after {batch_count} batches")
                            cleanup_memory()
                
                # Process remaining items
                if batch:
                    logger.debug(f"Processing final batch (items {i - len(batch) + 1} to {i})")
                    for result in func(batch, *args, **kwargs):
                        yield result
                    
                    cleanup_memory()
        
        return wrapper
    return decorator