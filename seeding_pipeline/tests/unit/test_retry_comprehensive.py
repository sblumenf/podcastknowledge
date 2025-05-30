"""Comprehensive tests for retry utilities."""

import pytest
from typing import Optional, Callable, Any, List, Dict
from unittest.mock import Mock, patch, call
import time
import asyncio
from datetime import datetime, timedelta
import random

from src.utils.retry import (
    RetryError,
    RetryExhausted,
    RetryConfig,
    RetryStrategy,
    ExponentialBackoff,
    LinearBackoff,
    FibonacciBackoff,
    RandomJitter,
    FullJitter,
    DecorrelatedJitter,
    RetryPolicy,
    CircuitBreaker,
    CircuitState,
    retry,
    async_retry,
    with_retry,
    RetryContext,
    RetryStats,
    create_retry_policy,
    should_retry,
    calculate_backoff,
    RetryableError,
    NonRetryableError,
    is_retryable,
)


class TestRetryConfig:
    """Test RetryConfig class."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter == True
        assert config.retry_on == (Exception,)
        assert config.retry_on_result is None
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        def custom_retry_on_result(result):
            return result is None
        
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
            retry_on=(ValueError, TypeError),
            retry_on_result=custom_retry_on_result
        )
        
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
        assert config.retry_on == (ValueError, TypeError)
        assert config.retry_on_result is custom_retry_on_result
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test invalid max_attempts
        with pytest.raises(ValueError, match="max_attempts must be positive"):
            RetryConfig(max_attempts=0)
        
        # Test invalid delays
        with pytest.raises(ValueError, match="initial_delay must be positive"):
            RetryConfig(initial_delay=-1)
        
        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryConfig(initial_delay=10, max_delay=5)
        
        # Test invalid exponential_base
        with pytest.raises(ValueError, match="exponential_base must be > 1"):
            RetryConfig(exponential_base=0.5)
    
    def test_config_copy(self):
        """Test configuration copying."""
        original = RetryConfig(max_attempts=5, initial_delay=2.0)
        copy = original.copy(max_attempts=10)
        
        assert original.max_attempts == 5
        assert copy.max_attempts == 10
        assert copy.initial_delay == 2.0  # Inherited from original


class TestRetryStrategies:
    """Test different retry strategies."""
    
    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        strategy = ExponentialBackoff(base=2.0, initial_delay=1.0)
        
        assert strategy.get_delay(0) == 1.0  # 1 * 2^0
        assert strategy.get_delay(1) == 2.0  # 1 * 2^1
        assert strategy.get_delay(2) == 4.0  # 1 * 2^2
        assert strategy.get_delay(3) == 8.0  # 1 * 2^3
    
    def test_exponential_backoff_with_max_delay(self):
        """Test exponential backoff with maximum delay."""
        strategy = ExponentialBackoff(base=2.0, initial_delay=1.0, max_delay=5.0)
        
        assert strategy.get_delay(0) == 1.0
        assert strategy.get_delay(1) == 2.0
        assert strategy.get_delay(2) == 4.0
        assert strategy.get_delay(3) == 5.0  # Capped at max_delay
        assert strategy.get_delay(10) == 5.0  # Still capped
    
    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        strategy = LinearBackoff(initial_delay=1.0, increment=0.5)
        
        assert strategy.get_delay(0) == 1.0
        assert strategy.get_delay(1) == 1.5
        assert strategy.get_delay(2) == 2.0
        assert strategy.get_delay(3) == 2.5
    
    def test_fibonacci_backoff(self):
        """Test Fibonacci backoff strategy."""
        strategy = FibonacciBackoff(initial_delay=1.0)
        
        assert strategy.get_delay(0) == 1.0  # F(0) = 1
        assert strategy.get_delay(1) == 1.0  # F(1) = 1
        assert strategy.get_delay(2) == 2.0  # F(2) = 2
        assert strategy.get_delay(3) == 3.0  # F(3) = 3
        assert strategy.get_delay(4) == 5.0  # F(4) = 5
        assert strategy.get_delay(5) == 8.0  # F(5) = 8
    
    def test_custom_strategy(self):
        """Test custom retry strategy."""
        class CustomStrategy(RetryStrategy):
            def get_delay(self, attempt: int) -> float:
                # Square the attempt number
                return float(attempt ** 2)
        
        strategy = CustomStrategy()
        assert strategy.get_delay(0) == 0.0
        assert strategy.get_delay(1) == 1.0
        assert strategy.get_delay(2) == 4.0
        assert strategy.get_delay(3) == 9.0


class TestJitterStrategies:
    """Test jitter strategies."""
    
    def test_random_jitter(self):
        """Test random jitter strategy."""
        jitter = RandomJitter(jitter_factor=0.1)
        base_delay = 10.0
        
        # Test multiple times to ensure randomness
        delays = [jitter.add_jitter(base_delay) for _ in range(100)]
        
        # All delays should be within ±10% of base
        assert all(9.0 <= d <= 11.0 for d in delays)
        
        # Should have some variation
        assert len(set(delays)) > 50
    
    def test_full_jitter(self):
        """Test full jitter strategy."""
        jitter = FullJitter()
        base_delay = 10.0
        
        delays = [jitter.add_jitter(base_delay) for _ in range(100)]
        
        # All delays should be between 0 and base_delay
        assert all(0 <= d <= base_delay for d in delays)
        
        # Should have good distribution
        assert min(delays) < 1.0  # Some very small delays
        assert max(delays) > 9.0  # Some near maximum delays
    
    def test_decorrelated_jitter(self):
        """Test decorrelated jitter strategy."""
        jitter = DecorrelatedJitter(initial_delay=1.0)
        
        # First delay should be close to initial
        delay1 = jitter.add_jitter(10.0)
        assert 0 <= delay1 <= 3.0
        
        # Subsequent delays should be decorrelated
        delays = []
        for _ in range(10):
            delay = jitter.add_jitter(10.0)
            delays.append(delay)
        
        # Should have variation but bounded
        assert all(0 <= d <= 30.0 for d in delays)
    
    def test_no_jitter(self):
        """Test no jitter (identity function)."""
        class NoJitter:
            def add_jitter(self, delay: float) -> float:
                return delay
        
        jitter = NoJitter()
        assert jitter.add_jitter(5.0) == 5.0
        assert jitter.add_jitter(10.0) == 10.0


class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        mock_func = Mock(return_value="success")
        
        @retry(max_attempts=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_exception(self):
        """Test retry on exception."""
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        
        @retry(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_retry_exhausted(self):
        """Test retry exhaustion."""
        mock_func = Mock(side_effect=ValueError("Always fails"))
        
        @retry(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(RetryExhausted) as exc_info:
            test_func()
        
        assert mock_func.call_count == 3
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)
    
    def test_retry_specific_exceptions(self):
        """Test retry only specific exceptions."""
        mock_func = Mock(side_effect=[ValueError(), TypeError(), "success"])
        
        @retry(max_attempts=3, retry_on=(ValueError,), initial_delay=0.01)
        def test_func():
            return mock_func()
        
        # Should retry ValueError but not TypeError
        with pytest.raises(TypeError):
            test_func()
        
        assert mock_func.call_count == 2
    
    def test_retry_on_result(self):
        """Test retry based on result."""
        mock_func = Mock(side_effect=[None, None, "success"])
        
        @retry(
            max_attempts=3,
            retry_on_result=lambda x: x is None,
            initial_delay=0.01
        )
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_retry_with_arguments(self):
        """Test retry with function arguments."""
        mock_func = Mock(side_effect=[ValueError(), "success"])
        
        @retry(max_attempts=2, initial_delay=0.01)
        def test_func(a, b, c=None):
            return mock_func(a, b, c)
        
        result = test_func(1, 2, c=3)
        assert result == "success"
        assert mock_func.call_count == 2
        mock_func.assert_called_with(1, 2, 3)
    
    def test_retry_with_callback(self):
        """Test retry with callback functions."""
        on_retry_calls = []
        on_success_calls = []
        on_failure_calls = []
        
        def on_retry(exc, attempt):
            on_retry_calls.append((exc, attempt))
        
        def on_success(result, attempts):
            on_success_calls.append((result, attempts))
        
        def on_failure(exc, attempts):
            on_failure_calls.append((exc, attempts))
        
        mock_func = Mock(side_effect=[ValueError("Err1"), ValueError("Err2"), "success"])
        
        @retry(
            max_attempts=3,
            initial_delay=0.01,
            on_retry=on_retry,
            on_success=on_success,
            on_failure=on_failure
        )
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        
        # Check callbacks
        assert len(on_retry_calls) == 2
        assert all(isinstance(exc, ValueError) for exc, _ in on_retry_calls)
        assert [attempt for _, attempt in on_retry_calls] == [1, 2]
        
        assert len(on_success_calls) == 1
        assert on_success_calls[0] == ("success", 3)
        
        assert len(on_failure_calls) == 0


class TestAsyncRetry:
    """Test async retry functionality."""
    
    @pytest.mark.asyncio
    async def test_async_successful_call(self):
        """Test successful async call doesn't retry."""
        mock_func = Mock(return_value="success")
        
        @async_retry(max_attempts=3)
        async def test_func():
            return mock_func()
        
        result = await test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_on_exception(self):
        """Test async retry on exception."""
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        
        @async_retry(max_attempts=3, initial_delay=0.01)
        async def test_func():
            return mock_func()
        
        result = await test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_with_async_function(self):
        """Test retry with actual async function."""
        call_count = 0
        
        @async_retry(max_attempts=3, initial_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise ValueError("Not yet")
            
            await asyncio.sleep(0.01)  # Simulate async work
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_concurrent_retries(self):
        """Test concurrent async retries."""
        call_counts = {"func1": 0, "func2": 0}
        
        @async_retry(max_attempts=3, initial_delay=0.01)
        async def test_func(name):
            call_counts[name] += 1
            
            if call_counts[name] < 2:
                raise ValueError(f"{name} not ready")
            
            await asyncio.sleep(0.01)
            return f"{name} success"
        
        # Run concurrently
        results = await asyncio.gather(
            test_func("func1"),
            test_func("func2")
        )
        
        assert results == ["func1 success", "func2 success"]
        assert call_counts["func1"] == 2
        assert call_counts["func2"] == 2


class TestRetryContext:
    """Test retry context functionality."""
    
    def test_retry_context_tracking(self):
        """Test retry context tracks attempts correctly."""
        contexts = []
        
        def capture_context(ctx: RetryContext):
            contexts.append({
                "attempt": ctx.attempt,
                "total_delay": ctx.total_delay,
                "start_time": ctx.start_time
            })
        
        mock_func = Mock(side_effect=[ValueError(), ValueError(), "success"])
        
        @retry(max_attempts=3, initial_delay=0.01, before_retry=capture_context)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        
        # Check context progression
        assert len(contexts) == 2  # Called before 2nd and 3rd attempts
        assert contexts[0]["attempt"] == 1
        assert contexts[1]["attempt"] == 2
        assert contexts[0]["total_delay"] < contexts[1]["total_delay"]
    
    def test_retry_context_in_function(self):
        """Test accessing retry context within function."""
        attempts_seen = []
        
        @retry(max_attempts=3, initial_delay=0.01, pass_context=True)
        def test_func(ctx: RetryContext):
            attempts_seen.append(ctx.attempt)
            if ctx.attempt < 3:
                raise ValueError("Not yet")
            return f"Success on attempt {ctx.attempt}"
        
        result = test_func()
        assert result == "Success on attempt 3"
        assert attempts_seen == [1, 2, 3]
    
    def test_retry_context_history(self):
        """Test retry context maintains history."""
        @retry(max_attempts=3, initial_delay=0.01, track_history=True, pass_context=True)
        def test_func(ctx: RetryContext):
            if ctx.attempt == 1:
                raise ValueError("First error")
            elif ctx.attempt == 2:
                raise TypeError("Second error")
            else:
                # Check history
                assert len(ctx.exception_history) == 2
                assert isinstance(ctx.exception_history[0], ValueError)
                assert isinstance(ctx.exception_history[1], TypeError)
                return "success"
        
        result = test_func()
        assert result == "success"


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            expected_exception=ValueError
        )
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.current_failures == 0
        
        # Successful calls don't affect state
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.current_failures == 0
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1
        )
        
        # Record failures
        for i in range(3):
            breaker.record_failure(ValueError(f"Error {i}"))
            if i < 2:
                assert breaker.state == CircuitState.CLOSED
            else:
                assert breaker.state == CircuitState.OPEN
        
        # Circuit is now open
        assert breaker.current_failures == 3
        
        # Calls should fail fast
        assert not breaker.can_proceed()
    
    def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker half-open state."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )
        
        # Open the circuit
        breaker.record_failure(ValueError())
        breaker.record_failure(ValueError())
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.can_proceed()
        
        # Success closes the circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.current_failures == 0
    
    def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker failure in half-open state."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )
        
        # Open the circuit
        breaker.record_failure(ValueError())
        breaker.record_failure(ValueError())
        
        # Wait for recovery timeout
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure in half-open reopens immediately
        breaker.record_failure(ValueError())
        assert breaker.state == CircuitState.OPEN
    
    def test_circuit_breaker_with_retry(self):
        """Test circuit breaker integration with retry."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )
        
        call_count = 0
        
        @retry(
            max_attempts=5,
            initial_delay=0.01,
            circuit_breaker=breaker
        )
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(RetryExhausted):
            test_func()
        
        # Should only be called twice before circuit opens
        assert call_count == 2
        assert breaker.state == CircuitState.OPEN
        
        # Further calls fail immediately
        call_count = 0
        with pytest.raises(CircuitBreakerOpen):
            test_func()
        assert call_count == 0


class TestRetryPolicy:
    """Test retry policy functionality."""
    
    def test_simple_retry_policy(self):
        """Test simple retry policy."""
        policy = RetryPolicy(
            should_retry=lambda e: isinstance(e, ValueError),
            max_attempts=3,
            backoff_strategy=LinearBackoff(1.0, 0.5)
        )
        
        assert policy.should_retry(ValueError())
        assert not policy.should_retry(TypeError())
        assert policy.get_delay(1) == 1.5
        assert policy.get_delay(2) == 2.0
    
    def test_complex_retry_policy(self):
        """Test complex retry policy with multiple conditions."""
        def should_retry_func(exception, attempt, elapsed_time):
            # Don't retry after 5 seconds
            if elapsed_time > 5.0:
                return False
            
            # Don't retry on specific error messages
            if str(exception) == "FATAL":
                return False
            
            # Retry temporary errors
            return isinstance(exception, (ValueError, IOError))
        
        policy = RetryPolicy(
            should_retry=should_retry_func,
            max_attempts=10,
            backoff_strategy=ExponentialBackoff(1.0, 2.0)
        )
        
        # Test various scenarios
        assert policy.should_retry(ValueError("Temp error"), 1, 1.0)
        assert not policy.should_retry(ValueError("FATAL"), 1, 1.0)
        assert not policy.should_retry(ValueError("Any"), 1, 6.0)
        assert not policy.should_retry(TypeError("Any"), 1, 1.0)
    
    def test_policy_chain(self):
        """Test chaining multiple retry policies."""
        # Policy 1: Retry ValueError up to 3 times
        policy1 = RetryPolicy(
            should_retry=lambda e: isinstance(e, ValueError),
            max_attempts=3
        )
        
        # Policy 2: Retry IOError up to 5 times with longer delays
        policy2 = RetryPolicy(
            should_retry=lambda e: isinstance(e, IOError),
            max_attempts=5,
            backoff_strategy=ExponentialBackoff(2.0, 2.0)
        )
        
        # Combine policies
        combined = RetryPolicy.combine([policy1, policy2])
        
        assert combined.should_retry(ValueError())
        assert combined.should_retry(IOError())
        assert not combined.should_retry(TypeError())


class TestRetryStats:
    """Test retry statistics tracking."""
    
    def test_retry_stats_collection(self):
        """Test collecting retry statistics."""
        stats = RetryStats()
        
        @retry(max_attempts=3, initial_delay=0.01, stats_collector=stats)
        def sometimes_fails(n):
            if n < 2:
                raise ValueError("Not yet")
            return "success"
        
        # Call multiple times
        sometimes_fails(3)  # Success on first try
        sometimes_fails(1)  # Success on third try
        
        assert stats.total_calls == 2
        assert stats.successful_calls == 2
        assert stats.failed_calls == 0
        assert stats.total_retries == 2  # Two retries for second call
        assert stats.total_time > 0
    
    def test_retry_stats_aggregation(self):
        """Test aggregating retry statistics."""
        stats = RetryStats()
        
        # Track individual operations
        with stats.track_operation("operation1"):
            time.sleep(0.01)
            stats.record_retry(ValueError("Error"))
        
        with stats.track_operation("operation2"):
            time.sleep(0.01)
            stats.record_success()
        
        # Check aggregated stats
        assert "operation1" in stats.operations
        assert "operation2" in stats.operations
        assert stats.operations["operation1"]["retries"] == 1
        assert stats.operations["operation2"]["retries"] == 0
    
    def test_retry_stats_reporting(self):
        """Test retry statistics reporting."""
        stats = RetryStats()
        
        # Simulate some operations
        for i in range(10):
            if i % 3 == 0:
                stats.record_retry(ValueError())
            stats.record_success()
        
        report = stats.generate_report()
        
        assert report["total_operations"] == 10
        assert report["retry_rate"] == 0.4  # 4 retries / 10 operations
        assert "average_retries_per_operation" in report
        assert "p95_retry_time" in report


class TestRetryHelpers:
    """Test retry helper functions."""
    
    def test_should_retry_helper(self):
        """Test should_retry helper function."""
        # Test with exception types
        assert should_retry(ValueError(), retry_on=(ValueError, TypeError))
        assert not should_retry(KeyError(), retry_on=(ValueError, TypeError))
        
        # Test with custom function
        def custom_check(exc):
            return "temporary" in str(exc).lower()
        
        assert should_retry(IOError("Temporary failure"), retry_on=custom_check)
        assert not should_retry(IOError("Permanent failure"), retry_on=custom_check)
    
    def test_calculate_backoff_helper(self):
        """Test calculate_backoff helper function."""
        # Exponential backoff
        assert calculate_backoff(0, strategy="exponential", base=2.0) == 1.0
        assert calculate_backoff(3, strategy="exponential", base=2.0) == 8.0
        
        # Linear backoff
        assert calculate_backoff(0, strategy="linear", increment=0.5) == 0.5
        assert calculate_backoff(3, strategy="linear", increment=0.5) == 2.0
        
        # Custom function
        custom_backoff = lambda n: n ** 2
        assert calculate_backoff(3, strategy=custom_backoff) == 9
    
    def test_is_retryable_helper(self):
        """Test is_retryable helper function."""
        # Test with RetryableError
        assert is_retryable(RetryableError("Temporary issue"))
        
        # Test with NonRetryableError
        assert not is_retryable(NonRetryableError("Permanent failure"))
        
        # Test with custom exceptions
        class CustomRetryable(Exception):
            retryable = True
        
        class CustomNonRetryable(Exception):
            retryable = False
        
        assert is_retryable(CustomRetryable())
        assert not is_retryable(CustomNonRetryable())
        
        # Test with standard exceptions (default behavior)
        assert is_retryable(IOError())  # Usually retryable
        assert not is_retryable(SyntaxError())  # Usually not retryable


class TestRetryPatterns:
    """Test common retry patterns."""
    
    def test_retry_with_fallback(self):
        """Test retry with fallback value."""
        primary_calls = 0
        fallback_calls = 0
        
        @retry(max_attempts=2, initial_delay=0.01)
        def primary_service():
            nonlocal primary_calls
            primary_calls += 1
            raise ValueError("Primary service down")
        
        def fallback_service():
            nonlocal fallback_calls
            fallback_calls += 1
            return "fallback result"
        
        def get_data():
            try:
                return primary_service()
            except RetryExhausted:
                return fallback_service()
        
        result = get_data()
        assert result == "fallback result"
        assert primary_calls == 2
        assert fallback_calls == 1
    
    def test_retry_with_cache(self):
        """Test retry with caching."""
        cache = {}
        service_calls = 0
        
        @retry(max_attempts=3, initial_delay=0.01)
        def expensive_operation(key):
            nonlocal service_calls
            
            # Check cache first
            if key in cache:
                return cache[key]
            
            service_calls += 1
            
            # Simulate flaky service
            if service_calls < 2:
                raise ValueError("Service temporarily unavailable")
            
            result = f"result_for_{key}"
            cache[key] = result
            return result
        
        # First call retries and succeeds
        result1 = expensive_operation("key1")
        assert result1 == "result_for_key1"
        assert service_calls == 2
        
        # Second call hits cache
        result2 = expensive_operation("key1")
        assert result2 == "result_for_key1"
        assert service_calls == 2  # No additional calls
    
    def test_retry_with_circuit_breaker_pattern(self):
        """Test retry with circuit breaker pattern."""
        class ServiceClient:
            def __init__(self):
                self.breaker = CircuitBreaker(
                    failure_threshold=2,
                    recovery_timeout=0.1
                )
                self.call_count = 0
            
            @retry(max_attempts=5, initial_delay=0.01)
            def call_service(self):
                if not self.breaker.can_proceed():
                    raise CircuitBreakerOpen("Circuit breaker is open")
                
                self.call_count += 1
                
                try:
                    # Simulate failures
                    if self.call_count <= 3:
                        raise ValueError("Service error")
                    
                    result = "success"
                    self.breaker.record_success()
                    return result
                    
                except Exception as e:
                    self.breaker.record_failure(e)
                    raise
        
        client = ServiceClient()
        
        # First call opens circuit after 2 failures
        with pytest.raises(RetryExhausted):
            client.call_service()
        
        assert client.call_count == 2
        assert client.breaker.state == CircuitState.OPEN
        
        # Immediate retry fails due to open circuit
        with pytest.raises(CircuitBreakerOpen):
            client.call_service()
        
        assert client.call_count == 2  # No additional calls
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Circuit should be half-open, call succeeds
        result = client.call_service()
        assert result == "success"
        assert client.breaker.state == CircuitState.CLOSED


class TestAdvancedRetryScenarios:
    """Test advanced retry scenarios."""
    
    def test_nested_retries(self):
        """Test nested retry decorators."""
        inner_calls = 0
        outer_calls = 0
        
        @retry(max_attempts=2, initial_delay=0.01)
        def inner_function():
            nonlocal inner_calls
            inner_calls += 1
            if inner_calls < 3:
                raise ValueError("Inner failure")
            return "inner success"
        
        @retry(max_attempts=2, initial_delay=0.01)
        def outer_function():
            nonlocal outer_calls
            outer_calls += 1
            try:
                return inner_function()
            except RetryExhausted:
                if outer_calls < 2:
                    raise ValueError("Outer failure")
                return "outer fallback"
        
        result = outer_function()
        
        # First outer call: inner retries twice and fails
        # Second outer call: inner succeeds on third total call
        assert inner_calls == 3
        assert outer_calls == 2
        assert result == "inner success"
    
    def test_retry_with_timeout(self):
        """Test retry with overall timeout."""
        start_time = time.time()
        attempts = 0
        
        @retry(
            max_attempts=10,
            initial_delay=0.5,
            max_total_time=1.0  # Overall timeout
        )
        def slow_operation():
            nonlocal attempts
            attempts += 1
            raise ValueError("Still failing")
        
        with pytest.raises(RetryExhausted) as exc_info:
            slow_operation()
        
        elapsed = time.time() - start_time
        
        # Should stop due to timeout, not max attempts
        assert attempts < 10
        assert elapsed < 1.5  # With some margin
        assert exc_info.value.reason == "timeout"
    
    def test_retry_with_adaptive_delay(self):
        """Test retry with adaptive delay based on error."""
        attempts = []
        
        def adaptive_delay(exception, attempt):
            if "rate_limit" in str(exception):
                return 2.0  # Longer delay for rate limits
            elif "timeout" in str(exception):
                return 0.5  # Shorter delay for timeouts
            else:
                return 1.0  # Default delay
        
        @retry(
            max_attempts=4,
            delay_function=adaptive_delay
        )
        def adaptive_operation():
            attempt = len(attempts) + 1
            attempts.append(time.time())
            
            if attempt == 1:
                raise ValueError("rate_limit exceeded")
            elif attempt == 2:
                raise ValueError("timeout error")
            elif attempt == 3:
                raise ValueError("generic error")
            else:
                return "success"
        
        start = time.time()
        result = adaptive_operation()
        
        assert result == "success"
        assert len(attempts) == 4
        
        # Check delays between attempts
        delays = []
        for i in range(1, len(attempts)):
            delays.append(attempts[i] - attempts[i-1])
        
        # First delay ~2.0s (rate limit)
        assert 1.8 < delays[0] < 2.2
        # Second delay ~0.5s (timeout)
        assert 0.3 < delays[1] < 0.7
        # Third delay ~1.0s (generic)
        assert 0.8 < delays[2] < 1.2