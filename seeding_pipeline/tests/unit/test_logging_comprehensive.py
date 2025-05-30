"""Comprehensive tests for logging utilities."""

import pytest
import logging
import json
import sys
import io
import tempfile
import os
from unittest.mock import Mock, patch, call
from datetime import datetime
from typing import Dict, Any, List
import threading
import asyncio
import time

from src.utils.logging import (
    # Core logging classes
    StructuredLogger,
    LogContext,
    LogFormatter,
    JSONFormatter,
    ColoredFormatter,
    
    # Log handlers
    RotatingFileHandler,
    TimedRotatingFileHandler,
    AsyncHandler,
    BufferedHandler,
    FilteredHandler,
    
    # Utilities
    get_logger,
    configure_logging,
    set_log_level,
    add_handler,
    remove_handler,
    
    # Context managers
    log_context,
    log_performance,
    log_error_context,
    
    # Decorators
    log_calls,
    log_exceptions,
    log_performance_decorator,
    
    # Filters
    LevelFilter,
    NameFilter,
    ContextFilter,
    RateLimitFilter,
    
    # Constants
    LOG_LEVELS,
    DEFAULT_FORMAT,
    DEFAULT_DATE_FORMAT,
)


class TestStructuredLogger:
    """Test StructuredLogger functionality."""
    
    def test_create_logger(self):
        """Test creating a structured logger."""
        logger = StructuredLogger("test.module")
        
        assert logger.name == "test.module"
        assert isinstance(logger.logger, logging.Logger)
        assert logger.context == {}
    
    def test_log_with_structure(self):
        """Test logging with structured data."""
        handler = Mock()
        logger = StructuredLogger("test")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        # Log with extra data
        logger.info("User action", user_id=123, action="login", ip="192.168.1.1")
        
        # Check the call
        assert handler.handle.called
        record = handler.handle.call_args[0][0]
        
        assert record.msg == "User action"
        assert record.user_id == 123
        assert record.action == "login"
        assert record.ip == "192.168.1.1"
    
    def test_log_levels(self):
        """Test different log levels."""
        handler = Mock()
        logger = StructuredLogger("test")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)
        
        # Test all levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        assert handler.handle.call_count == 5
        
        # Check levels
        calls = handler.handle.call_args_list
        assert calls[0][0][0].levelname == "DEBUG"
        assert calls[1][0][0].levelname == "INFO"
        assert calls[2][0][0].levelname == "WARNING"
        assert calls[3][0][0].levelname == "ERROR"
        assert calls[4][0][0].levelname == "CRITICAL"
    
    def test_with_context(self):
        """Test logger with context."""
        handler = Mock()
        logger = StructuredLogger("test")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        # Set context
        logger.set_context(request_id="req-123", user="john")
        
        # Log message
        logger.info("Processing request")
        
        # Check context is included
        record = handler.handle.call_args[0][0]
        assert record.request_id == "req-123"
        assert record.user == "john"
    
    def test_child_logger(self):
        """Test creating child loggers."""
        parent = StructuredLogger("parent")
        parent.set_context(app="myapp")
        
        # Create child
        child = parent.get_child("child")
        
        assert child.name == "parent.child"
        assert child.context["app"] == "myapp"  # Inherits context
        
        # Child can add own context
        child.set_context(module="auth")
        assert child.context["module"] == "auth"
        assert child.context["app"] == "myapp"
    
    def test_clear_context(self):
        """Test clearing logger context."""
        logger = StructuredLogger("test")
        logger.set_context(key1="value1", key2="value2")
        
        assert len(logger.context) == 2
        
        logger.clear_context()
        assert len(logger.context) == 0


class TestLogContext:
    """Test LogContext functionality."""
    
    def test_log_context_manager(self):
        """Test log context manager."""
        logger = StructuredLogger("test")
        handler = Mock()
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        # Use context manager
        with log_context(logger, request_id="123", user="alice"):
            logger.info("Inside context")
            
            # Check context is set
            record = handler.handle.call_args[0][0]
            assert record.request_id == "123"
            assert record.user == "alice"
        
        # Context should be cleared
        logger.info("Outside context")
        record = handler.handle.call_args[0][0]
        assert not hasattr(record, "request_id")
        assert not hasattr(record, "user")
    
    def test_nested_contexts(self):
        """Test nested log contexts."""
        logger = StructuredLogger("test")
        handler = Mock()
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        with log_context(logger, level1="value1"):
            logger.info("Level 1")
            
            with log_context(logger, level2="value2"):
                logger.info("Level 2")
                
                # Both contexts should be present
                record = handler.handle.call_args[0][0]
                assert record.level1 == "value1"
                assert record.level2 == "value2"
            
            # Only level1 context remains
            logger.info("Back to level 1")
            record = handler.handle.call_args[0][0]
            assert record.level1 == "value1"
            assert not hasattr(record, "level2")
    
    def test_context_exception_handling(self):
        """Test context manager handles exceptions."""
        logger = StructuredLogger("test")
        
        try:
            with log_context(logger, operation="risky"):
                logger.set_context(temp="value")
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Context should still be cleaned up
        assert "operation" not in logger.context
        assert "temp" not in logger.context


class TestLogFormatters:
    """Test log formatters."""
    
    def test_json_formatter(self):
        """Test JSON formatter."""
        formatter = JSONFormatter()
        
        # Create log record
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.user_id = 123
        record.action = "login"
        
        # Format record
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["user_id"] == 123
        assert data["action"] == "login"
        assert "timestamp" in data
    
    def test_json_formatter_with_exception(self):
        """Test JSON formatter with exception."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["message"] == "Error occurred"
        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]
        assert "traceback" in data
    
    def test_colored_formatter(self):
        """Test colored formatter."""
        formatter = ColoredFormatter(
            fmt="%(levelname)s: %(message)s",
            use_colors=True
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should contain ANSI color codes
        assert "\033[" in output  # ANSI escape sequence
        assert "Warning message" in output
    
    def test_custom_formatter(self):
        """Test custom formatter."""
        class CustomFormatter(LogFormatter):
            def format_message(self, record):
                return f"[{record.levelname}] {record.name}: {record.getMessage()}"
        
        formatter = CustomFormatter()
        
        record = logging.LogRecord(
            name="myapp",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        assert output == "[INFO] myapp: Hello world"


class TestLogHandlers:
    """Test custom log handlers."""
    
    def test_rotating_file_handler(self):
        """Test rotating file handler."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name
        
        try:
            handler = RotatingFileHandler(
                filename=filename,
                max_bytes=100,  # Small size for testing
                backup_count=3
            )
            
            logger = logging.getLogger("test_rotate")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Log messages to trigger rotation
            for i in range(10):
                logger.info(f"Message {i} " + "x" * 20)
            
            handler.close()
            
            # Check that backup files were created
            assert os.path.exists(f"{filename}.1")
            assert os.path.exists(f"{filename}.2")
            
        finally:
            # Cleanup
            for i in range(5):
                try:
                    if i == 0:
                        os.unlink(filename)
                    else:
                        os.unlink(f"{filename}.{i}")
                except:
                    pass
    
    def test_timed_rotating_handler(self):
        """Test timed rotating file handler."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name
        
        try:
            handler = TimedRotatingFileHandler(
                filename=filename,
                when="S",  # Rotate every second
                interval=1,
                backup_count=2
            )
            
            logger = logging.getLogger("test_timed")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Log over time
            logger.info("Message 1")
            time.sleep(1.1)
            logger.info("Message 2")
            
            handler.close()
            
            # Check log content
            with open(filename, "r") as f:
                content = f.read()
                assert "Message 2" in content
                
        finally:
            os.unlink(filename)
    
    def test_async_handler(self):
        """Test async log handler."""
        mock_handler = Mock()
        async_handler = AsyncHandler(mock_handler)
        
        logger = logging.getLogger("test_async")
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)
        
        # Log multiple messages
        for i in range(5):
            logger.info(f"Async message {i}")
        
        # Allow async processing
        time.sleep(0.1)
        
        # Check all messages were handled
        assert mock_handler.handle.call_count == 5
        
        # Cleanup
        async_handler.close()
    
    def test_buffered_handler(self):
        """Test buffered log handler."""
        mock_handler = Mock()
        buffered = BufferedHandler(
            target_handler=mock_handler,
            buffer_size=3
        )
        
        logger = logging.getLogger("test_buffer")
        logger.addHandler(buffered)
        logger.setLevel(logging.INFO)
        
        # Log less than buffer size
        logger.info("Message 1")
        logger.info("Message 2")
        
        # Should not flush yet
        assert mock_handler.handle.call_count == 0
        
        # Log to reach buffer size
        logger.info("Message 3")
        
        # Should flush now
        assert mock_handler.handle.call_count == 3
        
        # Manual flush
        logger.info("Message 4")
        buffered.flush()
        assert mock_handler.handle.call_count == 4
    
    def test_filtered_handler(self):
        """Test filtered log handler."""
        mock_handler = Mock()
        
        def filter_func(record):
            return record.levelno >= logging.WARNING
        
        filtered = FilteredHandler(
            target_handler=mock_handler,
            filter_func=filter_func
        )
        
        logger = logging.getLogger("test_filter")
        logger.addHandler(filtered)
        logger.setLevel(logging.DEBUG)
        
        # Log at different levels
        logger.debug("Debug")
        logger.info("Info")
        logger.warning("Warning")
        logger.error("Error")
        
        # Only WARNING and above should pass
        assert mock_handler.handle.call_count == 2
        
        records = [call[0][0] for call in mock_handler.handle.call_args_list]
        assert records[0].levelname == "WARNING"
        assert records[1].levelname == "ERROR"


class TestLogFilters:
    """Test log filters."""
    
    def test_level_filter(self):
        """Test level filter."""
        # Filter for WARNING and above
        filter = LevelFilter(min_level=logging.WARNING)
        
        # Create records
        info_record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        warning_record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        
        assert not filter.filter(info_record)
        assert filter.filter(warning_record)
    
    def test_name_filter(self):
        """Test name filter."""
        # Filter for specific logger names
        filter = NameFilter(
            allowed_names=["app.auth", "app.database"],
            denied_names=["app.debug"]
        )
        
        # Test allowed
        auth_record = logging.LogRecord(
            name="app.auth.login", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter.filter(auth_record)
        
        # Test denied
        debug_record = logging.LogRecord(
            name="app.debug.trace", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert not filter.filter(debug_record)
        
        # Test other
        other_record = logging.LogRecord(
            name="other.module", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert not filter.filter(other_record)
    
    def test_context_filter(self):
        """Test context filter."""
        # Filter based on context attributes
        def has_user_context(record):
            return hasattr(record, "user_id")
        
        filter = ContextFilter(filter_func=has_user_context)
        
        # Record with context
        with_context = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        with_context.user_id = 123
        assert filter.filter(with_context)
        
        # Record without context
        without_context = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert not filter.filter(without_context)
    
    def test_rate_limit_filter(self):
        """Test rate limit filter."""
        # Allow 2 messages per second
        filter = RateLimitFilter(
            rate=2,
            per_seconds=1.0,
            burst=3
        )
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Same message", args=(), exc_info=None
        )
        
        # First few should pass (burst)
        assert filter.filter(record)
        assert filter.filter(record)
        assert filter.filter(record)
        
        # Next should be rate limited
        assert not filter.filter(record)
        
        # Wait and try again
        time.sleep(1.1)
        assert filter.filter(record)


class TestLoggingDecorators:
    """Test logging decorators."""
    
    def test_log_calls_decorator(self):
        """Test log_calls decorator."""
        handler = Mock()
        logger = get_logger("test_decorator")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        @log_calls(logger)
        def add(a, b):
            return a + b
        
        result = add(3, 5)
        assert result == 8
        
        # Check logged calls
        calls = handler.handle.call_args_list
        assert len(calls) >= 2  # Entry and exit
        
        # Check entry log
        entry_record = calls[0][0][0]
        assert "add" in entry_record.getMessage()
        assert "args=(3, 5)" in entry_record.getMessage()
        
        # Check exit log
        exit_record = calls[1][0][0]
        assert "add" in exit_record.getMessage()
        assert "returned 8" in exit_record.getMessage()
    
    def test_log_exceptions_decorator(self):
        """Test log_exceptions decorator."""
        handler = Mock()
        logger = get_logger("test_exceptions")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        @log_exceptions(logger)
        def risky_function(x):
            if x < 0:
                raise ValueError("Negative value")
            return x * 2
        
        # Normal call
        assert risky_function(5) == 10
        assert handler.handle.call_count == 0
        
        # Exception call
        with pytest.raises(ValueError):
            risky_function(-1)
        
        # Check exception was logged
        assert handler.handle.call_count == 1
        record = handler.handle.call_args[0][0]
        assert record.levelname == "ERROR"
        assert "ValueError" in record.getMessage()
        assert record.exc_info is not None
    
    def test_log_performance_decorator(self):
        """Test log_performance decorator."""
        handler = Mock()
        logger = get_logger("test_performance")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        @log_performance_decorator(logger, threshold_ms=50)
        def slow_function():
            time.sleep(0.1)  # 100ms
            return "done"
        
        result = slow_function()
        assert result == "done"
        
        # Check performance was logged
        assert handler.handle.call_count == 1
        record = handler.handle.call_args[0][0]
        assert "slow_function" in record.getMessage()
        assert "took" in record.getMessage()
        assert hasattr(record, "duration_ms")
        assert record.duration_ms > 50


class TestLoggingConfiguration:
    """Test logging configuration."""
    
    def test_configure_logging_basic(self):
        """Test basic logging configuration."""
        config = {
            "level": "INFO",
            "format": "%(levelname)s: %(message)s",
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "sys.stdout"
                }
            }
        }
        
        configure_logging(config)
        
        logger = get_logger("test_config")
        assert logger.level == logging.INFO
    
    def test_configure_logging_complex(self):
        """Test complex logging configuration."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            logfile = f.name
        
        try:
            config = {
                "level": "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "default"
                    },
                    "file": {
                        "class": "logging.FileHandler",
                        "filename": logfile,
                        "level": "DEBUG",
                        "formatter": "detailed"
                    }
                },
                "formatters": {
                    "default": {
                        "format": "%(levelname)s: %(message)s"
                    },
                    "detailed": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    }
                },
                "loggers": {
                    "app.security": {
                        "level": "WARNING"
                    },
                    "app.database": {
                        "level": "DEBUG",
                        "handlers": ["file"]
                    }
                }
            }
            
            configure_logging(config)
            
            # Test different loggers
            security_logger = get_logger("app.security")
            assert security_logger.level == logging.WARNING
            
            db_logger = get_logger("app.database")
            assert db_logger.level == logging.DEBUG
            
        finally:
            os.unlink(logfile)
    
    def test_set_log_level(self):
        """Test setting log level."""
        logger = get_logger("test_level")
        
        # Set by string
        set_log_level(logger, "WARNING")
        assert logger.level == logging.WARNING
        
        # Set by constant
        set_log_level(logger, logging.DEBUG)
        assert logger.level == logging.DEBUG
        
        # Set invalid level
        with pytest.raises(ValueError):
            set_log_level(logger, "INVALID")


class TestLoggingUtilities:
    """Test logging utility functions."""
    
    def test_get_logger(self):
        """Test getting logger instances."""
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module1")
        logger3 = get_logger("test.module2")
        
        # Same name returns same instance
        assert logger1 is logger2
        
        # Different name returns different instance
        assert logger1 is not logger3
        
        # Check names
        assert logger1.name == "test.module1"
        assert logger3.name == "test.module2"
    
    def test_add_remove_handler(self):
        """Test adding and removing handlers."""
        logger = get_logger("test_handlers")
        handler = Mock()
        
        # Add handler
        add_handler(logger, handler)
        assert handler in logger.handlers
        
        # Remove handler
        remove_handler(logger, handler)
        assert handler not in logger.handlers
    
    def test_log_context_performance(self):
        """Test log context for performance measurement."""
        handler = Mock()
        logger = get_logger("test_perf")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        with log_performance(logger, "database_query"):
            time.sleep(0.1)
        
        # Check performance was logged
        assert handler.handle.call_count >= 1
        record = handler.handle.call_args[0][0]
        assert "database_query" in record.getMessage()
        assert hasattr(record, "duration_ms")
        assert record.duration_ms > 90  # At least 90ms
    
    def test_log_error_context(self):
        """Test log error context."""
        handler = Mock()
        logger = get_logger("test_error")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        with log_error_context(logger, "Processing failed", user_id=123):
            raise ValueError("Test error")
        
        # Check error was logged with context
        assert handler.handle.call_count == 1
        record = handler.handle.call_args[0][0]
        assert record.levelname == "ERROR"
        assert "Processing failed" in record.getMessage()
        assert record.user_id == 123
        assert record.exc_info is not None


class TestThreadSafeLogging:
    """Test thread-safe logging."""
    
    def test_concurrent_logging(self):
        """Test logging from multiple threads."""
        logger = StructuredLogger("test_concurrent")
        messages = []
        
        class CollectingHandler(logging.Handler):
            def emit(self, record):
                messages.append(self.format(record))
        
        handler = CollectingHandler()
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        def log_messages(thread_id, count):
            for i in range(count):
                logger.info(f"Message {i}", thread_id=thread_id)
        
        # Create threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=log_messages,
                args=(i, 10)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check all messages were logged
        assert len(messages) == 50
    
    def test_context_isolation(self):
        """Test context isolation between threads."""
        logger = StructuredLogger("test_isolation")
        results = {}
        
        def thread_function(thread_id):
            # Set thread-specific context
            with log_context(logger, thread_id=thread_id):
                # Simulate some work
                time.sleep(0.01)
                
                # Check context is isolated
                context_copy = logger.context.copy()
                results[thread_id] = context_copy
        
        # Run threads
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=thread_function,
                args=(i,)
            )
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Each thread should have its own context
        for i in range(3):
            assert results[i]["thread_id"] == i


class TestAsyncLogging:
    """Test async logging functionality."""
    
    @pytest.mark.asyncio
    async def test_async_logging(self):
        """Test logging in async context."""
        logger = StructuredLogger("test_async")
        handler = Mock()
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        async def async_operation():
            logger.info("Starting async operation")
            await asyncio.sleep(0.01)
            logger.info("Completed async operation")
        
        await async_operation()
        
        assert handler.handle.call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager for logging."""
        logger = StructuredLogger("test_async_context")
        messages = []
        
        class CollectingHandler(logging.Handler):
            def emit(self, record):
                messages.append({
                    "message": record.getMessage(),
                    "correlation_id": getattr(record, "correlation_id", None)
                })
        
        handler = CollectingHandler()
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        async def async_with_context():
            async with log_context(logger, correlation_id="async-123"):
                logger.info("Inside async context")
                await asyncio.sleep(0.01)
                logger.info("Still inside async context")
        
        await async_with_context()
        
        # Check both messages have correlation_id
        assert len(messages) == 2
        assert all(m["correlation_id"] == "async-123" for m in messages)


class TestLogAggregation:
    """Test log aggregation functionality."""
    
    def test_log_aggregation(self):
        """Test aggregating similar log messages."""
        class AggregatingHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.aggregated = {}
            
            def emit(self, record):
                key = (record.levelname, record.getMessage())
                self.aggregated[key] = self.aggregated.get(key, 0) + 1
        
        handler = AggregatingHandler()
        logger = get_logger("test_aggregation")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Log similar messages
        for i in range(10):
            logger.info("User login failed")
            logger.warning("High memory usage")
        
        # Check aggregation
        assert handler.aggregated[("INFO", "User login failed")] == 10
        assert handler.aggregated[("WARNING", "High memory usage")] == 10
    
    def test_log_sampling(self):
        """Test log sampling for high-volume messages."""
        class SamplingFilter(logging.Filter):
            def __init__(self, sample_rate=0.1):
                self.sample_rate = sample_rate
                self.counter = 0
            
            def filter(self, record):
                self.counter += 1
                return self.counter % int(1 / self.sample_rate) == 0
        
        handler = Mock()
        logger = get_logger("test_sampling")
        logger.addHandler(handler)
        logger.addFilter(SamplingFilter(0.1))  # 10% sampling
        logger.setLevel(logging.INFO)
        
        # Log many messages
        for i in range(100):
            logger.info(f"Message {i}")
        
        # Should log approximately 10% 
        assert 5 <= handler.handle.call_count <= 15


class TestLogSecurity:
    """Test log security features."""
    
    def test_sensitive_data_masking(self):
        """Test masking sensitive data in logs."""
        class MaskingFormatter(LogFormatter):
            def format_message(self, record):
                message = record.getMessage()
                # Mask credit card numbers
                message = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 
                                 'XXXX-XXXX-XXXX-XXXX', message)
                # Mask SSNs
                message = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', 'XXX-XX-XXXX', message)
                return message
        
        formatter = MaskingFormatter()
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User SSN: 123-45-6789, Card: 1234-5678-9012-3456",
            args=(), exc_info=None
        )
        
        output = formatter.format(record)
        assert "XXX-XX-XXXX" in output
        assert "XXXX-XXXX-XXXX-XXXX" in output
        assert "123-45-6789" not in output
        assert "1234-5678-9012-3456" not in output
    
    def test_log_injection_prevention(self):
        """Test prevention of log injection attacks."""
        class SafeFormatter(LogFormatter):
            def format_message(self, record):
                message = record.getMessage()
                # Remove newlines and control characters
                message = message.replace('\n', '\\n')
                message = message.replace('\r', '\\r')
                message = ''.join(c for c in message if ord(c) >= 32)
                return message
        
        formatter = SafeFormatter()
        
        # Attempt log injection
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Normal message\n[CRITICAL] Injected message",
            args=(), exc_info=None
        )
        
        output = formatter.format(record)
        assert "\\n" in output
        assert "\n" not in output
        assert "[CRITICAL] Injected message" in output  # But on same line