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
        metric = Metric("test_metric", MetricType.COUNTER, "A test metric")
        assert metric.name == "test_metric"
        assert metric.type == MetricType.COUNTER
        assert metric.description == "A test metric"
        assert metric.labels == {}
    
    def test_metric_with_labels(self):
        """Test metric with labels."""
        metric = Metric(
            "http_requests",
            MetricType.COUNTER,
            "HTTP request count",
            labels={"method": "GET", "endpoint": "/api/v1/health"}
        )
        assert metric.labels == {"method": "GET", "endpoint": "/api/v1/health"}
    
    def test_metric_value_not_implemented(self):
        """Test that base metric value raises NotImplementedError."""
        metric = Metric("test", MetricType.GAUGE, "test")
        with pytest.raises(NotImplementedError):
            metric.value()
    
    def test_metric_str_representation(self):
        """Test string representation of metric."""
        metric = Metric("cpu_usage", MetricType.GAUGE, "CPU usage percentage")
        str_repr = str(metric)
        assert "cpu_usage" in str_repr
        assert "gauge" in str_repr


class TestCounter:
    """Test the Counter metric class."""
    
    def test_counter_initialization(self):
        """Test counter starts at zero."""
        counter = Counter("request_count", "Total requests")
        assert counter.value() == 0
        assert counter._value == 0
    
    def test_counter_increment(self):
        """Test incrementing counter."""
        counter = Counter("error_count", "Total errors")
        counter.inc()
        assert counter.value() == 1
        
        counter.inc()
        counter.inc()
        assert counter.value() == 3
    
    def test_counter_increment_by_value(self):
        """Test incrementing by specific value."""
        counter = Counter("bytes_processed", "Bytes processed")
        counter.inc(100)
        assert counter.value() == 100
        
        counter.inc(250)
        assert counter.value() == 350
    
    def test_counter_no_decrement(self):
        """Test that counters cannot decrease."""
        counter = Counter("test", "test")
        counter.inc(10)
        
        # Incrementing by negative should be ignored or raise error
        counter.inc(-5)
        assert counter.value() >= 10  # Should not decrease
    
    def test_counter_thread_safety(self):
        """Test counter is thread-safe."""
        counter = Counter("concurrent_count", "Concurrent counter")
        
        def increment_many():
            for _ in range(1000):
                counter.inc()
        
        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert counter.value() == 10000


class TestGauge:
    """Test the Gauge metric class."""
    
    def test_gauge_initialization(self):
        """Test gauge starts at zero."""
        gauge = Gauge("memory_usage", "Memory usage in MB")
        assert gauge.value() == 0
    
    def test_gauge_set(self):
        """Test setting gauge value."""
        gauge = Gauge("temperature", "Temperature in Celsius")
        gauge.set(25.5)
        assert gauge.value() == 25.5
        
        gauge.set(30.0)
        assert gauge.value() == 30.0
    
    def test_gauge_inc_dec(self):
        """Test incrementing and decrementing gauge."""
        gauge = Gauge("active_connections", "Active connections")
        gauge.set(10)
        
        gauge.inc()
        assert gauge.value() == 11
        
        gauge.inc(5)
        assert gauge.value() == 16
        
        gauge.dec()
        assert gauge.value() == 15
        
        gauge.dec(3)
        assert gauge.value() == 12
    
    def test_gauge_can_be_negative(self):
        """Test gauge can have negative values."""
        gauge = Gauge("profit_loss", "Profit/Loss")
        gauge.set(-100)
        assert gauge.value() == -100
        
        gauge.inc(50)
        assert gauge.value() == -50
    
    def test_gauge_thread_safety(self):
        """Test gauge operations are thread-safe."""
        gauge = Gauge("concurrent_gauge", "Concurrent gauge")
        gauge.set(0)
        
        def modify_gauge():
            for _ in range(100):
                gauge.inc()
                time.sleep(0.0001)
                gauge.dec()
        
        threads = [threading.Thread(target=modify_gauge) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should end up back at 0
        assert gauge.value() == 0


class TestHistogram:
    """Test the Histogram metric class."""
    
    def test_histogram_initialization(self):
        """Test histogram with default buckets."""
        hist = Histogram("response_time", "Response time in seconds")
        assert hist._sum == 0
        assert hist._count == 0
        assert len(hist._buckets) > 0
        assert hist._bucket_counts == {b: 0 for b in hist._buckets}
    
    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        buckets = [0.1, 0.5, 1.0, 2.0, 5.0]
        hist = Histogram("custom_hist", "Custom histogram", buckets=buckets)
        assert hist._buckets == buckets
    
    def test_histogram_observe(self):
        """Test observing values in histogram."""
        hist = Histogram("latency", "Latency", buckets=[1, 5, 10, 50, 100])
        
        hist.observe(0.5)
        hist.observe(3)
        hist.observe(7)
        hist.observe(25)
        hist.observe(150)
        
        assert hist._count == 5
        assert hist._sum == 0.5 + 3 + 7 + 25 + 150
        
        # Check bucket counts
        assert hist._bucket_counts[1] == 1    # 0.5
        assert hist._bucket_counts[5] == 2    # 0.5, 3
        assert hist._bucket_counts[10] == 3   # 0.5, 3, 7
        assert hist._bucket_counts[50] == 4   # 0.5, 3, 7, 25
        assert hist._bucket_counts[100] == 4  # 150 exceeds all buckets
    
    def test_histogram_value(self):
        """Test histogram value representation."""
        hist = Histogram("test", "test", buckets=[10, 20, 30])
        hist.observe(5)
        hist.observe(15)
        hist.observe(25)
        
        value = hist.value()
        assert value['count'] == 3
        assert value['sum'] == 45
        assert value['buckets'] == {10: 1, 20: 2, 30: 3}
    
    def test_histogram_percentiles(self):
        """Test calculating percentiles from histogram."""
        hist = Histogram("percentile_test", "test", buckets=[1, 2, 5, 10, 20])
        
        # Add many observations
        for i in range(100):
            hist.observe(i % 15)
        
        p50 = hist.get_percentile(0.5)
        p95 = hist.get_percentile(0.95)
        p99 = hist.get_percentile(0.99)
        
        assert p50 <= p95 <= p99
        assert p50 >= 0
        assert p99 <= 20  # Should be within bucket range


class TestSummary:
    """Test the Summary metric class."""
    
    def test_summary_initialization(self):
        """Test summary initialization."""
        summary = Summary("process_duration", "Process duration")
        assert summary._count == 0
        assert summary._sum == 0
        assert len(summary._observations) == 0
    
    def test_summary_observe(self):
        """Test observing values in summary."""
        summary = Summary("request_size", "Request size in bytes")
        
        summary.observe(100)
        summary.observe(200)
        summary.observe(150)
        
        assert summary._count == 3
        assert summary._sum == 450
        assert len(summary._observations) <= summary._max_observations
    
    def test_summary_sliding_window(self):
        """Test summary maintains sliding window."""
        summary = Summary("test", "test", max_observations=5)
        
        for i in range(10):
            summary.observe(i)
        
        # Should only keep last 5 observations
        assert len(summary._observations) == 5
        assert summary._observations == list(range(5, 10))
    
    def test_summary_value(self):
        """Test summary value with statistics."""
        summary = Summary("stats_test", "test")
        
        values = [10, 20, 30, 40, 50]
        for v in values:
            summary.observe(v)
        
        value = summary.value()
        assert value['count'] == 5
        assert value['sum'] == 150
        
        stats = summary.get_stats()
        assert stats['mean'] == 30
        assert stats['min'] == 10
        assert stats['max'] == 50
        assert 'p50' in stats
        assert 'p90' in stats
        assert 'p99' in stats
    
    def test_summary_percentiles(self):
        """Test summary percentile calculations."""
        summary = Summary("percentiles", "test")
        
        # Add values 0-99
        for i in range(100):
            summary.observe(i)
        
        stats = summary.get_stats()
        assert abs(stats['p50'] - 49.5) < 2  # Approximate median
        assert stats['p90'] >= 89
        assert stats['p99'] >= 98


class TestMetricsCollector:
    """Test the MetricsCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a fresh collector instance."""
        # Clear singleton
        MetricsCollector._instance = None
        return MetricsCollector()
    
    def test_singleton_pattern(self):
        """Test collector follows singleton pattern."""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()
        assert collector1 is collector2
    
    def test_register_and_get_metric(self, collector):
        """Test registering and retrieving metrics."""
        counter = collector.counter("test_counter", "Test counter")
        assert isinstance(counter, Counter)
        
        # Getting same metric returns same instance
        counter2 = collector.get_metric("test_counter")
        assert counter is counter2
    
    def test_register_different_metric_types(self, collector):
        """Test registering all metric types."""
        counter = collector.counter("my_counter", "Counter")
        gauge = collector.gauge("my_gauge", "Gauge")
        hist = collector.histogram("my_hist", "Histogram", buckets=[1, 5, 10])
        summary = collector.summary("my_summary", "Summary")
        
        assert isinstance(counter, Counter)
        assert isinstance(gauge, Gauge)
        assert isinstance(hist, Histogram)
        assert isinstance(summary, Summary)
    
    def test_metrics_with_labels(self, collector):
        """Test metrics with labels create separate instances."""
        counter1 = collector.counter(
            "http_requests",
            "HTTP requests",
            labels={"method": "GET"}
        )
        counter2 = collector.counter(
            "http_requests",
            "HTTP requests",
            labels={"method": "POST"}
        )
        
        counter1.inc()
        counter1.inc()
        counter2.inc()
        
        assert counter1.value() == 2
        assert counter2.value() == 1
    
    def test_list_metrics(self, collector):
        """Test listing all registered metrics."""
        collector.counter("counter1", "First counter")
        collector.gauge("gauge1", "First gauge")
        collector.counter("counter2", "Second counter", labels={"env": "prod"})
        
        metrics = collector.list_metrics()
        assert len(metrics) >= 3
        
        names = [m['name'] for m in metrics]
        assert "counter1" in names
        assert "gauge1" in names
    
    def test_clear_metrics(self, collector):
        """Test clearing all metrics."""
        collector.counter("test1", "test")
        collector.gauge("test2", "test")
        
        collector.clear()
        
        metrics = collector.list_metrics()
        assert len(metrics) == 0
    
    @patch('src.api.metrics.psutil.cpu_percent')
    @patch('src.api.metrics.psutil.virtual_memory')
    @patch('src.api.metrics.psutil.disk_usage')
    def test_resource_monitoring(self, mock_disk, mock_memory, mock_cpu, collector):
        """Test system resource monitoring."""
        # Mock system metrics
        mock_cpu.return_value = 45.5
        mock_memory.return_value = MagicMock(percent=67.8)
        mock_disk.return_value = MagicMock(percent=23.4)
        
        # Start monitoring
        collector._start_resource_monitoring()
        
        # Wait a bit for monitoring to run
        time.sleep(0.1)
        
        # Check that system metrics were created
        cpu_gauge = collector.get_metric("system_cpu_usage_percent")
        memory_gauge = collector.get_metric("system_memory_usage_percent")
        disk_gauge = collector.get_metric("system_disk_usage_percent")
        
        assert cpu_gauge is not None
        assert memory_gauge is not None
        assert disk_gauge is not None
        
        # Stop monitoring
        collector._monitoring = False
        if hasattr(collector, '_monitor_thread'):
            collector._monitor_thread.join(timeout=1)
    
    def test_export_prometheus(self, collector):
        """Test Prometheus format export."""
        # Create some metrics
        requests = collector.counter("http_requests_total", "Total HTTP requests")
        requests.inc(100)
        
        memory = collector.gauge("memory_usage_mb", "Memory usage in MB")
        memory.set(1024)
        
        response_time = collector.histogram(
            "response_time_seconds",
            "Response time",
            buckets=[0.1, 0.5, 1.0]
        )
        response_time.observe(0.25)
        response_time.observe(0.75)
        
        # Export metrics
        output = collector.export_prometheus()
        
        # Check output format
        assert "# HELP http_requests_total Total HTTP requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert "http_requests_total 100" in output
        
        assert "# HELP memory_usage_mb Memory usage in MB" in output
        assert "# TYPE memory_usage_mb gauge" in output
        assert "memory_usage_mb 1024" in output
        
        assert "# HELP response_time_seconds Response time" in output
        assert "# TYPE response_time_seconds histogram" in output
        assert "response_time_seconds_bucket" in output
        assert "response_time_seconds_count 2" in output
    
    def test_export_with_labels(self, collector):
        """Test Prometheus export with labeled metrics."""
        collector.counter(
            "api_calls",
            "API calls",
            labels={"service": "auth", "method": "login"}
        ).inc(50)
        
        collector.counter(
            "api_calls",
            "API calls",
            labels={"service": "auth", "method": "logout"}
        ).inc(30)
        
        output = collector.export_prometheus()
        
        assert 'api_calls{service="auth",method="login"} 50' in output
        assert 'api_calls{service="auth",method="logout"} 30' in output
    
    def test_get_summary(self, collector):
        """Test getting metrics summary."""
        collector.counter("counter1", "test").inc(10)
        collector.gauge("gauge1", "test").set(5.5)
        collector.histogram("hist1", "test").observe(1.0)
        
        summary = collector.get_summary()
        
        assert summary['total_metrics'] >= 3
        assert summary['counters'] >= 1
        assert summary['gauges'] >= 1
        assert summary['histograms'] >= 1
        assert 'collection_timestamp' in summary


class TestTrackDurationDecorator:
    """Test the track_duration decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_collector(self):
        """Reset metrics collector."""
        MetricsCollector._instance = None
        yield
        MetricsCollector._instance = None
    
    def test_track_duration_function(self):
        """Test tracking function execution duration."""
        @track_duration("test_function_duration")
        def slow_function():
            time.sleep(0.1)
            return "done"
        
        result = slow_function()
        assert result == "done"
        
        # Check that metric was created and recorded
        collector = MetricsCollector()
        metric = collector.get_metric("test_function_duration_seconds")
        assert metric is not None
        assert isinstance(metric, Histogram)
        assert metric._count == 1
        assert metric._sum >= 0.1
    
    def test_track_duration_with_exception(self):
        """Test duration tracking when function raises exception."""
        @track_duration("error_function_duration")
        def error_function():
            time.sleep(0.05)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            error_function()
        
        # Duration should still be recorded
        collector = MetricsCollector()
        metric = collector.get_metric("error_function_duration_seconds")
        assert metric._count == 1
        assert metric._sum >= 0.05
    
    def test_track_duration_method(self):
        """Test tracking method execution duration."""
        class TestClass:
            @track_duration("method_duration")
            def process(self, x, y):
                time.sleep(0.02)
                return x + y
        
        obj = TestClass()
        result = obj.process(3, 4)
        assert result == 7
        
        collector = MetricsCollector()
        metric = collector.get_metric("method_duration_seconds")
        assert metric._count == 1
    
    def test_track_duration_custom_metric_name(self):
        """Test custom metric naming in decorator."""
        @track_duration("custom_metric", description="Custom timing metric")
        def custom_function():
            return 42
        
        custom_function()
        
        collector = MetricsCollector()
        metric = collector.get_metric("custom_metric_seconds")
        assert metric is not None
        assert metric.description == "Custom timing metric"


class TestTrackProviderCallDecorator:
    """Test the track_provider_call decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_collector(self):
        """Reset metrics collector."""
        MetricsCollector._instance = None
        yield
        MetricsCollector._instance = None
    
    def test_track_provider_success(self):
        """Test tracking successful provider calls."""
        @track_provider_call("test_provider")
        def provider_method():
            time.sleep(0.01)
            return "success"
        
        result = provider_method()
        assert result == "success"
        
        collector = MetricsCollector()
        
        # Check call counter
        calls = collector.get_metric("provider_calls_total")
        assert calls.labels == {"provider": "test_provider", "status": "success"}
        assert calls.value() == 1
        
        # Check duration histogram
        duration = collector.get_metric("provider_call_duration_seconds")
        assert duration.labels == {"provider": "test_provider"}
        assert duration._count == 1
    
    def test_track_provider_error(self):
        """Test tracking failed provider calls."""
        @track_provider_call("error_provider")
        def failing_provider():
            raise RuntimeError("Provider error")
        
        with pytest.raises(RuntimeError):
            failing_provider()
        
        collector = MetricsCollector()
        
        # Check error counter
        errors = collector.get_metric("provider_errors_total")
        assert errors.labels == {"provider": "error_provider", "error_type": "RuntimeError"}
        assert errors.value() == 1
        
        # Check call counter with error status
        calls = collector.get_metric("provider_calls_total")
        assert calls.labels == {"provider": "error_provider", "status": "error"}
        assert calls.value() == 1
    
    def test_track_provider_multiple_calls(self):
        """Test tracking multiple provider calls."""
        @track_provider_call("multi_provider")
        def sometimes_failing(should_fail):
            if should_fail:
                raise ValueError("Planned failure")
            return "ok"
        
        # Make some successful calls
        sometimes_failing(False)
        sometimes_failing(False)
        
        # Make some failing calls
        for _ in range(3):
            try:
                sometimes_failing(True)
            except ValueError:
                pass
        
        collector = MetricsCollector()
        
        # Check success calls
        success_calls = next(
            m for m in collector._metrics.values()
            if m.name == "provider_calls_total" 
            and m.labels.get("status") == "success"
        )
        assert success_calls.value() == 2
        
        # Check error calls
        error_calls = next(
            m for m in collector._metrics.values()
            if m.name == "provider_calls_total"
            and m.labels.get("status") == "error"
        )
        assert error_calls.value() == 3


class TestCreateMetricsEndpoint:
    """Test the create_metrics_endpoint function."""
    
    def test_create_flask_endpoint(self):
        """Test creating metrics endpoint for Flask."""
        from flask import Flask
        
        app = Flask(__name__)
        endpoint = create_metrics_endpoint(app)
        
        # Check that endpoint was added
        assert '/metrics' in [rule.rule for rule in app.url_map.iter_rules()]
        
        # Test the endpoint
        with app.test_client() as client:
            response = client.get('/metrics')
            assert response.status_code == 200
            assert response.content_type == 'text/plain; charset=utf-8'
            assert b'# HELP' in response.data
    
    def test_create_fastapi_endpoint(self):
        """Test creating metrics endpoint for FastAPI."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        endpoint = create_metrics_endpoint(app)
        
        # Test the endpoint
        client = TestClient(app)
        response = client.get('/metrics')
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/plain; charset=utf-8'
        assert '# HELP' in response.text
    
    def test_endpoint_with_custom_path(self):
        """Test creating endpoint with custom path."""
        from flask import Flask
        
        app = Flask(__name__)
        endpoint = create_metrics_endpoint(app, path='/custom/metrics')
        
        assert '/custom/metrics' in [rule.rule for rule in app.url_map.iter_rules()]
    
    def test_unsupported_framework(self):
        """Test handling unsupported framework."""
        class UnsupportedApp:
            pass
        
        app = UnsupportedApp()
        result = create_metrics_endpoint(app)
        assert result is None