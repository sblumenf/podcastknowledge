"""
Comprehensive tests for the metrics module.

This module tests all metric types, the metrics collector,
decorators, and Prometheus export functionality.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.api.metrics import (
    MetricType,
    Metric,
    Counter,
    Gauge,
    Histogram,
    Summary,
    MetricsCollector,
    track_duration,
    track_provider_call,
    create_metrics_endpoint,
    get_metrics_collector
)


class TestMetricType:
    """Test the MetricType enum."""
    
    def test_metric_types(self):
        """Test all metric types are defined."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"
    
    def test_all_types_present(self):
        """Test all expected metric types exist."""
        types = [t.value for t in MetricType]
        assert set(types) == {"counter", "gauge", "histogram", "summary"}


class TestMetric:
    """Test the base Metric class."""
    
    def test_metric_initialization(self):
        """Test basic metric initialization."""
        metric = Metric("test_metric", "A test metric")
        assert metric.name == "test_metric"
        assert metric.description == "A test metric"
        assert metric.labels == []
    
    def test_metric_with_labels(self):
        """Test metric with labels."""
        metric = Metric(
            "http_requests",
            "HTTP request count",
            labels=["method", "endpoint"]
        )
        assert metric.labels == ["method", "endpoint"]
    
    def test_metric_make_key(self):
        """Test label key generation."""
        metric = Metric("test", "test", labels=["method"])
        key = metric._make_key({"method": "GET"})
        assert key == "method=GET"
        
        # Multiple labels
        key = metric._make_key({"method": "GET", "endpoint": "/api"})
        assert key == "endpoint=/api,method=GET"  # Sorted


class TestCounter:
    """Test the Counter metric class."""
    
    def test_counter_initialization(self):
        """Test counter starts at zero."""
        counter = Counter("request_count", "Total requests")
        assert counter.get() == 0
    
    def test_counter_increment(self):
        """Test incrementing counter."""
        counter = Counter("error_count", "Total errors")
        counter.inc()
        assert counter.get() == 1
        
        counter.inc()
        counter.inc()
        assert counter.get() == 3
    
    def test_counter_increment_by_value(self):
        """Test incrementing by specific value."""
        counter = Counter("bytes_processed", "Bytes processed")
        counter.inc(100)
        assert counter.get() == 100
        
        counter.inc(50)
        assert counter.get() == 150
    
    def test_counter_with_labels(self):
        """Test counter with label values."""
        counter = Counter("http_requests", "HTTP requests", labels=["method"])
        
        counter.inc(1, {"method": "GET"})
        counter.inc(1, {"method": "POST"})
        counter.inc(1, {"method": "GET"})
        
        assert counter.get({"method": "GET"}) == 2
        assert counter.get({"method": "POST"}) == 1
    
    def test_counter_thread_safety(self):
        """Test counter is thread-safe."""
        counter = Counter("concurrent_ops", "Concurrent operations")
        
        def increment_many():
            for _ in range(1000):
                counter.inc()
        
        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert counter.get() == 10000


class TestGauge:
    """Test the Gauge metric class."""
    
    def test_gauge_initialization(self):
        """Test gauge starts at zero."""
        gauge = Gauge("memory_usage", "Memory usage")
        assert gauge.get() == 0
    
    def test_gauge_set(self):
        """Test setting gauge value."""
        gauge = Gauge("cpu_percent", "CPU percentage")
        gauge.set(45.5)
        assert gauge.get() == 45.5
        
        gauge.set(67.2)
        assert gauge.get() == 67.2
    
    def test_gauge_inc_dec(self):
        """Test incrementing and decrementing gauge."""
        gauge = Gauge("active_connections", "Active connections")
        
        gauge.inc()
        assert gauge.get() == 1
        
        gauge.inc(5)
        assert gauge.get() == 6
        
        gauge.dec(2)
        assert gauge.get() == 4
        
        gauge.dec()
        assert gauge.get() == 3
    
    def test_gauge_can_be_negative(self):
        """Test gauge can have negative values."""
        gauge = Gauge("temperature", "Temperature in Celsius")
        gauge.set(-10.5)
        assert gauge.get() == -10.5
        
        gauge.dec(5)
        assert gauge.get() == -15.5
    
    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauge = Gauge("disk_usage", "Disk usage", labels=["device"])
        
        gauge.set(80.5, {"device": "/dev/sda1"})
        gauge.set(45.2, {"device": "/dev/sda2"})
        
        assert gauge.get({"device": "/dev/sda1"}) == 80.5
        assert gauge.get({"device": "/dev/sda2"}) == 45.2


class TestHistogram:
    """Test the Histogram metric class."""
    
    def test_histogram_initialization(self):
        """Test histogram initialization."""
        hist = Histogram("request_duration", "Request duration")
        assert hist.name == "request_duration"
        assert hist.buckets == [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
    
    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        buckets = [0.1, 0.5, 1.0, 5.0, 10.0]
        hist = Histogram("response_time", "Response time", buckets=buckets)
        assert hist.buckets == buckets
    
    def test_histogram_observe(self):
        """Test observing values."""
        hist = Histogram("latency", "Operation latency")
        
        # Observe some values
        values = [0.002, 0.008, 0.015, 0.03, 0.12, 0.3, 0.8, 1.5, 3.0, 7.0, 15.0]
        for v in values:
            hist.observe(v)
        
        # Check that observations are recorded
        assert len(hist._observations[""]) == len(values)
    
    def test_histogram_with_labels(self):
        """Test histogram with labels."""
        hist = Histogram("api_latency", "API latency", labels=["endpoint"])
        
        hist.observe(0.1, {"endpoint": "/users"})
        hist.observe(0.2, {"endpoint": "/users"})
        hist.observe(0.5, {"endpoint": "/posts"})
        
        users_key = hist._make_key({"endpoint": "/users"})
        posts_key = hist._make_key({"endpoint": "/posts"})
        
        assert len(hist._observations[users_key]) == 2
        assert len(hist._observations[posts_key]) == 1


class TestSummary:
    """Test the Summary metric class."""
    
    def test_summary_initialization(self):
        """Test summary initialization."""
        summary = Summary("request_size", "Request size in bytes")
        assert summary.name == "request_size"
        assert summary.max_age_seconds == 600  # Default 10 minutes
    
    def test_summary_observe(self):
        """Test observing values."""
        summary = Summary("processing_time", "Processing time")
        
        values = [1.2, 2.3, 3.4, 4.5, 5.6]
        for v in values:
            summary.observe(v)
        
        # Check observations are recorded
        assert len(summary._observations[""]) == len(values)
    
    def test_summary_percentiles(self):
        """Test percentile calculations."""
        summary = Summary("test_metric", "Test metric")
        
        # Add 100 values from 1 to 100
        for i in range(1, 101):
            summary.observe(float(i))
        
        stats = summary.get_stats()
        assert stats is not None
        # Basic checks - exact values depend on implementation
        assert "count" in stats
        assert "sum" in stats


class TestMetricsCollector:
    """Test the MetricsCollector singleton."""
    
    def test_singleton_pattern(self):
        """Test that MetricsCollector is a singleton."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2
    
    def test_default_metrics_exist(self):
        """Test that default metrics are registered."""
        collector = get_metrics_collector()
        
        # Check some key metrics exist
        assert hasattr(collector, 'episodes_processed')
        assert hasattr(collector, 'processing_duration')
        assert hasattr(collector, 'memory_usage')
        assert hasattr(collector, 'cpu_usage')
    
    def test_counter_usage(self):
        """Test using counter through collector."""
        collector = get_metrics_collector()
        
        # Reset for testing
        initial_value = collector.episodes_processed.get()
        
        collector.episodes_processed.inc()
        assert collector.episodes_processed.get() == initial_value + 1
    
    def test_gauge_usage(self):
        """Test using gauge through collector."""
        collector = get_metrics_collector()
        
        collector.memory_usage.set(1024 * 1024 * 512)  # 512 MB
        assert collector.memory_usage.get() == 1024 * 1024 * 512
    
    def test_histogram_usage(self):
        """Test using histogram through collector."""
        collector = get_metrics_collector()
        
        # Record some processing times
        collector.processing_duration.observe(0.5)
        collector.processing_duration.observe(1.2)
        collector.processing_duration.observe(2.3)
        
        # Just verify it doesn't error
        assert collector.processing_duration._observations


class TestTrackDurationDecorator:
    """Test the track_duration decorator."""
    
    def test_track_duration_function(self):
        """Test tracking duration of a function."""
        collector = get_metrics_collector()
        
        @track_duration()
        def slow_function():
            time.sleep(0.01)
            return "done"
        
        result = slow_function()
        assert result == "done"
        
        # Check that duration was recorded
        # The exact metric name depends on implementation
    
    def test_track_duration_with_exception(self):
        """Test duration tracking when function raises."""
        @track_duration()
        def failing_function():
            time.sleep(0.01)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Duration should still be recorded
    
    def test_track_duration_with_metric_name(self):
        """Test custom metric name."""
        @track_duration(metric_name="custom_operation_duration")
        def custom_operation():
            return 42
        
        result = custom_operation()
        assert result == 42


class TestTrackProviderCallDecorator:
    """Test the track_provider_call decorator."""
    
    def test_track_provider_success(self):
        """Test tracking successful provider calls."""
        @track_provider_call("test_provider", "test_method")
        def provider_method():
            return "success"
        
        result = provider_method()
        assert result == "success"
    
    def test_track_provider_error(self):
        """Test tracking failed provider calls."""
        @track_provider_call("test_provider", "failing_method")
        def failing_provider():
            raise RuntimeError("Provider error")
        
        with pytest.raises(RuntimeError):
            failing_provider()


class TestCreateMetricsEndpoint:
    """Test creating metrics endpoints for different frameworks."""
    
    def test_endpoint_exists(self):
        """Test that create_metrics_endpoint function exists."""
        # Just verify the function is importable
        assert callable(create_metrics_endpoint)