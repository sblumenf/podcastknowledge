"""Tests for validation utilities."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.utils.validation import (
    validate_text_input,
    validate_date_format,
    sanitize_file_path,
    DataValidator,
    validate_and_enhance_insights,
    is_valid_url,
    is_valid_email,
)


class TestValidateTextInput:
    """Test validate_text_input function."""
    
    def test_valid_string(self):
        """Test validation of valid string input."""
        assert validate_text_input("Hello World") == "Hello World"
        assert validate_text_input("  Trimmed  ") == "Trimmed"
    
    def test_none_input(self):
        """Test validation of None input."""
        assert validate_text_input(None) == ""
        assert validate_text_input(None, "test_field") == ""
    
    def test_non_string_input(self):
        """Test validation of non-string input."""
        assert validate_text_input(123) == "123"
        assert validate_text_input(True) == "True"
        assert validate_text_input([1, 2, 3]) == "[1, 2, 3]"
    
    def test_empty_string(self):
        """Test validation of empty string."""
        assert validate_text_input("") == ""
        assert validate_text_input("   ") == ""


class TestValidateDateFormat:
    """Test validate_date_format function."""
    
    def test_valid_date_formats(self):
        """Test validation of various date formats."""
        # ISO format
        result = validate_date_format("2024-01-15")
        assert "2024-01-15" in result
        
        # With time
        result = validate_date_format("2024-01-15T10:30:00")
        assert "2024-01-15" in result
        
        # US format
        result = validate_date_format("01/15/2024")
        assert "2024-01-15" in result
    
    def test_empty_date(self):
        """Test validation of empty date."""
        result = validate_date_format("")
        assert datetime.now().year == datetime.fromisoformat(result).year
        
        result = validate_date_format(None)
        assert datetime.now().year == datetime.fromisoformat(result).year
    
    def test_invalid_date(self):
        """Test validation of invalid date."""
        # Should return current date for invalid input
        result = validate_date_format("not a date")
        assert datetime.now().year == datetime.fromisoformat(result).year


class TestSanitizeFilePath:
    """Test sanitize_file_path function."""
    
    def test_safe_path(self):
        """Test sanitization of safe paths."""
        assert sanitize_file_path("data/file.txt") == "data/file.txt"
        assert sanitize_file_path("folder/subfolder/file.py") == "folder/subfolder/file.py"
    
    def test_dangerous_paths(self):
        """Test sanitization of dangerous paths."""
        # Directory traversal
        assert sanitize_file_path("../../etc/passwd") == "etc/passwd"
        assert sanitize_file_path("../../../secret") == "secret"
        
        # Absolute paths
        assert sanitize_file_path("/etc/passwd") == "etc/passwd"
        assert sanitize_file_path("/root/.ssh/id_rsa") == "root/.ssh/id_rsa"
    
    def test_special_characters(self):
        """Test removal of special characters."""
        assert sanitize_file_path("file;rm -rf /") == "filerm -rf "
        assert sanitize_file_path("file|command") == "filecommand"
        assert sanitize_file_path("file&background") == "filebackground"
    
    def test_double_slashes(self):
        """Test normalization of double slashes."""
        assert sanitize_file_path("folder//file.txt") == "folder/file.txt"
        assert sanitize_file_path("path///to////file") == "path/to/file"


class TestDataValidator:
    """Test DataValidator class."""
    
    def setup_method(self):
        """Set up test validator."""
        self.validator = DataValidator(
            max_entities_per_segment=10,
            confidence_threshold=3,
            min_insight_length=20,
            min_quote_length=10
        )
    
    def test_validate_entities_empty(self):
        """Test validation of empty entities list."""
        result = self.validator.validate_entities([])
        assert result == []
    
    def test_validate_entities_basic(self):
        """Test basic entity validation."""
        entities = [
            {"name": "John Doe", "type": "person", "confidence": 5},
            {"name": "OpenAI", "type": "organization", "confidence": 8},
        ]
        
        result = self.validator.validate_entities(entities)
        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[0]["type"] == "PERSON"
        assert "normalized_name" in result[0]
    
    def test_validate_entities_missing_fields(self):
        """Test validation with missing fields."""
        entities = [
            {"name": "Valid Entity", "type": "person"},
            {"name": "Missing Type"},
            {"type": "person"},  # Missing name
            {},  # Missing both
        ]
        
        result = self.validator.validate_entities(entities)
        assert len(result) == 1
        assert result[0]["name"] == "Valid Entity"
    
    def test_validate_entities_duplicates(self):
        """Test deduplication of entities."""
        entities = [
            {"name": "John Doe", "type": "person", "confidence": 5},
            {"name": "john doe", "type": "person", "confidence": 7},  # Duplicate
            {"name": "John Doe", "type": "organization"},  # Different type
        ]
        
        result = self.validator.validate_entities(entities)
        assert len(result) == 2  # One duplicate merged
        
        # Check confidence was merged (max)
        person_entity = next(e for e in result if e["type"] == "PERSON")
        assert person_entity["confidence"] == 7
    
    def test_validate_entities_max_limit(self):
        """Test entity count limiting."""
        # Create more entities than max
        entities = [
            {"name": f"Entity {i}", "type": "person", "importance": i}
            for i in range(20)
        ]
        
        result = self.validator.validate_entities(entities)
        assert len(result) == 10  # Limited to max
        
        # Should keep highest importance
        assert result[0]["name"] == "Entity 19"
        assert result[-1]["name"] == "Entity 10"
    
    def test_validate_insights_empty(self):
        """Test validation of empty insights list."""
        result = self.validator.validate_insights([])
        assert result == []
    
    def test_validate_insights_basic(self):
        """Test basic insight validation."""
        insights = [
            {
                "title": "Key Finding",
                "description": "This is an important finding about the topic discussed.",
                "insight_type": "observation",
                "confidence": 0.9
            }
        ]
        
        result = self.validator.validate_insights(insights)
        assert len(result) == 1
        assert result[0]["title"] == "Key Finding"
        assert result[0]["insight_type"] == "observation"
    
    def test_validate_insights_too_short(self):
        """Test filtering of insights with short descriptions."""
        insights = [
            {
                "title": "Good Insight",
                "description": "This is a sufficiently long description for the insight."
            },
            {
                "title": "Bad Insight",
                "description": "Too short"  # Less than min_insight_length
            }
        ]
        
        result = self.validator.validate_insights(insights)
        assert len(result) == 1
        assert result[0]["title"] == "Good Insight"
    
    def test_validate_insights_duplicates(self):
        """Test deduplication of insights by title."""
        insights = [
            {"title": "Same Title", "description": "First description with enough length"},
            {"title": "same title", "description": "Second description with enough length"},  # Duplicate
            {"title": "Different Title", "description": "Third description with enough length"}
        ]
        
        result = self.validator.validate_insights(insights)
        assert len(result) == 2
        assert any(i["title"] == "Same Title" for i in result)
        assert any(i["title"] == "Different Title" for i in result)
    
    def test_validate_quotes_empty(self):
        """Test validation of empty quotes list."""
        result = self.validator.validate_quotes([])
        assert result == []
    
    def test_validate_quotes_basic(self):
        """Test basic quote validation."""
        quotes = [
            {
                "text": "This is a meaningful quote from the podcast.",
                "speaker": "John Doe",
                "context": "Discussing AI ethics",
                "importance": 8
            }
        ]
        
        result = self.validator.validate_quotes(quotes)
        assert len(result) == 1
        assert result[0]["text"] == "This is a meaningful quote from the podcast."
        assert result[0]["speaker"] == "John Doe"
    
    def test_validate_quotes_too_short(self):
        """Test filtering of short quotes."""
        quotes = [
            {"text": "This is a good quote", "speaker": "Speaker 1"},
            {"text": "Too short", "speaker": "Speaker 2"},  # Less than min_quote_length
        ]
        
        result = self.validator.validate_quotes(quotes)
        assert len(result) == 1
        assert result[0]["speaker"] == "Speaker 1"
    
    def test_validate_quotes_duplicates(self):
        """Test deduplication of quotes."""
        quotes = [
            {"text": "This is the same quote", "speaker": "Speaker 1"},
            {"text": "This is THE SAME quote", "speaker": "Speaker 2"},  # Duplicate (case-insensitive)
            {"text": "This is a different quote", "speaker": "Speaker 3"},
        ]
        
        result = self.validator.validate_quotes(quotes)
        assert len(result) == 2
    
    def test_validate_metrics(self):
        """Test metrics validation."""
        metrics = {
            "complexity_score": 150,  # Over 100
            "information_score": -10,  # Below 0
            "word_count": 1234.5,  # Float that should be int
            "information_density": 1.5,  # Over 1.0
            "entity_count": "invalid",  # Invalid type
        }
        
        result = self.validator.validate_metrics(metrics)
        
        # Scores clamped to 0-100
        assert result["complexity_score"] == 100
        assert result["information_score"] == 0
        
        # Counts converted to int
        assert result["word_count"] == 1234
        assert isinstance(result["word_count"], int)
        
        # Ratios clamped to 0-1
        assert result["information_density"] == 1.0
        
        # Invalid types get default values
        assert result["entity_count"] == 0
    
    def test_get_validation_report(self):
        """Test validation report generation."""
        # Trigger some validation issues
        entities = [
            {"name": "A", "type": "person"},  # Too short
            {"type": "person"},  # Missing name
            {"name": "Valid", "type": "person"},
            {"name": "Valid", "type": "person"},  # Duplicate
        ]
        
        self.validator.validate_entities(entities)
        
        report = self.validator.get_validation_report()
        assert "name_too_short" in report
        assert "missing_fields" in report
        assert "duplicates_merged" in report
        assert report["name_too_short"] == 1
        assert report["missing_fields"] == 1
        assert report["duplicates_merged"] == 1


class TestValidateAndEnhanceInsights:
    """Test validate_and_enhance_insights function."""
    
    @patch('src.utils.validation.logger')
    def test_basic_validation(self, mock_logger):
        """Test basic insight validation and enhancement."""
        insights = [
            {
                "title": "Key Insight",
                "description": "This is a detailed description of the insight found.",
                "insight_type": "observation"
            }
        ]
        
        result = validate_and_enhance_insights(insights)
        assert len(result) == 1
        assert result[0]["title"] == "Key Insight"
        
        # Check logging was called
        assert mock_logger.info.called


class TestUrlEmailValidation:
    """Test URL and email validation functions."""
    
    def test_is_valid_url(self):
        """Test URL validation."""
        # Valid URLs
        assert is_valid_url("http://example.com")
        assert is_valid_url("https://example.com")
        assert is_valid_url("https://sub.example.com/path?query=value")
        assert is_valid_url("http://localhost:8080")
        assert is_valid_url("http://192.168.1.1")
        
        # Invalid URLs
        assert not is_valid_url("not a url")
        assert not is_valid_url("example.com")  # No protocol
        assert not is_valid_url("ftp://example.com")  # Wrong protocol
        assert not is_valid_url("")
        assert not is_valid_url("javascript:alert('xss')")
    
    def test_is_valid_email(self):
        """Test email validation."""
        # Valid emails
        assert is_valid_email("user@example.com")
        assert is_valid_email("user.name@example.com")
        assert is_valid_email("user+tag@example.co.uk")
        assert is_valid_email("user123@sub.example.com")
        
        # Invalid emails
        assert not is_valid_email("not an email")
        assert not is_valid_email("@example.com")
        assert not is_valid_email("user@")
        assert not is_valid_email("user@@example.com")
        assert not is_valid_email("")
        assert not is_valid_email("user space@example.com")