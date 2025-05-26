"""Rate limiting utilities for API calls."""

import time
from typing import Dict, Any, Optional
from collections import deque
from abc import ABC, abstractmethod


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""
    
    @abstractmethod
    def can_make_request(self, identifier: str, cost: float = 1.0) -> bool:
        """Check if request can be made within rate limits."""
        pass
        
    @abstractmethod
    def record_request(self, identifier: str, cost: float = 1.0) -> None:
        """Record a successful request."""
        pass
        
    @abstractmethod
    def record_error(self, identifier: str, error_type: str) -> None:
        """Record an error for monitoring."""
        pass
        
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        pass


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter implementation."""
    
    def __init__(self, rate: float, capacity: float):
        """
        Initialize token bucket rate limiter.
        
        Args:
            rate: Tokens replenished per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.request_history = deque(maxlen=1000)
        self.error_counts = {}
        
    def can_make_request(self, identifier: str, cost: float = 1.0) -> bool:
        """Check if request can be made."""
        self._replenish_tokens()
        return self.tokens >= cost
        
    def record_request(self, identifier: str, cost: float = 1.0) -> None:
        """Record a successful request."""
        self._replenish_tokens()
        if self.tokens >= cost:
            self.tokens -= cost
            self.request_history.append({
                'time': time.time(),
                'identifier': identifier,
                'cost': cost
            })
            
    def record_error(self, identifier: str, error_type: str) -> None:
        """Record an error."""
        key = f"{identifier}:{error_type}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
        
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        self._replenish_tokens()
        return {
            'tokens_available': self.tokens,
            'capacity': self.capacity,
            'rate': self.rate,
            'recent_requests': len(self.request_history),
            'errors': dict(self.error_counts)
        }
        
    def _replenish_tokens(self) -> None:
        """Replenish tokens based on elapsed time."""
        current_time = time.time()
        elapsed = current_time - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = current_time


class WindowedRateLimiter(RateLimiter):
    """Sliding window rate limiter implementation."""
    
    def __init__(self, limits: Dict[str, Dict[str, Any]]):
        """
        Initialize windowed rate limiter.
        
        Args:
            limits: Dictionary of rate limits per identifier
                   Format: {
                       'identifier': {
                           'rpm': requests_per_minute,
                           'tpm': tokens_per_minute,
                           'rpd': requests_per_day
                       }
                   }
        """
        self.limits = limits
        self.default_limits = limits.get('default', {
            'rpm': 10,
            'tpm': 100000,
            'rpd': 500
        })
        
        # Track usage per identifier
        self.requests = {}
        self.error_counts = {}
        
    def can_make_request(self, identifier: str, cost: float = 1.0) -> bool:
        """Check if request can be made within rate limits."""
        current_time = time.time()
        
        # Get limits for identifier
        limits = self.limits.get(identifier, self.default_limits)
        
        # Get or create usage tracker
        if identifier not in self.requests:
            self.requests[identifier] = self._create_usage_tracker()
            
        usage = self.requests[identifier]
        
        # Clean old entries
        self._clean_old_entries(usage, current_time)
        
        # Check all limits
        if 'rpm' in limits:
            rpm_count = len(usage.get('minute', []))
            if rpm_count >= limits['rpm']:
                return False
                
        if 'tpm' in limits:
            tokens_used = sum(t[1] for t in usage.get('tokens_minute', []))
            if tokens_used + cost > limits['tpm']:
                return False
                
        if 'rpd' in limits:
            rpd_count = len(usage.get('day', []))
            if rpd_count >= limits['rpd']:
                return False
                
        return True
        
    def record_request(self, identifier: str, cost: float = 1.0) -> None:
        """Record a successful request."""
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = self._create_usage_tracker()
            
        usage = self.requests[identifier]
        
        if 'minute' in usage:
            usage['minute'].append(current_time)
        if 'day' in usage:
            usage['day'].append(current_time)
        if 'tokens_minute' in usage:
            usage['tokens_minute'].append((current_time, cost))
            
    def record_error(self, identifier: str, error_type: str) -> None:
        """Record an error for monitoring."""
        key = f"{identifier}:{error_type}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
        
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        current_time = time.time()
        status = {}
        
        for identifier, usage in self.requests.items():
            self._clean_old_entries(usage, current_time)
            
            limits = self.limits.get(identifier, self.default_limits)
            
            identifier_status = {}
            
            if 'rpm' in limits:
                rpm_count = len(usage.get('minute', []))
                identifier_status['rpm'] = {
                    'used': rpm_count,
                    'limit': limits['rpm']
                }
                
            if 'tpm' in limits:
                tokens_used = sum(t[1] for t in usage.get('tokens_minute', []))
                identifier_status['tpm'] = {
                    'used': int(tokens_used),
                    'limit': limits['tpm']
                }
                
            if 'rpd' in limits:
                rpd_count = len(usage.get('day', []))
                identifier_status['rpd'] = {
                    'used': rpd_count,
                    'limit': limits['rpd']
                }
                
            identifier_status['errors'] = {
                k: v for k, v in self.error_counts.items()
                if k.startswith(identifier)
            }
            
            status[identifier] = identifier_status
            
        return status
        
    def _clean_old_entries(self, usage: Dict[str, deque], current_time: float) -> None:
        """Remove entries older than rate limit windows."""
        # Clean minute window (60 seconds)
        if 'minute' in usage:
            while usage['minute'] and usage['minute'][0] < current_time - 60:
                usage['minute'].popleft()
                
        if 'tokens_minute' in usage:
            while usage['tokens_minute'] and usage['tokens_minute'][0][0] < current_time - 60:
                usage['tokens_minute'].popleft()
                
        # Clean day window (24 hours)
        if 'day' in usage:
            while usage['day'] and usage['day'][0] < current_time - 86400:
                usage['day'].popleft()
                
    def _create_usage_tracker(self) -> Dict[str, deque]:
        """Create a new usage tracker."""
        return {
            'minute': deque(),
            'day': deque(),
            'tokens_minute': deque()
        }


class CompositeRateLimiter(RateLimiter):
    """Composite rate limiter that combines multiple rate limiters."""
    
    def __init__(self, limiters: Dict[str, RateLimiter]):
        """Initialize with multiple rate limiters."""
        self.limiters = limiters
        
    def can_make_request(self, identifier: str, cost: float = 1.0) -> bool:
        """Check if request can be made across all limiters."""
        return all(
            limiter.can_make_request(identifier, cost)
            for limiter in self.limiters.values()
        )
        
    def record_request(self, identifier: str, cost: float = 1.0) -> None:
        """Record request across all limiters."""
        for limiter in self.limiters.values():
            limiter.record_request(identifier, cost)
            
    def record_error(self, identifier: str, error_type: str) -> None:
        """Record error across all limiters."""
        for limiter in self.limiters.values():
            limiter.record_error(identifier, error_type)
            
    def get_status(self) -> Dict[str, Any]:
        """Get status from all limiters."""
        return {
            name: limiter.get_status()
            for name, limiter in self.limiters.items()
        }