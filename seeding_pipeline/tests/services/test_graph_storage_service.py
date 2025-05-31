"""Tests for graph storage service implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.storage.graph_storage import GraphStorageService


class TestGraphStorageService:
    """Test suite for GraphStorageService."""
    
    @pytest.fixture
    def service(self):
        """Create graph storage service instance."""
        with patch('src.storage.graph_storage.GraphDatabase') as mock_gdb:
            mock_driver = Mock()
            mock_gdb.driver.return_value = mock_driver
            service = GraphStorageService(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="password"
            )
            service._driver = mock_driver
            return service
    
    def test_initialization(self):
        """Test service initialization."""
        with patch('src.storage.graph_storage.GraphDatabase') as mock_gdb:
            service = GraphStorageService(
                uri="bolt://localhost:7687",
                username="test_user",
                password="test_pass",
                database="test_db"
            )
            mock_gdb.driver.assert_called_once_with(
                "bolt://localhost:7687",
                auth=("test_user", "test_pass")
            )
            assert service.database == "test_db"
    
    def test_store_entity(self, service):
        """Test storing an entity."""
        entity = {
            "id": "ent1",
            "name": "Test Entity",
            "type": "PERSON",
            "confidence": 0.9
        }
        
        mock_session = Mock()
        mock_tx = Mock()
        service._driver.session.return_value = mock_session
        mock_session.execute_write.return_value = entity
        
        result = service.store_entity(entity)
        
        assert result == entity
        mock_session.execute_write.assert_called_once()
        mock_session.close.assert_called_once()
    
    def test_store_relationship(self, service):
        """Test storing a relationship."""
        mock_session = Mock()
        mock_session.execute_write.return_value = {
            "source": "ent1",
            "target": "ent2",
            "type": "RELATED_TO"
        }
        service._driver.session.return_value = mock_session
        
        result = service.store_relationship("ent1", "ent2", "RELATED_TO", {"weight": 0.8})
        
        assert result["source"] == "ent1"
        assert result["target"] == "ent2"
        mock_session.execute_write.assert_called_once()
    
    def test_batch_store_entities(self, service):
        """Test batch storing entities."""
        entities = [
            {"id": "ent1", "name": "Entity 1", "type": "PERSON"},
            {"id": "ent2", "name": "Entity 2", "type": "ORGANIZATION"}
        ]
        
        mock_session = Mock()
        service._driver.session.return_value = mock_session
        
        service.batch_store_entities(entities)
        
        # Should call execute_write for batch operation
        mock_session.execute_write.assert_called_once()
        mock_session.close.assert_called_once()
    
    def test_find_entity_by_name(self, service):
        """Test finding entity by name."""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = {"n": {"id": "ent1", "name": "Test Entity"}}
        mock_session.execute_read.return_value = mock_result
        service._driver.session.return_value = mock_session
        
        result = service.find_entity_by_name("Test Entity")
        
        assert result["id"] == "ent1"
        assert result["name"] == "Test Entity"
        mock_session.execute_read.assert_called_once()
    
    def test_close_connection(self, service):
        """Test closing database connection."""
        service.close()
        service._driver.close.assert_called_once()
    
    def test_connection_error_handling(self, service):
        """Test handling of connection errors."""
        service._driver.session.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            service.store_entity({"id": "test", "name": "Test"})
    
    def test_transaction_rollback(self, service):
        """Test transaction rollback on error."""
        mock_session = Mock()
        mock_session.execute_write.side_effect = Exception("Transaction error")
        service._driver.session.return_value = mock_session
        
        with pytest.raises(Exception, match="Transaction error"):
            service.store_entity({"id": "test", "name": "Test"})
        
        mock_session.close.assert_called_once()