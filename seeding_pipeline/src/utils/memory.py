"""Simple memory management utilities."""

import gc
import logging

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