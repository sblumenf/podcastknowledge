"""Unit tests for distributed tracing functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.tracing import (
    init_tracing,
    get_tracer,
    trace_method,
    trace_async,
    add_span_attributes,
    record_exception,
    set_span_status,
    create_span,
    get_current_span,
)
from src.tracing.config import TracingConfig
from src.tracing.middleware import (
    trace_request,
    trace_database,
    trace_provider_call,
    trace_queue_operation,
)


class TestTracingCore:
    """Test core tracing functionality."""
    
    def test_init_tracing(self):
        """Test tracing initialization."""
        with patch('src.tracing.tracer.TracerProvider') as mock_provider:
            with patch('src.tracing.tracer.JaegerExporter') as mock_exporter:
                tracer = init_tracing(
                    service_name="test-service",
                    jaeger_host="localhost",
                    jaeger_port=6831,
                )
                
                assert tracer is not None
                mock_provider.assert_called_once()
                mock_exporter.assert_called_once()
    
    def test_get_tracer_singleton(self):
        """Test tracer singleton behavior."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        assert tracer1 is tracer2
    
    def test_trace_method_decorator(self):
        """Test method tracing decorator."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_method(name="test.operation")
            def test_function(x, y):
                return x + y
            
            result = test_function(1, 2)
            
            assert result == 3
            mock_tracer.start_as_current_span.assert_called_once_with("test.operation")
            mock_span.set_status.assert_called_once()
    
    def test_trace_method_with_exception(self):
        """Test method tracing with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_method(name="test.operation")
            def test_function():
                raise ValueError("Test error")
            
            with pytest.raises(ValueError):
                test_function()
            
            mock_span.record_exception.assert_called_once()
            mock_span.set_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_trace_async_decorator(self):
        """Test async method tracing decorator."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_async(name="test.async_operation")
            async def test_async_function(x, y):
                return x + y
            
            result = await test_async_function(1, 2)
            
            assert result == 3
            mock_tracer.start_as_current_span.assert_called_once_with("test.async_operation")
            mock_span.set_attribute.assert_any_call("function.async", True)
    
    def test_create_span_context_manager(self):
        """Test span creation context manager."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            with create_span("test_span", attributes={"key": "value"}) as span:
                assert span == mock_span
            
            mock_tracer.start_as_current_span.assert_called_once()
            mock_span.set_attributes.assert_called_with({"key": "value"})
    
    def test_add_span_attributes(self):
        """Test adding attributes to current span."""
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        
        with patch('src.tracing.tracer.trace.get_current_span', return_value=mock_span):
            add_span_attributes({"attr1": "value1", "attr2": 42})
            
            mock_span.set_attributes.assert_called_once_with({
                "attr1": "value1",
                "attr2": 42
            })
    
    def test_record_exception(self):
        """Test exception recording."""
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        exception = ValueError("Test error")
        
        with patch('src.tracing.tracer.trace.get_current_span', return_value=mock_span):
            record_exception(exception, attributes={"error.type": "validation"})
            
            mock_span.record_exception.assert_called_once_with(
                exception,
                attributes={"error.type": "validation"}
            )


class TestTracingMiddleware:
    """Test tracing middleware decorators."""
    
    def test_trace_request_decorator(self):
        """Test HTTP request tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_request("GET", "/api/test")
            def api_handler():
                return {"status": "ok"}
            
            result = api_handler()
            
            assert result == {"status": "ok"}
            mock_tracer.start_as_current_span.assert_called_once()
            call_args = mock_tracer.start_as_current_span.call_args
            assert call_args[0][0] == "GET /api/test"
            assert call_args[1]["kind"] == trace.SpanKind.SERVER
    
    def test_trace_database_decorator(self):
        """Test database operation tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_database("query", "neo4j", query="MATCH (n) RETURN n")
            def db_query():
                return [{"n": "node1"}]
            
            result = db_query()
            
            assert result == [{"n": "node1"}]
            mock_span.set_attributes.assert_called()
            attrs = mock_span.set_attributes.call_args[0][0]
            assert attrs["db.system"] == "neo4j"
            assert attrs["db.operation"] == "query"
    
    def test_trace_provider_call_decorator(self):
        """Test provider call tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with patch('src.tracing.tracer.get_tracer', return_value=mock_tracer):
            @trace_provider_call("llm", "generate", model="gemini")
            def llm_call():
                return "Generated text"
            
            result = llm_call()
            
            assert result == "Generated text"
            mock_span.set_attributes.assert_called()
            attrs = mock_span.set_attributes.call_args[0][0]
            assert attrs["provider.type"] == "llm"
            assert attrs["provider.operation"] == "generate"
            assert attrs["model"] == "gemini"


class TestTracingConfig:
    """Test tracing configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TracingConfig()
        
        assert config.service_name == "podcast-kg-pipeline"
        assert config.environment == "development"
        assert config.jaeger_host == "localhost"
        assert config.jaeger_port == 6831
        assert config.sampling_rate == 1.0
        assert config.jaeger_enabled is True
    
    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("TRACING_SERVICE_NAME", "test-service")
        monkeypatch.setenv("JAEGER_HOST", "jaeger.example.com")
        monkeypatch.setenv("JAEGER_PORT", "16831")
        monkeypatch.setenv("TRACING_SAMPLING_RATE", "0.5")
        monkeypatch.setenv("ENVIRONMENT", "production")
        
        config = TracingConfig.from_env()
        
        assert config.service_name == "test-service"
        assert config.jaeger_host == "jaeger.example.com"
        assert config.jaeger_port == 16831
        assert config.sampling_rate == 0.5
        assert config.environment == "production"
    
    def test_config_to_dict(self):
        """Test configuration dictionary conversion."""
        config = TracingConfig(
            service_name="test-service",
            jaeger_host="jaeger.local",
            sampling_rate=0.1
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["service_name"] == "test-service"
        assert config_dict["jaeger"]["host"] == "jaeger.local"
        assert config_dict["sampling"]["rate"] == 0.1