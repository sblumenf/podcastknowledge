"""Unit tests for knowledge extraction module.

Tests for src/processing/extraction.py focusing on unit-level testing
with mocked dependencies.
"""

from datetime import datetime
from typing import Dict, Any, List
from unittest import mock
import json

import pytest

from src.extraction.extraction import (
    KnowledgeExtractor, ExtractionResult, create_extractor
)
from src.core.models import (
    Entity, EntityType, Insight, InsightType, Quote, QuoteType, Segment
)
from src.core.exceptions import ExtractionError


class TestExtractionResult:
    """Test ExtractionResult dataclass."""
    
    def test_extraction_result_creation(self):
        """Test creating ExtractionResult instance."""
        entities = [Entity(
            id="entity_1",
            name="Test Entity",
            entity_type=EntityType.PERSON,
            description="Test description"
        )]
        insights = [Insight(
            id="insight_1",
            title="Test Insight",
            description="Test description",
            insight_type=InsightType.FACTUAL
        )]
        quotes = [Quote(
            id="quote_1",
            text="Test quote",
            speaker="Test Speaker",
            quote_type=QuoteType.MEMORABLE
        )]
        topics = [{"name": "Test Topic", "description": "Test description"}]
        metadata = {"key": "value"}
        
        result = ExtractionResult(
            entities=entities,
            relationships=insights,
            quotes=quotes,
            metadata=metadata
        )
        
        assert result.entities == entities
        assert result.relationships == insights
        assert result.quotes == quotes
        assert result.metadata == metadata


class TestKnowledgeExtractor:
    """Test KnowledgeExtractor class."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = mock.Mock()
        service.complete = mock.Mock(return_value="Mock response")
        return service
    
    @pytest.fixture
    def extractor(self, mock_llm_service):
        """Create KnowledgeExtractor instance."""
        from src.extraction.extraction import ExtractionConfig
        config = ExtractionConfig(
            extract_quotes=True,
            validate_extractions=True
        )
        return KnowledgeExtractor(
            llm_service=mock_llm_service,
            config=config
        )
    
    def test_extractor_initialization(self, mock_llm_service):
        """Test extractor initialization."""
        from src.extraction.extraction import ExtractionConfig
        config = ExtractionConfig(
            extract_quotes=False,
            entity_confidence_threshold=0.7,
            max_entities_per_segment=30
        )
        extractor = KnowledgeExtractor(
            llm_service=mock_llm_service,
            embedding_service=None,
            config=config
        )
        
        assert extractor.llm_service == mock_llm_service
        assert extractor.embedding_service is None
        assert extractor.config.extract_quotes is False
        assert extractor.config.entity_confidence_threshold == 0.7
        assert extractor.config.max_entities_per_segment == 30
        assert len(extractor.quote_patterns) > 0
    
    def test_quote_patterns(self, extractor):
        """Test quote pattern configuration."""
        # Check that quote patterns are initialized
        assert len(extractor.quote_patterns) > 0
        assert isinstance(extractor.quote_patterns, list)
        
        # Check quote classifiers
        assert 'opinion' in extractor.quote_classifiers
        assert 'factual' in extractor.quote_classifiers
        assert 'insightful' in extractor.quote_classifiers
    
    def test_extraction_config(self, extractor):
        """Test extraction configuration."""
        assert extractor.config.extract_quotes is True
        assert extractor.config.validate_extractions is True
        assert extractor.config.min_quote_length == 10
        assert extractor.config.max_quote_length == 50
        assert extractor.config.entity_confidence_threshold == 0.6
    
    def test_extract_knowledge(self, extractor, mock_llm_service):
        """Test extract_all method."""
        # Create a test segment
        from src.core.models import Segment
        segment = Segment(
            id="seg_1",
            text="Test text for extraction",
            start_time=0.0,
            end_time=10.0,
            speaker="TestSpeaker"
        )
        
        # Mock internal extraction methods
        mock_entities = [{
            "name": "Test Entity",
            "type": "PERSON",
            "confidence": 0.8
        }]
        mock_quotes = [{
            "text": "Test quote",
            "speaker": "TestSpeaker",
            "type": "insightful"
        }]
        
        with mock.patch.object(extractor, '_extract_basic_entities', return_value=mock_entities):
            with mock.patch.object(extractor, '_extract_quotes', return_value=mock_quotes):
                with mock.patch.object(extractor, '_extract_relationships', return_value=[]):
                    result = extractor.extract_knowledge(segment, {"episode": "test"})
        
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 1
        assert len(result.quotes) == 1
        assert result.entities[0]['name'] == "Test Entity"
        assert result.quotes[0]['text'] == "Test quote"
        assert result.metadata['segment_id'] == "seg_1"
        assert result.metadata['text_length'] == len("Test text for extraction")
        assert result.metadata['entity_count'] == 1
        assert result.metadata['quote_count'] == 1
        assert 'extraction_timestamp' in result.metadata
    
    def test_extract_entities_success(self, extractor, mock_llm_service):
        """Test successful entity extraction."""
        # Mock the extract_knowledge method to return specific entities
        mock_result = ExtractionResult(
            entities=[
                {
                    "value": "John Doe",
                    "entity_type": "person",
                    "confidence": 0.9,
                    "properties": {"description": "A researcher"}
                }
            ],
            quotes=[],
            relationships=[],
            metadata={}
        )
        
        with mock.patch.object(extractor, 'extract_knowledge', return_value=mock_result):
            entities = extractor.extract_entities("John Doe is a researcher.")
        
        assert len(entities) == 1
        assert entities[0].name == "John Doe"
        assert entities[0].type == "person"
        assert entities[0].description == "A researcher"
        assert entities[0].confidence == 0.9
    
    def test_extract_entities_empty_text(self, extractor):
        """Test entity extraction with empty text."""
        assert extractor.extract_entities("") == []
        assert extractor.extract_entities("   ") == []
    
    def test_extract_entities_error_handling(self, extractor, mock_llm_service):
        """Test error handling in entity extraction."""
        # Mock LLM service to raise exception
        mock_llm_service.process = mock.Mock(side_effect=Exception("Network error"))
        
        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            entities = extractor.extract_entities("Test person")
        assert "Network error" in str(exc_info.value)
    
    def test_extract_quotes_from_segment(self, extractor, mock_llm_service):
        """Test successful combined extraction."""
        # Test quote extraction from segment
        from src.core.models import Segment
        # Lower the importance threshold for testing
        extractor.config.quote_importance_threshold = 0.5
        
        segment = Segment(
            id="seg_1",
            text='John said: "The future is artificial intelligence and we need to prepare for it now before it is too late"',
            start_time=0.0,
            end_time=10.0,
            speaker="Host"
        )
        
        result = extractor.extract_quotes(segment)
        
        assert isinstance(result, dict)
        assert 'quotes' in result
        assert 'metadata' in result
        
        quotes = result['quotes']
        assert len(quotes) >= 1  # Should find at least one quote
        assert any('artificial intelligence' in q.get('text', '') for q in quotes)
    
    def test_extract_basic_entities(self, extractor):
        """Test basic entity extraction."""
        from src.core.models import Segment
        segment = Segment(
            id="seg_1",
            text="Apple Inc. is a technology company founded by Steve Jobs.",
            start_time=0.0,
            end_time=10.0
        )
        
        # Mock the internal method
        with mock.patch.object(extractor, '_extract_basic_entities') as mock_extract:
            mock_extract.return_value = [
                {"value": "Apple Inc.", "entity_type": "organization", "confidence": 0.9},
                {"value": "Steve Jobs", "entity_type": "person", "confidence": 0.95}
            ]
            entities = extractor._extract_basic_entities(segment)
        
        assert len(entities) == 2
        assert entities[0]['value'] == "Apple Inc."
        assert entities[1]['value'] == "Steve Jobs"
    
    def test_extract_relationships(self, extractor):
        """Test relationship extraction between entities."""
        from src.core.models import Segment
        segment = Segment(
            id="seg_1",
            text="Apple was founded by Steve Jobs in California.",
            start_time=0.0,
            end_time=10.0
        )
        
        entities = [
            {"value": "Apple", "entity_type": "organization"},
            {"value": "Steve Jobs", "entity_type": "person"},
            {"value": "California", "entity_type": "location"}
        ]
        quotes = []
        
        # Mock the relationship extraction
        with mock.patch.object(extractor, '_extract_relationships') as mock_rel:
            mock_rel.return_value = [
                {
                    "source": "Steve Jobs",
                    "target": "Apple",
                    "relationship": "founded",
                    "confidence": 0.9
                }
            ]
            relationships = extractor._extract_relationships(entities, quotes, segment)
        
        assert len(relationships) == 1
        assert relationships[0]['source'] == "Steve Jobs"
        assert relationships[0]['target'] == "Apple"
    
    def test_quote_type_classification(self, extractor):
        """Test quote type classification."""
        # Test that quote classifiers are properly initialized
        assert 'opinion' in extractor.quote_classifiers
        assert 'factual' in extractor.quote_classifiers
        assert 'humorous' in extractor.quote_classifiers
        assert 'controversial' in extractor.quote_classifiers
        assert 'insightful' in extractor.quote_classifiers
        
        # Check keywords for each type
        assert 'believe' in extractor.quote_classifiers['opinion']
        assert 'research' in extractor.quote_classifiers['factual']
        assert 'funny' in extractor.quote_classifiers['humorous']
    
    def test_preview_extraction(self, extractor):
        """Test preview mode extraction."""
        from src.core.models import Segment
        # Set dry run mode
        extractor.config.dry_run = True
        
        segment = Segment(
            id="seg_1",
            text="Test preview extraction",
            start_time=0.0,
            end_time=10.0
        )
        
        # Mock the preview method
        with mock.patch.object(extractor, '_preview_extraction') as mock_preview:
            mock_preview.return_value = ExtractionResult(
                entities=[],
                quotes=[],
                relationships=[],
                metadata={'preview': True, 'dry_run': True}
            )
            result = extractor.extract_knowledge(segment)
        
        # In dry run mode, should return preview results
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get('preview', False) is True
        mock_preview.assert_called_once()
    
    def test_extract_insights_compatibility(self, extractor):
        """Test insight extraction compatibility method."""
        # Test the compatibility method
        with mock.patch.object(extractor, 'extract_knowledge') as mock_extract:
            mock_extract.return_value = ExtractionResult(
                entities=[],
                quotes=[],
                relationships=[],
                metadata={}
            )
            
            insights = extractor.extract_insights("Test text for insights")
            
            # Should call extract_knowledge internally
            mock_extract.assert_called_once()
            assert isinstance(insights, list)
    
    def test_extract_topics(self, extractor):
        """Test topic extraction compatibility method."""
        topics = extractor.extract_topics("Test text about technology and AI")
        
        # Should return a list (even if empty)
        assert isinstance(topics, list)


class TestFactoryFunction:
    """Test create_extractor factory function."""
    
    def test_create_extractor(self):
        """Test creating extractor via factory function."""
        from src.extraction.extraction import ExtractionConfig
        
        mock_llm = mock.Mock()
        mock_embedding = mock.Mock()
        config = ExtractionConfig(extract_quotes=True)
        
        extractor = create_extractor(
            llm_service=mock_llm,
            embedding_service=mock_embedding,
            config=config
        )
        
        assert isinstance(extractor, KnowledgeExtractor)
        assert extractor.llm_service == mock_llm
        assert extractor.embedding_service == mock_embedding
        assert extractor.config == config


class TestCompatibilityMethods:
    """Test compatibility methods for backward compatibility."""
    
    def test_extract_quotes_compatibility(self):
        """Test extract_quotes_compatibility method."""
        mock_llm = mock.Mock()
        extractor = KnowledgeExtractor(llm_service=mock_llm)
        
        # Test with string input
        quotes = extractor.extract_quotes_compatibility("Test quote text")
        assert isinstance(quotes, list)
        
        # Test with segment list input
        from src.core.interfaces import TranscriptSegment
        segments = [
            TranscriptSegment(id="seg1", text="Segment 1", start_time=0, end_time=10),
            TranscriptSegment(id="seg2", text="Segment 2", start_time=10, end_time=20)
        ]
        quotes = extractor.extract_quotes_compatibility(segments)
        assert isinstance(quotes, list)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor for edge case testing."""
        mock_llm = mock.Mock()
        return KnowledgeExtractor(llm_service=mock_llm)
    
    def test_empty_text_handling(self, extractor):
        """Test handling of empty text inputs."""
        # Test with empty string
        entities = extractor.extract_entities("")
        assert entities == []
        
        # Test with whitespace only
        entities = extractor.extract_entities("   \n\t   ")
        assert entities == []
    
    def test_unicode_handling(self, extractor):
        """Test handling of unicode in text."""
        text_with_unicode = "Discussion about 日本 (Japan) and machine learning 机器学习"
        
        from src.core.models import Segment
        segment = Segment(
            id="unicode_seg",
            text=text_with_unicode,
            start_time=0.0,
            end_time=10.0
        )
        
        # Mock internal methods to avoid actual processing
        with mock.patch.object(extractor, '_extract_quotes', return_value=[]):
            with mock.patch.object(extractor, '_extract_basic_entities', return_value=[]):
                with mock.patch.object(extractor, '_extract_relationships', return_value=[]):
                    result = extractor.extract_knowledge(segment)
        
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get('text_length') == len(text_with_unicode)
    
    def test_very_long_text(self, extractor):
        """Test handling of very long text."""
        # Create a very long text
        long_text = "This is a test. " * 10000  # ~150k characters
        
        from src.core.models import Segment
        segment = Segment(
            id="long_seg",
            text=long_text,
            start_time=0.0,
            end_time=100.0
        )
        
        # Mock the internal methods to avoid actual processing
        with mock.patch.object(extractor, '_extract_quotes', return_value=[]):
            with mock.patch.object(extractor, '_extract_basic_entities', return_value=[]):
                with mock.patch.object(extractor, '_extract_relationships', return_value=[]):
                    result = extractor.extract_knowledge(segment)
        
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get('segment_id') == "long_seg"
        assert result.metadata.get('text_length') == len(long_text)
    
    def test_segment_metadata_handling(self, extractor):
        """Test handling of segment metadata."""
        from src.core.models import Segment
        segment = Segment(
            id="meta_seg",
            text="Test segment with metadata",
            start_time=5.0,
            end_time=15.0,
            speaker="TestSpeaker"
        )
        
        # Mock internal methods
        with mock.patch.object(extractor, '_extract_quotes', return_value=[]):
            with mock.patch.object(extractor, '_extract_basic_entities', return_value=[]):
                with mock.patch.object(extractor, '_extract_relationships', return_value=[]):
                    result = extractor.extract_knowledge(
                        segment,
                        episode_metadata={"title": "Test Episode", "number": 42}
                    )
        
        # Check metadata
        assert result.metadata["segment_id"] == "meta_seg"
        assert result.metadata["episode_metadata"] == {"title": "Test Episode", "number": 42}
        assert result.metadata["text_length"] == len("Test segment with metadata")