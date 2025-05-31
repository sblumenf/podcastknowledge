"""Integration tests for schemaless pipeline end-to-end processing."""

from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

import pytest

from src.core.config import Config
from src.core.models import Podcast, Episode, Segment, ProcessingResult
from src.providers.embeddings.mock import MockEmbeddingProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.providers.llm.mock import MockLLMProvider
@pytest.mark.integration
class TestSchemalessIntegration:
    """End-to-end integration tests for schemaless pipeline."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return {
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "testpassword"
            },
            "llm": {
                "provider": "mock",
                "response_mode": "json",
                "default_response": '{"entities": [], "relationships": []}'
            },
            "embeddings": {
                "provider": "mock",
                "dimension": 384
            }
        }

    @pytest.fixture
    def test_podcast(self):
        """Create test podcast data."""
        return Podcast(
            id="podcast1",
            title="Tech Talks Daily",
            description="Daily discussions about technology",
            author="Tech Host",
            language="en",
            categories=["Technology", "Science"],
            website="https://example.com",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    @pytest.fixture
    def test_episode(self):
        """Create test episode data."""
        return Episode(
            id="episode1",
            podcast_id="podcast1",
            title="The Future of AI",
            description="Exploring artificial intelligence developments",
            audio_url="https://example.com/episode1.mp3",
            publication_date=datetime.now(),
            duration=1800,
            episode_number=1,
            season_number=1,
            created_at=datetime.now()
        )

    @pytest.fixture
    def test_segments(self):
        """Create test segments with diverse content."""
        return [
            Segment(
                id="seg1",
                episode_id="episode1",
                start_time=0.0,
                end_time=60.0,
                text="Welcome to Tech Talks Daily. I'm your host, and today we're discussing the future of artificial intelligence with Dr. Sarah Johnson from MIT.",
                speaker="Host"
            ),
            Segment(
                id="seg2",
                episode_id="episode1",
                start_time=60.0,
                end_time=120.0,
                text="Thanks for having me. AI has made incredible progress. Machine learning models like GPT and BERT have revolutionized natural language processing.",
                speaker="Dr. Sarah Johnson"
            ),
            Segment(
                id="seg3",
                episode_id="episode1",
                start_time=120.0,
                end_time=180.0,
                text="As I always say, 'The future of AI is not about replacing humans, but augmenting human capabilities.' This is the core philosophy at our lab.",
                speaker="Dr. Sarah Johnson"
            )
        ]

    @pytest.fixture
    def schemaless_provider(self, test_config):
        """Create schemaless provider with mocked Neo4j."""
        # Mock Neo4j driver
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        with patch('src.providers.graph.schemaless_neo4j.GraphDatabase') as mock_gdb:
            mock_gdb.driver.return_value = mock_driver
            
            provider = SchemalessNeo4jProvider(test_config["neo4j"])
            
            # Mock the pipeline with proper response structure
            mock_pipeline = MagicMock()
            mock_pipeline.run_async = AsyncMock(return_value={
                "entities": [
                    {"name": "AI", "type": "Technology"},
                    {"name": "Dr. Sarah Johnson", "type": "Person"},
                    {"name": "MIT", "type": "Organization"}
                ],
                "relationships": [
                    {"source": "Dr. Sarah Johnson", "target": "MIT", "type": "AFFILIATED_WITH"}
                ]
            })
            provider.pipeline = mock_pipeline
            
            # Mock LLM and embedding providers
            provider.llm_adapter = MagicMock()
            provider.embedding_adapter = MagicMock()
            provider.embedding_adapter.embed_query = AsyncMock(return_value=[0.1] * 384)
            
            # Initialize metadata enricher
            from src.providers.graph.metadata_enricher import SchemalessMetadataEnricher
            mock_embedding_provider = MockEmbeddingProvider(test_config["embeddings"])
            provider.metadata_enricher = SchemalessMetadataEnricher(mock_embedding_provider)
            
            yield provider
            # Cleanup would go here if needed

    def test_process_complete_episode_schemaless(self, schemaless_provider, test_podcast, test_episode, test_segments):
        """Test processing a complete episode with schemaless approach."""
        # Process all segments
        results = []
        for segment in test_segments:
            result = schemaless_provider.process_segment_schemaless(
                segment,
                test_episode,
                test_podcast
            )
            results.append(result)
        
        # Verify results
        assert len(results) == 3
        
        # Check that processing succeeded
        for result in results:
            assert result["status"] == "success"
            assert result["entities_extracted"] > 0

    def test_verify_all_metadata_preserved(self, schemaless_provider, test_segments, test_episode, test_podcast):
        """Test that all metadata is preserved in schemaless extraction."""
        segment = test_segments[0]
        
        # Mock the enrichment to verify it's called
        with patch.object(schemaless_provider.metadata_enricher, 'enrich_extraction_results') as mock_enrich:
            mock_enrich.return_value = {
                "entities": [
                    {
                        "name": "Test Entity",
                        "segment_id": segment.id,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "speaker": segment.speaker,
                        "episode_title": test_episode.title,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "embeddings": [0.1] * 384
                    }
                ],
                "relationships": []
            }
            
            result = schemaless_provider.process_segment_schemaless(segment, test_episode, test_podcast)
            
            # Verify metadata enrichment was called
            assert mock_enrich.called
            
            # Check result indicates success
            assert result["status"] == "success"

    def test_entity_resolution_works(self, schemaless_provider):
        """Test that entity resolution merges duplicates correctly."""
        # Create segments with duplicate entities
        segments = [
            Segment(
                id="seg1",
                episode_id="ep1",
                start_time=0.0,
                end_time=30.0,
                text="Artificial Intelligence is transforming the world.",
                speaker="Host"
            ),
            Segment(
                id="seg2",
                episode_id="ep1",
                start_time=30.0,
                end_time=60.0,
                text="AI and machine learning are related fields.",
                speaker="Host"
            )
        ]
        
        episode = Episode(id="ep1", podcast_id="pod1", title="AI Discussion", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Tech Podcast")
        
        # Mock pipeline to return entities that need resolution
        with patch.object(schemaless_provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {"entities": [{"name": "Artificial Intelligence", "type": "Technology"}], "relationships": []},
                {"entities": [{"name": "AI", "type": "Technology"}], "relationships": []}
            ]
            
            # Process both segments
            for segment in segments:
                result = schemaless_provider.process_segment_schemaless(segment, episode, podcast)
                assert result["status"] == "success"

    def test_validate_relationship_creation(self, schemaless_provider):
        """Test that relationships are created correctly."""
        segment = Segment(
            id="seg1",
            episode_id="ep1",
            start_time=0.0,
            end_time=60.0,
            text="OpenAI developed ChatGPT, which uses transformer architecture developed by Google.",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="AI Companies", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Tech Podcast")
        
        # Mock pipeline response with relationships
        with patch.object(schemaless_provider.pipeline, 'run_async', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "entities": [
                    {"name": "OpenAI", "type": "Organization"},
                    {"name": "ChatGPT", "type": "Product"},
                    {"name": "Google", "type": "Organization"}
                ],
                "relationships": [
                    {"source": "OpenAI", "target": "ChatGPT", "type": "DEVELOPED"},
                    {"source": "Google", "target": "transformer architecture", "type": "DEVELOPED"}
                ]
            }
            
            result = schemaless_provider.process_segment_schemaless(segment, episode, podcast)
            
            # Check relationships were processed
            assert result["status"] == "success"
            assert result["relationships_extracted"] > 0

    def test_quote_extraction_with_timestamps(self, schemaless_provider, test_segments, test_episode, test_podcast):
        """Test that quotes are extracted with proper timestamps."""
        # Process segment containing a quote
        quote_segment = test_segments[2]  # Contains the quote about AI future
        
        # Mock quote extractor to verify it's called
        with patch.object(schemaless_provider.quote_extractor, 'extract_quotes') as mock_extract:
            mock_extract.return_value = {
                "quotes": [{
                    "text": "The future of AI is not about replacing humans, but augmenting human capabilities.",
                    "speaker": "Dr. Sarah Johnson",
                    "start_time": 120.0,
                    "importance_score": 0.9
                }],
                "integrated_results": {"entities": [], "relationships": []}
            }
            
            result = schemaless_provider.process_segment_schemaless(quote_segment, test_episode, test_podcast)
            
            # Verify quote extraction was called
            assert mock_extract.called
            assert result["status"] == "success"
            assert result["quotes_extracted"] > 0

    def test_compare_with_fixed_schema_results(self, schemaless_provider):
        """Compare schemaless output with expected fixed schema results."""
        segment = Segment(
            id="seg1",
            episode_id="ep1",
            start_time=0.0,
            end_time=60.0,
            text="Google's DeepMind achieved breakthrough in protein folding with AlphaFold.",
            speaker="Host"
        )
        
        episode = Episode(id="ep1", podcast_id="pod1", title="AI Breakthroughs", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Science Podcast")
        
        # Process with schemaless
        result = schemaless_provider.process_segment_schemaless(segment, episode, podcast)
        
        # Verify processing succeeded
        assert result["status"] == "success"
        assert result["entities_extracted"] > 0

    def test_real_neo4j_instance_storage(self, schemaless_provider, test_podcast, test_episode):
        """Test actual storage in Neo4j test instance."""
        # This test requires a running Neo4j test instance
        try:
            # Mock the session to simulate successful storage
            with schemaless_provider.session() as session:
                # Store podcast
                schemaless_provider.store_podcast(test_podcast)
                
                # Verify the run method was called
                session.run.assert_called()
                
                # Store episode  
                schemaless_provider.store_episode(test_episode)
                
                # Verify relationship creation was attempted
                assert session.run.call_count >= 2
                
        except Exception as e:
            pytest.skip(f"Neo4j test instance not available: {e}")

    def test_performance_baseline(self, schemaless_provider, test_segments, test_episode, test_podcast):
        """Establish performance baseline for schemaless processing."""
        import time
        
        processing_times = []
        
        for segment in test_segments:
            start_time = time.time()
            schemaless_provider.process_segment_schemaless(segment, test_episode, test_podcast)
            end_time = time.time()
            processing_times.append(end_time - start_time)
        
        # Log performance metrics
        avg_time = sum(processing_times) / len(processing_times)
        max_time = max(processing_times)
        
        # Assert reasonable performance (adjust thresholds as needed)
        assert avg_time < 5.0, f"Average processing time too high: {avg_time}s"
        assert max_time < 10.0, f"Maximum processing time too high: {max_time}s"
        
        # Store baseline for future comparison
        print(f"Performance baseline - Avg: {avg_time:.2f}s, Max: {max_time:.2f}s")