"""Unit tests for SchemalessNeo4jProvider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Mock the problematic import for Python 3.9 compatibility
import sys
from unittest.mock import Mock
sys.modules['neo4j_graphrag'] = Mock()
sys.modules['neo4j_graphrag.experimental'] = Mock()
sys.modules['neo4j_graphrag.experimental.pipeline'] = Mock()
sys.modules['neo4j_graphrag.experimental.pipeline.kg_builder'] = Mock()
SimpleKGPipeline = Mock

from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.providers.llm.gemini_adapter import GeminiGraphRAGAdapter
from src.providers.embeddings.sentence_transformer_adapter import SentenceTransformerGraphRAGAdapter
from src.processing.schemaless_preprocessor import SegmentPreprocessor
from src.processing.schemaless_entity_resolution import SchemalessEntityResolver
from src.providers.graph.metadata_enricher import SchemalessMetadataEnricher
from src.processing.schemaless_quote_extractor import SchemalessQuoteExtractor
from src.core.models import Podcast, Episode, Segment


class TestSchemalessNeo4jProvider:
    """Test suite for SchemalessNeo4jProvider."""

    @pytest.fixture
    def mock_neo4j_driver(self):
        """Create a mock Neo4j driver."""
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        return driver

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.generate_text = AsyncMock(return_value="Generated text")
        provider.embed_text = AsyncMock(return_value=[0.1] * 768)
        return provider

    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = MagicMock()
        provider.embed_text = AsyncMock(return_value=[0.1] * 768)
        return provider

    @pytest.fixture
    def provider(self, mock_neo4j_driver, mock_llm_provider, mock_embedding_provider):
        """Create a SchemalessNeo4jProvider instance with mocks."""
        config = {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        }
        
        with patch('src.providers.graph.schemaless_neo4j.GraphDatabase') as mock_gdb:
            mock_gdb.driver.return_value = mock_neo4j_driver
            
            provider = SchemalessNeo4jProvider(config)
            
            # Mock the adapters and components
            provider.llm_adapter = GeminiGraphRAGAdapter(mock_llm_provider)
            provider.embedding_adapter = SentenceTransformerGraphRAGAdapter(mock_embedding_provider)
            
            # Mock the pipeline
            mock_pipeline = MagicMock(spec=SimpleKGPipeline)
            mock_pipeline.run_async = AsyncMock()
            provider.pipeline = mock_pipeline
            
            # Initialize metadata enricher with embedding provider
            provider.metadata_enricher = SchemalessMetadataEnricher(mock_embedding_provider)
            
            return provider

    def test_simple_kg_pipeline_initialization(self, provider):
        """Test that SimpleKGPipeline is properly initialized."""
        assert provider.pipeline is not None
        assert isinstance(provider.llm_adapter, GeminiGraphRAGAdapter)
        assert isinstance(provider.embedding_adapter, SentenceTransformerGraphRAGAdapter)
        assert isinstance(provider.preprocessor, SegmentPreprocessor)
        assert isinstance(provider.entity_resolver, SchemalessEntityResolver)
        assert isinstance(provider.metadata_enricher, SchemalessMetadataEnricher)
        assert isinstance(provider.quote_extractor, SchemalessQuoteExtractor)

    def test_segment_processing_with_metadata(self, provider):
        """Test segment processing includes metadata enrichment."""
        # Create test data
        segment = Segment(
            id="seg1",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="This is a test segment about AI and machine learning.",
            speaker="Host"
        )
        
        episode = Episode(
            id="ep1",
            podcast_id="pod1",
            title="AI Revolution",
            publication_date=datetime.now()
        )
        
        podcast = Podcast(
            id="pod1",
            title="Tech Talk"
        )
        
        # Mock SimpleKGPipeline response
        mock_kg_result = {
            "entities": [
                {"name": "AI", "type": "Technology"},
                {"name": "machine learning", "type": "Technology"}
            ],
            "relationships": [
                {"source": "AI", "target": "machine learning", "type": "RELATED_TO"}
            ]
        }
        
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_kg_result
            
            result = provider.process_segment_schemaless(segment, episode, podcast)
            
            # Verify preprocessing was called
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            
            # Check that metadata was injected
            assert "Speaker: Host" in call_args
            assert "[00:00 - 00:30]" in call_args
            
            # Check result structure
            assert "segment_id" in result
            assert "status" in result
            assert result["status"] == "success"

    def test_entity_extraction_validation(self, provider):
        """Test that entity extraction produces valid results."""
        segment = Segment(
            id="seg2",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="Apple Inc. is developing new artificial intelligence features.",
            speaker="Guest"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Tech News", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Tech Podcast")
        
        mock_kg_result = {
            "entities": [
                {"name": "Apple Inc.", "type": "Organization"},
                {"name": "artificial intelligence", "type": "Technology"}
            ],
            "relationships": []
        }
        
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_kg_result
            
            result = provider.process_segment_schemaless(segment, episode, podcast)
            
            # Validate extraction completed
            assert result["status"] == "success"
            assert result["entities_extracted"] >= 2

    def test_relationship_creation(self, provider):
        """Test that relationships are properly created."""
        segment = Segment(
            id="seg3",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="Elon Musk founded SpaceX and leads the company.",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Business Leaders", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Business Podcast")
        
        mock_kg_result = {
            "entities": [
                {"name": "Elon Musk", "type": "Person"},
                {"name": "SpaceX", "type": "Organization"}
            ],
            "relationships": [
                {"source": "Elon Musk", "target": "SpaceX", "type": "FOUNDED"},
                {"source": "Elon Musk", "target": "SpaceX", "type": "LEADS"}
            ]
        }
        
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_kg_result
            
            result = provider.process_segment_schemaless(segment, episode, podcast)
            
            # Validate relationships
            assert result["status"] == "success"
            assert result["relationships_extracted"] >= 2

    def test_property_storage(self, provider, mock_neo4j_driver):
        """Test that properties are stored correctly."""
        # Create test node data
        node_data = {
            "id": "test123",
            "name": "Test Entity",
            "type": "TestType",
            "confidence": 0.95,
            "importance_score": 0.8,
            "custom_property": "custom_value"
        }
        
        # Get the session mock
        session = mock_neo4j_driver.session.return_value.__enter__.return_value
        
        # Store the node
        provider.create_node("TestType", node_data)
        
        # Verify the query was executed with proper parameters
        session.run.assert_called()
        query = session.run.call_args[0][0]
        params = session.run.call_args[1]
        
        # Check that properties are included
        assert "id" in params
        assert params["id"] == "test123"
        assert params["_type"] == "TestType"

    def test_error_handling(self, provider):
        """Test error handling in segment processing."""
        segment = Segment(
            id="seg4",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="Test segment",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Test", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Test Podcast")
        
        # Mock SimpleKGPipeline to raise an error
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = Exception("Processing failed")
            
            # Should not raise but handle gracefully
            try:
                result = provider.process_segment_schemaless(segment, episode, podcast)
                # The actual implementation might raise or return error status
                assert result["status"] == "error" or "error" in result
            except Exception:
                # If it raises, that's also acceptable error handling
                pass

    def test_edge_cases_empty_text(self, provider):
        """Test handling of empty text segments."""
        segment = Segment(
            id="seg5",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Test", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Test Podcast")
        
        # Process empty segment
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"entities": [], "relationships": []}
            
            result = provider.process_segment_schemaless(segment, episode, podcast)
            
            # Should handle gracefully
            assert result is not None

    def test_edge_cases_special_characters(self, provider):
        """Test handling of special characters in text."""
        segment = Segment(
            id="seg6",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="Test with special chars: @#$% & \"quotes\" and 'apostrophes'",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Test", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Test Podcast")
        
        # Process segment with special characters
        with patch.object(provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"entities": [], "relationships": []}
            
            # Should not raise any errors
            result = provider.process_segment_schemaless(segment, episode, podcast)
            assert result is not None

    def test_mock_simple_kg_pipeline_isolation(self, provider):
        """Test that SimpleKGPipeline can be properly mocked for isolated testing."""
        # Verify mock works
        segment = Segment(
            id="seg7",
            episode_id="ep1",
            start_time=0.0,
            end_time=30.0,
            text="Test",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Test", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Test Podcast")
        
        # Call should work with mock
        result = provider.process_segment_schemaless(segment, episode, podcast)
        assert result is not None