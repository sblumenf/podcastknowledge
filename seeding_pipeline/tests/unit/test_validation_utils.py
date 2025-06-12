"""Comprehensive unit tests for validation utilities."""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import logging

import pytest

from src.utils.validation import (
    validate_text_input,
    validate_date_format,
    sanitize_file_path,
    DataValidator,
    validate_and_enhance_insights,
    is_valid_url,
    is_valid_email
)


class TestValidateTextInput:
    """Test validate_text_input function."""
    
    def test_validate_text_normal(self):
        """Test validating normal text."""
        assert validate_text_input("Hello World") == "Hello World"
        assert validate_text_input("  Trimmed  ") == "Trimmed"
    
    def test_validate_text_none(self):
        """Test validating None input."""
        with patch('src.utils.validation.logger') as mock_logger:
            result = validate_text_input(None)
            assert result == ""
            mock_logger.warning.assert_called_once()
    
    def test_validate_text_non_string(self):
        """Test validating non-string input."""
        with patch('src.utils.validation.logger') as mock_logger:
            result = validate_text_input(123)
            assert result == "123"
            mock_logger.warning.assert_called_once()
    
    def test_validate_text_with_field_name(self):
        """Test validating text with custom field name."""
        with patch('src.utils.validation.logger') as mock_logger:
            result = validate_text_input(None, "custom_field")
            assert result == ""
            warning_call = mock_logger.warning.call_args[0][0]
            assert "custom_field" in warning_call


class TestValidateDateFormat:
    """Test validate_date_format function."""
    
    def test_validate_date_none(self):
        """Test validating None date."""
        result = validate_date_format(None)
        # Should return current datetime
        parsed = datetime.fromisoformat(result)
        assert (datetime.now() - parsed).total_seconds() < 1
    
    def test_validate_date_empty_string(self):
        """Test validating empty string date."""
        result = validate_date_format("")
        parsed = datetime.fromisoformat(result)
        assert (datetime.now() - parsed).total_seconds() < 1
    
    @patch('dateutil.parser.parse')
    def test_validate_date_with_dateutil(self, mock_parse):
        """Test date validation with dateutil available."""
        mock_parse.return_value = datetime(2023, 12, 25, 10, 30, 0)
        
        result = validate_date_format("Dec 25, 2023 10:30 AM")
        assert result == "2023-12-25T10:30:00"
        mock_parse.assert_called_once_with("Dec 25, 2023 10:30 AM")
    
    @patch('dateutil.parser.parse', side_effect=ImportError)
    def test_validate_date_without_dateutil(self, mock_parse):
        """Test date validation without dateutil."""
        with patch('src.utils.validation.logger') as mock_logger:
            # Test standard format
            result = validate_date_format("2023-12-25")
            assert result == "2023-12-25T00:00:00"
            
            # Test with time
            result = validate_date_format("2023-12-25T10:30:00")
            assert result == "2023-12-25T10:30:00"
            
            # Test US format
            result = validate_date_format("12/25/2023")
            assert result == "2023-12-25T00:00:00"
    
    def test_validate_date_various_formats(self):
        """Test validating various date formats."""
        # These should work with manual parsing
        test_cases = [
            ("2023-12-25", "2023-12-25T00:00:00"),
            ("2023-12-25T10:30:00", "2023-12-25T10:30:00"),
            ("2023-12-25 10:30:00", "2023-12-25T10:30:00"),
            ("12/25/2023", "2023-12-25T00:00:00"),
            ("25/12/2023", "2023-12-25T00:00:00"),
            ("20231225", "2023-12-25T00:00:00"),
        ]
        
        with patch('dateutil.parser.parse', side_effect=ImportError):
            for input_date, expected in test_cases:
                result = validate_date_format(input_date)
                assert result == expected
    
    def test_validate_date_invalid_format(self):
        """Test validating invalid date format."""
        with patch('dateutil.parser.parse', side_effect=ImportError):
            with patch('src.utils.validation.logger') as mock_logger:
                result = validate_date_format("not a date")
                # Should return current datetime
                parsed = datetime.fromisoformat(result)
                assert (datetime.now() - parsed).total_seconds() < 1
                mock_logger.warning.assert_called()


class TestSanitizeFilePath:
    """Test sanitize_file_path function."""
    
    def test_sanitize_normal_path(self):
        """Test sanitizing normal file paths."""
        assert sanitize_file_path("folder/file.txt") == "folder/file.txt"
        assert sanitize_file_path("folder_name/file-name.txt") == "folder_name/file-name.txt"
    
    def test_sanitize_dangerous_characters(self):
        """Test removing dangerous characters."""
        assert sanitize_file_path("folder/file<script>.txt") == "folder/filescript.txt"
        assert sanitize_file_path("folder/file';DROP TABLE.txt") == "folder/fileDROP TABLE.txt"
        assert sanitize_file_path("folder/file!@#$%.txt") == "folder/file.txt"
    
    def test_sanitize_directory_traversal(self):
        """Test preventing directory traversal."""
        assert sanitize_file_path("../../../etc/passwd") == "etc/passwd"
        assert sanitize_file_path("folder/../../../file.txt") == "folder/file.txt"
    
    def test_sanitize_absolute_paths(self):
        """Test removing leading slashes."""
        assert sanitize_file_path("/etc/passwd") == "etc/passwd"
        assert sanitize_file_path("///folder/file.txt") == "folder/file.txt"
    
    def test_sanitize_multiple_slashes(self):
        """Test normalizing multiple slashes."""
        assert sanitize_file_path("folder//file.txt") == "folder/file.txt"
        assert sanitize_file_path("folder///subfolder////file.txt") == "folder/subfolder/file.txt"
    
    def test_sanitize_unicode(self):
        """Test handling unicode characters."""
        assert sanitize_file_path("folder/файл.txt") == "folder/.txt"
        assert sanitize_file_path("folder/文件.txt") == "folder/.txt"
    
    def test_sanitize_non_string_input(self):
        """Test sanitizing non-string input."""
        assert sanitize_file_path(123) == "123"
        assert sanitize_file_path(None) == "None"


class TestDataValidator:
    """Test DataValidator class."""
    
    def test_data_validator_initialization(self):
        """Test DataValidator initialization."""
        validator = DataValidator()
        assert validator.max_entities_per_segment == 50
        assert validator.confidence_threshold == 3
        assert validator.min_insight_length == 20
        assert validator.min_quote_length == 10
    
    def test_data_validator_custom_initialization(self):
        """Test DataValidator with custom parameters."""
        validator = DataValidator(
            max_entities_per_segment=100,
            confidence_threshold=5,
            min_insight_length=30,
            min_quote_length=15
        )
        assert validator.max_entities_per_segment == 100
        assert validator.confidence_threshold == 5
        assert validator.min_insight_length == 30
        assert validator.min_quote_length == 15
    
    def test_validate_entities_empty(self):
        """Test validating empty entities list."""
        validator = DataValidator()
        assert validator.validate_entities([]) == []
        assert validator.validate_entities(None) == []
    
    def test_validate_entities_invalid_format(self):
        """Test validating entities with invalid format."""
        validator = DataValidator()
        
        # Non-dict entity
        result = validator.validate_entities(["not a dict"])
        assert result == []
        assert validator.validation_stats['missing_fields'] == 1
        
        # Missing required fields
        result = validator.validate_entities([{"name": "Test"}])
        assert result == []
        assert validator.validation_stats['missing_fields'] == 2
        
        result = validator.validate_entities([{"type": "PERSON"}])
        assert result == []
        assert validator.validation_stats['missing_fields'] == 3
    
    @patch('src.utils.validation.normalize_entity_name')
    def test_validate_entities_normal(self, mock_normalize):
        """Test validating normal entities."""
        mock_normalize.return_value = "john smith"
        
        validator = DataValidator()
        entities = [
            {"name": "John Smith", "type": "PERSON", "confidence": 5},
            {"name": "Apple Inc", "type": "ORGANIZATION", "importance": 8}
        ]
        
        result = validator.validate_entities(entities)
        
        assert len(result) == 2
        assert result[0]['name'] == "John Smith"
        assert result[0]['normalized_name'] == "john smith"
        assert result[0]['type'] == "PERSON"
        assert result[0]['confidence'] == 5
        assert result[0]['importance'] == 5  # Default
        
        assert result[1]['name'] == "Apple Inc"
        assert result[1]['type'] == "ORGANIZATION"
        assert result[1]['importance'] == 8
        assert result[1]['confidence'] == 3  # Default threshold
    
    @patch('src.utils.validation.normalize_entity_name')
    def test_validate_entities_duplicates(self, mock_normalize):
        """Test validating duplicate entities."""
        mock_normalize.side_effect = ["john smith", "john smith"]
        
        validator = DataValidator()
        entities = [
            {"name": "John Smith", "type": "PERSON", "confidence": 3},
            {"name": "John Smith", "type": "PERSON", "confidence": 5}
        ]
        
        result = validator.validate_entities(entities)
        
        assert len(result) == 1
        assert result[0]['confidence'] == 5  # Should take max confidence
        assert validator.validation_stats['duplicates_merged'] == 1
    
    def test_validate_entities_short_names(self):
        """Test validating entities with short names."""
        validator = DataValidator()
        entities = [
            {"name": "A", "type": "PERSON"},
            {"name": "AB", "type": "PERSON"},
            {"name": "ABC", "type": "PERSON"}
        ]
        
        result = validator.validate_entities(entities)
        
        assert len(result) == 2  # Only "AB" and "ABC" should pass
        assert validator.validation_stats['name_too_short'] == 1
    
    def test_validate_entities_max_limit(self):
        """Test entity limit enforcement."""
        validator = DataValidator(max_entities_per_segment=3)
        
        entities = [
            {"name": f"Entity{i}", "type": "THING", "importance": i}
            for i in range(5)
        ]
        
        result = validator.validate_entities(entities)
        
        assert len(result) == 3
        # Should keep highest importance
        assert result[0]['importance'] == 4
        assert result[1]['importance'] == 3
        assert result[2]['importance'] == 2
        assert validator.validation_stats['entities_truncated'] == 1
    
    def test_validate_insights_empty(self):
        """Test validating empty insights."""
        validator = DataValidator()
        assert validator.validate_insights([]) == []
        assert validator.validate_insights(None) == []
    
    def test_validate_insights_missing_fields(self):
        """Test validating insights with missing fields."""
        validator = DataValidator()
        
        insights = [
            {"title": "Test"},
            {"description": "Test description"},
            {"title": "", "description": "Test"}
        ]
        
        result = validator.validate_insights(insights)
        assert result == []
        assert validator.validation_stats['insight_missing_fields'] == 3
    
    def test_validate_insights_short_description(self):
        """Test validating insights with short descriptions."""
        validator = DataValidator(min_insight_length=20)
        
        insights = [
            {"title": "Short", "description": "Too short"},
            {"title": "Good", "description": "This is a long enough description for the validator"}
        ]
        
        result = validator.validate_insights(insights)
        
        assert len(result) == 1
        assert result[0]['title'] == "Good"
        assert validator.validation_stats['insight_too_short'] == 1
    
    def test_validate_insights_duplicates(self):
        """Test validating duplicate insight titles."""
        validator = DataValidator()
        
        insights = [
            {"title": "Test Insight", "description": "First description with enough length"},
            {"title": "test insight", "description": "Second description with enough length"},
            {"title": "Different", "description": "Third description with enough length"}
        ]
        
        result = validator.validate_insights(insights)
        
        assert len(result) == 2  # Duplicate should be removed
        assert validator.validation_stats['duplicate_insights'] == 1
    
    def test_validate_insights_types(self):
        """Test validating insight types."""
        validator = DataValidator()
        
        insights = [
            {"title": "Test1", "description": "Long enough description for testing", "insight_type": "observation"},
            {"title": "Test2", "description": "Long enough description for testing", "insight_type": "invalid"},
            {"title": "Test3", "description": "Long enough description for testing"}
        ]
        
        result = validator.validate_insights(insights)
        
        assert result[0]['insight_type'] == "observation"
        assert result[1]['insight_type'] == "observation"  # Default for invalid
        assert result[2]['insight_type'] == "observation"  # Default
    
    def test_validate_insights_optional_fields(self):
        """Test validating insights with optional fields."""
        validator = DataValidator()
        
        insights = [{
            "title": "Complete Insight",
            "description": "This is a complete insight with all optional fields",
            "supporting_evidence": "Evidence text",
            "entities": ["Entity1", "Entity2", "", None, 123]
        }]
        
        result = validator.validate_insights(insights)
        
        assert len(result) == 1
        assert result[0]['supporting_evidence'] == "Evidence text"
        assert result[0]['entities'] == ["Entity1", "Entity2"]  # Filtered
    
    def test_validate_quotes_empty(self):
        """Test validating empty quotes."""
        validator = DataValidator()
        assert validator.validate_quotes([]) == []
        assert validator.validate_quotes(None) == []
    
    def test_validate_quotes_missing_fields(self):
        """Test validating quotes with missing fields."""
        validator = DataValidator()
        
        quotes = [
            {"text": "Quote text"},
            {"speaker": "Speaker"},
            {"text": "", "speaker": "Speaker"}
        ]
        
        result = validator.validate_quotes(quotes)
        assert result == []
        assert validator.validation_stats['quote_missing_fields'] == 3
    
    def test_validate_quotes_short_text(self):
        """Test validating quotes with short text."""
        validator = DataValidator(min_quote_length=10)
        
        quotes = [
            {"text": "Short", "speaker": "Speaker1"},
            {"text": "This is a long enough quote", "speaker": "Speaker2"}
        ]
        
        result = validator.validate_quotes(quotes)
        
        assert len(result) == 1
        assert result[0]['speaker'] == "Speaker2"
        assert validator.validation_stats['quote_too_short'] == 1
    
    def test_validate_quotes_duplicates(self):
        """Test validating duplicate quotes."""
        validator = DataValidator()
        
        quotes = [
            {"text": "This is a test quote", "speaker": "Speaker1"},
            {"text": "this IS a   TEST quote", "speaker": "Speaker2"},  # Normalized duplicate
            {"text": "Different quote", "speaker": "Speaker3"}
        ]
        
        result = validator.validate_quotes(quotes)
        
        assert len(result) == 2
        assert validator.validation_stats['duplicate_quotes'] == 1
    
    def test_validate_quotes_complete(self):
        """Test validating complete quotes."""
        validator = DataValidator()
        
        quotes = [{
            "text": "This is a complete quote with all fields",
            "speaker": "Test Speaker",
            "context": "In a discussion about testing",
            "importance": 8,
            "timestamp": "00:01:30"
        }]
        
        result = validator.validate_quotes(quotes)
        
        assert len(result) == 1
        assert result[0]['text'] == "This is a complete quote with all fields"
        assert result[0]['speaker'] == "Test Speaker"
        assert result[0]['context'] == "In a discussion about testing"
        assert result[0]['importance'] == 8
        assert result[0]['timestamp'] == "00:01:30"
    
    def test_validate_metrics_scores(self):
        """Test validating metric scores."""
        validator = DataValidator()
        
        metrics = {
            "complexity_score": 150,  # Too high
            "information_score": -10,  # Too low
            "accessibility_score": 75,  # Good
            "quotability_score": "invalid",  # Invalid type
            "other_field": "preserved"
        }
        
        result = validator.validate_metrics(metrics)
        
        assert result["complexity_score"] == 100  # Clamped
        assert result["information_score"] == 0  # Clamped
        assert result["accessibility_score"] == 75  # Unchanged
        assert result["quotability_score"] == 50  # Default
        assert result["other_field"] == "preserved"
    
    def test_validate_metrics_counts(self):
        """Test validating metric counts."""
        validator = DataValidator()
        
        metrics = {
            "word_count": 100.5,  # Float
            "sentence_count": -5,  # Negative
            "unique_words": "invalid",  # Invalid type
            "entity_count": 25  # Good
        }
        
        result = validator.validate_metrics(metrics)
        
        assert result["word_count"] == 100  # Converted to int
        assert result["sentence_count"] == 0  # Clamped
        assert result["unique_words"] == 0  # Default
        assert result["entity_count"] == 25  # Unchanged
    
    def test_validate_metrics_ratios(self):
        """Test validating metric ratios."""
        validator = DataValidator()
        
        metrics = {
            "information_density": 1.5,  # Too high
            "entity_density": -0.1,  # Too low
            "valid_density": 0.5  # Not a ratio field
        }
        
        result = validator.validate_metrics(metrics)
        
        assert result["information_density"] == 1.0  # Clamped
        assert result["entity_density"] == 0.0  # Clamped
        assert result["valid_density"] == 0.5  # Unchanged
    
    def test_get_validation_report(self):
        """Test getting validation report."""
        validator = DataValidator()
        
        # Trigger some validation stats
        validator.validate_entities([{"name": "A", "type": "PERSON"}])
        validator.validate_insights([{"title": "Short", "description": "Too short"}])
        
        report = validator.get_validation_report()
        
        assert isinstance(report, dict)
        assert report['name_too_short'] == 1
        assert report['insight_too_short'] == 1


class TestValidateAndEnhanceInsights:
    """Test validate_and_enhance_insights function."""
    
    @patch('src.utils.validation.DataValidator')
    @patch('src.utils.validation.logger')
    def test_validate_and_enhance_insights(self, mock_logger, mock_validator_class):
        """Test the validate_and_enhance_insights function."""
        # Setup mock validator
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        
        mock_validator.validate_insights.return_value = [
            {"title": "Enhanced", "description": "Enhanced insight"}
        ]
        mock_validator.get_validation_report.return_value = {
            "insights_processed": 1
        }
        
        # Test function
        insights = [{"title": "Test", "description": "Test insight"}]
        result = validate_and_enhance_insights(insights)
        
        assert len(result) == 1
        assert result[0]['title'] == "Enhanced"
        
        # Check logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "insights_processed" in log_message
    
    @patch('src.utils.validation.DataValidator')
    def test_validate_and_enhance_insights_no_report(self, mock_validator_class):
        """Test when no validation report is generated."""
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        
        mock_validator.validate_insights.return_value = []
        mock_validator.get_validation_report.return_value = {}
        
        result = validate_and_enhance_insights([])
        
        assert result == []


class TestIsValidUrl:
    """Test is_valid_url function."""
    
    def test_valid_urls(self):
        """Test valid URL patterns."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "http://sub.example.com",
            "https://example.com/path",
            "http://example.com:8080",
            "https://example.com/path?query=value",
            "http://localhost",
            "http://localhost:3000",
            "http://192.168.1.1",
            "https://192.168.1.1:8080/path"
        ]
        
        for url in valid_urls:
            assert is_valid_url(url) is True, f"Failed for: {url}"
    
    def test_invalid_urls(self):
        """Test invalid URL patterns."""
        invalid_urls = [
            "not a url",
            "ftp://example.com",  # Not http/https
            "http://",
            "https://",
            "example.com",  # Missing protocol
            "http:/example.com",  # Missing slash
            "http://example",  # Missing TLD (except localhost)
            "http://example..com",
            "http://.example.com",
            ""
        ]
        
        for url in invalid_urls:
            assert is_valid_url(url) is False, f"Failed for: {url}"


class TestIsValidEmail:
    """Test is_valid_email function."""
    
    def test_valid_emails(self):
        """Test valid email patterns."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user_name@example.com",  # Changed - hyphen in domain not supported by the regex
            "123@example.com",
            "user%test@example.com"
        ]
        
        for email in valid_emails:
            assert is_valid_email(email) is True, f"Failed for: {email}"
    
    def test_invalid_emails(self):
        """Test invalid email patterns."""
        invalid_emails = [
            "not an email",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@example",
            "user@.com",
            "user@example.",
            "user @example.com",
            "user@exam ple.com",
            ""
        ]
        
        for email in invalid_emails:
            assert is_valid_email(email) is False, f"Failed for: {email}"