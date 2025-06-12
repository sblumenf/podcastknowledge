"""Comprehensive unit tests for debugging utilities."""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import json
import logging

import pytest

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


class TestErrorSeverity:
    """Test ErrorSeverity enum."""
    
    def test_severity_values(self):
        """Test severity level values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestErrorCategory:
    """Test ErrorCategory enum."""
    
    def test_category_values(self):
        """Test error category values."""
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
        """Test creating error context."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION
        )
        
        assert context.error_type == "ValueError"
        assert context.error_message == "Test error"
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.category == ErrorCategory.VALIDATION
        assert context.recovery_attempted is False
        assert context.recovery_successful is False
        assert isinstance(context.timestamp, str)
        assert context.traceback is None
        assert context.context_data == {}
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary."""
        context = ErrorContext(
            error_type="TestError",
            error_message="Test message",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK,
            traceback="Test traceback",
            context_data={"key": "value"},
            recovery_attempted=True,
            recovery_successful=False
        )
        
        result = context.to_dict()
        
        assert result["error_type"] == "TestError"
        assert result["error_message"] == "Test message"
        assert result["severity"] == "high"
        assert result["category"] == "network"
        assert result["traceback"] == "Test traceback"
        assert result["context_data"] == {"key": "value"}
        assert result["recovery_attempted"] is True
        assert result["recovery_successful"] is False
        assert "timestamp" in result
    
    def test_error_context_to_json(self):
        """Test converting error context to JSON."""
        context = ErrorContext(
            error_type="JSONError",
            error_message="JSON test",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.PARSING
        )
        
        json_str = context.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["error_type"] == "JSONError"
        assert parsed["error_message"] == "JSON test"
        assert parsed["severity"] == "low"
        assert parsed["category"] == "parsing"


class TestDebugLogger:
    """Test DebugLogger class."""
    
    def test_debug_logger_initialization(self):
        """Test debug logger initialization."""
        logger = DebugLogger("test_logger", debug_mode=False)
        
        assert logger.debug_mode is False
        assert logger.error_history == []
        assert logger.logger.level == logging.INFO
    
    def test_debug_logger_debug_mode(self):
        """Test debug logger in debug mode."""
        logger = DebugLogger("test_debug", debug_mode=True)
        
        assert logger.debug_mode is True
        assert logger.logger.level == logging.DEBUG
    
    @patch('logging.FileHandler')
    def test_debug_logger_with_file(self, mock_file_handler):
        """Test debug logger with file output."""
        logger = DebugLogger("test_file", log_file="test.log")
        
        mock_file_handler.assert_called_once_with("test.log")
    
    def test_log_error_context(self):
        """Test logging error context."""
        logger = DebugLogger("test_context", debug_mode=True)
        
        context = ErrorContext(
            error_type="TestError",
            error_message="Test message",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.DATABASE
        )
        
        with patch.object(logger.logger, 'critical') as mock_critical:
            logger.log_error_context(context)
            
            assert len(logger.error_history) == 1
            assert logger.error_history[0] == context
            mock_critical.assert_called_once()
    
    def test_log_error_context_different_severities(self):
        """Test logging errors with different severities."""
        logger = DebugLogger("test_severities")
        
        # Test critical
        with patch.object(logger.logger, 'critical') as mock_critical:
            context = ErrorContext(
                error_type="Critical",
                error_message="Critical error",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.RESOURCE
            )
            logger.log_error_context(context)
            mock_critical.assert_called_once()
        
        # Test high
        with patch.object(logger.logger, 'error') as mock_error:
            context = ErrorContext(
                error_type="High",
                error_message="High error",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.RESOURCE
            )
            logger.log_error_context(context)
            mock_error.assert_called_once()
        
        # Test medium
        with patch.object(logger.logger, 'warning') as mock_warning:
            context = ErrorContext(
                error_type="Medium",
                error_message="Medium error",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.RESOURCE
            )
            logger.log_error_context(context)
            mock_warning.assert_called_once()
        
        # Test low
        with patch.object(logger.logger, 'info') as mock_info:
            context = ErrorContext(
                error_type="Low",
                error_message="Low error",
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.RESOURCE
            )
            logger.log_error_context(context)
            mock_info.assert_called_once()
    
    def test_get_error_summary(self):
        """Test getting error summary."""
        logger = DebugLogger("test_summary")
        
        # Add various errors
        errors = [
            ErrorContext(
                error_type="Error1",
                error_message="Message1",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.NETWORK,
                recovery_attempted=True,
                recovery_successful=True
            ),
            ErrorContext(
                error_type="Error2",
                error_message="Message2",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE,
                recovery_attempted=True,
                recovery_successful=False
            ),
            ErrorContext(
                error_type="Error3",
                error_message="Message3",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.NETWORK
            )
        ]
        
        for error in errors:
            logger.log_error_context(error)
        
        summary = logger.get_error_summary()
        
        assert summary['total_errors'] == 3
        assert summary['by_severity']['high'] == 2
        assert summary['by_severity']['medium'] == 1
        assert summary['by_category']['network'] == 2
        assert summary['by_category']['database'] == 1
        assert summary['recovery_stats']['attempted'] == 2
        assert summary['recovery_stats']['successful'] == 1


class TestWithErrorContext:
    """Test with_error_context decorator."""
    
    def test_decorator_success(self):
        """Test decorator with successful function."""
        @with_error_context(
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            context_keys=['user_id']
        )
        def test_function(user_id, data):
            return f"Success: {user_id}"
        
        result = test_function(123, "test_data")
        assert result == "Success: 123"
    
    def test_decorator_with_error(self):
        """Test decorator with function that raises error."""
        @with_error_context(
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.VALIDATION,
            context_keys=['value']
        )
        def test_function(value):
            raise ValueError(f"Invalid value: {value}")
        
        with pytest.raises(ValueError) as exc_info:
            test_function("bad_value")
        
        # Check that error context was attached
        assert hasattr(exc_info.value, 'error_context')
        context = exc_info.value.error_context
        assert context.error_type == "ValueError"
        assert context.severity == ErrorSeverity.CRITICAL
        assert context.category == ErrorCategory.VALIDATION
        assert context.context_data['value'] == "bad_value"
    
    @patch('logging.getLogger')
    def test_decorator_logging(self, mock_get_logger):
        """Test decorator logs errors."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        @with_error_context()
        def test_function():
            raise RuntimeError("Test error")
        
        with pytest.raises(RuntimeError):
            test_function()
        
        mock_logger.error.assert_called_once()


class TestDebugContext:
    """Test debug_context context manager."""
    
    @patch('logging.getLogger')
    def test_debug_context_success(self, mock_get_logger):
        """Test debug context with successful operation."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with debug_context("test_operation", user_id=123, batch_size=100):
            pass
        
        # Check start and completion logs
        assert mock_logger.debug.call_count == 2
        start_call = mock_logger.debug.call_args_list[0]
        assert "Starting test_operation" in start_call[0][0]
        
        end_call = mock_logger.debug.call_args_list[1]
        assert "Completed test_operation" in end_call[0][0]
    
    @patch('logging.getLogger')
    def test_debug_context_with_error(self, mock_get_logger):
        """Test debug context with error."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with pytest.raises(ValueError):
            with debug_context("failing_operation", data="test"):
                raise ValueError("Test failure")
        
        # Check error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed failing_operation" in error_call
    
    def test_debug_context_with_custom_logger(self):
        """Test debug context with custom logger."""
        custom_logger = Mock()
        
        with debug_context("custom_op", logger=custom_logger, key="value"):
            pass
        
        assert custom_logger.debug.call_count == 2


class TestErrorAnalyzer:
    """Test ErrorAnalyzer class."""
    
    def test_error_analyzer_initialization(self):
        """Test error analyzer initialization."""
        analyzer = ErrorAnalyzer()
        
        assert isinstance(analyzer.error_patterns, dict)
        assert len(analyzer.error_patterns) > 0
    
    def test_analyze_network_error(self):
        """Test analyzing network errors."""
        analyzer = ErrorAnalyzer()
        
        # Test rate limit error
        error = Exception("Rate limit exceeded")
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.NETWORK
        assert result['severity'] == ErrorSeverity.MEDIUM
        assert 'rate limiting' in result['suggestion'].lower()
    
    def test_analyze_database_error(self):
        """Test analyzing database errors."""
        analyzer = ErrorAnalyzer()
        
        error = Exception("Connection refused to database")
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.DATABASE
        assert result['severity'] == ErrorSeverity.HIGH
        assert 'database connection' in result['suggestion'].lower()
    
    def test_analyze_parsing_error(self):
        """Test analyzing parsing errors."""
        analyzer = ErrorAnalyzer()
        
        error = json.JSONDecodeError("Invalid JSON", "doc", 0)
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.PARSING
        assert result['severity'] == ErrorSeverity.MEDIUM
        assert 'validate input' in result['suggestion'].lower()
    
    def test_analyze_resource_error(self):
        """Test analyzing resource errors."""
        analyzer = ErrorAnalyzer()
        
        # Test memory error
        error = MemoryError("Out of memory")
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.RESOURCE
        assert result['severity'] == ErrorSeverity.CRITICAL
        assert 'memory' in result['suggestion'].lower()
        
        # Test disk space error
        error = OSError("No space left on device")
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.RESOURCE
        assert result['severity'] == ErrorSeverity.HIGH
        assert 'disk space' in result['suggestion'].lower()
    
    def test_analyze_unknown_error(self):
        """Test analyzing unknown errors."""
        analyzer = ErrorAnalyzer()
        
        error = Exception("Some random error")
        result = analyzer.analyze_error(error)
        
        assert result['category'] == ErrorCategory.UNKNOWN
        assert result['severity'] == ErrorSeverity.MEDIUM
        assert result['matched_pattern'] is None


class TestCreateProviderErrorHandler:
    """Test create_provider_error_handler function."""
    
    def test_openai_rate_limit_handler(self):
        """Test OpenAI rate limit error handling."""
        handler = create_provider_error_handler('openai')
        
        error = Exception("Rate limit exceeded")
        result = handler(error)
        
        assert result['retry'] is True
        assert result['wait_time'] == 60
        assert result['fallback'] == 'gemini'
    
    def test_openai_context_length_handler(self):
        """Test OpenAI context length error handling."""
        handler = create_provider_error_handler('openai')
        
        error = Exception("Maximum context length exceeded")
        result = handler(error)
        
        assert result['retry'] is True
        assert result['reduce_context'] is True
        assert result['fallback'] is None
    
    def test_gemini_quota_handler(self):
        """Test Gemini quota error handling."""
        handler = create_provider_error_handler('gemini')
        
        error = Exception("Quota exceeded")
        result = handler(error)
        
        assert result['retry'] is True
        assert result['wait_time'] == 300
        assert result['fallback'] == 'openai'
    
    def test_gemini_invalid_handler(self):
        """Test Gemini invalid request error handling."""
        handler = create_provider_error_handler('gemini')
        
        error = Exception("Invalid request")
        result = handler(error)
        
        assert result['retry'] is False
        assert result['log_error'] is True
        assert result['fallback'] is None
    
    def test_unknown_provider_handler(self):
        """Test unknown provider error handling."""
        handler = create_provider_error_handler('unknown')
        
        error = Exception("Some error")
        result = handler(error)
        
        assert result['retry'] is False
        assert result['log_error'] is True
        assert result['fallback'] is None


class TestErrorRecoveryStrategy:
    """Test ErrorRecoveryStrategy class."""
    
    def test_recovery_strategy_initialization(self):
        """Test recovery strategy initialization."""
        strategy = ErrorRecoveryStrategy()
        
        assert ErrorCategory.NETWORK in strategy.strategies
        assert ErrorCategory.DATABASE in strategy.strategies
        assert ErrorCategory.PARSING in strategy.strategies
        assert ErrorCategory.RESOURCE in strategy.strategies
        assert ErrorCategory.PROVIDER in strategy.strategies
    
    @patch('time.sleep')
    def test_network_recovery(self, mock_sleep):
        """Test network error recovery."""
        strategy = ErrorRecoveryStrategy()
        
        context = ErrorContext(
            error_type="TimeoutError",
            error_message="Connection timeout",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK
        )
        
        retry_called = False
        def retry_func():
            nonlocal retry_called
            retry_called = True
        
        result = strategy.attempt_recovery(context, retry_func)
        
        assert result is True
        assert retry_called is True
        mock_sleep.assert_called_once_with(5)
    
    def test_database_recovery(self):
        """Test database error recovery."""
        strategy = ErrorRecoveryStrategy()
        
        context = ErrorContext(
            error_type="DatabaseError",
            error_message="Connection lost",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE
        )
        
        result = strategy.attempt_recovery(context)
        
        # Database recovery not implemented, should return False
        assert result is False
    
    @patch('gc.collect')
    def test_resource_memory_recovery(self, mock_gc):
        """Test resource memory error recovery."""
        strategy = ErrorRecoveryStrategy()
        
        context = ErrorContext(
            error_type="MemoryError",
            error_message="Out of memory",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.RESOURCE
        )
        
        retry_called = False
        def retry_func():
            nonlocal retry_called
            retry_called = True
        
        result = strategy.attempt_recovery(context, retry_func)
        
        assert result is True
        assert retry_called is True
        mock_gc.assert_called_once()
    
    def test_unknown_category_recovery(self):
        """Test recovery for unknown category."""
        strategy = ErrorRecoveryStrategy()
        
        context = ErrorContext(
            error_type="UnknownError",
            error_message="Unknown error",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.UNKNOWN
        )
        
        result = strategy.attempt_recovery(context)
        
        assert result is False