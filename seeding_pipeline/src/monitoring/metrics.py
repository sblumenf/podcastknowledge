"""Core metric types for the unified monitoring system.

This module provides Prometheus-compatible metric types that form the foundation
for all metrics collection in the pipeline.
"""

from collections import defaultdict
from enum import Enum
from typing import Dict, Any, Optional, List
import threading
import time


class MetricType(Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric:
    """Base class for all metrics."""
    
    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None):
        """Initialize a metric.
        
        Args:
            name: Metric name (should follow Prometheus naming conventions)
            description: Human-readable description
            labels: Optional list of label names
        """
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values = defaultdict(lambda: 0)
        self._lock = threading.Lock()
    
    def _make_key(self, label_values: Optional[Dict[str, str]] = None) -> str:
        """Create a key from label values."""
        if not label_values:
            return ""
        # Validate that all required labels are provided
        if self.labels:
            missing = set(self.labels) - set(label_values.keys())
            if missing:
                raise ValueError(f"Missing required labels: {missing}")
        return ",".join(f"{k}={v}" for k, v in sorted(label_values.items()))


class Counter(Metric):
    """A counter metric that only goes up."""
    
    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the counter.
        
        Args:
            value: Amount to increment (must be positive)
            labels: Label values
        """
        if value < 0:
            raise ValueError("Counter can only be incremented with positive values")
        with self._lock:
            key = self._make_key(labels)
            self._values[key] += value
    
    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        key = self._make_key(labels)
        return self._values[key]


class Gauge(Metric):
    """A gauge metric that can go up and down."""
    
    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Set the gauge value."""
        with self._lock:
            key = self._make_key(labels)
            self._values[key] = value
    
    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the gauge."""
        with self._lock:
            key = self._make_key(labels)
            self._values[key] += value
    
    def dec(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Decrement the gauge."""
        with self._lock:
            key = self._make_key(labels)
            self._values[key] -= value
    
    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        key = self._make_key(labels)
        return self._values[key]


class Histogram(Metric):
    """A histogram metric for tracking distributions."""
    
    def __init__(self, name: str, description: str, 
                 buckets: Optional[List[float]] = None,
                 labels: Optional[List[str]] = None):
        """Initialize histogram with configurable buckets.
        
        Args:
            name: Metric name
            description: Human-readable description
            buckets: Upper bounds for histogram buckets
            labels: Optional list of label names
        """
        super().__init__(name, description, labels)
        # Default buckets suitable for latencies in seconds
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self._observations = defaultdict(list)
        self._sums = defaultdict(float)
        self._counts = defaultdict(int)
    
    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Record an observation."""
        with self._lock:
            key = self._make_key(labels)
            self._observations[key].append(value)
            self._sums[key] += value
            self._counts[key] += 1
    
    def get_percentile(self, percentile: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Get a specific percentile.
        
        Args:
            percentile: Percentile to calculate (0-100)
            labels: Label values
            
        Returns:
            Percentile value
        """
        if not 0 <= percentile <= 100:
            raise ValueError("Percentile must be between 0 and 100")
            
        key = self._make_key(labels)
        with self._lock:
            observations = sorted(self._observations[key])
        
        if not observations:
            return 0
        
        index = int(len(observations) * percentile / 100)
        return observations[min(index, len(observations) - 1)]
    
    def get_stats(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(labels)
        with self._lock:
            count = self._counts[key]
            sum_value = self._sums[key]
            observations = self._observations[key][:]
        
        if not observations:
            return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0}
        
        return {
            "count": count,
            "sum": sum_value,
            "mean": sum_value / count if count > 0 else 0,
            "min": min(observations),
            "max": max(observations),
            "p50": self.get_percentile(50, labels),
            "p90": self.get_percentile(90, labels),
            "p95": self.get_percentile(95, labels),
            "p99": self.get_percentile(99, labels)
        }


class Summary(Metric):
    """A summary metric for tracking statistics over a sliding window."""
    
    def __init__(self, name: str, description: str, 
                 max_age_seconds: int = 600,
                 age_buckets: int = 5,
                 labels: Optional[List[str]] = None):
        """Initialize summary with time window.
        
        Args:
            name: Metric name
            description: Human-readable description
            max_age_seconds: Maximum age of observations to keep
            age_buckets: Number of age buckets for efficiency
            labels: Optional list of label names
        """
        super().__init__(name, description, labels)
        self.max_age_seconds = max_age_seconds
        self.age_buckets = age_buckets
        self._observations = defaultdict(list)
    
    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Record an observation."""
        with self._lock:
            key = self._make_key(labels)
            now = time.time()
            
            # Add new observation
            self._observations[key].append((now, value))
            
            # Remove old observations
            cutoff = now - self.max_age_seconds
            self._observations[key] = [
                (t, v) for t, v in self._observations[key] if t > cutoff
            ]
    
    def get_stats(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get summary statistics."""
        key = self._make_key(labels)
        with self._lock:
            # Clean old observations first
            now = time.time()
            cutoff = now - self.max_age_seconds
            self._observations[key] = [
                (t, v) for t, v in self._observations[key] if t > cutoff
            ]
            
            values = [v for _, v in self._observations[key]]
        
        if not values:
            return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0}
        
        count = len(values)
        sum_value = sum(values)
        
        return {
            "count": count,
            "sum": sum_value,
            "mean": sum_value / count,
            "min": min(values),
            "max": max(values)
        }


def format_prometheus_metric(metric: Metric, 
                           label_values: Optional[Dict[str, str]] = None,
                           value: float = None) -> str:
    """Format a metric value in Prometheus text format.
    
    Args:
        metric: The metric object
        label_values: Label values for this metric
        value: The metric value (if None, will be fetched from metric)
        
    Returns:
        Formatted metric line
    """
    # Format labels
    if label_values:
        label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(label_values.items())) + "}"
    else:
        label_str = ""
    
    # Get value if not provided
    if value is None:
        if isinstance(metric, (Counter, Gauge)):
            value = metric.get(label_values)
        else:
            raise ValueError(f"Value must be provided for {type(metric).__name__}")
    
    return f"{metric.name}{label_str} {value}"