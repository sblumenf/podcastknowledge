"""Comprehensive tests for response parsing module.

Tests for src/processing/parsers.py covering all parsing functionality,
edge cases, and validation utilities.
"""

from datetime import datetime
from typing import Dict, Any, List
import json

import pytest

from src.extraction.parsers import (
    ResponseParser, ParseResult
)
from src.core.models import (
    Entity, EntityType, Insight, InsightType, Quote, QuoteType
)
from src.core.exceptions import ParsingError


class TestParseResult:
    """Test ParseResult dataclass."""
    
    def test_parse_result_creation(self):
        """Test creating ParseResult instances."""
        # Basic creation
        result = ParseResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.errors == []
        assert result.warnings == []
        
        # With errors and warnings
        result = ParseResult(
            success=False,
            data=None,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"]
        )
        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
    
    def test_parse_result_post_init(self):
        """Test post_init initialization of lists."""
        # Without specifying errors/warnings
        result = ParseResult(success=True, data=[])
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


class TestResponseParser:
    """Test ResponseParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create ResponseParser instance."""
        return ResponseParser(strict_mode=False)
    
    @pytest.fixture
    def strict_parser(self):
        """Create ResponseParser in strict mode."""
        return ResponseParser(strict_mode=True)
    
    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = ResponseParser(strict_mode=True)
        assert parser.strict_mode is True
        
        parser = ResponseParser()
        assert parser.strict_mode is False
    
    def test_parse_json_response_valid(self, parser):
        """Test parsing valid JSON responses."""
        # Direct JSON array
        response = '[{"name": "Test", "value": 1}]'
        result = parser.parse_json_response(response, list)
        assert result.success is True
        assert result.data == [{"name": "Test", "value": 1}]
        assert len(result.errors) == 0
        
        # JSON in markdown code block
        response = """
        Here's the result:
        ```json
        [{"id": 1, "status": "active"}]
        ```
        """
        result = parser.parse_json_response(response, list)
        assert result.success is True
        assert result.data == [{"id": 1, "status": "active"}]
        
        # Direct JSON object
        response = '{"single": "object"}'
        result = parser.parse_json_response(response, dict)
        assert result.success is True
        assert result.data == {"single": "object"}
    
    def test_parse_json_response_type_conversion(self, parser):
        """Test automatic type conversion."""
        # Single dict to list conversion
        response = '{"name": "Single Item"}'
        result = parser.parse_json_response(response, list)
        assert result.success is True
        assert result.data == [{"name": "Single Item"}]
        assert "Converted single object to list" in result.warnings
        
        # Wrong type without conversion
        response = '[1, 2, 3]'
        result = parser.parse_json_response(response, dict)
        assert result.success is False
        assert "Expected dict, got list" in result.errors[0]
    
    def test_parse_json_response_no_json(self, parser):
        """Test handling responses with no JSON."""
        response = "This is just plain text with no JSON"
        result = parser.parse_json_response(response)
        assert result.success is False
        assert "No valid JSON found in response" in result.errors[0]
    
    def test_parse_json_response_malformed(self, parser):
        """Test handling malformed JSON."""
        # Missing closing bracket
        response = '[{"name": "Test"'
        result = parser.parse_json_response(response)
        assert result.success is False
        assert "JSON decode error" in result.errors[0]
        
        # With common errors that can be fixed
        response = "{'name': 'Test', 'value': True,}"  # Single quotes and trailing comma
        result = parser.parse_json_response(response, dict)
        assert result.success is True
        assert result.data == {"name": "Test", "value": True}
        assert "Fixed JSON formatting issues" in result.warnings
    
    def test_extract_json_string(self, parser):
        """Test JSON string extraction from various formats."""
        # Test with markdown code blocks
        response = """
        Some text before
        ```json
        {"key": "value"}
        ```
        Some text after
        """
        json_str = parser._extract_json_string(response)
        assert json_str == '{"key": "value"}'
        
        # Test with array
        response = 'The result is [1, 2, 3] as expected'
        json_str = parser._extract_json_string(response)
        assert json_str == '[1, 2, 3]'
        
        # Test with nested structures
        response = '{"outer": {"inner": [1, 2, 3]}}'
        json_str = parser._extract_json_string(response)
        assert json_str == '{"outer": {"inner": [1, 2, 3]}}'
        
        # Test with no JSON
        response = 'No JSON here at all'
        json_str = parser._extract_json_string(response)
        assert json_str is None
    
    def test_fix_common_json_errors(self, parser):
        """Test fixing common JSON formatting errors."""
        # Trailing commas
        json_str = '{"a": 1, "b": 2,}'
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"a": 1, "b": 2}'
        
        json_str = '[1, 2, 3,]'
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '[1, 2, 3]'
        
        # Single quotes
        json_str = "{'name': 'value'}"
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"name": "value"}'
        
        # Unquoted keys
        json_str = '{name: "value", age: 30}'
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"name": "value", "age": 30}'
        
        # Python literals
        json_str = '{"value": None, "active": True, "disabled": False}'
        fixed = parser._fix_common_json_errors(json_str)
        assert fixed == '{"value": null, "active": true, "disabled": false}'
    
    def test_parse_entities_success(self, parser):
        """Test successful entity parsing."""
        response = json.dumps([
            {
                "name": "OpenAI",
                "type": "Company",
                "description": "AI research company",
                "frequency": 5,
                "importance": 8
            },
            {
                "name": "GPT-4",
                "type": "Technology",
                "description": "Language model",
                "frequency": 10,
                "importance": 9
            }
        ])
        
        # Debug the response
        print(f"Response type: {type(response)}")
        print(f"Response: {response[:100]}...")
        
        result = parser.parse_entities(response)
        assert result.success is True
        assert len(result.data) == 2
        
        # Check first entity
        entity1 = result.data[0]
        assert isinstance(entity1, Entity)
        assert entity1.name == "OpenAI"
        assert entity1.entity_type == EntityType.ORGANIZATION
        assert entity1.description == "AI research company"
        assert entity1.mention_count == 5
        assert entity1.bridge_score == 0.8
        
        # Check second entity
        entity2 = result.data[1]
        assert entity2.name == "GPT-4"
        assert entity2.entity_type == EntityType.CONCEPT
        assert entity2.mention_count == 10
    
    def test_parse_entities_missing_fields(self, parser):
        """Test parsing entities with missing fields."""
        response = json.dumps([
            {"name": "Valid Entity", "type": "Person"},
            {"type": "Technology"},  # Missing name
            {"name": "Another Valid"}  # Missing type, should default
        ])
        
        result = parser.parse_entities(response)
        assert result.success is True
        assert len(result.data) == 2  # Only valid entities
        assert len(result.warnings) == 1  # Warning about failed entity
        
        assert result.data[0].name == "Valid Entity"
        assert result.data[1].name == "Another Valid"
        assert result.data[1].entity_type == EntityType.OTHER  # Default type
    
    def test_parse_entities_strict_mode(self, strict_parser):
        """Test entity parsing in strict mode."""
        response = json.dumps([
            {"name": "Valid"},
            {"invalid": "entry"}  # Will cause error
        ])
        
        result = strict_parser.parse_entities(response)
        assert result.success is False
        assert len(result.errors) > 0
        assert "Failed to parse entity" in result.errors[0]
    
    def test_parse_insights_success(self, parser):
        """Test successful insight parsing."""
        response = json.dumps([
            {
                "content": "AI is transforming industries",
                "type": "conceptual",
                "confidence": 0.9,
                "evidence": "Multiple examples"
            },
            {
                "content": "Invest in AI education",
                "type": "recommendation",
                "confidence": 0.85
            }
        ])
        
        result = parser.parse_insights(response)
        assert result.success is True
        assert len(result.data) == 2
        
        # Check insights
        insight1 = result.data[0]
        assert isinstance(insight1, Insight)
        assert insight1.description == "AI is transforming industries"
        assert insight1.insight_type == InsightType.CONCEPTUAL
        assert insight1.confidence_score == 0.9
        
        insight2 = result.data[1]
        assert insight2.insight_type == InsightType.RECOMMENDATION
        assert insight2.confidence_score == 0.85
    
    def test_parse_quotes_success(self, parser):
        """Test successful quote parsing."""
        response = json.dumps([
            {
                "text": "The future is already here",
                "speaker": "William Gibson",
                "type": "memorable",
                "context": "On technology adoption"
            },
            {
                "text": "Move fast and break things",
                "speaker": "Mark Zuckerberg",
                "type": "controversial"
            }
        ])
        
        result = parser.parse_quotes(response)
        assert result.success is True
        assert len(result.data) == 2
        
        # Check quotes
        quote1 = result.data[0]
        assert isinstance(quote1, Quote)
        assert quote1.text == "The future is already here"
        assert quote1.speaker == "William Gibson"
        assert quote1.quote_type == QuoteType.MEMORABLE
        assert quote1.context == "On technology adoption"
        
        quote2 = result.data[1]
        assert quote2.quote_type == QuoteType.CONTROVERSIAL
    
    def test_parse_complexity_success(self, parser):
        """Test successful complexity parsing."""
        response = json.dumps({
            "classification": "TECHNICAL",
            "technical_density": 0.8,
            "concepts": ["AI", "ML", "Neural Networks"],
            "explanation": "High technical content"
        })
        
        result = parser.parse_complexity(response)
        assert result.success is True
        assert result.data['classification'] == 'technical'  # Normalized to lowercase
        assert result.data['technical_density'] == 0.8
        assert 'concepts' in result.data
    
    def test_parse_complexity_validation(self, parser):
        """Test complexity parsing with validation."""
        # Missing required fields
        response = json.dumps({"technical_density": 0.5})
        result = parser.parse_complexity(response)
        assert result.success is False
        assert "Missing required fields: ['classification']" in result.errors[0]
        
        # Out of range values
        response = json.dumps({
            "classification": "TECHNICAL",
            "technical_density": 1.5  # Out of range
        })
        result = parser.parse_complexity(response)
        assert result.success is True
        assert result.data['technical_density'] == 1.0  # Clamped
        assert "outside 0-1 range" in result.warnings[0]
    
    def test_parse_information_density_success(self, parser):
        """Test successful information density parsing."""
        response = json.dumps({
            "density": 0.75,
            "concept_count": 15,
            "explanation": "Dense technical discussion"
        })
        
        result = parser.parse_information_density(response)
        assert result.success is True
        assert result.data['density'] == 0.75
        assert result.data['concept_count'] == 15
        assert result.data['explanation'] == "Dense technical discussion"
    
    def test_parse_information_density_defaults(self, parser):
        """Test information density parsing with defaults."""
        response = json.dumps({"density": 0.5})
        
        result = parser.parse_information_density(response)
        assert result.success is True
        assert result.data['density'] == 0.5
        assert result.data['concept_count'] == 0  # Default
        assert result.data['explanation'] == ''  # Default
    
    def test_parse_sentiment_success(self, parser):
        """Test successful sentiment parsing."""
        response = json.dumps({
            "overall_sentiment": "POSITIVE",
            "score": 0.8,
            "emotions": ["excitement", "optimism"],
            "explanation": "Speaker is enthusiastic about the topic"
        })
        
        result = parser.parse_sentiment(response)
        assert result.success is True
        assert result.data['overall_sentiment'] == 'positive'  # Normalized
        assert result.data['score'] == 0.8
        assert 'excitement' in result.data['emotions']
    
    def test_parse_sentiment_validation(self, parser):
        """Test sentiment parsing with validation."""
        # Out of range score
        response = json.dumps({
            "overall_sentiment": "negative",
            "score": -1.5  # Out of range
        })
        
        result = parser.parse_sentiment(response)
        assert result.success is True
        assert result.data['score'] == -1.0  # Clamped
        assert "outside -1 to 1 range" in result.warnings[0]
    
    def test_entity_type_mapping(self, parser):
        """Test entity type string to enum mapping."""
        test_cases = [
            ("person", EntityType.PERSON),
            ("Person", EntityType.PERSON),  # Case insensitive
            ("company", EntityType.ORGANIZATION),
            ("organization", EntityType.ORGANIZATION),
            ("institution", EntityType.ORGANIZATION),
            ("product", EntityType.PRODUCT),
            ("technology", EntityType.CONCEPT),
            ("concept", EntityType.CONCEPT),
            ("location", EntityType.LOCATION),
            ("event", EntityType.EVENT),
            ("unknown", EntityType.OTHER),  # Default
            ("", EntityType.OTHER)  # Empty default
        ]
        
        for type_str, expected in test_cases:
            result = parser._map_entity_type(type_str)
            assert result == expected
    
    def test_insight_type_mapping(self, parser):
        """Test insight type string to enum mapping."""
        test_cases = [
            ("factual", InsightType.FACTUAL),
            ("conceptual", InsightType.CONCEPTUAL),
            ("prediction", InsightType.PREDICTION),
            ("recommendation", InsightType.RECOMMENDATION),
            ("key_point", InsightType.KEY_POINT),
            ("technical", InsightType.TECHNICAL),
            ("methodological", InsightType.METHODOLOGICAL),
            ("unknown", InsightType.FACTUAL),  # Default
        ]
        
        for type_str, expected in test_cases:
            result = parser._map_insight_type(type_str)
            assert result == expected
    
    def test_quote_type_mapping(self, parser):
        """Test quote type string to enum mapping."""
        test_cases = [
            ("memorable", QuoteType.MEMORABLE),
            ("controversial", QuoteType.CONTROVERSIAL),
            ("humorous", QuoteType.HUMOROUS),
            ("insightful", QuoteType.INSIGHTFUL),
            ("technical", QuoteType.TECHNICAL),
            ("general", QuoteType.OTHER),
            ("unknown", QuoteType.OTHER),  # Default
        ]
        
        for type_str, expected in test_cases:
            result = parser._map_quote_type(type_str)
            assert result == expected


# TestValidationUtils removed - ValidationUtils class doesn't exist in parsers.py


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def parser(self):
        """Create parser for edge case testing."""
        return ResponseParser()
    
    def test_empty_responses(self, parser):
        """Test parsing empty responses."""
        test_cases = [
            "",
            "   ",
            "\n\n\n",
            "```json\n```",  # Empty code block
        ]
        
        for response in test_cases:
            result = parser.parse_json_response(response)
            assert result.success is False
            assert len(result.errors) > 0
    
    def test_nested_json_extraction(self, parser):
        """Test extraction of deeply nested JSON."""
        response = """
        The analysis shows:
        {
            "level1": {
                "level2": {
                    "level3": {
                        "data": [1, 2, 3]
                    }
                }
            }
        }
        """
        
        result = parser.parse_json_response(response, dict)
        assert result.success is True
        assert result.data["level1"]["level2"]["level3"]["data"] == [1, 2, 3]
    
    def test_multiple_json_blocks(self, parser):
        """Test response with multiple JSON blocks."""
        response = """
        First result: {"id": 1}
        Second result: {"id": 2}
        Main result: [{"id": 3}, {"id": 4}]
        """
        
        # Should extract the first complete JSON structure (object in this case)
        result = parser.parse_json_response(response, dict)
        assert result.success is True
        assert result.data == {"id": 1}
        
        # For array, should find the array
        result = parser.parse_json_response(response, list)
        assert result.success is True
        assert result.data == [{"id": 3}, {"id": 4}]
    
    def test_unicode_handling(self, parser):
        """Test parsing responses with unicode."""
        response = json.dumps({
            "name": "测试",  # Chinese
            "description": "Тест",  # Russian
            "emoji": "🚀🎉",
            "mixed": "Test 日本語 test"
        })
        
        result = parser.parse_json_response(response, dict)
        assert result.success is True
        assert result.data["name"] == "测试"
        assert result.data["emoji"] == "🚀🎉"
    
    def test_large_response_handling(self, parser):
        """Test parsing very large responses."""
        # Create a large response
        large_data = [{"id": i, "data": "x" * 1000} for i in range(100)]
        response = json.dumps(large_data)
        
        result = parser.parse_json_response(response, list)
        assert result.success is True
        assert len(result.data) == 100
    
    def test_parse_entity_edge_cases(self, parser):
        """Test entity parsing edge cases."""
        # Entity with all optional fields
        response = json.dumps([{
            "name": "Minimal Entity"
            # No type, description, etc.
        }])
        
        result = parser.parse_entities(response)
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0].type == EntityType.OTHER.value  # Default
        assert result.data[0].mention_count == 1  # Default
        
        # Entity with very high importance
        response = json.dumps([{
            "name": "Important",
            "importance": 15  # Over 10
        }])
        
        result = parser.parse_entities(response)
        assert result.success is True
        # Should handle gracefully (15/10 = 1.5, clamped to 1.0)
        assert result.data[0].bridge_score <= 1.0
    
    def test_concurrent_parsing(self, parser):
        """Test thread safety of parser."""
        import threading
        
        results = []
        errors = []
        
        def parse_response(response_text):
            try:
                result = parser.parse_json_response(response_text, list)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads parsing different responses
        threads = []
        for i in range(10):
            response = json.dumps([{"thread": i, "data": f"test_{i}"}])
            t = threading.Thread(target=parse_response, args=(response,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r.success for r in results)