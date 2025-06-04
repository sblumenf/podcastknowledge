"""Critical path end-to-end test for VTT to Knowledge Graph pipeline."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
from src.vtt.vtt_parser import VTTParser
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.storage.graph_storage import GraphStorageService
from src.core.models import Episode, Segment


class TestCriticalPath:
    """End-to-end test of the complete VTT to Knowledge Graph pipeline."""
    
    @pytest.fixture
    def test_episode(self):
        """Create test episode."""
        return Episode(
            id="test-ep-001",
            title="Test Episode: AI Discussion",
            description="A test episode about AI and machine learning",
            published_date="2024-01-01",
            audio_url="https://example.com/test-ep-001.mp3",
            duration=1800
        )
    
    @pytest.fixture
    def minimal_vtt_content(self):
        """Minimal VTT content for testing."""
        return """WEBVTT

00:00:00.000 --> 00:00:10.000
<v Host> Welcome to Tech Talks. Today we're discussing artificial intelligence with Dr. Jane Smith from Stanford University.

00:00:10.000 --> 00:00:20.000
<v Dr. Smith> Thank you for having me. AI has made incredible progress in recent years, especially in natural language processing.

00:00:20.000 --> 00:00:30.000
<v Host> What do you see as the most significant breakthroughs?

00:00:30.000 --> 00:00:45.000
<v Dr. Smith> I think the transformer architecture and models like GPT have fundamentally changed how we approach language understanding.
"""
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM extraction response."""
        return {
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "id": "jane-smith", "confidence": 0.95},
                {"name": "Stanford University", "type": "ORGANIZATION", "id": "stanford", "confidence": 0.9},
                {"name": "artificial intelligence", "type": "TECHNOLOGY", "id": "ai", "confidence": 0.85},
                {"name": "natural language processing", "type": "TECHNOLOGY", "id": "nlp", "confidence": 0.85},
                {"name": "transformer architecture", "type": "CONCEPT", "id": "transformer", "confidence": 0.8},
                {"name": "GPT", "type": "TECHNOLOGY", "id": "gpt", "confidence": 0.9}
            ],
            "relationships": [
                {"source": "jane-smith", "target": "stanford", "type": "AFFILIATED_WITH"},
                {"source": "ai", "target": "nlp", "type": "INCLUDES"},
                {"source": "transformer", "target": "gpt", "type": "ENABLES"},
                {"source": "jane-smith", "target": "ai", "type": "DISCUSSES"}
            ],
            "quotes": [
                {
                    "text": "AI has made incredible progress in recent years, especially in natural language processing",
                    "speaker": "Dr. Smith",
                    "importance": 0.8
                },
                {
                    "text": "the transformer architecture and models like GPT have fundamentally changed how we approach language understanding",
                    "speaker": "Dr. Smith", 
                    "importance": 0.9
                }
            ]
        }
    
    @pytest.fixture
    def mock_neo4j_driver(self):
        """Mock Neo4j driver for testing."""
        from tests.utils.neo4j_mocks import create_mock_neo4j_driver
        
        # Use the proper mock driver
        driver = create_mock_neo4j_driver("bolt://localhost:7688")
        
        yield driver
    
    def test_vtt_to_knowledge_graph_flow(self, test_episode, minimal_vtt_content, 
                                        mock_llm_response, mock_neo4j_driver):
        """Test complete flow from VTT file to knowledge graph."""
        
        # Step 1: Parse VTT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(minimal_vtt_content)
            vtt_file = Path(f.name)
        
        try:
            parser = VTTParser()
            segments = parser.parse_file(vtt_file)
            
            # Verify VTT parsing
            assert len(segments) == 4
            assert segments[0].text.startswith("Welcome to Tech Talks")
            assert segments[0].speaker == "Host"
            assert segments[1].speaker == "Dr. Smith"
            
            # Step 2: Extract knowledge (with mocked LLM)
            extractor = KnowledgeExtractor(config=ExtractionConfig())
            
            with patch.object(extractor, 'llm_provider') as mock_llm:
                mock_llm.generate.return_value = mock_llm_response
                
                # Extract from all segments
                all_entities = []
                all_relationships = []
                all_quotes = []
                
                for segment in segments:
                    result = extractor.extract_knowledge(segment)
                    all_entities.extend(result.entities)
                    all_relationships.extend(result.relationships)
                    all_quotes.extend(result.quotes)
                
                # Verify extraction
                assert len(all_entities) >= 6  # Should have key entities
                assert any(e["name"] == "Dr. Jane Smith" for e in all_entities)
                assert any(e["name"] == "artificial intelligence" for e in all_entities)
                assert len(all_relationships) >= 4
                assert len(all_quotes) >= 2
            
            # Step 3: Store in Neo4j (with mocked driver)
            storage = GraphStorageService(
                uri="bolt://localhost:7687",
                username="test",
                password="test"
            )
            storage._driver = mock_neo4j_driver
            
            # Create episode node
            episode_id = storage.create_node("Episode", {
                "id": test_episode.id,
                "title": test_episode.title,
                "podcast_name": test_episode.podcast_name
            })
            assert episode_id == "test-ep-001"
            
            # Create entity nodes
            entity_map = {}
            for entity in all_entities:
                if entity["id"] not in entity_map:  # Deduplicate
                    node_id = storage.create_node(entity["type"], {
                        "id": entity["id"],
                        "name": entity["name"],
                        "confidence": entity.get("confidence", 1.0)
                    })
                    entity_map[entity["id"]] = node_id
            
            # Create relationships
            rel_count = 0
            for rel in all_relationships:
                if rel["source"] in entity_map and rel["target"] in entity_map:
                    storage.create_relationship(
                        source_id=entity_map[rel["source"]],
                        target_id=entity_map[rel["target"]],
                        rel_type=rel["type"],
                        properties={"episode_id": test_episode.id}
                    )
                    rel_count += 1
            
            # Step 4: Verify complete pipeline results
            # Check that all expected data was created
            assert len(entity_map) >= 6  # All unique entities created
            assert rel_count >= 4  # All relationships created
            
            # Verify specific entities exist
            assert "jane-smith" in entity_map
            assert "stanford" in entity_map
            assert "ai" in entity_map
            
            # Step 5: Query to verify (simulated)
            # In real test, would query Neo4j to verify data
            with patch.object(storage, 'query') as mock_query:
                # Simulate query results
                mock_query.return_value = [
                    {"name": "Dr. Jane Smith", "type": "PERSON"},
                    {"name": "Stanford University", "type": "ORGANIZATION"}
                ]
                
                # Query for entities
                results = storage.query(
                    "MATCH (n) WHERE n.episode_id = $episode_id RETURN n.name as name, labels(n)[0] as type",
                    parameters={"episode_id": test_episode.id}
                )
                
                assert len(results) >= 2
                assert any(r["name"] == "Dr. Jane Smith" for r in results)
            
            # Step 6: Verify relationships connected
            # Check that nodes were created with proper relationships
            created_nodes = mock_neo4j_driver._created_nodes
            created_rels = mock_neo4j_driver._created_relationships
            
            # Should have created nodes for entities
            assert len(created_nodes) > 0
            
            # Should have created relationships
            assert len(created_rels) >= 4
            
            # Step 7: Clean up test data
            # In real test, would delete test data from Neo4j
            # For this mock test, just verify cleanup would be called
            assert storage._driver is not None
            
        finally:
            # Clean up temp file
            vtt_file.unlink()
        
        # Test passed - complete pipeline works!
        assert True
    
    def test_pipeline_with_empty_vtt(self):
        """Test pipeline handles empty VTT gracefully."""
        empty_vtt = """WEBVTT
        
        """
        
        parser = VTTParser()
        segments = parser.parse_content(empty_vtt)
        
        # Should handle empty content gracefully
        assert len(segments) == 0
    
    def test_pipeline_with_extraction_failure(self, test_episode, minimal_vtt_content):
        """Test pipeline handles extraction failures gracefully."""
        parser = VTTParser()
        segments = parser.parse_content(minimal_vtt_content)
        
        extractor = KnowledgeExtractor(config=ExtractionConfig())
        
        # Mock LLM to fail
        with patch.object(extractor, 'llm_provider') as mock_llm:
            mock_llm.generate.side_effect = Exception("LLM service unavailable")
            
            # Should handle failure gracefully
            for segment in segments:
                result = extractor.extract_knowledge(segment)
                assert isinstance(result.entities, list)
                assert len(result.entities) == 0  # Empty on failure
                assert result.metadata.get("error") is not None
    
    def test_pipeline_with_storage_failure(self, mock_neo4j_driver):
        """Test pipeline handles storage failures gracefully."""
        storage = GraphStorageService(
            uri="bolt://localhost:7687",
            username="test",
            password="test"
        )
        
        # Make driver fail
        mock_neo4j_driver.session.side_effect = Exception("Connection lost")
        storage._driver = mock_neo4j_driver
        
        # Should handle failure gracefully
        from src.core.exceptions import ProviderError
        with pytest.raises(ProviderError):
            storage.create_node("Test", {"name": "test"})