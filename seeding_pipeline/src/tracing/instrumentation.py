"""Auto-instrumentation for various libraries and components."""

import logging
from typing import Optional, Dict, Any, Callable
import functools

from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry import trace

from neo4j import GraphDatabase
from neo4j._sync.work import Session as Neo4jSession

from .tracer import get_tracer
from .middleware import trace_database

logger = logging.getLogger(__name__)


def instrument_neo4j():
    """Instrument Neo4j driver for distributed tracing."""
    try:
        # Monkey-patch Neo4j session methods
        original_run = Neo4jSession.run
        
        @functools.wraps(original_run)
        def traced_run(self, query, parameters=None, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                "neo4j.query",
                kind=trace.SpanKind.CLIENT
            ) as span:
                # Add query attributes
                span.set_attributes({
                    "db.system": "neo4j",
                    "db.operation": "query",
                    "db.statement": query[:500] + "..." if len(query) > 500 else query,
                })
                
                if parameters:
                    # Add parameter count (not values for security)
                    span.set_attribute("db.parameter_count", len(parameters))
                
                try:
                    result = original_run(self, query, parameters, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    raise
        
        Neo4jSession.run = traced_run
        logger.info("Neo4j instrumentation enabled")
        
    except Exception as e:
        logger.warning(f"Failed to instrument Neo4j: {e}")


def instrument_redis():
    """Instrument Redis client for distributed tracing."""
    try:
        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")


def instrument_requests():
    """Instrument HTTP requests library for distributed tracing."""
    try:
        RequestsInstrumentor().instrument()
        URLLib3Instrumentor().instrument()
        logger.info("Requests/urllib3 instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument requests: {e}")


def instrument_logging():
    """Instrument logging to include trace context."""
    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
        logger.info("Logging instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument logging: {e}")


def instrument_langchain():
    """Instrument LangChain for distributed tracing."""
    try:
        from langchain.callbacks import OpenAICallbackHandler
        from opentelemetry import trace
        
        class TracingCallbackHandler(OpenAICallbackHandler):
            """Custom callback handler that creates spans for LangChain operations."""
            
            def __init__(self):
                super().__init__()
                self.tracer = get_tracer()
                self.active_spans = {}
            
            def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs) -> None:
                super().on_llm_start(serialized, prompts, **kwargs)
                
                # Create span for LLM call
                span = self.tracer.start_span(
                    "langchain.llm.call",
                    kind=trace.SpanKind.CLIENT
                )
                span.set_attributes({
                    "llm.model": serialized.get("name", "unknown"),
                    "llm.prompt_count": len(prompts),
                    "llm.prompt_tokens": sum(len(p.split()) for p in prompts),
                })
                
                # Store span for later
                run_id = kwargs.get("run_id", id(prompts))
                self.active_spans[run_id] = span
            
            def on_llm_end(self, response, **kwargs) -> None:
                super().on_llm_end(response, **kwargs)
                
                # End the span
                run_id = kwargs.get("run_id")
                if run_id in self.active_spans:
                    span = self.active_spans.pop(run_id)
                    
                    # Add response metrics
                    if hasattr(response, "generations"):
                        total_tokens = sum(
                            len(g.text.split()) 
                            for gens in response.generations 
                            for g in gens
                        )
                        span.set_attribute("llm.response_tokens", total_tokens)
                    
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    span.end()
            
            def on_llm_error(self, error: Exception, **kwargs) -> None:
                super().on_llm_error(error, **kwargs)
                
                # Record error in span
                run_id = kwargs.get("run_id")
                if run_id in self.active_spans:
                    span = self.active_spans.pop(run_id)
                    span.record_exception(error)
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(error))
                    )
                    span.end()
        
        # Register the callback handler globally
        import langchain
        if hasattr(langchain, "callbacks"):
            langchain.callbacks.set_handler(TracingCallbackHandler())
            logger.info("LangChain instrumentation enabled")
        
    except ImportError:
        logger.debug("LangChain not installed, skipping instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument LangChain: {e}")


def instrument_whisper():
    """Instrument Whisper/audio processing for distributed tracing."""
    try:
        import whisper
        
        # Monkey-patch whisper transcribe method
        original_transcribe = whisper.transcribe
        
        @functools.wraps(original_transcribe)
        def traced_transcribe(model, audio, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                "whisper.transcribe",
                kind=trace.SpanKind.INTERNAL
            ) as span:
                # Add audio attributes
                span.set_attributes({
                    "audio.model": getattr(model, "name", "unknown"),
                    "audio.language": kwargs.get("language", "auto"),
                })
                
                if hasattr(audio, "shape"):
                    span.set_attribute("audio.duration_seconds", audio.shape[0] / 16000)
                
                try:
                    result = original_transcribe(model, audio, **kwargs)
                    
                    # Add result metrics
                    if isinstance(result, dict) and "text" in result:
                        span.set_attribute("audio.transcript_length", len(result["text"]))
                    
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    raise
        
        whisper.transcribe = traced_transcribe
        logger.info("Whisper instrumentation enabled")
        
    except ImportError:
        logger.debug("Whisper not installed, skipping instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument Whisper: {e}")


def instrument_all():
    """Enable all available instrumentations."""
    instrument_neo4j()
    instrument_redis()
    instrument_requests()
    instrument_logging()
    instrument_langchain()
    instrument_whisper()
    
    logger.info("All available instrumentations enabled")