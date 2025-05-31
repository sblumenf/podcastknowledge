"""Enhanced error handling and debugging utilities."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Callable, Type, List, Union
import functools
import json
import logging
import sys
import traceback
class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    NETWORK = "network"
    DATABASE = "database"
    PARSING = "parsing"
    VALIDATION = "validation"
    RESOURCE = "resource"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Structured error context for debugging."""
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    traceback: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'error_type': self.error_type,
            'error_message': self.error_message,
            'severity': self.severity.value,
            'category': self.category.value,
            'timestamp': self.timestamp,
            'traceback': self.traceback,
            'context_data': self.context_data,
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class DebugLogger:
    """Enhanced logger with debug mode and structured logging."""
    
    def __init__(self, 
                 name: str,
                 debug_mode: bool = False,
                 log_file: Optional[str] = None):
        """Initialize debug logger.
        
        Args:
            name: Logger name
            debug_mode: Whether to enable debug logging
            log_file: Optional file to write logs to
        """
        self.logger = logging.getLogger(name)
        self.debug_mode = debug_mode
        self.error_history: List[ErrorContext] = []
        
        # Set log level based on debug mode
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        
        # Formatter with more detail in debug mode
        if debug_mode:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - '
                '[%(filename)s:%(lineno)d] - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def log_error_context(self, error_context: ErrorContext) -> None:
        """Log structured error context."""
        self.error_history.append(error_context)
        
        # Log based on severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"[{error_context.category.value}] "
                               f"{error_context.error_message}")
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(f"[{error_context.category.value}] "
                            f"{error_context.error_message}")
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"[{error_context.category.value}] "
                              f"{error_context.error_message}")
        else:
            self.logger.info(f"[{error_context.category.value}] "
                           f"{error_context.error_message}")
        
        # Log additional context in debug mode
        if self.debug_mode:
            self.logger.debug(f"Error context: {error_context.to_json()}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered."""
        summary = {
            'total_errors': len(self.error_history),
            'by_severity': {},
            'by_category': {},
            'recovery_stats': {
                'attempted': 0,
                'successful': 0
            }
        }
        
        for error in self.error_history:
            # Count by severity
            severity = error.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # Count by category
            category = error.category.value
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
            
            # Recovery stats
            if error.recovery_attempted:
                summary['recovery_stats']['attempted'] += 1
                if error.recovery_successful:
                    summary['recovery_stats']['successful'] += 1
        
        return summary


def with_error_context(severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                      category: ErrorCategory = ErrorCategory.UNKNOWN,
                      context_keys: Optional[List[str]] = None):
    """Decorator to add structured error context to functions.
    
    Args:
        severity: Default error severity
        category: Error category
        context_keys: List of argument names to include in context
        
    Example:
        @with_error_context(severity=ErrorSeverity.HIGH, 
                          category=ErrorCategory.DATABASE,
                          context_keys=['user_id', 'query'])
        def database_operation(user_id, query):
            # Function that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            context_data = {}
            
            # Extract context from function arguments
            if context_keys:
                # Get function argument names
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                for key in context_keys:
                    if key in bound_args.arguments:
                        context_data[key] = str(bound_args.arguments[key])
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create error context
                error_context = ErrorContext(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    severity=severity,
                    category=category,
                    traceback=traceback.format_exc(),
                    context_data=context_data
                )
                
                # Log if logger is available
                logger = logging.getLogger(func.__module__)
                if logger:
                    logger.error(f"Error in {func.__name__}: {error_context.to_json()}")
                
                # Re-raise with context attached
                e.error_context = error_context
                raise
        
        return wrapper
    return decorator


@contextmanager
def debug_context(operation_name: str, 
                 logger: Optional[logging.Logger] = None,
                 **context_data):
    """Context manager for detailed operation debugging.
    
    Args:
        operation_name: Name of the operation being performed
        logger: Logger instance to use
        **context_data: Additional context data
        
    Example:
        with debug_context("data_processing", user_id=123, batch_size=100):
            # Process data
            pass
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    start_time = datetime.now()
    logger.debug(f"Starting {operation_name} with context: {context_data}")
    
    try:
        yield
        
        # Log successful completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.debug(f"Completed {operation_name} in {duration:.2f}s")
        
    except Exception as e:
        # Log failure with context
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Failed {operation_name} after {duration:.2f}s: {e}")
        logger.debug(f"Failure context: {context_data}")
        raise


class ErrorAnalyzer:
    """Analyze errors to identify patterns and suggest fixes."""
    
    def __init__(self):
        """Initialize error analyzer."""
        self.error_patterns = {
            # Network errors
            r'rate limit|429|too many requests': {
                'category': ErrorCategory.NETWORK,
                'severity': ErrorSeverity.MEDIUM,
                'suggestion': 'Implement rate limiting or backoff strategy'
            },
            r'timeout|timed out|connection reset': {
                'category': ErrorCategory.NETWORK,
                'severity': ErrorSeverity.MEDIUM,
                'suggestion': 'Increase timeout or retry with exponential backoff'
            },
            
            # Database errors
            r'connection refused|unable to connect|database': {
                'category': ErrorCategory.DATABASE,
                'severity': ErrorSeverity.HIGH,
                'suggestion': 'Check database connection settings and availability'
            },
            
            # Parsing errors
            r'json|parse|decode|invalid': {
                'category': ErrorCategory.PARSING,
                'severity': ErrorSeverity.MEDIUM,
                'suggestion': 'Validate input format and add error handling for malformed data'
            },
            
            # Resource errors
            r'memory|out of memory|oom': {
                'category': ErrorCategory.RESOURCE,
                'severity': ErrorSeverity.CRITICAL,
                'suggestion': 'Reduce batch size or implement memory management'
            },
            r'disk space|no space': {
                'category': ErrorCategory.RESOURCE,
                'severity': ErrorSeverity.HIGH,
                'suggestion': 'Clean up temporary files or increase disk space'
            }
        }
    
    def analyze_error(self, error: Exception) -> Dict[str, Any]:
        """Analyze an error and provide insights.
        
        Args:
            error: Exception to analyze
            
        Returns:
            Analysis results with category, severity, and suggestions
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Check against patterns
        for pattern, info in self.error_patterns.items():
            import re
            if re.search(pattern, error_str):
                return {
                    'error_type': error_type,
                    'matched_pattern': pattern,
                    'category': info['category'],
                    'severity': info['severity'],
                    'suggestion': info['suggestion']
                }
        
        # Default analysis
        return {
            'error_type': error_type,
            'matched_pattern': None,
            'category': ErrorCategory.UNKNOWN,
            'severity': ErrorSeverity.MEDIUM,
            'suggestion': 'Add specific error handling for this error type'
        }


def create_provider_error_handler(provider_name: str) -> Callable:
    """Create provider-specific error handler.
    
    Args:
        provider_name: Name of the provider (e.g., 'openai', 'gemini')
        
    Returns:
        Error handler function
    """
    def handle_provider_error(error: Exception) -> Optional[Dict[str, Any]]:
        """Handle provider-specific errors."""
        error_str = str(error).lower()
        
        # Provider-specific handling
        if provider_name == 'openai':
            if 'rate limit' in error_str:
                return {
                    'retry': True,
                    'wait_time': 60,
                    'fallback': 'gemini'
                }
            elif 'context length' in error_str:
                return {
                    'retry': True,
                    'reduce_context': True,
                    'fallback': None
                }
        
        elif provider_name == 'gemini':
            if 'quota' in error_str:
                return {
                    'retry': True,
                    'wait_time': 300,
                    'fallback': 'openai'
                }
            elif 'invalid' in error_str:
                return {
                    'retry': False,
                    'log_error': True,
                    'fallback': None
                }
        
        # Default handling
        return {
            'retry': False,
            'log_error': True,
            'fallback': None
        }
    
    return handle_provider_error


class ErrorRecoveryStrategy:
    """Strategies for recovering from different types of errors."""
    
    def __init__(self):
        """Initialize recovery strategies."""
        self.strategies = {
            ErrorCategory.NETWORK: self._network_recovery,
            ErrorCategory.DATABASE: self._database_recovery,
            ErrorCategory.PARSING: self._parsing_recovery,
            ErrorCategory.RESOURCE: self._resource_recovery,
            ErrorCategory.PROVIDER: self._provider_recovery
        }
    
    def attempt_recovery(self, 
                        error_context: ErrorContext,
                        retry_func: Optional[Callable] = None) -> bool:
        """Attempt to recover from an error.
        
        Args:
            error_context: Error context information
            retry_func: Function to retry if applicable
            
        Returns:
            True if recovery successful
        """
        strategy = self.strategies.get(error_context.category)
        
        if strategy:
            return strategy(error_context, retry_func)
        
        return False
    
    def _network_recovery(self, 
                         error_context: ErrorContext,
                         retry_func: Optional[Callable]) -> bool:
        """Recover from network errors."""
        if retry_func and 'timeout' in error_context.error_message.lower():
            try:
                import time
                time.sleep(5)  # Wait before retry
                retry_func()
                return True
            except:
                return False
        return False
    
    def _database_recovery(self,
                          error_context: ErrorContext,
                          retry_func: Optional[Callable]) -> bool:
        """Recover from database errors."""
        # Could implement connection pool reset, retry logic, etc.
        return False
    
    def _parsing_recovery(self,
                         error_context: ErrorContext,
                         retry_func: Optional[Callable]) -> bool:
        """Recover from parsing errors."""
        # Could implement data cleaning, format conversion, etc.
        return False
    
    def _resource_recovery(self,
                          error_context: ErrorContext,
                          retry_func: Optional[Callable]) -> bool:
        """Recover from resource errors."""
        if 'memory' in error_context.error_message.lower():
            try:
                import gc
                gc.collect()
                if retry_func:
                    retry_func()
                return True
            except:
                return False
        return False
    
    def _provider_recovery(self,
                          error_context: ErrorContext,
                          retry_func: Optional[Callable]) -> bool:
        """Recover from provider errors."""
        # Could implement provider switching, rate limiting, etc.
        return False