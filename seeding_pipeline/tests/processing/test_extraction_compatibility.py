"""
Tests for extraction system backward compatibility.

This module ensures that existing code using the legacy extraction system
continues to work during the migration period.
"""

import pytest
import warnings
from unittest.mock import Mock, patch

from src.processing.extraction import KnowledgeExtractor, ExtractionResult, create_extractor
from src.core.models import Entity, Insight, Quote


class TestBackwardCompatibility:
    """Test backward compatibility with legacy extraction system."""
    
    def test_knowledge_extractor_still_works(self):
        """Test that KnowledgeExtractor can still be instantiated and used."""
        mock_llm = Mock()
        
        # Should work without warnings
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm,
            use_large_context=True
        )
        
        assert extractor is not None
        assert extractor.llm_provider == mock_llm
        assert extractor.use_large_context is True
    
    def test_extract_all_method_works(self):
        """Test that extract_all method still functions."""
        mock_llm = Mock()
        extractor = KnowledgeExtractor(llm_provider=mock_llm)
        
        # Mock the individual extraction methods
        extractor.extract_entities = Mock(return_value=[
            Entity(id='1', name='Test Entity', type='PERSON')
        ])
        extractor.extract_insights = Mock(return_value=[
            Insight(id='1', content='Test insight', type='FACTUAL')
        ])
        extractor.extract_quotes = Mock(return_value=[
            Quote(id='1', text='Test quote', speaker='Speaker', type='INSIGHTFUL')
        ])
        extractor.extract_topics = Mock(return_value=[
            {'name': 'Test Topic', 'relevance': 0.8}
        ])
        
        # Call extract_all
        result = extractor.extract_all('Test text')
        
        # Verify result structure
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 1
        assert len(result.insights) == 1
        assert len(result.quotes) == 1
        assert len(result.topics) == 1
        assert 'extraction_timestamp' in result.metadata
    
    def test_create_extractor_shows_deprecation_warning(self):
        """Test that create_extractor shows deprecation warning."""
        mock_llm = Mock()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # This should trigger a deprecation warning
            strategy = create_extractor(mode='fixed', llm_provider=mock_llm)
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "create_extractor is deprecated" in str(w[0].message)
    
    @patch('src.processing.extraction.ExtractionFactory')
    def test_create_extractor_delegates_to_factory(self, mock_factory):
        """Test that create_extractor delegates to ExtractionFactory."""
        mock_llm = Mock()
        mock_strategy = Mock()
        mock_factory.create_strategy.return_value = mock_strategy
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = create_extractor(mode='fixed', llm_provider=mock_llm)
        
        # Verify delegation
        mock_factory.create_strategy.assert_called_once_with(
            'fixed',
            llm_provider=mock_llm
        )
        assert result == mock_strategy
    
    def test_imports_remain_compatible(self):
        """Test that all expected imports still work."""
        # These imports should not raise errors
        from src.processing.extraction import KnowledgeExtractor
        from src.processing.extraction import ExtractionResult
        from src.processing.extraction import create_extractor
        
        assert KnowledgeExtractor is not None
        assert ExtractionResult is not None
        assert create_extractor is not None
    
    def test_extraction_result_structure_unchanged(self):
        """Test that ExtractionResult structure remains unchanged."""
        entities = [Entity(id='1', name='Entity', type='PERSON')]
        insights = [Insight(id='1', content='Insight', type='FACTUAL')]
        quotes = [Quote(id='1', text='Quote', speaker='Speaker', type='INSIGHTFUL')]
        topics = [{'name': 'Topic'}]
        metadata = {'key': 'value'}
        
        result = ExtractionResult(
            entities=entities,
            insights=insights,
            quotes=quotes,
            topics=topics,
            metadata=metadata
        )
        
        # Verify all fields are accessible
        assert result.entities == entities
        assert result.insights == insights
        assert result.quotes == quotes
        assert result.topics == topics
        assert result.metadata == metadata
    
    def test_module_all_exports(self):
        """Test that __all__ exports expected items."""
        from src.processing import extraction
        
        assert hasattr(extraction, '__all__')
        assert 'KnowledgeExtractor' in extraction.__all__
        assert 'ExtractionResult' in extraction.__all__
        assert 'create_extractor' in extraction.__all__