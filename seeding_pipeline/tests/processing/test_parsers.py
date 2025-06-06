"""
Tests for response parsing functionality
"""
import pytest
import json
from typing import List, Dict, Any

from src.core.models import Entity, Insight, Quote, EntityType, InsightType, QuoteType
from src.processing.parsers import ResponseParser, ParseResult, ValidationUtils


class TestResponseParser:
    """Test suite for ResponseParser class"""
    
    @pytest.fixture
    def parser(self):
        """Create a ResponseParser instance"""
        return ResponseParser()
    
    @pytest.fixture
    def validation_utils(self):
        """Create ValidationUtils instance"""
        return ValidationUtils()
    
    def test_parse_json_response_valid(self, parser):
        """Test parsing valid JSON response"""
        response = """
        Here are the results:
        ```json
        [
            {"name": "AI", "type": "TECHNOLOGY"},
            {"name": "Google", "type": "COMPANY"}
        ]
        ```
        """
        
        result = parser.parse_json_response(response)
        
        assert result.success
        assert isinstance(result.data, list)
        assert len(result.data) == 2
        assert result.data[0]["name"] == "AI"
        assert result.error is None
    
    def test_parse_json_response_no_markers(self, parser):
        """Test parsing JSON without code block markers"""
        response = '[{"name": "Test", "type": "CONCEPT"}]'
        
        result = parser.parse_json_response(response)
        
        assert result.success
        assert isinstance(result.data, list)
        assert len(result.data) == 1
    
    def test_parse_json_response_with_text(self, parser):
        """Test parsing JSON embedded in text"""
        response = """
        I found the following entities:
        {"entities": [{"name": "Python", "type": "TECHNOLOGY"}]}
        That's all I could find.
        """
        
        result = parser.parse_json_response(response, expected_type=dict)
        
        assert result.success
        assert isinstance(result.data, dict)
        assert "entities" in result.data
    
    def test_parse_json_response_malformed(self, parser):
        """Test parsing malformed JSON"""
        response = '{"name": "Test", "type": "CONCEPT"'  # Missing closing brace
        
        result = parser.parse_json_response(response)
        
        assert not result.success
        assert result.data is None
        assert "Failed to parse JSON" in result.error
    
    def test_parse_entities_structured(self, parser):
        """Test parsing entities from structured response"""
        response = """
        Entities found:
        1. **Apple Inc.** - Type: COMPANY - Technology company
        2. **Tim Cook** - Type: PERSON - CEO of Apple
        3. **iPhone** - Type: PRODUCT - Smartphone by Apple
        """
        
        entities = parser.parse_entities(response)
        
        assert len(entities) == 3
        assert entities[0].name == "Apple Inc."
        assert entities[0].entity_type == EntityType.ORGANIZATION
        assert entities[1].name == "Tim Cook"
        assert entities[1].entity_type == EntityType.PERSON
        assert entities[2].name == "iPhone"
        assert entities[2].entity_type == EntityType.PRODUCT
    
    def test_parse_entities_json(self, parser):
        """Test parsing entities from JSON response"""
        response = """
        ```json
        [
            {
                "name": "Machine Learning",
                "type": "TECHNOLOGY",
                "description": "AI subset",
                "frequency": 5
            }
        ]
        ```
        """
        
        entities = parser.parse_entities(response)
        
        assert len(entities) == 1
        assert entities[0].name == "Machine Learning"
        assert entities[0].entity_type == EntityType.TECHNOLOGY
        assert entities[0].description == "AI subset"
    
    def test_parse_insights_structured(self, parser):
        """Test parsing insights from structured response"""
        response = """
        Key Insights:
        1. **AI is transforming industries** - Revolutionary impact on business
        2. **Ethics are crucial** - Need for responsible AI development
        3. **Future is automated** - Prediction about workplace changes
        """
        
        insights = parser.parse_insights(response)
        
        assert len(insights) == 3
        assert "AI is transforming industries" in insights[0].content
        assert insights[0].type in [InsightType.TREND, InsightType.OBSERVATION]
        assert all(i.confidence > 0 for i in insights)
    
    def test_parse_quotes_structured(self, parser):
        """Test parsing quotes from structured response"""
        response = """
        Notable Quotes:
        
        "AI will change everything" - Dr. Smith
        Context: Opening statement
        Type: PREDICTION
        
        "We must be careful with AI development" - Dr. Smith
        Context: Discussing ethics
        Type: WARNING
        """
        
        quotes = parser.parse_quotes(response)
        
        assert len(quotes) == 2
        assert quotes[0].text == "AI will change everything"
        assert quotes[0].speaker == "Dr. Smith"
        assert quotes[0].type == QuoteType.PREDICTION
        assert quotes[1].type == QuoteType.WARNING
    
    def test_parse_topics_simple(self, parser):
        """Test parsing topics from simple list"""
        response = """
        Main topics discussed:
        1. Artificial Intelligence - Core discussion about AI
        2. Healthcare Applications - How AI is used in medicine
        3. Ethical Considerations - Concerns about AI ethics
        """
        
        topics = parser.parse_topics(response)
        
        assert len(topics) == 3
        assert topics[0]["name"] == "Artificial Intelligence"
        assert "Core discussion" in topics[0]["description"]
        assert all("name" in t and "description" in t for t in topics)
    
    def test_extract_json_from_text(self, parser):
        """Test JSON extraction from various text formats"""
        # Test with markdown code block
        text1 = """```json
        {"key": "value"}
        ```"""
        json_str = parser._extract_json_from_text(text1)
        assert json_str == '{"key": "value"}'
        
        # Test with plain JSON
        text2 = '{"key": "value"}'
        json_str = parser._extract_json_from_text(text2)
        assert json_str == '{"key": "value"}'
        
        # Test with JSON in text
        text3 = 'The result is {"key": "value"} as shown'
        json_str = parser._extract_json_from_text(text3)
        assert json_str == '{"key": "value"}'
    
    def test_clean_entity_type(self, parser):
        """Test entity type cleaning"""
        assert parser._clean_entity_type("company") == "ORGANIZATION"
        assert parser._clean_entity_type("COMPANY") == "ORGANIZATION"
        assert parser._clean_entity_type("person") == "PERSON"
        assert parser._clean_entity_type("tech") == "TECHNOLOGY"
        assert parser._clean_entity_type("unknown") == "CONCEPT"
    
    def test_parse_confidence_score(self, parser):
        """Test confidence score parsing"""
        assert parser._parse_confidence_score("high") == 0.9
        assert parser._parse_confidence_score("medium") == 0.7
        assert parser._parse_confidence_score("low") == 0.5
        assert parser._parse_confidence_score("0.85") == 0.85
        assert parser._parse_confidence_score("invalid") == 0.7  # default


class TestValidationUtils:
    """Test suite for ValidationUtils class"""
    
    @pytest.fixture
    def validator(self):
        """Create ValidationUtils instance"""
        return ValidationUtils()
    
    def test_validate_entity(self, validator):
        """Test entity validation"""
        valid_entity = Entity(
            name="Test Entity",
            type=EntityType.CONCEPT,
            confidence=0.8
        )
        
        assert validator.validate_entity(valid_entity)
        
        # Test invalid entity (no name)
        invalid_entity = Entity(
            name="",
            type=EntityType.CONCEPT,
            confidence=0.8
        )
        
        assert not validator.validate_entity(invalid_entity)
    
    def test_validate_insight(self, validator):
        """Test insight validation"""
        valid_insight = Insight(
            content="This is a valid insight",
            type=InsightType.OBSERVATION,
            confidence=0.7
        )
        
        assert validator.validate_insight(valid_insight)
        
        # Test invalid insight (too short)
        invalid_insight = Insight(
            content="Too short",
            type=InsightType.OBSERVATION,
            confidence=0.7
        )
        
        assert not validator.validate_insight(invalid_insight)
    
    def test_validate_quote(self, validator):
        """Test quote validation"""
        valid_quote = Quote(
            text="This is a valid quote",
            speaker="Speaker",
            timestamp="00:01:30",
            context="Discussion context",
            type=QuoteType.STATEMENT
        )
        
        assert validator.validate_quote(valid_quote)
        
        # Test invalid quote (no speaker)
        invalid_quote = Quote(
            text="Quote without speaker",
            speaker="",
            timestamp="00:01:30",
            context="Context",
            type=QuoteType.STATEMENT
        )
        
        assert not validator.validate_quote(invalid_quote)
    
    def test_clean_text(self, validator):
        """Test text cleaning"""
        # Test whitespace cleaning
        assert validator.clean_text("  Hello   World  ") == "Hello World"
        
        # Test special character handling
        assert validator.clean_text("Hello\nWorld") == "Hello World"
        assert validator.clean_text("Hello\tWorld") == "Hello World"
        
        # Test multiple spaces
        assert validator.clean_text("Hello     World") == "Hello World"
    
    def test_normalize_confidence(self, validator):
        """Test confidence normalization"""
        assert validator.normalize_confidence(0.5) == 0.5
        assert validator.normalize_confidence(1.5) == 1.0
        assert validator.normalize_confidence(-0.1) == 0.0
        assert validator.normalize_confidence(None) == 0.7  # default


class TestParserEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture
    def parser(self):
        return ResponseParser()
    
    def test_empty_response(self, parser):
        """Test parsing empty responses"""
        assert parser.parse_entities("") == []
        assert parser.parse_insights("") == []
        assert parser.parse_quotes("") == []
        assert parser.parse_topics("") == []
    
    def test_none_response(self, parser):
        """Test parsing None responses"""
        assert parser.parse_entities(None) == []
        assert parser.parse_insights(None) == []
        assert parser.parse_quotes(None) == []
        assert parser.parse_topics(None) == []
    
    def test_mixed_format_response(self, parser):
        """Test parsing responses with mixed formats"""
        response = """
        Here are some entities in different formats:
        
        1. **JSON Format**:
        ```json
        [{"name": "AI", "type": "TECHNOLOGY"}]
        ```
        
        2. **Text Format**:
        - Machine Learning - Type: TECHNOLOGY - ML subset
        
        3. **Numbered List**:
        1. Python - TECHNOLOGY - Programming language
        """
        
        entities = parser.parse_entities(response)
        
        # Should parse at least some entities
        assert len(entities) > 0
        entity_names = [e.name for e in entities]
        assert any(name in entity_names for name in ["AI", "Machine Learning", "Python"])
    
    def test_unicode_handling(self, parser):
        """Test parsing responses with unicode characters"""
        response = """
        Entities:
        1. **Café** - Type: LOCATION - French café
        2. **北京** - Type: LOCATION - Beijing
        3. **α-beta** - Type: CONCEPT - Greek letters
        """
        
        entities = parser.parse_entities(response)
        
        assert len(entities) == 3
        assert any(e.name == "Café" for e in entities)
        assert any(e.name == "北京" for e in entities)
    
    def test_large_response(self, parser):
        """Test parsing very large responses"""
        # Create a large response with many entities
        large_response = "Entities found:\n"
        for i in range(100):
            large_response += f"{i+1}. **Entity{i}** - Type: CONCEPT - Description {i}\n"
        
        entities = parser.parse_entities(large_response)
        
        # Should handle large responses
        assert len(entities) > 50  # May not parse all 100 due to limits
        assert all(isinstance(e, Entity) for e in entities)
    
    def test_malformed_structured_response(self, parser):
        """Test parsing malformed structured responses"""
        response = """
        Entities:
        1. Missing type information here
        2. **Valid Entity** - Type: CONCEPT - Good description
        3. - Type: TECHNOLOGY - Missing name
        4. **Another Valid** - Type: PERSON - OK
        """
        
        entities = parser.parse_entities(response)
        
        # Should only parse valid entities
        assert len(entities) >= 2
        valid_names = [e.name for e in entities]
        assert "Valid Entity" in valid_names
        assert "Another Valid" in valid_names