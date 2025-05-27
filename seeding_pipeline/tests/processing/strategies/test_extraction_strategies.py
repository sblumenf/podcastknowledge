"""
Tests for extraction strategies.

This module tests the three extraction strategies: FixedSchemaStrategy,
SchemalessStrategy, and DualModeStrategy.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.processing.strategies import ExtractedData
from src.processing.strategies.fixed_schema_strategy import FixedSchemaStrategy
from src.processing.strategies.schemaless_strategy import SchemalessStrategy
from src.processing.strategies.dual_mode_strategy import DualModeStrategy
from src.core.models import Segment, Entity, Insight, Quote, Podcast, Episode
from src.processing.extraction import ExtractionResult


class TestFixedSchemaStrategy:
    """Test cases for FixedSchemaStrategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        mock_llm = Mock()
        strategy = FixedSchemaStrategy(
            llm_provider=mock_llm,
            use_large_context=True,
            enable_cache=False
        )
        
        assert strategy.extractor is not None
        assert strategy.get_extraction_mode() == 'fixed'
    
    @patch('src.processing.strategies.fixed_schema_strategy.KnowledgeExtractor')
    def test_extract(self, mock_extractor_class):
        """Test extraction with fixed schema."""
        # Setup mocks
        mock_llm = Mock()
        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        
        # Create test data
        test_entities = [
            Entity(id='1', name='Test Entity', type='PERSON')
        ]
        test_quotes = [
            Quote(id='1', text='Test quote', speaker='Speaker 1', type='INSIGHTFUL')
        ]
        test_insights = [
            Insight(id='1', content='Test insight', type='FACTUAL')
        ]
        
        mock_extractor.extract_all.return_value = ExtractionResult(
            entities=test_entities,
            insights=test_insights,
            quotes=test_quotes,
            topics=[{'name': 'test topic'}],
            metadata={'test': 'metadata'}
        )
        
        # Create strategy and test segment
        strategy = FixedSchemaStrategy(llm_provider=mock_llm)
        segment = Segment(
            id='seg1',
            text='Test segment text',
            start_time=0.0,
            end_time=10.0,
            speaker='Speaker 1',
            episode_id='ep1',
            segment_index=0
        )
        
        # Execute extraction
        result = strategy.extract(segment)
        
        # Verify results
        assert isinstance(result, ExtractedData)
        assert len(result.entities) == 1
        assert result.entities[0].name == 'Test Entity'
        assert len(result.quotes) == 1
        assert result.quotes[0].text == 'Test quote'
        assert len(result.insights) == 1
        assert result.insights[0].content == 'Test insight'
        assert result.metadata['extraction_mode'] == 'fixed'
        assert result.relationships == []  # Fixed schema doesn't extract relationships
    
    def test_get_extraction_mode(self):
        """Test extraction mode identifier."""
        mock_llm = Mock()
        strategy = FixedSchemaStrategy(llm_provider=mock_llm)
        assert strategy.get_extraction_mode() == 'fixed'


class TestSchemalessStrategy:
    """Test cases for SchemalessStrategy."""
    
    def test_initialization_with_valid_provider(self):
        """Test initialization with valid graph provider."""
        mock_graph_provider = Mock()
        mock_graph_provider.process_segment_schemaless = Mock()
        
        strategy = SchemalessStrategy(
            graph_provider=mock_graph_provider,
            podcast_id='pod1',
            episode_id='ep1'
        )
        
        assert strategy.graph_provider is not None
        assert strategy.podcast_id == 'pod1'
        assert strategy.episode_id == 'ep1'
        assert strategy.get_extraction_mode() == 'schemaless'
    
    def test_initialization_with_invalid_provider(self):
        """Test initialization with provider that doesn't support schemaless."""
        mock_graph_provider = Mock()
        # Don't add process_segment_schemaless method
        
        with pytest.raises(ValueError, match="does not support schemaless"):
            SchemalessStrategy(
                graph_provider=mock_graph_provider,
                podcast_id='pod1',
                episode_id='ep1'
            )
    
    def test_extract(self):
        """Test schemaless extraction."""
        # Setup mock graph provider
        mock_graph_provider = Mock()
        mock_result = {
            'entities': [
                {'id': '1', 'name': 'Entity 1', 'type': 'PERSON', 'properties': {}},
                {'id': '2', 'name': 'Entity 2', 'type': 'CONCEPT', 'properties': {}}
            ],
            'relationships': [
                {'source': '1', 'target': '2', 'type': 'DISCUSSES'}
            ],
            'entities': 2,  # Count
            'relationships': 1,  # Count
            'discovered_types': ['PERSON', 'CONCEPT']
        }
        mock_graph_provider.process_segment_schemaless.return_value = mock_result
        
        # Create strategy and test segment
        strategy = SchemalessStrategy(
            graph_provider=mock_graph_provider,
            podcast_id='pod1',
            episode_id='ep1'
        )
        
        segment = Segment(
            id='seg1',
            text='Test segment text',
            start_time=0.0,
            end_time=10.0,
            speaker='Speaker 1'
        )
        
        # Execute extraction
        result = strategy.extract(segment)
        
        # Verify results
        assert isinstance(result, ExtractedData)
        assert len(result.entities) == 2
        assert result.entities[0].name == 'Entity 1'
        assert result.entities[1].name == 'Entity 2'
        assert len(result.relationships) == 1
        assert result.quotes == []  # Schemaless doesn't extract quotes
        assert result.insights == []  # Schemaless doesn't extract insights
        assert result.metadata['extraction_mode'] == 'schemaless'
        assert strategy.get_discovered_types() == ['PERSON', 'CONCEPT']
    
    def test_extract_with_error(self):
        """Test extraction error handling."""
        mock_graph_provider = Mock()
        mock_graph_provider.process_segment_schemaless.side_effect = Exception("Test error")
        
        strategy = SchemalessStrategy(
            graph_provider=mock_graph_provider,
            podcast_id='pod1',
            episode_id='ep1'
        )
        
        segment = Segment(
            id='seg1',
            text='Test segment text',
            start_time=0.0,
            end_time=10.0
        )
        
        # Should return empty result on error
        result = strategy.extract(segment)
        
        assert isinstance(result, ExtractedData)
        assert result.entities == []
        assert result.relationships == []
        assert 'error' in result.metadata
        assert result.metadata['error'] == 'Test error'


class TestDualModeStrategy:
    """Test cases for DualModeStrategy."""
    
    @patch('src.processing.strategies.dual_mode_strategy.FixedSchemaStrategy')
    @patch('src.processing.strategies.dual_mode_strategy.SchemalessStrategy')
    def test_initialization(self, mock_schemaless_class, mock_fixed_class):
        """Test dual mode initialization."""
        mock_llm = Mock()
        mock_graph_provider = Mock()
        
        strategy = DualModeStrategy(
            llm_provider=mock_llm,
            graph_provider=mock_graph_provider,
            podcast_id='pod1',
            episode_id='ep1'
        )
        
        # Verify both strategies were initialized
        mock_fixed_class.assert_called_once()
        mock_schemaless_class.assert_called_once()
        assert strategy.get_extraction_mode() == 'dual'
    
    def test_extract_combines_results(self):
        """Test that dual mode combines results from both strategies."""
        # Create mock strategies
        mock_fixed_strategy = Mock()
        mock_schemaless_strategy = Mock()
        
        # Setup fixed result
        fixed_entities = [
            Entity(id='1', name='Fixed Entity', type='PERSON')
        ]
        fixed_quotes = [
            Quote(id='1', text='Fixed quote', speaker='Speaker 1', type='INSIGHTFUL')
        ]
        fixed_insights = [
            Insight(id='1', content='Fixed insight', type='FACTUAL')
        ]
        
        mock_fixed_strategy.extract.return_value = ExtractedData(
            entities=fixed_entities,
            relationships=[],
            quotes=fixed_quotes,
            insights=fixed_insights,
            topics=[{'name': 'fixed topic'}],
            metadata={'mode': 'fixed'}
        )
        
        # Setup schemaless result
        schemaless_entities = [
            Entity(id='2', name='Schemaless Entity', type='CONCEPT'),
            Entity(id='3', name='fixed entity', type='PERSON')  # Duplicate (lowercase)
        ]
        schemaless_relationships = [
            {'source': '1', 'target': '2', 'type': 'RELATED'}
        ]
        
        mock_schemaless_strategy.extract.return_value = ExtractedData(
            entities=schemaless_entities,
            relationships=schemaless_relationships,
            quotes=[],
            insights=[],
            topics=[],
            metadata={'mode': 'schemaless'}
        )
        mock_schemaless_strategy.get_discovered_types.return_value = ['PERSON', 'CONCEPT']
        
        # Create strategy with mocked sub-strategies
        mock_llm = Mock()
        mock_graph_provider = Mock()
        strategy = DualModeStrategy(
            llm_provider=mock_llm,
            graph_provider=mock_graph_provider,
            podcast_id='pod1',
            episode_id='ep1'
        )
        strategy.fixed_strategy = mock_fixed_strategy
        strategy.schemaless_strategy = mock_schemaless_strategy
        
        # Test segment
        segment = Segment(
            id='seg1',
            text='Test segment',
            start_time=0.0,
            end_time=10.0
        )
        
        # Execute extraction
        result = strategy.extract(segment)
        
        # Verify combined results
        assert isinstance(result, ExtractedData)
        assert len(result.entities) == 2  # Fixed + unique schemaless
        assert result.entities[0].name == 'Fixed Entity'
        assert result.entities[1].name == 'Schemaless Entity'
        assert len(result.relationships) == 1  # From schemaless
        assert len(result.quotes) == 1  # From fixed
        assert len(result.insights) == 1  # From fixed
        assert result.metadata['extraction_mode'] == 'dual'
        assert 'entity_comparison' in result.metadata
        assert result.metadata['discovered_types'] == ['PERSON', 'CONCEPT']