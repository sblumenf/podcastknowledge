"""Health monitoring and circuit breaker for providers."""

import time
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import threading

from src.core.interfaces import HealthCheckable


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class HealthMetrics:
    """Health metrics for a provider."""
    total_requests: int = 0
    failed_requests: int = 0
    successful_requests: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
        
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
        
    def record_success(self, response_time: float) -> None:
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        self.response_times.append(response_time)
        
    def record_failure(self) -> None:
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()


class CircuitBreaker:
    """Circuit breaker for provider resilience."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = CircuitState.CLOSED
        self._metrics = HealthMetrics()
        self._lock = threading.Lock()
        
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
        
    @property
    def metrics(self) -> HealthMetrics:
        """Get health metrics."""
        return self._metrics
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise Exception(
                        f"Circuit breaker is OPEN. "
                        f"Failed {self._metrics.consecutive_failures} times. "
                        f"Retry after {self._time_until_retry():.1f} seconds."
                    )
                    
        # Try to call the function
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            
            with self._lock:
                self._on_success(response_time)
                
            return result
            
        except self.expected_exception as e:
            with self._lock:
                self._on_failure()
            raise e
            
    def _should_attempt_reset(self) -> bool:
        """Check if we should try to reset the circuit."""
        return (
            self._metrics.last_failure_time and
            time.time() - self._metrics.last_failure_time >= self.recovery_timeout
        )
        
    def _time_until_retry(self) -> float:
        """Calculate seconds until retry is allowed."""
        if not self._metrics.last_failure_time:
            return 0.0
        elapsed = time.time() - self._metrics.last_failure_time
        return max(0, self.recovery_timeout - elapsed)
        
    def _on_success(self, response_time: float) -> None:
        """Handle successful call."""
        self._metrics.record_success(response_time)
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("Circuit breaker closed after successful test")
            
    def _on_failure(self) -> None:
        """Handle failed call."""
        self._metrics.record_failure()
        
        if self._metrics.consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._metrics.consecutive_failures} failures"
            )
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker reopened after test failure")
            
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._metrics = HealthMetrics()
            logger.info("Circuit breaker manually reset")


class ProviderHealthMonitor:
    """Monitor health of multiple providers."""
    
    def __init__(self, check_interval: float = 300.0):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Seconds between health checks
        """
        self.check_interval = check_interval
        self._providers: Dict[str, HealthCheckable] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._health_history: Dict[str, deque] = {}
        self._fallback_providers: Dict[str, List[str]] = {}
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.Lock()
        
    def register_provider(
        self,
        name: str,
        provider: HealthCheckable,
        circuit_breaker: Optional[CircuitBreaker] = None,
        fallback_providers: Optional[List[str]] = None
    ) -> None:
        """Register a provider for health monitoring."""
        with self._lock:
            self._providers[name] = provider
            
            if circuit_breaker:
                self._circuit_breakers[name] = circuit_breaker
            else:
                # Create default circuit breaker
                self._circuit_breakers[name] = CircuitBreaker()
                
            self._health_history[name] = deque(maxlen=10)
            
            if fallback_providers:
                self._fallback_providers[name] = fallback_providers
                
        logger.info(f"Registered provider '{name}' for health monitoring")
        
    def unregister_provider(self, name: str) -> None:
        """Unregister a provider from health monitoring."""
        with self._lock:
            self._providers.pop(name, None)
            self._circuit_breakers.pop(name, None)
            self._health_history.pop(name, None)
            self._fallback_providers.pop(name, None)
            
        logger.info(f"Unregistered provider '{name}' from health monitoring")
        
    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Started health monitoring")
        
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Stopped health monitoring")
        
    def check_provider_health(self, name: str) -> Dict[str, Any]:
        """Check health of a specific provider."""
        if name not in self._providers:
            return {'healthy': False, 'error': 'Provider not registered'}
            
        provider = self._providers[name]
        circuit_breaker = self._circuit_breakers[name]
        
        try:
            # Use circuit breaker for health check
            health_result = circuit_breaker.call(provider.health_check)
            
            # Record health check result
            with self._lock:
                self._health_history[name].append({
                    'timestamp': datetime.now(),
                    'result': health_result,
                    'circuit_state': circuit_breaker.state.value
                })
                
            return health_result
            
        except Exception as e:
            logger.error(f"Health check failed for provider '{name}': {e}")
            return {
                'healthy': False,
                'error': str(e),
                'circuit_state': circuit_breaker.state.value
            }
            
    def get_provider_status(self, name: str) -> Dict[str, Any]:
        """Get detailed status of a provider."""
        if name not in self._providers:
            return {'error': 'Provider not registered'}
            
        circuit_breaker = self._circuit_breakers[name]
        metrics = circuit_breaker.metrics
        
        status = {
            'circuit_state': circuit_breaker.state.value,
            'metrics': {
                'total_requests': metrics.total_requests,
                'failed_requests': metrics.failed_requests,
                'failure_rate': metrics.failure_rate,
                'consecutive_failures': metrics.consecutive_failures,
                'average_response_time': metrics.average_response_time
            },
            'fallback_providers': self._fallback_providers.get(name, [])
        }
        
        # Add recent health check history
        if name in self._health_history:
            status['recent_health_checks'] = [
                {
                    'timestamp': check['timestamp'].isoformat(),
                    'healthy': check['result'].get('healthy', False),
                    'circuit_state': check['circuit_state']
                }
                for check in self._health_history[name]
            ]
            
        return status
        
    def get_healthy_provider(self, provider_type: str) -> Optional[str]:
        """
        Get a healthy provider of the specified type.
        
        Args:
            provider_type: Type of provider needed
            
        Returns:
            Name of healthy provider or None
        """
        # Get all providers of this type
        candidates = [
            name for name in self._providers
            if provider_type in name.lower()
        ]
        
        # Check each candidate
        for name in candidates:
            if self._circuit_breakers[name].state == CircuitState.CLOSED:
                return name
                
        # No healthy providers found
        return None
        
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered providers."""
        return {
            name: self.get_provider_status(name)
            for name in self._providers
        }
        
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitoring:
            # Check all providers
            for name in list(self._providers.keys()):
                try:
                    self.check_provider_health(name)
                except Exception as e:
                    logger.error(f"Error monitoring provider '{name}': {e}")
                    
            # Wait for next check interval
            time.sleep(self.check_interval)
            
    def aggregate_health(self) -> Dict[str, Any]:
        """Aggregate health status across all providers."""
        total_providers = len(self._providers)
        if total_providers == 0:
            return {
                'overall_health': 'unknown',
                'healthy_count': 0,
                'total_count': 0,
                'health_percentage': 0.0
            }
            
        healthy_count = sum(
            1 for name in self._providers
            if self._circuit_breakers[name].state == CircuitState.CLOSED
        )
        
        health_percentage = (healthy_count / total_providers) * 100
        
        if health_percentage >= 80:
            overall_health = 'healthy'
        elif health_percentage >= 50:
            overall_health = 'degraded'
        else:
            overall_health = 'critical'
            
        return {
            'overall_health': overall_health,
            'healthy_count': healthy_count,
            'total_count': total_providers,
            'health_percentage': health_percentage,
            'providers': self.get_all_status()
        }