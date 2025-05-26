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