"""
Consolidated logging utilities for VTT knowledge extraction.

Combines structured logging with correlation ID support for comprehensive
logging capabilities throughout the pipeline.
"""

from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Optional, Union, Callable
import json
import logging
import os
import sys
import time
import traceback
import uuid

import contextvars
# Try to use python-json-logger if available
try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', 
    default=None
)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID in context."""
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    correlation_id_var.set(correlation_id)
    return correlation_id


class StructuredFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging with correlation ID support."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with correlation ID."""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        
        # Add location info
        log_data.update({
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "path": record.pathname,
        })
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno', 
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
        
        # Handle exceptions
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, default=str)


class ContextFilter(logging.Filter):
    """Add context information to log records."""
    
    def __init__(self, context_data: Optional[Dict[str, Any]] = None):
        """Initialize context filter.
        
        Args:
            context_data: Static context data to add to all records
        """
        super().__init__()
        self.context_data = context_data or {}
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context data to log record."""
        # Add correlation ID
        record.correlation_id = get_correlation_id()
        
        # Add any static context data
        for key, value in self.context_data.items():
            setattr(record, key, value)
            
        # Add dynamic context if available
        if hasattr(record, 'context'):
            for key, value in record.context.items():
                setattr(record, key, value)
                
        return True


def setup_logging(
    level: Union[str, int] = "INFO",
    log_file: Optional[str] = None,
    structured: bool = True,
    correlation_id: Optional[str] = None
) -> None:
    """
    Configure logging for the application with correlation ID support.
    
    Args:
        level: Logging level
        log_file: Optional file path for logging
        structured: Use structured JSON logging
        correlation_id: Optional correlation ID to set
    """
    # Set correlation ID if provided
    if correlation_id:
        set_correlation_id(correlation_id)
    
    # Convert string level to int
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    if structured and HAS_JSON_LOGGER:
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True,
        )
    elif structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_execution_time(func: Optional[Callable] = None, *, 
                      log_args: bool = False,
                      log_result: bool = False) -> Callable:
    """
    Decorator to log function execution time with correlation ID.
    
    Args:
        func: Function to wrap
        log_args: Whether to log function arguments
        log_result: Whether to log function result
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = get_logger(f.__module__)
            start_time = time.time()
            
            # Log function call
            extra = {
                'function': f.__name__,
                'correlation_id': get_correlation_id()
            }
            if log_args:
                extra['args'] = args
                extra['kwargs'] = kwargs
            
            logger.debug(f"Starting {f.__name__}", extra=extra)
            
            try:
                result = f(*args, **kwargs)
                
                # Log completion
                duration = time.time() - start_time
                extra['duration_seconds'] = duration
                if log_result:
                    extra['result'] = result
                
                logger.debug(f"Completed {f.__name__}", extra=extra)
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Error in {f.__name__}: {str(e)}",
                    exc_info=True,
                    extra={
                        'function': f.__name__,
                        'duration_seconds': duration,
                        'correlation_id': get_correlation_id()
                    }
                )
                raise
        
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def log_error_with_context(logger: logging.Logger, 
                          message: str,
                          error: Exception,
                          context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error with full context and correlation ID.
    
    Args:
        logger: Logger instance
        message: Error message
        error: Exception that occurred
        context: Additional context data
    """
    error_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'correlation_id': get_correlation_id()
    }
    
    if context:
        error_data.update(context)
    
    logger.error(message, exc_info=error, extra=error_data)


def log_metric(logger: logging.Logger,
              metric_name: str,
              value: Union[int, float],
              unit: str = "count",
              tags: Optional[Dict[str, str]] = None) -> None:
    """
    Log a metric value with correlation ID.
    
    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        tags: Additional tags
    """
    metric_data = {
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit,
        'correlation_id': get_correlation_id()
    }
    
    if tags:
        metric_data['tags'] = tags
    
    logger.info(f"Metric: {metric_name}={value} {unit}", extra=metric_data)


def with_correlation_id(correlation_id: Optional[str] = None) -> Callable:
    """
    Decorator to set correlation ID for a function's execution.
    
    Args:
        correlation_id: Correlation ID to use (generates new if None)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Save current correlation ID
            current_id = get_correlation_id()
            
            try:
                # Set new correlation ID
                new_id = set_correlation_id(correlation_id)
                
                # Log function entry
                logger = get_logger(func.__module__)
                logger.debug(
                    f"Entering {func.__name__} with correlation_id={new_id}",
                    extra={'correlation_id': new_id}
                )
                
                # Execute function
                return func(*args, **kwargs)
                
            finally:
                # Restore previous correlation ID
                correlation_id_var.set(current_id)
        
        return wrapper
    return decorator


# Convenience functions for backward compatibility
def setup_structured_logging(level: str = "INFO", 
                           log_file: Optional[str] = None) -> None:
    """Setup structured JSON logging (backward compatibility)."""
    setup_logging(level=level, log_file=log_file, structured=True)


# Re-export commonly used functions
__all__ = [
    'setup_logging',
    'setup_structured_logging',
    'get_logger',
    'log_execution_time',
    'log_error_with_context',
    'log_metric',
    'generate_correlation_id',
    'get_correlation_id',
    'set_correlation_id',
    'with_correlation_id',
    'StructuredFormatter'
]