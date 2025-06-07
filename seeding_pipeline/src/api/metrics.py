"""
Metrics collection and export for monitoring the Podcast Knowledge Graph Pipeline.

Provides Prometheus-compatible metrics for monitoring performance,
success rates, and resource usage.
"""

from collections import defaultdict
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Dict, Any, Optional, List, Callable
import threading
import time

from ..utils.log_utils import get_logger
try:
    import psutil
except ImportError:
    # Use mock psutil if real one not available
    from tests.utils import mock_psutil as psutil
logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric:
    """Base class for metrics."""
    
    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values = defaultdict(lambda: 0)
        self._lock = threading.Lock()
    
    def _make_key(self, label_values: Optional[Dict[str, str]] = None) -> str:
        """Create a key from label values."""
        if not label_values:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(label_values.items()))


class Counter(Metric):
    """A counter metric that only goes up."""
    
    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the counter."""
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
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self._observations = defaultdict(list)
        self._bucket_counts = defaultdict(lambda: defaultdict(int))
    
    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Record an observation."""
        with self._lock:
            key = self._make_key(labels)
            self._observations[key].append(value)
            
            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[key][bucket] += 1
    
    def get_percentile(self, percentile: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Get a specific percentile."""
        key = self._make_key(labels)
        observations = sorted(self._observations[key])
        if not observations:
            return 0
        
        index = int(len(observations) * percentile / 100)
        return observations[min(index, len(observations) - 1)]


class Summary(Metric):
    """A summary metric for tracking statistics over a sliding window."""
    
    def __init__(self, name: str, description: str, 
                 max_age_seconds: int = 600,
                 labels: Optional[List[str]] = None):
        super().__init__(name, description, labels)
        self.max_age_seconds = max_age_seconds
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
        values = [v for _, v in self._observations[key]]
        
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }


class MetricsCollector:
    """Central metrics collector for the application."""
    
    def __init__(self):
        # Processing metrics
        self.episodes_processed = Counter(
            "podcast_kg_episodes_processed_total",
            "Total number of episodes processed"
        )
        self.episodes_failed = Counter(
            "podcast_kg_episodes_failed_total",
            "Total number of episodes that failed processing"
        )
        self.processing_duration = Histogram(
            "podcast_kg_processing_duration_seconds",
            "Time spent processing episodes",
            labels=["stage"]
        )
        
        # Provider metrics
        self.provider_calls = Counter(
            "podcast_kg_provider_calls_total",
            "Total provider API calls",
            labels=["provider", "method"]
        )
        self.provider_errors = Counter(
            "podcast_kg_provider_errors_total",
            "Total provider errors",
            labels=["provider", "error_type"]
        )
        self.provider_latency = Histogram(
            "podcast_kg_provider_latency_seconds",
            "Provider API latency",
            labels=["provider", "method"]
        )
        
        # Resource metrics
        self.memory_usage = Gauge(
            "podcast_kg_memory_usage_bytes",
            "Current memory usage"
        )
        self.cpu_usage = Gauge(
            "podcast_kg_cpu_usage_percent",
            "Current CPU usage percentage"
        )
        
        # Graph metrics
        self.nodes_created = Counter(
            "podcast_kg_nodes_created_total",
            "Total nodes created in graph",
            labels=["node_type"]
        )
        self.relationships_created = Counter(
            "podcast_kg_relationships_created_total",
            "Total relationships created in graph",
            labels=["relationship_type"]
        )
        
        # Quality metrics
        self.extraction_quality = Histogram(
            "podcast_kg_extraction_quality_score",
            "Quality scores for extracted knowledge",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            labels=["type"]  # transcription, entity_extraction, etc.
        )
        self.entities_per_episode = Summary(
            "podcast_kg_entities_per_episode",
            "Number of entities extracted per episode"
        )
        self.entities_extracted_total = Counter(
            "podcast_kg_entities_extracted_total",
            "Total number of entities extracted"
        )
        
        # Queue metrics
        self.queue_size = Gauge(
            "podcast_kg_queue_size",
            "Current size of processing queue"
        )
        self.queue_wait_time = Histogram(
            "podcast_kg_queue_wait_seconds",
            "Time spent waiting in queue"
        )
        
        # SLO-specific metrics
        self.last_processed_timestamp = Gauge(
            "podcast_kg_last_processed_timestamp",
            "Timestamp of last successfully processed episode"
        )
        self.last_checkpoint_timestamp = Gauge(
            "podcast_kg_last_checkpoint_timestamp", 
            "Timestamp of last checkpoint save"
        )
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            labels=["method", "endpoint", "status"]
        )
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            labels=["method", "endpoint"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        # Schemaless extraction metrics
        self.discovered_entity_types = Counter(
            "podcast_kg_discovered_entity_types_total",
            "Total discovered entity types in schemaless mode",
            labels=["entity_type"]
        )
        self.discovered_relationship_types = Counter(
            "podcast_kg_discovered_relationship_types_total",
            "Total discovered relationship types in schemaless mode",
            labels=["relationship_type"]
        )
        self.entity_resolution_matches = Counter(
            "podcast_kg_entity_resolution_matches_total",
            "Total entity resolution matches"
        )
        self.schema_evolution_rate = Gauge(
            "podcast_kg_schema_evolution_rate",
            "Rate of schema evolution (new types per episode)"
        )
        self.extraction_mode = Gauge(
            "podcast_kg_extraction_mode",
            "Current extraction mode (0=fixed, 1=schemaless)"
        )
        
        # Start resource monitoring
        self._start_resource_monitoring()
    
    def _start_resource_monitoring(self):
        """Start background thread for resource monitoring."""
        def monitor():
            while True:
                try:
                    # Update memory usage
                    process = psutil.Process()
                    self.memory_usage.set(process.memory_info().rss)
                    
                    # Update CPU usage
                    self.cpu_usage.set(process.cpu_percent(interval=1))
                    
                    time.sleep(10)  # Update every 10 seconds
                except Exception as e:
                    logger.error(f"Error in resource monitoring: {e}")
                    time.sleep(30)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Helper to format metric
        def format_metric(metric: Metric, value: float, labels: Optional[Dict[str, str]] = None):
            if labels:
                label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
            else:
                label_str = ""
            return f"{metric.name}{label_str} {value}"
        
        # Export counters
        for metric in [self.episodes_processed, self.episodes_failed, 
                      self.provider_calls, self.provider_errors,
                      self.nodes_created, self.relationships_created,
                      self.entities_extracted_total, self.http_requests_total,
                      self.discovered_entity_types, self.discovered_relationship_types,
                      self.entity_resolution_matches]:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} counter")
            for key, value in metric._values.items():
                if key:
                    labels = dict(kv.split("=") for kv in key.split(","))
                    lines.append(format_metric(metric, value, labels))
                else:
                    lines.append(format_metric(metric, value))
        
        # Export gauges
        for metric in [self.memory_usage, self.cpu_usage, self.queue_size,
                      self.last_processed_timestamp, self.last_checkpoint_timestamp,
                      self.schema_evolution_rate, self.extraction_mode]:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} gauge")
            for key, value in metric._values.items():
                if key:
                    labels = dict(kv.split("=") for kv in key.split(","))
                    lines.append(format_metric(metric, value, labels))
                else:
                    lines.append(format_metric(metric, value))
        
        # Export histograms
        for metric in [self.processing_duration, self.provider_latency,
                      self.extraction_quality, self.queue_wait_time,
                      self.http_request_duration]:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} histogram")
            
            for key in metric._observations:
                observations = metric._observations[key]
                if observations:
                    # Bucket counts
                    bucket_counts = metric._bucket_counts[key]
                    for bucket in metric.buckets:
                        count = sum(1 for v in observations if v <= bucket)
                        if key:
                            labels = dict(kv.split("=") for kv in key.split(","))
                            labels["le"] = str(bucket)
                        else:
                            labels = {"le": str(bucket)}
                        lines.append(f"{metric.name}_bucket{format_metric(metric, count, labels)}")
                    
                    # +Inf bucket
                    if key:
                        labels = dict(kv.split("=") for kv in key.split(","))
                        labels["le"] = "+Inf"
                    else:
                        labels = {"le": "+Inf"}
                    lines.append(f"{metric.name}_bucket{format_metric(metric, len(observations), labels)}")
                    
                    # Sum and count
                    if key:
                        labels = dict(kv.split("=") for kv in key.split(","))
                    else:
                        labels = None
                    lines.append(f"{metric.name}_sum{format_metric(metric, sum(observations), labels)}")
                    lines.append(f"{metric.name}_count{format_metric(metric, len(observations), labels)}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "episodes": {
                "processed": self.episodes_processed.get(),
                "failed": self.episodes_failed.get(),
                "success_rate": (self.episodes_processed.get() / 
                               max(1, self.episodes_processed.get() + self.episodes_failed.get()))
            },
            "performance": {
                "avg_processing_time": self.processing_duration.get_percentile(50),
                "p95_processing_time": self.processing_duration.get_percentile(95),
                "p99_processing_time": self.processing_duration.get_percentile(99)
            },
            "resources": {
                "memory_mb": self.memory_usage.get() / (1024 * 1024),
                "cpu_percent": self.cpu_usage.get()
            },
            "quality": {
                "avg_extraction_score": self.extraction_quality.get_percentile(50),
                "entities_per_episode": self.entities_per_episode.get_stats()["avg"]
            }
        }


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def track_duration(metric_name: str = "processing_duration", **labels):
    """Decorator to track function execution duration."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record duration
                if hasattr(collector, metric_name):
                    metric = getattr(collector, metric_name)
                    if isinstance(metric, Histogram):
                        metric.observe(duration, labels)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Record duration even on failure
                if hasattr(collector, metric_name):
                    metric = getattr(collector, metric_name)
                    if isinstance(metric, Histogram):
                        metric.observe(duration, labels)
                
                # Record failure
                collector.episodes_failed.inc()
                raise
        
        return wrapper
    return decorator


def track_provider_call(provider: str, method: str):
    """Decorator to track provider API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record successful call
                collector.provider_calls.inc(labels={"provider": provider, "method": method})
                collector.provider_latency.observe(duration, 
                                                 labels={"provider": provider, "method": method})
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Record failed call
                collector.provider_calls.inc(labels={"provider": provider, "method": method})
                collector.provider_errors.inc(
                    labels={"provider": provider, "error_type": type(e).__name__}
                )
                collector.provider_latency.observe(duration,
                                                 labels={"provider": provider, "method": method})
                raise
        
        return wrapper
    return decorator


# FastAPI/Flask integration
def create_metrics_endpoint(app):
    """Add metrics endpoint to a FastAPI or Flask app."""
    try:
        # Try FastAPI
        from fastapi import FastAPI, Response
        if isinstance(app, FastAPI):
            @app.get("/metrics")
            async def metrics():
                collector = get_metrics_collector()
                return Response(
                    content=collector.export_prometheus(),
                    media_type="text/plain"
                )
            return
    except ImportError:
        pass
    
    try:
        # Try Flask
        from flask import Flask, Response
        if isinstance(app, Flask):
            @app.route("/metrics")
            def metrics():
                collector = get_metrics_collector()
                return Response(
                    collector.export_prometheus(),
                    mimetype="text/plain"
                )
            return
    except ImportError:
        pass
    
    raise ValueError("App must be either FastAPI or Flask instance")


# Alias for compatibility
setup_metrics = create_metrics_endpoint