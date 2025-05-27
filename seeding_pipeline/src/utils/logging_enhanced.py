"""
Enhanced logging utilities with consistent correlation ID support.

This module provides enhanced logging capabilities with automatic correlation ID
propagation, structured logging patterns, and standardized log formats.
"""

import logging
import uuid
import contextvars
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime

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
    """
    Set the correlation ID for the current context.
    
    Args:
        correlation_id: Correlation ID to set (generates new one if None)
        
    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    correlation_id_var.set(correlation_id)
    return correlation_id


class CorrelationIdFilter(logging.Filter):
    """Automatically add correlation ID to all log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        # Get correlation ID from context or record
        correlation_id = getattr(record, 'correlation_id', None) or get_correlation_id()
        record.correlation_id = correlation_id
        return True


class StandardizedLogger(logging.LoggerAdapter):
    """
    Logger adapter that ensures consistent structured logging.
    
    This adapter automatically adds correlation IDs and other context
    to all log messages.
    """
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """Initialize with logger and optional extra context."""
        super().__init__(logger, extra or {})
        
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message to add standard context."""
        extra = kwargs.get('extra', {})
        
        # Add correlation ID if not present
        if 'correlation_id' not in extra:
            extra['correlation_id'] = get_correlation_id()
            
        # Add timestamp if not present
        if 'timestamp' not in extra:
            extra['timestamp'] = datetime.utcnow().isoformat()
            
        # Merge with adapter's extra
        extra.update(self.extra)
        kwargs['extra'] = extra
        
        return msg, kwargs


def with_correlation_id(correlation_id: Optional[str] = None) -> Callable:
    """
    Decorator to set correlation ID for a function's execution.
    
    Args:
        correlation_id: Correlation ID to use (generates new one if None)
        
    Example:
        @with_correlation_id()
        def process_request():
            logger.info("Processing request")  # Will include correlation ID
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Save current correlation ID
            token = correlation_id_var.set(correlation_id or generate_correlation_id())
            try:
                return func(*args, **kwargs)
            finally:
                # Restore previous correlation ID
                correlation_id_var.reset(token)
        return wrapper
    return decorator


def log_operation(
    operation_name: str,
    log_args: bool = False,
    log_result: bool = False,
    log_duration: bool = True
) -> Callable:
    """
    Decorator for consistent operation logging.
    
    Args:
        operation_name: Name of the operation being performed
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_duration: Whether to log execution duration
        
    Example:
        @log_operation("process_episode", log_duration=True)
        def process_episode(episode_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            correlation_id = get_correlation_id() or generate_correlation_id()
            
            # Log start
            start_extra = {
                'operation': operation_name,
                'phase': 'start',
                'correlation_id': correlation_id
            }
            if log_args:
                start_extra['args'] = str(args)
                start_extra['kwargs'] = str(kwargs)
                
            logger.info(f"Starting {operation_name}", extra=start_extra)
            
            # Execute function
            import time
            start_time = time.time()
            error_occurred = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = e
                raise
            finally:
                # Log completion
                duration = time.time() - start_time
                end_extra = {
                    'operation': operation_name,
                    'phase': 'end',
                    'correlation_id': correlation_id,
                    'success': error_occurred is None
                }
                
                if log_duration:
                    end_extra['duration_seconds'] = round(duration, 3)
                    
                if log_result and error_occurred is None:
                    end_extra['result'] = str(result)
                    
                if error_occurred:
                    end_extra['error_type'] = type(error_occurred).__name__
                    end_extra['error_message'] = str(error_occurred)
                    logger.error(
                        f"Failed {operation_name} after {duration:.2f}s",
                        extra=end_extra,
                        exc_info=True
                    )
                else:
                    logger.info(
                        f"Completed {operation_name} in {duration:.2f}s",
                        extra=end_extra
                    )
        
        return wrapper
    return decorator


def get_logger(name: str) -> StandardizedLogger:
    """
    Get a standardized logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        StandardizedLogger instance with correlation ID support
    """
    base_logger = logging.getLogger(name)
    return StandardizedLogger(base_logger)


# Structured logging helpers
def log_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    **kwargs
) -> None:
    """
    Log a structured event.
    
    Args:
        logger: Logger instance
        event_type: Type of event (e.g., 'episode_processed', 'entity_extracted')
        message: Human-readable message
        **kwargs: Additional structured data
    """
    extra = {
        'event_type': event_type,
        'correlation_id': get_correlation_id(),
        **kwargs
    }
    logger.info(message, extra=extra)


def log_business_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = 'count',
    **dimensions
) -> None:
    """
    Log a business metric with dimensions.
    
    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        **dimensions: Additional dimensions (tags)
    """
    extra = {
        'metric_type': 'business',
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit,
        'correlation_id': get_correlation_id(),
        **dimensions
    }
    logger.info(f"Business metric: {metric_name}={value} {unit}", extra=extra)


def log_technical_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = 'count',
    **dimensions
) -> None:
    """
    Log a technical metric with dimensions.
    
    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        **dimensions: Additional dimensions (tags)
    """
    extra = {
        'metric_type': 'technical',
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit,
        'correlation_id': get_correlation_id(),
        **dimensions
    }
    logger.info(f"Technical metric: {metric_name}={value} {unit}", extra=extra)


# Logging Guidelines
LOGGING_GUIDELINES = """
Logging Guidelines for Podcast Knowledge Pipeline
================================================

1. Always use structured logging with extra fields
2. Include correlation_id in all logs for request tracing
3. Use appropriate log levels:
   - DEBUG: Detailed diagnostic information
   - INFO: General informational messages
   - WARNING: Warning messages for recoverable issues
   - ERROR: Error messages for failures
   - CRITICAL: Critical failures requiring immediate attention

4. Standard fields to include:
   - correlation_id: Request correlation ID
   - operation: Current operation name
   - phase: Operation phase (start, processing, end)
   - duration_seconds: Operation duration
   - success: Whether operation succeeded
   - error_type: Exception type on failure
   - error_message: Error message on failure

5. Use structured logging helpers:
   - log_event(): For business events
   - log_business_metric(): For business metrics
   - log_technical_metric(): For technical metrics
   - @log_operation(): For consistent operation logging
   - @with_correlation_id(): For correlation ID propagation

6. Example usage:

   from src.utils.logging_enhanced import get_logger, log_operation, with_correlation_id

   logger = get_logger(__name__)
   
   @with_correlation_id()
   @log_operation("process_episode")
   def process_episode(episode_id: str):
       logger.info("Processing episode", extra={'episode_id': episode_id})
       # ... processing logic ...
       log_business_metric(logger, "episodes_processed", 1, episode_id=episode_id)

7. For error logging, always include context:
   try:
       # operation
   except Exception as e:
       logger.error(
           "Operation failed",
           extra={
               'operation': 'process_episode',
               'episode_id': episode_id,
               'error_type': type(e).__name__
           },
           exc_info=True
       )
"""


__all__ = [
    'get_logger',
    'get_correlation_id',
    'set_correlation_id',
    'with_correlation_id',
    'log_operation',
    'log_event',
    'log_business_metric',
    'log_technical_metric',
    'CorrelationIdFilter',
    'StandardizedLogger',
    'LOGGING_GUIDELINES'
]