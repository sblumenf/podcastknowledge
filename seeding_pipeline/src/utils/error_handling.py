"""
Error handling utilities and decorators for standardized error management.

This module provides decorators and utilities for consistent error handling
across the podcast knowledge pipeline.
"""

import functools
import logging
import time
from typing import Callable, TypeVar, Optional, Any, Type, Tuple, Union
from datetime import datetime

from src.core.exceptions import PipelineError, ExtractionError, ProviderError
from src.utils.retry import ExponentialBackoff

logger = logging.getLogger(__name__)

# Type variables for generic decorator
F = TypeVar('F', bound=Callable[..., Any])


def with_error_handling(
    retry_count: int = 3,
    log_errors: bool = True,
    raise_on_failure: bool = True,
    default_return: Optional[Any] = None,
    exceptions_to_retry: Tuple[Type[Exception], ...] = (Exception,),
    exceptions_to_ignore: Tuple[Type[Exception], ...] = (),
    backoff_base: float = 2.0,
    backoff_max: float = 60.0
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling with retry logic.
    
    Args:
        retry_count: Number of retry attempts (default: 3)
        log_errors: Whether to log errors (default: True)
        raise_on_failure: Whether to raise exception after all retries (default: True)
        default_return: Value to return on failure if not raising (default: None)
        exceptions_to_retry: Tuple of exceptions that trigger retry (default: all)
        exceptions_to_ignore: Tuple of exceptions to ignore and not retry
        backoff_base: Base for exponential backoff (default: 2.0)
        backoff_max: Maximum backoff time in seconds (default: 60.0)
        
    Returns:
        Decorated function with error handling
        
    Example:
        @with_error_handling(retry_count=3, log_errors=True)
        def process_episode(...):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper function with error handling logic."""
            func_name = f"{func.__module__}.{func.__name__}"
            backoff = ExponentialBackoff(
                base=backoff_base,
                max_delay=backoff_max
            )
            
            last_exception = None
            
            for attempt in range(retry_count + 1):
                try:
                    # Log function call on first attempt
                    if attempt == 0 and log_errors:
                        logger.debug(f"Calling {func_name}")
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Success - reset backoff and return
                    backoff.reset()
                    return result
                    
                except exceptions_to_ignore as e:
                    # These exceptions should not trigger retry
                    if log_errors:
                        logger.warning(
                            f"{func_name} encountered ignorable exception: {type(e).__name__}: {e}"
                        )
                    if raise_on_failure:
                        raise
                    return default_return
                    
                except exceptions_to_retry as e:
                    last_exception = e
                    
                    if attempt < retry_count:
                        # Calculate backoff delay
                        delay = backoff.get_next_delay()
                        
                        if log_errors:
                            logger.warning(
                                f"{func_name} failed (attempt {attempt + 1}/{retry_count + 1}): "
                                f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                            )
                        
                        # Wait before retry
                        time.sleep(delay)
                    else:
                        # Final attempt failed
                        if log_errors:
                            logger.error(
                                f"{func_name} failed after {retry_count + 1} attempts: "
                                f"{type(e).__name__}: {e}",
                                exc_info=True
                            )
                        
                        if raise_on_failure:
                            raise
                        
                        return default_return
            
            # Should not reach here, but just in case
            if last_exception and raise_on_failure:
                raise last_exception
            
            return default_return
        
        return wrapper
    
    return decorator


def with_timeout(
    timeout_seconds: float,
    timeout_exception: Type[Exception] = TimeoutError,
    message: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator to add timeout functionality to a function.
    
    Note: This is a simplified version. For production use,
    consider using threading or signal-based timeouts.
    
    Args:
        timeout_seconds: Maximum execution time
        timeout_exception: Exception to raise on timeout
        message: Custom timeout message
        
    Returns:
        Decorated function with timeout
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper function with timeout logic."""
            import signal
            
            def timeout_handler(signum, frame):
                msg = message or f"{func.__name__} timed out after {timeout_seconds}s"
                raise timeout_exception(msg)
            
            # Set up timeout (Unix only)
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel alarm and restore handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result
        
        return wrapper
    
    return decorator


def log_execution(
    log_args: bool = False,
    log_result: bool = False,
    log_time: bool = True
) -> Callable[[F], F]:
    """
    Decorator to log function execution details.
    
    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_time: Whether to log execution time
        
    Returns:
        Decorated function with logging
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper function with logging logic."""
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log entry
            if log_args:
                logger.info(
                    f"Entering {func_name} with args={args}, kwargs={kwargs}"
                )
            else:
                logger.info(f"Entering {func_name}")
            
            # Track execution time
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Log success
                elapsed = time.time() - start_time
                
                log_parts = [f"Completed {func_name}"]
                if log_time:
                    log_parts.append(f"in {elapsed:.2f}s")
                if log_result:
                    log_parts.append(f"result={result}")
                
                logger.info(" ".join(log_parts))
                
                return result
                
            except Exception as e:
                # Log failure
                elapsed = time.time() - start_time
                logger.error(
                    f"Failed {func_name} after {elapsed:.2f}s: "
                    f"{type(e).__name__}: {e}"
                )
                raise
        
        return wrapper
    
    return decorator


def handle_provider_errors(
    provider_type: str,
    operation: str
) -> Callable[[F], F]:
    """
    Specialized error handler for provider operations.
    
    Args:
        provider_type: Type of provider (audio, llm, graph, embedding)
        operation: Operation being performed
        
    Returns:
        Decorated function with provider-specific error handling
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper function with provider error handling."""
            try:
                return func(*args, **kwargs)
            except ProviderError:
                # Already a provider error, re-raise
                raise
            except Exception as e:
                # Wrap in provider error with context
                raise ProviderError(
                    provider_type,
                    f"Failed during {operation}: {e}",
                    original_error=e
                )
        
        return wrapper
    
    return decorator


# Convenience decorators with common configurations
retry_on_error = functools.partial(
    with_error_handling,
    retry_count=3,
    log_errors=True
)

retry_on_network_error = functools.partial(
    with_error_handling,
    retry_count=5,
    exceptions_to_retry=(ConnectionError, TimeoutError),
    backoff_max=120.0
)

log_and_suppress_errors = functools.partial(
    with_error_handling,
    retry_count=0,
    log_errors=True,
    raise_on_failure=False
)


__all__ = [
    'with_error_handling',
    'with_timeout',
    'log_execution',
    'handle_provider_errors',
    'retry_on_error',
    'retry_on_network_error',
    'log_and_suppress_errors'
]