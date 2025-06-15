"""
Unified logging system for VTT knowledge extraction.

Combines structured logging, correlation ID support, rotation, metrics collection,
and comprehensive tracing capabilities in a single, configurable module.
"""

from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Optional, Union, Callable, List
import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
import uuid
import threading
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

import contextvars

# Try to use python-json-logger if available
try:
    from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter
    HAS_JSON_LOGGER = True
except ImportError:
    try:
        # Fallback to old import for older versions
        from pythonjsonlogger import jsonlogger as BaseJsonFormatter
        HAS_JSON_LOGGER = True
    except ImportError:
        HAS_JSON_LOGGER = False
        BaseJsonFormatter = logging.Formatter


# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', 
    default=None
)


class LoggingFeatures(Enum):
    """Available logging features that can be enabled."""
    ROTATION = "rotation"
    METRICS = "metrics"
    TRACING = "tracing"
    PROGRESS = "progress"
    PERFORMANCE = "performance"


@dataclass
class LoggingConfig:
    """Configuration for unified logging system."""
    # Base configuration
    level: str = "INFO"
    format: str = "structured"  # "structured" or "simple"
    
    # File configuration
    log_dir: Optional[str] = None
    filename: Optional[str] = "app.log"
    
    # Feature flags
    enable_rotation: bool = False
    enable_metrics: bool = False
    enable_tracing: bool = False
    enable_progress: bool = False
    
    # Rotation settings
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Console output
    console_output: bool = True
    
    @classmethod
    def from_env(cls) -> 'LoggingConfig':
        """Create config from environment variables."""
        return cls(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            log_dir=os.getenv('LOG_DIR'),
            enable_rotation=os.getenv('LOG_ROTATION', 'false').lower() == 'true',
            enable_metrics=os.getenv('LOG_METRICS', 'false').lower() == 'true',
            enable_tracing=os.getenv('LOG_TRACING', 'false').lower() == 'true',
            enable_progress=os.getenv('LOG_PROGRESS', 'false').lower() == 'true',
        )


# Correlation ID functions
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


class ContextFilter(logging.Filter):
    """Filter that adds correlation ID and context data to log records."""
    
    def __init__(self, context_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context_data = context_data or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context data to log record."""
        # Add correlation ID
        record.correlation_id = get_correlation_id() or 'no-correlation-id'
        
        # Add any static context data
        for key, value in self.context_data.items():
            setattr(record, key, value)
        
        # Add process and thread info
        record.process_name = record.processName
        record.thread_name = record.threadName
        
        return True


class StructuredFormatter(BaseJsonFormatter if HAS_JSON_LOGGER else logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_metrics: bool = False):
        self.include_metrics = include_metrics
        if HAS_JSON_LOGGER:
            super().__init__(
                fmt="%(timestamp)s %(level)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            super().__init__(
                fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"logger": "%(name)s", "message": "%(message)s", '
                    '"correlation_id": "%(correlation_id)s"}'
            )
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, 
                   message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record."""
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add correlation ID
        log_record['correlation_id'] = getattr(record, 'correlation_id', 'no-correlation-id')
        
        # Add level name
        log_record['level'] = record.levelname
        
        # Add logger name
        log_record['logger'] = record.name
        
        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName',
                          'relativeCreated', 'thread', 'threadName', 'exc_info',
                          'exc_text', 'stack_info', 'getMessage', 'correlation_id']:
                log_record[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


class MetricsCollector:
    """Collects and stores performance metrics."""
    
    def __init__(self):
        self._metrics = {}
        self._lock = threading.Lock()
        self._start_time = time.time()
        
    def record_metric(self, name: str, value: float, unit: str = "count", 
                     tags: Optional[Dict[str, str]] = None):
        """Record a metric value."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            
            metric_data = {
                'timestamp': datetime.now().isoformat(),
                'value': value,
                'unit': unit,
                'tags': tags or {}
            }
            self._metrics[name].append(metric_data)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        with self._lock:
            return {
                'start_time': self._start_time,
                'metrics': self._metrics.copy()
            }
    
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get metric summaries."""
        with self._lock:
            summary = {}
            for name, values in self._metrics.items():
                if values:
                    nums = [v['value'] for v in values]
                    summary[name] = {
                        'count': len(nums),
                        'sum': sum(nums),
                        'avg': sum(nums) / len(nums),
                        'min': min(nums),
                        'max': max(nums)
                    }
            return summary


class ProcessingTraceLogger:
    """Logger for detailed processing traces."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.traces = []
        self.current_trace = None
        
    def start_trace(self, operation: str, **kwargs):
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        trace = {
            'id': trace_id,
            'operation': operation,
            'start_time': time.time(),
            'start_timestamp': datetime.now().isoformat(),
            'attributes': kwargs
        }
        self.current_trace = trace
        self.traces.append(trace)
        
        self.logger.info(
            f"[TRACE_START] {operation}",
            extra={
                'trace_id': trace_id,
                'trace_operation': operation,
                'trace_event': 'start',
                **kwargs
            }
        )
        
        return trace_id
    
    def end_trace(self, trace_id: str, status: str = "success", **kwargs):
        """End a trace."""
        trace = next((t for t in self.traces if t['id'] == trace_id), None)
        if trace:
            end_time = time.time()
            duration = end_time - trace['start_time']
            
            trace['end_time'] = end_time
            trace['end_timestamp'] = datetime.now().isoformat()
            trace['duration'] = duration
            trace['status'] = status
            trace['end_attributes'] = kwargs
            
            self.logger.info(
                f"[TRACE_END] {trace['operation']} - {status} ({duration:.3f}s)",
                extra={
                    'trace_id': trace_id,
                    'trace_operation': trace['operation'],
                    'trace_event': 'end',
                    'trace_duration': duration,
                    'trace_status': status,
                    **kwargs
                }
            )
    
    def get_traces(self) -> List[Dict[str, Any]]:
        """Get all traces."""
        return self.traces.copy()


# Global instances
_metrics_collector: Optional[MetricsCollector] = None
_loggers: Dict[str, logging.Logger] = {}
_config: Optional[LoggingConfig] = None


def setup_logging(config: Optional[LoggingConfig] = None, **kwargs) -> None:
    """
    Set up unified logging system with specified configuration.
    
    Args:
        config: LoggingConfig object or None to use defaults
        **kwargs: Override config values
    """
    global _config, _metrics_collector
    
    # Create or update config
    if config is None:
        config = LoggingConfig.from_env()
    
    # Apply kwargs overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    _config = config
    
    # Set up metrics collector if enabled
    if config.enable_metrics:
        _metrics_collector = MetricsCollector()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add console handler if enabled
    if config.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level.upper()))
        
        if config.format == "structured":
            console_handler.setFormatter(StructuredFormatter(include_metrics=config.enable_metrics))
        else:
            console_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
        
        console_handler.addFilter(ContextFilter())
        root_logger.addHandler(console_handler)
    
    # Add file handler if log_dir is specified
    if config.log_dir:
        log_path = Path(config.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / config.filename
        
        if config.enable_rotation:
            # Use rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count
            )
        else:
            # Use regular file handler
            file_handler = logging.FileHandler(log_file)
        
        file_handler.setLevel(getattr(logging, config.level.upper()))
        
        if config.format == "structured":
            file_handler.setFormatter(StructuredFormatter(include_metrics=config.enable_metrics))
        else:
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
        
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with enhanced capabilities.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    
    # Add trace logger if tracing is enabled
    if _config and _config.enable_tracing:
        logger.trace_logger = ProcessingTraceLogger(logger)
    
    _loggers[name] = logger
    return logger


def log_metric(name: str, value: float, unit: str = "count", 
               tags: Optional[Dict[str, str]] = None, logger: Optional[logging.Logger] = None):
    """Log a metric value."""
    if _metrics_collector:
        _metrics_collector.record_metric(name, value, unit, tags)
    
    # Also log as regular log entry
    if logger is None:
        logger = logging.getLogger(__name__)
    
    logger.info(
        f"Metric: {name}",
        extra={
            'metric_name': name,
            'metric_value': value,
            'metric_unit': unit,
            'metric_tags': tags or {}
        }
    )


def log_performance_metric(operation: str, duration: float, 
                          success: bool = True, metadata: Optional[Dict[str, Any]] = None):
    """Log a performance metric."""
    tags = {
        'operation': operation,
        'success': str(success)
    }
    if metadata:
        tags.update({f'meta_{k}': str(v) for k, v in metadata.items()})
    
    log_metric(f"{operation}_duration", duration, unit="seconds", tags=tags)


def log_batch_progress(current: int, total: int, operation: str, 
                      start_time: Optional[float] = None, logger: Optional[logging.Logger] = None):
    """Log batch processing progress with ETA."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    progress_pct = (current / total * 100) if total > 0 else 0
    
    extra = {
        'batch_current': current,
        'batch_total': total,
        'batch_progress': progress_pct,
        'batch_operation': operation
    }
    
    if start_time:
        elapsed = time.time() - start_time
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        
        extra.update({
            'batch_elapsed': elapsed,
            'batch_rate': rate,
            'batch_eta': eta
        })
        
        logger.info(
            f"[PROGRESS] {operation}: {current}/{total} ({progress_pct:.1f}%) "
            f"Rate: {rate:.1f}/s ETA: {eta:.1f}s",
            extra=extra
        )
    else:
        logger.info(
            f"[PROGRESS] {operation}: {current}/{total} ({progress_pct:.1f}%)",
            extra=extra
        )


def trace_operation(operation_name: str = None):
    """Decorator for tracing operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            logger = get_logger(func.__module__)
            
            if hasattr(logger, 'trace_logger'):
                trace_id = logger.trace_logger.start_trace(name, args=str(args), kwargs=str(kwargs))
                try:
                    result = func(*args, **kwargs)
                    logger.trace_logger.end_trace(trace_id, status="success")
                    return result
                except Exception as e:
                    logger.trace_logger.end_trace(trace_id, status="error", error=str(e))
                    raise
            else:
                # Fallback to simple timing
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    log_performance_metric(name, duration, success=True)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    log_performance_metric(name, duration, success=False, metadata={'error': str(e)})
                    raise
        
        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """Decorator to log function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger = get_logger(func.__module__)
            logger.info(
                f"{func.__name__} completed in {execution_time:.3f}s",
                extra={'execution_time': execution_time, 'function': func.__name__}
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger = get_logger(func.__module__)
            logger.error(
                f"{func.__name__} failed after {execution_time:.3f}s: {e}",
                extra={'execution_time': execution_time, 'function': func.__name__, 'error': str(e)}
            )
            raise
    
    return wrapper


def with_correlation_id(func: Callable) -> Callable:
    """Decorator to ensure function runs with a correlation ID."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Set correlation ID if not already set
        correlation_id = get_correlation_id()
        if not correlation_id:
            correlation_id = set_correlation_id()
        
        return func(*args, **kwargs)
    
    return wrapper


def log_error_with_context(logger: logging.Logger, error: Exception, 
                          context: Dict[str, Any], message: str = "Error occurred"):
    """Log an error with full context and traceback."""
    logger.error(
        message,
        extra={
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_traceback': traceback.format_exc(),
            'error_context': context
        },
        exc_info=True
    )


def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of all collected metrics."""
    if _metrics_collector:
        return _metrics_collector.get_summary()
    return {}


# Backward compatibility functions
def setup_structured_logging(*args, **kwargs):
    """Backward compatibility wrapper for setup_logging."""
    # Convert old parameters to new config
    config = LoggingConfig()
    if 'log_level' in kwargs:
        config.level = kwargs.pop('log_level')
    if 'log_file' in kwargs:
        log_file = Path(kwargs.pop('log_file'))
        config.log_dir = str(log_file.parent)
        config.filename = log_file.name
    
    setup_logging(config, **kwargs)


def setup_enhanced_logging(log_dir: str = "logs", **kwargs):
    """Backward compatibility wrapper for enhanced logging setup."""
    config = LoggingConfig(
        log_dir=log_dir,
        enable_rotation=True,
        enable_metrics=True,
        enable_tracing=True,
        enable_progress=True,
        **kwargs
    )
    setup_logging(config)


# Initialize with default config on import
if not _config:
    setup_logging()