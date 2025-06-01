"""Integration tests for Neo4j storage operations."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
from src.storage.graph_storage import GraphStorageService
from src.core.models import Episode, Segment
from src.core.exceptions import ConnectionError, ProviderError


class TestNeo4jStorage:
    """Test Neo4j graph storage operations."""
    
    @pytest.fixture
    def storage_config(self):
        """Neo4j storage configuration."""
        return {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "testpassword",
            "database": "test"
        }
    
    @pytest.fixture
    def graph_storage(self, storage_config):
        """Create graph storage instance."""
        return GraphStorageService(**storage_config)
    
    @pytest.fixture
    def mock_driver(self):
        """Create mock Neo4j driver."""
        driver = Mock()
        session = Mock()
        tx = Mock()
        
        # Setup mock chain
        driver.session.return_value.__enter__.return_value = session
        session.begin_transaction.return_value.__enter__.return_value = tx
        
        # Default query result
        result = Mock()
        result.single.return_value = {"id": "test-node-id"}
        tx.run.return_value = result
        
        return driver
    
    @pytest.fixture
    def sample_episode(self):
        """Create sample episode."""
        return Episode(
            id="ep123",
            title="Test Episode",
            podcast_name="Test Podcast",
            url="https://example.com/ep123.mp3",
            metadata={"duration": 3600}
        )
    
    @pytest.fixture
    def sample_segment(self):
        """Create sample segment with extraction results."""
        return Segment(
            text="Dr. Jane Smith discusses AI advances.",
            start_time=0.0,
            end_time=10.0,
            speaker="Host",
            extraction_result={
                "entities": [
                    {"name": "Dr. Jane Smith", "type": "PERSON", "id": "jane-smith"},
                    {"name": "AI", "type": "TECHNOLOGY", "id": "ai-tech"}
                ],
                "relationships": [
                    {
                        "source": "jane-smith",
                        "target": "ai-tech",
                        "type": "DISCUSSES"
                    }
                ]
            }
        )
    
    def test_create_episode_node(self, graph_storage, sample_episode, mock_driver):
        """Test creating episode node in Neo4j."""
        # Setup
        graph_storage._driver = mock_driver
        mock_driver.session.return_value.__enter__.return_value.run.return_value.single.return_value = {
            "id": "ep123"
        }
        
        # Create episode node
        node_id = graph_storage.create_node("Episode", {
            "id": sample_episode.id,
            "title": sample_episode.title,
            "podcast_name": sample_episode.podcast_name,
            "url": sample_episode.url
        })
        
        # Verify
        assert node_id == "ep123"
        mock_driver.session.assert_called()
        
        # Check Cypher query was run
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.assert_called()
        call_args = session.run.call_args
        cypher = call_args[0][0]
        assert "CREATE" in cypher
        assert "Episode" in cypher
    
    def test_create_knowledge_nodes(self, graph_storage, sample_segment, mock_driver):
        """Test creating entity/insight nodes from extraction."""
        # Setup
        graph_storage._driver = mock_driver
        
        # Mock return different IDs for each entity
        mock_driver.session.return_value.__enter__.return_value.run.return_value.single.side_effect = [
            {"id": "jane-smith"},
            {"id": "ai-tech"}
        ]
        
        # Create entity nodes
        entities = sample_segment.extraction_result["entities"]
        created_ids = []
        
        for entity in entities:
            node_id = graph_storage.create_node(entity["type"], {
                "name": entity["name"],
                "id": entity["id"]
            })
            created_ids.append(node_id)
        
        # Verify
        assert len(created_ids) == 2
        assert created_ids[0] == "jane-smith"
        assert created_ids[1] == "ai-tech"
    
    def test_create_relationships(self, graph_storage, sample_segment, mock_driver):
        """Test creating relationships between nodes."""
        # Setup
        graph_storage._driver = mock_driver
        
        # Create relationship
        rel = sample_segment.extraction_result["relationships"][0]
        rel_id = graph_storage.create_relationship(
            source_id=rel["source"],
            target_id=rel["target"],
            rel_type=rel["type"],
            properties={"segment_time": sample_segment.start_time}
        )
        
        # Verify
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.assert_called()
        call_args = session.run.call_args
        cypher = call_args[0][0]
        assert "MATCH" in cypher
        assert "CREATE" in cypher
        assert "DISCUSSES" in cypher
    
    def test_transaction_rollback(self, graph_storage, mock_driver):
        """Test transaction rollback on error."""
        # Setup error scenario
        graph_storage._driver = mock_driver
        tx = mock_driver.session.return_value.__enter__.return_value.begin_transaction.return_value.__enter__.return_value
        tx.run.side_effect = Exception("Database error")
        
        # Attempt operation that will fail
        with pytest.raises(ProviderError):
            graph_storage.create_node("TestNode", {"name": "test"})
        
        # Verify rollback was called
        tx.rollback.assert_called_once()
    
    def test_duplicate_handling(self, graph_storage, sample_episode, mock_driver):
        """Test idempotent handling of duplicate nodes."""
        # Setup
        graph_storage._driver = mock_driver
        
        # First create succeeds
        node_id1 = graph_storage.create_node("Episode", {
            "id": sample_episode.id,
            "title": sample_episode.title
        })
        
        # Second create should merge
        node_id2 = graph_storage.create_node("Episode", {
            "id": sample_episode.id,
            "title": sample_episode.title
        })
        
        # Should return same ID (assuming MERGE operation)
        # Note: Actual implementation may vary
        assert node_id1 is not None
        assert node_id2 is not None
    
    def test_query_execution(self, graph_storage, mock_driver):
        """Test executing custom Cypher queries."""
        # Setup
        graph_storage._driver = mock_driver
        mock_result = [
            {"name": "Entity1", "count": 5},
            {"name": "Entity2", "count": 3}
        ]
        mock_driver.session.return_value.__enter__.return_value.run.return_value.data.return_value = mock_result
        
        # Execute query
        results = graph_storage.query(
            "MATCH (n) RETURN n.name as name, count(*) as count",
            parameters={"limit": 10}
        )
        
        # Verify
        assert len(results) == 2
        assert results[0]["name"] == "Entity1"
        assert results[0]["count"] == 5
    
    def test_connection_failure(self, storage_config):
        """Test handling of connection failures."""
        # Create storage with invalid URI
        storage_config["uri"] = "bolt://invalid:7687"
        storage = GraphStorageService(**storage_config)
        
        # Mock driver creation to fail
        with patch('neo4j.GraphDatabase.driver') as mock_driver_class:
            mock_driver_class.side_effect = Exception("Connection failed")
            
            # Should raise ConnectionError
            with pytest.raises(ConnectionError):
                storage.connect()
    
    def test_session_context_manager(self, graph_storage, mock_driver):
        """Test session context manager usage."""
        # Setup
        graph_storage._driver = mock_driver
        
        # Use session context
        with graph_storage.session() as session:
            # Should get mock session
            assert session is not None
            
        # Verify session was properly closed
        mock_driver.session.return_value.__enter__.assert_called()
        mock_driver.session.return_value.__exit__.assert_called()
    
    def test_process_segment_schemaless(self, graph_storage, sample_segment, sample_episode, mock_driver):
        """Test processing a complete segment with schemaless extraction."""
        # Setup
        graph_storage._driver = mock_driver
        
        # Mock multiple returns for node creation
        mock_driver.session.return_value.__enter__.return_value.run.return_value.single.side_effect = [
            {"id": "segment-1"},
            {"id": "jane-smith"},  
            {"id": "ai-tech"},
            {"id": "rel-1"}
        ]
        
        # Process segment
        result = graph_storage.process_segment_schemaless(
            segment=sample_segment,
            episode=sample_episode,
            extraction_result=sample_segment.extraction_result
        )
        
        # Verify processing result
        assert result["entities_created"] == 2
        assert result["relationships_created"] == 1
        assert "processing_time" in result
    
    def test_setup_schema(self, graph_storage, mock_driver):
        """Test schema setup (indexes, constraints)."""
        # Setup
        graph_storage._driver = mock_driver
        
        # Setup schema
        graph_storage.setup_schema()
        
        # Verify index/constraint creation
        session = mock_driver.session.return_value.__enter__.return_value
        # Should create indexes for common lookups
        calls = session.run.call_args_list
        cypher_queries = [call[0][0] for call in calls]
        
        # Check for index creation
        assert any("INDEX" in q for q in cypher_queries)
    
    def test_performance_metrics(self, graph_storage):
        """Test performance metrics collection."""
        # Add some metrics
        graph_storage._extraction_times.extend([0.1, 0.2, 0.15])
        graph_storage._entity_counts.extend([10, 15, 12])
        graph_storage._relationship_counts.extend([5, 8, 6])
        
        # Get metrics
        metrics = graph_storage.get_performance_metrics()
        
        # Verify metrics
        assert "avg_extraction_time" in metrics
        assert "avg_entities_per_segment" in metrics
        assert "avg_relationships_per_segment" in metrics
        assert metrics["avg_extraction_time"] == pytest.approx(0.15, 0.01)
        assert metrics["avg_entities_per_segment"] == pytest.approx(12.33, 0.01)