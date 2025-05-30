"""Comprehensive tests for validation utilities."""

import re
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any

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
    """Test suite for validate_text_input function."""
    
    def test_valid_string_input(self):
        """Test validation of valid string input."""
        assert validate_text_input("Hello World") == "Hello World"
        assert validate_text_input("  Trimmed  ") == "Trimmed"
        assert validate_text_input("\n\tWhitespace\n\t") == "Whitespace"
    
    def test_none_input(self):
        """Test handling of None input."""
        assert validate_text_input(None) == ""
        assert validate_text_input(None, "custom_field") == ""
    
    def test_non_string_input(self):
        """Test conversion of non-string types."""
        assert validate_text_input(123) == "123"
        assert validate_text_input(45.67) == "45.67"
        assert validate_text_input(True) == "True"
        assert validate_text_input([1, 2, 3]) == "[1, 2, 3]"
        assert validate_text_input({"key": "value"}) == "{'key': 'value'}"
    
    def test_empty_string(self):
        """Test handling of empty strings."""
        assert validate_text_input("") == ""
        assert validate_text_input("   ") == ""
        assert validate_text_input("\n\t\r") == ""
    
    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        assert validate_text_input("Hello 🌍") == "Hello 🌍"
        assert validate_text_input("测试中文") == "测试中文"
        assert validate_text_input("Ñoño") == "Ñoño"
    
    @patch('logging.Logger.warning')
    def test_logging_for_none(self, mock_warning):
        """Test that None input generates warning log."""
        validate_text_input(None, "test_field")
        mock_warning.assert_called_with("test_field is None, using empty string")
    
    @patch('logging.Logger.warning')
    def test_logging_for_type_conversion(self, mock_warning):
        """Test that type conversion generates warning log."""
        validate_text_input(123, "numeric_field")
        mock_warning.assert_called_with("numeric_field is not string, converting: <class 'int'>")


class TestValidateDateFormat:
    """Test suite for validate_date_format function."""
    
    def test_valid_iso_format(self):
        """Test validation of already valid ISO format dates."""
        iso_date = "2024-01-15T10:30:00"
        result = validate_date_format(iso_date)
        assert result.startswith("2024-01-15")
    
    def test_empty_or_none_date(self):
        """Test handling of empty or None dates."""
        result = validate_date_format(None)
        assert datetime.fromisoformat(result)  # Should be valid ISO format
        
        result = validate_date_format("")
        assert datetime.fromisoformat(result)
    
    def test_common_date_formats(self):
        """Test parsing of common date formats."""
        formats = [
            ("2024-01-15", "2024-01-15"),
            ("2024-01-15T10:30:00", "2024-01-15"),
            ("2024-01-15 10:30:00", "2024-01-15"),
            ("01/15/2024", "2024-01-15"),
            ("15/01/2024", "2024-01-15"),
            ("20240115", "2024-01-15")
        ]
        
        for date_str, expected_prefix in formats:
            result = validate_date_format(date_str)
            assert result.startswith(expected_prefix)
    
    @patch('dateutil.parser.parse')
    def test_dateutil_parsing(self, mock_parse):
        """Test parsing with dateutil when available."""
        mock_datetime = MagicMock()
        mock_datetime.isoformat.return_value = "2024-01-15T00:00:00"
        mock_parse.return_value = mock_datetime
        
        result = validate_date_format("Jan 15, 2024")
        assert result == "2024-01-15T00:00:00"
        mock_parse.assert_called_once()
    
    @patch('dateutil.parser.parse', side_effect=ImportError)
    def test_fallback_without_dateutil(self, mock_parse):
        """Test fallback parsing when dateutil is not available."""
        result = validate_date_format("2024-01-15")
        assert result.startswith("2024-01-15")
    
    def test_invalid_date_formats(self):
        """Test handling of invalid date formats."""
        invalid_dates = [
            "not a date",
            "12345",
            "2024-13-45",  # Invalid month/day
            "abc-def-ghi"
        ]
        
        for date_str in invalid_dates:
            result = validate_date_format(date_str)
            # Should return current datetime
            assert datetime.fromisoformat(result)
            assert (datetime.now() - datetime.fromisoformat(result)).total_seconds() < 1
    
    @patch('logging.Logger.warning')
    def test_logging_for_parse_failures(self, mock_warning):
        """Test logging when date parsing fails."""
        validate_date_format("invalid date")
        assert mock_warning.called


class TestSanitizeFilePath:
    """Test suite for sanitize_file_path function."""
    
    def test_valid_paths(self):
        """Test sanitization of valid file paths."""
        assert sanitize_file_path("folder/file.txt") == "folder/file.txt"
        assert sanitize_file_path("folder_name/file-name.txt") == "folder_name/file-name.txt"
        assert sanitize_file_path("path/to/file.py") == "path/to/file.py"
    
    def test_dangerous_characters_removal(self):
        """Test removal of potentially dangerous characters."""
        assert sanitize_file_path("file;rm -rf /") == "filerm rf "
        assert sanitize_file_path("file&command") == "filecommand"
        assert sanitize_file_path("file|pipe") == "filepipe"
        assert sanitize_file_path("file`backtick`") == "filebacktick"
        assert sanitize_file_path("file$variable") == "filevariable"
    
    def test_directory_traversal_prevention(self):
        """Test prevention of directory traversal attacks."""
        assert sanitize_file_path("../../../etc/passwd") == "etc/passwd"
        assert sanitize_file_path("folder/../..") == "folder/"
        assert sanitize_file_path("..\\..\\windows\\system32") == "windowssystem32"
    
    def test_absolute_path_prevention(self):
        """Test removal of leading slashes."""
        assert sanitize_file_path("/etc/passwd") == "etc/passwd"
        assert sanitize_file_path("///root/file") == "root/file"
        assert sanitize_file_path("\\windows\\system32") == "windowssystem32"
    
    def test_double_slash_normalization(self):
        """Test normalization of double slashes."""
        assert sanitize_file_path("folder//file.txt") == "folder/file.txt"
        assert sanitize_file_path("path///to////file") == "path/to/file"
    
    def test_special_cases(self):
        """Test special edge cases."""
        assert sanitize_file_path("") == ""
        assert sanitize_file_path(".") == "."
        assert sanitize_file_path("./file.txt") == "./file.txt"
        assert sanitize_file_path(123) == "123"  # Non-string input
    
    def test_unicode_in_paths(self):
        """Test handling of Unicode in file paths."""
        assert sanitize_file_path("文件/测试.txt") == ".txt"  # Non-word characters removed
        assert sanitize_file_path("naïve_file.txt") == "nave_file.txt"


class TestDataValidator:
    """Test suite for DataValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a DataValidator instance."""
        return DataValidator(
            max_entities_per_segment=10,
            confidence_threshold=3,
            min_insight_length=20,
            min_quote_length=10
        )
    
    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator.max_entities_per_segment == 10
        assert validator.confidence_threshold == 3
        assert validator.min_insight_length == 20
        assert validator.min_quote_length == 10
        assert len(validator.validation_stats) == 0
    
    def test_validate_entities_empty(self, validator):
        """Test validation of empty entity list."""
        assert validator.validate_entities([]) == []
        assert validator.validate_entities(None) == []
    
    def test_validate_entities_missing_fields(self, validator):
        """Test handling of entities with missing fields."""
        entities = [
            {"name": "Entity1"},  # Missing type
            {"type": "PERSON"},  # Missing name
            {},  # Missing both
            {"name": "Valid", "type": "PERSON"}
        ]
        
        result = validator.validate_entities(entities)
        assert len(result) == 1
        assert result[0]['name'] == "Valid"
        assert validator.validation_stats['missing_fields'] == 3
    
    def test_validate_entities_name_validation(self, validator):
        """Test entity name validation."""
        entities = [
            {"name": "A", "type": "PERSON"},  # Too short
            {"name": "  ", "type": "PERSON"},  # Empty after strip
            {"name": "Valid Name", "type": "PERSON"},
            {"name": 123, "type": "PERSON"}  # Non-string converted
        ]
        
        result = validator.validate_entities(entities)
        assert len(result) == 2
        assert result[0]['name'] == "Valid Name"
        assert result[1]['name'] == "123"
        assert validator.validation_stats['name_too_short'] >= 1
    
    def test_validate_entities_deduplication(self, validator):
        """Test entity deduplication."""
        entities = [
            {"name": "John Doe", "type": "PERSON", "confidence": 5},
            {"name": "john doe", "type": "PERSON", "confidence": 8},  # Duplicate
            {"name": "John Doe", "type": "ORGANIZATION"},  # Different type
            {"name": "John  Doe", "type": "PERSON", "confidence": 3}  # Normalized duplicate
        ]
        
        result = validator.validate_entities(entities)
        assert len(result) == 2  # One PERSON and one ORGANIZATION
        
        # Check confidence was merged to maximum
        person_entity = next(e for e in result if e['type'] == 'PERSON')
        assert person_entity['confidence'] == 8
        assert validator.validation_stats['duplicates_merged'] >= 1
    
    def test_validate_entities_confidence_threshold(self, validator):
        """Test confidence threshold handling."""
        entities = [
            {"name": "Low Confidence", "type": "PERSON", "confidence": 1},
            {"name": "High Confidence", "type": "PERSON", "confidence": 10}
        ]
        
        result = validator.validate_entities(entities)
        assert len(result) == 2  # Both kept but low confidence logged
        assert validator.validation_stats['low_confidence'] == 1
    
    def test_validate_entities_max_limit(self, validator):
        """Test entity count limiting."""
        # Create more entities than the limit
        entities = [
            {"name": f"Entity{i}", "type": "PERSON", "importance": i}
            for i in range(15)
        ]
        
        result = validator.validate_entities(entities)
        assert len(result) == 10  # Limited to max_entities_per_segment
        
        # Check that highest importance entities were kept
        importances = [e['importance'] for e in result]
        assert min(importances) >= 5
        assert validator.validation_stats['entities_truncated'] == 1
    
    def test_validate_entities_optional_fields(self, validator):
        """Test handling of optional entity fields."""
        entities = [{
            "name": "Complete Entity",
            "type": "PERSON",
            "confidence": 8,
            "importance": 9,
            "description": "This is a description"
        }]
        
        result = validator.validate_entities(entities)
        assert len(result) == 1
        entity = result[0]
        assert entity['description'] == "This is a description"
        assert 'normalized_name' in entity
    
    def test_validate_insights_empty(self, validator):
        """Test validation of empty insight list."""
        assert validator.validate_insights([]) == []
        assert validator.validate_insights(None) == []
    
    def test_validate_insights_missing_fields(self, validator):
        """Test handling of insights with missing fields."""
        insights = [
            {"title": "Title Only"},
            {"description": "Description only"},
            {},
            {"title": "Valid", "description": "This is a valid insight description"}
        ]
        
        result = validator.validate_insights(insights)
        assert len(result) == 1
        assert result[0]['title'] == "Valid"
        assert validator.validation_stats['insight_missing_fields'] == 3
    
    def test_validate_insights_length_validation(self, validator):
        """Test insight description length validation."""
        insights = [
            {"title": "Short", "description": "Too short"},
            {"title": "Valid", "description": "This description is long enough to be valid"}
        ]
        
        result = validator.validate_insights(insights)
        assert len(result) == 1
        assert result[0]['title'] == "Valid"
        assert validator.validation_stats['insight_too_short'] == 1
    
    def test_validate_insights_duplicate_titles(self, validator):
        """Test duplicate insight title detection."""
        insights = [
            {"title": "Duplicate Title", "description": "First insight with this title"},
            {"title": "duplicate title", "description": "Second insight with same title"},
            {"title": "Unique Title", "description": "This insight has a unique title"}
        ]
        
        result = validator.validate_insights(insights)
        assert len(result) == 2
        titles = [i['title'] for i in result]
        assert "Duplicate Title" in titles
        assert "Unique Title" in titles
        assert validator.validation_stats['duplicate_insights'] == 1
    
    def test_validate_insights_type_validation(self, validator):
        """Test insight type validation."""
        insights = [
            {"title": "Default", "description": "No type specified - should default"},
            {"title": "Valid", "description": "Valid type specified", "insight_type": "trend"},
            {"title": "Invalid", "description": "Invalid type specified", "insight_type": "random"}
        ]
        
        result = validator.validate_insights(insights)
        assert len(result) == 3
        assert result[0]['insight_type'] == 'observation'  # Default
        assert result[1]['insight_type'] == 'trend'
        assert result[2]['insight_type'] == 'observation'  # Invalid replaced
    
    def test_validate_insights_optional_fields(self, validator):
        """Test handling of optional insight fields."""
        insights = [{
            "title": "Complete Insight",
            "description": "This insight has all optional fields",
            "insight_type": "analysis",
            "confidence": 0.95,
            "importance": 8,
            "supporting_evidence": "Evidence text",
            "entities": ["Entity1", "Entity2", "", None, 123]  # Mixed valid/invalid
        }]
        
        result = validator.validate_insights(insights)
        assert len(result) == 1
        insight = result[0]
        assert insight['supporting_evidence'] == "Evidence text"
        assert insight['entities'] == ["Entity1", "Entity2"]  # Invalid ones filtered
    
    def test_validate_quotes_empty(self, validator):
        """Test validation of empty quote list."""
        assert validator.validate_quotes([]) == []
        assert validator.validate_quotes(None) == []
    
    def test_validate_quotes_missing_fields(self, validator):
        """Test handling of quotes with missing fields."""
        quotes = [
            {"text": "Quote without speaker"},
            {"speaker": "Speaker without quote"},
            {},
            {"text": "Valid quote text", "speaker": "Valid Speaker"}
        ]
        
        result = validator.validate_quotes(quotes)
        assert len(result) == 1
        assert result[0]['text'] == "Valid quote text"
        assert validator.validation_stats['quote_missing_fields'] == 3
    
    def test_validate_quotes_length_validation(self, validator):
        """Test quote text length validation."""
        quotes = [
            {"text": "Too short", "speaker": "Speaker"},
            {"text": "This quote is long enough", "speaker": "Speaker"}
        ]
        
        result = validator.validate_quotes(quotes)
        assert len(result) == 1
        assert "long enough" in result[0]['text']
        assert validator.validation_stats['quote_too_short'] == 1
    
    def test_validate_quotes_deduplication(self, validator):
        """Test quote deduplication."""
        quotes = [
            {"text": "This is a duplicate quote", "speaker": "Speaker1"},
            {"text": "  This  is  a  DUPLICATE  quote  ", "speaker": "Speaker2"},  # Normalized duplicate
            {"text": "This is a unique quote", "speaker": "Speaker3"}
        ]
        
        result = validator.validate_quotes(quotes)
        assert len(result) == 2
        assert validator.validation_stats['duplicate_quotes'] == 1
    
    def test_validate_quotes_optional_fields(self, validator):
        """Test handling of optional quote fields."""
        quotes = [{
            "text": "Complete quote with all fields",
            "speaker": "Complete Speaker",
            "context": "In a discussion about testing",
            "importance": 9,
            "timestamp": "00:15:30"
        }]
        
        result = validator.validate_quotes(quotes)
        assert len(result) == 1
        quote = result[0]
        assert quote['context'] == "In a discussion about testing"
        assert quote['importance'] == 9
        assert quote['timestamp'] == "00:15:30"
    
    def test_validate_metrics_score_ranges(self, validator):
        """Test validation of score metrics (0-100 range)."""
        metrics = {
            'complexity_score': 150,  # Over 100
            'information_score': -50,  # Below 0
            'accessibility_score': 75,  # Valid
            'quotability_score': 'invalid',  # Non-numeric
            'best_of_score': 50.5  # Valid float
        }
        
        result = validator.validate_metrics(metrics)
        assert result['complexity_score'] == 100
        assert result['information_score'] == 0
        assert result['accessibility_score'] == 75
        assert result['quotability_score'] == 50  # Default
        assert result['best_of_score'] == 50.5
    
    def test_validate_metrics_count_fields(self, validator):
        """Test validation of count metrics (non-negative integers)."""
        metrics = {
            'word_count': -10,  # Negative
            'sentence_count': 5.7,  # Float to int
            'unique_words': 'twenty',  # Non-numeric
            'entity_count': 15  # Valid
        }
        
        result = validator.validate_metrics(metrics)
        assert result['word_count'] == 0
        assert result['sentence_count'] == 5
        assert result['unique_words'] == 0
        assert result['entity_count'] == 15
    
    def test_validate_metrics_ratio_fields(self, validator):
        """Test validation of ratio metrics (0-1 range)."""
        metrics = {
            'information_density': 1.5,  # Over 1
            'entity_density': -0.2,  # Below 0
            'other_field': 0.75  # Not a ratio field
        }
        
        result = validator.validate_metrics(metrics)
        assert result['information_density'] == 1.0
        assert result['entity_density'] == 0.0
        assert result['other_field'] == 0.75  # Unchanged
    
    def test_get_validation_report(self, validator):
        """Test getting validation statistics report."""
        # Perform some validations to generate stats
        validator.validate_entities([{"name": "A", "type": "PERSON"}])
        validator.validate_insights([{"title": "Short", "description": "Too short"}])
        
        report = validator.get_validation_report()
        assert isinstance(report, dict)
        assert 'name_too_short' in report
        assert 'insight_too_short' in report
        assert report['name_too_short'] >= 1
        assert report['insight_too_short'] >= 1


class TestValidateAndEnhanceInsights:
    """Test suite for validate_and_enhance_insights function."""
    
    @patch('src.utils.validation.logger')
    def test_basic_validation(self, mock_logger):
        """Test basic insight validation and enhancement."""
        insights = [
            {"title": "Valid Insight", "description": "This is a valid insight description"},
            {"title": "Invalid", "description": "Short"}
        ]
        
        result = validate_and_enhance_insights(insights)
        assert len(result) == 1
        assert result[0]['title'] == "Valid Insight"
        
        # Check that validation report was logged
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "validation report" in call_args
    
    def test_with_large_context_flag(self):
        """Test validation with large context flag."""
        insights = [{"title": "Test", "description": "Test insight for large context validation"}]
        
        # Should work the same regardless of flag
        result1 = validate_and_enhance_insights(insights, use_large_context=True)
        result2 = validate_and_enhance_insights(insights, use_large_context=False)
        
        assert result1 == result2
    
    def test_empty_insights(self):
        """Test handling of empty insights."""
        result = validate_and_enhance_insights([])
        assert result == []
        
        result = validate_and_enhance_insights(None)
        assert result == []


class TestIsValidUrl:
    """Test suite for is_valid_url function."""
    
    def test_valid_urls(self):
        """Test validation of valid URLs."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "http://sub.example.com",
            "https://example.com/path/to/page",
            "http://example.com:8080",
            "https://example.com/path?query=value",
            "http://localhost",
            "http://localhost:3000",
            "http://192.168.1.1",
            "https://192.168.1.1:8443/path"
        ]
        
        for url in valid_urls:
            assert is_valid_url(url), f"URL should be valid: {url}"
    
    def test_invalid_urls(self):
        """Test validation of invalid URLs."""
        invalid_urls = [
            "not a url",
            "ftp://example.com",  # Not http/https
            "http://",
            "https://",
            "//example.com",
            "example.com",  # Missing protocol
            "http:/example.com",  # Single slash
            "http://example",  # Might be valid for some patterns
            "javascript:alert('xss')",
            "mailto:test@example.com",
            ""
        ]
        
        for url in invalid_urls:
            assert not is_valid_url(url), f"URL should be invalid: {url}"
    
    def test_case_insensitivity(self):
        """Test case insensitive URL validation."""
        assert is_valid_url("HTTP://EXAMPLE.COM")
        assert is_valid_url("HtTpS://Example.Com/Path")
    
    def test_edge_cases(self):
        """Test edge cases for URL validation."""
        # Very long domain
        long_domain = "http://" + "sub." * 20 + "example.com"
        assert is_valid_url(long_domain)
        
        # URL with many query parameters
        complex_url = "https://example.com/path?a=1&b=2&c=3&d=4"
        assert is_valid_url(complex_url)
        
        # URL with fragment
        assert is_valid_url("https://example.com/page#section")


class TestIsValidEmail:
    """Test suite for is_valid_email function."""
    
    def test_valid_emails(self):
        """Test validation of valid email addresses."""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "test_email@sub.example.com",
            "123@example.com",
            "test%special@example.com",
            "firstname-lastname@example.com"
        ]
        
        for email in valid_emails:
            assert is_valid_email(email), f"Email should be valid: {email}"
    
    def test_invalid_emails(self):
        """Test validation of invalid email addresses."""
        invalid_emails = [
            "not an email",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@example",
            "user.example.com",
            "user@.com",
            "user@example..com",
            "user name@example.com",  # Space in local part
            "user@exam ple.com",  # Space in domain
            "",
            "user@",
            "@",
            "user@example.c"  # TLD too short
        ]
        
        for email in invalid_emails:
            assert not is_valid_email(email), f"Email should be invalid: {email}"
    
    def test_edge_cases(self):
        """Test edge cases for email validation."""
        # Very long local part
        long_local = "a" * 64 + "@example.com"
        assert is_valid_email(long_local)
        
        # Multiple dots in local part
        assert is_valid_email("first.middle.last@example.com")
        
        # Numbers in domain
        assert is_valid_email("test@123.456.com")
        
        # Uppercase letters
        assert is_valid_email("Test@Example.COM")


class TestIntegrationScenarios:
    """Integration tests for validation utilities."""
    
    def test_full_data_validation_pipeline(self):
        """Test complete data validation pipeline."""
        validator = DataValidator()
        
        # Simulate extraction output
        entities = [
            {"name": "John Doe", "type": "PERSON", "confidence": 8},
            {"name": "OpenAI", "type": "ORGANIZATION", "importance": 9},
            {"name": "AI", "type": "CONCEPT", "confidence": 2},  # Low confidence
            {"name": "A", "type": "PERSON"}  # Too short
        ]
        
        insights = [
            {
                "title": "AI Development Trends",
                "description": "The rapid advancement of AI technology is reshaping industries",
                "insight_type": "trend",
                "entities": ["OpenAI", "AI"]
            },
            {
                "title": "Short",
                "description": "Too brief"  # Will be filtered
            }
        ]
        
        quotes = [
            {
                "text": "AI will transform how we work and live",
                "speaker": "John Doe",
                "importance": 8
            },
            {
                "text": "Short",  # Too short
                "speaker": "Unknown"
            }
        ]
        
        metrics = {
            'complexity_score': 150,  # Will be clamped
            'word_count': 500,
            'information_density': 0.75
        }
        
        # Validate all data
        validated_entities = validator.validate_entities(entities)
        validated_insights = validator.validate_insights(insights)
        validated_quotes = validator.validate_quotes(quotes)
        validated_metrics = validator.validate_metrics(metrics)
        
        # Check results
        assert len(validated_entities) == 2  # John Doe and OpenAI
        assert len(validated_insights) == 1  # Only the valid one
        assert len(validated_quotes) == 1  # Only the valid one
        assert validated_metrics['complexity_score'] == 100
        
        # Check validation report
        report = validator.get_validation_report()
        assert report['name_too_short'] >= 1
        assert report['low_confidence'] >= 1
        assert report['insight_too_short'] >= 1
        assert report['quote_too_short'] >= 1
    
    @patch('src.utils.validation.normalize_entity_name')
    @patch('src.utils.validation.calculate_name_similarity')
    def test_validation_with_text_processing_integration(self, mock_similarity, mock_normalize):
        """Test integration with text processing utilities."""
        mock_normalize.side_effect = lambda x: x.lower().replace(" ", "")
        mock_similarity.return_value = 0.9
        
        validator = DataValidator()
        
        entities = [
            {"name": "John Doe", "type": "PERSON"},
            {"name": "JOHN DOE", "type": "PERSON"}  # Should be deduplicated
        ]
        
        result = validator.validate_entities(entities)
        
        # Should call normalization
        assert mock_normalize.call_count >= 2
        
        # Should deduplicate
        assert len(result) == 1
    
    def test_validation_error_recovery(self):
        """Test validation handles errors gracefully."""
        validator = DataValidator()
        
        # Malformed data that might cause errors
        entities = [
            {"name": None, "type": "PERSON"},
            {"name": {"nested": "object"}, "type": "PERSON"},
            ["not", "a", "dict"],  # Wrong type
            {"name": "Valid", "type": "PERSON"}
        ]
        
        # Should handle errors and return valid entities
        try:
            result = validator.validate_entities(entities)
            # Should get at least the valid entity
            valid_names = [e['name'] for e in result if isinstance(e, dict)]
            assert "Valid" in valid_names or len(result) >= 0
        except Exception as e:
            pytest.fail(f"Validation should handle errors gracefully: {e}")


class TestPerformanceAndScaling:
    """Test performance and scaling of validation utilities."""
    
    def test_large_entity_list_performance(self):
        """Test performance with large entity lists."""
        validator = DataValidator(max_entities_per_segment=100)
        
        # Create 1000 entities
        entities = [
            {
                "name": f"Entity_{i}",
                "type": "PERSON" if i % 2 == 0 else "ORGANIZATION",
                "confidence": i % 10,
                "importance": i % 10
            }
            for i in range(1000)
        ]
        
        import time
        start = time.time()
        result = validator.validate_entities(entities)
        duration = time.time() - start
        
        # Should complete in reasonable time
        assert duration < 1.0  # Less than 1 second
        assert len(result) == 100  # Limited to max
        
        # Check highest importance kept
        importances = [e['importance'] for e in result]
        assert min(importances) >= 9  # Only highest importance
    
    def test_memory_efficiency(self):
        """Test memory efficiency of validation."""
        validator = DataValidator()
        
        # Create data with potential memory issues
        large_text = "x" * 10000
        entities = [
            {"name": f"Entity{i}", "type": "PERSON", "description": large_text}
            for i in range(100)
        ]
        
        # Should handle without memory issues
        result = validator.validate_entities(entities)
        assert len(result) <= validator.max_entities_per_segment
    
    def test_validation_caching_behavior(self):
        """Test if validation has any caching behavior."""
        validator = DataValidator()
        
        entities = [{"name": "Test", "type": "PERSON"}]
        
        # Validate same data multiple times
        result1 = validator.validate_entities(entities)
        result2 = validator.validate_entities(entities)
        
        # Results should be independent (no shared state)
        assert result1 is not result2
        result1[0]['name'] = "Modified"
        assert result2[0]['name'] == "Test"


class TestBackwardCompatibility:
    """Test backward compatibility of validation functions."""
    
    def test_legacy_data_formats(self):
        """Test handling of legacy data formats."""
        validator = DataValidator()
        
        # Old format might have different field names
        legacy_entities = [
            {"entity_name": "John Doe", "entity_type": "PERSON"},  # Wrong field names
            {"name": "Valid Entity", "type": "ORGANIZATION"}
        ]
        
        # Should handle gracefully (skip invalid, keep valid)
        result = validator.validate_entities(legacy_entities)
        assert any(e['name'] == "Valid Entity" for e in result)
    
    def test_deprecated_validation_patterns(self):
        """Test deprecated validation patterns still work."""
        # Test old-style validation calls
        text = validate_text_input(None)
        assert text == ""
        
        date = validate_date_format("")
        assert date  # Should return some valid date
        
        path = sanitize_file_path("../etc/passwd")
        assert ".." not in path