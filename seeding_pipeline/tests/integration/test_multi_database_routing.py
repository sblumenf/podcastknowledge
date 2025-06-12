"""Test multi-database routing for podcasts."""

import os
import tempfile
from pathlib import Path
import pytest
import yaml
from unittest.mock import Mock, patch, MagicMock

from src.config.podcast_databases import PodcastDatabaseConfig
from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage


class TestPodcastDatabaseConfig:
    """Test podcast database configuration."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'default_database': 'neo4j',
                'podcasts': {
                    'tech_show': {
                        'database': 'tech_db',
                        'name': 'Tech Show'
                    },
                    'science_pod': {
                        'database': 'science_db',
                        'name': 'Science Podcast'
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        config = PodcastDatabaseConfig(temp_config_file)
        
        assert config.get_database_for_podcast('tech_show') == 'tech_db'
        assert config.get_database_for_podcast('science_pod') == 'science_db'
        assert config.get_database_for_podcast('unknown') == 'neo4j'
    
    def test_default_config(self):
        """Test default configuration when file doesn't exist."""
        config = PodcastDatabaseConfig('/nonexistent/path.yaml')
        
        assert config.get_database_for_podcast('unknown_podcast') == 'neo4j'
        assert config.get_database_for_podcast('any_podcast') == 'neo4j'
    
    def test_add_podcast(self, temp_config_file):
        """Test adding new podcast configuration."""
        config = PodcastDatabaseConfig(temp_config_file)
        
        config.add_podcast('new_podcast', {
            'database': 'new_db',
            'name': 'New Podcast',
            'description': 'A new podcast'
        })
        
        assert config.get_database_for_podcast('new_podcast') == 'new_db'
        
    def test_list_podcasts(self, temp_config_file):
        """Test listing all podcast databases."""
        config = PodcastDatabaseConfig(temp_config_file)
        
        podcasts = config.list_podcasts()
        assert podcasts == {
            'tech_show': 'tech_db',
            'science_pod': 'science_db'
        }


class TestMultiDatabaseGraphStorage:
    """Test multi-database graph storage routing."""
    
    @pytest.fixture
    def mock_graph_storage(self):
        """Mock GraphStorageService class."""
        with patch('src.storage.multi_database_graph_storage.GraphStorageService') as mock:
            yield mock
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'default_database': 'neo4j',
                'podcasts': {
                    'podcast_a': {'database': 'db_a'},
                    'podcast_b': {'database': 'db_b'}
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        os.unlink(temp_path)
    
    def test_get_connection_creates_new(self, mock_graph_storage, temp_config_file):
        """Test that get_connection creates new connections."""
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Get connection for podcast_a
        conn = storage.get_connection('podcast_a')
        
        # Verify GraphStorageService was created with correct database
        mock_graph_storage.assert_called_once_with(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            database='db_a'
        )
        
        # Verify connection was initialized
        conn.connect.assert_called_once()
    
    def test_get_connection_uses_cache(self, mock_graph_storage, temp_config_file):
        """Test that connections are cached."""
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Get connection twice
        conn1 = storage.get_connection('podcast_a')
        conn2 = storage.get_connection('podcast_a')
        
        # Should be same instance
        assert conn1 is conn2
        
        # GraphStorageService should only be created once
        assert mock_graph_storage.call_count == 1
    
    def test_podcast_context_manager(self, mock_graph_storage, temp_config_file):
        """Test podcast context manager."""
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Use context manager
        with storage.podcast_context('podcast_b') as conn:
            assert storage._current_podcast_id == 'podcast_b'
            # Verify correct database was used
            mock_graph_storage.assert_called_with(
                uri='bolt://localhost:7687',
                username='neo4j',
                password='password',
                database='db_b'
            )
        
        # Context should be restored
        assert storage._current_podcast_id is None
    
    def test_store_methods_route_correctly(self, mock_graph_storage, temp_config_file):
        """Test that store methods route to correct database."""
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Mock episode with podcast_id
        mock_episode = Mock()
        mock_episode.podcast_id = 'podcast_a'
        
        # Store episode
        storage.store_episode(mock_episode)
        
        # Verify correct database was used
        mock_graph_storage.assert_called_with(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            database='db_a'
        )
        
        # Verify store_episode was called on connection
        mock_conn = mock_graph_storage.return_value
        mock_conn.store_episode.assert_called_once_with(mock_episode)
    
    def test_fallback_to_default_database(self, mock_graph_storage, temp_config_file):
        """Test fallback to default database for unknown podcasts."""
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Get connection for unknown podcast
        conn = storage.get_connection('unknown_podcast')
        
        # Should use default database
        mock_graph_storage.assert_called_with(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            database='neo4j'
        )
    
    def test_close_all_connections(self, mock_graph_storage, temp_config_file):
        """Test closing all connections."""
        # Create separate mock instances for each connection
        mock_conn_a = MagicMock()
        mock_conn_b = MagicMock()
        
        # Configure mock to return different instances
        mock_graph_storage.side_effect = [mock_conn_a, mock_conn_b]
        
        storage = MultiDatabaseGraphStorage(
            uri='bolt://localhost:7687',
            username='neo4j',
            password='password',
            config_path=temp_config_file
        )
        
        # Create multiple connections
        conn_a = storage.get_connection('podcast_a')
        conn_b = storage.get_connection('podcast_b')
        
        # Verify we got different instances
        assert conn_a is mock_conn_a
        assert conn_b is mock_conn_b
        
        # Close all
        storage.close()
        
        # Verify all connections were closed
        mock_conn_a.close.assert_called_once()
        mock_conn_b.close.assert_called_once()
        
        # Cache should be cleared
        assert len(storage._connections) == 0