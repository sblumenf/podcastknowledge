"""
Structured logging configuration for the Podcast Knowledge Graph Pipeline.

Provides JSON-formatted logs with proper levels, context, and metadata
for production monitoring and debugging.
"""

import logging
import sys
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import os
from functools import wraps
import time

# Try to use python-json-logger if available
try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class StructuredFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", 
                          "funcName", "levelname", "levelno", "lineno", 
                          "module", "msecs", "message", "pathname", "process",
                          "processName", "relativeCreated", "thread", 
                          "threadName", "exc_info", "exc_text", "stack_info"]:
                log_data[key] = value
        
        return json.dumps(log_data)


class ContextFilter(logging.Filter):
    """Add contextual information to log records."""
    
    def __init__(self, app_name: str = "podcast-kg-pipeline"):
        super().__init__()
        self.app_name = app_name
        self.hostname = os.environ.get("HOSTNAME", "unknown")
        self.environment = os.environ.get("PODCAST_KG_ENV", "development")
        self.version = os.environ.get("APP_VERSION", "unknown")
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        record.app = self.app_name
        record.hostname = self.hostname
        record.environment = self.environment
        record.version = self.version
        record.correlation_id = getattr(record, "correlation_id", None)
        return True


class PerformanceFilter(logging.Filter):
    """Add performance metrics to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add performance context."""
        # Add memory usage
        try:
            import psutil
            process = psutil.Process()
            record.memory_mb = round(process.memory_info().rss / 1024 / 1024, 2)
            record.cpu_percent = process.cpu_percent()
        except:
            pass
        
        return True


def setup_logging(
    level: Union[str, int] = None,
    log_file: Optional[str] = None,
    json_format: bool = True,
    add_context: bool = True,
    add_performance: bool = False
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_format: Whether to use JSON formatting
        add_context: Whether to add contextual information
        add_performance: Whether to add performance metrics
    """
    # Determine log level
    if level is None:
        level = os.environ.get("PODCAST_KG_LOG_LEVEL", "INFO")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    if json_format:
        if HAS_JSON_LOGGER:
            formatter = jsonlogger.JsonFormatter(
                "%(timestamp)s %(level)s %(name)s %(message)s",
                timestamp=lambda: datetime.utcnow().isoformat()
            )
        else:
            formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Add filters
    if add_context:
        console_handler.addFilter(ContextFilter())
    if add_performance:
        console_handler.addFilter(PerformanceFilter())
    
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        
        if add_context:
            file_handler.addFilter(ContextFilter())
        if add_performance:
            file_handler.addFilter(PerformanceFilter())
        
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("whisper").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": logging.getLevelName(level),
            "json_format": json_format,
            "log_file": log_file,
            "pid": os.getpid()
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_execution_time(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function execution time.
    
    Args:
        logger: Logger instance to use
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    f"Function executed successfully",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": round(duration, 3),
                        "status": "success"
                    }
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Function execution failed",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": round(duration, 3),
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )
                raise
        return wrapper
    return decorator


def log_with_context(**context):
    """
    Decorator to add context to all logs within a function.
    
    Args:
        **context: Context key-value pairs to add to logs
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger for the function's module
            logger = logging.getLogger(func.__module__)
            
            # Create a log adapter with context
            adapter = logging.LoggerAdapter(logger, context)
            
            # Temporarily replace the logger
            original_logger = logging.getLogger(func.__module__)
            setattr(sys.modules[func.__module__], 'logger', adapter)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Restore original logger
                setattr(sys.modules[func.__module__], 'logger', original_logger)
        return wrapper
    return decorator


class LogContext:
    """Context manager for adding temporary log context."""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.original_class = None
    
    def __enter__(self):
        """Add context to logger."""
        self.original_class = self.logger.__class__
        
        # Create a custom logger class with context
        class ContextLogger(self.original_class):
            def _log(self, level, msg, args, exc_info=None, extra=None, **kwargs):
                if extra is None:
                    extra = {}
                extra.update(self.context)
                super()._log(level, msg, args, exc_info, extra, **kwargs)
        
        self.logger.__class__ = ContextLogger
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove context from logger."""
        self.logger.__class__ = self.original_class


def create_operation_logger(operation: str, correlation_id: Optional[str] = None) -> logging.Logger:
    """
    Create a logger for a specific operation with correlation ID.
    
    Args:
        operation: Operation name
        correlation_id: Optional correlation ID for request tracing
        
    Returns:
        Logger with operation context
    """
    logger = logging.getLogger(f"podcast_kg.{operation}")
    
    # Add correlation ID to all logs from this logger
    if correlation_id:
        class CorrelationAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                extra = kwargs.get('extra', {})
                extra['correlation_id'] = correlation_id
                extra['operation'] = operation
                kwargs['extra'] = extra
                return msg, kwargs
        
        return CorrelationAdapter(logger, {})
    
    return logger


# Convenience functions for common log patterns
def log_error_with_context(logger: logging.Logger, error: Exception, 
                          operation: str, **context) -> None:
    """Log an error with full context."""
    logger.error(
        f"Error in {operation}",
        extra={
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        },
        exc_info=True
    )


def log_metric(logger: logging.Logger, metric_name: str, 
               value: Union[int, float], unit: str = "count", **tags) -> None:
    """Log a metric value."""
    logger.info(
        f"Metric: {metric_name}",
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "metric_type": "gauge",
            **tags
        }
    )