"""Retry and resilience utilities for handling transient failures."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Type, Tuple, Optional, Union, Any, List, Dict
import functools
import logging
import random
import time
logger = logging.getLogger(__name__)


class ExponentialBackoff:
    """Exponential backoff calculator for retry logic."""

    def __init__(self, base: float = 2.0, max_delay: float = 60.0):
        """Initialize exponential backoff.

        Args:
            base: Base for exponential calculation
            max_delay: Maximum delay in seconds
        """
        self.base = base
        self.max_delay = max_delay
        self.attempt = 0

    def get_next_delay(self) -> float:
        """Get the next delay value."""
        delay = min(self.base**self.attempt, self.max_delay)
        self.attempt += 1
        return delay

    def reset(self):
        """Reset the backoff counter."""
        self.attempt = 0


class RetryStrategy(Enum):
    """Retry strategies for different backoff patterns."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    FIBONACCI = "fibonacci"


class CircuitState(Enum):
    """States for circuit breaker pattern."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


def retry(
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    tries: int = 3,
    delay: float = 1.0,
    max_delay: float = 60.0,
    backoff: float = 2.0,
    jitter: bool = True,
) -> Callable:
    """Decorator to retry a function on exception.

    Args:
        exceptions: Exception(s) to catch
        tries: Number of attempts
        delay: Initial delay between retries
        max_delay: Maximum delay between retries
        backoff: Backoff multiplier
        jitter: Add random jitter to delays

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_delay = delay

            while attempt < tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= tries:
                        logger.error(f"Failed after {tries} attempts: {e}")
                        raise

                    # Calculate next delay
                    if jitter:
                        actual_delay = current_delay * (0.5 + random.random())
                    else:
                        actual_delay = current_delay

                    logger.warning(
                        f"Attempt {attempt}/{tries} failed: {e}. "
                        f"Retrying in {actual_delay:.1f}s..."
                    )

                    time.sleep(actual_delay)
                    current_delay = min(current_delay * backoff, max_delay)

            return None  # Should never reach here

        return wrapper

    return decorator


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retryable_errors: Optional[List[str]] = None,
    max_delay: float = 60.0,
    jitter: bool = True,
):
    """Decorator for retrying transient failures with configurable backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor for calculating backoff delay
        strategy: Backoff strategy to use
        retryable_exceptions: Tuple of exception types to retry
        retryable_errors: List of error message patterns to retry
        max_delay: Maximum delay between retries in seconds
        jitter: Whether to add random jitter to delays

    Example:
        @with_retry(max_retries=5, strategy=RetryStrategy.EXPONENTIAL)
        def call_api():
            # Make API call that might fail transiently
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            # If max_retries is 0, just call the function once
            if max_retries == 0:
                return func(*args, **kwargs)

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    # Check if this is the last attempt
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise

                    # If retryable_errors is provided, check if error matches patterns
                    if retryable_errors:
                        error_str = str(e).lower()
                        is_retryable = any(pattern in error_str for pattern in retryable_errors)

                        if not is_retryable:
                            logger.error(f"Non-retryable error: {e}")
                            raise

                    # Calculate delay based on strategy
                    delay = _calculate_delay(attempt, backoff_factor, strategy, max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        f"Retryable error on attempt {attempt + 1}/{max_retries}, "
                        f"waiting {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)

            # Should never reach here
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def _calculate_delay(
    attempt: int, factor: float, strategy: RetryStrategy, max_delay: float
) -> float:
    """Calculate backoff delay based on strategy."""
    if strategy == RetryStrategy.EXPONENTIAL:
        delay = factor**attempt
    elif strategy == RetryStrategy.LINEAR:
        delay = factor * (attempt + 1)
    elif strategy == RetryStrategy.CONSTANT:
        delay = factor
    elif strategy == RetryStrategy.FIBONACCI:
        # Fibonacci sequence for delays
        a, b = 1, 1
        for _ in range(attempt):
            a, b = b, a + b
        delay = a * factor
    else:
        delay = factor

    return min(delay, max_delay)


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            expected_exception: Exception type to monitor
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = max(0, recovery_timeout)  # Non-negative timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and datetime.now() - self._last_failure_time > timedelta(
                seconds=self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker moving to HALF_OPEN state")
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            raise Exception("Circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered, moving to CLOSED state")
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        # Only open circuit if threshold is positive
        if self.failure_threshold > 0 and self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(f"Circuit breaker opened after {self._failure_count} failures")
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker test failed, returning to OPEN state")

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper


def retry_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    max_retries: int = 3,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Try primary function with retries, fall back to alternative on failure.

    Args:
        primary_func: Primary function to try
        fallback_func: Fallback function if primary fails
        max_retries: Number of retries for primary function
        exceptions: Exceptions to catch and retry

    Example:
        def get_from_api():
            # Try to get from API
            pass

        def get_from_cache():
            # Get from cache as fallback
            pass

        result = retry_with_fallback(get_from_api, get_from_cache)
    """

    def execute(*args, **kwargs):
        # Try primary function with retries
        last_exception = None

        for attempt in range(max_retries):
            try:
                return primary_func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                logger.warning(
                    f"Primary function failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff

        # Primary failed, try fallback
        logger.warning(f"Primary function failed after {max_retries} attempts, trying fallback")
        try:
            return fallback_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback function also failed: {e}")
            # Raise the original exception from primary function
            if last_exception:
                raise last_exception
            raise

    return execute


class RateLimiter:
    """Token bucket rate limiter for controlling request rates."""

    def __init__(self, rate: float, burst: int):
        """Initialize rate limiter.

        Args:
            rate: Tokens per second
            burst: Maximum burst size (bucket capacity)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = burst
        self._last_update = time.time()

    def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        while True:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            # Calculate wait time
            wait_time = (tokens - self._tokens) / self.rate
            time.sleep(wait_time)
            return wait_time

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait_time = self.acquire()
            if wait_time > 0:
                logger.debug(f"Rate limited, waited {wait_time:.2f}s")
            return func(*args, **kwargs)

        return wrapper


def resilient_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    circuit_breaker: Optional[CircuitBreaker] = None,
    rate_limiter: Optional[RateLimiter] = None,
    timeout: Optional[float] = None,
    **kwargs,
) -> Any:
    """Make a resilient function call with multiple protection mechanisms.

    Args:
        func: Function to call
        max_retries: Maximum retry attempts
        circuit_breaker: Optional circuit breaker instance
        rate_limiter: Optional rate limiter instance
        timeout: Optional timeout in seconds
        *args, **kwargs: Arguments for the function

    Returns:
        Function result

    Example:
        breaker = CircuitBreaker(failure_threshold=5)
        limiter = RateLimiter(rate=10.0, burst=20)

        result = resilient_call(
            api_client.get_data,
            max_retries=5,
            circuit_breaker=breaker,
            rate_limiter=limiter,
            timeout=30.0
        )
    """
    # Apply rate limiting if configured
    if rate_limiter:
        rate_limiter.acquire()

    # Apply circuit breaker if configured
    if circuit_breaker:
        wrapped_func = circuit_breaker(func)
    else:
        wrapped_func = func

    # Apply retry logic
    @with_retry(max_retries=max_retries)
    def retriable_func():
        if timeout:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function call timed out after {timeout}s")

            # Set timeout alarm (minimum 1 second for signal.alarm)
            timeout_seconds = max(1, int(timeout))
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

            try:
                return wrapped_func(*args, **kwargs)
            finally:
                # Reset alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            return wrapped_func(*args, **kwargs)

    return retriable_func()


class RetryableError(Exception):
    """Base class for errors that should be retried."""

    pass


class TransientError(RetryableError):
    """Error that is expected to be temporary."""

    pass


class RateLimitError(RetryableError):
    """Error indicating rate limit has been hit."""

    pass
