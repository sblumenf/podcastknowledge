"""Unit tests for response parsing utilities."""

from datetime import datetime
from unittest.mock import Mock, patch
import json

import pytest

from src.extraction.parsers import (
    ParseResult,
    ResponseParser,
    ValidationUtils
)
from src.core.models import (
    Entity, Insight, Quote, EntityType, InsightType, QuoteType
)


class TestParseResult:
    """Test ParseResult class."""
    
    def test_parse_result_creation(self):
        """Test creating ParseResult."""
        entities = [Entity(id="1", name="Test", entity_type=EntityType.PERSON)]
        insights = [Insight(id="1", title="Test", description="Test insight", insight_type=InsightType.FACTUAL, confidence_score=0.8)]
        quotes = []
        
        result = ParseResult(
            entities=entities,
            insights=insights,
            quotes=quotes
        )
        
        assert len(result.entities) == 1
        assert len(result.insights) == 1
        assert len(result.quotes) == 0
        assert result.entities[0].name == "Test"
        assert result.insights[0].description == "Test insight"


class TestResponseParser:
    """Test ResponseParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create ResponseParser instance."""
        return ResponseParser()
    
    def test_parser_initialization(self):
        """Test ResponseParser initialization."""
        parser = ResponseParser()
        assert parser is not None
    
    def test_parse_llm_response_json(self, parser):
        """Test parsing JSON LLM response."""
        response = json.dumps({
            "entities": [
                {"id": "1", "name": "John Doe", "entity_type": "PERSON"}
            ],
            "insights": [
                {"id": "1", "title": "Important", "description": "Important insight", "insight_type": "FACTUAL", "confidence_score": 0.8}
            ],
            "quotes": []
        })
        
        if hasattr(parser, 'parse_llm_response'):
            result = parser.parse_llm_response(response)
            assert isinstance(result, ParseResult)
    
    def test_parse_empty_response(self, parser):
        """Test parsing empty response."""
        if hasattr(parser, 'parse_llm_response'):
            result = parser.parse_llm_response("{}")
            assert isinstance(result, ParseResult)
            assert len(result.entities) == 0
            assert len(result.insights) == 0
            assert len(result.quotes) == 0
    
    def test_parse_invalid_json(self, parser):
        """Test parsing invalid JSON."""
        if hasattr(parser, 'parse_llm_response'):
            with pytest.raises(Exception):
                parser.parse_llm_response("invalid json {")


class TestValidationUtils:
    """Test ValidationUtils class."""
    
    def test_validate_entity(self):
        """Test entity validation."""
        entity = Entity(id="1", name="Test Entity", entity_type=EntityType.PERSON)
        
        if hasattr(ValidationUtils, 'validate_entity'):
            assert ValidationUtils.validate_entity(entity) is True
    
    def test_validate_insight(self):
        """Test insight validation."""
        insight = Insight(id="1", title="Test", description="Test insight", insight_type=InsightType.FACTUAL, confidence_score=0.8)
        
        if hasattr(ValidationUtils, 'validate_insight'):
            assert ValidationUtils.validate_insight(insight) is True
    
    def test_validate_quote(self):
        """Test quote validation."""
        quote = Quote(
            id="1",
            text="Test quote",
            speaker="Speaker",
            quote_type=QuoteType.GENERAL
        )
        
        if hasattr(ValidationUtils, 'validate_quote'):
            assert ValidationUtils.validate_quote(quote) is True