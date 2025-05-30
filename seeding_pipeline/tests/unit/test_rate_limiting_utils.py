"""Tests for rate limiting utilities."""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading

from src.utils.rate_limiting import (
    RateLimiter,
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
    FixedWindowRateLimiter,
    rate_limit,
    async_rate_limit,
    RateLimitExceeded,
    MultiRateLimiter,
    DistributedRateLimiter,
    AdaptiveRateLimiter,
    rate_limit_key,
    get_rate_limiter,
    clear_rate_limiters,
)


class TestRateLimiter:
    """Test base RateLimiter class."""
    
    def test_rate_limiter_basic(self):
        """Test basic rate limiter functionality."""
        limiter = RateLimiter(calls=5, period=1.0)
        
        assert limiter.calls == 5
        assert limiter.period == 1.0
        assert limiter.remaining_calls() == 5
    
    def test_rate_limiter_acquire(self):
        """Test acquiring permits."""
        limiter = RateLimiter(calls=3, period=1.0)
        
        # Should allow first 3 calls
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        
        # 4th call should be rate limited
        assert limiter.acquire() is False
        assert limiter.remaining_calls() == 0
    
    def test_rate_limiter_wait(self):
        """Test waiting for permit."""
        limiter = RateLimiter(calls=2, period=0.2)
        
        # Use up permits
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        
        # Wait should block until period expires
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start
        
        assert elapsed >= 0.19  # Close to period
        assert limiter.acquire() is True  # Should work after wait
    
    def test_rate_limiter_try_acquire(self):
        """Test non-blocking acquire."""
        limiter = RateLimiter(calls=1, period=1.0)
        
        # First should succeed
        assert limiter.try_acquire() is True
        
        # Second should fail without blocking
        start = time.time()
        assert limiter.try_acquire() is False
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should not block
    
    def test_rate_limiter_reset(self):
        """Test resetting rate limiter."""
        limiter = RateLimiter(calls=2, period=1.0)
        
        # Use up permits
        limiter.acquire()
        limiter.acquire()
        assert limiter.remaining_calls() == 0
        
        # Reset
        limiter.reset()
        assert limiter.remaining_calls() == 2


class TestTokenBucketRateLimiter:
    """Test TokenBucketRateLimiter implementation."""
    
    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)
        
        assert bucket.capacity == 10
        assert bucket.refill_rate == 5.0
        assert bucket.tokens == 10  # Starts full
    
    def test_token_bucket_consume(self):
        """Test consuming tokens."""
        bucket = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)
        
        # Consume some tokens
        assert bucket.consume(3) is True
        assert bucket.tokens == 7
        
        assert bucket.consume(5) is True
        assert bucket.tokens == 2
        
        # Try to consume more than available
        assert bucket.consume(3) is False
        assert bucket.tokens == 2  # Unchanged
    
    def test_token_bucket_refill(self):
        """Test token refill over time."""
        bucket = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        
        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0
        
        # Wait for refill
        time.sleep(0.5)
        
        # Should have ~5 tokens (10 tokens/sec * 0.5 sec)
        bucket._refill()
        assert 4 <= bucket.tokens <= 6
    
    def test_token_bucket_max_capacity(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucketRateLimiter(capacity=5, refill_rate=100.0)
        
        # Wait for potential overfill
        time.sleep(0.1)
        bucket._refill()
        
        # Should not exceed capacity
        assert bucket.tokens == 5
    
    def test_token_bucket_wait_for_tokens(self):
        """Test waiting for tokens to be available."""
        bucket = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)
        
        # Consume all tokens
        bucket.consume(5)
        
        # Wait for specific number of tokens
        start = time.time()
        bucket.wait_for_tokens(2)
        elapsed = time.time() - start
        
        # Should wait ~0.2 seconds (2 tokens at 10 tokens/sec)
        assert 0.15 <= elapsed <= 0.25
        assert bucket.consume(2) is True


class TestSlidingWindowRateLimiter:
    """Test SlidingWindowRateLimiter implementation."""
    
    def test_sliding_window_basic(self):
        """Test basic sliding window functionality."""
        limiter = SlidingWindowRateLimiter(calls=5, period=1.0)
        
        # Should allow 5 calls
        for _ in range(5):
            assert limiter.acquire() is True
        
        # 6th should fail
        assert limiter.acquire() is False
    
    def test_sliding_window_expiry(self):
        """Test that old calls expire from window."""
        limiter = SlidingWindowRateLimiter(calls=3, period=0.3)
        
        # Make 3 calls
        for _ in range(3):
            limiter.acquire()
            time.sleep(0.05)
        
        # Wait for first call to expire
        time.sleep(0.2)
        
        # Should allow new call as oldest expired
        assert limiter.acquire() is True
    
    def test_sliding_window_cleanup(self):
        """Test cleanup of old timestamps."""
        limiter = SlidingWindowRateLimiter(calls=100, period=0.1)
        
        # Make many calls
        for _ in range(50):
            limiter.acquire()
        
        # Wait for all to expire
        time.sleep(0.2)
        
        # Make new call to trigger cleanup
        limiter.acquire()
        
        # Old timestamps should be cleaned up
        assert len(limiter.calls) == 1


class TestFixedWindowRateLimiter:
    """Test FixedWindowRateLimiter implementation."""
    
    def test_fixed_window_basic(self):
        """Test basic fixed window functionality."""
        limiter = FixedWindowRateLimiter(calls=5, period=1.0)
        
        # Should allow 5 calls in current window
        for _ in range(5):
            assert limiter.acquire() is True
        
        # 6th should fail
        assert limiter.acquire() is False
    
    def test_fixed_window_reset(self):
        """Test window reset after period."""
        limiter = FixedWindowRateLimiter(calls=3, period=0.2)
        
        # Use up current window
        for _ in range(3):
            limiter.acquire()
        
        assert limiter.acquire() is False
        
        # Wait for new window
        time.sleep(0.21)
        
        # Should reset
        assert limiter.acquire() is True
        assert limiter.count == 1
    
    def test_fixed_window_boundary(self):
        """Test behavior at window boundaries."""
        limiter = FixedWindowRateLimiter(calls=2, period=0.5)
        
        # Make calls near end of window
        limiter.acquire()
        limiter.acquire()
        
        # Get time until next window
        time_to_next = limiter.time_until_reset()
        assert 0 <= time_to_next <= 0.5
        
        # Wait for reset
        time.sleep(time_to_next + 0.01)
        
        # Should work in new window
        assert limiter.acquire() is True


class TestRateLimitDecorators:
    """Test rate limiting decorators."""
    
    def test_rate_limit_decorator(self):
        """Test rate_limit decorator."""
        call_count = 0
        
        @rate_limit(calls=3, period=0.5)
        def limited_function():
            nonlocal call_count
            call_count += 1
            return call_count
        
        # First 3 calls should work
        assert limited_function() == 1
        assert limited_function() == 2
        assert limited_function() == 3
        
        # 4th should raise
        with pytest.raises(RateLimitExceeded):
            limited_function()
        
        # Wait for reset
        time.sleep(0.51)
        
        # Should work again
        assert limited_function() == 4
    
    def test_rate_limit_with_key(self):
        """Test rate limiting with key function."""
        @rate_limit(calls=2, period=1.0, key_func=lambda x: x)
        def limited_function(user_id):
            return f"Called by {user_id}"
        
        # Different keys have separate limits
        assert limited_function("user1") == "Called by user1"
        assert limited_function("user1") == "Called by user1"
        assert limited_function("user2") == "Called by user2"
        assert limited_function("user2") == "Called by user2"
        
        # Each key exhausted
        with pytest.raises(RateLimitExceeded):
            limited_function("user1")
        
        with pytest.raises(RateLimitExceeded):
            limited_function("user2")
    
    def test_rate_limit_custom_limiter(self):
        """Test rate limit with custom limiter."""
        bucket = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)
        
        @rate_limit(limiter=bucket)
        def limited_function():
            return "success"
        
        # Should use token bucket behavior
        for _ in range(5):
            assert limited_function() == "success"
        
        with pytest.raises(RateLimitExceeded):
            limited_function()
    
    def test_async_rate_limit(self):
        """Test async rate limiting."""
        @async_rate_limit(calls=2, period=0.5)
        async def async_limited():
            return "async result"
        
        async def test():
            # First 2 should work
            assert await async_limited() == "async result"
            assert await async_limited() == "async result"
            
            # 3rd should fail
            with pytest.raises(RateLimitExceeded):
                await async_limited()
        
        # Run async test
        asyncio.run(test())


class TestMultiRateLimiter:
    """Test MultiRateLimiter for complex rate limiting."""
    
    def test_multi_rate_limiter(self):
        """Test combining multiple rate limiters."""
        # Create multi-limiter with different windows
        multi = MultiRateLimiter([
            RateLimiter(calls=10, period=1.0),    # 10 per second
            RateLimiter(calls=50, period=60.0),   # 50 per minute
        ])
        
        # Should respect all limits
        for i in range(10):
            assert multi.acquire() is True
        
        # 11th call exceeds per-second limit
        assert multi.acquire() is False
    
    def test_multi_rate_limiter_different_types(self):
        """Test combining different limiter types."""
        multi = MultiRateLimiter([
            TokenBucketRateLimiter(capacity=5, refill_rate=5.0),
            FixedWindowRateLimiter(calls=20, period=10.0),
        ])
        
        # Should work with mixed types
        for _ in range(5):
            assert multi.acquire() is True
        
        # Token bucket exhausted
        assert multi.acquire() is False


class TestAdaptiveRateLimiter:
    """Test AdaptiveRateLimiter that adjusts based on response."""
    
    def test_adaptive_rate_limiter_basic(self):
        """Test basic adaptive rate limiting."""
        limiter = AdaptiveRateLimiter(
            initial_rate=10.0,
            min_rate=1.0,
            max_rate=100.0,
            increase_factor=2.0,
            decrease_factor=0.5
        )
        
        assert limiter.current_rate == 10.0
        
        # Success should increase rate
        limiter.record_success()
        assert limiter.current_rate == 20.0
        
        # Failure should decrease rate
        limiter.record_failure()
        assert limiter.current_rate == 10.0
    
    def test_adaptive_rate_limiter_bounds(self):
        """Test rate bounds are respected."""
        limiter = AdaptiveRateLimiter(
            initial_rate=50.0,
            min_rate=10.0,
            max_rate=100.0,
            increase_factor=3.0,
            decrease_factor=0.1
        )
        
        # Increase to max
        limiter.record_success()
        limiter.record_success()
        assert limiter.current_rate == 100.0  # Capped at max
        
        # Decrease to min
        for _ in range(5):
            limiter.record_failure()
        assert limiter.current_rate == 10.0  # Capped at min
    
    def test_adaptive_rate_limiter_with_backoff(self):
        """Test adaptive limiter with backoff on consecutive failures."""
        limiter = AdaptiveRateLimiter(
            initial_rate=20.0,
            consecutive_failures_threshold=3,
            backoff_factor=0.25
        )
        
        # Record consecutive failures
        limiter.record_failure()
        limiter.record_failure()
        assert limiter.current_rate == 5.0  # Normal decrease
        
        limiter.record_failure()  # 3rd consecutive
        assert limiter.current_rate == 1.25  # Aggressive backoff
        
        # Success resets consecutive counter
        limiter.record_success()
        assert limiter.consecutive_failures == 0


class TestDistributedRateLimiter:
    """Test DistributedRateLimiter for multi-instance scenarios."""
    
    def test_distributed_rate_limiter_basic(self):
        """Test basic distributed rate limiting."""
        # Mock Redis-like backend
        mock_backend = MagicMock()
        mock_backend.incr.return_value = 1
        mock_backend.expire.return_value = True
        
        limiter = DistributedRateLimiter(
            backend=mock_backend,
            key="api_limit",
            calls=100,
            period=60
        )
        
        assert limiter.acquire() is True
        mock_backend.incr.assert_called_with("api_limit:window")
        mock_backend.expire.assert_called()
    
    def test_distributed_rate_limiter_exceeded(self):
        """Test distributed limiter when limit exceeded."""
        mock_backend = MagicMock()
        mock_backend.incr.return_value = 101  # Over limit
        
        limiter = DistributedRateLimiter(
            backend=mock_backend,
            key="api_limit",
            calls=100,
            period=60
        )
        
        assert limiter.acquire() is False


class TestRateLimitingUtilities:
    """Test rate limiting utility functions."""
    
    def test_rate_limit_key(self):
        """Test generating rate limit keys."""
        # Basic key
        key = rate_limit_key("user", "123")
        assert key == "user:123"
        
        # Multiple parts
        key = rate_limit_key("api", "v1", "users", "list")
        assert key == "api:v1:users:list"
        
        # With None values
        key = rate_limit_key("user", None, "action")
        assert key == "user:None:action"
    
    def test_get_rate_limiter(self):
        """Test getting rate limiter instances."""
        # Get limiter
        limiter1 = get_rate_limiter("test_api", calls=10, period=1.0)
        assert isinstance(limiter1, RateLimiter)
        
        # Get same limiter
        limiter2 = get_rate_limiter("test_api")
        assert limiter1 is limiter2
        
        # Different key
        limiter3 = get_rate_limiter("other_api", calls=5, period=1.0)
        assert limiter3 is not limiter1
    
    def test_clear_rate_limiters(self):
        """Test clearing rate limiter cache."""
        # Create some limiters
        limiter1 = get_rate_limiter("api1", calls=10, period=1.0)
        limiter2 = get_rate_limiter("api2", calls=5, period=1.0)
        
        # Clear all
        clear_rate_limiters()
        
        # Should get new instances
        limiter1_new = get_rate_limiter("api1", calls=10, period=1.0)
        assert limiter1_new is not limiter1
        
        # Clear specific
        get_rate_limiter("api3", calls=3, period=1.0)
        clear_rate_limiters("api3")
        
        # api1 should still exist
        assert get_rate_limiter("api1") is limiter1_new


class TestConcurrentRateLimiting:
    """Test rate limiting under concurrent access."""
    
    def test_thread_safe_rate_limiting(self):
        """Test rate limiter is thread-safe."""
        limiter = RateLimiter(calls=10, period=1.0)
        successful_calls = []
        failed_calls = []
        
        def make_call(thread_id):
            for i in range(5):
                if limiter.acquire():
                    successful_calls.append((thread_id, i))
                else:
                    failed_calls.append((thread_id, i))
                time.sleep(0.01)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_call, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have exactly 10 successful calls
        assert len(successful_calls) == 10
        assert len(failed_calls) == 15  # 25 total - 10 successful
    
    def test_token_bucket_thread_safe(self):
        """Test token bucket is thread-safe."""
        bucket = TokenBucketRateLimiter(capacity=20, refill_rate=10.0)
        consumed = []
        
        def consume_tokens(thread_id):
            for i in range(10):
                if bucket.consume(1):
                    consumed.append((thread_id, i))
                time.sleep(0.01)
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=consume_tokens, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should consume up to capacity + refilled tokens
        assert 20 <= len(consumed) <= 25  # Some refill during execution