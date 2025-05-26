"""Tests for validation utilities."""

import pytest
from datetime import datetime
from unittest.mock import patch
from src.utils.validation import (
    validate_text_input,
    validate_date_format,
    sanitize_file_path,
    normalize_entity_name,
    calculate_name_similarity,
    DataValidator,
    validate_and_enhance_insights,
    is_valid_url,
    is_valid_email
)


class TestTextValidation:
    """Tests for text validation functions."""
    
    def test_validate_text_input_string(self):
        """Test validation of normal string input."""
        assert validate_text_input("  hello world  ") == "hello world"
        assert validate_text_input("test") == "test"
    
    def test_validate_text_input_none(self):
        """Test handling of None input."""
        assert validate_text_input(None) == ""
        assert validate_text_input(None, "custom_field") == ""
    
    def test_validate_text_input_non_string(self):
        """Test conversion of non-string types."""
        assert validate_text_input(123) == "123"
        assert validate_text_input(45.67) == "45.67"
        assert validate_text_input([1, 2, 3]) == "[1, 2, 3]"
    
    def test_validate_text_input_empty(self):
        """Test handling of empty strings."""
        assert validate_text_input("") == ""
        assert validate_text_input("   ") == ""


class TestDateValidation:
    """Tests for date validation functions."""
    
    def test_validate_date_format_valid(self):
        """Test validation of valid date formats."""
        # ISO format
        result = validate_date_format("2023-12-25T10:30:00")
        assert "2023-12-25" in result
        
        # Common formats
        assert "2023-12-25" in validate_date_format("2023-12-25")
        assert "2023-12-25" in validate_date_format("12/25/2023")
        assert "2023-12-25" in validate_date_format("25/12/2023")
    
    def test_validate_date_format_empty(self):
        """Test handling of empty date input."""
        result = validate_date_format("")
        assert datetime.now().year == datetime.fromisoformat(result).year
        
        result = validate_date_format(None)
        assert datetime.now().year == datetime.fromisoformat(result).year
    
    @patch('src.utils.validation.datetime')
    def test_validate_date_format_invalid(self, mock_datetime):
        """Test handling of invalid date formats."""
        mock_now = datetime(2023, 12, 25, 10, 30, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.side_effect = ValueError
        
        result = validate_date_format("invalid-date")
        assert mock_now.isoformat() in result
    
    def test_validate_date_format_with_dateutil(self):
        """Test date parsing with dateutil if available."""
        try:
            import dateutil
            # Complex format that dateutil can handle
            result = validate_date_format("Dec 25, 2023 at 10:30 AM")
            assert "2023-12-25" in result
        except ImportError:
            pytest.skip("dateutil not available")


class TestPathSanitization:
    """Tests for path sanitization."""
    
    def test_sanitize_file_path_normal(self):
        """Test sanitization of normal paths."""
        assert sanitize_file_path("path/to/file.txt") == "path/to/file.txt"
        assert sanitize_file_path("file_name-123.pdf") == "file_name-123.pdf"
    
    def test_sanitize_file_path_dangerous(self):
        """Test removal of dangerous characters."""
        assert sanitize_file_path("../../etc/passwd") == "etc/passwd"
        assert sanitize_file_path("/etc/passwd") == "etc/passwd"
        assert sanitize_file_path("file;rm -rf /") == "filerm -rf "
    
    def test_sanitize_file_path_special_chars(self):
        """Test handling of special characters."""
        assert sanitize_file_path("file<>:|?*name.txt") == "filename.txt"
        assert sanitize_file_path("path//to///file") == "path/to/file"
    
    def test_sanitize_file_path_unicode(self):
        """Test handling of unicode characters."""
        # Unicode characters should be removed
        assert sanitize_file_path("file_名前.txt") == "file_.txt"


class TestEntityNormalization:
    """Tests for entity name normalization."""
    
    def test_normalize_entity_name_basic(self):
        """Test basic normalization."""
        assert normalize_entity_name("Apple Inc.") == "apple"
        assert normalize_entity_name("  Microsoft Corporation  ") == "microsoft"
        assert normalize_entity_name("Google LLC") == "google"
    
    def test_normalize_entity_name_abbreviations(self):
        """Test handling of abbreviations."""
        assert normalize_entity_name("U.S. Government") == "us government"
        assert normalize_entity_name("Dr. Smith") == "doctor smith"
        assert normalize_entity_name("Johnson & Johnson") == "johnson and johnson"
    
    def test_normalize_entity_name_suffixes(self):
        """Test removal of corporate suffixes."""
        assert normalize_entity_name("Amazon, Inc.") == "amazon"
        assert normalize_entity_name("Tesla Inc") == "tesla"
        assert normalize_entity_name("Meta Platforms, Inc.") == "meta platforms"
    
    def test_normalize_entity_name_empty(self):
        """Test handling of empty names."""
        assert normalize_entity_name("") == ""
        assert normalize_entity_name(None) == ""
        assert normalize_entity_name("   ") == ""
    
    def test_calculate_name_similarity(self):
        """Test name similarity calculation."""
        # Exact match
        assert calculate_name_similarity("Apple", "Apple") == 1.0
        
        # Similar names
        similarity = calculate_name_similarity("Apple Inc.", "Apple Corporation")
        assert similarity > 0.5
        
        # Different names
        similarity = calculate_name_similarity("Apple", "Microsoft")
        assert similarity < 0.3


class TestDataValidator:
    """Tests for DataValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return DataValidator(
            max_entities_per_segment=5,
            confidence_threshold=3,
            min_insight_length=10,
            min_quote_length=5
        )
    
    def test_validate_entities_basic(self, validator):
        """Test basic entity validation."""
        entities = [
            {'name': 'Apple', 'type': 'COMPANY', 'confidence': 5},
            {'name': 'Steve Jobs', 'type': 'PERSON', 'confidence': 4},
            {'name': 'A', 'type': 'PERSON'},  # Too short
            {'type': 'LOCATION'},  # Missing name
        ]
        
        validated = validator.validate_entities(entities)
        assert len(validated) == 2
        assert validated[0]['name'] == 'Apple'
        assert validated[1]['name'] == 'Steve Jobs'
        assert all('normalized_name' in e for e in validated)
    
    def test_validate_entities_deduplication(self, validator):
        """Test entity deduplication."""
        entities = [
            {'name': 'Apple Inc.', 'type': 'COMPANY', 'confidence': 5},
            {'name': 'apple', 'type': 'COMPANY', 'confidence': 3},
            {'name': 'APPLE', 'type': 'COMPANY', 'confidence': 4},
        ]
        
        validated = validator.validate_entities(entities)
        assert len(validated) == 1
        assert validated[0]['confidence'] == 5  # Should keep highest confidence
    
    def test_validate_entities_max_limit(self, validator):
        """Test entity count limiting."""
        entities = [
            {'name': f'Entity{i}', 'type': 'COMPANY', 'importance': i}
            for i in range(10)
        ]
        
        validated = validator.validate_entities(entities)
        assert len(validated) == 5  # max_entities_per_segment
        # Should keep highest importance
        assert validated[0]['importance'] == 9
    
    def test_validate_insights_basic(self, validator):
        """Test basic insight validation."""
        insights = [
            {
                'title': 'Key Finding',
                'description': 'This is an important finding about the topic',
                'insight_type': 'observation'
            },
            {
                'title': 'Another Finding',
                'description': 'Short',  # Too short
                'insight_type': 'fact'
            },
            {
                'description': 'Missing title',
                'insight_type': 'trend'
            }
        ]
        
        validated = validator.validate_insights(insights)
        assert len(validated) == 1
        assert validated[0]['title'] == 'Key Finding'
    
    def test_validate_insights_duplicates(self, validator):
        """Test insight deduplication."""
        insights = [
            {
                'title': 'Same Title',
                'description': 'First description that is long enough',
                'insight_type': 'observation'
            },
            {
                'title': 'same title',  # Duplicate (case-insensitive)
                'description': 'Second description that is long enough',
                'insight_type': 'fact'
            }
        ]
        
        validated = validator.validate_insights(insights)
        assert len(validated) == 1
        assert validated[0]['description'] == 'First description that is long enough'
    
    def test_validate_insights_type_normalization(self, validator):
        """Test insight type validation."""
        insights = [
            {
                'title': 'Finding',
                'description': 'A detailed finding about something important',
                'insight_type': 'INVALID_TYPE'
            }
        ]
        
        validated = validator.validate_insights(insights)
        assert validated[0]['insight_type'] == 'observation'  # Default type
    
    def test_validate_quotes_basic(self, validator):
        """Test basic quote validation."""
        quotes = [
            {
                'text': 'This is a meaningful quote',
                'speaker': 'John Doe',
                'importance': 8
            },
            {
                'text': 'Hi',  # Too short
                'speaker': 'Jane'
            },
            {
                'text': 'Missing speaker quote'
            }
        ]
        
        validated = validator.validate_quotes(quotes)
        assert len(validated) == 1
        assert validated[0]['text'] == 'This is a meaningful quote'
    
    def test_validate_quotes_deduplication(self, validator):
        """Test quote deduplication."""
        quotes = [
            {
                'text': 'This is the SAME quote!',
                'speaker': 'Speaker 1'
            },
            {
                'text': 'this is the same quote!',  # Duplicate (normalized)
                'speaker': 'Speaker 2'
            }
        ]
        
        validated = validator.validate_quotes(quotes)
        assert len(validated) == 1
    
    def test_validate_metrics(self, validator):
        """Test metric validation."""
        metrics = {
            'complexity_score': 150,  # Out of range
            'information_score': -10,  # Negative
            'word_count': 100.5,  # Should be int
            'entity_count': -5,  # Negative count
            'information_density': 1.5,  # Out of range ratio
            'invalid_field': 'ignored'
        }
        
        validated = validator.validate_metrics(metrics)
        assert validated['complexity_score'] == 100  # Clamped to max
        assert validated['information_score'] == 0  # Clamped to min
        assert validated['word_count'] == 100  # Converted to int
        assert validated['entity_count'] == 0  # Non-negative
        assert validated['information_density'] == 1.0  # Clamped to max ratio
        assert validated['invalid_field'] == 'ignored'  # Unchanged
    
    def test_get_validation_report(self, validator):
        """Test validation statistics reporting."""
        # Perform some validations that will generate stats
        entities = [
            {'name': 'A', 'type': 'PERSON'},  # Too short
            {'type': 'LOCATION'},  # Missing field
            {'name': 'Valid', 'type': 'COMPANY'},
            {'name': 'Valid', 'type': 'COMPANY'},  # Duplicate
        ]
        
        validator.validate_entities(entities)
        report = validator.get_validation_report()
        
        assert report['name_too_short'] == 1
        assert report['missing_fields'] == 1
        assert report['duplicates_merged'] == 1


class TestValidationHelpers:
    """Tests for validation helper functions."""
    
    def test_validate_and_enhance_insights(self):
        """Test the insight validation wrapper."""
        insights = [
            {
                'title': 'Valid Insight',
                'description': 'This is a valid insight with sufficient detail',
                'insight_type': 'observation'
            },
            {
                'title': 'Invalid',
                'description': 'Short'
            }
        ]
        
        validated = validate_and_enhance_insights(insights)
        assert len(validated) == 1
        assert validated[0]['title'] == 'Valid Insight'
    
    def test_is_valid_url(self):
        """Test URL validation."""
        # Valid URLs
        assert is_valid_url("https://www.example.com")
        assert is_valid_url("http://example.com/path/to/page")
        assert is_valid_url("https://example.com:8080/resource")
        assert is_valid_url("http://192.168.1.1")
        assert is_valid_url("http://localhost:3000")
        
        # Invalid URLs
        assert not is_valid_url("not a url")
        assert not is_valid_url("ftp://example.com")
        assert not is_valid_url("//example.com")
        assert not is_valid_url("example.com")
        assert not is_valid_url("")
    
    def test_is_valid_email(self):
        """Test email validation."""
        # Valid emails
        assert is_valid_email("user@example.com")
        assert is_valid_email("john.doe@company.co.uk")
        assert is_valid_email("test+tag@domain.org")
        assert is_valid_email("123@numbers.com")
        
        # Invalid emails
        assert not is_valid_email("not.an.email")
        assert not is_valid_email("@example.com")
        assert not is_valid_email("user@")
        assert not is_valid_email("user @example.com")
        assert not is_valid_email("")