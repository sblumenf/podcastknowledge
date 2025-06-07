"""Simple memory management utilities."""

from typing import Optional, Dict, Any
import gc
import logging
import time
logger = logging.getLogger(__name__)


def cleanup_memory() -> None:
    """Clean up memory using garbage collection.
    
    This function performs basic garbage collection to free unreferenced objects.
    """
    # Force garbage collection
    gc.collect()
    logger.debug("Memory cleanup completed")


def get_memory_usage() -> float:
    """Get current memory usage in MB.
    
    Returns:
        Memory usage in MB, or 0.0 if unable to determine.
    """
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        logger.debug("psutil not available for memory monitoring")
        return 0.0
    except Exception as e:
        logger.debug(f"Unable to get memory usage: {e}")
        return 0.0


class MemoryMonitor:
    """Monitor memory usage during processing."""
    
    def __init__(self, threshold_mb: float = 1000.0):
        """
        Initialize memory monitor.
        
        Args:
            threshold_mb: Memory threshold in MB for warnings
        """
        self.threshold_mb = threshold_mb
        self.start_memory = 0.0
        self.peak_memory = 0.0
        self._monitoring = False
        
    def start(self) -> None:
        """Start memory monitoring."""
        self.start_memory = get_memory_usage()
        self.peak_memory = self.start_memory
        self._monitoring = True
        logger.debug(f"Memory monitoring started. Initial: {self.start_memory:.1f} MB")
        
    def stop(self) -> Dict[str, float]:
        """Stop memory monitoring and return statistics."""
        if not self._monitoring:
            return {"start": 0.0, "peak": 0.0, "current": 0.0, "increase": 0.0}
            
        current_memory = get_memory_usage()
        self._monitoring = False
        
        stats = {
            "start": self.start_memory,
            "peak": self.peak_memory,
            "current": current_memory,
            "increase": current_memory - self.start_memory
        }
        
        logger.debug(f"Memory monitoring stopped. Current: {current_memory:.1f} MB, "
                    f"Peak: {self.peak_memory:.1f} MB, "
                    f"Increase: {stats['increase']:.1f} MB")
        
        return stats
        
    def check(self) -> Optional[float]:
        """Check current memory usage and update peak."""
        if not self._monitoring:
            return None
            
        current_memory = get_memory_usage()
        self.peak_memory = max(self.peak_memory, current_memory)
        
        if current_memory > self.threshold_mb:
            logger.warning(f"Memory usage high: {current_memory:.1f} MB "
                         f"(threshold: {self.threshold_mb:.1f} MB)")
            
        return current_memory
        
    def __enter__(self) -> 'MemoryMonitor':
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()