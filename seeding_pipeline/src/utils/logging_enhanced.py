"""Enhanced logging with rotation, metrics, and comprehensive tracing."""

import json
import logging
import logging.handlers
import os
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
import threading
from queue import Queue, Empty

from src.utils.log_utils import (
    get_logger, 
    get_correlation_id, 
    set_correlation_id,
    ContextFilter,
    StructuredFormatter,
    HAS_JSON_LOGGER
)

# Performance metrics storage
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
                'start_time': datetime.fromtimestamp(self._start_time).isoformat(),
                'uptime_seconds': time.time() - self._start_time,
                'metrics': self._metrics.copy()
            }
    
    def get_summary(self, metric_name: str) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        with self._lock:
            if metric_name not in self._metrics:
                return {}
            
            values = [m['value'] for m in self._metrics[metric_name]]
            if not values:
                return {}
            
            return {
                'count': len(values),
                'sum': sum(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values)
            }

# Global metrics collector
_metrics_collector = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector


class ProcessingTraceLogger:
    """Logger for detailed processing traces."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._trace_stack = []
        
    def start_trace(self, operation: str, context: Optional[Dict[str, Any]] = None):
        """Start a new trace operation."""
        trace_id = f"{operation}_{time.time()}"
        trace_data = {
            'operation': operation,
            'start_time': time.time(),
            'context': context or {},
            'trace_id': trace_id
        }
        self._trace_stack.append(trace_data)
        
        self.logger.debug(
            f"TRACE_START: {operation}",
            extra={
                'trace_type': 'start',
                'trace_id': trace_id,
                'operation': operation,
                'context': context,
                'correlation_id': get_correlation_id()
            }
        )
        return trace_id
    
    def end_trace(self, trace_id: Optional[str] = None, result: Any = None, error: Optional[Exception] = None):
        """End a trace operation."""
        if not self._trace_stack:
            return
        
        # Pop the most recent trace if no ID specified
        if trace_id:
            trace_data = next((t for t in self._trace_stack if t.get('trace_id') == trace_id), None)
            if trace_data:
                self._trace_stack.remove(trace_data)
        else:
            trace_data = self._trace_stack.pop()
        
        if not trace_data:
            return
        
        duration = time.time() - trace_data['start_time']
        
        log_data = {
            'trace_type': 'end',
            'trace_id': trace_data['trace_id'],
            'operation': trace_data['operation'],
            'duration_seconds': duration,
            'correlation_id': get_correlation_id()
        }
        
        if result is not None:
            log_data['result_summary'] = str(result)[:200]  # Truncate large results
        
        if error:
            log_data['error'] = str(error)
            log_data['error_type'] = type(error).__name__
            self.logger.error(f"TRACE_ERROR: {trace_data['operation']}", extra=log_data, exc_info=error)
        else:
            self.logger.debug(f"TRACE_END: {trace_data['operation']}", extra=log_data)
            
        # Record as metric
        _metrics_collector.record_metric(
            f"operation.{trace_data['operation']}.duration",
            duration,
            unit="seconds"
        )


def setup_enhanced_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    structured: bool = True,
    enable_metrics: bool = True,
    enable_tracing: bool = True
) -> None:
    """
    Set up enhanced logging with rotation and metrics.
    
    Args:
        level: Logging level
        log_file: Optional file path for logging
        max_bytes: Max size before rotation (default 10MB)
        backup_count: Number of backup files to keep
        structured: Use structured JSON logging
        enable_metrics: Enable metrics collection
        enable_tracing: Enable detailed tracing
    """
    # Convert string level to int
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create enhanced formatter with additional fields
    class EnhancedJSONFormatter(logging.Formatter):
        """Enhanced JSON formatter with additional context."""
        
        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'correlation_id': getattr(record, 'correlation_id', None),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.threadName,
                'process': record.processName,
            }
            
            # Add any extra fields
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                              'levelname', 'levelno', 'lineno', 'module', 'msecs',
                              'pathname', 'process', 'processName', 'relativeCreated',
                              'thread', 'threadName', 'getMessage']:
                    log_data[key] = value
            
            # Add exception info if present
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
            
            return json.dumps(log_data)
    
    # Choose formatter
    if structured:
        formatter = EnhancedJSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
            defaults={'correlation_id': 'no-correlation-id'}
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add context filter
    context_filter = ContextFilter()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)
    
    # Add metrics handler if enabled
    if enable_metrics:
        class MetricsHandler(logging.Handler):
            """Handler that extracts metrics from log records."""
            
            def emit(self, record: logging.LogRecord):
                # Extract metrics from specific log patterns
                if hasattr(record, 'metric_name') and hasattr(record, 'metric_value'):
                    _metrics_collector.record_metric(
                        record.metric_name,
                        record.metric_value,
                        unit=getattr(record, 'metric_unit', 'count'),
                        tags=getattr(record, 'metric_tags', {})
                    )
        
        metrics_handler = MetricsHandler()
        metrics_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(metrics_handler)
    
    logger = get_logger(__name__)
    logger.info(
        "Enhanced logging configured",
        extra={
            'log_level': level,
            'log_file': log_file,
            'structured': structured,
            'rotation_enabled': log_file is not None,
            'metrics_enabled': enable_metrics,
            'tracing_enabled': enable_tracing
        }
    )


def log_performance_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = "seconds",
    operation: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
):
    """
    Log a performance metric.
    
    Args:
        logger: Logger instance
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        operation: Operation name for context
        tags: Additional tags
    """
    extra = {
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit,
        'metric_tags': tags or {},
        'correlation_id': get_correlation_id()
    }
    
    if operation:
        extra['operation'] = operation
    
    logger.info(f"METRIC: {metric_name}={value} {unit}", extra=extra)


def trace_operation(operation_name: str):
    """
    Decorator to trace operation execution.
    
    Args:
        operation_name: Name of the operation to trace
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            tracer = ProcessingTraceLogger(logger)
            
            # Start trace
            trace_id = tracer.start_trace(
                operation_name,
                context={
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
            )
            
            try:
                result = func(*args, **kwargs)
                tracer.end_trace(trace_id, result=result)
                return result
            except Exception as e:
                tracer.end_trace(trace_id, error=e)
                raise
        
        return wrapper
    return decorator


def log_batch_progress(
    logger: logging.Logger,
    current: int,
    total: int,
    operation: str,
    start_time: float,
    additional_info: Optional[Dict[str, Any]] = None
):
    """
    Log batch processing progress with ETA.
    
    Args:
        logger: Logger instance
        current: Current item number
        total: Total items
        operation: Operation being performed
        start_time: Start time of batch processing
        additional_info: Additional context
    """
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / rate if rate > 0 else 0
    
    extra = {
        'operation': operation,
        'progress_current': current,
        'progress_total': total,
        'progress_percent': (current / total * 100) if total > 0 else 0,
        'rate_per_second': rate,
        'eta_seconds': eta,
        'elapsed_seconds': elapsed,
        'correlation_id': get_correlation_id()
    }
    
    if additional_info:
        extra.update(additional_info)
    
    logger.info(
        f"PROGRESS: {operation} - {current}/{total} ({current/total*100:.1f}%) - "
        f"Rate: {rate:.1f}/s - ETA: {eta:.0f}s",
        extra=extra
    )