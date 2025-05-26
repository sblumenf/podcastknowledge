"""Tests for graph database providers."""

import pytest
from unittest.mock import patch, MagicMock
import uuid

from src.providers.graph.memory import InMemoryGraphProvider
from src.providers.graph.neo4j import Neo4jProvider
from src.core.exceptions import ProviderError, ConnectionError
from src.core.models import Entity, Episode, Segment


class TestInMemoryGraphProvider:
    """Test in-memory graph provider functionality."""
    
    def test_initialization(self):
        """Test provider initialization."""
        config = {'database': 'test'}
        provider = InMemoryGraphProvider(config)
        
        assert provider.database == 'test'
        assert len(provider.nodes) == 0
        assert len(provider.relationships) == 0
        
    def test_connect_disconnect(self):
        """Test connect and disconnect."""
        provider = InMemoryGraphProvider({})
        
        provider.connect()
        assert provider._initialized is True
        
        # Add some data
        node_id = provider.create_node('TestNode', {'id': 'test1', 'name': 'Test'})
        assert provider.get_node_count() == 1
        
        provider.disconnect()
        assert provider._initialized is False
        assert provider.get_node_count() == 0
        
    def test_create_node(self):
        """Test node creation."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create node with ID
        properties = {'id': 'entity1', 'name': 'Test Entity', 'type': 'PERSON'}
        node_id = provider.create_node('Entity', properties)
        
        assert node_id == 'entity1'
        assert provider.get_node_count() == 1
        
        # Verify node data
        node = provider.get_node('entity1')
        assert node['name'] == 'Test Entity'
        assert node['type'] == 'PERSON'
        assert 'Entity' in node['_labels']
        
    def test_create_node_auto_id(self):
        """Test node creation with auto-generated ID."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create node without ID
        properties = {'name': 'Test Node'}
        node_id = provider.create_node('TestNode', properties)
        
        assert node_id is not None
        assert len(node_id) > 0
        
        # Verify node
        node = provider.get_node(node_id)
        assert node['name'] == 'Test Node'
        assert node['id'] == node_id
        
    def test_create_relationship(self):
        """Test relationship creation."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create nodes
        node1_id = provider.create_node('Entity', {'id': 'e1', 'name': 'Entity 1'})
        node2_id = provider.create_node('Entity', {'id': 'e2', 'name': 'Entity 2'})
        
        # Create relationship
        provider.create_relationship(node1_id, node2_id, 'RELATED_TO', {'weight': 0.8})
        
        assert provider.get_relationship_count() == 1
        
        # Verify relationship
        rels = provider.get_all_relationships()
        assert rels[0]['source_id'] == 'e1'
        assert rels[0]['target_id'] == 'e2'
        assert rels[0]['type'] == 'RELATED_TO'
        assert rels[0]['properties']['weight'] == 0.8
        
    def test_create_relationship_missing_nodes(self):
        """Test relationship creation with missing nodes."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Try to create relationship with non-existent nodes
        with pytest.raises(ProviderError, match="Source node"):
            provider.create_relationship('missing1', 'missing2', 'RELATED_TO')
            
    def test_update_node(self):
        """Test node update."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create node
        node_id = provider.create_node('Entity', {
            'id': 'e1',
            'name': 'Original Name',
            'count': 1
        })
        
        # Update node
        provider.update_node(node_id, {
            'name': 'Updated Name',
            'count': 2,
            'new_prop': 'New Value'
        })
        
        # Verify update
        node = provider.get_node(node_id)
        assert node['name'] == 'Updated Name'
        assert node['count'] == 2
        assert node['new_prop'] == 'New Value'
        
    def test_delete_node(self):
        """Test node deletion."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create nodes and relationship
        node1_id = provider.create_node('Entity', {'id': 'e1'})
        node2_id = provider.create_node('Entity', {'id': 'e2'})
        provider.create_relationship(node1_id, node2_id, 'RELATED_TO')
        
        assert provider.get_node_count() == 2
        assert provider.get_relationship_count() == 1
        
        # Delete node (should also delete relationship)
        provider.delete_node(node1_id)
        
        assert provider.get_node_count() == 1
        assert provider.get_relationship_count() == 0
        assert provider.get_node(node1_id) is None
        assert provider.get_node(node2_id) is not None
        
    def test_query_simple(self):
        """Test simple query execution."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Test connection query
        with provider.session() as session:
            result = session.run("RETURN 'OK' AS status")
            assert result[0]['status'] == 'OK'
            
    def test_query_match_node(self):
        """Test MATCH query for nodes."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create test nodes
        provider.create_node('Entity', {'id': 'e1', 'name': 'Entity 1'})
        provider.create_node('Entity', {'id': 'e2', 'name': 'Entity 2'})
        provider.create_node('Insight', {'id': 'i1', 'content': 'Test insight'})
        
        # Query by ID
        results = provider.query(
            "MATCH (n:Entity {id: $node_id}) RETURN n",
            {'node_id': 'e1'}
        )
        
        assert len(results) == 1
        assert results[0]['n']['name'] == 'Entity 1'
        
    def test_health_check(self):
        """Test health check."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        health = provider.health_check()
        assert health['healthy'] is True
        assert health['provider'] == 'InMemoryGraphProvider'
        assert health['status'] == 'OK'
        
    def test_high_level_methods(self):
        """Test high-level convenience methods."""
        provider = InMemoryGraphProvider({})
        provider.connect()
        
        # Create entity using high-level method
        entity = Entity(
            id='e1',
            name='Test Entity',
            type='PERSON',
            description='A test entity',
            first_mentioned='2024-01-01',
            mention_count=5,
            bridge_score=0.8,
            is_peripheral=False
        )
        
        entity_id = provider.create_entity(entity)
        assert entity_id == 'e1'
        
        # Verify entity was created correctly
        node = provider.get_node('e1')
        assert node['name'] == 'Test Entity'
        assert node['type'] == 'PERSON'
        assert node['bridge_score'] == 0.8


class TestNeo4jProvider:
    """Test Neo4j provider functionality."""
    
    def test_initialization_without_credentials(self):
        """Test initialization fails without credentials."""
        # Missing URI
        config = {'username': 'neo4j', 'password': 'pass'}
        provider = Neo4jProvider(config)
        with pytest.raises(ProviderError, match="URI is required"):
            provider._initialize_driver()
            
        # Missing username/password
        config = {'uri': 'bolt://localhost:7687'}
        provider = Neo4jProvider(config)
        with pytest.raises(ProviderError, match="username and password"):
            provider._initialize_driver()
            
    @patch('src.providers.graph.neo4j.GraphDatabase')
    def test_initialization_with_credentials(self, mock_graph_db):
        """Test successful initialization."""
        config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password',
            'database': 'testdb',
            'pool_size': 10
        }
        
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        
        provider = Neo4jProvider(config)
        provider._initialize_driver()
        
        assert provider._driver == mock_driver
        mock_graph_db.driver.assert_called_once_with(
            'bolt://localhost:7687',
            auth=('neo4j', 'password'),
            max_connection_pool_size=10,
            max_connection_lifetime=3600,
            connection_acquisition_timeout=30.0
        )
        
    @patch('src.providers.graph.neo4j.GraphDatabase')
    def test_connect(self, mock_graph_db):
        """Test connection verification."""
        config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {'status': 'Connected'}
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        provider = Neo4jProvider(config)
        provider.connect()
        
        mock_session.run.assert_called_with("RETURN 'Connected' AS status")
        
    @patch('src.providers.graph.neo4j.GraphDatabase')
    def test_create_node(self, mock_graph_db):
        """Test node creation."""
        config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {'id': 'test1'}
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        provider = Neo4jProvider(config)
        provider._initialized = True
        provider._driver = mock_driver
        
        # Create node
        properties = {'id': 'test1', 'name': 'Test Node', 'value': 42}
        node_id = provider.create_node('TestNode', properties)
        
        assert node_id == 'test1'
        
        # Verify Cypher query
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        params = call_args[1]
        
        assert 'CREATE (n:TestNode' in cypher
        assert params['id'] == 'test1'
        assert params['name'] == 'Test Node'
        assert params['value'] == 42
        
    @patch('src.providers.graph.neo4j.GraphDatabase')
    def test_health_check_success(self, mock_graph_db):
        """Test successful health check."""
        config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {'status': 'OK'}
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        provider = Neo4jProvider(config)
        provider._initialized = True
        provider._driver = mock_driver
        
        health = provider.health_check()
        
        assert health['healthy'] is True
        assert health['provider'] == 'Neo4jProvider'
        assert health['status'] == 'OK'
        
    def test_missing_import(self):
        """Test handling of missing neo4j package."""
        config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        with patch('src.providers.graph.neo4j.GraphDatabase', side_effect=ImportError):
            provider = Neo4jProvider(config)
            with pytest.raises(ProviderError, match="neo4j is not installed"):
                provider._initialize_driver()