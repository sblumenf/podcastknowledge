"""Comprehensive tests for retry and resilience utilities."""

from datetime import datetime, timedelta
from typing import Any, List
from unittest.mock import patch, MagicMock, call
import random
import signal
import time

import pytest

from src.utils.retry import (
    ExponentialBackoff,
    RetryStrategy,
    CircuitState,
    CircuitBreaker,
    RateLimiter,
    with_retry,
    retry_with_fallback,
    resilient_call,
    RetryableError,
    TransientError,
    RateLimitError,
    _calculate_delay
)


class TestExponentialBackoff:
    """Test suite for ExponentialBackoff class."""
    
    def test_initialization(self):
        """Test backoff initialization."""
        backoff = ExponentialBackoff()
        assert backoff.base == 2.0
        assert backoff.max_delay == 60.0
        assert backoff.attempt == 0
        
        backoff = ExponentialBackoff(base=3.0, max_delay=120.0)
        assert backoff.base == 3.0
        assert backoff.max_delay == 120.0
    
    def test_exponential_growth(self):
        """Test exponential delay growth."""
        backoff = ExponentialBackoff(base=2.0, max_delay=100.0)
        
        # Test exponential growth
        assert backoff.get_next_delay() == 1.0  # 2^0
        assert backoff.get_next_delay() == 2.0  # 2^1
        assert backoff.get_next_delay() == 4.0  # 2^2
        assert backoff.get_next_delay() == 8.0  # 2^3
        assert backoff.get_next_delay() == 16.0  # 2^4
    
    def test_max_delay_capping(self):
        """Test that delays are capped at max_delay."""
        backoff = ExponentialBackoff(base=2.0, max_delay=10.0)
        
        # Get to the cap
        for _ in range(10):
            delay = backoff.get_next_delay()
            assert delay <= 10.0
        
        # Should stay at max
        assert backoff.get_next_delay() == 10.0
    
    def test_reset(self):
        """Test resetting the backoff counter."""
        backoff = ExponentialBackoff()
        
        # Make some attempts
        backoff.get_next_delay()
        backoff.get_next_delay()
        assert backoff.attempt == 2
        
        # Reset
        backoff.reset()
        assert backoff.attempt == 0
        assert backoff.get_next_delay() == 1.0  # Back to 2^0
    
    def test_different_bases(self):
        """Test backoff with different base values."""
        # Base 3
        backoff = ExponentialBackoff(base=3.0)
        assert backoff.get_next_delay() == 1.0  # 3^0
        assert backoff.get_next_delay() == 3.0  # 3^1
        assert backoff.get_next_delay() == 9.0  # 3^2
        
        # Base 1.5
        backoff = ExponentialBackoff(base=1.5)
        assert backoff.get_next_delay() == 1.0  # 1.5^0
        assert backoff.get_next_delay() == 1.5  # 1.5^1
        assert backoff.get_next_delay() == 2.25  # 1.5^2


class TestCalculateDelay:
    """Test suite for _calculate_delay function."""
    
    def test_exponential_strategy(self):
        """Test exponential backoff strategy."""
        assert _calculate_delay(0, 2.0, RetryStrategy.EXPONENTIAL, 100) == 1.0  # 2^0
        assert _calculate_delay(1, 2.0, RetryStrategy.EXPONENTIAL, 100) == 2.0  # 2^1
        assert _calculate_delay(2, 2.0, RetryStrategy.EXPONENTIAL, 100) == 4.0  # 2^2
        assert _calculate_delay(3, 2.0, RetryStrategy.EXPONENTIAL, 100) == 8.0  # 2^3
    
    def test_linear_strategy(self):
        """Test linear backoff strategy."""
        assert _calculate_delay(0, 2.0, RetryStrategy.LINEAR, 100) == 2.0  # 2 * 1
        assert _calculate_delay(1, 2.0, RetryStrategy.LINEAR, 100) == 4.0  # 2 * 2
        assert _calculate_delay(2, 2.0, RetryStrategy.LINEAR, 100) == 6.0  # 2 * 3
        assert _calculate_delay(3, 2.0, RetryStrategy.LINEAR, 100) == 8.0  # 2 * 4
    
    def test_constant_strategy(self):
        """Test constant backoff strategy."""
        assert _calculate_delay(0, 5.0, RetryStrategy.CONSTANT, 100) == 5.0
        assert _calculate_delay(1, 5.0, RetryStrategy.CONSTANT, 100) == 5.0
        assert _calculate_delay(10, 5.0, RetryStrategy.CONSTANT, 100) == 5.0
    
    def test_fibonacci_strategy(self):
        """Test Fibonacci backoff strategy."""
        assert _calculate_delay(0, 1.0, RetryStrategy.FIBONACCI, 100) == 1.0  # F(1) * 1
        assert _calculate_delay(1, 1.0, RetryStrategy.FIBONACCI, 100) == 1.0  # F(2) * 1
        assert _calculate_delay(2, 1.0, RetryStrategy.FIBONACCI, 100) == 2.0  # F(3) * 1
        assert _calculate_delay(3, 1.0, RetryStrategy.FIBONACCI, 100) == 3.0  # F(4) * 1
        assert _calculate_delay(4, 1.0, RetryStrategy.FIBONACCI, 100) == 5.0  # F(5) * 1
    
    def test_max_delay_cap(self):
        """Test that all strategies respect max_delay."""
        strategies = [
            RetryStrategy.EXPONENTIAL,
            RetryStrategy.LINEAR,
            RetryStrategy.CONSTANT,
            RetryStrategy.FIBONACCI
        ]
        
        for strategy in strategies:
            delay = _calculate_delay(10, 10.0, strategy, 5.0)
            assert delay <= 5.0


class TestWithRetryDecorator:
    """Test suite for with_retry decorator."""
    
    def test_successful_call(self):
        """Test successful function call without retries."""
        call_count = 0
        
        @with_retry(max_retries=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_func()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_exception(self):
        """Test retry on exceptions."""
        call_count = 0
        
        @with_retry(max_retries=3, backoff_factor=0.1)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = failing_func()
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries."""
        call_count = 0
        
        @with_retry(max_retries=3, backoff_factor=0.1)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            always_failing()
        
        assert call_count == 3
    
    def test_specific_exception_types(self):
        """Test retry only on specific exception types."""
        call_count = 0
        
        @with_retry(
            max_retries=3,
            retryable_exceptions=(ValueError, TypeError),
            backoff_factor=0.1
        )
        def specific_exception_func(error_type):
            nonlocal call_count
            call_count += 1
            if error_type == "value":
                raise ValueError("Value error")
            elif error_type == "key":
                raise KeyError("Key error")
            return "success"
        
        # Should retry on ValueError
        call_count = 0
        with pytest.raises(ValueError):
            specific_exception_func("value")
        assert call_count == 3
        
        # Should not retry on KeyError
        call_count = 0
        with pytest.raises(KeyError):
            specific_exception_func("key")
        assert call_count == 1
    
    def test_retryable_error_patterns(self):
        """Test retry based on error message patterns."""
        call_count = 0
        
        @with_retry(
            max_retries=3,
            retryable_errors=["rate limit", "timeout"],
            backoff_factor=0.1
        )
        def pattern_based_func(error_msg):
            nonlocal call_count
            call_count += 1
            raise Exception(error_msg)
        
        # Should retry on rate limit
        call_count = 0
        with pytest.raises(Exception):
            pattern_based_func("Hit rate limit")
        assert call_count == 3
        
        # Should not retry on other errors
        call_count = 0
        with pytest.raises(Exception):
            pattern_based_func("Permission denied")
        assert call_count == 1
    
    @patch('time.sleep')
    def test_backoff_timing(self, mock_sleep):
        """Test that backoff delays are applied correctly."""
        @with_retry(
            max_retries=4,
            backoff_factor=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=False
        )
        def failing_func():
            raise Exception("rate limit exceeded")
        
        with pytest.raises(Exception):
            failing_func()
        
        # Check sleep calls (1, 2, 4 seconds)
        assert mock_sleep.call_count == 3
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_times == [1.0, 2.0, 4.0]
    
    @patch('time.sleep')
    @patch('random.random', return_value=0.5)
    def test_jitter(self, mock_random, mock_sleep):
        """Test that jitter is applied to delays."""
        @with_retry(
            max_retries=3,
            backoff_factor=2.0,
            jitter=True
        )
        def failing_func():
            raise Exception("timeout")
        
        with pytest.raises(Exception):
            failing_func()
        
        # With jitter, delays should be multiplied by (0.5 + 0.5) = 1.0
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_times == [1.0, 2.0]  # (1 * 1.0, 2 * 1.0)
    
    def test_different_strategies(self):
        """Test different retry strategies."""
        strategies_and_expected = [
            (RetryStrategy.LINEAR, [2.0, 4.0]),
            (RetryStrategy.CONSTANT, [2.0, 2.0]),
            (RetryStrategy.FIBONACCI, [1.0, 1.0])
        ]
        
        for strategy, expected_delays in strategies_and_expected:
            with patch('time.sleep') as mock_sleep:
                @with_retry(
                    max_retries=3,
                    backoff_factor=2.0,
                    strategy=strategy,
                    jitter=False
                )
                def failing_func():
                    raise Exception("connection timeout")
                
                with pytest.raises(Exception):
                    failing_func()
                
                sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_times == expected_delays
    
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_logging(self, mock_error, mock_warning):
        """Test that appropriate logs are generated."""
        @with_retry(max_retries=2, backoff_factor=0.1)
        def failing_func():
            raise Exception("503 Service Unavailable")
        
        with pytest.raises(Exception):
            failing_func()
        
        # Should have warning for retry attempt
        assert mock_warning.called
        warning_msg = mock_warning.call_args[0][0]
        assert "Retryable error on attempt" in warning_msg
        
        # Should have error for final failure
        assert mock_error.called
        error_msg = mock_error.call_args[0][0]
        assert "Failed after 2 attempts" in error_msg


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        breaker = CircuitBreaker()
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 60
        assert breaker._failure_count == 0
        assert breaker._state == CircuitState.CLOSED
    
    def test_successful_calls(self):
        """Test that successful calls keep circuit closed."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
        
        # Multiple successful calls
        for _ in range(10):
            result = breaker.call(success_func)
            assert result == "success"
            assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_opens_on_failures(self):
        """Test that circuit opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise Exception("Service error")
        
        # Fail up to threshold
        for i in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_func)
            
            if i < 2:
                assert breaker.state == CircuitState.CLOSED
            else:
                assert breaker.state == CircuitState.OPEN
    
    def test_open_circuit_rejects_calls(self):
        """Test that open circuit rejects calls."""
        breaker = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise Exception("Service error")
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        
        # Further calls should be rejected
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            breaker.call(lambda: "success")
    
    def test_half_open_state(self):
        """Test transition to half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        def failing_func():
            raise Exception("Service error")
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN
    
    def test_recovery_from_half_open(self):
        """Test successful recovery from half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(lambda: (_ for _ in ()).throw(Exception("error")))
        
        # Wait for half-open
        time.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Successful call should close circuit
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
    
    def test_failure_in_half_open_reopens(self):
        """Test that failure in half-open state reopens circuit."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(lambda: (_ for _ in ()).throw(Exception("error")))
        
        # Wait for half-open
        time.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure should reopen
        with pytest.raises(Exception):
            breaker.call(lambda: (_ for _ in ()).throw(Exception("still failing")))
        
        assert breaker.state == CircuitState.OPEN
    
    def test_decorator_usage(self):
        """Test circuit breaker as decorator."""
        breaker = CircuitBreaker(failure_threshold=2)
        call_count = 0
        
        @breaker
        def decorated_func(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise Exception("Decorated failure")
            return "success"
        
        # Successful calls
        assert decorated_func() == "success"
        assert decorated_func() == "success"
        
        # Failures to open circuit
        with pytest.raises(Exception):
            decorated_func(should_fail=True)
        with pytest.raises(Exception):
            decorated_func(should_fail=True)
        
        # Circuit should be open
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            decorated_func()
    
    def test_specific_exception_type(self):
        """Test monitoring specific exception types."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ValueError
        )
        
        def multi_error_func(error_type):
            if error_type == "value":
                raise ValueError("Value error")
            elif error_type == "key":
                raise KeyError("Key error")
            return "success"
        
        # KeyError shouldn't count toward failures
        with pytest.raises(KeyError):
            breaker.call(multi_error_func, "key")
        assert breaker._failure_count == 0
        
        # ValueError should count
        with pytest.raises(ValueError):
            breaker.call(multi_error_func, "value")
        assert breaker._failure_count == 1


class TestRateLimiter:
    """Test suite for RateLimiter class."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate=10.0, burst=20)
        assert limiter.rate == 10.0
        assert limiter.burst == 20
        assert limiter._tokens == 20
    
    def test_token_consumption(self):
        """Test basic token consumption."""
        limiter = RateLimiter(rate=10.0, burst=10)
        
        # Should be able to consume tokens immediately
        wait_time = limiter.acquire(5)
        assert wait_time == 0.0
        assert limiter._tokens == 5
        
        # Consume remaining tokens
        wait_time = limiter.acquire(5)
        assert wait_time == 0.0
        assert limiter._tokens == 0
    
    def test_token_regeneration(self):
        """Test that tokens regenerate over time."""
        limiter = RateLimiter(rate=10.0, burst=10)
        
        # Consume all tokens
        limiter.acquire(10)
        assert limiter._tokens == 0
        
        # Wait for regeneration
        time.sleep(0.5)  # Should regenerate 5 tokens
        
        # Should be able to acquire some tokens
        wait_time = limiter.acquire(3)
        assert wait_time == 0.0
    
    def test_burst_limit(self):
        """Test that tokens don't exceed burst limit."""
        limiter = RateLimiter(rate=10.0, burst=5)
        
        # Wait for potential regeneration
        time.sleep(1.0)
        
        # Tokens should be capped at burst
        limiter.acquire(0)  # Update tokens
        assert limiter._tokens <= 5
    
    def test_waiting_for_tokens(self):
        """Test waiting when tokens aren't available."""
        limiter = RateLimiter(rate=100.0, burst=1)
        
        # Consume the token
        limiter.acquire(1)
        
        # Try to acquire another token
        start = time.time()
        wait_time = limiter.acquire(1)
        elapsed = time.time() - start
        
        # Should have waited approximately 1/100 second
        assert wait_time > 0
        assert 0.005 < elapsed < 0.02  # Some tolerance for timing
    
    def test_decorator_usage(self):
        """Test rate limiter as decorator."""
        limiter = RateLimiter(rate=100.0, burst=2)
        call_times = []
        
        @limiter
        def rate_limited_func():
            call_times.append(time.time())
            return "success"
        
        # First calls should be immediate
        rate_limited_func()
        rate_limited_func()
        
        # Third call should be delayed
        rate_limited_func()
        
        # Check timing
        assert len(call_times) == 3
        assert call_times[1] - call_times[0] < 0.01  # First two immediate
        assert call_times[2] - call_times[1] > 0.005  # Third delayed
    
    def test_multiple_token_request(self):
        """Test requesting multiple tokens at once."""
        limiter = RateLimiter(rate=10.0, burst=10)
        
        # Request more tokens than available
        limiter._tokens = 2
        start = time.time()
        wait_time = limiter.acquire(5)
        elapsed = time.time() - start
        
        # Should wait for (5-2)/10 = 0.3 seconds
        assert 0.25 < elapsed < 0.35


class TestRetryWithFallback:
    """Test suite for retry_with_fallback function."""
    
    def test_primary_succeeds(self):
        """Test when primary function succeeds."""
        primary_calls = 0
        fallback_calls = 0
        
        def primary():
            nonlocal primary_calls
            primary_calls += 1
            return "primary result"
        
        def fallback():
            nonlocal fallback_calls
            fallback_calls += 1
            return "fallback result"
        
        executor = retry_with_fallback(primary, fallback)
        result = executor()
        
        assert result == "primary result"
        assert primary_calls == 1
        assert fallback_calls == 0
    
    def test_primary_fails_fallback_succeeds(self):
        """Test fallback when primary fails."""
        primary_calls = 0
        fallback_calls = 0
        
        def primary():
            nonlocal primary_calls
            primary_calls += 1
            raise Exception("Primary failed")
        
        def fallback():
            nonlocal fallback_calls
            fallback_calls += 1
            return "fallback result"
        
        executor = retry_with_fallback(primary, fallback, max_retries=3)
        result = executor()
        
        assert result == "fallback result"
        assert primary_calls == 3
        assert fallback_calls == 1
    
    def test_both_fail(self):
        """Test when both primary and fallback fail."""
        def primary():
            raise ValueError("Primary failed")
        
        def fallback():
            raise Exception("Fallback failed")
        
        executor = retry_with_fallback(primary, fallback, max_retries=2)
        
        # Should raise the primary exception
        with pytest.raises(ValueError, match="Primary failed"):
            executor()
    
    def test_with_arguments(self):
        """Test passing arguments to functions."""
        def primary(x, y, z=3):
            return x + y + z
        
        def fallback(x, y, z=3):
            return (x + y) * z
        
        executor = retry_with_fallback(primary, fallback)
        result = executor(1, 2, z=4)
        assert result == 7
    
    def test_primary_eventually_succeeds(self):
        """Test primary succeeds after retries."""
        attempt = 0
        
        def primary():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise Exception("Temporary failure")
            return "success after retries"
        
        def fallback():
            return "fallback"
        
        executor = retry_with_fallback(primary, fallback, max_retries=3)
        result = executor()
        
        assert result == "success after retries"
        assert attempt == 3
    
    @patch('time.sleep')
    def test_exponential_backoff(self, mock_sleep):
        """Test exponential backoff between retries."""
        def primary():
            raise Exception("Always fails")
        
        def fallback():
            return "fallback"
        
        executor = retry_with_fallback(primary, fallback, max_retries=3)
        executor()
        
        # Check sleep calls (1, 2, 4 seconds)
        assert mock_sleep.call_count == 2  # max_retries - 1
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_times == [1, 2]


class TestResilientCall:
    """Test suite for resilient_call function."""
    
    def test_basic_call(self):
        """Test basic function call without protection."""
        def simple_func(x, y):
            return x + y
        
        result = resilient_call(simple_func, 1, 2)
        assert result == 3
    
    def test_with_retry(self):
        """Test resilient call with retry."""
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("connection timeout")
            return "success"
        
        result = resilient_call(flaky_func, max_retries=3)
        assert result == "success"
        assert call_count == 3
    
    def test_with_circuit_breaker(self):
        """Test resilient call with circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise Exception("Service error")
        
        # First call should fail and open circuit
        with pytest.raises(Exception):
            resilient_call(failing_func, circuit_breaker=breaker)
        
        # Second call should be rejected by circuit breaker
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            resilient_call(failing_func, circuit_breaker=breaker)
    
    def test_with_rate_limiter(self):
        """Test resilient call with rate limiter."""
        limiter = RateLimiter(rate=100.0, burst=1)
        call_times = []
        
        def timed_func():
            call_times.append(time.time())
            return "success"
        
        # Make multiple calls
        resilient_call(timed_func, rate_limiter=limiter)
        resilient_call(timed_func, rate_limiter=limiter)
        
        # Second call should be delayed
        assert len(call_times) == 2
        assert call_times[1] - call_times[0] > 0.005
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGALRM'),
        reason="Timeout test requires SIGALRM support"
    )
    def test_with_timeout(self):
        """Test resilient call with timeout."""
        def slow_func():
            time.sleep(2)
            return "too late"
        
        with pytest.raises(TimeoutError):
            resilient_call(slow_func, timeout=0.5)
    
    def test_combined_protections(self):
        """Test with multiple protection mechanisms."""
        breaker = CircuitBreaker(failure_threshold=5)
        limiter = RateLimiter(rate=10.0, burst=5)
        call_count = 0
        
        def protected_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("rate limit exceeded")
            return "success"
        
        result = resilient_call(
            protected_func,
            max_retries=5,
            circuit_breaker=breaker,
            rate_limiter=limiter
        )
        
        assert result == "success"
        assert call_count == 3


class TestCustomExceptions:
    """Test suite for custom exception classes."""
    
    def test_exception_hierarchy(self):
        """Test exception class hierarchy."""
        assert issubclass(RetryableError, Exception)
        assert issubclass(TransientError, RetryableError)
        assert issubclass(RateLimitError, RetryableError)
    
    def test_exception_creation(self):
        """Test creating custom exceptions."""
        e1 = RetryableError("Base retryable error")
        assert str(e1) == "Base retryable error"
        
        e2 = TransientError("Temporary issue")
        assert str(e2) == "Temporary issue"
        assert isinstance(e2, RetryableError)
        
        e3 = RateLimitError("Rate limit hit")
        assert str(e3) == "Rate limit hit"
        assert isinstance(e3, RetryableError)
    
    def test_with_retry_decorator_custom_exceptions(self):
        """Test retry decorator with custom exceptions."""
        call_count = 0
        
        @with_retry(
            max_retries=3,
            retryable_exceptions=(TransientError, RateLimitError),
            backoff_factor=0.1
        )
        def custom_exception_func(error_type):
            nonlocal call_count
            call_count += 1
            
            if error_type == "transient":
                raise TransientError("Temporary failure")
            elif error_type == "rate_limit":
                raise RateLimitError("Too many requests")
            elif error_type == "permanent":
                raise ValueError("Permanent failure")
            return "success"
        
        # Should retry on TransientError
        call_count = 0
        with pytest.raises(TransientError):
            custom_exception_func("transient")
        assert call_count == 3
        
        # Should retry on RateLimitError
        call_count = 0
        with pytest.raises(RateLimitError):
            custom_exception_func("rate_limit")
        assert call_count == 3
        
        # Should not retry on ValueError
        call_count = 0
        with pytest.raises(ValueError):
            custom_exception_func("permanent")
        assert call_count == 1


class TestIntegrationScenarios:
    """Integration tests for retry utilities."""
    
    def test_api_client_scenario(self):
        """Test simulated API client with full protection."""
        # Simulate an API client
        class APIClient:
            def __init__(self):
                self.call_count = 0
                self.breaker = CircuitBreaker(failure_threshold=3)
                self.limiter = RateLimiter(rate=5.0, burst=10)
            
            @with_retry(max_retries=3, retryable_errors=["503", "timeout"])
            def get_data(self, endpoint):
                self.call_count += 1
                
                # Simulate various failures
                if self.call_count <= 2:
                    raise Exception("503 Service Unavailable")
                elif self.call_count == 3:
                    return {"data": "success"}
                else:
                    raise Exception("Unexpected error")
        
        client = APIClient()
        
        # Use resilient_call for full protection
        result = resilient_call(
            client.get_data,
            "/api/data",
            circuit_breaker=client.breaker,
            rate_limiter=client.limiter
        )
        
        assert result == {"data": "success"}
        assert client.call_count == 3
    
    def test_cascading_fallback_scenario(self):
        """Test cascading fallback pattern."""
        def primary_service():
            raise Exception("Primary service down")
        
        def secondary_service():
            raise Exception("Secondary service down")
        
        def cache_service():
            return {"data": "from cache", "stale": True}
        
        # Try primary with fallback to secondary
        primary_with_secondary = retry_with_fallback(
            primary_service,
            secondary_service,
            max_retries=2
        )
        
        # Then fallback to cache
        final_executor = retry_with_fallback(
            primary_with_secondary,
            cache_service,
            max_retries=1
        )
        
        result = final_executor()
        assert result == {"data": "from cache", "stale": True}
    
    def test_gradual_recovery_scenario(self):
        """Test gradual recovery with circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        recovery_stage = 0
        
        def recovering_service():
            nonlocal recovery_stage
            recovery_stage += 1
            
            if recovery_stage <= 2:
                raise Exception("Still recovering")
            elif recovery_stage == 3:
                raise Exception("Almost there")
            else:
                return "Fully recovered"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(recovering_service)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for half-open
        time.sleep(1.1)
        
        # First recovery attempt fails
        with pytest.raises(Exception):
            breaker.call(recovering_service)
        assert breaker.state == CircuitState.OPEN
        
        # Wait again
        time.sleep(1.1)
        
        # Second recovery attempt succeeds
        result = breaker.call(recovering_service)
        assert result == "Fully recovered"
        assert breaker.state == CircuitState.CLOSED


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_retries(self):
        """Test with zero retries."""
        @with_retry(max_retries=0)
        def no_retry_func():
            raise Exception("Fails immediately")
        
        # Should fail without any retries
        with pytest.raises(Exception, match="Fails immediately"):
            no_retry_func()
    
    def test_negative_parameters(self):
        """Test handling of negative parameters."""
        # RateLimiter with negative rate should still work
        limiter = RateLimiter(rate=-1.0, burst=1)
        # Should not be able to regenerate tokens
        limiter._tokens = 0
        
        # Circuit breaker with negative threshold
        breaker = CircuitBreaker(failure_threshold=-1, recovery_timeout=1)
        # Should never open
        for _ in range(10):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception()))
            except:
                pass
        assert breaker.state == CircuitState.CLOSED
    
    def test_very_long_delays(self):
        """Test handling of very long delays."""
        with patch('time.sleep') as mock_sleep:
            @with_retry(
                max_retries=2,
                backoff_factor=1000.0,
                max_delay=5.0,
                jitter=False
            )
            def long_delay_func():
                raise Exception("timeout")
            
            with pytest.raises(Exception):
                long_delay_func()
            
            # Delays should be capped at max_delay
            sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
            assert all(t <= 5.0 for t in sleep_times)
    
    def test_function_with_side_effects(self):
        """Test retry with functions that have side effects."""
        side_effects = []
        
        @with_retry(max_retries=3, backoff_factor=0.1)
        def side_effect_func():
            side_effects.append(len(side_effects))
            if len(side_effects) < 3:
                raise Exception("Not ready")
            return "done"
        
        result = side_effect_func()
        assert result == "done"
        assert side_effects == [0, 1, 2]
    
    def test_concurrent_rate_limiting(self):
        """Test rate limiter with concurrent access."""
        import threading
        
        limiter = RateLimiter(rate=10.0, burst=5)
        results = []
        
        def concurrent_acquire():
            wait = limiter.acquire(1)
            results.append(time.time())
        
        # Start multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=concurrent_acquire)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # First 5 should be immediate, rest should be spread out
        assert len(results) == 10
        
        # Sort results to check timing
        results.sort()
        
        # First 5 should be very close together
        first_five_span = results[4] - results[0]
        assert first_five_span < 0.1
        
        # Last 5 should be spread over ~0.5 seconds (5 tokens at 10/sec)
        last_five_span = results[9] - results[4]
        assert 0.4 < last_five_span < 0.6