"""
Comprehensive tests for the exceptions module.

This module tests all custom exceptions, their initialization,
string representations, and severity levels.
"""

import pytest

from src.core.exceptions import (
    ErrorSeverity,
    PodcastProcessingError,
    DatabaseConnectionError,
    AudioProcessingError,
    LLMProcessingError,
    ConfigurationError,
    PipelineError,
    ValidationError,
    ProviderError,
    CriticalError,
    ExtractionError,
    RateLimitError,
    TimeoutError,
    ResourceError,
    DataIntegrityError,
    ParsingError,
    CheckpointError,
    BatchProcessingError,
    PodcastKGError,  # Alias
    ConnectionError,  # Alias
)


class TestErrorSeverity:
    """Test the ErrorSeverity enum."""
    
    def test_severity_values(self):
        """Test that severity levels have expected values."""
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.INFO.value == "info"
    
    def test_all_severities_defined(self):
        """Test that all expected severities are defined."""
        severities = [s.value for s in ErrorSeverity]
        assert "critical" in severities
        assert "warning" in severities
        assert "info" in severities
        assert len(severities) == 3


class TestPodcastProcessingError:
    """Test the base PodcastProcessingError class."""
    
    def test_basic_initialization(self):
        """Test basic exception initialization."""
        error = PodcastProcessingError("Test error")
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.WARNING
        assert error.details == {}
    
    def test_initialization_with_severity(self):
        """Test initialization with custom severity."""
        error = PodcastProcessingError("Critical error", ErrorSeverity.CRITICAL)
        assert error.message == "Critical error"
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_initialization_with_details(self):
        """Test initialization with details."""
        details = {"code": "ERR001", "context": "test"}
        error = PodcastProcessingError("Error with details", details=details)
        assert error.details == details
    
    def test_string_representation_basic(self):
        """Test basic string representation."""
        error = PodcastProcessingError("Simple error")
        assert str(error) == "[WARNING] Simple error"
    
    def test_string_representation_with_severity(self):
        """Test string representation with different severities."""
        error1 = PodcastProcessingError("Critical", ErrorSeverity.CRITICAL)
        assert str(error1) == "[CRITICAL] Critical"
        
        error2 = PodcastProcessingError("Info", ErrorSeverity.INFO)
        assert str(error2) == "[INFO] Info"
    
    def test_string_representation_with_details(self):
        """Test string representation including details."""
        details = {"code": "E001", "retry_count": 3}
        error = PodcastProcessingError("Error", details=details)
        error_str = str(error)
        assert error_str.startswith("[WARNING] Error")
        assert "Details:" in error_str
        assert "'code': 'E001'" in error_str
        assert "'retry_count': 3" in error_str
    
    def test_inheritance_from_exception(self):
        """Test that it properly inherits from Exception."""
        error = PodcastProcessingError("Test")
        assert isinstance(error, Exception)
        
        # Can be raised and caught
        with pytest.raises(PodcastProcessingError) as exc_info:
            raise error
        assert exc_info.value.message == "Test"


class TestDatabaseConnectionError:
    """Test DatabaseConnectionError class."""
    
    def test_always_critical(self):
        """Test that database errors are always critical."""
        error = DatabaseConnectionError("Connection failed")
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.message == "Connection failed"
    
    def test_with_details(self):
        """Test database error with connection details."""
        details = {"host": "localhost", "port": 5432, "error": "timeout"}
        error = DatabaseConnectionError("DB timeout", details)
        assert error.details == details
        assert str(error) == "[CRITICAL] DB timeout | Details: {'host': 'localhost', 'port': 5432, 'error': 'timeout'}"
    
    def test_alias_compatibility(self):
        """Test that ConnectionError alias works."""
        error = ConnectionError("Using alias")
        assert isinstance(error, DatabaseConnectionError)
        assert error.severity == ErrorSeverity.CRITICAL


class TestAudioProcessingError:
    """Test AudioProcessingError class."""
    
    def test_default_severity(self):
        """Test default severity is WARNING."""
        error = AudioProcessingError("Transcription failed")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_custom_severity(self):
        """Test can override severity."""
        error = AudioProcessingError("Critical audio failure", ErrorSeverity.CRITICAL)
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_with_audio_details(self):
        """Test with audio-specific details."""
        details = {
            "file": "episode1.mp3",
            "duration": 3600,
            "error_at": 1800
        }
        error = AudioProcessingError("Diarization error", details=details)
        assert error.details["file"] == "episode1.mp3"
        assert error.details["duration"] == 3600


class TestLLMProcessingError:
    """Test LLMProcessingError class."""
    
    def test_default_warning_severity(self):
        """Test default severity for LLM errors."""
        error = LLMProcessingError("Model timeout")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_with_model_details(self):
        """Test with model-specific details."""
        details = {
            "model": "gpt-4",
            "tokens": 4096,
            "error_type": "rate_limit"
        }
        error = LLMProcessingError("Rate limit exceeded", details=details)
        assert error.details["model"] == "gpt-4"
        assert "rate_limit" in str(error)


class TestConfigurationError:
    """Test ConfigurationError class."""
    
    def test_always_critical(self):
        """Test configuration errors are critical."""
        error = ConfigurationError("Invalid config")
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_with_config_details(self):
        """Test with configuration details."""
        details = {
            "field": "neo4j_uri",
            "value": "invalid://uri",
            "expected": "bolt://host:port"
        }
        error = ConfigurationError("Invalid Neo4j URI", details)
        assert error.details["field"] == "neo4j_uri"


class TestPipelineError:
    """Test PipelineError class."""
    
    def test_default_critical_severity(self):
        """Test pipeline errors default to critical."""
        error = PipelineError("Pipeline failed")
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_can_override_severity(self):
        """Test can set non-critical pipeline error."""
        error = PipelineError("Partial failure", ErrorSeverity.WARNING)
        assert error.severity == ErrorSeverity.WARNING


class TestValidationError:
    """Test ValidationError class."""
    
    def test_basic_validation_error(self):
        """Test basic validation error."""
        error = ValidationError("Invalid input")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_with_field_and_value(self):
        """Test validation error with field info."""
        error = ValidationError(
            "Invalid email",
            field="email",
            value="not-an-email"
        )
        assert error.details["field"] == "email"
        assert error.details["value"] == "not-an-email"
    
    def test_with_existing_details(self):
        """Test that field/value merge with existing details."""
        existing = {"validator": "email_regex"}
        error = ValidationError(
            "Invalid format",
            field="email",
            value="bad@",
            details=existing
        )
        assert error.details["validator"] == "email_regex"
        assert error.details["field"] == "email"
        assert error.details["value"] == "bad@"


class TestProviderError:
    """Test ProviderError class."""
    
    def test_provider_name_required(self):
        """Test provider name is included."""
        error = ProviderError("whisper", "Provider failed")
        assert error.details["provider"] == "whisper"
        assert error.severity == ErrorSeverity.WARNING
    
    def test_provider_error_string(self):
        """Test string representation includes provider."""
        error = ProviderError("neo4j", "Connection lost")
        error_str = str(error)
        assert "[WARNING] Connection lost" in error_str
        assert "'provider': 'neo4j'" in error_str
    
    def test_with_additional_details(self):
        """Test merging provider name with other details."""
        details = {"retry_count": 3, "last_error": "timeout"}
        error = ProviderError("gemini", "API error", details=details)
        assert error.details["provider"] == "gemini"
        assert error.details["retry_count"] == 3
        assert error.details["last_error"] == "timeout"


class TestCriticalError:
    """Test CriticalError class."""
    
    def test_always_critical(self):
        """Test critical errors are always CRITICAL severity."""
        error = CriticalError("System failure")
        assert error.severity == ErrorSeverity.CRITICAL
        assert str(error) == "[CRITICAL] System failure"


class TestExtractionError:
    """Test ExtractionError class."""
    
    def test_default_warning(self):
        """Test extraction errors default to warning."""
        error = ExtractionError("Entity extraction failed")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_can_be_critical(self):
        """Test can create critical extraction error."""
        error = ExtractionError("Complete extraction failure", ErrorSeverity.CRITICAL)
        assert error.severity == ErrorSeverity.CRITICAL


class TestRateLimitError:
    """Test RateLimitError class."""
    
    def test_basic_rate_limit(self):
        """Test basic rate limit error."""
        error = RateLimitError("openai", "Rate limit hit")
        assert error.severity == ErrorSeverity.WARNING
        assert error.details["provider"] == "openai"
    
    def test_with_retry_after(self):
        """Test rate limit with retry information."""
        error = RateLimitError(
            "anthropic",
            "Too many requests",
            retry_after=60.5
        )
        assert error.details["retry_after"] == 60.5
        assert error.details["provider"] == "anthropic"
    
    def test_with_additional_details(self):
        """Test with both retry_after and other details."""
        details = {"requests_made": 100, "limit": 100}
        error = RateLimitError(
            "gemini",
            "Quota exceeded",
            retry_after=300,
            details=details
        )
        assert error.details["retry_after"] == 300
        assert error.details["requests_made"] == 100
        assert error.details["limit"] == 100
        assert error.details["provider"] == "gemini"


class TestTimeoutError:
    """Test TimeoutError class."""
    
    def test_basic_timeout(self):
        """Test basic timeout error."""
        error = TimeoutError("Operation timed out")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_with_operation_details(self):
        """Test timeout with operation information."""
        error = TimeoutError(
            "Transcription timeout",
            operation="whisper_transcribe",
            timeout_seconds=300.0
        )
        assert error.details["operation"] == "whisper_transcribe"
        assert error.details["timeout_seconds"] == 300.0
    
    def test_with_all_details(self):
        """Test with operation, timeout, and extra details."""
        details = {"file_size_mb": 150}
        error = TimeoutError(
            "Large file timeout",
            operation="audio_processing",
            timeout_seconds=600,
            details=details
        )
        assert error.details["operation"] == "audio_processing"
        assert error.details["timeout_seconds"] == 600
        assert error.details["file_size_mb"] == 150


class TestResourceError:
    """Test ResourceError class."""
    
    def test_default_critical(self):
        """Test resource errors are critical by default."""
        error = ResourceError("Out of memory")
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_with_resource_type(self):
        """Test with specific resource type."""
        error = ResourceError(
            "Disk space exhausted",
            resource_type="disk"
        )
        assert error.details["resource_type"] == "disk"
        assert str(error) == "[CRITICAL] Disk space exhausted | Details: {'resource_type': 'disk'}"
    
    def test_memory_resource_error(self):
        """Test memory-specific resource error."""
        details = {"available_mb": 100, "required_mb": 8000}
        error = ResourceError(
            "Insufficient memory",
            resource_type="memory",
            details=details
        )
        assert error.details["resource_type"] == "memory"
        assert error.details["available_mb"] == 100
        assert error.details["required_mb"] == 8000


class TestDataIntegrityError:
    """Test DataIntegrityError class."""
    
    def test_default_critical(self):
        """Test data integrity errors are critical."""
        error = DataIntegrityError("Corrupted data")
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_with_entity_info(self):
        """Test with entity type and ID."""
        error = DataIntegrityError(
            "Missing required field",
            entity_type="Episode",
            entity_id="ep_123"
        )
        assert error.details["entity_type"] == "Episode"
        assert error.details["entity_id"] == "ep_123"
    
    def test_with_full_details(self):
        """Test with all parameters."""
        details = {"missing_fields": ["title", "audio_url"]}
        error = DataIntegrityError(
            "Invalid episode data",
            entity_type="Episode",
            entity_id="ep_456",
            details=details
        )
        assert error.details["entity_type"] == "Episode"
        assert error.details["entity_id"] == "ep_456"
        assert error.details["missing_fields"] == ["title", "audio_url"]


class TestParsingError:
    """Test ParsingError class."""
    
    def test_default_warning(self):
        """Test parsing errors default to warning."""
        error = ParsingError("Invalid JSON")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_with_parse_details(self):
        """Test with parsing context."""
        details = {
            "line": 42,
            "column": 15,
            "expected": "string",
            "found": "number"
        }
        error = ParsingError("JSON parse error", details=details)
        assert error.details["line"] == 42
        assert error.details["column"] == 15


class TestCheckpointError:
    """Test CheckpointError class."""
    
    def test_default_warning(self):
        """Test checkpoint errors are warnings by default."""
        error = CheckpointError("Failed to save checkpoint")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_critical_checkpoint_error(self):
        """Test can create critical checkpoint error."""
        error = CheckpointError(
            "Checkpoint corruption",
            ErrorSeverity.CRITICAL,
            {"checkpoint_id": "ckpt_789"}
        )
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.details["checkpoint_id"] == "ckpt_789"


class TestBatchProcessingError:
    """Test BatchProcessingError class."""
    
    def test_default_warning(self):
        """Test batch errors default to warning."""
        error = BatchProcessingError("Batch failed")
        assert error.severity == ErrorSeverity.WARNING
    
    def test_with_batch_details(self):
        """Test with batch processing details."""
        details = {
            "batch_size": 100,
            "failed_items": 15,
            "success_items": 85
        }
        error = BatchProcessingError("Partial batch failure", details=details)
        assert error.details["batch_size"] == 100
        assert error.details["failed_items"] == 15


class TestAliases:
    """Test backward compatibility aliases."""
    
    def test_podcast_kg_error_alias(self):
        """Test PodcastKGError is alias for PodcastProcessingError."""
        error = PodcastKGError("Using legacy name")
        assert isinstance(error, PodcastProcessingError)
        assert error.message == "Using legacy name"
    
    def test_connection_error_alias(self):
        """Test ConnectionError is alias for DatabaseConnectionError."""
        error = ConnectionError("Using old name")
        assert isinstance(error, DatabaseConnectionError)
        assert error.severity == ErrorSeverity.CRITICAL


class TestExceptionHierarchy:
    """Test the exception hierarchy and inheritance."""
    
    def test_all_inherit_from_base(self):
        """Test all custom exceptions inherit from PodcastProcessingError."""
        exceptions = [
            DatabaseConnectionError("test"),
            AudioProcessingError("test"),
            LLMProcessingError("test"),
            ConfigurationError("test"),
            PipelineError("test"),
            ValidationError("test"),
            ProviderError("provider", "test"),
            CriticalError("test"),
            ExtractionError("test"),
            RateLimitError("provider", "test"),
            TimeoutError("test"),
            ResourceError("test"),
            DataIntegrityError("test"),
            ParsingError("test"),
            CheckpointError("test"),
            BatchProcessingError("test"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, PodcastProcessingError)
            assert isinstance(exc, Exception)
    
    def test_provider_error_hierarchy(self):
        """Test RateLimitError inherits from ProviderError."""
        error = RateLimitError("test_provider", "rate limited")
        assert isinstance(error, ProviderError)
        assert isinstance(error, PodcastProcessingError)


class TestExceptionUsagePatterns:
    """Test common usage patterns for exceptions."""
    
    def test_catching_specific_exceptions(self):
        """Test catching specific exception types."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Bad config")
        
        with pytest.raises(RateLimitError):
            raise RateLimitError("openai", "Too fast")
    
    def test_catching_by_base_class(self):
        """Test catching exceptions by base class."""
        exceptions_raised = 0
        
        for ExcClass in [ConfigurationError, AudioProcessingError, ValidationError]:
            try:
                raise ExcClass("Test error")
            except PodcastProcessingError:
                exceptions_raised += 1
        
        assert exceptions_raised == 3
    
    def test_exception_context_preservation(self):
        """Test that exception context is preserved."""
        original = ValueError("Original error")
        
        try:
            raise original
        except ValueError as e:
            error = PipelineError(f"Pipeline failed: {e}", details={"original": str(e)})
            assert "Original error" in error.details["original"]
            assert error.severity == ErrorSeverity.CRITICAL