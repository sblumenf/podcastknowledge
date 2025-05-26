"""Tests for retry and resilience utilities."""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.utils.retry import (
    with_retry,
    RetryStrategy,
    CircuitBreaker,
    CircuitState,
    retry_with_fallback,
    RateLimiter,
    resilient_call,
    RetryableError,
    TransientError,
    RateLimitError,
    _calculate_delay
)


class TestWithRetry:
    """Tests for with_retry decorator."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        mock_func = Mock(return_value="success")
        
        @with_retry(max_retries=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_failure(self):
        """Test function retries on failure."""
        mock_func = Mock(side_effect=[Exception("error"), Exception("error"), "success"])
        
        @with_retry(max_retries=3, backoff_factor=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test exception raised when max retries exceeded."""
        mock_func = Mock(side_effect=Exception("persistent error"))
        
        @with_retry(max_retries=3, backoff_factor=0.1)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception, match="persistent error"):
            test_func()
        
        assert mock_func.call_count == 3
    
    def test_retryable_errors(self):
        """Test only specific errors are retried."""
        mock_func = Mock(side_effect=[
            Exception("rate limit exceeded"),
            Exception("429 too many requests"),
            "success"
        ])
        
        @with_retry(max_retries=5, backoff_factor=0.1, retryable_errors=['rate limit', '429'])
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_non_retryable_error(self):
        """Test non-retryable errors are raised immediately."""
        mock_func = Mock(side_effect=Exception("fatal error"))
        
        @with_retry(max_retries=3, retryable_errors=['timeout'])
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception, match="fatal error"):
            test_func()
        
        assert mock_func.call_count == 1  # No retries
    
    def test_specific_exception_types(self):
        """Test retrying only specific exception types."""
        mock_func = Mock(side_effect=[ValueError("error"), "success"])
        
        @with_retry(max_retries=3, retryable_exceptions=(ValueError,), backoff_factor=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        
        # Test with non-retryable exception
        mock_func.side_effect = [TypeError("error")]
        
        @with_retry(max_retries=3, retryable_exceptions=(ValueError,))
        def test_func2():
            return mock_func()
        
        with pytest.raises(TypeError):
            test_func2()
    
    @pytest.mark.parametrize("strategy,expected_delays", [
        (RetryStrategy.EXPONENTIAL, [1, 2, 4]),
        (RetryStrategy.LINEAR, [2, 4, 6]),
        (RetryStrategy.CONSTANT, [2, 2, 2]),
        (RetryStrategy.FIBONACCI, [2, 2, 4]),
    ])
    def test_backoff_strategies(self, strategy, expected_delays):
        """Test different backoff strategies."""
        delays = []
        for i in range(3):
            delay = _calculate_delay(i, 2, strategy, 100)
            delays.append(delay)
        
        assert delays == expected_delays
    
    def test_max_delay(self):
        """Test maximum delay is respected."""
        delay = _calculate_delay(10, 2, RetryStrategy.EXPONENTIAL, max_delay=5.0)
        assert delay == 5.0
    
    @patch('time.sleep')
    def test_jitter(self, mock_sleep):
        """Test jitter adds randomness to delays."""
        mock_func = Mock(side_effect=[Exception("error"), "success"])
        
        @with_retry(max_retries=2, backoff_factor=1.0, jitter=True)
        def test_func():
            return mock_func()
        
        test_func()
        
        # Check that sleep was called with a jittered value
        assert mock_sleep.called
        sleep_time = mock_sleep.call_args[0][0]
        assert 0.5 <= sleep_time <= 1.5  # Jitter adds 0.5x to 1.5x variation


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state allows calls."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(return_value="success")
        
        result = breaker.call(mock_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(side_effect=Exception("error"))
        
        # First two failures
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)
        assert breaker.state == CircuitState.CLOSED
        
        # Third failure opens circuit
        with pytest.raises(Exception):
            breaker.call(mock_func)
        assert breaker.state == CircuitState.OPEN
    
    def test_circuit_breaker_open_state_rejects_calls(self):
        """Test open circuit rejects calls."""
        breaker = CircuitBreaker(failure_threshold=1)
        mock_func = Mock(side_effect=Exception("error"))
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(mock_func)
        
        # Next call should be rejected
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            breaker.call(mock_func)
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit moves to half-open and recovers."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        mock_func = Mock()
        
        # Open the circuit
        mock_func.side_effect = Exception("error")
        with pytest.raises(Exception):
            breaker.call(mock_func)
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Should be half-open now, successful call closes it
        mock_func.side_effect = None
        mock_func.return_value = "success"
        
        result = breaker.call(mock_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_half_open_failure(self):
        """Test circuit returns to open on half-open failure."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        mock_func = Mock(side_effect=Exception("error"))
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(mock_func)
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Failure in half-open state
        with pytest.raises(Exception):
            breaker.call(mock_func)
        
        assert breaker.state == CircuitState.OPEN
    
    def test_circuit_breaker_decorator(self):
        """Test circuit breaker as decorator."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        @breaker
        def test_func(should_fail=False):
            if should_fail:
                raise Exception("error")
            return "success"
        
        # Successful calls
        assert test_func() == "success"
        assert test_func() == "success"
        
        # Failures open circuit
        with pytest.raises(Exception):
            test_func(should_fail=True)
        with pytest.raises(Exception):
            test_func(should_fail=True)
        
        # Circuit is open
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            test_func()


class TestRetryWithFallback:
    """Tests for retry_with_fallback function."""
    
    def test_primary_succeeds(self):
        """Test fallback not called when primary succeeds."""
        primary = Mock(return_value="primary result")
        fallback = Mock(return_value="fallback result")
        
        func = retry_with_fallback(primary, fallback)
        result = func()
        
        assert result == "primary result"
        primary.assert_called_once()
        fallback.assert_not_called()
    
    def test_fallback_on_primary_failure(self):
        """Test fallback called when primary fails."""
        primary = Mock(side_effect=Exception("primary failed"))
        fallback = Mock(return_value="fallback result")
        
        func = retry_with_fallback(primary, fallback, max_retries=2)
        result = func()
        
        assert result == "fallback result"
        assert primary.call_count == 2
        fallback.assert_called_once()
    
    def test_both_fail(self):
        """Test original exception raised when both fail."""
        primary = Mock(side_effect=Exception("primary failed"))
        fallback = Mock(side_effect=Exception("fallback failed"))
        
        func = retry_with_fallback(primary, fallback, max_retries=1)
        
        with pytest.raises(Exception, match="primary failed"):
            func()
    
    def test_primary_recovers(self):
        """Test primary recovers during retries."""
        primary = Mock(side_effect=[Exception("error"), "primary result"])
        fallback = Mock(return_value="fallback result")
        
        func = retry_with_fallback(primary, fallback, max_retries=3)
        result = func()
        
        assert result == "primary result"
        assert primary.call_count == 2
        fallback.assert_not_called()


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_rate_limiting(self):
        """Test rate limiter controls request rate."""
        limiter = RateLimiter(rate=10.0, burst=2)  # 10 per second, burst of 2
        
        # First two calls should be immediate (burst)
        start = time.time()
        limiter.acquire()
        limiter.acquire()
        elapsed = time.time() - start
        assert elapsed < 0.1
        
        # Third call should wait
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        assert elapsed >= 0.05  # Should wait ~0.1s, allow some margin
    
    def test_rate_limiter_decorator(self):
        """Test rate limiter as decorator."""
        limiter = RateLimiter(rate=100.0, burst=2)  # High rate for testing
        call_count = 0
        
        @limiter
        def test_func():
            nonlocal call_count
            call_count += 1
            return call_count
        
        # Should allow burst
        assert test_func() == 1
        assert test_func() == 2
        
        # Should still work after burst
        assert test_func() == 3


class TestResilientCall:
    """Tests for resilient_call function."""
    
    def test_basic_call(self):
        """Test basic function call without protections."""
        mock_func = Mock(return_value="success")
        
        result = resilient_call(mock_func, arg1="test", max_retries=1)
        
        assert result == "success"
        mock_func.assert_called_once_with(arg1="test")
    
    def test_with_circuit_breaker(self):
        """Test resilient call with circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=2)
        mock_func = Mock(side_effect=[Exception("error"), "success"])
        
        result = resilient_call(
            mock_func,
            max_retries=3,
            circuit_breaker=breaker
        )
        
        assert result == "success"
    
    def test_with_rate_limiter(self):
        """Test resilient call with rate limiter."""
        limiter = RateLimiter(rate=100.0, burst=1)
        mock_func = Mock(return_value="success")
        
        result = resilient_call(
            mock_func,
            rate_limiter=limiter
        )
        
        assert result == "success"
    
    @patch('signal.signal')
    @patch('signal.alarm')
    def test_with_timeout(self, mock_alarm, mock_signal):
        """Test resilient call with timeout."""
        mock_func = Mock(return_value="success")
        
        result = resilient_call(
            mock_func,
            timeout=30.0
        )
        
        assert result == "success"
        mock_alarm.assert_called()
    
    def test_combined_protections(self):
        """Test resilient call with multiple protections."""
        breaker = CircuitBreaker(failure_threshold=5)
        limiter = RateLimiter(rate=100.0, burst=10)
        mock_func = Mock(side_effect=[TransientError("error"), "success"])
        
        result = resilient_call(
            mock_func,
            max_retries=3,
            circuit_breaker=breaker,
            rate_limiter=limiter
        )
        
        assert result == "success"


class TestRetryableErrors:
    """Tests for retryable error classes."""
    
    def test_retryable_error_hierarchy(self):
        """Test error class hierarchy."""
        assert issubclass(TransientError, RetryableError)
        assert issubclass(RateLimitError, RetryableError)
        
        # Test instantiation
        error1 = TransientError("temporary issue")
        error2 = RateLimitError("rate limit exceeded")
        
        assert str(error1) == "temporary issue"
        assert str(error2) == "rate limit exceeded"
        assert isinstance(error1, RetryableError)
        assert isinstance(error2, RetryableError)