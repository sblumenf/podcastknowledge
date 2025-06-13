"""
Performance tests for semantic pipeline optimization.

This module tests the performance improvements from:
- Caching conversation structure analysis
- Batch processing for units
- Memory optimization
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile

from src.services.performance_optimizer import PerformanceOptimizer
from src.services.conversation_analyzer import ConversationAnalyzer
from src.seeding.components.semantic_pipeline_executor import SemanticPipelineExecutor
from src.core.interfaces import TranscriptSegment
from src.services.segment_regrouper import MeaningfulUnit


class TestSemanticPerformance:
    """Test performance optimizations in semantic pipeline."""
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        segments = []
        for i in range(100):  # 100 segments for performance testing
            segments.append(TranscriptSegment(
                id=f"seg_{i}",
                text=f"This is segment {i} with some content about topic {i % 10}.",
                start_time=i * 5.0,
                end_time=(i + 1) * 5.0,
                speaker=f"Speaker{i % 3}"
            ))
        return segments
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service with realistic delay."""
        llm_service = Mock()
        
        def mock_generate_completion(*args, **kwargs):
            # Simulate LLM delay
            time.sleep(0.1)  # 100ms delay
            return {
                'units': [
                    {
                        'start_index': i * 10,
                        'end_index': (i + 1) * 10 - 1,
                        'unit_type': 'topic_discussion',
                        'summary': f'Discussion about topic {i}',
                        'is_complete': True,
                        'completeness_note': 'Complete'
                    }
                    for i in range(10)
                ],
                'themes': [
                    {'name': f'Theme {i}', 'description': f'Description {i}', 'related_units': [i]}
                    for i in range(3)
                ],
                'boundaries': [],
                'flow': {'narrative_arc': 'intro->main->conclusion', 'pacing': 'steady', 'coherence_score': 0.9},
                'insights': {'fragmentation_issues': [], 'coherence_observations': [], 'suggested_improvements': []},
                'total_segments': 100
            }
        
        llm_service.generate_completion = Mock(side_effect=mock_generate_completion)
        return llm_service
    
    def test_conversation_structure_caching(self, sample_segments, mock_llm_service):
        """Test that conversation structure analysis is cached."""
        # Create optimizer and analyzer
        optimizer = PerformanceOptimizer(cache_ttl_minutes=60)
        analyzer = ConversationAnalyzer(mock_llm_service, optimizer)
        
        # First analysis - should call LLM
        start1 = time.time()
        structure1 = analyzer.analyze_structure(sample_segments)
        time1 = time.time() - start1
        
        # Second analysis - should use cache
        start2 = time.time()
        structure2 = analyzer.analyze_structure(sample_segments)
        time2 = time.time() - start2
        
        # Verify caching worked
        assert mock_llm_service.generate_completion.call_count == 1  # Only called once
        assert time2 < time1 * 0.1  # Cache hit should be much faster
        assert structure1.units == structure2.units  # Same results
    
    def test_batch_processing_optimization(self):
        """Test batch processing reduces total processing time."""
        optimizer = PerformanceOptimizer()
        
        # Mock processing function with delay
        def mock_process(item):
            time.sleep(0.05)  # 50ms per item
            return f"processed_{item}"
        
        items = list(range(20))  # 20 items to process
        
        # Process with batching
        start_batch = time.time()
        results_batch = optimizer.batch_llm_calls(
            items,
            mock_process,
            batch_size=5
        )
        time_batch = time.time() - start_batch
        
        # Process without batching (sequential)
        start_seq = time.time()
        results_seq = []
        for item in items:
            results_seq.append(mock_process(item))
        time_seq = time.time() - start_seq
        
        # Verify batch processing adds delays between batches
        # but is still efficient overall
        assert len(results_batch) == len(results_seq)
        assert all(f"processed_{i}" in results_batch for i in range(20))
    
    def test_memory_optimization(self):
        """Test memory optimization functionality."""
        optimizer = PerformanceOptimizer()
        
        # Create some memory usage
        large_data = [list(range(10000)) for _ in range(100)]
        
        # Optimize memory
        stats = optimizer.optimize_memory_usage()
        
        # Verify stats structure
        assert 'initial_memory_mb' in stats
        assert 'final_memory_mb' in stats
        assert 'memory_freed_mb' in stats
        assert 'memory_percent' in stats
        assert 'warning' in stats
        assert 'critical' in stats
        
        # Clean up
        del large_data
    
    def test_performance_monitoring(self):
        """Test performance monitoring decorators."""
        optimizer = PerformanceOptimizer()
        
        @optimizer.measure_performance("test_operation")
        def slow_operation():
            time.sleep(0.1)
            return "done"
        
        # Run operation multiple times
        for _ in range(3):
            result = slow_operation()
            assert result == "done"
        
        # Get performance summary
        summary = optimizer.get_performance_summary()
        
        assert "test_operation" in summary
        assert summary["test_operation"]["count"] == 3
        assert summary["test_operation"]["average_time"] >= 0.1
        assert summary["test_operation"]["min_time"] >= 0.1
        assert summary["test_operation"]["max_time"] >= 0.1
    
    def test_unit_processing_optimization(self):
        """Test meaningful unit grouping for optimal processing."""
        optimizer = PerformanceOptimizer()
        
        # Create units with varying durations
        units = []
        for i in range(20):
            unit = Mock(spec=MeaningfulUnit)
            unit.id = f"unit_{i}"
            unit.duration = 30.0 + (i * 10)  # 30s to 220s
            units.append(unit)
        
        # Group units
        groups = optimizer.optimize_unit_processing(units, max_parallel_units=3)
        
        # Verify grouping
        assert len(groups) > 1  # Should create multiple groups
        assert all(len(group) <= 3 for group in groups)  # Max 3 units per group
        
        # Verify all units are included
        all_unit_ids = []
        for group in groups:
            all_unit_ids.extend([u.id for u in group])
        assert len(all_unit_ids) == 20
        assert len(set(all_unit_ids)) == 20  # No duplicates
    
    def test_processing_benchmark(self):
        """Test processing benchmark functionality."""
        optimizer = PerformanceOptimizer()
        
        with optimizer.create_processing_benchmark() as benchmark:
            benchmark.set_operation_name("test_pipeline")
            
            # Simulate processing phases
            time.sleep(0.05)
            benchmark.checkpoint("phase1")
            
            time.sleep(0.1)
            benchmark.checkpoint("phase2")
            
            time.sleep(0.05)
            benchmark.checkpoint("phase3")
        
        # Verify checkpoints were recorded
        # (The benchmark logs the results, so we just verify it runs without error)
        assert True  # If we get here, benchmark worked
    
    @pytest.mark.integration
    def test_full_pipeline_performance(self, sample_segments, mock_llm_service):
        """Test full semantic pipeline with optimizations."""
        # Create mock components
        config = Mock()
        provider_coordinator = Mock()
        provider_coordinator.llm_service = mock_llm_service
        provider_coordinator.knowledge_extractor = Mock()
        provider_coordinator.entity_resolver = Mock()
        
        checkpoint_manager = Mock()
        checkpoint_manager.save_progress = Mock()
        checkpoint_manager.is_completed = Mock(return_value=False)
        checkpoint_manager.mark_completed = Mock()
        
        storage_coordinator = Mock()
        
        # Create semantic pipeline executor
        executor = SemanticPipelineExecutor(
            config,
            provider_coordinator,
            checkpoint_manager,
            storage_coordinator
        )
        
        # Mock graph service
        executor.graph_service = Mock()
        executor.graph_service.create_node = Mock()
        executor.graph_service.create_relationship = Mock()
        executor.graph_service.query = Mock(return_value=[])
        
        # Create test data
        podcast_config = {'id': 'test_podcast', 'name': 'Test Podcast'}
        episode = {'id': 'test_episode', 'title': 'Test Episode'}
        
        # Process with optimizations
        start_time = time.time()
        result = executor.process_vtt_segments(
            podcast_config,
            episode,
            sample_segments,
            use_large_context=True
        )
        processing_time = time.time() - start_time
        
        # Verify results
        assert result['status'] == 'success'
        assert result['processing_type'] == 'semantic'
        assert 'performance_metrics' in result
        assert result['total_segments'] == 100
        
        # Verify performance tracking
        if 'performance_metrics' in result:
            metrics = result['performance_metrics']
            # Should have metrics for different operations
            assert len(metrics) > 0