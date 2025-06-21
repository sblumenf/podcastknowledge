"""
Performance test suite for UnifiedKnowledgePipeline.

This module tests performance optimizations including:
- Combined extraction method usage
- Parallel processing implementation
- Sentiment analysis error handling
- Overall performance targets
"""

import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import pytest

from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.services.segment_regrouper import MeaningfulUnit
from src.core.interfaces import TranscriptSegment
from src.extraction.extraction import ExtractionResult
from src.extraction.sentiment_analyzer import SentimentResult


class TestCombinedExtractionUsage:
    """Test that combined extraction is being used instead of separate methods."""
    
    @pytest.mark.asyncio
    async def test_combined_extraction_is_used(self):
        """Verify that extract_knowledge_combined is called, not separate methods."""
        # Create mock services
        mock_graph_storage = Mock()
        mock_llm_service = Mock()
        
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=mock_graph_storage,
            llm_service=mock_llm_service
        )
        
        # Mock the knowledge extractor
        mock_extractor = Mock()
        mock_extractor.extract_knowledge_combined = Mock(return_value=ExtractionResult(
            entities=[], quotes=[], relationships=[], insights=[]
        ))
        mock_extractor.extract_entities = Mock()
        mock_extractor.extract_quotes = Mock()
        mock_extractor.extract_relationships = Mock()
        mock_extractor.extract_insights = Mock()
        
        pipeline.knowledge_extractor = mock_extractor
        
        # Create test meaningful unit
        test_unit = MeaningfulUnit(
            id="test_unit_1",
            segments=[],
            unit_type="discussion",
            summary="Test unit",
            themes=["test"],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        # Process the unit
        result = pipeline._process_single_unit(test_unit, 0)
        
        # Verify combined extraction was called
        assert mock_extractor.extract_knowledge_combined.called
        assert mock_extractor.extract_knowledge_combined.call_count == 1
        
        # Verify separate methods were NOT called
        assert not mock_extractor.extract_entities.called
        assert not mock_extractor.extract_quotes.called
        assert not mock_extractor.extract_relationships.called
        assert not mock_extractor.extract_insights.called
    
    @pytest.mark.asyncio
    async def test_fallback_to_separate_methods(self):
        """Test fallback to separate methods if combined is not available."""
        # Create mock services
        mock_graph_storage = Mock()
        mock_llm_service = Mock()
        
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=mock_graph_storage,
            llm_service=mock_llm_service
        )
        
        # Mock extractor without combined method
        mock_extractor = Mock()
        # Remove the combined method
        delattr(mock_extractor, 'extract_knowledge_combined')
        mock_extractor.extract_knowledge = Mock(return_value=ExtractionResult(
            entities=[], quotes=[], relationships=[], insights=[]
        ))
        
        pipeline.knowledge_extractor = mock_extractor
        
        # Create test unit
        test_unit = MeaningfulUnit(
            id="test_unit_1",
            segments=[],
            unit_type="discussion",
            summary="Test unit",
            themes=["test"],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        # Process the unit
        result = pipeline._process_single_unit(test_unit, 0)
        
        # Verify fallback method was called
        assert mock_extractor.extract_knowledge.called


class TestParallelProcessing:
    """Test that parallel processing is working correctly."""
    
    @pytest.mark.asyncio
    async def test_parallel_execution_engages(self):
        """Verify that multiple threads are used for unit processing."""
        # Track thread IDs
        thread_ids = set()
        processing_times = []
        
        def mock_process_unit(unit, idx):
            """Mock unit processor that tracks thread ID."""
            import threading
            thread_ids.add(threading.current_thread().ident)
            # Simulate some work
            time.sleep(0.1)
            processing_times.append(time.time())
            return {
                'success': True,
                'unit_index': idx,
                'extraction_result': ExtractionResult(entities=[], quotes=[], relationships=[], insights=[]),
                'sentiment_result': None,
                'error': None,
                'processing_time': 0.1
            }
        
        # Create mock services
        mock_graph_storage = Mock()
        mock_llm_service = Mock()
        
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=mock_graph_storage,
            llm_service=mock_llm_service
        )
        
        # Replace _process_single_unit with our mock
        pipeline._process_single_unit = mock_process_unit
        
        # Create test units
        test_units = [
            MeaningfulUnit(
                id=f"test_unit_{i}",
                segments=[],
                unit_type="discussion",
                summary=f"Test unit {i}",
                themes=["test"],
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                primary_speaker="Speaker1",
                is_complete=True
            )
            for i in range(5)
        ]
        
        # Process units
        start_time = time.time()
        results = await pipeline._extract_knowledge(test_units)
        end_time = time.time()
        
        # Verify multiple threads were used
        assert len(thread_ids) > 1, f"Expected multiple threads, but got {len(thread_ids)}"
        
        # Verify parallel execution (should be faster than sequential)
        total_time = end_time - start_time
        sequential_time = 0.1 * len(test_units)
        assert total_time < sequential_time * 0.8, \
            f"Parallel execution too slow: {total_time:.2f}s vs sequential {sequential_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_thread_pool_size_configuration(self):
        """Verify thread pool size matches MAX_CONCURRENT_UNITS configuration."""
        from src.core.pipeline_config import PipelineConfig
        
        # Get configured value
        expected_pool_size = PipelineConfig.MAX_CONCURRENT_UNITS
        
        # Track active threads
        active_threads = set()
        max_concurrent = 0
        
        def mock_process_unit_slow(unit, idx):
            """Mock processor that runs slowly to test concurrency."""
            import threading
            thread_id = threading.current_thread().ident
            active_threads.add(thread_id)
            
            # Update max concurrent count
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, len(active_threads))
            
            # Simulate slow processing
            time.sleep(0.2)
            
            active_threads.remove(thread_id)
            return {
                'success': True,
                'unit_index': idx,
                'extraction_result': ExtractionResult(entities=[], quotes=[], relationships=[], insights=[]),
                'sentiment_result': None,
                'error': None,
                'processing_time': 0.2
            }
        
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=Mock(),
            llm_service=Mock()
        )
        
        pipeline._process_single_unit = mock_process_unit_slow
        
        # Create enough units to test concurrency limit
        test_units = [
            MeaningfulUnit(
                id=f"test_unit_{i}",
                segments=[],
                unit_type="discussion",
                summary=f"Test unit {i}",
                themes=["test"],
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                primary_speaker="Speaker1",
                is_complete=True
            )
            for i in range(10)  # More than MAX_CONCURRENT_UNITS
        ]
        
        # Process units
        await pipeline._extract_knowledge(test_units)
        
        # Verify max concurrent threads matches configuration
        assert max_concurrent <= expected_pool_size, \
            f"Max concurrent threads {max_concurrent} exceeded configured limit {expected_pool_size}"


class TestSentimentAnalysisRobustness:
    """Test sentiment analysis error handling."""
    
    def test_sentiment_handles_none_response(self):
        """Test sentiment analyzer handles None responses gracefully."""
        from src.extraction.sentiment_analyzer import SentimentAnalyzer
        
        # Create analyzer with mock LLM that returns None
        mock_llm = Mock()
        mock_llm.complete_with_options = Mock(return_value=None)
        
        analyzer = SentimentAnalyzer(llm_service=mock_llm)
        
        # Create test unit
        test_unit = MeaningfulUnit(
            id="test_unit",
            segments=[TranscriptSegment(
                id="seg1",
                start_time=0.0,
                end_time=10.0,
                text="This is a test segment",
                speaker="Speaker1"
            )],
            unit_type="discussion",
            summary="Test unit",
            themes=["test"],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        # Analyze sentiment - should not crash
        result = analyzer.analyze_meaningful_unit(test_unit, {})
        
        # Should return a result (likely from fallback)
        assert result is not None
        assert isinstance(result, (dict, SentimentResult))
    
    def test_sentiment_handles_malformed_json(self):
        """Test sentiment analyzer handles malformed JSON responses."""
        from src.extraction.sentiment_analyzer import SentimentAnalyzer
        
        # Create analyzer with mock LLM that returns malformed JSON
        mock_llm = Mock()
        mock_llm.complete_with_options = Mock(return_value={
            'content': 'This is not valid JSON { broken'
        })
        
        analyzer = SentimentAnalyzer(llm_service=mock_llm)
        
        # Create test unit
        test_unit = MeaningfulUnit(
            id="test_unit",
            segments=[TranscriptSegment(
                id="seg1",
                start_time=0.0,
                end_time=10.0,
                text="This is a test segment",
                speaker="Speaker1"
            )],
            unit_type="discussion",
            summary="Test unit",
            themes=["test"],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        # Analyze sentiment - should not crash
        result = analyzer.analyze_meaningful_unit(test_unit, {})
        
        # Should return a result (likely from fallback)
        assert result is not None
    
    def test_sentiment_handles_text_scores(self):
        """Test sentiment analyzer handles text descriptions instead of numeric scores."""
        from src.extraction.sentiment_analyzer import SentimentAnalyzer
        
        # Create analyzer with mock LLM that returns text scores
        mock_llm = Mock()
        mock_llm.complete_with_options = Mock(return_value={
            'content': '{"overall_sentiment": {"score": "very positive", "confidence": "high"}}'
        })
        
        analyzer = SentimentAnalyzer(llm_service=mock_llm)
        
        # Create test unit
        test_unit = MeaningfulUnit(
            id="test_unit",
            segments=[TranscriptSegment(
                id="seg1",
                start_time=0.0,
                end_time=10.0,
                text="This is a test segment",
                speaker="Speaker1"
            )],
            unit_type="discussion",
            summary="Test unit",
            themes=["test"],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        # Analyze sentiment - should handle text scores
        result = analyzer.analyze_meaningful_unit(test_unit, {})
        
        # Should return a valid result
        assert result is not None


class TestPerformanceRegression:
    """Test to prevent performance regressions."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_performance_does_not_regress(self):
        """Test that processing time stays within acceptable bounds."""
        # Create mock services with controlled delays
        mock_graph_storage = Mock()
        mock_llm_service = Mock()
        
        # Mock LLM responses with consistent timing
        def mock_llm_response(*args, **kwargs):
            time.sleep(0.05)  # Simulate 50ms LLM response time
            return {
                'content': '{"entities": [], "quotes": [], "relationships": [], "insights": []}'
            }
        
        mock_llm_service.complete_with_options = Mock(side_effect=mock_llm_response)
        
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=mock_graph_storage,
            llm_service=mock_llm_service
        )
        
        # Mock the knowledge extractor to use our LLM
        pipeline.knowledge_extractor.llm_service = mock_llm_service
        
        # Create test units
        num_units = 10
        test_units = [
            MeaningfulUnit(
                id=f"test_unit_{i}",
                segments=[TranscriptSegment(
                    id=f"seg_{i}",
                    start_time=i * 10.0,
                    end_time=(i + 1) * 10.0,
                    text=f"Test segment {i}",
                    speaker="Speaker1"
                )],
                unit_type="discussion",
                summary=f"Test unit {i}",
                themes=["test"],
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                primary_speaker="Speaker1",
                is_complete=True
            )
            for i in range(num_units)
        ]
        
        # Time the extraction
        start_time = time.time()
        results = await pipeline._extract_knowledge(test_units)
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # Calculate expected times
        # With combined extraction: 1 LLM call per unit @ 50ms each
        # With parallel processing (5 concurrent): ~100ms per batch
        expected_sequential_time = num_units * 0.05
        expected_parallel_time = (num_units / 5) * 0.05
        
        # Allow some overhead (100%)
        max_acceptable_time = expected_parallel_time * 2
        
        assert total_time < max_acceptable_time, \
            f"Processing took {total_time:.2f}s, expected < {max_acceptable_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_combined_extraction_not_accidentally_disabled(self):
        """Regression test to ensure combined extraction stays enabled."""
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=Mock(),
            llm_service=Mock()
        )
        
        # Verify knowledge extractor has combined method
        assert hasattr(pipeline.knowledge_extractor, 'extract_knowledge_combined'), \
            "Combined extraction method missing - performance regression!"
    
    @pytest.mark.asyncio
    async def test_parallel_processing_not_accidentally_disabled(self):
        """Regression test to ensure parallel processing stays enabled."""
        # Create pipeline
        pipeline = UnifiedKnowledgePipeline(
            graph_storage=Mock(),
            llm_service=Mock()
        )
        
        # Mock _process_single_unit to track calls
        call_times = []
        
        def mock_process(unit, idx):
            call_times.append(time.time())
            time.sleep(0.1)
            return {'success': True, 'unit_index': idx}
        
        pipeline._process_single_unit = mock_process
        
        # Process multiple units
        test_units = [
            MeaningfulUnit(
                id=f"unit_{i}",
                segments=[],
                unit_type="test",
                summary="test",
                themes=[],
                start_time=0,
                end_time=10,
                primary_speaker="test",
                is_complete=True
            )
            for i in range(3)
        ]
        
        start = time.time()
        await pipeline._extract_knowledge(test_units)
        end = time.time()
        
        # If processed sequentially, would take 0.3s
        # If parallel, should take ~0.1s (plus overhead)
        assert (end - start) < 0.25, \
            "Processing appears to be sequential - parallel processing may be disabled!"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_performance_with_mocks():
    """Integration test with full pipeline and mock services."""
    # Create comprehensive mocks
    mock_graph_storage = Mock()
    mock_graph_storage.store_meaningful_unit = Mock()
    mock_graph_storage.store_entity = Mock()
    mock_graph_storage.create_relationship = Mock()
    
    mock_llm_service = Mock()
    # Mock fast LLM responses
    mock_llm_service.complete_with_options = Mock(return_value={
        'content': '''{
            "entities": [{"name": "Test Entity", "type": "CONCEPT"}],
            "quotes": [{"text": "Test quote", "speaker": "Speaker1"}],
            "relationships": [{"source": "A", "target": "B", "type": "RELATES_TO"}],
            "insights": [{"insight": "Test insight", "evidence": ["test"]}]
        }'''
    })
    
    # Create pipeline
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=mock_graph_storage,
        llm_service=mock_llm_service
    )
    
    # Create episode metadata
    episode_metadata = {
        'episode_id': 'perf_test_001',
        'title': 'Performance Test Episode',
        'description': 'Testing pipeline performance',
        'published_date': '2024-01-01'
    }
    
    # Create test VTT content
    vtt_content = '''WEBVTT

00:00:00.000 --> 00:00:10.000
<v Speaker1>This is the first segment of our performance test.

00:00:10.000 --> 00:00:20.000
<v Speaker2>And this is the second segment with different speaker.

00:00:20.000 --> 00:00:30.000
<v Speaker1>We continue with more content for testing.

00:00:30.000 --> 00:00:40.000
<v Speaker2>Performance should be optimized with combined extraction.

00:00:40.000 --> 00:00:50.000
<v Speaker1>And parallel processing should speed things up.
'''
    
    # Write test VTT file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(vtt_content)
        vtt_path = f.name
    
    try:
        # Process the file
        start_time = time.time()
        result = await pipeline.process_vtt_file(Path(vtt_path), episode_metadata)
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # Verify processing completed
        assert result['status'] == 'completed'
        
        # Check performance (should be fast with mocks)
        assert total_time < 5.0, f"Pipeline took {total_time:.2f}s, expected < 5s"
        
        # Verify phases completed
        expected_phases = [
            'VTT_PARSING',
            'SPEAKER_IDENTIFICATION',
            'CONVERSATION_ANALYSIS',
            'MEANINGFUL_UNIT_CREATION',
            'KNOWLEDGE_EXTRACTION',
            'KNOWLEDGE_STORAGE'
        ]
        for phase in expected_phases:
            assert phase in result['phases_completed']
        
    finally:
        # Cleanup
        Path(vtt_path).unlink()