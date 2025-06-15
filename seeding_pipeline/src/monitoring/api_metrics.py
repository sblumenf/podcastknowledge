"""API metrics collection and Prometheus export functionality.

This module provides the central metrics collector that integrates all metrics
and provides Prometheus-format export and HTTP endpoint integration.
"""

from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional, List, Callable
import time
import logging

from .metrics import Counter, Gauge, Histogram, Summary, format_prometheus_metric
from .content_metrics import ContentMetricsCalculator
from .performance_metrics import PerformanceMetrics
from .resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Central metrics collector for the entire application.
    
    This class integrates all metric subsystems and provides
    unified access and export functionality.
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        # Component metrics
        self.content_metrics = ContentMetricsCalculator()
        self.performance_metrics = PerformanceMetrics()
        self.resource_monitor = get_resource_monitor()
        
        # High-level application metrics
        self.episodes_processed = Counter(
            "podcast_kg_episodes_processed_total",
            "Total number of episodes processed"
        )
        
        self.episodes_failed = Counter(
            "podcast_kg_episodes_failed_total",
            "Total number of episodes that failed processing"
        )
        
        # Queue metrics
        self.queue_size = Gauge(
            "podcast_kg_queue_size",
            "Current size of processing queue"
        )
        
        self.queue_wait_time = Histogram(
            "podcast_kg_queue_wait_seconds",
            "Time spent waiting in queue",
            buckets=[1, 5, 10, 30, 60, 120, 300, 600]
        )
        
        # Checkpoint metrics
        self.last_checkpoint_timestamp = Gauge(
            "podcast_kg_last_checkpoint_timestamp",
            "Timestamp of last checkpoint save"
        )
        
        # HTTP metrics (if API is active)
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
            labels=["type"]
        )
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        logger.info("MetricsCollector initialized")
    
    def record_episode_processed(self, success: bool = True):
        """Record an episode processing completion.
        
        Args:
            success: Whether processing was successful
        """
        if success:
            self.episodes_processed.inc()
        else:
            self.episodes_failed.inc()
    
    def record_graph_creation(self, node_type: Optional[str] = None, 
                            relationship_type: Optional[str] = None):
        """Record graph element creation.
        
        Args:
            node_type: Type of node created
            relationship_type: Type of relationship created
        """
        if node_type:
            self.nodes_created.inc(labels={"node_type": node_type})
        if relationship_type:
            self.relationships_created.inc(labels={"relationship_type": relationship_type})
    
    def record_quality_score(self, score: float, metric_type: str):
        """Record a quality score.
        
        Args:
            score: Quality score (0-1)
            metric_type: Type of quality metric
        """
        self.extraction_quality.observe(score, labels={"type": metric_type})
    
    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        # Export counters
        for metric in [
            self.episodes_processed, self.episodes_failed,
            self.nodes_created, self.relationships_created,
            self.http_requests_total,
            # From performance metrics
            self.performance_metrics.api_calls,
            self.performance_metrics.db_operations,
            self.performance_metrics.entities_extracted
        ]:
            lines.extend(self._export_counter(metric))
        
        # Export gauges
        for metric in [
            self.queue_size, self.last_checkpoint_timestamp,
            # From performance metrics
            self.performance_metrics.entity_extraction_rate,
            # From resource monitor
            self.resource_monitor.memory_usage_mb,
            self.resource_monitor.memory_usage_percent,
            self.resource_monitor.cpu_usage_percent,
            self.resource_monitor.cpu_count,
            self.resource_monitor.process_memory_mb,
            self.resource_monitor.process_cpu_percent
        ]:
            lines.extend(self._export_gauge(metric))
        
        # Export histograms
        for metric in [
            self.queue_wait_time, self.http_request_duration,
            self.extraction_quality,
            # From performance metrics
            self.performance_metrics.file_processing_duration,
            self.performance_metrics.api_latency,
            self.performance_metrics.db_latency
        ]:
            lines.extend(self._export_histogram(metric))
        
        return "\n".join(lines)
    
    def _export_counter(self, metric: Counter) -> List[str]:
        """Export a counter metric."""
        lines = [
            f"# HELP {metric.name} {metric.description}",
            f"# TYPE {metric.name} counter"
        ]
        
        for key, value in metric._values.items():
            if key:
                labels = dict(kv.split("=") for kv in key.split(","))
                lines.append(format_prometheus_metric(metric, labels, value))
            else:
                lines.append(format_prometheus_metric(metric, None, value))
        
        return lines
    
    def _export_gauge(self, metric: Gauge) -> List[str]:
        """Export a gauge metric."""
        lines = [
            f"# HELP {metric.name} {metric.description}",
            f"# TYPE {metric.name} gauge"
        ]
        
        for key, value in metric._values.items():
            if key:
                labels = dict(kv.split("=") for kv in key.split(","))
                lines.append(format_prometheus_metric(metric, labels, value))
            else:
                lines.append(format_prometheus_metric(metric, None, value))
        
        return lines
    
    def _export_histogram(self, metric: Histogram) -> List[str]:
        """Export a histogram metric."""
        lines = [
            f"# HELP {metric.name} {metric.description}",
            f"# TYPE {metric.name} histogram"
        ]
        
        for key in metric._observations:
            observations = metric._observations[key]
            if observations:
                # Parse labels if any
                if key:
                    base_labels = dict(kv.split("=") for kv in key.split(","))
                else:
                    base_labels = {}
                
                # Bucket counts
                for bucket in metric.buckets:
                    count = sum(1 for v in observations if v <= bucket)
                    labels = dict(base_labels)
                    labels["le"] = str(bucket)
                    lines.append(f"{metric.name}_bucket{{{self._format_labels(labels)}}} {count}")
                
                # +Inf bucket
                labels = dict(base_labels)
                labels["le"] = "+Inf"
                lines.append(f"{metric.name}_bucket{{{self._format_labels(labels)}}} {len(observations)}")
                
                # Sum and count
                if base_labels:
                    label_str = "{" + self._format_labels(base_labels) + "}"
                else:
                    label_str = ""
                lines.append(f"{metric.name}_sum{label_str} {sum(observations)}")
                lines.append(f"{metric.name}_count{label_str} {len(observations)}")
        
        return lines
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus export."""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of all metrics.
        
        Returns:
            Dictionary containing all metric summaries
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "episodes": {
                "processed": self.episodes_processed.get(),
                "failed": self.episodes_failed.get(),
                "success_rate": (
                    self.episodes_processed.get() / 
                    max(1, self.episodes_processed.get() + self.episodes_failed.get())
                )
            },
            "performance": self.performance_metrics.get_summary(),
            "resources": self.resource_monitor.get_current_metrics(),
            "graph": {
                "total_nodes": self.nodes_created.get(),
                "total_relationships": self.relationships_created.get()
            },
            "queue": {
                "current_size": self.queue_size.get(),
                "avg_wait_time": self.queue_wait_time.get_stats().get("mean", 0)
            }
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics in dictionary format (alias for get_summary).
        
        This method exists for backward compatibility with tests.
        
        Returns:
            Dictionary containing all metric summaries
        """
        return self.get_summary()
    
    def cleanup(self):
        """Clean up resources."""
        self.resource_monitor.stop_monitoring()


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector.
    
    Returns:
        MetricsCollector singleton instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def cleanup_metrics():
    """Clean up metrics resources."""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.cleanup()
        _metrics_collector = None


# Decorators for metric tracking

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
                
                # Record duration in performance metrics
                if metric_name == "processing_duration":
                    # Default to file processing
                    collector.performance_metrics.file_processing_duration.observe(
                        duration, labels
                    )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Record failure
                collector.episodes_failed.inc()
                raise
        
        return wrapper
    return decorator


def track_api_call(provider: str, method: str):
    """Decorator to track API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record successful call
                collector.performance_metrics.record_api_call(
                    provider, method, True, duration
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Record failed call
                collector.performance_metrics.record_api_call(
                    provider, method, False, duration
                )
                raise
        
        return wrapper
    return decorator


# HTTP Framework Integration

def create_metrics_endpoint(app):
    """Add metrics endpoint to a FastAPI or Flask app.
    
    Args:
        app: FastAPI or Flask application instance
    """
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
            logger.info("Added /metrics endpoint to FastAPI app")
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
            logger.info("Added /metrics endpoint to Flask app")
            return
    except ImportError:
        pass
    
    raise ValueError("App must be either FastAPI or Flask instance")


# Alias for backward compatibility
setup_metrics = create_metrics_endpoint