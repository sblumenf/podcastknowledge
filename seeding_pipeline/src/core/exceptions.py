"""
Custom exceptions for the podcast knowledge pipeline.

This module defines the exception hierarchy used throughout the system.
Each exception includes severity levels to guide error handling strategies.
"""

from enum import Enum
from typing import Optional, Any


class ErrorSeverity(Enum):
    """Error severity levels for guiding error handling."""
    CRITICAL = "critical"  # System must stop
    WARNING = "warning"    # Can continue with degraded functionality
    INFO = "info"         # Informational, no action needed


class PodcastProcessingError(Exception):
    """
    Base exception for all podcast processing errors.
    
    Attributes:
        message: Error description
        severity: Error severity level
        details: Optional additional error details
    """
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.details = details or {}
        
    def __str__(self) -> str:
        """String representation of the error."""
        base = f"[{self.severity.value.upper()}] {self.message}"
        if self.details:
            base += f" | Details: {self.details}"
        return base


class DatabaseConnectionError(PodcastProcessingError):
    """
    Raised when Neo4j connection fails.
    
    This is always a CRITICAL error as the system cannot function
    without database connectivity.
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, ErrorSeverity.CRITICAL, details)


class AudioProcessingError(PodcastProcessingError):
    """
    Raised when audio transcription or diarization fails.
    
    Default severity is WARNING as processing can sometimes continue
    with partial results.
    """
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


class LLMProcessingError(PodcastProcessingError):
    """
    Raised when LLM processing fails.
    
    Default severity is WARNING as the system can often retry
    or fall back to alternative models.
    """
    
    def __init__(
        self, 
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


class ConfigurationError(PodcastProcessingError):
    """
    Raised when configuration is invalid.
    
    This is always a CRITICAL error as invalid configuration
    prevents system initialization.
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, ErrorSeverity.CRITICAL, details)


class PipelineError(PodcastProcessingError):
    """
    Raised when pipeline processing fails.
    
    Default severity is CRITICAL as pipeline failures usually
    prevent further processing.
    """
    
    def __init__(
        self, 
        message: str,
        severity: ErrorSeverity = ErrorSeverity.CRITICAL,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


# Additional specific exceptions for better error handling
class ValidationError(PodcastProcessingError):
    """
    Raised when input validation fails.
    
    Default severity is WARNING as invalid inputs can often be skipped.
    """
    
    def __init__(
        self, 
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, ErrorSeverity.WARNING, details)


class ProviderError(PodcastProcessingError):
    """
    Base exception for provider-specific errors.
    
    Used when a provider fails but the system might be able to
    fall back to an alternative provider.
    """
    
    def __init__(
        self,
        provider_name: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["provider"] = provider_name
        super().__init__(message, severity, details)


class CriticalError(PodcastProcessingError):
    """
    Raised for unrecoverable errors that require immediate termination.
    
    This is always a CRITICAL error and should trigger system shutdown.
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, ErrorSeverity.CRITICAL, details)


class ExtractionError(PodcastProcessingError):
    """
    Raised when knowledge extraction fails.
    
    Use this for failures in entity extraction, insight generation,
    or quote extraction. Default severity is WARNING as extraction
    can often continue with partial results.
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


class RateLimitError(ProviderError):
    """
    Raised when API rate limits are exceeded.
    
    This should trigger exponential backoff and retry logic.
    Default severity is WARNING as the operation can be retried.
    """
    
    def __init__(
        self,
        provider_name: str,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(provider_name, message, ErrorSeverity.WARNING, details)


class TimeoutError(PodcastProcessingError):
    """
    Raised when an operation exceeds its time limit.
    
    Default severity is WARNING as timeouts can often be retried
    with adjusted parameters.
    """
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if operation:
            details["operation"] = operation
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, ErrorSeverity.WARNING, details)


class ResourceError(PodcastProcessingError):
    """
    Raised when system resources are exhausted.
    
    Use this for memory, disk space, or other resource limitations.
    Default severity is CRITICAL as resource exhaustion usually
    requires intervention.
    """
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if resource_type:
            details["resource_type"] = resource_type
        super().__init__(message, ErrorSeverity.CRITICAL, details)


class DataIntegrityError(PodcastProcessingError):
    """
    Raised when data consistency or integrity issues are detected.
    
    Use this for corrupted data, missing required fields, or
    inconsistent state. Default severity is CRITICAL.
    """
    
    def __init__(
        self,
        message: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if entity_type:
            details["entity_type"] = entity_type
        if entity_id:
            details["entity_id"] = entity_id
        super().__init__(message, ErrorSeverity.CRITICAL, details)


# Aliases for backward compatibility
ConnectionError = DatabaseConnectionError
PodcastKGError = PodcastProcessingError  # Legacy name

# Additional specific exceptions
class ParsingError(PodcastProcessingError):
    """
    Raised when parsing fails (e.g., feed parsing, JSON parsing).
    
    Default severity is WARNING as parsing errors can often be skipped.
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


class CheckpointError(PodcastProcessingError):
    """
    Raised when checkpoint operations fail.
    
    Default severity is WARNING as checkpoint failures can often be recovered.
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


class BatchProcessingError(PodcastProcessingError):
    """
    Raised when batch processing fails.
    
    Default severity is WARNING as individual items can often be retried.
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, severity, details)


# Exception Usage Guidelines
"""
Exception Usage Guidelines:

1. PodcastProcessingError - Base exception, rarely used directly
2. ConfigurationError - Invalid config, missing required settings
3. ValidationError - Invalid input data, failed validation rules
4. DatabaseConnectionError - Neo4j connection failures
5. LLMProcessingError - LLM API failures, response parsing errors
6. ExtractionError - Entity/insight/quote extraction failures
7. ProviderError - Generic provider failures, use specific types when possible
8. RateLimitError - API rate limit exceeded (subclass of ProviderError)
9. TimeoutError - Operation timeout exceeded
10. ResourceError - Memory, disk, or other resource exhaustion
11. DataIntegrityError - Data consistency or corruption issues
12. PipelineError - Overall pipeline processing failures
13. CriticalError - Unrecoverable errors requiring shutdown

Severity Guidelines:
- CRITICAL: System must stop, requires intervention
- WARNING: Can continue with degraded functionality or retry
- INFO: Informational only, no action needed

Always include relevant details in the exception for debugging.
"""