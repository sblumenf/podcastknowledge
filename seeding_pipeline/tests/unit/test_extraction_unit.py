"""Unit tests for knowledge extraction module.

Tests for src/processing/extraction.py focusing on unit-level testing
with mocked dependencies.
"""

from datetime import datetime
from typing import Dict, Any, List
from unittest import mock
import json

import pytest

from src.processing.extraction import (
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
            insights=insights,
            quotes=quotes,
            topics=topics,
            metadata=metadata
        )
        
        assert result.entities == entities
        assert result.insights == insights
        assert result.quotes == quotes
        assert result.topics == topics
        assert result.metadata == metadata


class TestKnowledgeExtractor:
    """Test KnowledgeExtractor class."""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = mock.Mock()
        provider.complete = mock.Mock(return_value="Mock response")
        return provider
    
    @pytest.fixture
    def extractor(self, mock_llm_provider):
        """Create KnowledgeExtractor instance."""
        return KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            use_large_context=True,
            max_retries=3,
            enable_cache=True,
            cache_size=128
        )
    
    def test_extractor_initialization(self, mock_llm_provider):
        """Test extractor initialization."""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            use_large_context=False,
            max_retries=5,
            enable_cache=False,
            cache_size=256
        )
        
        assert extractor.llm_provider == mock_llm_provider
        assert extractor.use_large_context is False
        assert extractor.max_retries == 5
        assert extractor.enable_cache is False
        assert extractor._cache_size == 256
        assert extractor._cache == {}
    
    def test_cache_key_generation(self, extractor):
        """Test cache key generation."""
        key1 = extractor._get_cache_key("entities", "test text", "extra")
        key2 = extractor._get_cache_key("entities", "test text", "extra")
        key3 = extractor._get_cache_key("insights", "test text", "extra")
        key4 = extractor._get_cache_key("entities", "different text", "extra")
        
        # Same inputs should generate same key
        assert key1 == key2
        # Different method should generate different key
        assert key1 != key3
        # Different text should generate different key
        assert key1 != key4
        
        # Key should be a valid MD5 hash (32 characters)
        assert len(key1) == 32
        assert all(c in '0123456789abcdef' for c in key1)
    
    def test_cache_operations(self, extractor):
        """Test cache get/add operations."""
        # Test with cache enabled
        cache_key = "test_key"
        value = {"data": "test"}
        
        # Initially cache should be empty
        assert extractor._get_from_cache(cache_key) is None
        
        # Add to cache
        extractor._add_to_cache(cache_key, value)
        assert extractor._get_from_cache(cache_key) == value
        
        # Clear cache
        extractor.clear_cache()
        assert extractor._get_from_cache(cache_key) is None
    
    def test_cache_disabled(self, mock_llm_provider):
        """Test cache operations when disabled."""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            enable_cache=False
        )
        
        cache_key = "test_key"
        value = {"data": "test"}
        
        # Cache operations should do nothing
        assert extractor._get_from_cache(cache_key) is None
        extractor._add_to_cache(cache_key, value)
        assert extractor._get_from_cache(cache_key) is None
    
    def test_cache_size_limit(self, extractor):
        """Test cache size limit enforcement."""
        # Set small cache size for testing
        extractor._cache_size = 3
        
        # Add items to fill cache
        for i in range(5):
            extractor._add_to_cache(f"key_{i}", f"value_{i}")
        
        # Cache should only contain last 3 items
        assert len(extractor._cache) == 3
        assert extractor._get_from_cache("key_0") is None
        assert extractor._get_from_cache("key_1") is None
        assert extractor._get_from_cache("key_2") == "value_2"
        assert extractor._get_from_cache("key_3") == "value_3"
        assert extractor._get_from_cache("key_4") == "value_4"
    
    def test_extract_all(self, extractor, mock_llm_provider):
        """Test extract_all method."""
        # Mock entity extraction
        mock_entities = [Entity(
            id="entity_1",
            name="Test Entity",
            entity_type=EntityType.PERSON,
            description="Test"
        )]
        
        # Mock responses for different extraction methods
        with mock.patch.object(extractor, 'extract_entities', return_value=mock_entities):
            with mock.patch.object(extractor, 'extract_insights', return_value=[]):
                with mock.patch.object(extractor, 'extract_quotes', return_value=[]):
                    with mock.patch.object(extractor, 'extract_topics', return_value=[]):
                        result = extractor.extract_all("Test text", {"context": "test"})
        
        assert isinstance(result, ExtractionResult)
        assert result.entities == mock_entities
        assert result.insights == []
        assert result.quotes == []
        assert result.topics == []
        assert result.metadata['text_length'] == len("Test text")
        assert result.metadata['entity_count'] == 1
        assert result.metadata['context'] == {"context": "test"}
        assert 'extraction_timestamp' in result.metadata
    
    def test_extract_entities_success(self, extractor, mock_llm_provider):
        """Test successful entity extraction."""
        # Mock LLM response
        llm_response = json.dumps([
            {
                "name": "John Doe",
                "type": "Person",
                "description": "A researcher",
                "frequency": 5,
                "importance": 8,
                "has_citation": True,
                "context_type": "research"
            }
        ])
        mock_llm_provider.complete.return_value = llm_response
        
        entities = extractor.extract_entities("John Doe is a researcher.")
        
        assert len(entities) == 1
        assert entities[0].name == "John Doe"
        assert entities[0].entity_type == EntityType.PERSON
        assert entities[0].description == "A researcher"
        assert entities[0].mention_count == 5
        
        # Check caching
        mock_llm_provider.complete.reset_mock()
        entities2 = extractor.extract_entities("John Doe is a researcher.")
        assert entities2 == entities
        # LLM should not be called again due to cache
        mock_llm_provider.complete.assert_not_called()
    
    def test_extract_entities_empty_text(self, extractor):
        """Test entity extraction with empty text."""
        assert extractor.extract_entities("") == []
        assert extractor.extract_entities("   ") == []
    
    def test_extract_entities_retry_logic(self, extractor, mock_llm_provider):
        """Test retry logic on extraction failure."""
        # First two attempts fail, third succeeds
        mock_llm_provider.complete.side_effect = [
            Exception("Network error"),
            Exception("Parse error"),
            json.dumps([{"name": "Test", "type": "Person"}])
        ]
        
        entities = extractor.extract_entities("Test person")
        
        assert len(entities) == 1
        assert entities[0].name == "Test"
        assert mock_llm_provider.complete.call_count == 3
    
    def test_extract_entities_all_retries_fail(self, extractor, mock_llm_provider):
        """Test when all retries fail."""
        mock_llm_provider.complete.side_effect = Exception("Persistent error")
        
        # Should return empty list instead of raising
        entities = extractor.extract_entities("Test text")
        assert entities == []
        assert mock_llm_provider.complete.call_count == 3
    
    def test_extract_combined_success(self, extractor, mock_llm_provider):
        """Test successful combined extraction."""
        # Mock LLM response
        llm_response = json.dumps({
            "entities": [
                {"name": "AI", "type": "Technology", "description": "Artificial Intelligence", "importance": 9}
            ],
            "insights": [
                {"content": "AI is transforming industries", "type": "factual", "confidence": 0.9}
            ],
            "quotes": [
                {"text": "The future is AI", "speaker": "Expert", "type": "memorable"}
            ]
        })
        mock_llm_provider.complete.return_value = llm_response
        
        result = extractor.extract_combined(
            "Discussion about AI",
            podcast_name="Tech Talk",
            episode_title="AI Revolution"
        )
        
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 1
        assert result.entities[0].name == "AI"
        assert len(result.insights) == 1
        assert len(result.quotes) == 1
        assert result.metadata['podcast_name'] == "Tech Talk"
        assert result.metadata['episode_title'] == "AI Revolution"
    
    def test_extract_combined_empty_text(self, extractor):
        """Test combined extraction with empty text."""
        result = extractor.extract_combined("")
        
        assert isinstance(result, ExtractionResult)
        assert result.entities == []
        assert result.insights == []
        assert result.quotes == []
        assert result.topics == []
        assert result.metadata['empty_input'] is True
    
    def test_extract_combined_fallback(self, extractor, mock_llm_provider):
        """Test fallback to individual extraction on combined failure."""
        # Make combined extraction fail
        mock_llm_provider.complete.side_effect = Exception("Parse error")
        
        # Mock individual extraction methods
        with mock.patch.object(extractor, 'extract_all') as mock_extract_all:
            mock_result = ExtractionResult(
                entities=[], insights=[], quotes=[], topics=[], metadata={}
            )
            mock_extract_all.return_value = mock_result
            
            result = extractor.extract_combined("Test text")
            
            assert result == mock_result
            mock_extract_all.assert_called_once_with("Test text")
    
    def test_parse_entities_from_combined(self, extractor):
        """Test parsing entities from combined response."""
        entity_data = [
            {"name": "Python", "type": "Technology", "description": "Programming language", "importance": 8, "frequency": 10},
            {"name": "Django", "type": "Framework", "description": "Web framework", "importance": 7}
        ]
        
        entities = extractor._parse_entities_from_combined(entity_data)
        
        assert len(entities) == 2
        assert entities[0].name == "Python"
        assert entities[0].entity_type == EntityType.TECHNOLOGY
        assert entities[0].confidence_score == 0.8
        assert entities[0].mention_count == 10
        assert entities[1].name == "Django"
        assert entities[1].mention_count == 1  # Default
    
    def test_parse_entities_from_combined_error_handling(self, extractor):
        """Test error handling in entity parsing."""
        entity_data = [
            {"name": "Valid", "type": "Person"},
            {},  # Missing required fields
            {"name": "Another", "type": "InvalidType"}
        ]
        
        entities = extractor._parse_entities_from_combined(entity_data)
        
        # Should skip invalid entries
        assert len(entities) == 2
        assert entities[0].name == "Valid"
        assert entities[1].name == "Another"
    
    def test_parse_insights_from_combined(self, extractor):
        """Test parsing insights from combined response."""
        insight_data = [
            {
                "title": "Key Finding",
                "description": "Important discovery",
                "type": "factual",
                "confidence": 0.95,
                "related_entities": ["Entity1", "Entity2"]
            },
            {
                "content": "Technical insight: New algorithm improves performance",
                "type": "technical",
                "confidence": 0.8
            }
        ]
        
        insights = extractor._parse_insights_from_combined(insight_data)
        
        assert len(insights) == 2
        assert insights[0].title == "Key Finding"
        assert insights[0].description == "Important discovery"
        assert insights[0].insight_type == InsightType.FACTUAL
        assert insights[0].confidence_score == 0.95
        assert insights[0].supporting_entities == ["Entity1", "Entity2"]
        
        assert insights[1].title == "Technical insight"
        assert "New algorithm improves performance" in insights[1].description
        assert insights[1].insight_type == InsightType.TECHNICAL
    
    def test_parse_quotes_from_combined(self, extractor):
        """Test parsing quotes from combined response."""
        quote_data = [
            {
                "text": "Innovation is key to progress",
                "speaker": "CEO",
                "type": "memorable",
                "context": "During keynote"
            },
            {
                "text": "We must adapt or perish",
                "speaker": "Unknown",
                "type": "controversial"
            }
        ]
        
        quotes = extractor._parse_quotes_from_combined(quote_data)
        
        assert len(quotes) == 2
        assert quotes[0].text == "Innovation is key to progress"
        assert quotes[0].speaker == "CEO"
        assert quotes[0].quote_type == QuoteType.MEMORABLE
        assert quotes[0].context == "During keynote"
        
        assert quotes[1].speaker == "Unknown"
        assert quotes[1].quote_type == QuoteType.CONTROVERSIAL
    
    def test_derive_topics_from_insights(self, extractor):
        """Test deriving topics from insights."""
        insights = [
            Insight(id="1", title="Fact 1", description="", insight_type=InsightType.FACTUAL),
            Insight(id="2", title="Fact 2", description="", insight_type=InsightType.FACTUAL),
            Insight(id="3", title="Tech 1", description="", insight_type=InsightType.TECHNICAL),
            Insight(id="4", title="Rec 1", description="", insight_type=InsightType.RECOMMENDATION)
        ]
        
        topics = extractor._derive_topics_from_insights(insights)
        
        assert len(topics) == 3  # 3 different insight types
        
        # Find factual topic
        factual_topic = next(t for t in topics if "factual" in t['name'].lower())
        assert factual_topic['insight_count'] == 2
    
    def test_extract_from_segments(self, extractor, mock_llm_provider):
        """Test extraction from multiple segments."""
        segments = [
            {
                "text": "First segment about AI",
                "start_time": 0,
                "end_time": 30,
                "speaker": "Host"
            },
            {
                "text": "Second segment about ML",
                "start_time": 30,
                "end_time": 60,
                "speaker": "Guest"
            }
        ]
        
        # Mock combined extraction
        def mock_extract_combined(text, **kwargs):
            if "AI" in text:
                entities = [Entity(id="ai", name="AI", entity_type=EntityType.TECHNOLOGY)]
            else:
                entities = [Entity(id="ml", name="ML", entity_type=EntityType.TECHNOLOGY)]
            
            return ExtractionResult(
                entities=entities,
                insights=[],
                quotes=[],
                topics=[],
                metadata={}
            )
        
        with mock.patch.object(extractor, 'extract_combined', side_effect=mock_extract_combined):
            result = extractor.extract_from_segments(segments, "Tech Podcast", "Episode 1")
        
        assert 'entities' in result
        assert 'segments' in result
        assert result['segments'] == 2
        assert result['metadata']['total_duration'] == 60
        assert result['metadata']['importance_scoring_applied'] is True
    
    def test_merge_duplicate_entities(self, extractor):
        """Test merging duplicate entities."""
        entities = [
            Entity(id="1", name="Apple", entity_type=EntityType.ORGANIZATION, 
                   description="Tech company", mention_count=3, aliases=[]),
            Entity(id="2", name="apple", entity_type=EntityType.ORGANIZATION,
                   description="iPhone maker", mention_count=2, aliases=["AAPL"]),
            Entity(id="3", name="Google", entity_type=EntityType.ORGANIZATION,
                   description="Search giant", mention_count=1, aliases=[])
        ]
        
        # Add segment tracking attributes
        entities[0]._segment_indices = [0, 1]
        entities[0]._timestamps = [0, 30]
        entities[1]._segment_indices = [2]
        entities[1]._timestamps = [60]
        
        merged = extractor._merge_duplicate_entities(entities)
        
        assert len(merged) == 2  # Apple entities merged, Google separate
        
        # Find merged Apple entity
        apple = next(e for e in merged if e.name.lower() == "apple")
        assert apple.mention_count == 5  # 3 + 2
        assert "Tech company" in apple.description
        assert "iPhone maker" in apple.description
        assert "AAPL" in apple.aliases
        assert len(apple._segment_indices) == 3
        assert len(apple._timestamps) == 3
    
    def test_entity_type_mapping(self, extractor):
        """Test entity type string to enum mapping."""
        mappings = [
            ("PERSON", EntityType.PERSON),
            ("Company", EntityType.ORGANIZATION),
            ("PRODUCT", EntityType.PRODUCT),
            ("TECHNOLOGY", EntityType.TECHNOLOGY),
            ("CONCEPT", EntityType.CONCEPT),
            ("LOCATION", EntityType.LOCATION),
            ("EVENT", EntityType.EVENT),
            ("STUDY", EntityType.RESEARCH_METHOD),
            ("MEDICATION", EntityType.MEDICAL_TERM),
            ("CONDITION", EntityType.MEDICAL_TERM),
            ("Unknown", EntityType.CONCEPT)  # Default
        ]
        
        for type_str, expected in mappings:
            assert extractor._map_entity_type(type_str) == expected
    
    def test_insight_type_mapping(self, extractor):
        """Test insight type string to enum mapping."""
        mappings = [
            ("factual", InsightType.FACTUAL),
            ("conceptual", InsightType.CONCEPTUAL),
            ("prediction", InsightType.PREDICTION),
            ("recommendation", InsightType.RECOMMENDATION),
            ("key_point", InsightType.KEY_POINT),
            ("technical", InsightType.TECHNICAL),
            ("methodological", InsightType.METHODOLOGICAL),
            ("unknown", InsightType.FACTUAL)  # Default
        ]
        
        for type_str, expected in mappings:
            assert extractor._map_insight_type(type_str) == expected
    
    def test_quote_type_mapping(self, extractor):
        """Test quote type string to enum mapping."""
        mappings = [
            ("memorable", QuoteType.MEMORABLE),
            ("controversial", QuoteType.CONTROVERSIAL),
            ("humorous", QuoteType.HUMOROUS),
            ("insightful", QuoteType.INSIGHTFUL),
            ("technical", QuoteType.TECHNICAL),
            ("general", QuoteType.GENERAL),
            ("unknown", QuoteType.GENERAL)  # Default
        ]
        
        for type_str, expected in mappings:
            assert extractor._map_quote_type(type_str) == expected
    
    def test_build_entity_prompt_large_context(self, extractor):
        """Test entity prompt building with large context."""
        prompt = extractor._build_entity_prompt("Sample text")
        
        assert "1M token context window" in prompt
        assert "Sample text" in prompt
        assert "Entity Types to Extract" in prompt
        assert "JSON RESPONSE:" in prompt
    
    def test_build_entity_prompt_small_context(self, mock_llm_provider):
        """Test entity prompt building with small context."""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            use_large_context=False
        )
        
        prompt = extractor._build_entity_prompt("Sample text")
        
        assert "1M token context window" not in prompt
        assert "Sample text" in prompt
        assert "Entity Types:" in prompt
    
    def test_build_insight_prompt_with_entities(self, extractor):
        """Test insight prompt with entity context."""
        entities = [
            Entity(id="1", name="Entity1", entity_type=EntityType.PERSON),
            Entity(id="2", name="Entity2", entity_type=EntityType.ORGANIZATION)
        ]
        
        prompt = extractor._build_insight_prompt("Text", entities)
        
        assert "Key entities mentioned: Entity1, Entity2" in prompt
    
    def test_extract_json_from_response(self, extractor):
        """Test JSON extraction from LLM response."""
        # Test with markdown code block
        response1 = """
        Here's the JSON:
        ```json
        [{"name": "Test", "value": 1}]
        ```
        """
        result1 = extractor._extract_json_from_response(response1)
        assert result1 == [{"name": "Test", "value": 1}]
        
        # Test with direct JSON
        response2 = '[{"name": "Direct", "value": 2}]'
        result2 = extractor._extract_json_from_response(response2)
        assert result2 == [{"name": "Direct", "value": 2}]
        
        # Test with object instead of array
        response3 = '{"name": "Single", "value": 3}'
        result3 = extractor._extract_json_from_response(response3)
        assert result3 == [{"name": "Single", "value": 3}]
        
        # Test with invalid JSON
        response4 = "This is not JSON"
        result4 = extractor._extract_json_from_response(response4)
        assert result4 == []
    
    def test_validate_entities(self, extractor):
        """Test entity validation."""
        source_text = "John Doe works at Apple Inc. They develop the iPhone."
        
        entities = [
            Entity(id="1", name="John Doe", entity_type=EntityType.PERSON),
            Entity(id="2", name="Apple Inc", entity_type=EntityType.ORGANIZATION),
            Entity(id="3", name="iPhone", entity_type=EntityType.PRODUCT),
            Entity(id="4", name="X", entity_type=EntityType.OTHER),  # Too short
            Entity(id="5", name="Microsoft", entity_type=EntityType.ORGANIZATION),  # Not in text
            Entity(id="6", name="John Doe", entity_type=EntityType.PERSON)  # Duplicate
        ]
        
        validated = extractor._validate_entities(entities, source_text)
        
        assert len(validated) == 3
        assert validated[0].name == "John Doe"
        assert validated[1].name == "Apple Inc"
        assert validated[2].name == "iPhone"
    
    def test_validate_insights(self, extractor):
        """Test insight validation."""
        insights = [
            Insight(id="1", title="Valid", description="Valid insight", 
                    insight_type=InsightType.FACTUAL, confidence_score=0.8),
            Insight(id="2", title="Short", description="Too short", 
                    insight_type=InsightType.FACTUAL, confidence_score=0.5),
            Insight(id="3", title="High confidence", description="Over confidence", 
                    insight_type=InsightType.FACTUAL, confidence_score=1.5),
            Insight(id="4", title="", description="", 
                    insight_type=InsightType.FACTUAL, confidence_score=0.7)
        ]
        
        # Modify content attribute for testing
        insights[0].content = "This is a valid insight with enough content"
        insights[1].content = "Short"
        insights[2].content = "This insight has over-confidence score"
        insights[3].content = ""
        
        validated = extractor._validate_insights(insights)
        
        assert len(validated) == 2
        assert validated[0].content == "This is a valid insight with enough content"
        assert validated[1].content == "This insight has over-confidence score"
        assert validated[1].confidence_score == 1.0  # Clamped to max
    
    def test_validate_quotes(self, extractor):
        """Test quote validation."""
        source_text = "The speaker said 'Innovation is key to success' during the talk. Also mentioned 'Failure is part of learning'."
        
        quotes = [
            Quote(id="1", text="Innovation is key to success", speaker="Speaker", quote_type=QuoteType.MEMORABLE),
            Quote(id="2", text="Short", speaker="Speaker", quote_type=QuoteType.GENERAL),  # Too short
            Quote(id="3", text="This quote is not in the source text at all", speaker="Unknown", quote_type=QuoteType.GENERAL),
            Quote(id="4", text="Failure is part of learning", speaker="Speaker", quote_type=QuoteType.INSIGHTFUL)
        ]
        
        validated = extractor._validate_quotes(quotes, source_text)
        
        assert len(validated) == 2
        assert validated[0].text == "Innovation is key to success"
        assert validated[1].text == "Failure is part of learning"


class TestFactoryFunction:
    """Test create_extractor factory function."""
    
    def test_create_extractor(self):
        """Test creating extractor via factory function."""
        config = {
            "llm_provider": mock.Mock(),
            "use_large_context": True,
            "max_retries": 5
        }
        
        # Note: The actual implementation seems to expect a config dict
        # but the current implementation takes a config parameter
        # This test assumes the factory function would be implemented properly
        with mock.patch('src.processing.extraction.KnowledgeExtractor') as MockExtractor:
            extractor = create_extractor(config)
            MockExtractor.assert_called_once_with(config)


class TestDeprecationWarnings:
    """Test deprecation warnings are properly applied."""
    
    def test_class_deprecation_warning(self):
        """Test that KnowledgeExtractor shows deprecation warning."""
        # The class should have deprecation decorator
        assert hasattr(KnowledgeExtractor, '__deprecated__')
    
    def test_method_deprecation_warnings(self):
        """Test that deprecated methods have warnings."""
        mock_llm = mock.Mock()
        extractor = KnowledgeExtractor(llm_provider=mock_llm)
        
        # These methods should have deprecation decorators
        deprecated_methods = [
            'extract_entities',
            'extract_insights', 
            'extract_quotes',
            'extract_topics'
        ]
        
        for method_name in deprecated_methods:
            method = getattr(extractor, method_name)
            assert hasattr(method, '__deprecated__')


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor for edge case testing."""
        mock_llm = mock.Mock()
        return KnowledgeExtractor(llm_provider=mock_llm)
    
    def test_malformed_json_response(self, extractor):
        """Test handling of malformed JSON responses."""
        responses = [
            "Not JSON at all",
            '{"incomplete": ',
            '["missing", "closing"',
            'null',
            'undefined',
            '{"nested": {"too": {"deep": {"for": {"parsing": "maybe"}}}}}'
        ]
        
        for response in responses:
            result = extractor._extract_json_from_response(response)
            assert isinstance(result, list)  # Should always return a list
    
    def test_unicode_handling(self, extractor):
        """Test handling of unicode in text."""
        text_with_unicode = "Discussion about 日本 (Japan) and machine learning 机器学习"
        
        # Should handle unicode in cache keys
        cache_key = extractor._get_cache_key("entities", text_with_unicode)
        assert isinstance(cache_key, str)
        assert len(cache_key) == 32
        
        # Should handle unicode in prompts
        prompt = extractor._build_entity_prompt(text_with_unicode)
        assert "日本" in prompt
        assert "机器学习" in prompt
    
    def test_very_long_text(self, extractor):
        """Test handling of very long text."""
        # Create a very long text
        long_text = "This is a test. " * 10000  # ~150k characters
        
        # Should handle long text in cache key (uses first 200 chars)
        cache_key = extractor._get_cache_key("entities", long_text)
        assert len(cache_key) == 32
        
        # Metadata should track text length
        with mock.patch.object(extractor, 'extract_entities', return_value=[]):
            with mock.patch.object(extractor, 'extract_insights', return_value=[]):
                with mock.patch.object(extractor, 'extract_quotes', return_value=[]):
                    with mock.patch.object(extractor, 'extract_topics', return_value=[]):
                        result = extractor.extract_all(long_text)
                        assert result.metadata['text_length'] == len(long_text)
    
    def test_concurrent_extraction(self, extractor):
        """Test thread safety of extraction (cache operations)."""
        import threading
        
        results = []
        errors = []
        
        def extract_entities():
            try:
                # Each thread extracts different text to avoid cache hits
                import random
                text = f"Test text {random.random()}"
                entities = extractor.extract_entities(text)
                results.append(entities)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=extract_entities)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 10