"""Integration tests for distributed tracing."""

import pytest
import time
import asyncio
from unittest.mock import patch

from src.tracing import init_tracing, create_span, trace_method
from src.tracing.config import TracingConfig
from src.seeding import PodcastKnowledgePipeline
from src.core.config import PipelineConfig


class TestTracingIntegration:
    """Test distributed tracing integration with pipeline components."""
    
    @pytest.fixture
    def tracing_config(self):
        """Create test tracing configuration."""
        return TracingConfig(
            service_name="test-pipeline",
            jaeger_enabled=False,  # Disable Jaeger for tests
            console_export=True,   # Use console export for testing
        )
    
    @pytest.fixture
    def pipeline_config(self):
        """Create test pipeline configuration."""
        config = PipelineConfig()
        config.neo4j_uri = "bolt://localhost:7687"
        config.neo4j_user = "neo4j"
        config.neo4j_password = "test"
        return config
    
    def test_pipeline_initialization_tracing(self, tracing_config, pipeline_config):
        """Test tracing during pipeline initialization."""
        # Initialize tracing
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        with create_span("test.pipeline_init") as span:
            # Mock providers to avoid actual connections
            with patch('src.factories.provider_factory.ProviderFactory.get_provider'):
                pipeline = PodcastKnowledgePipeline(pipeline_config)
                
                # Check span attributes were set
                assert span.is_recording()
                span.set_attribute("test.status", "initialized")
    
    def test_nested_span_hierarchy(self, tracing_config):
        """Test nested span creation and hierarchy."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        with create_span("parent_operation") as parent_span:
            parent_span.set_attribute("level", "parent")
            
            with create_span("child_operation") as child_span:
                child_span.set_attribute("level", "child")
                
                with create_span("grandchild_operation") as grandchild_span:
                    grandchild_span.set_attribute("level", "grandchild")
                    time.sleep(0.1)  # Simulate work
        
        # Spans should complete without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_async_tracing_flow(self, tracing_config):
        """Test tracing across async operations."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        async def async_operation(name: str, delay: float):
            with create_span(f"async.{name}") as span:
                span.set_attribute("operation.name", name)
                span.set_attribute("operation.delay", delay)
                await asyncio.sleep(delay)
                return f"completed_{name}"
        
        with create_span("test.async_flow"):
            # Run multiple async operations
            results = await asyncio.gather(
                async_operation("op1", 0.1),
                async_operation("op2", 0.2),
                async_operation("op3", 0.15),
            )
            
            assert len(results) == 3
            assert all("completed_" in r for r in results)
    
    def test_error_propagation_tracing(self, tracing_config):
        """Test error tracking through spans."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        @trace_method(name="failing_operation")
        def failing_function():
            raise ValueError("Intentional test error")
        
        with create_span("test.error_flow") as span:
            try:
                failing_function()
            except ValueError as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        
        # Test should complete without raising
        assert True
    
    def test_cross_component_tracing(self, tracing_config):
        """Test tracing across multiple components."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        class MockAudioProvider:
            @trace_method(name="audio.transcribe")
            def transcribe(self, audio_path):
                time.sleep(0.1)
                return [{"text": "test transcript", "start": 0, "end": 10}]
        
        class MockLLMProvider:
            @trace_method(name="llm.extract")
            def extract_knowledge(self, text):
                time.sleep(0.05)
                return {"entities": ["entity1"], "insights": ["insight1"]}
        
        class MockGraphProvider:
            @trace_method(name="graph.save")
            def save_data(self, data):
                time.sleep(0.02)
                return True
        
        with create_span("test.component_flow") as span:
            # Simulate pipeline flow
            audio = MockAudioProvider()
            llm = MockLLMProvider()
            graph = MockGraphProvider()
            
            transcript = audio.transcribe("test.mp3")
            knowledge = llm.extract_knowledge(transcript[0]["text"])
            result = graph.save_data(knowledge)
            
            span.set_attribute("pipeline.complete", True)
            span.set_attribute("result.success", result)
    
    def test_batch_processing_tracing(self, tracing_config):
        """Test tracing for batch operations."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        def process_item(item_id: int):
            with create_span(f"process_item_{item_id}") as span:
                span.set_attribute("item.id", item_id)
                time.sleep(0.01)  # Simulate work
                return item_id * 2
        
        with create_span("test.batch_processing") as span:
            items = list(range(10))
            results = []
            
            span.set_attribute("batch.size", len(items))
            
            for item in items:
                result = process_item(item)
                results.append(result)
            
            span.set_attribute("batch.completed", len(results))
            span.set_attribute("batch.success", True)
            
            assert len(results) == 10
            assert results == [i * 2 for i in range(10)]
    
    def test_context_propagation(self, tracing_config):
        """Test trace context propagation."""
        init_tracing(
            service_name=tracing_config.service_name,
            enable_console=tracing_config.console_export,
        )
        
        from src.tracing import inject_context, extract_context
        
        # Create a span and inject context
        with create_span("test.context_source") as span:
            carrier = {}
            inject_context(carrier)
            
            # Simulate passing context to another service
            assert "traceparent" in carrier or len(carrier) > 0
            
            # Extract context in "another service"
            context = extract_context(carrier)
            
            # Continue trace with extracted context
            with trace.use_context(context):
                with create_span("test.context_target") as target_span:
                    target_span.set_attribute("context.propagated", True)