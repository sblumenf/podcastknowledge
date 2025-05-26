"""Tracing middleware and decorators for various components."""

import time
import functools
from typing import Optional, Dict, Any, Callable, TypeVar
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .tracer import get_tracer, get_current_span, add_span_attributes

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])


class TracingMiddleware:
    """Base middleware for adding tracing to various components."""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.tracer = get_tracer()
    
    def trace_operation(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    ):
        """Create a traced operation context.
        
        Args:
            operation_name: Name of the operation
            attributes: Additional span attributes
            kind: Span kind
            
        Returns:
            Context manager for the operation
        """
        span_name = f"{self.component_name}.{operation_name}"
        return self.tracer.start_as_current_span(
            span_name,
            kind=kind,
            attributes=attributes or {}
        )


def trace_request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
) -> Callable[[F], F]:
    """Decorator to trace HTTP requests.
    
    Args:
        method: HTTP method
        path: Request path
        headers: Request headers
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"{method} {path}",
                kind=trace.SpanKind.SERVER
            ) as span:
                # Add HTTP attributes
                span.set_attributes({
                    "http.method": method,
                    "http.path": path,
                    "http.scheme": "http",
                })
                
                # Add headers if provided
                if headers:
                    for key, value in headers.items():
                        if key.lower() not in ['authorization', 'cookie']:
                            span.set_attribute(f"http.header.{key}", value)
                
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    
                    # Add response attributes
                    if hasattr(result, 'status_code'):
                        span.set_attribute("http.status_code", result.status_code)
                        if result.status_code >= 400:
                            span.set_status(
                                Status(StatusCode.ERROR, f"HTTP {result.status_code}")
                            )
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("http.duration_ms", duration * 1000)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"{method} {path}",
                kind=trace.SpanKind.SERVER
            ) as span:
                # Add HTTP attributes
                span.set_attributes({
                    "http.method": method,
                    "http.path": path,
                    "http.scheme": "http",
                })
                
                # Add headers if provided
                if headers:
                    for key, value in headers.items():
                        if key.lower() not in ['authorization', 'cookie']:
                            span.set_attribute(f"http.header.{key}", value)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    
                    # Add response attributes
                    if hasattr(result, 'status_code'):
                        span.set_attribute("http.status_code", result.status_code)
                        if result.status_code >= 400:
                            span.set_status(
                                Status(StatusCode.ERROR, f"HTTP {result.status_code}")
                            )
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("http.duration_ms", duration * 1000)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def trace_database(
    operation: str,
    database_type: str = "neo4j",
    query: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to trace database operations.
    
    Args:
        operation: Database operation name
        database_type: Type of database
        query: Optional query string
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"db.{database_type}.{operation}",
                kind=trace.SpanKind.CLIENT
            ) as span:
                # Add database attributes
                span.set_attributes({
                    "db.system": database_type,
                    "db.operation": operation,
                })
                
                if query:
                    # Truncate long queries
                    truncated_query = query[:500] + "..." if len(query) > 500 else query
                    span.set_attribute("db.statement", truncated_query)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("db.duration_ms", duration * 1000)
        
        return wrapper
    return decorator


def trace_provider_call(
    provider_type: str,
    operation: str,
    **attributes: Any,
) -> Callable[[F], F]:
    """Decorator to trace provider API calls.
    
    Args:
        provider_type: Type of provider (audio, llm, etc.)
        operation: Operation name
        **attributes: Additional attributes
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"provider.{provider_type}.{operation}",
                kind=trace.SpanKind.CLIENT
            ) as span:
                # Add provider attributes
                span.set_attributes({
                    "provider.type": provider_type,
                    "provider.operation": operation,
                    **attributes
                })
                
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    
                    # Add result metrics if available
                    if hasattr(result, '__len__'):
                        span.set_attribute("provider.result_size", len(result))
                    
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("provider.duration_ms", duration * 1000)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"provider.{provider_type}.{operation}",
                kind=trace.SpanKind.CLIENT
            ) as span:
                # Add provider attributes
                span.set_attributes({
                    "provider.type": provider_type,
                    "provider.operation": operation,
                    **attributes
                })
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    
                    # Add result metrics if available
                    if hasattr(result, '__len__'):
                        span.set_attribute("provider.result_size", len(result))
                    
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("provider.duration_ms", duration * 1000)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def trace_queue_operation(
    queue_name: str,
    operation: str,
    message_type: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to trace queue operations.
    
    Args:
        queue_name: Name of the queue
        operation: Operation type (publish, consume, etc.)
        message_type: Optional message type
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_kind = (
                trace.SpanKind.PRODUCER if operation in ['publish', 'send']
                else trace.SpanKind.CONSUMER
            )
            
            with tracer.start_as_current_span(
                f"queue.{operation}",
                kind=span_kind
            ) as span:
                # Add queue attributes
                span.set_attributes({
                    "messaging.system": "redis",
                    "messaging.destination": queue_name,
                    "messaging.operation": operation,
                })
                
                if message_type:
                    span.set_attribute("messaging.message_type", message_type)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    
                    # Add message count if available
                    if hasattr(result, '__len__'):
                        span.set_attribute("messaging.message_count", len(result))
                    
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("messaging.duration_ms", duration * 1000)
        
        return wrapper
    return decorator


@contextmanager
def trace_business_operation(
    name: str,
    operation_type: str,
    **attributes: Any,
):
    """Context manager for tracing business logic operations.
    
    Args:
        name: Operation name
        operation_type: Type of operation
        **attributes: Additional attributes
        
    Yields:
        The span for additional configuration
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"business.{operation_type}.{name}"
    ) as span:
        span.set_attributes({
            "business.operation": name,
            "business.type": operation_type,
            **attributes
        })
        
        start_time = time.time()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute("business.duration_ms", duration * 1000)