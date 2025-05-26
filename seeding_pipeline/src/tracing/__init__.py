"""Distributed tracing module for the Podcast Knowledge Pipeline.

This module provides OpenTelemetry-based distributed tracing
with Jaeger backend integration for end-to-end observability.
"""

from .tracer import (
    init_tracing,
    get_tracer,
    trace_method,
    trace_async,
    add_span_attributes,
    record_exception,
    set_span_status,
    create_span,
    get_current_span,
    inject_context,
    extract_context,
)

from .middleware import (
    TracingMiddleware,
    trace_request,
    trace_database,
    trace_provider_call,
    trace_queue_operation,
)

from .instrumentation import (
    instrument_neo4j,
    instrument_redis,
    instrument_requests,
    instrument_all,
)

__all__ = [
    # Core tracing
    'init_tracing',
    'get_tracer',
    'trace_method',
    'trace_async',
    'add_span_attributes',
    'record_exception',
    'set_span_status',
    'create_span',
    'get_current_span',
    'inject_context',
    'extract_context',
    
    # Middleware
    'TracingMiddleware',
    'trace_request',
    'trace_database',
    'trace_provider_call',
    'trace_queue_operation',
    
    # Instrumentation
    'instrument_neo4j',
    'instrument_redis',
    'instrument_requests',
    'instrument_all',
]