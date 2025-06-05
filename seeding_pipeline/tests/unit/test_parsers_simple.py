"""Unit tests for response parsing utilities - testing actual implementation."""

import json
import pytest
from unittest.mock import Mock, patch

from src.extraction.parsers import (
    ParseResult,
    ResponseParser
)


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