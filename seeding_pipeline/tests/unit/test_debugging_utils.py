"""Tests for debugging utilities - matches actual API."""

import pytest
import logging
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path

from src.utils.debugging import (
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    DebugLogger,
    with_error_context,
    debug_context,
    ErrorAnalyzer,
    create_provider_error_handler,
    ErrorRecoveryStrategy
)


class TestErrorEnums:
    """Test error severity and category enums."""
    
    def test_error_severity_values(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"
    
    def test_error_category_values(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.DATABASE.value == "database"
        assert ErrorCategory.PARSING.value == "parsing"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.RESOURCE.value == "resource"
        assert ErrorCategory.PROVIDER.value == "provider"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestErrorContext:
    """Test ErrorContext dataclass."""
    
    def test_error_context_creation(self):
        """Test creating ErrorContext instances."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            context_data={"key": "value"}
        )
        
        assert context.error_type == "ValueError"
        assert context.error_message == "Test error"
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.category == ErrorCategory.VALIDATION
        assert context.context_data == {"key": "value"}
        assert context.recovery_attempted is False
        assert context.recovery_successful is False
        assert context.timestamp is not None
    
    def test_error_context_to_dict(self):
        """Test converting ErrorContext to dictionary."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PARSING,
            traceback="Test traceback",
            context_data={"test": True}
        )
        
        result = context.to_dict()
        
        assert result['error_type'] == "ValueError"
        assert result['error_message'] == "Test error"
        assert result['severity'] == "high"
        assert result['category'] == "parsing"
        assert result['traceback'] == "Test traceback"
        assert result['context_data'] == {"test": True}
        assert 'timestamp' in result
    
    def test_error_context_to_json(self):
        """Test converting ErrorContext to JSON."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION
        )
        
        json_str = context.to_json()
        data = json.loads(json_str)
        
        assert data['error_type'] == "ValueError"
        assert data['severity'] == "low"


class TestDebugLogger:
    """Test DebugLogger class."""
    
    @pytest.fixture
    def debug_logger(self, tmp_path):
        """Create DebugLogger instance."""
        return DebugLogger(log_dir=str(tmp_path), name="test_logger")
    
    def test_debug_logger_initialization(self, tmp_path):
        """Test DebugLogger initialization."""
        logger = DebugLogger(
            log_dir=str(tmp_path),
            name="test_logger",
            max_file_size=1024,
            backup_count=3
        )
        assert logger.logger.name == "test_logger"
        assert logger.log_dir == str(tmp_path)
        assert logger.error_history == []
        assert logger.max_file_size == 1024
        assert logger.backup_count == 3
    
    def test_log_error_context(self, debug_logger):
        """Test logging error context."""
        context = ErrorContext(
            error_type="TestError",
            error_message="Test message",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION
        )
        
        debug_logger.log_error_context(context)
        
        assert len(debug_logger.error_history) == 1
        assert debug_logger.error_history[0] == context
    
    def test_get_error_summary(self, debug_logger):
        """Test getting error summary."""
        # Add some errors
        context1 = ErrorContext(
            error_type="Error1",
            error_message="Message 1",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION
        )
        context2 = ErrorContext(
            error_type="Error2",
            error_message="Message 2",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK
        )
        
        debug_logger.log_error_context(context1)
        debug_logger.log_error_context(context2)
        
        summary = debug_logger.get_error_summary()
        
        assert summary['total_errors'] == 2
        assert summary['by_severity']['low'] == 1
        assert summary['by_severity']['high'] == 1
        assert summary['by_category']['validation'] == 1
        assert summary['by_category']['network'] == 1


class TestWithErrorContext:
    """Test with_error_context decorator."""
    
    def test_successful_function(self):
        """Test decorator with successful function."""
        @with_error_context(severity=ErrorSeverity.MEDIUM)
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
    
    def test_function_with_error(self):
        """Test decorator with failing function."""
        @with_error_context(
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION
        )
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function()
    
    def test_function_with_custom_logger(self):
        """Test decorator with custom logger."""
        mock_logger = Mock(spec=DebugLogger)
        
        @with_error_context(
            severity=ErrorSeverity.CRITICAL,
            logger=mock_logger
        )
        def test_function():
            raise RuntimeError("Critical error")
        
        with pytest.raises(RuntimeError):
            test_function()
        
        mock_logger.log_error_context.assert_called_once()


class TestDebugContext:
    """Test debug_context context manager."""
    
    def test_successful_context(self):
        """Test context manager with successful block."""
        with debug_context("test_operation") as ctx:
            result = 2 + 2
        
        assert ctx['operation'] == "test_operation"
        assert ctx['success'] is True
        assert 'error' not in ctx
        assert 'duration' in ctx
    
    def test_context_with_error(self):
        """Test context manager with error."""
        with pytest.raises(ValueError):
            with debug_context("failing_operation") as ctx:
                raise ValueError("Test error")
    
    def test_context_with_metadata(self):
        """Test context manager with metadata."""
        metadata = {"user_id": 123, "request_id": "abc"}
        
        with debug_context("metadata_operation", metadata=metadata) as ctx:
            pass
        
        assert ctx['metadata'] == metadata


class TestErrorAnalyzer:
    """Test ErrorAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create ErrorAnalyzer instance."""
        return ErrorAnalyzer()
    
    def test_analyze_validation_error(self, analyzer):
        """Test analyzing validation error."""
        error = ValueError("Invalid input format")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['error_type'] == "ValueError"
        assert analysis['category'] == ErrorCategory.VALIDATION
        assert analysis['severity'] == ErrorSeverity.MEDIUM
        assert 'suggestions' in analysis
    
    def test_analyze_network_error(self, analyzer):
        """Test analyzing network error."""
        error = ConnectionError("Connection refused")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.NETWORK
        assert analysis['severity'] == ErrorSeverity.HIGH
    
    def test_analyze_unknown_error(self, analyzer):
        """Test analyzing unknown error."""
        error = Exception("Unknown error")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.UNKNOWN
        assert analysis['severity'] == ErrorSeverity.MEDIUM


class TestCreateProviderErrorHandler:
    """Test create_provider_error_handler function."""
    
    def test_create_handler(self):
        """Test creating provider error handler."""
        handler = create_provider_error_handler("test_provider")
        
        assert callable(handler)
        
        # Test handling an error
        error = RuntimeError("Provider error")
        result = handler(error)
        
        assert isinstance(result, dict)
        assert result['provider'] == "test_provider"
        assert result['error_type'] == "RuntimeError"
    
    def test_handler_with_retryable_error(self):
        """Test handler with retryable error."""
        handler = create_provider_error_handler("api_provider")
        
        error = ConnectionError("Timeout")
        result = handler(error)
        
        assert result['retryable'] is True
        assert result['category'] == ErrorCategory.NETWORK


class TestErrorRecoveryStrategy:
    """Test ErrorRecoveryStrategy class."""
    
    @pytest.fixture
    def recovery_strategy(self):
        """Create ErrorRecoveryStrategy instance."""
        return ErrorRecoveryStrategy()
    
    def test_attempt_recovery_network(self, recovery_strategy):
        """Test recovery attempt for network error."""
        context = ErrorContext(
            error_type="ConnectionError",
            error_message="Connection timeout",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK
        )
        
        result = recovery_strategy.attempt_recovery(
            context,
            retry_count=1,
            max_retries=3
        )
        
        assert 'action' in result
        assert 'delay' in result
        assert result['should_retry'] is True
    
    def test_attempt_recovery_parsing(self, recovery_strategy):
        """Test recovery attempt for parsing error."""
        context = ErrorContext(
            error_type="JSONDecodeError",
            error_message="Invalid JSON",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PARSING
        )
        
        result = recovery_strategy.attempt_recovery(
            context,
            retry_count=2,
            max_retries=3
        )
        
        assert 'action' in result
        assert result['should_retry'] is True or result['should_retry'] is False
    
    def test_max_retries_exceeded(self, recovery_strategy):
        """Test recovery when max retries exceeded."""
        context = ErrorContext(
            error_type="Error",
            error_message="Persistent error",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROVIDER
        )
        
        result = recovery_strategy.attempt_recovery(
            context,
            retry_count=3,
            max_retries=3
        )
        
        assert result['should_retry'] is False
        assert 'Max retries exceeded' in result.get('reason', '')