"""Retry Logic Wrapper for API Calls.

This module implements exponential backoff retry logic for API calls,
with special handling for quota limits and circuit breaker functionality.
"""

import asyncio
import os
from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
from pathlib import Path

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

from src.utils.logging import get_logger

logger = get_logger('retry_wrapper')

T = TypeVar('T')


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state for repeated failures."""
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    is_open: bool = False
    recovery_time: Optional[datetime] = None
    open_count: int = 0  # Track how many times circuit has opened
    last_reset: Optional[datetime] = None  # Track when circuit was last reset
    
    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure = datetime.now()
        
        # Open circuit after 3 consecutive failures
        if self.failure_count >= 3:
            self.is_open = True
            self.open_count += 1
            
            # Exponential backoff: 30min -> 1hr -> 2hr -> 2hr (max)
            if self.open_count == 1:
                recovery_minutes = 30
            elif self.open_count == 2:
                recovery_minutes = 60
            else:
                recovery_minutes = 120  # Cap at 2 hours
            
            self.recovery_time = datetime.now() + timedelta(minutes=recovery_minutes)
            logger.warning(
                f"Circuit breaker opened (count: {self.open_count}). "
                f"Will recover at {self.recovery_time} ({recovery_minutes} minutes)"
            )
    
    def record_success(self):
        """Record a success and reset the circuit."""
        self.failure_count = 0
        self.last_failure = None
        self.is_open = False
        self.recovery_time = None
        self.last_reset = datetime.now()
        # Reset open count after successful operation
        if self.last_reset and (datetime.now() - self.last_reset).days > 1:
            self.open_count = 0  # Reset count after 24 hours of stability
    
    def can_attempt(self) -> bool:
        """Check if we can attempt a call."""
        if not self.is_open:
            return True
        
        # Check if recovery time has passed
        if self.recovery_time and datetime.now() >= self.recovery_time:
            logger.info(
                f"Circuit breaker recovery time reached (was open {self.open_count} times), "
                "attempting reset"
            )
            self.is_open = False
            self.failure_count = 0
            return True
        
        return False


class QuotaExceededException(Exception):
    """Raised when API quota is exceeded."""
    pass


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open."""
    pass


class RetryManager:
    """Manages retry logic and circuit breaker state."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize retry manager.
        
        Args:
            state_dir: Directory for state files. Uses env var STATE_DIR or 'data' if not provided.
        """
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        
        # Determine state directory
        if state_dir:
            base_dir = state_dir
        elif os.environ.get('STATE_DIR'):
            base_dir = Path(os.environ['STATE_DIR'])
        else:
            base_dir = Path("data")
        
        self.state_file = base_dir / ".retry_state.json"
        self._load_state()
    
    def _load_state(self):
        """Load circuit breaker state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                for key, state_data in data.get('circuit_breakers', {}).items():
                    breaker = CircuitBreakerState(
                        failure_count=state_data.get('failure_count', 0),
                        is_open=state_data.get('is_open', False),
                        open_count=state_data.get('open_count', 0)
                    )
                    
                    if state_data.get('last_failure'):
                        breaker.last_failure = datetime.fromisoformat(state_data['last_failure'])
                    
                    if state_data.get('recovery_time'):
                        breaker.recovery_time = datetime.fromisoformat(state_data['recovery_time'])
                        # Check if we should have recovered
                        if datetime.now() >= breaker.recovery_time:
                            breaker.is_open = False
                            breaker.failure_count = 0
                    
                    self.circuit_breakers[key] = breaker
                    
                logger.info("Loaded retry state from file")
            except Exception as e:
                logger.warning(f"Failed to load retry state: {e}")
    
    def _save_state(self):
        """Save current state to file."""
        self.state_file.parent.mkdir(exist_ok=True)
        
        data = {
            'last_updated': datetime.now().isoformat(),
            'circuit_breakers': {}
        }
        
        for key, breaker in self.circuit_breakers.items():
            data['circuit_breakers'][key] = {
                'failure_count': breaker.failure_count,
                'is_open': breaker.is_open,
                'last_failure': breaker.last_failure.isoformat() if breaker.last_failure else None,
                'recovery_time': breaker.recovery_time.isoformat() if breaker.recovery_time else None
            }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save retry state: {e}")
    
    def get_circuit_breaker(self, key: str) -> CircuitBreakerState:
        """Get or create circuit breaker for a key."""
        if key not in self.circuit_breakers:
            self.circuit_breakers[key] = CircuitBreakerState()
        return self.circuit_breakers[key]
    
    def check_circuit(self, api_name: str, key_index: int):
        """Check if circuit breaker allows the call."""
        breaker_key = f"{api_name}_key_{key_index}"
        breaker = self.get_circuit_breaker(breaker_key)
        
        if not breaker.can_attempt():
            raise CircuitBreakerOpenException(
                f"Circuit breaker is open for {breaker_key}. "
                f"Recovery at {breaker.recovery_time}"
            )
    
    def record_success(self, api_name: str, key_index: int):
        """Record successful API call."""
        breaker_key = f"{api_name}_key_{key_index}"
        breaker = self.get_circuit_breaker(breaker_key)
        breaker.record_success()
        self._save_state()
    
    def record_failure(self, api_name: str, key_index: int):
        """Record failed API call."""
        breaker_key = f"{api_name}_key_{key_index}"
        breaker = self.get_circuit_breaker(breaker_key)
        breaker.record_failure()
        self._save_state()
    
    def force_reset(self, api_name: str, key_index: int):
        """Force reset a circuit breaker for a specific API and key."""
        breaker_key = f"{api_name}_key_{key_index}"
        if breaker_key in self.circuit_breakers:
            breaker = self.circuit_breakers[breaker_key]
            breaker.is_open = False
            breaker.failure_count = 0
            breaker.recovery_time = None
            breaker.last_reset = datetime.now()
            breaker.open_count = 0  # Reset open count on force reset
            logger.info(f"Force reset circuit breaker for {breaker_key}")
            self._save_state()
        else:
            logger.warning(f"No circuit breaker found for {breaker_key}")
    
    def force_reset_all(self):
        """Force reset all circuit breakers."""
        reset_count = 0
        for key, breaker in self.circuit_breakers.items():
            if breaker.is_open:
                breaker.is_open = False
                breaker.failure_count = 0
                breaker.recovery_time = None
                breaker.last_reset = datetime.now()
                breaker.open_count = 0
                reset_count += 1
                logger.info(f"Force reset circuit breaker: {key}")
        
        self._save_state()
        logger.info(f"Force reset {reset_count} circuit breakers")
        return reset_count
    
    def check_and_reset_expired_breakers(self):
        """Check for expired circuit breakers and reset them."""
        reset_count = 0
        current_time = datetime.now()
        
        for key, breaker in self.circuit_breakers.items():
            if breaker.is_open and breaker.recovery_time and current_time >= breaker.recovery_time:
                logger.info(f"Auto-resetting expired circuit breaker: {key}")
                breaker.is_open = False
                breaker.failure_count = 0
                breaker.last_reset = current_time
                reset_count += 1
        
        if reset_count > 0:
            self._save_state()
            logger.info(f"Auto-reset {reset_count} expired circuit breakers")
        
        return reset_count


# Global retry manager instance
retry_manager = RetryManager()


def force_reset_circuit_breakers():
    """Force reset all circuit breakers - utility function for manual intervention."""
    global retry_manager
    count = retry_manager.force_reset_all()
    return count


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable."""
    error_str = str(error).lower()
    
    # Non-retryable errors
    if any(term in error_str for term in ['quota', 'rate limit', 'limit exceeded']):
        return False
    
    # Retryable errors
    if any(term in error_str for term in ['timeout', 'connection', 'temporary', 'unavailable']):
        return True
    
    # Default to not retrying unknown errors
    return False


def create_retry_decorator(api_name: str, max_attempts: int = 2):
    """Create a retry decorator with proper configuration.
    
    Args:
        api_name: Name of the API being called (for logging)
        max_attempts: Maximum retry attempts (default 2 to preserve quota)
    
    Returns:
        Configured retry decorator
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logger.level)
    )


def with_retry_and_circuit_breaker(api_name: str, max_attempts: int = 2):
    """Decorator that adds retry logic and circuit breaker to async functions.
    
    Args:
        api_name: Name of the API for tracking
        max_attempts: Maximum retry attempts
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract key index from kwargs or args
            key_index = kwargs.get('key_index', 0)
            
            # Check circuit breaker
            try:
                retry_manager.check_circuit(api_name, key_index)
            except CircuitBreakerOpenException as e:
                logger.error(str(e))
                raise
            
            # Create retry logic
            retry_func = create_retry_decorator(api_name, max_attempts)(func)
            
            try:
                # Attempt the call with retries
                result = await retry_func(*args, **kwargs)
                
                # Record success
                retry_manager.record_success(api_name, key_index)
                return result
                
            except RetryError as e:
                # All retries exhausted
                logger.error(f"{api_name} failed after {max_attempts} attempts")
                retry_manager.record_failure(api_name, key_index)
                
                # Check if it's a quota error
                if e.last_attempt and e.last_attempt.exception():
                    last_error = e.last_attempt.exception()
                    if "quota" in str(last_error).lower():
                        raise QuotaExceededException(
                            f"API quota exceeded for {api_name}"
                        ) from last_error
                
                raise
            
            except Exception as e:
                # Direct failure (no retries)
                if is_retryable_error(e):
                    logger.warning(f"Retryable error in {api_name}: {e}")
                else:
                    logger.error(f"Non-retryable error in {api_name}: {e}")
                    if "quota" in str(e).lower():
                        raise QuotaExceededException(
                            f"API quota exceeded for {api_name}"
                        ) from e
                
                retry_manager.record_failure(api_name, key_index)
                raise
        
        return wrapper
    
    return decorator


def should_skip_episode(daily_requests_used: int, attempts_needed: int = 2, daily_limit: int = 25) -> bool:
    """Determine if an episode should be skipped to preserve daily quota.
    
    Args:
        daily_requests_used: Number of requests already used today
        attempts_needed: Number of attempts needed for the episode
        daily_limit: Daily request limit (default 25 for Gemini free tier)
    
    Returns:
        True if episode should be skipped
    """
    remaining = daily_limit - daily_requests_used
    
    if remaining < attempts_needed:
        logger.warning(
            f"Skipping episode: {remaining} requests remaining, "
            f"need {attempts_needed} for potential retries"
        )
        return True
    
    return False


async def retry_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    *args,
    **kwargs
) -> Any:
    """Execute primary function with retry, fall back to secondary on failure.
    
    Args:
        primary_func: Primary function to try
        fallback_func: Fallback function if primary fails
        *args: Positional arguments for functions
        **kwargs: Keyword arguments for functions
    
    Returns:
        Result from either primary or fallback function
    """
    try:
        return await primary_func(*args, **kwargs)
    except (RetryError, QuotaExceededException, CircuitBreakerOpenException) as e:
        logger.warning(f"Primary function failed: {e}, attempting fallback")
        return await fallback_func(*args, **kwargs)


class RetryableAPIClient:
    """Base class for API clients with retry capabilities."""
    
    def __init__(self, api_name: str):
        """Initialize retryable client.
        
        Args:
            api_name: Name of the API for tracking
        """
        self.api_name = api_name
        self.retry_manager = retry_manager
    
    def check_daily_quota(self, used_requests: int) -> bool:
        """Check if we have quota for retryable operation.
        
        Args:
            used_requests: Number of requests used today
            
        Returns:
            True if we have quota for operation with retries
        """
        return not should_skip_episode(used_requests)
    
    def get_circuit_state(self, key_index: int) -> Dict[str, Any]:
        """Get circuit breaker state for a key.
        
        Args:
            key_index: API key index
            
        Returns:
            Circuit breaker state information
        """
        breaker_key = f"{self.api_name}_key_{key_index}"
        breaker = self.retry_manager.get_circuit_breaker(breaker_key)
        
        return {
            'is_open': breaker.is_open,
            'failure_count': breaker.failure_count,
            'can_attempt': breaker.can_attempt(),
            'recovery_time': breaker.recovery_time.isoformat() if breaker.recovery_time else None
        }