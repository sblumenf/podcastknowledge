"""Comprehensive unit tests for performance profiling utilities."""

import json
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import io
import pstats
import cProfile

from src.utils.performance_profiling import (
    ProfileResult,
    PerformanceProfiler,
    profile_function,
    OptimizationManager,
    BatchOptimizer,
    CacheOptimizer,
    AsyncOptimizer,
    ConnectionPoolOptimizer
)


class TestProfileResult:
    """Test ProfileResult dataclass."""
    
    def test_profile_result_creation(self):
        """Test creating ProfileResult."""
        result = ProfileResult(
            name="test_profile",
            duration=1.5,
            cpu_time=1.2,
            memory_used=1024 * 1024,
            memory_peak=2048 * 1024,
            call_count=100,
            bottlenecks=[("func1", 0.5), ("func2", 0.3)],
            timestamp="2023-12-25T10:00:00"
        )
        
        assert result.name == "test_profile"
        assert result.duration == 1.5
        assert result.cpu_time == 1.2
        assert result.memory_used == 1024 * 1024
        assert result.memory_peak == 2048 * 1024
        assert result.call_count == 100
        assert len(result.bottlenecks) == 2
        assert result.timestamp == "2023-12-25T10:00:00"


class TestPerformanceProfiler:
    """Test PerformanceProfiler class."""
    
    def test_profiler_initialization(self):
        """Test profiler initialization."""
        profiler = PerformanceProfiler()
        
        assert profiler.output_dir == Path("profiling_results")
        assert profiler.output_dir.exists()
        assert profiler.results == []
        assert profiler.metrics is not None
    
    def test_profiler_custom_output_dir(self):
        """Test profiler with custom output directory."""
        custom_dir = Path("/tmp/test_profiling")
        profiler = PerformanceProfiler(output_dir=custom_dir)
        
        assert profiler.output_dir == custom_dir
        assert profiler.output_dir.exists()
    
    @patch('src.utils.performance_profiling.tracemalloc')
    @patch('src.utils.performance_profiling.time')
    @patch('src.utils.performance_profiling.cProfile.Profile')
    def test_profile_section_success(self, mock_profile_class, mock_time, mock_tracemalloc):
        """Test profiling a section successfully."""
        # Setup mocks
        mock_profiler = Mock()
        mock_profile_class.return_value = mock_profiler
        
        mock_time.time.side_effect = [1.0, 2.5]  # Start and end time
        mock_time.process_time.side_effect = [0.5, 1.5]  # Start and end CPU time
        
        mock_tracemalloc.get_traced_memory.return_value = (1024 * 1024, 2048 * 1024)
        
        # Mock pstats
        mock_stats = Mock()
        mock_stats.total_calls = 150
        mock_stats.stats = {
            ("file1.py", 10, "func1"): (1, 1, 0.1, 0.5, {}),
            ("file2.py", 20, "func2"): (1, 1, 0.1, 0.3, {}),
        }
        
        with patch('pstats.Stats', return_value=mock_stats):
            profiler = PerformanceProfiler()
            
            with profiler.profile_section("test_section"):
                # Simulate some work
                pass
            
            # Verify tracking was started/stopped
            mock_tracemalloc.start.assert_called_once()
            mock_tracemalloc.stop.assert_called_once()
            mock_profiler.enable.assert_called_once()
            mock_profiler.disable.assert_called_once()
            
            # Check result
            assert len(profiler.results) == 1
            result = profiler.results[0]
            assert result.name == "test_section"
            assert result.duration == 1.5  # 2.5 - 1.0
            assert result.cpu_time == 1.0  # 1.5 - 0.5
            assert result.memory_used == 1024 * 1024
            assert result.memory_peak == 2048 * 1024
            assert result.call_count == 150
            assert len(result.bottlenecks) > 0
    
    @patch('src.utils.performance_profiling.tracemalloc')
    @patch('src.utils.performance_profiling.time')
    def test_profile_section_without_memory_tracking(self, mock_time, mock_tracemalloc):
        """Test profiling without memory tracking."""
        mock_time.time.side_effect = [1.0, 2.0]
        mock_time.process_time.side_effect = [0.5, 1.0]
        
        profiler = PerformanceProfiler()
        
        with patch('pstats.Stats'):
            with profiler.profile_section("test_no_memory", track_memory=False):
                pass
            
            # Memory tracking should not be called
            mock_tracemalloc.start.assert_not_called()
            mock_tracemalloc.stop.assert_not_called()
            
            result = profiler.results[0]
            assert result.memory_used == 0
            assert result.memory_peak == 0
    
    @patch('src.utils.performance_profiling.logger')
    def test_profile_section_with_error(self, mock_logger):
        """Test profiling when section raises error."""
        profiler = PerformanceProfiler()
        
        with pytest.raises(ValueError):
            with profiler.profile_section("error_section"):
                raise ValueError("Test error")
        
        # Should still create result
        assert len(profiler.results) == 1
        assert profiler.results[0].name == "error_section"
    
    def test_extract_bottlenecks(self):
        """Test extracting bottlenecks from stats."""
        profiler = PerformanceProfiler()
        
        # Create mock stats
        mock_stats = Mock()
        mock_stats.stats = {
            ("file1.py", 10, "slow_func"): (1, 1, 0.1, 2.0, {}),
            ("file2.py", 20, "fast_func"): (1, 1, 0.1, 0.1, {}),
            ("file3.py", 30, "medium_func"): (1, 1, 0.1, 0.5, {}),
        }
        
        bottlenecks = profiler._extract_bottlenecks(mock_stats)
        
        assert len(bottlenecks) <= 10
        assert bottlenecks[0][0] == "file1.py:10:slow_func"
        assert bottlenecks[0][1] == 2.0
    
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_save_profile(self, mock_json_dump, mock_open):
        """Test saving profile data."""
        profiler = PerformanceProfiler()
        
        mock_profiler = Mock()
        result = ProfileResult(
            name="test",
            duration=1.0,
            cpu_time=0.8,
            memory_used=1024,
            memory_peak=2048,
            call_count=100,
            bottlenecks=[("func", 0.5)],
            timestamp="2023-12-25T10:00:00"
        )
        
        profiler._save_profile("test", mock_profiler, result)
        
        # Should save profile stats
        mock_profiler.dump_stats.assert_called_once()
        
        # Should save JSON result
        mock_open.assert_called()
        mock_json_dump.assert_called_once()
    
    def test_profile_schemaless_pipeline(self):
        """Test profiling schemaless pipeline."""
        profiler = PerformanceProfiler()
        
        # Mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.extract.return_value = {"entities": [], "insights": []}
        
        with patch.object(profiler, 'profile_section'):
            results = profiler.profile_schemaless_pipeline(mock_pipeline, "Test text")
            
            assert "profile_results" in results
            assert "analysis" in results
            mock_pipeline.extract.assert_called_once_with("Test text")
    
    def test_analyze_results_empty(self):
        """Test analyzing results with no data."""
        profiler = PerformanceProfiler()
        
        analysis = profiler.analyze_results()
        
        assert analysis["error"] == "No profiling results available"
    
    def test_analyze_results_with_data(self):
        """Test analyzing results with profiling data."""
        profiler = PerformanceProfiler()
        
        # Add test results
        profiler.results = [
            ProfileResult(
                name="section1",
                duration=2.0,
                cpu_time=1.8,
                memory_used=1024 * 1024,
                memory_peak=2048 * 1024,
                call_count=100,
                bottlenecks=[("func1", 1.0), ("func2", 0.5)],
                timestamp="2023-12-25T10:00:00"
            ),
            ProfileResult(
                name="section1",
                duration=3.0,
                cpu_time=2.5,
                memory_used=2048 * 1024,
                memory_peak=4096 * 1024,
                call_count=150,
                bottlenecks=[("func1", 1.5), ("func3", 0.8)],
                timestamp="2023-12-25T10:01:00"
            ),
            ProfileResult(
                name="section2",
                duration=1.0,
                cpu_time=0.9,
                memory_used=512 * 1024,
                memory_peak=1024 * 1024,
                call_count=50,
                bottlenecks=[("func4", 0.5)],
                timestamp="2023-12-25T10:02:00"
            )
        ]
        
        analysis = profiler.analyze_results()
        
        assert "summary" in analysis
        assert "bottlenecks" in analysis
        assert "recommendations" in analysis
        
        # Check summary
        assert "section1" in analysis["summary"]
        assert analysis["summary"]["section1"]["total_time"] == 5.0  # 2.0 + 3.0
        assert analysis["summary"]["section1"]["count"] == 2
        assert analysis["summary"]["section1"]["avg_time"] == 2.5
        
        # Check bottlenecks
        assert "func1" in analysis["bottlenecks"]
        assert analysis["bottlenecks"]["func1"] == 2.5  # 1.0 + 1.5
    
    def test_generate_recommendations(self):
        """Test generating optimization recommendations."""
        profiler = PerformanceProfiler()
        
        analysis = {
            "summary": {},
            "bottlenecks": {
                "llm_call": 10.0,
                "embedding_generate": 5.0,
                "neo4j_write": 3.0,
                "other_func": 1.0
            },
            "recommendations": []
        }
        
        section_stats = {
            "slow_section": {
                "avg_time": 10.0,
                "avg_memory": 600 * 1024 * 1024
            },
            "fast_section": {
                "avg_time": 1.0,
                "avg_memory": 100 * 1024 * 1024
            }
        }
        
        profiler._generate_recommendations(analysis, section_stats)
        
        recommendations = analysis["recommendations"]
        
        # Should have recommendations for slow section
        assert any(r["type"] == "performance" and r["section"] == "slow_section" 
                  for r in recommendations)
        
        # Should have memory recommendation
        assert any(r["type"] == "memory" and r["section"] == "slow_section" 
                  for r in recommendations)
        
        # Should have bottleneck recommendations
        assert any(r["type"] == "bottleneck" and "llm" in r["function"] 
                  for r in recommendations)
        assert any(r["type"] == "bottleneck" and "embed" in r["function"] 
                  for r in recommendations)
        assert any(r["type"] == "bottleneck" and ("neo4j" in r["function"] or "graph" in r["function"])
                  for r in recommendations)
    
    def test_generate_report(self):
        """Test generating profiling report."""
        profiler = PerformanceProfiler()
        
        # Add test result
        profiler.results = [
            ProfileResult(
                name="test_section",
                duration=1.5,
                cpu_time=1.2,
                memory_used=1024 * 1024,
                memory_peak=2048 * 1024,
                call_count=100,
                bottlenecks=[("slow_func", 1.0)],
                timestamp="2023-12-25T10:00:00"
            )
        ]
        
        report = profiler.generate_report()
        
        assert "# Performance Profiling Report" in report
        assert "test_section" in report
        assert "1.500s" in report
        assert "slow_func" in report
        assert "Recommendations" in report
    
    def test_generate_report_with_file(self):
        """Test generating report to file."""
        profiler = PerformanceProfiler()
        profiler.results = [
            ProfileResult(
                name="test",
                duration=1.0,
                cpu_time=0.8,
                memory_used=1024,
                memory_peak=2048,
                call_count=10,
                bottlenecks=[],
                timestamp="2023-12-25T10:00:00"
            )
        ]
        
        output_file = Mock()
        output_file.write_text = Mock()
        
        report = profiler.generate_report(output_file)
        
        output_file.write_text.assert_called_once_with(report)


class TestProfileFunction:
    """Test profile_function decorator."""
    
    @patch('src.utils.performance_profiling.PerformanceProfiler')
    def test_profile_function_decorator(self, mock_profiler_class):
        """Test profile function decorator."""
        mock_profiler = Mock()
        mock_profiler_class.return_value = mock_profiler
        
        # Create mock context manager
        mock_context = MagicMock()
        mock_profiler.profile_section.return_value = mock_context
        
        @profile_function()
        def test_func(x, y):
            return x + y
        
        result = test_func(1, 2)
        
        assert result == 3
        mock_profiler.profile_section.assert_called_once_with("test_func", True)
    
    @patch('src.utils.performance_profiling.PerformanceProfiler')
    def test_profile_function_custom_name(self, mock_profiler_class):
        """Test profile function with custom name."""
        mock_profiler = Mock()
        mock_profiler_class.return_value = mock_profiler
        
        mock_context = MagicMock()
        mock_profiler.profile_section.return_value = mock_context
        
        @profile_function(name="custom_profile")
        def test_func():
            return "result"
        
        result = test_func()
        
        assert result == "result"
        mock_profiler.profile_section.assert_called_once_with("custom_profile", True)
    
    @patch('src.utils.performance_profiling.PerformanceProfiler')
    @patch('src.utils.performance_profiling.logger')
    def test_profile_function_logging(self, mock_logger, mock_profiler_class):
        """Test profile function logs results."""
        mock_profiler = Mock()
        mock_profiler_class.return_value = mock_profiler
        
        # Setup mock result
        mock_result = ProfileResult(
            name="test",
            duration=1.5,
            cpu_time=1.2,
            memory_used=1024,
            memory_peak=2048,
            call_count=10,
            bottlenecks=[],
            timestamp="2023-12-25T10:00:00"
        )
        mock_profiler.results = [mock_result]
        
        mock_context = MagicMock()
        mock_profiler.profile_section.return_value = mock_context
        
        @profile_function()
        def test_func():
            return "done"
        
        test_func()
        
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "test_func" in log_message
        assert "1.500s" in log_message


class TestOptimizationManager:
    """Test OptimizationManager class."""
    
    def test_optimization_manager_initialization(self):
        """Test optimization manager initialization."""
        manager = OptimizationManager()
        
        assert isinstance(manager.batch_processor, BatchOptimizer)
        assert isinstance(manager.cache_manager, CacheOptimizer)
        assert isinstance(manager.async_manager, AsyncOptimizer)
        assert isinstance(manager.pool_manager, ConnectionPoolOptimizer)
    
    @patch('src.utils.performance_profiling.logger')
    def test_apply_optimizations(self, mock_logger):
        """Test applying all optimizations."""
        manager = OptimizationManager()
        
        # Mock optimizers
        manager.batch_processor.optimize = Mock()
        manager.cache_manager.optimize = Mock()
        manager.async_manager.optimize = Mock()
        manager.pool_manager.optimize = Mock()
        
        mock_pipeline = Mock()
        manager.apply_optimizations(mock_pipeline)
        
        # All optimizers should be called
        manager.batch_processor.optimize.assert_called_once_with(mock_pipeline)
        manager.cache_manager.optimize.assert_called_once_with(mock_pipeline)
        manager.async_manager.optimize.assert_called_once_with(mock_pipeline)
        manager.pool_manager.optimize.assert_called_once_with(mock_pipeline)
        
        # Should log start and end
        assert mock_logger.info.call_count == 2


class TestBatchOptimizer:
    """Test BatchOptimizer class."""
    
    @patch('src.utils.performance_profiling.logger')
    def test_batch_optimizer(self, mock_logger):
        """Test batch optimizer."""
        optimizer = BatchOptimizer()
        mock_pipeline = Mock()
        
        optimizer.optimize(mock_pipeline)
        
        mock_logger.info.assert_called_once_with("Batch processing optimization applied")


class TestCacheOptimizer:
    """Test CacheOptimizer class."""
    
    @patch('src.utils.performance_profiling.logger')
    def test_cache_optimizer(self, mock_logger):
        """Test cache optimizer."""
        optimizer = CacheOptimizer()
        mock_pipeline = Mock()
        
        optimizer.optimize(mock_pipeline)
        
        mock_logger.info.assert_called_once_with("Caching optimization applied")


class TestAsyncOptimizer:
    """Test AsyncOptimizer class."""
    
    @patch('src.utils.performance_profiling.logger')
    def test_async_optimizer(self, mock_logger):
        """Test async optimizer."""
        optimizer = AsyncOptimizer()
        mock_pipeline = Mock()
        
        optimizer.optimize(mock_pipeline)
        
        mock_logger.info.assert_called_once_with("Async optimization applied")


class TestConnectionPoolOptimizer:
    """Test ConnectionPoolOptimizer class."""
    
    @patch('src.utils.performance_profiling.logger')
    def test_connection_pool_optimizer(self, mock_logger):
        """Test connection pool optimizer."""
        optimizer = ConnectionPoolOptimizer()
        mock_pipeline = Mock()
        
        optimizer.optimize(mock_pipeline)
        
        mock_logger.info.assert_called_once_with("Connection pooling optimization applied")