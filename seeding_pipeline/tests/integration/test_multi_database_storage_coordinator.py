"""Test multi-database storage coordinator."""

import os
from unittest.mock import Mock, MagicMock, patch
import pytest

from src.storage.multi_database_storage_coordinator import MultiDatabaseStorageCoordinator
from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage
from src.core.models import Entity


class TestMultiDatabaseStorageCoordinator:
    """Test multi-database storage coordinator functionality."""
    
    @pytest.fixture
    def mock_multi_db_storage(self):
        """Create mock multi-database storage."""
        mock = MagicMock()
        mock.set_podcast_context = MagicMock()
        mock._current_podcast_id = None
        mock.create_node = MagicMock()
        mock.create_relationship = MagicMock()
        mock.driver = MagicMock()
        mock.driver.session = MagicMock()
        return mock
    
    @pytest.fixture
    def mock_graph_enhancer(self):
        """Create mock graph enhancer."""
        mock = Mock()
        mock.enhance_episode = Mock()
        return mock
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock()
        config.enhance_graph = True
        config.enable_knowledge_discovery = False
        return config
    
    def test_multi_db_mode_detection(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test that multi-db mode is correctly detected."""
        # With MultiDatabaseGraphStorage instance
        mock_multi_db_storage.__class__ = MultiDatabaseGraphStorage
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        assert coordinator.multi_db_mode is True
        
        # With regular storage but PODCAST_MODE=multi
        with patch.dict(os.environ, {'PODCAST_MODE': 'multi'}):
            regular_storage = Mock()
            coordinator = MultiDatabaseStorageCoordinator(
                regular_storage, mock_graph_enhancer, mock_config
            )
            assert coordinator.multi_db_mode is True
    
    def test_store_all_sets_podcast_context(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test that store_all sets podcast context correctly."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        podcast_config = {
            'id': 'tech_podcast',
            'podcast_id': 'tech_podcast',
            'name': 'Tech Podcast'
        }
        
        episode = {
            'id': 'ep123',
            'title': 'Episode 123',
            'podcast_id': 'tech_podcast'
        }
        
        segments = []
        extraction_result = {}
        resolved_entities = []
        
        # Call store_all
        coordinator.store_all(
            podcast_config, episode, segments, 
            extraction_result, resolved_entities
        )
        
        # Verify podcast context was set
        mock_multi_db_storage.set_podcast_context.assert_called_once_with('tech_podcast')
    
    def test_podcast_id_extraction_priority(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test podcast ID extraction priority order."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        # Test priority: podcast_config['podcast_id'] > podcast_config['id'] > episode['podcast_id']
        
        # Case 1: podcast_id in podcast_config
        podcast_config = {'podcast_id': 'from_config', 'id': 'config_id'}
        episode = {'id': 'ep1', 'title': 'Ep 1', 'podcast_id': 'from_episode'}
        
        coordinator.store_all(podcast_config, episode, [], {}, [])
        mock_multi_db_storage.set_podcast_context.assert_called_with('from_config')
        
        # Case 2: Only id in podcast_config
        podcast_config = {'id': 'config_id'}
        episode = {'id': 'ep1', 'title': 'Ep 1', 'podcast_id': 'from_episode'}
        
        coordinator.store_all(podcast_config, episode, [], {}, [])
        mock_multi_db_storage.set_podcast_context.assert_called_with('config_id')
        
        # Case 3: Only podcast_id in episode
        podcast_config = {}
        episode = {'id': 'ep1', 'title': 'Ep 1', 'podcast_id': 'from_episode'}
        
        coordinator.store_all(podcast_config, episode, [], {}, [])
        mock_multi_db_storage.set_podcast_context.assert_called_with('from_episode')
    
    def test_store_podcast_includes_podcast_id(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test that _store_podcast includes podcast_id in node data."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        podcast_config = {
            'id': 'test_podcast',
            'name': 'Test Podcast'
        }
        
        coordinator._store_podcast(podcast_config)
        
        # Verify create_node was called with podcast_id
        mock_multi_db_storage.create_node.assert_called_once()
        call_args = mock_multi_db_storage.create_node.call_args
        assert call_args[0][0] == 'Podcast'
        node_data = call_args[0][1]
        assert node_data['podcast_id'] == 'test_podcast'
    
    def test_store_episode_includes_podcast_id(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test that _store_episode includes podcast_id in node data."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        episode = {
            'id': 'ep123',
            'title': 'Episode 123',
            'podcast_id': 'my_podcast'
        }
        
        coordinator._store_episode(episode, {})
        
        # Verify create_node was called with podcast_id
        mock_multi_db_storage.create_node.assert_called_once()
        call_args = mock_multi_db_storage.create_node.call_args
        assert call_args[0][0] == 'Episode'
        node_data = call_args[0][1]
        assert node_data['podcast_id'] == 'my_podcast'
    
    def test_switch_podcast_context(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test switching podcast context."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        coordinator.switch_podcast_context('new_podcast')
        
        mock_multi_db_storage.set_podcast_context.assert_called_once_with('new_podcast')
    
    def test_get_current_podcast_context(self, mock_multi_db_storage, mock_graph_enhancer, mock_config):
        """Test getting current podcast context."""
        coordinator = MultiDatabaseStorageCoordinator(
            mock_multi_db_storage, mock_graph_enhancer, mock_config
        )
        
        mock_multi_db_storage._current_podcast_id = 'current_podcast'
        
        context = coordinator.get_current_podcast_context()
        assert context == 'current_podcast'
    
    def test_backwards_compatibility(self, mock_graph_enhancer, mock_config):
        """Test that coordinator works with regular storage (backwards compatibility)."""
        # Create a mock that explicitly doesn't have set_podcast_context
        regular_storage = MagicMock(spec=['create_node', 'create_relationship', 'driver'])
        regular_storage.create_node = Mock()
        regular_storage.create_relationship = Mock()
        
        # Mock driver for knowledge discovery
        regular_storage.driver = Mock()
        regular_storage.driver.session = Mock()
        
        # Ensure PODCAST_MODE is not set to 'multi'
        with patch.dict(os.environ, {'PODCAST_MODE': 'single'}, clear=True):
            coordinator = MultiDatabaseStorageCoordinator(
                regular_storage, mock_graph_enhancer, mock_config
            )
            
            # Should not be in multi-db mode with regular storage
            assert coordinator.multi_db_mode is False
            
            # Should work normally without setting context
            podcast_config = {'id': 'test', 'name': 'Test'}
            episode = {'id': 'ep1', 'title': 'Episode 1'}
            
            coordinator.store_all(podcast_config, episode, [], {}, [])
            
            # Should have created nodes without error
            assert regular_storage.create_node.called