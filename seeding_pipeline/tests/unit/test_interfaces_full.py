"""Comprehensive tests for src/core/interfaces.py - targeting 100% coverage.

This test suite covers:
- All Protocol definitions and their methods
- All dataclass models in interfaces
- Abstract base classes and context managers
- Type hints and protocol compliance
- Edge cases and error scenarios
"""

from contextlib import AbstractContextManager
from typing import Dict, Any, List, Optional
from unittest import mock

import pytest

from src.core.interfaces import (
    # Protocols
    HealthCheckable, AudioProvider, LLMProvider, GraphProvider, 
    EmbeddingProvider, KnowledgeExtractor,
    # Dataclasses
    DiarizationSegment, TranscriptSegment, LLMResponse,
    ExtractedEntity, ExtractedInsight, ExtractedQuote,
    # Context managers
    Neo4jManager
)


class TestHealthCheckableProtocol:
    """Test HealthCheckable protocol."""
    
    def test_health_checkable_protocol_definition(self):
        """Test that HealthCheckable is properly defined as a Protocol."""
        # Create a class that implements the protocol
        class HealthyComponent:
            def health_check(self) -> Dict[str, Any]:
                return {
                    "status": "healthy",
                    "details": {"uptime": 100},
                    "timestamp": "2024-01-01T00:00:00"
                }
        
        # Should be able to use it as HealthCheckable
        component: HealthCheckable = HealthyComponent()
        result = component.health_check()
        
        assert result["status"] == "healthy"
        assert "details" in result
        assert "timestamp" in result
    
    def test_health_checkable_with_different_implementations(self):
        """Test different implementations of HealthCheckable."""
        # Degraded component
        class DegradedComponent:
            def health_check(self) -> Dict[str, Any]:
                return {
                    "status": "degraded",
                    "details": {"memory_usage": "high"},
                    "timestamp": "2024-01-01T00:00:00"
                }
        
        # Unhealthy component
        class UnhealthyComponent:
            def health_check(self) -> Dict[str, Any]:
                return {
                    "status": "unhealthy",
                    "details": {"error": "Connection failed"},
                    "timestamp": "2024-01-01T00:00:00"
                }
        
        degraded: HealthCheckable = DegradedComponent()
        unhealthy: HealthCheckable = UnhealthyComponent()
        
        assert degraded.health_check()["status"] == "degraded"
        assert unhealthy.health_check()["status"] == "unhealthy"


class TestDiarizationSegment:
    """Test DiarizationSegment dataclass."""
    
    def test_diarization_segment_creation_minimal(self):
        """Test creating diarization segment with required fields."""
        segment = DiarizationSegment(
            speaker="speaker1",
            start_time=0.0,
            end_time=10.0
        )
        
        assert segment.speaker == "speaker1"
        assert segment.start_time == 0.0
        assert segment.end_time == 10.0
        assert segment.confidence is None
    
    def test_diarization_segment_creation_full(self):
        """Test creating diarization segment with all fields."""
        segment = DiarizationSegment(
            speaker="speaker2",
            start_time=10.0,
            end_time=20.0,
            confidence=0.95
        )
        
        assert segment.confidence == 0.95
    
    def test_diarization_segment_equality(self):
        """Test diarization segment equality."""
        seg1 = DiarizationSegment("speaker1", 0.0, 10.0, 0.9)
        seg2 = DiarizationSegment("speaker1", 0.0, 10.0, 0.9)
        seg3 = DiarizationSegment("speaker2", 0.0, 10.0, 0.9)
        
        assert seg1 == seg2
        assert seg1 != seg3


class TestTranscriptSegment:
    """Test TranscriptSegment dataclass."""
    
    def test_transcript_segment_creation_minimal(self):
        """Test creating transcript segment with required fields."""
        segment = TranscriptSegment(
            id="seg1",
            text="Hello world",
            start_time=0.0,
            end_time=2.0
        )
        
        assert segment.id == "seg1"
        assert segment.text == "Hello world"
        assert segment.start_time == 0.0
        assert segment.end_time == 2.0
        assert segment.speaker is None
        assert segment.confidence is None
    
    def test_transcript_segment_creation_full(self):
        """Test creating transcript segment with all fields."""
        segment = TranscriptSegment(
            id="seg2",
            text="How are you?",
            start_time=2.0,
            end_time=4.0,
            speaker="speaker1",
            confidence=0.98
        )
        
        assert segment.speaker == "speaker1"
        assert segment.confidence == 0.98


class TestAudioProvider:
    """Test AudioProvider protocol."""
    
    def test_audio_provider_implementation(self):
        """Test implementing AudioProvider protocol."""
        class TestAudioProvider:
            def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
                return [
                    TranscriptSegment(
                        id="seg1",
                        text="Test transcription",
                        start_time=0.0,
                        end_time=5.0
                    )
                ]
            
            def diarize(self, audio_path: str) -> List[DiarizationSegment]:
                return [
                    DiarizationSegment(
                        speaker="speaker1",
                        start_time=0.0,
                        end_time=5.0,
                        confidence=0.9
                    )
                ]
            
            def align_transcript_with_diarization(
                self,
                transcript_segments: List[TranscriptSegment],
                diarization_segments: List[DiarizationSegment]
            ) -> List[TranscriptSegment]:
                # Simple alignment implementation
                for ts in transcript_segments:
                    for ds in diarization_segments:
                        if ts.start_time >= ds.start_time and ts.end_time <= ds.end_time:
                            ts.speaker = ds.speaker
                return transcript_segments
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        provider: AudioProvider = TestAudioProvider()
        
        # Test transcribe
        transcripts = provider.transcribe("test.mp3")
        assert len(transcripts) == 1
        assert transcripts[0].text == "Test transcription"
        
        # Test diarize
        diarizations = provider.diarize("test.mp3")
        assert len(diarizations) == 1
        assert diarizations[0].speaker == "speaker1"
        
        # Test alignment
        aligned = provider.align_transcript_with_diarization(transcripts, diarizations)
        assert aligned[0].speaker == "speaker1"
        
        # Test health check
        health = provider.health_check()
        assert health["status"] == "healthy"


class TestLLMResponse:
    """Test LLMResponse dataclass."""
    
    def test_llm_response_creation_minimal(self):
        """Test creating LLM response with required fields."""
        response = LLMResponse(
            content="Generated text",
            model="gpt-4"
        )
        
        assert response.content == "Generated text"
        assert response.model == "gpt-4"
        assert response.usage is None
        assert response.metadata is None
    
    def test_llm_response_creation_full(self):
        """Test creating LLM response with all fields."""
        response = LLMResponse(
            content="Generated text",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            metadata={"temperature": 0.7, "max_tokens": 100}
        )
        
        assert response.usage["total_tokens"] == 30
        assert response.metadata["temperature"] == 0.7


class TestLLMProvider:
    """Test LLMProvider protocol."""
    
    def test_llm_provider_implementation(self):
        """Test implementing LLMProvider protocol."""
        class TestLLMProvider:
            def invoke(self, prompt: str, temperature: float = 0.3) -> LLMResponse:
                return LLMResponse(
                    content=f"Response to: {prompt}",
                    model="test-model",
                    usage={"prompt_tokens": len(prompt.split()), "completion_tokens": 10}
                )
            
            def invoke_with_retry(
                self,
                prompt: str,
                temperature: float = 0.3,
                max_retries: int = 3
            ) -> LLMResponse:
                # Simulate retry logic
                return self.invoke(prompt, temperature)
            
            def check_rate_limits(self) -> Dict[str, Any]:
                return {
                    "requests_remaining": 1000,
                    "tokens_remaining": 50000,
                    "reset_time": "2024-01-01T01:00:00"
                }
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        provider: LLMProvider = TestLLMProvider()
        
        # Test invoke
        response = provider.invoke("Hello AI")
        assert response.content == "Response to: Hello AI"
        assert response.model == "test-model"
        
        # Test invoke with custom temperature
        response = provider.invoke("Test", temperature=0.9)
        assert "Response to: Test" in response.content
        
        # Test invoke with retry
        response = provider.invoke_with_retry("Retry test", max_retries=5)
        assert "Response to: Retry test" in response.content
        
        # Test rate limits
        limits = provider.check_rate_limits()
        assert limits["requests_remaining"] == 1000
        assert "reset_time" in limits


class TestGraphProvider:
    """Test GraphProvider protocol."""
    
    def test_graph_provider_implementation(self):
        """Test implementing GraphProvider protocol."""
        class TestGraphProvider:
            def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                # Simulate query execution
                if "MATCH" in query:
                    return [{"name": "Node1", "id": 1}, {"name": "Node2", "id": 2}]
                return []
            
            def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                # Simulate write operation
                return {
                    "nodes_created": 1,
                    "relationships_created": 0,
                    "properties_set": 2
                }
            
            def setup_schema(self) -> None:
                # Simulate schema setup
                pass
            
            def get_connection_pool_status(self) -> Dict[str, Any]:
                return {
                    "active_connections": 5,
                    "idle_connections": 10,
                    "max_connections": 50
                }
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        provider: GraphProvider = TestGraphProvider()
        
        # Test query execution
        results = provider.execute_query("MATCH (n) RETURN n")
        assert len(results) == 2
        assert results[0]["name"] == "Node1"
        
        # Test query with parameters
        results = provider.execute_query("MATCH (n:Person {name: $name})", {"name": "Alice"})
        assert isinstance(results, list)
        
        # Test write operation
        write_result = provider.execute_write("CREATE (n:Person {name: 'Bob'})")
        assert write_result["nodes_created"] == 1
        
        # Test schema setup
        provider.setup_schema()  # Should not raise
        
        # Test connection pool status
        pool_status = provider.get_connection_pool_status()
        assert pool_status["active_connections"] == 5
        assert pool_status["max_connections"] == 50


class TestEmbeddingProvider:
    """Test EmbeddingProvider protocol."""
    
    def test_embedding_provider_implementation(self):
        """Test implementing EmbeddingProvider protocol."""
        class TestEmbeddingProvider:
            def generate_embedding(self, text: str) -> List[float]:
                # Simulate embedding generation
                # Return a vector of fixed dimension based on text length
                return [0.1 * i for i in range(384)]  # 384-dimensional embedding
            
            def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.generate_embedding(text) for text in texts]
            
            def get_embedding_dimension(self) -> int:
                return 384
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        provider: EmbeddingProvider = TestEmbeddingProvider()
        
        # Test single embedding
        embedding = provider.generate_embedding("Test text")
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
        
        # Test batch embeddings
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = provider.generate_embeddings_batch(texts)
        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)
        
        # Test embedding dimension
        assert provider.get_embedding_dimension() == 384


class TestExtractedEntities:
    """Test extracted entity dataclasses."""
    
    def test_extracted_entity(self):
        """Test ExtractedEntity dataclass."""
        entity = ExtractedEntity(
            name="OpenAI",
            entity_type="organization",
            description="AI research company",
            confidence=0.95
        )
        
        assert entity.name == "OpenAI"
        assert entity.entity_type == "organization"
        assert entity.description == "AI research company"
        assert entity.confidence == 0.95
        
        # Test with defaults
        entity2 = ExtractedEntity(
            name="GPT",
            entity_type="technology"
        )
        assert entity2.description is None
        assert entity2.confidence == 1.0
    
    def test_extracted_insight(self):
        """Test ExtractedInsight dataclass."""
        insight = ExtractedInsight(
            content="AI will transform healthcare",
            insight_type="prediction",
            confidence=0.8,
            supporting_segments=["seg1", "seg2"]
        )
        
        assert insight.content == "AI will transform healthcare"
        assert insight.insight_type == "prediction"
        assert insight.confidence == 0.8
        assert insight.supporting_segments == ["seg1", "seg2"]
        
        # Test with defaults
        insight2 = ExtractedInsight(
            content="Important finding",
            insight_type="key_point"
        )
        assert insight2.confidence == 1.0
        assert insight2.supporting_segments is None
    
    def test_extracted_quote(self):
        """Test ExtractedQuote dataclass."""
        quote = ExtractedQuote(
            text="The future is already here",
            speaker="William Gibson",
            context="Discussing technology adoption",
            quote_type="insightful"
        )
        
        assert quote.text == "The future is already here"
        assert quote.speaker == "William Gibson"
        assert quote.context == "Discussing technology adoption"
        assert quote.quote_type == "insightful"
        
        # Test with defaults
        quote2 = ExtractedQuote(
            text="Hello world",
            speaker="Unknown"
        )
        assert quote2.context is None
        assert quote2.quote_type == "general"


class TestKnowledgeExtractor:
    """Test KnowledgeExtractor protocol."""
    
    def test_knowledge_extractor_implementation(self):
        """Test implementing KnowledgeExtractor protocol."""
        class TestKnowledgeExtractor:
            def extract_entities(self, transcript: str) -> List[ExtractedEntity]:
                # Simple mock extraction
                if "OpenAI" in transcript:
                    return [
                        ExtractedEntity("OpenAI", "organization", "AI company", 0.9),
                        ExtractedEntity("GPT", "technology", "Language model", 0.85)
                    ]
                return []
            
            def extract_insights(self, transcript: str) -> List[ExtractedInsight]:
                if "future" in transcript:
                    return [
                        ExtractedInsight(
                            "AI will shape the future",
                            "prediction",
                            0.75,
                            ["seg1"]
                        )
                    ]
                return []
            
            def extract_quotes(self, transcript: str) -> List[ExtractedQuote]:
                if "quote:" in transcript.lower():
                    return [
                        ExtractedQuote(
                            "This is a notable quote",
                            "Speaker",
                            "During introduction",
                            "memorable"
                        )
                    ]
                return []
        
        extractor: KnowledgeExtractor = TestKnowledgeExtractor()
        
        # Test entity extraction
        entities = extractor.extract_entities("OpenAI created GPT")
        assert len(entities) == 2
        assert entities[0].name == "OpenAI"
        assert entities[1].name == "GPT"
        
        # Test insight extraction
        insights = extractor.extract_insights("The future of AI is bright")
        assert len(insights) == 1
        assert insights[0].insight_type == "prediction"
        
        # Test quote extraction
        quotes = extractor.extract_quotes("He said quote: something important")
        assert len(quotes) == 1
        assert quotes[0].quote_type == "memorable"


class TestNeo4jManager:
    """Test Neo4jManager abstract context manager."""
    
    def test_neo4j_manager_implementation(self):
        """Test implementing Neo4jManager."""
        class TestNeo4jManager(Neo4jManager):
            def __init__(self):
                self.connected = False
                self.driver = None
            
            def __enter__(self):
                self.connected = True
                self.driver = mock.Mock()  # Mock driver object
                return self.driver
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.connected = False
                if self.driver:
                    self.driver.close()
                return False  # Don't suppress exceptions
        
        # Test context manager usage
        manager = TestNeo4jManager()
        assert not manager.connected
        
        with manager as driver:
            assert manager.connected
            assert driver is not None
        
        assert not manager.connected
    
    def test_neo4j_manager_with_exception(self):
        """Test Neo4jManager handling exceptions."""
        class TestNeo4jManager(Neo4jManager):
            def __enter__(self):
                return mock.Mock()
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                # Log exception info
                if exc_type:
                    print(f"Exception: {exc_type.__name__}: {exc_val}")
                return False  # Propagate exception
        
        manager = TestNeo4jManager()
        
        # Test that exceptions are propagated
        with pytest.raises(ValueError):
            with manager:
                raise ValueError("Test error")
    
    def test_neo4j_manager_abstract_methods(self):
        """Test that Neo4jManager requires implementation of abstract methods."""
        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            Neo4jManager()
        
        # Must implement all abstract methods
        class IncompleteManager(Neo4jManager):
            def __enter__(self):
                return None
            # Missing __exit__ implementation
        
        with pytest.raises(TypeError):
            IncompleteManager()


class TestProtocolCompliance:
    """Test protocol compliance and type checking."""
    
    def test_multiple_protocol_implementation(self):
        """Test a class implementing multiple protocols."""
        class MultiProvider:
            """Provider that implements both LLM and Embedding protocols."""
            
            # LLMProvider methods
            def invoke(self, prompt: str, temperature: float = 0.3) -> LLMResponse:
                return LLMResponse(f"Response: {prompt}", "multi-model")
            
            def invoke_with_retry(self, prompt: str, temperature: float = 0.3, max_retries: int = 3) -> LLMResponse:
                return self.invoke(prompt, temperature)
            
            def check_rate_limits(self) -> Dict[str, Any]:
                return {"status": "ok"}
            
            # EmbeddingProvider methods
            def generate_embedding(self, text: str) -> List[float]:
                return [0.1] * 768
            
            def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.generate_embedding(t) for t in texts]
            
            def get_embedding_dimension(self) -> int:
                return 768
            
            # HealthCheckable method
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        provider = MultiProvider()
        
        # Can use as LLMProvider
        llm_provider: LLMProvider = provider
        response = llm_provider.invoke("test")
        assert response.content == "Response: test"
        
        # Can use as EmbeddingProvider
        embedding_provider: EmbeddingProvider = provider
        embedding = embedding_provider.generate_embedding("test")
        assert len(embedding) == 768
        
        # Can use as HealthCheckable
        health_checkable: HealthCheckable = provider
        health = health_checkable.health_check()
        assert health["status"] == "healthy"
    
    def test_protocol_with_optional_methods(self):
        """Test protocol implementation with optional methods."""
        class MinimalAudioProvider:
            """Minimal implementation of AudioProvider."""
            
            def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
                return []
            
            def diarize(self, audio_path: str) -> List[DiarizationSegment]:
                return []
            
            def align_transcript_with_diarization(
                self,
                transcript_segments: List[TranscriptSegment],
                diarization_segments: List[DiarizationSegment]
            ) -> List[TranscriptSegment]:
                return transcript_segments
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "details": {}, "timestamp": "now"}
        
        # Should be valid AudioProvider
        provider: AudioProvider = MinimalAudioProvider()
        assert provider.transcribe("test.mp3") == []
        assert provider.diarize("test.mp3") == []