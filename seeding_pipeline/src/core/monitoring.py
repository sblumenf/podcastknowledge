"""Monitoring utilities for the seeding pipeline."""

from functools import wraps
from typing import Any, Callable, TypeVar, Optional
import time
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def trace_operation(operation_name: Optional[str] = None) -> Callable:
    """
    Decorator to trace operation execution time.
    
    Args:
        operation_name: Optional name for the operation
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.debug(f"{op_name} completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{op_name} failed after {elapsed:.2f}s: {str(e)}")
                raise
                
        return wrapper
    return decorator