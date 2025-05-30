"""Tests for graph provider implementations."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.providers.graph.base import GraphProvider
from src.providers.graph.memory import InMemoryGraphProvider
from src.providers.graph.neo4j import Neo4jProvider
from src.providers.graph.compatible_neo4j import CompatibleNeo4jProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.providers.graph.metadata_enricher import MetadataEnricher


class TestInMemoryGraphProvider:
    """Test InMemoryGraphProvider implementation."""
    
    def test_memory_provider_initialization(self):
        """Test in-memory provider initialization."""
        provider = InMemoryGraphProvider()
        
        assert provider.name == "memory"
        assert len(provider.nodes) == 0
        assert len(provider.edges) == 0
        assert len(provider.node_index) == 0
    
    def test_memory_provider_add_node(self):
        """Test adding nodes."""
        provider = InMemoryGraphProvider()
        
        node_id = provider.add_node(
            labels=["Person"],
            properties={"name": "John Doe", "age": 30}
        )
        
        assert node_id is not None
        assert node_id in provider.nodes
        assert provider.nodes[node_id]["labels"] == ["Person"]
        assert provider.nodes[node_id]["properties"]["name"] == "John Doe"
        assert provider.nodes[node_id]["properties"]["age"] == 30
    
    def test_memory_provider_add_edge(self):
        """Test adding edges."""
        provider = InMemoryGraphProvider()
        
        # Add nodes
        node1 = provider.add_node(["Person"], {"name": "Alice"})
        node2 = provider.add_node(["Person"], {"name": "Bob"})
        
        # Add edge
        edge_id = provider.add_edge(
            from_node=node1,
            to_node=node2,
            edge_type="KNOWS",
            properties={"since": 2020}
        )
        
        assert edge_id is not None
        assert edge_id in provider.edges
        assert provider.edges[edge_id]["from_node"] == node1
        assert provider.edges[edge_id]["to_node"] == node2
        assert provider.edges[edge_id]["type"] == "KNOWS"
        assert provider.edges[edge_id]["properties"]["since"] == 2020
    
    def test_memory_provider_get_node(self):
        """Test retrieving nodes."""
        provider = InMemoryGraphProvider()
        
        node_id = provider.add_node(["Company"], {"name": "OpenAI"})
        
        node = provider.get_node(node_id)
        assert node is not None
        assert node["labels"] == ["Company"]
        assert node["properties"]["name"] == "OpenAI"
        
        # Non-existent node
        assert provider.get_node("non-existent") is None
    
    def test_memory_provider_find_nodes(self):
        """Test finding nodes by properties."""
        provider = InMemoryGraphProvider()
        
        # Add multiple nodes
        provider.add_node(["Person"], {"name": "John", "age": 30})
        provider.add_node(["Person"], {"name": "Jane", "age": 25})
        provider.add_node(["Person"], {"name": "John", "age": 40})
        provider.add_node(["Company"], {"name": "John Inc"})
        
        # Find by label and property
        johns = provider.find_nodes(labels=["Person"], properties={"name": "John"})
        assert len(johns) == 2
        assert all(node["properties"]["name"] == "John" for node in johns)
        
        # Find by label only
        people = provider.find_nodes(labels=["Person"])
        assert len(people) == 3
        
        # Find by property only
        all_johns = provider.find_nodes(properties={"name": "John"})
        assert len(all_johns) == 3  # 2 people + 1 company
    
    def test_memory_provider_update_node(self):
        """Test updating node properties."""
        provider = InMemoryGraphProvider()
        
        node_id = provider.add_node(["Person"], {"name": "John", "age": 30})
        
        # Update properties
        provider.update_node(node_id, {"age": 31, "city": "New York"})
        
        node = provider.get_node(node_id)
        assert node["properties"]["age"] == 31
        assert node["properties"]["city"] == "New York"
        assert node["properties"]["name"] == "John"  # Original property retained
    
    def test_memory_provider_delete_node(self):
        """Test deleting nodes."""
        provider = InMemoryGraphProvider()
        
        # Add nodes and edge
        node1 = provider.add_node(["Person"], {"name": "Alice"})
        node2 = provider.add_node(["Person"], {"name": "Bob"})
        edge_id = provider.add_edge(node1, node2, "KNOWS")
        
        # Delete node
        provider.delete_node(node1)
        
        assert provider.get_node(node1) is None
        assert provider.get_node(node2) is not None
        
        # Edge should also be deleted
        assert edge_id not in provider.edges
    
    def test_memory_provider_get_neighbors(self):
        """Test getting node neighbors."""
        provider = InMemoryGraphProvider()
        
        # Create graph: A -> B -> C, A -> C
        node_a = provider.add_node(["Node"], {"name": "A"})
        node_b = provider.add_node(["Node"], {"name": "B"})
        node_c = provider.add_node(["Node"], {"name": "C"})
        
        provider.add_edge(node_a, node_b, "CONNECTS")
        provider.add_edge(node_b, node_c, "CONNECTS")
        provider.add_edge(node_a, node_c, "CONNECTS")
        
        # Get outgoing neighbors of A
        neighbors_a = provider.get_neighbors(node_a, direction="out")
        assert len(neighbors_a) == 2
        neighbor_names = {n["properties"]["name"] for n in neighbors_a}
        assert neighbor_names == {"B", "C"}
        
        # Get incoming neighbors of C
        neighbors_c = provider.get_neighbors(node_c, direction="in")
        assert len(neighbors_c) == 2
        
        # Get all neighbors of B
        neighbors_b = provider.get_neighbors(node_b, direction="both")
        assert len(neighbors_b) == 2
    
    def test_memory_provider_query(self):
        """Test basic query functionality."""
        provider = InMemoryGraphProvider()
        
        # Add test data
        john = provider.add_node(["Person"], {"name": "John", "age": 30})
        jane = provider.add_node(["Person"], {"name": "Jane", "age": 25})
        provider.add_edge(john, jane, "KNOWS")
        
        # Simple query (mock Cypher-like)
        results = provider.query("MATCH (p:Person) WHERE p.age > 20 RETURN p")
        assert len(results) == 2
    
    def test_memory_provider_health_check(self):
        """Test health check."""
        provider = InMemoryGraphProvider()
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "memory"
        assert "node_count" in health
        assert "edge_count" in health
    
    def test_memory_provider_clear(self):
        """Test clearing the graph."""
        provider = InMemoryGraphProvider()
        
        # Add data
        provider.add_node(["Test"], {"data": "test"})
        provider.add_edge("1", "2", "TEST")
        
        # Clear
        provider.clear()
        
        assert len(provider.nodes) == 0
        assert len(provider.edges) == 0
        assert len(provider.node_index) == 0


class TestNeo4jProvider:
    """Test Neo4jProvider implementation."""
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_initialization(self, mock_driver):
        """Test Neo4j provider initialization."""
        mock_driver_instance = MagicMock()
        mock_driver.return_value = mock_driver_instance
        
        config = {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
            "database": "neo4j"
        }
        
        provider = Neo4jProvider(config)
        
        mock_driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
        assert provider.database == "neo4j"
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_add_node(self, mock_driver):
        """Test adding node in Neo4j."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": 123}
        mock_session.run.return_value = mock_result
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        node_id = provider.add_node(
            labels=["Person", "Employee"],
            properties={"name": "John", "age": 30}
        )
        
        assert node_id == 123
        
        # Check query
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "CREATE (n:Person:Employee" in query
        assert "$props" in query
        assert call_args[1]["props"] == {"name": "John", "age": 30}
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_add_edge(self, mock_driver):
        """Test adding edge in Neo4j."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": 456}
        mock_session.run.return_value = mock_result
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        edge_id = provider.add_edge(
            from_node=123,
            to_node=456,
            edge_type="WORKS_FOR",
            properties={"since": 2020}
        )
        
        assert edge_id == 456
        
        # Check query
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "MATCH (a), (b)" in query
        assert "CREATE (a)-[r:WORKS_FOR]->(b)" in query
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_query(self, mock_driver):
        """Test executing Cypher query."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        
        mock_records = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
        ]
        mock_result = MagicMock()
        mock_result.data.return_value = mock_records
        mock_session.run.return_value = mock_result
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        results = provider.query(
            "MATCH (p:Person) WHERE p.age > $min_age RETURN p.name, p.age",
            parameters={"min_age": 20}
        )
        
        assert len(results) == 2
        assert results[0]["name"] == "John"
        assert results[1]["age"] == 25
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_error_handling(self, mock_driver):
        """Test Neo4j error handling."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_session.run.side_effect = Exception("Connection failed")
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        with pytest.raises(Exception, match="Connection failed"):
            provider.query("MATCH (n) RETURN n")
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_transaction(self, mock_driver):
        """Test Neo4j transaction support."""
        mock_session = MagicMock()
        mock_tx = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_session.begin_transaction.return_value.__enter__.return_value = mock_tx
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        # Execute in transaction
        with provider.transaction() as tx:
            provider.add_node(["Test"], {"data": "test"}, tx=tx)
            provider.add_edge(1, 2, "TEST", tx=tx)
        
        # Should use transaction
        assert mock_tx.run.call_count >= 2
    
    @patch('neo4j.GraphDatabase.driver')
    def test_neo4j_provider_close(self, mock_driver):
        """Test closing Neo4j connection."""
        mock_driver_instance = MagicMock()
        mock_driver.return_value = mock_driver_instance
        
        provider = Neo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        provider.close()
        
        mock_driver_instance.close.assert_called_once()


class TestSchemalessNeo4jProvider:
    """Test SchemalessNeo4jProvider implementation."""
    
    @patch('neo4j.GraphDatabase.driver')
    def test_schemaless_provider_initialization(self, mock_driver):
        """Test schemaless provider initialization."""
        mock_driver_instance = MagicMock()
        mock_driver.return_value = mock_driver_instance
        
        provider = SchemalessNeo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        assert provider.schema_version == "2.0"
        assert provider.property_namespace == "props"
    
    @patch('neo4j.GraphDatabase.driver')
    def test_schemaless_provider_add_entity(self, mock_driver):
        """Test adding entity in schemaless mode."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": "entity-123"}
        mock_session.run.return_value = mock_result
        
        provider = SchemalessNeo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        entity_data = {
            "name": "John Doe",
            "type": "person",
            "attributes": {
                "age": 30,
                "occupation": "Engineer"
            },
            "metadata": {
                "source": "podcast-1",
                "confidence": 0.95
            }
        }
        
        entity_id = provider.add_entity(entity_data)
        
        assert entity_id == "entity-123"
        
        # Check query includes schemaless properties
        call_args = mock_session.run.call_args
        assert "props" in str(call_args)
    
    @patch('neo4j.GraphDatabase.driver')
    def test_schemaless_provider_add_relationship(self, mock_driver):
        """Test adding relationship in schemaless mode."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": "rel-456"}
        mock_session.run.return_value = mock_result
        
        provider = SchemalessNeo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        relationship_data = {
            "from_entity": "entity-123",
            "to_entity": "entity-456",
            "type": "works_with",
            "properties": {
                "since": "2020",
                "department": "Engineering"
            },
            "metadata": {
                "extracted_from": "segment-1"
            }
        }
        
        rel_id = provider.add_relationship(relationship_data)
        
        assert rel_id == "rel-456"
    
    @patch('neo4j.GraphDatabase.driver')
    def test_schemaless_provider_flexible_query(self, mock_driver):
        """Test flexible querying in schemaless mode."""
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        
        mock_records = [
            {
                "entity": {
                    "id": "1",
                    "props": {"name": "John", "type": "person", "age": 30}
                }
            }
        ]
        mock_result = MagicMock()
        mock_result.data.return_value = mock_records
        mock_session.run.return_value = mock_result
        
        provider = SchemalessNeo4jProvider({
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        })
        
        # Query by dynamic property
        results = provider.find_entities({
            "type": "person",
            "attributes.age": {"$gte": 25}
        })
        
        assert len(results) == 1
        assert results[0]["entity"]["props"]["name"] == "John"


class TestMetadataEnricher:
    """Test MetadataEnricher functionality."""
    
    def test_metadata_enricher_initialization(self):
        """Test metadata enricher initialization."""
        enricher = MetadataEnricher()
        
        assert enricher.enrichment_rules is not None
        assert len(enricher.extractors) > 0
    
    def test_enrich_entity_metadata(self):
        """Test enriching entity metadata."""
        enricher = MetadataEnricher()
        
        entity = {
            "name": "Apple Inc.",
            "type": "organization",
            "description": "Technology company founded in 1976"
        }
        
        enriched = enricher.enrich_entity(entity)
        
        # Should add metadata
        assert "metadata" in enriched
        assert "enriched_at" in enriched["metadata"]
        assert "extracted_dates" in enriched["metadata"]
        assert "1976" in enriched["metadata"]["extracted_dates"]
    
    def test_enrich_relationship_metadata(self):
        """Test enriching relationship metadata."""
        enricher = MetadataEnricher()
        
        relationship = {
            "type": "founded_by",
            "properties": {
                "date": "April 1, 1976",
                "location": "Cupertino, California"
            }
        }
        
        enriched = enricher.enrich_relationship(relationship)
        
        assert "metadata" in enriched
        assert "normalized_date" in enriched["metadata"]
        assert "location_components" in enriched["metadata"]
    
    def test_batch_enrichment(self):
        """Test batch enrichment of entities."""
        enricher = MetadataEnricher()
        
        entities = [
            {"name": "Entity 1", "type": "person"},
            {"name": "Entity 2", "type": "organization"},
            {"name": "Entity 3", "type": "location"}
        ]
        
        enriched_entities = enricher.enrich_batch(entities)
        
        assert len(enriched_entities) == 3
        assert all("metadata" in e for e in enriched_entities)
    
    def test_custom_enrichment_rules(self):
        """Test custom enrichment rules."""
        def custom_enricher(entity):
            if entity.get("type") == "person":
                entity["metadata"]["is_individual"] = True
            return entity
        
        enricher = MetadataEnricher(custom_rules=[custom_enricher])
        
        person = {"name": "John Doe", "type": "person"}
        enriched = enricher.enrich_entity(person)
        
        assert enriched["metadata"]["is_individual"] is True
        
        org = {"name": "OpenAI", "type": "organization"}
        enriched_org = enricher.enrich_entity(org)
        
        assert "is_individual" not in enriched_org["metadata"]