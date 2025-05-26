"""Tests for provider factory."""

import pytest
from unittest.mock import MagicMock, patch

from src.factories.provider_factory import ProviderFactory, ProviderManager
from src.core.exceptions import ProviderError


class TestProviderFactory:
    """Test provider factory functionality."""
    
    def test_register_provider(self):
        """Test provider registration."""
        # Create a mock provider class
        class MockProvider:
            def __init__(self, config):
                self.config = config
                
        # Register the provider
        ProviderFactory.register_provider('audio', 'test_provider', MockProvider)
        
        # Check it's in the registry
        assert 'test_provider' in ProviderFactory._provider_registry['audio']
        assert ProviderFactory._provider_registry['audio']['test_provider'] == MockProvider
        
    def test_create_provider_from_registry(self):
        """Test creating provider from registry."""
        # Register a mock provider
        class MockProvider:
            def __init__(self, config):
                self.config = config
                self.test_value = config.get('test_value', 'default')
                
        ProviderFactory.register_provider('llm', 'test_llm', MockProvider)
        
        # Create provider
        config = {'test_value': 'custom'}
        provider = ProviderFactory.create_provider('llm', 'test_llm', config)
        
        assert isinstance(provider, MockProvider)
        assert provider.test_value == 'custom'
        
    def test_create_provider_invalid_type(self):
        """Test creating provider with invalid type."""
        with pytest.raises(ValueError, match="Invalid provider type"):
            ProviderFactory.create_provider('invalid_type', 'some_provider', {})
            
    def test_create_provider_unknown_name(self):
        """Test creating provider with unknown name."""
        with pytest.raises(ValueError, match="Unknown audio provider"):
            ProviderFactory.create_provider('audio', 'unknown_provider', {})
            
    @patch('src.factories.provider_factory.import_module')
    def test_create_provider_dynamic_import(self, mock_import):
        """Test dynamic import of provider."""
        # Mock the import
        mock_module = MagicMock()
        mock_provider_class = MagicMock()
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance
        
        # Set up the mock to return our provider class
        mock_module.MockProvider = mock_provider_class
        mock_import.return_value = mock_module
        
        # Clear any cached entries
        if 'mock' in ProviderFactory._provider_registry.get('audio', {}):
            del ProviderFactory._provider_registry['audio']['mock']
        
        # Create provider (should trigger dynamic import)
        config = {'key': 'value'}
        provider = ProviderFactory.create_provider('audio', 'mock', config)
        
        assert provider == mock_provider_instance
        mock_provider_class.assert_called_once_with(config)
        
    def test_create_typed_providers(self):
        """Test creating providers with typed methods."""
        # Register mock providers
        class MockAudioProvider:
            def __init__(self, config):
                self.config = config
                
        class MockLLMProvider:
            def __init__(self, config):
                self.config = config
                
        ProviderFactory.register_provider('audio', 'test_audio', MockAudioProvider)
        ProviderFactory.register_provider('llm', 'test_llm', MockLLMProvider)
        
        # Create using typed methods
        audio_provider = ProviderFactory.create_audio_provider('test_audio', {})
        llm_provider = ProviderFactory.create_llm_provider('test_llm', {})
        
        assert isinstance(audio_provider, MockAudioProvider)
        assert isinstance(llm_provider, MockLLMProvider)
        
    def test_create_from_config(self):
        """Test creating multiple providers from config."""
        # Register mock providers
        class MockProvider:
            def __init__(self, config):
                self.config = config
                self.provider_type = config.get('provider')
                
        for ptype in ['audio', 'llm', 'graph', 'embedding']:
            ProviderFactory.register_provider(ptype, 'mock', MockProvider)
            
        # Create from config
        config = {
            'audio': {'provider': 'mock', 'setting': 'audio_value'},
            'llm': {'provider': 'mock', 'setting': 'llm_value'},
            'graph': {'provider': 'mock', 'setting': 'graph_value'},
            'embedding': {'provider': 'mock', 'setting': 'embedding_value'}
        }
        
        providers = ProviderFactory.create_from_config(config)
        
        assert len(providers) == 4
        assert providers['audio'].config['setting'] == 'audio_value'
        assert providers['llm'].config['setting'] == 'llm_value'
        assert providers['graph'].config['setting'] == 'graph_value'
        assert providers['embedding'].config['setting'] == 'embedding_value'
        
    def test_get_available_providers(self):
        """Test getting available providers."""
        # Get all providers
        all_providers = ProviderFactory.get_available_providers()
        
        assert 'audio' in all_providers
        assert 'whisper' in all_providers['audio']
        assert 'mock' in all_providers['audio']
        
        assert 'llm' in all_providers
        assert 'gemini' in all_providers['llm']
        
        # Get specific type
        audio_providers = ProviderFactory.get_available_providers('audio')
        assert 'audio' in audio_providers
        assert len(audio_providers) == 1
        
    def test_health_check_all(self):
        """Test health checking all providers."""
        # Create mock providers
        class HealthyProvider:
            def health_check(self):
                return {'healthy': True, 'status': 'ok'}
                
        class UnhealthyProvider:
            def health_check(self):
                return {'healthy': False, 'error': 'test error'}
                
        class NoHealthCheckProvider:
            pass
            
        providers = {
            'provider1': HealthyProvider(),
            'provider2': UnhealthyProvider(),
            'provider3': NoHealthCheckProvider()
        }
        
        results = ProviderFactory.health_check_all(providers)
        
        assert results['provider1']['healthy'] is True
        assert results['provider2']['healthy'] is False
        assert results['provider3']['healthy'] == 'unknown'


class TestProviderManager:
    """Test provider manager functionality."""
    
    def test_add_provider(self):
        """Test adding providers to manager."""
        manager = ProviderManager()
        
        mock_provider = MagicMock()
        manager.add_provider('audio', 'test_audio', mock_provider, version='1.0.0')
        
        assert 'test_audio' in manager.providers['audio']
        assert manager.providers['audio']['test_audio'] == mock_provider
        assert manager.versions['audio']['test_audio'] == '1.0.0'
        
    def test_get_provider(self):
        """Test getting providers from manager."""
        manager = ProviderManager()
        
        mock_provider1 = MagicMock()
        mock_provider2 = MagicMock()
        
        manager.add_provider('llm', 'provider1', mock_provider1)
        manager.add_provider('llm', 'provider2', mock_provider2)
        
        # Get specific provider
        provider = manager.get_provider('llm', 'provider1')
        assert provider == mock_provider1
        
        # Get any provider of type
        provider = manager.get_provider('llm')
        assert provider in [mock_provider1, mock_provider2]
        
    def test_get_provider_errors(self):
        """Test error cases for getting providers."""
        manager = ProviderManager()
        
        # Invalid type
        with pytest.raises(ValueError, match="Invalid provider type"):
            manager.get_provider('invalid_type')
            
        # No providers of type
        with pytest.raises(KeyError, match="No audio providers available"):
            manager.get_provider('audio')
            
        # Named provider not found
        manager.add_provider('audio', 'existing', MagicMock())
        with pytest.raises(KeyError, match="No audio provider named 'missing'"):
            manager.get_provider('audio', 'missing')
            
    def test_remove_provider(self):
        """Test removing providers."""
        manager = ProviderManager()
        
        # Create provider with disconnect method
        mock_provider = MagicMock()
        mock_provider.disconnect = MagicMock()
        
        manager.add_provider('graph', 'test_graph', mock_provider, version='2.0.0')
        
        # Remove provider
        manager.remove_provider('graph', 'test_graph')
        
        # Check it's removed
        assert 'test_graph' not in manager.providers['graph']
        assert 'graph' not in manager.versions or 'test_graph' not in manager.versions['graph']
        
        # Check disconnect was called
        mock_provider.disconnect.assert_called_once()
        
    def test_remove_provider_disconnect_error(self):
        """Test removing provider when disconnect fails."""
        manager = ProviderManager()
        
        # Create provider with failing disconnect
        mock_provider = MagicMock()
        mock_provider.disconnect.side_effect = Exception("Disconnect failed")
        
        manager.add_provider('graph', 'failing', mock_provider)
        
        # Remove should not raise exception
        manager.remove_provider('graph', 'failing')
        
        # Provider should still be removed
        assert 'failing' not in manager.providers['graph']
        
    def test_health_check_all_manager(self):
        """Test health checking all managed providers."""
        manager = ProviderManager()
        
        # Add providers with different health states
        healthy_provider = MagicMock()
        healthy_provider.health_check.return_value = {'healthy': True}
        
        unhealthy_provider = MagicMock()
        unhealthy_provider.health_check.side_effect = Exception("Health check failed")
        
        no_health_provider = MagicMock(spec=[])  # No health_check method
        
        manager.add_provider('audio', 'healthy', healthy_provider)
        manager.add_provider('audio', 'unhealthy', unhealthy_provider)
        manager.add_provider('llm', 'no_health', no_health_provider)
        
        results = manager.health_check_all()
        
        assert results['audio']['healthy']['healthy'] is True
        assert results['audio']['unhealthy']['healthy'] is False
        assert 'error' in results['audio']['unhealthy']
        assert 'no_health' not in results['llm']  # Skipped because no health check