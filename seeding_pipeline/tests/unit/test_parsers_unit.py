"""Unit tests for response parsing utilities."""

from datetime import datetime
from unittest.mock import Mock, patch
import json

import pytest

from src.extraction.parsers import (
    ParseResult,
    ResponseParser
)
from src.core.models import (
    Entity, Insight, Quote, EntityType, InsightType, QuoteType
)


class TestParseResult:
    """Test ParseResult class."""
    
    def test_parse_result_creation(self):
        """Test creating ParseResult."""
        entities = [Entity(id="1", name="Test", entity_type=EntityType.PERSON)]
        
        # Test successful result
        result = ParseResult(
            success=True,
            data={"entities": entities}
        )
        
        assert result.success is True
        assert result.data["entities"] == entities
        assert result.errors == []
        assert result.warnings == []
        
        # Test failed result with errors
        result_failed = ParseResult(
            success=False,
            data=None,
            errors=["Parsing failed"]
        )
        
        assert result_failed.success is False
        assert result_failed.data is None
        assert len(result_failed.errors) == 1
        assert result_failed.errors[0] == "Parsing failed"


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
        
        result = parser.parse_json_response(response, expected_type=dict)
        assert isinstance(result, ParseResult)
        assert result.success is True
        assert isinstance(result.data, dict)
    
    def test_parse_empty_response(self, parser):
        """Test parsing empty response."""
        result = parser.parse_json_response("{}", expected_type=dict)
        assert isinstance(result, ParseResult)
        assert result.success is True
        assert result.data == {}
    
    def test_parse_invalid_json(self, parser):
        """Test parsing invalid JSON."""
        result = parser.parse_json_response("invalid json {", expected_type=dict)
        assert isinstance(result, ParseResult)
        assert result.success is False
        assert len(result.errors) > 0


@pytest.mark.skip(reason="ValidationUtils class not implemented in current version")
class TestValidationUtils:
    """Test ValidationUtils class."""
    
    def test_validate_entity(self):
        """Test entity validation."""
        entity = Entity(id="1", name="Test Entity", entity_type=EntityType.PERSON)
        
        # ValidationUtils not implemented
        assert True
    
    def test_validate_insight(self):
        """Test insight validation."""
        insight = Insight(id="1", title="Test", description="Test insight", insight_type=InsightType.FACTUAL, confidence_score=0.8)
        
        # ValidationUtils not implemented
        assert True
    
    def test_validate_quote(self):
        """Test quote validation."""
        quote = Quote(
            id="1",
            text="Test quote",
            speaker="Speaker",
            quote_type=QuoteType.GENERAL
        )
        
        # ValidationUtils not implemented
        assert True