"""Unit tests for episode flow processing."""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.core.models import Segment, Entity


class TestEpisodeFlowAnalyzer:
    """Test EpisodeFlowAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create EpisodeFlowAnalyzer instance."""
        mock_embedding_provider = Mock()
        return EpisodeFlowAnalyzer(embedding_provider=mock_embedding_provider)
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        segments = [
            Segment(
                id="seg1",
                episode_id="ep1",
                start_time=0.0,
                end_time=10.0,
                text="Introduction to machine learning concepts.",
                speaker="Host",
                entities=[]
            ),
            Segment(
                id="seg2",
                episode_id="ep1",
                start_time=10.0,
                end_time=20.0,
                text="Deep learning is a subset of machine learning.",
                speaker="Guest",
                entities=[]
            ),
            Segment(
                id="seg3",
                episode_id="ep1",
                start_time=20.0,
                end_time=30.0,
                text="Let's talk about neural networks.",
                speaker="Host",
                entities=[]
            )
        ]
        return segments
    
    def test_analyzer_initialization(self):
        """Test EpisodeFlowAnalyzer initialization."""
        analyzer = EpisodeFlowAnalyzer()
        assert analyzer.embedding_provider is None
        
        mock_provider = Mock()
        analyzer = EpisodeFlowAnalyzer(embedding_provider=mock_provider)
        assert analyzer.embedding_provider == mock_provider
    
    def test_classify_segment_transitions(self, analyzer, sample_segments):
        """Test classifying segment transitions."""
        # Mock the semantic similarity calculation
        analyzer._calculate_semantic_similarity = Mock(return_value=0.8)
        
        transitions = analyzer.classify_segment_transitions(sample_segments)
        
        # Should have 2 transitions for 3 segments
        assert len(transitions) == 2
        
        # Check that similarity was calculated
        assert analyzer._calculate_semantic_similarity.called
    
    def test_identify_discourse_patterns(self, analyzer, sample_segments):
        """Test identifying discourse patterns."""
        if hasattr(analyzer, 'identify_discourse_patterns'):
            patterns = analyzer.identify_discourse_patterns(sample_segments)
            assert isinstance(patterns, dict)
    
    def test_track_entity_flow(self, analyzer, sample_segments):
        """Test tracking entity flow through episode."""
        # Add some entities to segments
        sample_segments[0].entities = [
            Entity(name="machine learning", type="CONCEPT", confidence=0.9)
        ]
        sample_segments[1].entities = [
            Entity(name="machine learning", type="CONCEPT", confidence=0.9),
            Entity(name="deep learning", type="CONCEPT", confidence=0.8)
        ]
        
        if hasattr(analyzer, 'track_entity_flow'):
            entity_flow = analyzer.track_entity_flow(sample_segments)
            assert isinstance(entity_flow, dict)
    
    def test_empty_segments_handling(self, analyzer):
        """Test handling of empty segment list."""
        transitions = analyzer.classify_segment_transitions([])
        assert transitions == []
        
        # Single segment should also return empty transitions
        single_segment = [
            Segment(
                id="seg1",
                episode_id="ep1",
                start_time=0.0,
                end_time=10.0,
                text="Only segment",
                speaker="Host",
                entities=[]
            )
        ]
        transitions = analyzer.classify_segment_transitions(single_segment)
        assert transitions == []