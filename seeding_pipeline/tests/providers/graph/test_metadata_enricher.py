"""Tests for metadata enricher component."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.providers.graph.metadata_enricher import MetadataEnricher
from src.core.models import Segment, Episode, Podcast


class TestMetadataEnricher:
    """Test suite for MetadataEnricher."""

    @pytest.fixture
    def enricher(self):
        """Create metadata enricher instance."""
        return MetadataEnricher()

    @pytest.fixture
    def enricher_with_embedder(self):
        """Create enricher with mock embedding provider."""
        mock_embedder = Mock()
        mock_embedder.generate_embedding.return_value = [0.1] * 768
        mock_embedder.generate_embeddings.return_value = [[0.1] * 768, [0.2] * 768]
        return MetadataEnricher(embedding_provider=mock_embedder)

    @pytest.fixture
    def sample_nodes(self) -> List[Dict[str, Any]]:
        """Create test nodes."""
        return [
            {"id": "1", "name": "Artificial Intelligence", "type": "CONCEPT"},
            {"id": "2", "name": "Dr. Smith", "type": "PERSON"},
            {"id": "3", "name": "Machine Learning", "type": "CONCEPT", "confidence": 0.8}
        ]

    @pytest.fixture
    def sample_segment(self) -> Segment:
        """Create test segment with metadata."""
        return Segment(
            start_time=10.5,
            end_time=25.3,
            text="This is a test segment about AI and machine learning.",
            speaker="Dr. Smith",
            confidence=0.95
        )

    @pytest.fixture
    def sample_episode(self) -> Episode:
        """Create test episode."""
        return Episode(
            id="ep123",
            title="AI Revolution",
            description="Discussion about artificial intelligence",
            audio_url="https://example.com/episode.mp3",
            publication_date=datetime.now(),
            duration=1800
        )

    @pytest.fixture
    def sample_podcast(self) -> Podcast:
        """Create test podcast."""
        return Podcast(
            id="pod456",
            title="Tech Talks",
            description="Technology discussions",
            rss_url="https://example.com/feed.xml",
            author="Tech Network",
            categories=["Technology", "Science"]
        )

    # Setup and Fixture Tests
    def test_init_default(self):
        """Test default initialization."""
        enricher = MetadataEnricher()
        assert enricher.embedding_provider is None
        assert enricher.add_embeddings is True
        assert enricher.add_timestamps is True

    def test_init_with_embedder(self):
        """Test initialization with embedding provider."""
        mock_embedder = Mock()
        enricher = MetadataEnricher(embedding_provider=mock_embedder)
        assert enricher.embedding_provider == mock_embedder

    # Temporal Metadata Tests
    def test_add_temporal_basic(self, enricher, sample_segment):
        """Add start/end times to nodes."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_temporal_metadata(node, sample_segment)
        
        assert node["start_time"] == 10.5
        assert node["end_time"] == 25.3
        assert node["duration"] == 14.8
        assert "timestamp" in fields

    def test_add_temporal_missing_segment(self, enricher):
        """Handle None segment gracefully."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_temporal_metadata(node, None)
        
        assert "start_time" not in node
        assert fields == []

    def test_preserve_existing_timestamps(self, enricher, sample_segment):
        """Don't overwrite existing times."""
        node = {"id": "1", "name": "Test", "start_time": 5.0}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_temporal_metadata(node, sample_segment)
        
        assert node["start_time"] == 5.0  # Preserved
        assert node["end_time"] == 25.3  # Added

    def test_temporal_format_consistency(self, enricher, sample_segment):
        """Ensure consistent time format."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_temporal_metadata(node, sample_segment)
        
        assert isinstance(node["start_time"], float)
        assert isinstance(node["end_time"], float)
        assert isinstance(node["duration"], float)

    def test_duration_calculation(self, enricher, sample_segment):
        """Add duration based on start/end."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_temporal_metadata(node, sample_segment)
        
        assert node["duration"] == pytest.approx(14.8, rel=1e-3)

    def test_temporal_validation(self, enricher):
        """Reject invalid time values."""
        segment = Segment(
            start_time=-1.0,  # Invalid
            end_time=10.0,
            text="Test",
            speaker="Speaker"
        )
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_temporal_metadata(node, segment)
        
        # Should skip invalid times
        assert "start_time" not in node or node["start_time"] >= 0

    # Source Metadata Tests
    def test_add_episode_source(self, enricher, sample_episode):
        """Add episode title, ID, URL."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_source_metadata(node, sample_episode, None)
        
        assert node["source"]["episode"]["id"] == "ep123"
        assert node["source"]["episode"]["title"] == "AI Revolution"
        assert node["source"]["episode"]["url"] == "https://example.com/episode.mp3"
        assert "source.episode" in fields

    def test_add_podcast_source(self, enricher, sample_episode, sample_podcast):
        """Add podcast name, author, category."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_source_metadata(node, sample_episode, sample_podcast)
        
        assert node["source"]["podcast"]["id"] == "pod456"
        assert node["source"]["podcast"]["title"] == "Tech Talks"
        assert node["source"]["podcast"]["author"] == "Tech Network"
        assert node["source"]["podcast"]["categories"] == ["Technology", "Science"]

    def test_nested_source_structure(self, enricher, sample_episode, sample_podcast):
        """Create source.episode.podcast hierarchy."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_source_metadata(node, sample_episode, sample_podcast)
        
        assert "source" in node
        assert "episode" in node["source"]
        assert "podcast" in node["source"]

    def test_source_url_validation(self, enricher):
        """Validate URLs before adding."""
        episode = Episode(
            id="ep1",
            title="Test",
            audio_url="not-a-valid-url",  # Invalid URL
            publication_date=datetime.now()
        )
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_source_metadata(node, episode, None)
        
        # Should still add the URL (validation is lenient)
        assert node["source"]["episode"]["url"] == "not-a-valid-url"

    def test_partial_source_info(self, enricher, sample_episode):
        """Handle missing episode or podcast data."""
        node = {"id": "1", "name": "Test"}
        
        # Only episode, no podcast
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_source_metadata(node, sample_episode, None)
        assert "episode" in node["source"]
        assert "podcast" not in node["source"]
        
        # No episode or podcast
        node2 = {"id": "2", "name": "Test2"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_source_metadata(node2, None, None)
        assert fields == []

    def test_source_field_mapping(self, enricher, sample_episode):
        """Map fields correctly from models."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_source_metadata(node, sample_episode, None)
        
        # Check field mapping
        assert node["source"]["episode"]["duration"] == 1800
        assert "publication_date" in node["source"]["episode"]

    def test_preserve_custom_source_fields(self, enricher, sample_episode):
        """Keep non-standard source fields."""
        node = {"id": "1", "name": "Test", "source": {"custom": "value"}}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_source_metadata(node, sample_episode, None)
        
        assert node["source"]["custom"] == "value"  # Preserved
        assert "episode" in node["source"]  # Added

    # Extraction Metadata Tests
    def test_add_extraction_timestamp(self, enricher):
        """Add current timestamp."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            with patch('datetime.datetime') as mock_dt:
                mock_dt.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
                fields = enricher.add_extraction_metadata(node)
        
        assert node["extraction"]["timestamp"] == "2024-01-01T12:00:00"
        assert "extraction.timestamp" in fields

    def test_add_extraction_version(self, enricher):
        """Add pipeline version."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_extraction_metadata(node)
        
        assert "version" in node["extraction"]
        assert node["extraction"]["version"] == "1.0.0"

    def test_add_extraction_confidence(self, enricher):
        """Add default confidence if missing."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_extraction_metadata(node)
        
        assert "confidence" in node["extraction"]
        assert 0 <= node["extraction"]["confidence"] <= 1

    def test_extraction_method_tracking(self, enricher):
        """Track which method extracted entity."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_extraction_metadata(node, method="SimpleKGPipeline")
        
        assert node["extraction"]["method"] == "SimpleKGPipeline"

    def test_extraction_context(self, enricher, sample_segment):
        """Add segment context to extraction."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_extraction_metadata(node, segment_context=sample_segment.text)
        
        assert "context" in node["extraction"]

    # Embedding Integration Tests
    def test_add_embeddings_basic(self, enricher_with_embedder):
        """Generate and add embeddings."""
        node = {"id": "1", "name": "Test Entity"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher_with_embedder.add_embeddings(node)
        
        assert "embedding" in node
        assert len(node["embedding"]) == 768
        assert "embedding" in fields

    def test_embedding_dimension_check(self, enricher_with_embedder):
        """Verify correct dimensions."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher_with_embedder.add_embeddings(node)
        
        assert len(node["embedding"]) == 768
        assert all(isinstance(x, float) for x in node["embedding"])

    def test_no_embedder_provided(self, enricher):
        """Skip embedding if no provider."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_embeddings(node)
        
        assert "embedding" not in node
        assert fields == []

    def test_embedding_cache_behavior(self, enricher_with_embedder):
        """Don't regenerate existing embeddings."""
        existing_embedding = [0.5] * 768
        node = {"id": "1", "name": "Test", "embedding": existing_embedding}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher_with_embedder.add_embeddings(node)
        
        assert node["embedding"] == existing_embedding  # Unchanged

    def test_batch_embedding_generation(self, enricher_with_embedder):
        """Efficient batch processing."""
        nodes = [
            {"id": "1", "name": "Entity 1"},
            {"id": "2", "name": "Entity 2"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            for node in nodes:
                enricher_with_embedder.add_embeddings(node)
        
        # All nodes should have embeddings
        assert all("embedding" in node for node in nodes)

    def test_embedding_error_handling(self):
        """Handle embedding failures gracefully."""
        mock_embedder = Mock()
        mock_embedder.generate_embedding.side_effect = Exception("Embedding error")
        enricher = MetadataEnricher(embedding_provider=mock_embedder)
        
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_embeddings(node)
        
        assert "embedding" not in node
        assert fields == []

    # Confidence Score Tests
    def test_calculate_confidence_basic(self, enricher):
        """Base confidence calculation."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_confidence_scores(node)
        
        assert "confidence_score" in node
        assert 0 <= node["confidence_score"] <= 1

    def test_confidence_factors(self, enricher, sample_segment):
        """Multiple factors affect score."""
        node = {"id": "1", "name": "Test", "type": "PERSON"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_confidence_scores(node, extraction_confidence=0.9, segment=sample_segment)
        
        assert node["confidence_score"] > 0.5
        assert "confidence_factors" in node

    def test_confidence_normalization(self, enricher):
        """Ensure 0-1 range."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_confidence_scores(node, extraction_confidence=2.0)  # Out of range
        
        assert 0 <= node["confidence_score"] <= 1

    def test_existing_confidence_merge(self, enricher):
        """Combine with existing scores."""
        node = {"id": "1", "name": "Test", "confidence": 0.7}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_confidence_scores(node, extraction_confidence=0.9)
        
        assert node["confidence_score"] != 0.7  # Modified
        assert node["confidence"] == 0.7  # Original preserved

    def test_confidence_explanation(self, enricher):
        """Add confidence factors breakdown."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_confidence_scores(node, extraction_confidence=0.85)
        
        assert "confidence_factors" in node
        assert "extraction" in node["confidence_factors"]

    # Segment Context Tests
    def test_add_segment_context(self, enricher, sample_segment):
        """Add surrounding text context."""
        node = {"id": "1", "name": "AI"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            fields = enricher.add_segment_context(node, sample_segment)
        
        assert "segment_context" in node
        assert "text" in node["segment_context"]
        assert sample_segment.text in node["segment_context"]["text"]

    def test_context_window_size(self, enricher, sample_segment):
        """Configurable context window."""
        enricher.context_window_size = 50
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_segment_context(node, sample_segment)
        
        assert len(node["segment_context"]["text"]) <= 50

    def test_speaker_context(self, enricher, sample_segment):
        """Include speaker information."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_segment_context(node, sample_segment)
        
        assert node["segment_context"]["speaker"] == "Dr. Smith"

    def test_context_overlap_handling(self, enricher):
        """Handle overlapping segments."""
        seg1 = Segment(0, 10, "First segment", "Speaker1")
        seg2 = Segment(5, 15, "Second segment", "Speaker2")  # Overlaps
        
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_segment_context(node, seg1, adjacent_segments=[seg2])
        
        assert "adjacent_context" in node["segment_context"]

    def test_context_truncation(self, enricher):
        """Limit context length appropriately."""
        long_text = "A" * 1000
        segment = Segment(0, 10, long_text, "Speaker")
        node = {"id": "1", "name": "Test"}
        
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_segment_context(node, segment)
        
        assert len(node["segment_context"]["text"]) < 1000

    # Relationship Enrichment Tests
    def test_enrich_relationships_basic(self, enricher):
        """Add metadata to relationships."""
        relationships = [
            {"source": "1", "target": "2", "type": "KNOWS"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enriched = enricher.enrich_relationships(relationships)
        
        assert enriched[0]["metadata"]["enriched"] is True

    def test_relationship_confidence(self, enricher):
        """Add confidence to relationships."""
        relationships = [
            {"source": "1", "target": "2", "type": "WORKS_WITH"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enriched = enricher.enrich_relationships(relationships, confidence=0.85)
        
        assert enriched[0]["confidence"] == 0.85

    def test_relationship_source_tracking(self, enricher, sample_segment):
        """Track which segment created relationship."""
        relationships = [
            {"source": "1", "target": "2", "type": "DISCUSSES"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enriched = enricher.enrich_relationships(relationships, segment=sample_segment)
        
        assert enriched[0]["source_segment"]["start_time"] == 10.5

    def test_bidirectional_relationships(self, enricher):
        """Handle both directions."""
        relationships = [
            {"source": "1", "target": "2", "type": "KNOWS", "bidirectional": True}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enriched = enricher.enrich_relationships(relationships)
        
        assert enriched[0]["metadata"]["bidirectional"] is True

    def test_relationship_timestamp(self, enricher):
        """Add temporal data to relationships."""
        relationships = [
            {"source": "1", "target": "2", "type": "MENTIONS"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            with patch('datetime.datetime') as mock_dt:
                mock_dt.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
                enriched = enricher.enrich_relationships(relationships)
        
        assert enriched[0]["created_at"] == "2024-01-01T12:00:00"

    def test_relationship_properties(self, enricher):
        """Preserve existing properties."""
        relationships = [
            {"source": "1", "target": "2", "type": "EMPLOYS", "since": "2020"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enriched = enricher.enrich_relationships(relationships)
        
        assert enriched[0]["since"] == "2020"  # Preserved

    # Batch Processing Tests
    def test_enrich_nodes_batch(self, enricher, sample_nodes, sample_segment):
        """Process multiple nodes efficiently."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = enricher.enrich_nodes(sample_nodes, sample_segment)
        
        assert len(result["nodes"]) == len(sample_nodes)
        assert all("extraction" in node for node in result["nodes"])

    def test_batch_with_mixed_types(self, enricher):
        """Handle different node types."""
        nodes = [
            {"id": "1", "name": "Person", "type": "PERSON"},
            {"id": "2", "name": "Concept", "type": "CONCEPT"},
            {"id": "3", "name": "Org", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = enricher.enrich_nodes(nodes)
        
        assert len(result["nodes"]) == 3
        assert all("confidence_score" in node for node in result["nodes"])

    def test_batch_error_recovery(self, enricher):
        """Continue on individual failures."""
        nodes = [
            {"id": "1", "name": "Valid"},
            {"id": "2"},  # Missing name
            {"id": "3", "name": "Also Valid"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = enricher.enrich_nodes(nodes)
        
        # Should process valid nodes
        assert len(result["nodes"]) >= 2

    def test_batch_progress_tracking(self, enricher, sample_nodes):
        """Track enrichment progress."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = enricher.enrich_nodes(sample_nodes)
        
        assert "metadata" in result
        assert result["metadata"]["nodes_processed"] == len(sample_nodes)

    # Component Tracking Integration Tests
    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_tracking_decorator_applied(self, mock_log, enricher):
        """Verify tracking is active."""
        enricher.add_temporal_metadata({}, None)
        assert mock_log.called

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_metadata_fields_tracked(self, mock_log, enricher, sample_segment):
        """Log which fields were added."""
        node = {"id": "1", "name": "Test"}
        enricher.add_temporal_metadata(node, sample_segment)
        
        call_args = mock_log.call_args[1]
        assert "contributions" in call_args
        assert call_args["contributions"]["fields_added"] > 0

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_enrichment_metrics(self, mock_log, enricher, sample_nodes):
        """Track nodes enriched, fields added."""
        enricher.enrich_nodes(sample_nodes)
        
        call_args = mock_log.call_args[1]
        assert call_args["contributions"]["nodes_enriched"] == len(sample_nodes)

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_performance_impact(self, mock_log, enricher_with_embedder, sample_nodes):
        """Measure enrichment overhead."""
        enricher_with_embedder.enrich_nodes(sample_nodes)
        
        # Performance tracked via decorator
        assert mock_log.called

    # Error Handling Tests
    def test_invalid_node_structure(self, enricher):
        """Handle malformed nodes."""
        nodes = [
            None,  # None node
            {},  # Empty node
            {"name": "No ID"},  # Missing ID
            {"id": "1", "name": "Valid"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = enricher.enrich_nodes(nodes)
        
        # Should process valid node
        assert any(n.get("name") == "Valid" for n in result["nodes"])

    def test_null_values_handling(self, enricher, sample_segment):
        """Deal with None values gracefully."""
        node = {"id": "1", "name": None}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_temporal_metadata(node, sample_segment)
        
        # Should still add temporal data
        assert "start_time" in node

    def test_type_mismatch_handling(self, enricher):
        """Wrong types for metadata fields."""
        node = {"id": 1, "name": "Test"}  # ID should be string
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            enricher.add_extraction_metadata(node)
        
        # Should handle gracefully
        assert "extraction" in node

    def test_missing_required_data(self, enricher):
        """Handle missing segment/episode data."""
        node = {"id": "1", "name": "Test"}
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            # All None
            fields = enricher.add_source_metadata(node, None, None)
        
        assert fields == []

    def test_exception_propagation(self, enricher):
        """Proper error reporting."""
        with patch('datetime.datetime.now', side_effect=Exception("Time error")):
            node = {"id": "1", "name": "Test"}
            with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
                # Should handle datetime errors
                enricher.add_extraction_metadata(node)
        
        # Node should still be valid
        assert "id" in node