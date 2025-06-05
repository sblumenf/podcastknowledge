"""Unit tests for graph storage."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from src.storage.graph_storage import (
    GraphStorageService,
    GraphStorageConfig,
    GraphNode,
    GraphRelationship,
    GraphStorageError,
    create_graph_storage
)


class TestGraphStorageConfig:
    """Test GraphStorageConfig dataclass."""
    
    def test_config_creation_default(self):
        """Test creating GraphStorageConfig with defaults."""
        config = GraphStorageConfig()
        
        assert config.uri == "bolt://localhost:7687"
        assert config.username == "neo4j"
        assert config.password == "password"
        assert config.database == "neo4j"
        assert config.max_connection_lifetime == 3600
        assert config.max_connection_pool_size == 50
        assert config.connection_timeout == 30
    
    def test_config_creation_custom(self):
        """Test creating GraphStorageConfig with custom values."""
        config = GraphStorageConfig(
            uri="bolt://remote:7687",
            username="admin",
            password="secret",
            database="knowledge",
            batch_size=500
        )
        
        assert config.uri == "bolt://remote:7687"
        assert config.username == "admin"
        assert config.database == "knowledge"
        assert config.batch_size == 500


class TestGraphNode:
    """Test GraphNode dataclass."""
    
    def test_graph_node_creation(self):
        """Test creating GraphNode."""
        node = GraphNode(
            id="node123",
            labels=["Entity", "Person"],
            properties={"name": "John Doe", "age": 30}
        )
        
        assert node.id == "node123"
        assert "Entity" in node.labels
        assert "Person" in node.labels
        assert node.properties["name"] == "John Doe"
        assert node.properties["age"] == 30
    
    def test_graph_node_to_cypher(self):
        """Test converting GraphNode to Cypher."""
        node = GraphNode(
            id="node123",
            labels=["Entity"],
            properties={"name": "Test", "value": 123}
        )
        
        cypher = node.to_cypher()
        
        assert "Entity" in cypher
        assert "name: $name" in cypher
        assert "value: $value" in cypher


class TestGraphRelationship:
    """Test GraphRelationship dataclass."""
    
    def test_graph_relationship_creation(self):
        """Test creating GraphRelationship."""
        rel = GraphRelationship(
            start_node_id="node1",
            end_node_id="node2",
            type="RELATES_TO",
            properties={"weight": 0.8}
        )
        
        assert rel.start_node_id == "node1"
        assert rel.end_node_id == "node2"
        assert rel.type == "RELATES_TO"
        assert rel.properties["weight"] == 0.8
    
    def test_graph_relationship_to_cypher(self):
        """Test converting GraphRelationship to Cypher."""
        rel = GraphRelationship(
            start_node_id="node1",
            end_node_id="node2",
            type="KNOWS",
            properties={"since": 2020}
        )
        
        cypher = rel.to_cypher()
        
        assert "KNOWS" in cypher
        assert "since: $since" in cypher


class TestGraphStorageService:
    """Test GraphStorageService class."""
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_service_initialization(self, mock_graph_db):
        """Test GraphStorageService initialization."""
        config = GraphStorageConfig()
        mock_driver = Mock()
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(config)
        
        assert service.config == config
        assert service.driver == mock_driver
        
        # Verify driver was created with correct parameters
        mock_graph_db.driver.assert_called_once_with(
            config.uri,
            auth=(config.username, config.password),
            max_connection_lifetime=config.max_connection_lifetime,
            max_connection_pool_size=config.max_connection_pool_size,
            connection_timeout=config.connection_timeout
        )
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_verify_connection_success(self, mock_graph_db):
        """Test successful connection verification."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = Mock()
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.verify_connection()
        
        assert result is True
        mock_session.run.assert_called_once_with("RETURN 1")
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_verify_connection_failure(self, mock_graph_db):
        """Test failed connection verification."""
        mock_driver = Mock()
        mock_driver.session.side_effect = Exception("Connection failed")
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.verify_connection()
        
        assert result is False
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_create_node(self, mock_graph_db):
        """Test creating a node."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_tx = Mock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = {"id": "node123"}
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        node = GraphNode(
            id="node123",
            labels=["Entity"],
            properties={"name": "Test"}
        )
        
        result = service.create_node(node)
        
        assert result == {"id": "node123"}
        mock_session.execute_write.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_create_node_error(self, mock_graph_db):
        """Test node creation error handling."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.execute_write.side_effect = Exception("Database error")
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        node = GraphNode(id="node123", labels=["Entity"])
        
        with pytest.raises(GraphStorageError):
            service.create_node(node)
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_create_relationship(self, mock_graph_db):
        """Test creating a relationship."""
        mock_driver = Mock()
        mock_session = Mock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = {"created": True}
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        rel = GraphRelationship(
            start_node_id="node1",
            end_node_id="node2",
            type="RELATES_TO"
        )
        
        result = service.create_relationship(rel)
        
        assert result == {"created": True}
        mock_session.execute_write.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_batch_create_nodes(self, mock_graph_db):
        """Test batch creating nodes."""
        mock_driver = Mock()
        mock_session = Mock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = [{"id": "1"}, {"id": "2"}]
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig(batch_size=2))
        
        nodes = [
            GraphNode(id="1", labels=["Entity"]),
            GraphNode(id="2", labels=["Entity"]),
            GraphNode(id="3", labels=["Entity"])
        ]
        
        results = service.batch_create_nodes(nodes)
        
        # Should process in batches
        assert len(results) == 3
        assert mock_session.execute_write.call_count == 2  # Two batches
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_find_node(self, mock_graph_db):
        """Test finding a node."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = {"n": {"id": "123", "name": "Test"}}
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_read.return_value = mock_result
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.find_node("123")
        
        assert result == {"id": "123", "name": "Test"}
        mock_session.execute_read.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_find_node_not_found(self, mock_graph_db):
        """Test finding non-existent node."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = None
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_read.return_value = mock_result
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.find_node("nonexistent")
        
        assert result is None
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_update_node(self, mock_graph_db):
        """Test updating a node."""
        mock_driver = Mock()
        mock_session = Mock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = {"updated": True}
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.update_node("123", {"name": "Updated"})
        
        assert result == {"updated": True}
        mock_session.execute_write.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_delete_node(self, mock_graph_db):
        """Test deleting a node."""
        mock_driver = Mock()
        mock_session = Mock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = {"deleted": 1}
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.delete_node("123")
        
        assert result is True
        mock_session.execute_write.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_execute_query(self, mock_graph_db):
        """Test executing custom query."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.data.return_value = [{"count": 10}]
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result
        
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        
        result = service.execute_query("MATCH (n) RETURN count(n) as count")
        
        assert result == [{"count": 10}]
        mock_session.run.assert_called_once()
    
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_close(self, mock_graph_db):
        """Test closing the service."""
        mock_driver = Mock()
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(GraphStorageConfig())
        service.close()
        
        mock_driver.close.assert_called_once()
    
    def test_graph_storage_error(self):
        """Test GraphStorageError exception."""
        with pytest.raises(GraphStorageError) as exc_info:
            raise GraphStorageError("Storage failed")
        
        assert str(exc_info.value) == "Storage failed"


class TestCreateGraphStorage:
    """Test create_graph_storage function."""
    
    @patch.dict('os.environ', {
        "NEO4J_URI": "bolt://custom:7687",
        "NEO4J_USERNAME": "custom_user",
        "NEO4J_PASSWORD": "custom_pass"
    })
    @patch('src.storage.graph_storage.GraphStorageService')
    def test_create_graph_storage_with_env(self, mock_service_class):
        """Test creating graph storage with environment variables."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        service = create_graph_storage()
        
        assert service == mock_service
        
        # Check config was created with env values
        config_arg = mock_service_class.call_args[0][0]
        assert config_arg.uri == "bolt://custom:7687"
        assert config_arg.username == "custom_user"
        assert config_arg.password == "custom_pass"
    
    @patch.dict('os.environ', {}, clear=True)
    @patch('src.storage.graph_storage.GraphStorageService')
    def test_create_graph_storage_defaults(self, mock_service_class):
        """Test creating graph storage with defaults."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        service = create_graph_storage()
        
        # Check config was created with defaults
        config_arg = mock_service_class.call_args[0][0]
        assert config_arg.uri == "bolt://localhost:7687"
        assert config_arg.username == "neo4j"