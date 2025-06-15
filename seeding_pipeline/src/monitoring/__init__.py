"""Unified monitoring system for the podcast knowledge graph pipeline.

This module consolidates all metrics collection into a clean, organized structure:
- Content metrics: Text analysis and quality metrics
- Performance metrics: Pipeline execution and API tracking
- Resource monitoring: CPU and memory usage
- API metrics: Prometheus export and HTTP integration

Example usage:
    from src.monitoring import get_metrics_collector, track_api_call
    
    collector = get_metrics_collector()
    collector.record_episode_processed(success=True)
    
    @track_api_call("gemini", "generate_content")
    def call_gemini_api():
        # API call implementation
        pass
"""

# Core metric types
from .metrics import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    MetricType
)

# Content analysis metrics
from .content_metrics import (
    ContentMetricsCalculator,
    ComplexityMetrics,
    InformationDensityMetrics,
    AccessibilityMetrics
)

# Performance tracking
from .performance_metrics import PerformanceMetrics

# Resource monitoring
from .resource_monitor import ResourceMonitor, get_resource_monitor

# API and export functionality
from .api_metrics import (
    MetricsCollector,
    get_metrics_collector,
    cleanup_metrics,
    track_duration,
    track_api_call,
    create_metrics_endpoint,
    setup_metrics  # Backward compatibility alias
)

# Backward compatibility exports
# These maintain compatibility with existing code that imports from old locations
MetricsCalculator = ContentMetricsCalculator  # Alias for old name
PipelineMetrics = PerformanceMetrics  # Alias for old name

# Helper function for backward compatibility
def get_pipeline_metrics() -> PerformanceMetrics:
    """Get performance metrics instance (backward compatibility)."""
    collector = get_metrics_collector()
    return collector.performance_metrics


__all__ = [
    # Core types
    "Counter",
    "Gauge", 
    "Histogram",
    "Summary",
    "MetricType",
    
    # Content metrics
    "ContentMetricsCalculator",
    "ComplexityMetrics",
    "InformationDensityMetrics",
    "AccessibilityMetrics",
    
    # Performance metrics
    "PerformanceMetrics",
    
    # Resource monitoring
    "ResourceMonitor",
    "get_resource_monitor",
    
    # API metrics
    "MetricsCollector",
    "get_metrics_collector",
    "cleanup_metrics",
    "track_duration",
    "track_api_call",
    "create_metrics_endpoint",
    "setup_metrics",
    
    # Backward compatibility
    "MetricsCalculator",
    "PipelineMetrics",
    "get_pipeline_metrics"
]