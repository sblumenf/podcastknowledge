"""Tests for debugging and error handling utilities."""

import pytest
import json
import logging
import tempfile
from unittest.mock import Mock, patch, MagicMock
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


class TestErrorContext:
    """Tests for ErrorContext class."""
    
    def test_error_context_creation(self):
        """Test creating error context."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Invalid value",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            context_data={"value": "test", "field": "name"}
        )
        
        assert context.error_type == "ValueError"
        assert context.error_message == "Invalid value"
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.category == ErrorCategory.VALIDATION
        assert context.context_data == {"value": "test", "field": "name"}
        assert context.recovery_attempted is False
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary."""
        context = ErrorContext(
            error_type="RuntimeError",
            error_message="Test error",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.UNKNOWN,
            traceback="Traceback details..."
        )
        
        result = context.to_dict()
        assert result['error_type'] == "RuntimeError"
        assert result['severity'] == "high"
        assert result['category'] == "unknown"
        assert result['traceback'] == "Traceback details..."
    
    def test_error_context_to_json(self):
        """Test converting error context to JSON."""
        context = ErrorContext(
            error_type="TypeError",
            error_message="Type mismatch",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.PARSING
        )
        
        json_str = context.to_json()
        parsed = json.loads(json_str)
        
        assert parsed['error_type'] == "TypeError"
        assert parsed['severity'] == "low"
        assert parsed['category'] == "parsing"


class TestDebugLogger:
    """Tests for DebugLogger class."""
    
    def test_debug_logger_creation(self):
        """Test creating debug logger."""
        logger = DebugLogger("test_logger", debug_mode=True)
        
        assert logger.debug_mode is True
        assert logger.logger.level == logging.DEBUG
        assert len(logger.error_history) == 0
    
    def test_log_error_context(self):
        """Test logging error context."""
        logger = DebugLogger("test_logger")
        
        context = ErrorContext(
            error_type="TestError",
            error_message="Test message",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE
        )
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.log_error_context(context)
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0][0]
            assert "[database]" in call_args
            assert "Test message" in call_args
        
        assert len(logger.error_history) == 1
        assert logger.error_history[0] == context
    
    def test_log_error_context_severity_levels(self):
        """Test logging different severity levels."""
        logger = DebugLogger("test_logger")
        
        # Test critical
        critical_context = ErrorContext(
            error_type="CriticalError",
            error_message="Critical failure",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.RESOURCE
        )
        
        with patch.object(logger.logger, 'critical') as mock_critical:
            logger.log_error_context(critical_context)
            mock_critical.assert_called_once()
        
        # Test warning
        warning_context = ErrorContext(
            error_type="Warning",
            error_message="Warning message",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION
        )
        
        with patch.object(logger.logger, 'warning') as mock_warning:
            logger.log_error_context(warning_context)
            mock_warning.assert_called_once()
    
    def test_get_error_summary(self):
        """Test getting error summary."""
        logger = DebugLogger("test_logger")
        
        # Add various errors
        errors = [
            ErrorContext("Error1", "Message1", ErrorSeverity.HIGH, 
                        ErrorCategory.DATABASE, recovery_attempted=True, 
                        recovery_successful=True),
            ErrorContext("Error2", "Message2", ErrorSeverity.HIGH, 
                        ErrorCategory.NETWORK),
            ErrorContext("Error3", "Message3", ErrorSeverity.MEDIUM, 
                        ErrorCategory.DATABASE, recovery_attempted=True,
                        recovery_successful=False),
        ]
        
        for error in errors:
            logger.log_error_context(error)
        
        summary = logger.get_error_summary()
        
        assert summary['total_errors'] == 3
        assert summary['by_severity']['high'] == 2
        assert summary['by_severity']['medium'] == 1
        assert summary['by_category']['database'] == 2
        assert summary['by_category']['network'] == 1
        assert summary['recovery_stats']['attempted'] == 2
        assert summary['recovery_stats']['successful'] == 1
    
    def test_debug_logger_with_file(self):
        """Test debug logger with file output."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_file = f.name
        
        try:
            logger = DebugLogger("test_logger", debug_mode=True, log_file=log_file)
            
            # Log a message
            logger.logger.info("Test message")
            
            # Check file contains the message
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Test message" in content
        finally:
            import os
            os.unlink(log_file)


class TestErrorContextDecorator:
    """Tests for with_error_context decorator."""
    
    def test_successful_function_call(self):
        """Test decorator with successful function call."""
        @with_error_context(severity=ErrorSeverity.HIGH,
                          category=ErrorCategory.DATABASE,
                          context_keys=['user_id'])
        def test_func(user_id):
            return f"Success for {user_id}"
        
        result = test_func(user_id=123)
        assert result == "Success for 123"
    
    def test_function_with_error(self):
        """Test decorator with function that raises error."""
        @with_error_context(severity=ErrorSeverity.MEDIUM,
                          category=ErrorCategory.VALIDATION,
                          context_keys=['value', 'field'])
        def test_func(value, field):
            raise ValueError(f"Invalid {field}: {value}")
        
        with pytest.raises(ValueError) as exc_info:
            test_func(value="bad", field="email")
        
        # Check error context is attached
        assert hasattr(exc_info.value, 'error_context')
        context = exc_info.value.error_context
        assert context.error_type == "ValueError"
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.category == ErrorCategory.VALIDATION
        assert context.context_data == {'value': 'bad', 'field': 'email'}


class TestDebugContext:
    """Tests for debug_context context manager."""
    
    def test_successful_operation(self):
        """Test debug context with successful operation."""
        mock_logger = Mock()
        
        with debug_context("test_operation", logger=mock_logger, 
                         user_id=123, batch_size=100):
            # Simulate operation
            pass
        
        # Check start and completion logged
        assert mock_logger.debug.call_count == 2
        start_call = mock_logger.debug.call_args_list[0][0][0]
        assert "Starting test_operation" in start_call
        assert "user_id" in start_call
        
        complete_call = mock_logger.debug.call_args_list[1][0][0]
        assert "Completed test_operation" in complete_call
    
    def test_failed_operation(self):
        """Test debug context with failed operation."""
        mock_logger = Mock()
        
        with pytest.raises(RuntimeError):
            with debug_context("failing_operation", logger=mock_logger,
                             param="value"):
                raise RuntimeError("Operation failed")
        
        # Check error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed failing_operation" in error_call
        assert "Operation failed" in error_call


class TestErrorAnalyzer:
    """Tests for ErrorAnalyzer class."""
    
    def test_analyze_rate_limit_error(self):
        """Test analyzing rate limit error."""
        analyzer = ErrorAnalyzer()
        error = Exception("429 Too Many Requests")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.NETWORK
        assert analysis['severity'] == ErrorSeverity.MEDIUM
        assert 'rate limiting' in analysis['suggestion']
    
    def test_analyze_database_error(self):
        """Test analyzing database connection error."""
        analyzer = ErrorAnalyzer()
        error = Exception("Connection refused to database")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.DATABASE
        assert analysis['severity'] == ErrorSeverity.HIGH
        assert 'database connection' in analysis['suggestion']
    
    def test_analyze_memory_error(self):
        """Test analyzing memory error."""
        analyzer = ErrorAnalyzer()
        error = MemoryError("Out of memory")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.RESOURCE
        assert analysis['severity'] == ErrorSeverity.CRITICAL
        assert 'memory management' in analysis['suggestion']
    
    def test_analyze_unknown_error(self):
        """Test analyzing unknown error."""
        analyzer = ErrorAnalyzer()
        error = Exception("Some random error")
        
        analysis = analyzer.analyze_error(error)
        
        assert analysis['category'] == ErrorCategory.UNKNOWN
        assert analysis['matched_pattern'] is None


class TestProviderErrorHandler:
    """Tests for provider-specific error handlers."""
    
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
        error = Exception("Context length exceeded")
        
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
    
    def test_unknown_provider_error(self):
        """Test handling unknown provider error."""
        handler = create_provider_error_handler('unknown_provider')
        error = Exception("Some error")
        
        result = handler(error)
        
        assert result['retry'] is False
        assert result['log_error'] is True
        assert result['fallback'] is None


class TestErrorRecoveryStrategy:
    """Tests for ErrorRecoveryStrategy class."""
    
    def test_network_timeout_recovery(self):
        """Test recovery from network timeout."""
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
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = strategy.attempt_recovery(context, retry_func)
        
        assert result is True
        assert retry_called is True
    
    def test_memory_error_recovery(self):
        """Test recovery from memory error."""
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
        
        with patch('gc.collect') as mock_gc:
            result = strategy.attempt_recovery(context, retry_func)
        
        mock_gc.assert_called_once()
        assert result is True
        assert retry_called is True
    
    def test_no_recovery_strategy(self):
        """Test when no recovery strategy exists."""
        strategy = ErrorRecoveryStrategy()
        context = ErrorContext(
            error_type="UnknownError",
            error_message="Unknown error",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.UNKNOWN
        )
        
        result = strategy.attempt_recovery(context)
        assert result is False