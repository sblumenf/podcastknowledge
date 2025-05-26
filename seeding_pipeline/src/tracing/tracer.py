"""Core OpenTelemetry tracer configuration and utilities."""

import functools
import asyncio
from typing import Optional, Dict, Any, Callable, TypeVar, Union
from contextlib import contextmanager
import os
import logging

from opentelemetry import trace, context, propagate
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from ..core.config import PipelineConfig
from ..__version__ import __version__

logger = logging.getLogger(__name__)

# Type variables for decorators
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_tracer_provider: Optional[TracerProvider] = None


def init_tracing(
    service_name: str = "podcast-kg-pipeline",
    jaeger_host: Optional[str] = None,
    jaeger_port: Optional[int] = None,
    config: Optional[PipelineConfig] = None,
    enable_console: bool = False,
) -> trace.Tracer:
    """Initialize distributed tracing with OpenTelemetry and Jaeger.
    
    Args:
        service_name: Name of the service for tracing
        jaeger_host: Jaeger collector host (default from env or localhost)
        jaeger_port: Jaeger collector port (default from env or 6831)
        config: Pipeline configuration
        enable_console: Whether to also export spans to console
        
    Returns:
        Configured tracer instance
    """
    global _tracer, _tracer_provider
    
    if _tracer is not None:
        return _tracer
    
    # Get configuration
    if config:
        jaeger_host = jaeger_host or getattr(config, 'jaeger_host', 'localhost')
        jaeger_port = jaeger_port or getattr(config, 'jaeger_port', 6831)
    else:
        jaeger_host = jaeger_host or os.environ.get('JAEGER_HOST', 'localhost')
        jaeger_port = jaeger_port or int(os.environ.get('JAEGER_PORT', '6831'))
    
    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: __version__,
        "deployment.environment": os.environ.get('ENVIRONMENT', 'development'),
        "host.name": os.environ.get('HOSTNAME', 'unknown'),
    })
    
    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)
    
    # Configure Jaeger exporter
    try:
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
            udp_split_oversized_batches=True,
        )
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(jaeger_exporter)
        )
        logger.info(f"Jaeger tracing enabled: {jaeger_host}:{jaeger_port}")
    except Exception as e:
        logger.warning(f"Failed to initialize Jaeger exporter: {e}")
        # Fall back to console exporter
        enable_console = True
    
    # Add console exporter if requested or as fallback
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(console_exporter)
        )
        logger.info("Console tracing enabled")
    
    # Set as global tracer provider
    trace.set_tracer_provider(_tracer_provider)
    
    # Configure propagator for context propagation
    propagate.set_global_textmap(TraceContextTextMapPropagator())
    
    # Instrument logging to include trace context
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    # Create tracer
    _tracer = trace.get_tracer(
        service_name,
        __version__,
        tracer_provider=_tracer_provider
    )
    
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = init_tracing()
    return _tracer


def trace_method(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
    set_status_on_exception: bool = True,
) -> Callable[[F], F]:
    """Decorator to trace a method execution.
    
    Args:
        name: Span name (defaults to function name)
        attributes: Additional span attributes
        record_exception: Whether to record exceptions
        set_status_on_exception: Whether to set error status on exception
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes
                if attributes:
                    span.set_attributes(attributes)
                
                # Add method-specific attributes
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("function.name", func.__name__)
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                    if set_status_on_exception:
                        span.set_status(
                            Status(StatusCode.ERROR, str(e))
                        )
                    raise
        
        return wrapper
    return decorator


def trace_async(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
    set_status_on_exception: bool = True,
) -> Callable[[F], F]:
    """Decorator to trace an async method execution.
    
    Args:
        name: Span name (defaults to function name)
        attributes: Additional span attributes
        record_exception: Whether to record exceptions
        set_status_on_exception: Whether to set error status on exception
        
    Returns:
        Decorated async function
    """
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes
                if attributes:
                    span.set_attributes(attributes)
                
                # Add method-specific attributes
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.async", True)
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                    if set_status_on_exception:
                        span.set_status(
                            Status(StatusCode.ERROR, str(e))
                        )
                    raise
        
        return wrapper
    return decorator


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """Context manager to create a new span.
    
    Args:
        name: Span name
        attributes: Span attributes
        kind: Span kind (INTERNAL, SERVER, CLIENT, etc.)
        
    Yields:
        The created span
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            span.set_attributes(attributes)
        yield span


def get_current_span() -> Optional[Span]:
    """Get the currently active span."""
    return trace.get_current_span()


def add_span_attributes(attributes: Dict[str, Any]) -> None:
    """Add attributes to the current span.
    
    Args:
        attributes: Dictionary of attributes to add
    """
    span = get_current_span()
    if span and span.is_recording():
        span.set_attributes(attributes)


def record_exception(
    exception: Exception,
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an exception in the current span.
    
    Args:
        exception: The exception to record
        attributes: Additional attributes for the exception
    """
    span = get_current_span()
    if span and span.is_recording():
        span.record_exception(exception, attributes=attributes)


def set_span_status(code: StatusCode, description: Optional[str] = None) -> None:
    """Set the status of the current span.
    
    Args:
        code: Status code (OK, ERROR, UNSET)
        description: Optional status description
    """
    span = get_current_span()
    if span and span.is_recording():
        span.set_status(Status(code, description))


def inject_context(carrier: Dict[str, Any]) -> Dict[str, Any]:
    """Inject trace context into a carrier for propagation.
    
    Args:
        carrier: Dictionary to inject context into
        
    Returns:
        Carrier with injected context
    """
    propagate.inject(carrier)
    return carrier


def extract_context(carrier: Dict[str, Any]) -> context.Context:
    """Extract trace context from a carrier.
    
    Args:
        carrier: Dictionary containing trace context
        
    Returns:
        Extracted context
    """
    return propagate.extract(carrier)