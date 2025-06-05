"""Comprehensive unit tests for response parsing utilities."""

import json
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.extraction.parsers import (
    ParseResult,
    ResponseParser,
    EntityParser,
    InsightParser,
    QuoteParser,
    MetricsParser,
    ExtractedParsedData
)
from src.core.models import (
    Entity, Insight, Quote, EntityType, InsightType, QuoteType
)
from src.core.exceptions import ParsingError


class TestParseResult:
    """Test ParseResult dataclass."""
    
    def test_parse_result_creation_success(self):
        """Test creating successful ParseResult."""
        result = ParseResult(success=True, data={"key": "value"})
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.errors == []
        assert result.warnings == []
    
    def test_parse_result_creation_with_errors(self):
        """Test creating ParseResult with errors."""
        result = ParseResult(
            success=False,
            data=None,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"]
        )
        
        assert result.success is False
        assert result.data is None
        assert result.errors == ["Error 1", "Error 2"]
        assert result.warnings == ["Warning 1"]
    
    def test_parse_result_auto_init_lists(self):
        """Test automatic initialization of error/warning lists."""
        result = ParseResult(success=True, data="test")
        
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


class TestResponseParser:
    """Test ResponseParser class."""
    
    def test_response_parser_initialization(self):
        """Test ResponseParser initialization."""
        parser = ResponseParser()
        assert parser.strict_mode is False
        
        strict_parser = ResponseParser(strict_mode=True)
        assert strict_parser.strict_mode is True
    
    def test_parse_json_response_valid_list(self):
        """Test parsing valid JSON list response."""
        parser = ResponseParser()
        response = '```json\n[{"name": "John"}, {"name": "Jane"}]\n```'
        
        result = parser.parse_json_response(response, expected_type=list)
        
        assert result.success is True
        assert result.data == [{"name": "John"}, {"name": "Jane"}]
        assert len(result.errors) == 0
    
    def test_parse_json_response_valid_dict(self):
        """Test parsing valid JSON dict response."""
        parser = ResponseParser()
        response = '{"status": "success", "count": 10}'
        
        result = parser.parse_json_response(response, expected_type=dict)
        
        assert result.success is True
        assert result.data == {"status": "success", "count": 10}
        assert len(result.errors) == 0
    
    def test_parse_json_response_convert_dict_to_list(self):
        """Test converting single dict to list when list expected."""
        parser = ResponseParser()
        response = '{"name": "John"}'
        
        result = parser.parse_json_response(response, expected_type=list)
        
        assert result.success is True
        assert result.data == [{"name": "John"}]
        assert "Converted single object to list" in result.warnings
    
    def test_parse_json_response_type_mismatch(self):
        """Test parsing with type mismatch."""
        parser = ResponseParser()
        response = '[1, 2, 3]'
        
        result = parser.parse_json_response(response, expected_type=dict)
        
        assert result.success is False
        assert result.data is None
        assert any("Expected dict, got list" in error for error in result.errors)
    
    def test_parse_json_response_no_json(self):
        """Test parsing response with no JSON."""
        parser = ResponseParser()
        response = "This is just plain text with no JSON"
        
        result = parser.parse_json_response(response)
        
        assert result.success is False
        assert result.data is None
        assert any("No valid JSON found" in error for error in result.errors)
    
    def test_parse_json_response_malformed_json(self):
        """Test parsing malformed JSON with recovery."""
        parser = ResponseParser()
        # Missing closing quote
        response = '{"name": "John", "age": 25'
        
        with patch.object(parser, '_fix_common_json_errors') as mock_fix:
            mock_fix.return_value = '{"name": "John", "age": 25}'
            
            result = parser.parse_json_response(response)
            
            assert result.success is True
            assert result.data == {"name": "John", "age": 25}
            assert "Fixed JSON formatting issues" in result.warnings
    
    def test_extract_json_string_code_block(self):
        """Test extracting JSON from code block."""
        parser = ResponseParser()
        
        # JSON in code block
        response = "Here's the data:\n```json\n{\"key\": \"value\"}\n```"
        json_str = parser._extract_json_string(response)
        assert json_str == '{"key": "value"}'
        
        # Without language marker
        response = "```\n[1, 2, 3]\n```"
        json_str = parser._extract_json_string(response)
        assert json_str == '[1, 2, 3]'
    
    def test_extract_json_string_direct(self):
        """Test extracting direct JSON."""
        parser = ResponseParser()
        
        response = '{"direct": "json"}'
        json_str = parser._extract_json_string(response)
        assert json_str == '{"direct": "json"}'
    
    def test_fix_common_json_errors(self):
        """Test fixing common JSON errors."""
        parser = ResponseParser()
        
        # Test trailing commas
        json_str = '{"a": 1, "b": 2,}'
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"a": 1, "b": 2}'
        
        # Test single quotes
        json_str = "{'key': 'value'}"
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"key": "value"}'
        
        # Test unquoted keys
        json_str = '{name: "John", age: 25}'
        fixed = parser._fix_common_json_errors(json_str)
        assert '"name"' in fixed and '"age"' in fixed
    
    def test_parse_entities_list_valid(self):
        """Test parsing valid entities list."""
        parser = ResponseParser()
        entities_data = [
            {"name": "Apple Inc", "type": "ORGANIZATION"},
            {"name": "John Smith", "type": "PERSON", "confidence": 0.9}
        ]
        
        result = parser.parse_entities_list(entities_data)
        
        assert result.success is True
        assert len(result.data) == 2
        assert all(isinstance(e, Entity) for e in result.data)
        assert result.data[0].name == "Apple Inc"
        assert result.data[0].type == EntityType.ORGANIZATION
        assert result.data[1].confidence == 0.9
    
    def test_parse_entities_list_invalid_type(self):
        """Test parsing entities with invalid type."""
        parser = ResponseParser()
        entities_data = [
            {"name": "Test", "type": "INVALID_TYPE"}
        ]
        
        result = parser.parse_entities_list(entities_data)
        
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0].type == EntityType.UNKNOWN
        assert len(result.warnings) > 0
    
    def test_parse_entities_list_missing_fields(self):
        """Test parsing entities with missing required fields."""
        parser = ResponseParser()
        entities_data = [
            {"type": "PERSON"},  # Missing name
            {"name": "Test"}     # Missing type
        ]
        
        result = parser.parse_entities_list(entities_data)
        
        assert result.success is True
        assert len(result.data) == 0  # Both should be skipped
        assert len(result.errors) == 2
    
    def test_parse_structured_response(self):
        """Test parsing structured response with multiple sections."""
        parser = ResponseParser()
        response = {
            "entities": [{"name": "Test Entity", "type": "THING"}],
            "insights": [{"title": "Test Insight", "description": "Description"}],
            "quotes": [{"text": "Test quote", "speaker": "Speaker"}],
            "metrics": {"complexity": 50}
        }
        
        result = parser.parse_structured_response(json.dumps(response))
        
        assert result.success is True
        assert "entities" in result.data
        assert "insights" in result.data
        assert "quotes" in result.data
        assert "metrics" in result.data


class TestEntityParser:
    """Test EntityParser class."""
    
    def test_entity_parser_parse_valid(self):
        """Test parsing valid entity data."""
        parser = EntityParser()
        entity_data = {
            "name": "Apple Inc",
            "type": "ORGANIZATION",
            "confidence": 0.95,
            "context": "Tech company",
            "aliases": ["Apple", "AAPL"]
        }
        
        entity = parser.parse(entity_data)
        
        assert isinstance(entity, Entity)
        assert entity.name == "Apple Inc"
        assert entity.type == EntityType.ORGANIZATION
        assert entity.confidence == 0.95
        assert entity.context == "Tech company"
        assert entity.aliases == ["Apple", "AAPL"]
    
    def test_entity_parser_parse_minimal(self):
        """Test parsing entity with minimal data."""
        parser = EntityParser()
        entity_data = {
            "name": "John Smith",
            "type": "PERSON"
        }
        
        entity = parser.parse(entity_data)
        
        assert entity.name == "John Smith"
        assert entity.type == EntityType.PERSON
        assert entity.confidence == 1.0  # Default
        assert entity.context == ""
        assert entity.aliases == []
    
    def test_entity_parser_parse_invalid_type(self):
        """Test parsing entity with invalid type."""
        parser = EntityParser()
        entity_data = {
            "name": "Test",
            "type": "INVALID"
        }
        
        with patch('src.extraction.parsers.logger') as mock_logger:
            entity = parser.parse(entity_data)
            
            assert entity.type == EntityType.UNKNOWN
            mock_logger.warning.assert_called_once()
    
    def test_entity_parser_parse_missing_fields(self):
        """Test parsing entity with missing required fields."""
        parser = EntityParser()
        
        # Missing name
        with pytest.raises(ParsingError):
            parser.parse({"type": "PERSON"})
        
        # Missing type
        with pytest.raises(ParsingError):
            parser.parse({"name": "Test"})
    
    def test_entity_parser_parse_batch(self):
        """Test batch parsing of entities."""
        parser = EntityParser()
        entities_data = [
            {"name": "Entity1", "type": "PERSON"},
            {"name": "Entity2", "type": "ORGANIZATION"},
            {"name": "Entity3", "type": "INVALID"}  # Will be UNKNOWN
        ]
        
        entities = parser.parse_batch(entities_data)
        
        assert len(entities) == 3
        assert all(isinstance(e, Entity) for e in entities)
        assert entities[0].name == "Entity1"
        assert entities[1].type == EntityType.ORGANIZATION
        assert entities[2].type == EntityType.UNKNOWN


class TestInsightParser:
    """Test InsightParser class."""
    
    def test_insight_parser_parse_valid(self):
        """Test parsing valid insight data."""
        parser = InsightParser()
        insight_data = {
            "title": "Key Finding",
            "description": "This is an important discovery",
            "type": "OBSERVATION",
            "confidence": 0.8,
            "supporting_entities": ["Entity1", "Entity2"],
            "tags": ["important", "research"]
        }
        
        insight = parser.parse(insight_data)
        
        assert isinstance(insight, Insight)
        assert insight.title == "Key Finding"
        assert insight.description == "This is an important discovery"
        assert insight.type == InsightType.OBSERVATION
        assert insight.confidence == 0.8
        assert insight.supporting_entities == ["Entity1", "Entity2"]
        assert insight.tags == ["important", "research"]
    
    def test_insight_parser_parse_minimal(self):
        """Test parsing insight with minimal data."""
        parser = InsightParser()
        insight_data = {
            "title": "Simple Insight",
            "description": "Basic description"
        }
        
        insight = parser.parse(insight_data)
        
        assert insight.title == "Simple Insight"
        assert insight.description == "Basic description"
        assert insight.type == InsightType.OBSERVATION  # Default
        assert insight.confidence == 1.0  # Default
        assert insight.supporting_entities == []
        assert insight.tags == []
    
    def test_insight_parser_parse_invalid_type(self):
        """Test parsing insight with invalid type."""
        parser = InsightParser()
        insight_data = {
            "title": "Test",
            "description": "Test description",
            "type": "INVALID_TYPE"
        }
        
        with patch('src.extraction.parsers.logger') as mock_logger:
            insight = parser.parse(insight_data)
            
            assert insight.type == InsightType.OBSERVATION  # Default
            mock_logger.warning.assert_called_once()
    
    def test_insight_parser_parse_batch(self):
        """Test batch parsing of insights."""
        parser = InsightParser()
        insights_data = [
            {"title": "Insight1", "description": "Desc1", "type": "TREND"},
            {"title": "Insight2", "description": "Desc2", "type": "ANALYSIS"},
            {"title": "Insight3", "description": "Desc3"}
        ]
        
        insights = parser.parse_batch(insights_data)
        
        assert len(insights) == 3
        assert all(isinstance(i, Insight) for i in insights)
        assert insights[0].type == InsightType.TREND
        assert insights[1].type == InsightType.ANALYSIS
        assert insights[2].type == InsightType.OBSERVATION


class TestQuoteParser:
    """Test QuoteParser class."""
    
    def test_quote_parser_parse_valid(self):
        """Test parsing valid quote data."""
        parser = QuoteParser()
        quote_data = {
            "text": "This is a memorable quote",
            "speaker": "John Smith",
            "type": "MEMORABLE",
            "context": "During the interview",
            "timestamp": "00:15:30"
        }
        
        quote = parser.parse(quote_data)
        
        assert isinstance(quote, Quote)
        assert quote.text == "This is a memorable quote"
        assert quote.speaker == "John Smith"
        assert quote.type == QuoteType.MEMORABLE
        assert quote.context == "During the interview"
        assert quote.timestamp == "00:15:30"
    
    def test_quote_parser_parse_minimal(self):
        """Test parsing quote with minimal data."""
        parser = QuoteParser()
        quote_data = {
            "text": "Simple quote",
            "speaker": "Unknown"
        }
        
        quote = parser.parse(quote_data)
        
        assert quote.text == "Simple quote"
        assert quote.speaker == "Unknown"
        assert quote.type == QuoteType.GENERAL  # Default
        assert quote.context == ""
        assert quote.timestamp is None
    
    def test_quote_parser_parse_batch(self):
        """Test batch parsing of quotes."""
        parser = QuoteParser()
        quotes_data = [
            {"text": "Quote1", "speaker": "Speaker1", "type": "INSIGHTFUL"},
            {"text": "Quote2", "speaker": "Speaker2", "type": "CONTROVERSIAL"},
            {"text": "Quote3", "speaker": "Speaker3"}
        ]
        
        quotes = parser.parse_batch(quotes_data)
        
        assert len(quotes) == 3
        assert all(isinstance(q, Quote) for q in quotes)
        assert quotes[0].type == QuoteType.INSIGHTFUL
        assert quotes[1].type == QuoteType.CONTROVERSIAL
        assert quotes[2].type == QuoteType.GENERAL


class TestMetricsParser:
    """Test MetricsParser class."""
    
    def test_metrics_parser_parse_valid(self):
        """Test parsing valid metrics data."""
        parser = MetricsParser()
        metrics_data = {
            "complexity": 75,
            "information_density": 0.8,
            "entity_count": 15,
            "insight_count": 5,
            "quote_count": 3,
            "custom_metric": 100
        }
        
        metrics = parser.parse(metrics_data)
        
        assert metrics["complexity"] == 75
        assert metrics["information_density"] == 0.8
        assert metrics["entity_count"] == 15
        assert metrics["custom_metric"] == 100
    
    def test_metrics_parser_normalize_values(self):
        """Test normalizing metric values."""
        parser = MetricsParser()
        metrics_data = {
            "complexity": 150,  # Over 100
            "score": -10,      # Below 0
            "density": 2.5     # Over 1
        }
        
        metrics = parser.parse(metrics_data)
        
        assert metrics["complexity"] == 100  # Capped at 100
        assert metrics["score"] == 0         # Capped at 0
        assert metrics["density"] == 1.0     # Capped at 1


class TestExtractedParsedData:
    """Test ExtractedParsedData container."""
    
    def test_extracted_parsed_data_creation(self):
        """Test creating ExtractedParsedData."""
        entities = [Entity(name="Test", type=EntityType.THING)]
        insights = [Insight(title="Test", description="Desc")]
        quotes = [Quote(text="Test quote", speaker="Speaker")]
        metrics = {"complexity": 50}
        
        data = ExtractedParsedData(
            entities=entities,
            insights=insights,
            quotes=quotes,
            metrics=metrics
        )
        
        assert data.entities == entities
        assert data.insights == insights
        assert data.quotes == quotes
        assert data.metrics == metrics
    
    def test_extracted_parsed_data_to_dict(self):
        """Test converting ExtractedParsedData to dictionary."""
        entity = Entity(name="Test Entity", type=EntityType.PERSON)
        insight = Insight(title="Test Insight", description="Description")
        quote = Quote(text="Test quote", speaker="Speaker")
        
        data = ExtractedParsedData(
            entities=[entity],
            insights=[insight],
            quotes=[quote],
            metrics={"score": 75}
        )
        
        result = data.to_dict()
        
        assert "entities" in result
        assert "insights" in result
        assert "quotes" in result
        assert "metrics" in result
        
        # Check serialization
        assert result["entities"][0]["name"] == "Test Entity"
        assert result["insights"][0]["title"] == "Test Insight"
        assert result["quotes"][0]["text"] == "Test quote"
        assert result["metrics"]["score"] == 75