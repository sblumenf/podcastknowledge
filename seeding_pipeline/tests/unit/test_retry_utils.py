"""Tests for retry utilities."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch, call
import time

import pytest

from src.utils.retry import (
    ExponentialBackoff,
    RetryStrategy,
    CircuitState,
    CircuitBreaker,
    retry,
    retry_on_exception,
    async_retry,
    RetryConfig,
    Exception,
)


class TestExponentialBackoff:
    """Test ExponentialBackoff class."""
    
    def test_initial_state(self):
        """Test initial backoff state."""
        backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        assert backoff.base == 2.0
        assert backoff.max_delay == 60.0
        assert backoff.attempt == 0
    
    def test_get_next_delay(self):
        """Test getting next delay values."""
        backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        
        # First attempts follow exponential pattern
        assert backoff.get_next_delay() == 1.0  # 2^0
        assert backoff.get_next_delay() == 2.0  # 2^1
        assert backoff.get_next_delay() == 4.0  # 2^2
        assert backoff.get_next_delay() == 8.0  # 2^3
        
        # Should track attempts
        assert backoff.attempt == 4
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        backoff = ExponentialBackoff(base=2.0, max_delay=5.0)
        
        # Skip to high attempt count
        backoff.attempt = 10
        
        # Should be capped at max_delay
        assert backoff.get_next_delay() == 5.0
        assert backoff.get_next_delay() == 5.0
    
    def test_reset(self):
        """Test resetting backoff state."""
        backoff = ExponentialBackoff()
        
        # Make some attempts
        backoff.get_next_delay()
        backoff.get_next_delay()
        assert backoff.attempt == 2
        
        # Reset
        backoff.reset()
        assert backoff.attempt == 0
        assert backoff.get_next_delay() == 1.0  # Back to initial


class TestCircuitBreaker:
    """Test CircuitBreaker class."""
    
    def test_initial_state(self):
        """Test initial circuit breaker state."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=5.0,
            half_open_max_calls=1
        )
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None
    
    def test_record_success_in_closed_state(self):
        """Test recording success in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # Record some failures then success
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        
        breaker.record_success()
        assert breaker.failure_count == 0  # Reset on success
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_opens_on_threshold(self):
        """Test circuit opens when failure threshold reached."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # Record failures
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.last_failure_time is not None
    
    def test_call_permitted_in_states(self):
        """Test if calls are permitted in different states."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Closed state - calls permitted
        assert breaker.call_permitted() is True
        
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.call_permitted() is False
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should transition to half-open
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.call_permitted() is True
    
    def test_half_open_to_closed_transition(self):
        """Test transition from half-open to closed on success."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        
        # Wait for half-open
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Success in half-open closes circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_half_open_to_open_transition(self):
        """Test transition from half-open back to open on failure."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        
        # Wait for half-open
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure in half-open reopens circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.last_failure_time is not None


class TestRetryWithBackoff:
    """Test retry decorator."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        mock_func = Mock(return_value="success")
        
        @retry(max_retries=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_exception(self):
        """Test retry on exception."""
        mock_func = Mock(side_effect=[ValueError("Error 1"), ValueError("Error 2"), "success"])
        
        @retry(max_retries=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test when max retries is exceeded."""
        mock_func = Mock(side_effect=ValueError("Always fails"))
        
        @retry(max_retries=2, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(ValueError, match="Always fails"):
            test_func()
        
        # Original call + 2 retries = 3 total calls
        assert mock_func.call_count == 3
    
    def test_retry_specific_exceptions(self):
        """Test retrying only specific exceptions."""
        mock_func = Mock(side_effect=[ValueError("Retry this"), TypeError("Don't retry")])
        
        @retry(
            max_retries=3,
            retry_exceptions=(ValueError,),
            initial_delay=0.01
        )
        def test_func():
            return mock_func()
        
        # Should not retry TypeError
        with pytest.raises(TypeError, match="Don't retry"):
            test_func()
        
        assert mock_func.call_count == 2  # First ValueError, then TypeError
    
    def test_exponential_backoff_timing(self):
        """Test exponential backoff delays."""
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        call_times = []
        
        @retry(
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0
        )
        def test_func():
            call_times.append(time.time())
            return mock_func()
        
        test_func()
        
        # Check delays between calls
        assert len(call_times) == 3
        
        # First retry after ~0.1s
        delay1 = call_times[1] - call_times[0]
        assert 0.08 < delay1 < 0.12
        
        # Second retry after ~0.2s (backoff_factor=2)
        delay2 = call_times[2] - call_times[1]
        assert 0.18 < delay2 < 0.22


class TestRetryOnException:
    """Test retry_on_exception decorator."""
    
    def test_basic_retry(self):
        """Test basic retry functionality."""
        attempts = 0
        
        @retry_on_exception(ValueError, max_attempts=3, delay=0.01)
        def flaky_function():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError(f"Attempt {attempts} failed")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert attempts == 3
    
    def test_multiple_exception_types(self):
        """Test retrying multiple exception types."""
        mock_func = Mock(side_effect=[ValueError(), TypeError(), "success"])
        
        @retry_on_exception((ValueError, TypeError), max_attempts=3, delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        mock_func = Mock(side_effect=RuntimeError("Should not retry"))
        
        @retry_on_exception(ValueError, max_attempts=3, delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(RuntimeError, match="Should not retry"):
            test_func()
        
        assert mock_func.call_count == 1  # No retries


class TestAsyncRetry:
    """Test async_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry with eventual success."""
        attempts = 0
        
        @async_retry(max_attempts=3, delay=0.01)
        async def async_flaky_function():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError(f"Attempt {attempts}")
            return "async success"
        
        result = await async_flaky_function()
        assert result == "async success"
        assert attempts == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_failure(self):
        """Test async retry with all attempts failing."""
        mock_func = Mock(side_effect=ValueError("Always fails"))
        
        @async_retry(max_attempts=2, delay=0.01)
        async def async_failing_function():
            return mock_func()
        
        with pytest.raises(ValueError, match="Always fails"):
            await async_failing_function()
        
        assert mock_func.call_count == 2


class TestRetryConfig:
    """Test RetryConfig class."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True
        assert config.retry_exceptions == (Exception,)
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_factor=3.0,
            jitter=False,
            retry_exceptions=(ValueError, TypeError)
        )
        
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 3.0
        assert config.jitter is False
        assert config.retry_exceptions == (ValueError, TypeError)
    
    def test_apply_to_function(self):
        """Test applying config to a function."""
        config = RetryConfig(max_attempts=2, initial_delay=0.01)
        mock_func = Mock(side_effect=[ValueError(), "success"])
        
        @config.apply
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 2


class TestRetryIntegration:
    """Test integration of retry components."""
    
    def test_retry_with_circuit_breaker(self):
        """Test retry decorator with circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        call_count = 0
        
        @retry(
            max_retries=5,
            initial_delay=0.01,
            circuit_breaker=breaker
        )
        def protected_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        # First call should trigger retries and open circuit
        with pytest.raises(ValueError):
            protected_function()
        
        # Circuit should be open after 2 failures (1 + 2 retries)
        assert breaker.state == CircuitState.OPEN
        assert call_count == 3  # Initial + 2 retries
        
        # Next call should fail fast due to open circuit
        call_count = 0
        with pytest.raises(Exception, match="Circuit breaker is open"):
            protected_function()
        
        assert call_count == 0  # No actual function calls
    
    def test_retry_with_jitter(self):
        """Test retry with jitter to prevent thundering herd."""
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        call_times = []
        
        @retry(
            max_retries=3,
            initial_delay=0.1,
            jitter=True
        )
        def test_func():
            call_times.append(time.time())
            return mock_func()
        
        test_func()
        
        # Check that delays have some variance due to jitter
        delays = []
        for i in range(1, len(call_times)):
            delays.append(call_times[i] - call_times[i-1])
        
        # Delays should be different (unlikely to be exactly the same with jitter)
        assert len(set(delays)) > 1