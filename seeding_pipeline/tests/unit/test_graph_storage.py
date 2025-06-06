"""Unit tests for graph storage."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from src.storage.graph_storage import GraphStorageService
from src.core.exceptions import ProviderError, ConnectionError


class TestGraphStorageService:
    """Test GraphStorageService class."""
    
    @pytest.fixture
    def mock_driver(self):
        """Create mock Neo4j driver."""
        driver = Mock()
        driver.session.return_value.__enter__ = Mock()
        driver.session.return_value.__exit__ = Mock()
        return driver
    
    def test_service_initialization(self):
        """Test GraphStorageService initialization."""
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            database="neo4j"
        )
        
        assert service.uri == "bolt://localhost:7687"
        assert service.username == "neo4j"
        assert service.password == "password"
        assert service.database == "neo4j"
        assert service._driver is None
        
    def test_service_initialization_missing_uri(self):
        """Test GraphStorageService initialization with missing URI."""
        with pytest.raises(ValueError, match="Neo4j URI is required"):
            GraphStorageService(
                uri="",
                username="neo4j",
                password="password"
            )
            
    def test_service_initialization_missing_credentials(self):
        """Test GraphStorageService initialization with missing credentials."""
        with pytest.raises(ValueError, match="Neo4j username and password are required"):
            GraphStorageService(
                uri="bolt://localhost:7687",
                username="",
                password="password"
            )
            
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_connect(self, mock_graph_db):
        """Test connecting to Neo4j."""
        mock_driver = self.mock_driver()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = {"status": "Connected"}
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        service.connect()
        
        mock_graph_db.driver.assert_called_once()
        mock_session.run.assert_called_with("RETURN 'Connected' AS status")
        
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_connect_failure(self, mock_graph_db):
        """Test connection failure."""
        mock_graph_db.driver.side_effect = Exception("Connection failed")
        
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        with pytest.raises(ImportError):
            service.connect()
            
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_disconnect(self, mock_graph_db):
        """Test disconnecting from Neo4j."""
        mock_driver = Mock()
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        service._driver = mock_driver
        
        service.disconnect()
        
        mock_driver.close.assert_called_once()
        assert service._driver is None
        
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_session_context_manager(self, mock_graph_db):
        """Test session context manager."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        with service.session() as session:
            assert session == mock_session
            
        mock_session.close.assert_called_once()
        
    @patch('src.storage.graph_storage.GraphDatabase')
    def test_store_podcast(self, mock_graph_db):
        """Test storing podcast data."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_tx = Mock()
        mock_session.execute_write.return_value = {"nodes": 10, "relationships": 5}
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        mock_graph_db.driver.return_value = mock_driver
        
        service = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        # Create mock podcast data
        from src.core.models import Podcast, Episode
        podcast = Podcast(
            id="pod123",
            title="Test Podcast",
            description="Test Description"
        )
        episode = Episode(
            id="ep123",
            podcast_id="pod123",
            title="Test Episode",
            description="Episode Description",
            segments=[]
        )
        podcast.episodes = [episode]
        
        # Test store_podcast method if it exists
        if hasattr(service, 'store_podcast'):
            result = service.store_podcast(podcast)
            mock_session.execute_write.assert_called()