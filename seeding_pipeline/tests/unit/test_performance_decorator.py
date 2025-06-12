"""Comprehensive unit tests for performance decorator utilities."""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import json
import time

import pytest

from src.utils.performance_decorator import (
    PerformanceMetrics,
    PerformanceTracker,
    profile_performance,
    track_llm_tokens,
    create_performance_dashboard,
    _generate_performance_recommendations
)


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass."""
    
    def test_performance_metrics_creation(self):
        """Test creating PerformanceMetrics."""
        metrics = PerformanceMetrics(
            component_name="test_component",
            execution_time=1.5,
            memory_used=1024 * 1024,
            memory_peak=2048 * 1024,
            cpu_percent=25.5,
            tokens_used=100
        )
        
        assert metrics.component_name == "test_component"
        assert metrics.execution_time == 1.5
        assert metrics.memory_used == 1024 * 1024
        assert metrics.memory_peak == 2048 * 1024
        assert metrics.cpu_percent == 25.5
        assert metrics.tokens_used == 100
        assert metrics.timestamp != ""
    
    def test_performance_metrics_auto_timestamp(self):
        """Test automatic timestamp generation."""
        metrics = PerformanceMetrics(
            component_name="test",
            execution_time=1.0,
            memory_used=1024,
            memory_peak=2048,
            cpu_percent=10.0
        )
        
        # Should have auto-generated timestamp
        assert metrics.timestamp
        # Should be parseable as datetime
        datetime.fromisoformat(metrics.timestamp)
    
    def test_performance_metrics_custom_timestamp(self):
        """Test using custom timestamp."""
        custom_timestamp = "2023-12-25T10:00:00"
        metrics = PerformanceMetrics(
            component_name="test",
            execution_time=1.0,
            memory_used=1024,
            memory_peak=2048,
            cpu_percent=10.0,
            timestamp=custom_timestamp
        )
        
        assert metrics.timestamp == custom_timestamp


class TestPerformanceTracker:
    """Test PerformanceTracker class."""
    
    @patch('src.utils.performance_decorator.get_metrics_collector')
    @patch('src.utils.performance_decorator.get_component_tracker')
    @patch('src.utils.performance_decorator.psutil.Process')
    def test_tracker_initialization(self, mock_process_class, mock_get_tracker, mock_get_metrics):
        """Test PerformanceTracker initialization."""
        mock_metrics = Mock()
        mock_tracker = Mock()
        mock_process = Mock()
        
        mock_get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker
        mock_process_class.return_value = mock_process
        
        tracker = PerformanceTracker()
        
        assert tracker.metrics_collector == mock_metrics
        assert tracker.component_tracker == mock_tracker
        assert tracker.process == mock_process
    
    @patch('src.utils.performance_decorator.tracemalloc')
    @patch('src.utils.performance_decorator.time')
    @patch('src.utils.performance_decorator.get_metrics_collector')
    @patch('src.utils.performance_decorator.get_component_tracker')
    @patch('src.utils.performance_decorator.psutil.Process')
    def test_track_performance_success(self, mock_process_class, mock_get_tracker, 
                                     mock_get_metrics, mock_time, mock_tracemalloc):
        """Test tracking performance successfully."""
        # Setup mocks
        mock_process = Mock()
        mock_process.memory_info.side_effect = [
            Mock(rss=1000 * 1024),  # Start memory
            Mock(rss=2000 * 1024)   # End memory
        ]
        mock_process.cpu_percent.side_effect = [20.0, 30.0]
        mock_process_class.return_value = mock_process
        
        mock_time.time.side_effect = [1.0, 2.5]  # Start and end time
        mock_tracemalloc.get_traced_memory.return_value = (500 * 1024, 1500 * 1024)
        
        tracker = PerformanceTracker()
        
        # Test function
        def test_func(x, y):
            return x + y
        
        result, metrics = tracker.track_performance("test_component", test_func, 2, 3)
        
        # Verify result
        assert result == 5
        
        # Verify metrics
        assert metrics.component_name == "test_component"
        assert metrics.execution_time == 1.5  # 2.5 - 1.0
        assert metrics.memory_used == 1000 * 1024  # 2000 - 1000
        assert metrics.memory_peak == 1500 * 1024
        assert metrics.cpu_percent == 25.0  # (20 + 30) / 2
        assert metrics.tokens_used is None
        
        # Verify tracking calls
        mock_tracemalloc.start.assert_called_once()
        mock_tracemalloc.stop.assert_called_once()
    
    @patch('src.utils.performance_decorator.tracemalloc')
    @patch('src.utils.performance_decorator.psutil.Process')
    def test_track_performance_with_token_usage(self, mock_process_class, mock_tracemalloc):
        """Test tracking performance with token usage."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=1024)
        mock_process.cpu_percent.return_value = 10.0
        mock_process_class.return_value = mock_process
        
        mock_tracemalloc.get_traced_memory.return_value = (1024, 2048)
        
        tracker = PerformanceTracker()
        
        # Test function that returns object with token usage
        class Result:
            def __init__(self):
                self.value = "test"
                self.__token_usage__ = 150
        
        def test_func():
            return Result()
        
        result, metrics = tracker.track_performance("test", test_func)
        
        assert result.value == "test"
        assert metrics.tokens_used == 150
    
    @patch('src.utils.performance_decorator.tracemalloc')
    @patch('src.utils.performance_decorator.logger')
    @patch('src.utils.performance_decorator.psutil.Process')
    def test_track_performance_with_error(self, mock_process_class, mock_logger, mock_tracemalloc):
        """Test tracking performance when function raises error."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=1024)
        mock_process.cpu_percent.return_value = 10.0
        mock_process_class.return_value = mock_process
        
        tracker = PerformanceTracker()
        
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            tracker.track_performance("failing", failing_func)
        
        # Should stop tracemalloc and log error
        mock_tracemalloc.stop.assert_called_once()
        mock_logger.error.assert_called_once()
    
    @patch('src.utils.performance_decorator.get_metrics_collector')
    @patch('src.utils.performance_decorator.get_component_tracker')
    def test_record_metrics(self, mock_get_tracker, mock_get_metrics):
        """Test recording metrics."""
        # Setup mocks
        mock_metrics_collector = Mock()
        mock_component_tracker = Mock()
        mock_impact_context = Mock()
        
        mock_get_metrics.return_value = mock_metrics_collector
        mock_get_tracker.return_value = mock_component_tracker
        mock_component_tracker.track_impact.return_value.__enter__ = Mock(return_value=mock_impact_context)
        mock_component_tracker.track_impact.return_value.__exit__ = Mock()
        
        tracker = PerformanceTracker()
        
        # Create test metrics
        metrics = PerformanceMetrics(
            component_name="test",
            execution_time=1.5,
            memory_used=1024 * 1024,
            memory_peak=2048 * 1024,
            cpu_percent=25.0,
            tokens_used=100
        )
        
        tracker._record_metrics(metrics)
        
        # Verify Prometheus metrics
        mock_metrics_collector.processing_duration.observe.assert_called_once_with(
            1.5,
            labels={"stage": "component_test"}
        )
        mock_metrics_collector.memory_usage.set.assert_called_once_with(1024 * 1024)
        mock_metrics_collector.cpu_usage.set.assert_called_once_with(25.0)
        
        # Verify component tracker
        mock_component_tracker.track_impact.assert_called_once_with("test")
        mock_impact_context.add_metadata.assert_has_calls([
            call("execution_time", 1.5),
            call("memory_used", 1024 * 1024),
            call("cpu_percent", 25.0),
            call("tokens_used", 100)
        ])


class TestProfilePerformanceDecorator:
    """Test profile_performance decorator."""
    
    @patch('src.utils.performance_decorator.is_enabled')
    @patch('src.utils.performance_decorator.PerformanceTracker')
    def test_profile_performance_enabled(self, mock_tracker_class, mock_is_enabled):
        """Test profile_performance when feature is enabled."""
        mock_is_enabled.return_value = True
        
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        mock_metrics = PerformanceMetrics(
            component_name="test_func",
            execution_time=1.0,
            memory_used=1024,
            memory_peak=2048,
            cpu_percent=10.0
        )
        mock_tracker.track_performance.return_value = ("result", mock_metrics)
        
        @profile_performance()
        def test_func(x):
            return x * 2
        
        result = test_func(5)
        
        assert result == "result"
        mock_tracker.track_performance.assert_called_once()
        assert test_func.__profiled__ is True
        assert test_func.__component_name__ == "test_func"
    
    @patch('src.utils.performance_decorator.is_enabled')
    def test_profile_performance_disabled(self, mock_is_enabled):
        """Test profile_performance when feature is disabled."""
        mock_is_enabled.return_value = False
        
        @profile_performance()
        def test_func(x):
            return x * 2
        
        result = test_func(5)
        
        # Should execute function normally without tracking
        assert result == 10
    
    @patch('src.utils.performance_decorator.is_enabled')
    @patch('src.utils.performance_decorator.PerformanceTracker')
    @patch('src.utils.performance_decorator.logger')
    def test_profile_performance_custom_name(self, mock_logger, mock_tracker_class, mock_is_enabled):
        """Test profile_performance with custom component name."""
        mock_is_enabled.return_value = True
        
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        mock_metrics = PerformanceMetrics(
            component_name="custom_component",
            execution_time=2.5,
            memory_used=2048 * 1024,
            memory_peak=4096 * 1024,
            cpu_percent=30.0
        )
        mock_tracker.track_performance.return_value = ("result", mock_metrics)
        
        @profile_performance(component_name="custom_component")
        def test_func():
            return "test"
        
        result = test_func()
        
        assert result == "result"
        assert test_func.__component_name__ == "custom_component"
        
        # Check logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "custom_component" in log_message
        assert "2.500s" in log_message
        assert "2.0MB" in log_message


class TestTrackLLMTokens:
    """Test track_llm_tokens decorator."""
    
    def test_track_llm_tokens_with_usage_attribute(self):
        """Test tracking tokens from result with usage attribute."""
        # Mock LLM response
        class MockUsage:
            prompt_tokens = 50
            completion_tokens = 100
            total_tokens = 150
        
        class MockResult:
            def __init__(self):
                self.content = "Generated text"
                self.usage = MockUsage()
        
        @track_llm_tokens
        def generate_text():
            return MockResult()
        
        result = generate_text()
        
        assert result.content == "Generated text"
        assert hasattr(result, '__token_usage__')
        assert result.__token_usage__['prompt_tokens'] == 50
        assert result.__token_usage__['completion_tokens'] == 100
        assert result.__token_usage__['total_tokens'] == 150
    
    def test_track_llm_tokens_with_dict_result(self):
        """Test tracking tokens from dictionary result."""
        @track_llm_tokens
        def generate_text():
            return {
                "content": "Generated text",
                "usage": {
                    "prompt_tokens": 60,
                    "completion_tokens": 120,
                    "total_tokens": 180
                }
            }
        
        result = generate_text()
        
        assert result["content"] == "Generated text"
        assert "__token_usage__" in result
        assert result["__token_usage__"]["prompt_tokens"] == 60
        assert result["__token_usage__"]["completion_tokens"] == 120
        assert result["__token_usage__"]["total_tokens"] == 180
    
    @patch('src.utils.performance_decorator.logger')
    def test_track_llm_tokens_no_usage(self, mock_logger):
        """Test tracking tokens when no usage info available."""
        @track_llm_tokens
        def generate_text():
            return "Just a string"
        
        result = generate_text()
        
        assert result == "Just a string"
        # No token usage should be logged
        mock_logger.debug.assert_not_called()
    
    @patch('src.utils.performance_decorator.logger')
    def test_track_llm_tokens_logging(self, mock_logger):
        """Test token usage logging."""
        @track_llm_tokens
        def generate_text():
            return {
                "content": "text",
                "usage": {"total_tokens": 100}
            }
        
        generate_text()
        
        mock_logger.debug.assert_called_once()
        log_message = mock_logger.debug.call_args[0][0]
        assert "LLM tokens used" in log_message


class TestCreatePerformanceDashboard:
    """Test create_performance_dashboard function."""
    
    @patch('src.utils.performance_decorator.get_component_tracker')
    @patch('src.utils.performance_decorator.get_metrics_collector')
    def test_create_performance_dashboard(self, mock_get_metrics, mock_get_tracker):
        """Test creating performance dashboard."""
        # Setup mocks
        mock_tracker = Mock()
        mock_tracker.generate_impact_report.return_value = {
            "components": {
                "entity_extraction": {"avg_time": 0.5},
                "insight_generation": {"avg_time": 1.2}
            }
        }
        mock_get_tracker.return_value = mock_tracker
        
        mock_metrics = Mock()
        mock_metrics.get_summary.return_value = {
            "resources": {"memory_mb": 512}
        }
        mock_get_metrics.return_value = mock_metrics
        
        dashboard = create_performance_dashboard()
        
        assert "generated_at" in dashboard
        assert "component_impacts" in dashboard
        assert "performance_metrics" in dashboard
        assert "recommendations" in dashboard
        
        # Check generated timestamp
        datetime.fromisoformat(dashboard["generated_at"])
    
    @patch('src.utils.performance_decorator.get_component_tracker')
    @patch('src.utils.performance_decorator.get_metrics_collector')
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_create_performance_dashboard_with_output(self, mock_json_dump, mock_open,
                                                    mock_get_metrics, mock_get_tracker):
        """Test creating dashboard with file output."""
        # Setup mocks
        mock_tracker = Mock()
        mock_tracker.generate_impact_report.return_value = {}
        mock_get_tracker.return_value = mock_tracker
        
        mock_metrics = Mock()
        mock_metrics.get_summary.return_value = {}
        mock_get_metrics.return_value = mock_metrics
        
        output_path = "/tmp/dashboard.json"
        dashboard = create_performance_dashboard(output_path)
        
        # Should save to file
        mock_open.assert_called_once_with(output_path, 'w')
        mock_json_dump.assert_called_once()
        
        # Check dashboard was saved
        saved_data = mock_json_dump.call_args[0][0]
        assert saved_data == dashboard


class TestGeneratePerformanceRecommendations:
    """Test _generate_performance_recommendations function."""
    
    def test_generate_recommendations_slow_components(self):
        """Test generating recommendations for slow components."""
        impact_report = {
            "components": {
                "slow_component": {"avg_time": 2.5},
                "fast_component": {"avg_time": 0.5}
            }
        }
        metrics_summary = {"resources": {"memory_mb": 500}}
        
        recommendations = _generate_performance_recommendations(impact_report, metrics_summary)
        
        # Should have recommendation for slow component
        assert len(recommendations) >= 1
        assert any("slow_component" in rec and "2.5s" in rec for rec in recommendations)
        assert not any("fast_component" in rec for rec in recommendations)
    
    def test_generate_recommendations_high_memory(self):
        """Test generating recommendations for high memory usage."""
        impact_report = {"components": {}}
        metrics_summary = {"resources": {"memory_mb": 1500}}
        
        recommendations = _generate_performance_recommendations(impact_report, metrics_summary)
        
        # Should have memory recommendation
        assert any("memory usage" in rec.lower() for rec in recommendations)
        assert any("streaming" in rec or "chunking" in rec for rec in recommendations)
    
    def test_generate_recommendations_redundant_components(self):
        """Test generating recommendations for redundant components."""
        impact_report = {
            "components": {},
            "recommendations": [
                {"type": "no_additions", "component": "useless_component"},
                {"type": "other", "component": "useful_component"}
            ]
        }
        metrics_summary = {"resources": {"memory_mb": 500}}
        
        recommendations = _generate_performance_recommendations(impact_report, metrics_summary)
        
        # Should recommend removing redundant component
        assert any("useless_component" in rec and "remove" in rec for rec in recommendations)
        assert not any("useful_component" in rec for rec in recommendations)
    
    def test_generate_recommendations_all_good(self):
        """Test when no recommendations needed."""
        impact_report = {
            "components": {
                "fast_component": {"avg_time": 0.2}
            }
        }
        metrics_summary = {"resources": {"memory_mb": 200}}
        
        recommendations = _generate_performance_recommendations(impact_report, metrics_summary)
        
        # Should have no recommendations
        assert len(recommendations) == 0