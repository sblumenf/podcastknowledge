"""
Retry utilities for resilient database and API operations.

Provides retry logic with exponential backoff for handling transient failures
in Neo4j queries, embedding service calls, and other external operations.
"""

import time
import random
from typing import TypeVar, Callable, Any, Optional, Tuple, Type
from functools import wraps
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> T:
    """
    Execute a function with retry logic and exponential backoff.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for delay on each retry (default: 2.0)
        max_delay: Maximum delay between retries (default: 60.0)
        jitter: Add random jitter to delays to prevent thundering herd (default: True)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
        on_retry: Optional callback called on each retry with (exception, attempt_number)
        
    Returns:
        Result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                # Final attempt failed
                logger.error(f"All {max_retries + 1} attempts failed. Final error: {e}")
                raise
            
            # Calculate next delay with optional jitter
            if jitter:
                # Add up to 20% random jitter
                jitter_amount = delay * 0.2 * random.random()
                actual_delay = delay + jitter_amount
            else:
                actual_delay = delay
            
            # Log retry attempt
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {actual_delay:.2f}s..."
            )
            
            # Call optional retry callback
            if on_retry:
                on_retry(e, attempt + 1)
            
            # Wait before retry
            time.sleep(actual_delay)
            
            # Increase delay for next attempt
            delay = min(delay * backoff_factor, max_delay)
    
    # Should never reach here
    raise last_exception


def retry_decorator(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator version of retry_with_backoff.
    
    Usage:
        @retry_decorator(max_retries=3, initial_delay=2.0)
        def my_function():
            # Function that might fail transiently
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                max_delay=max_delay,
                jitter=jitter,
                exceptions=exceptions
            )
        return wrapper
    return decorator


class RetryableNeo4j:
    """
    Wrapper for Neo4j operations with built-in retry logic.
    """
    
    def __init__(
        self, 
        neo4j_service,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0
    ):
        """
        Initialize retryable Neo4j wrapper.
        
        Args:
            neo4j_service: GraphStorageService instance
            max_retries: Maximum retry attempts for queries
            initial_delay: Initial retry delay in seconds
            backoff_factor: Delay multiplier for each retry
        """
        self.neo4j = neo4j_service
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
    
    def query(self, cypher: str, parameters: Optional[dict] = None, **kwargs) -> list:
        """
        Execute a Neo4j query with retry logic.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            **kwargs: Additional arguments for the query method
            
        Returns:
            Query results
        """
        def _execute():
            return self.neo4j.query(cypher, parameters, **kwargs)
        
        return retry_with_backoff(
            _execute,
            max_retries=self.max_retries,
            initial_delay=self.initial_delay,
            backoff_factor=self.backoff_factor,
            on_retry=lambda e, attempt: logger.info(
                f"Neo4j query retry {attempt}/{self.max_retries} after error: {type(e).__name__}"
            )
        )
    
    def run_in_transaction(self, transaction_func: Callable, *args, **kwargs):
        """
        Run a function in a Neo4j transaction with retry logic.
        
        Args:
            transaction_func: Function to execute in transaction
            *args, **kwargs: Arguments for the transaction function
            
        Returns:
            Result of the transaction function
        """
        def _execute():
            with self.neo4j.session() as session:
                return session.write_transaction(transaction_func, *args, **kwargs)
        
        return retry_with_backoff(
            _execute,
            max_retries=self.max_retries,
            initial_delay=self.initial_delay,
            backoff_factor=self.backoff_factor,
            on_retry=lambda e, attempt: logger.info(
                f"Neo4j transaction retry {attempt}/{self.max_retries} after error: {type(e).__name__}"
            )
        )