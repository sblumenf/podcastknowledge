"""
Comprehensive tests for provider factory edge cases.

This module tests edge cases and error conditions for the provider
factory, including registration conflicts, initialization failures,
and dynamic imports.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Type, Optional
import threading
import concurrent.futures

from src.factories.provider_factory import ProviderFactory, ProviderManager
from src.providers.audio.base import AudioProvider
from src.providers.llm.base import LLMProvider
from src.providers.graph.base import GraphProvider
from src.providers.embeddings.base import EmbeddingProvider
from src.core.exceptions import ProviderError, ConfigurationError


class TestProviderFactoryEdgeCases:
    """Test edge cases for ProviderFactory."""
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset factory state before each test."""
        # Clear any existing provider registrations
        ProviderFactory._default_providers = {
            'audio': {},
            'llm': {},
            'graph': {},
            'embedding': {}
        }
        yield
        # Reset after test
        ProviderFactory._default_providers = {
            'audio': {
                'whisper': 'src.providers.audio.whisper.WhisperProvider',
                'mock': 'src.providers.audio.mock.MockAudioProvider'
            },
            'llm': {
                'gemini': 'src.providers.llm.gemini.GeminiProvider',
                'mock': 'src.providers.llm.mock.MockLLMProvider'
            },
            'graph': {
                'neo4j': 'src.providers.graph.neo4j.Neo4jProvider',
                'memory': 'src.providers.graph.memory.InMemoryGraphProvider'
            },
            'embedding': {
                'sentence_transformer': 'src.providers.embeddings.sentence_transformer.SentenceTransformerProvider',
                'mock': 'src.providers.embeddings.mock.MockEmbeddingProvider'
            }
        }
    
    def test_register_duplicate_provider(self):
        """Test registering a provider that already exists."""
        # Create test provider classes
        class TestProvider1(AudioProvider):
            def transcribe(self, audio_path: str) -> Dict[str, Any]:
                return {}
        
        class TestProvider2(AudioProvider):
            def transcribe(self, audio_path: str) -> Dict[str, Any]:
                return {}
        
        # First registration should succeed
        ProviderFactory.register_provider(
            'audio', 
            'test_provider', 
            TestProvider1,
            version="1.0.0"
        )
        
        # Store the first provider metadata
        first_metadata = ProviderFactory.get_provider_metadata('audio', 'test_provider')
        assert first_metadata['version'] == "1.0.0"
        
        # Second registration should overwrite
        ProviderFactory.register_provider(
            'audio', 
            'test_provider', 
            TestProvider2,
            version="2.0.0"
        )
        
        # Verify it was overwritten
        new_metadata = ProviderFactory.get_provider_metadata('audio', 'test_provider')
        assert new_metadata['version'] == "2.0.0"
        assert new_metadata['class'] == 'TestProvider2'
    
    def test_register_invalid_provider_type(self):
        """Test registering provider with invalid type."""
        with pytest.raises(ValueError, match="Invalid provider type"):
            ProviderFactory.register_provider(
                'invalid_type',
                'test_provider',
                Mock(),
                version="1.0.0"
            )
    
    def test_create_provider_initialization_failure(self):
        """Test provider creation when initialization fails."""
        # Create a provider that fails on init
        class FailingProvider(AudioProvider):
            def __init__(self, config: Dict[str, Any]):
                raise RuntimeError("Initialization failed")
            
            def transcribe(self, audio_path: str) -> Dict[str, Any]:
                pass
        
        # Register the failing provider
        ProviderFactory._default_providers['audio']['failing'] = FailingProvider
        
        # Try to create it
        with pytest.raises(RuntimeError, match="Initialization failed"):
            ProviderFactory.create_audio_provider('failing', {})
    
    def test_create_provider_missing_required_config(self):
        """Test provider creation with missing required config."""
        # Mock a provider that requires specific config
        with patch('src.factories.provider_factory.ProviderFactory._import_provider_class') as mock_import:
            mock_class = Mock()
            mock_instance = mock_class.return_value
            mock_instance.validate_config = Mock(side_effect=ConfigurationError("Missing api_key"))
            mock_import.return_value = mock_class
            
            ProviderFactory._default_providers['llm']['test'] = 'mock.path'
            
            with pytest.raises(ConfigurationError, match="Missing api_key"):
                ProviderFactory.create_llm_provider('test', {})
    
    def test_dynamic_import_module_not_found(self):
        """Test dynamic import when module doesn't exist."""
        ProviderFactory._default_providers['audio']['nonexistent'] = 'nonexistent.module.Provider'
        
        with pytest.raises(ImportError):
            ProviderFactory.create_audio_provider('nonexistent', {})
    
    def test_dynamic_import_class_not_found(self):
        """Test dynamic import when class doesn't exist in module."""
        ProviderFactory._default_providers['audio']['badclass'] = 'src.providers.audio.mock.NonExistentClass'
        
        with pytest.raises(AttributeError):
            ProviderFactory.create_audio_provider('badclass', {})
    
    def test_provider_with_complex_initialization(self):
        """Test provider with complex initialization requirements."""
        class ComplexProvider(GraphProvider):
            def __init__(self, config: Dict[str, Any]):
                super().__init__(config)
                # Simulate complex initialization
                self.connection = self._establish_connection(config)
                self.cache = self._initialize_cache(config)
            
            def _establish_connection(self, config):
                if 'connection_string' not in config:
                    raise ValueError("connection_string required")
                return Mock()
            
            def _initialize_cache(self, config):
                return {}
            
            def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
                return "node_id"
            
            def create_relationship(self, source_id: str, target_id: str, 
                                  rel_type: str, properties: Dict[str, Any]) -> str:
                return "rel_id"
            
            def query(self, cypher: str, parameters: Dict[str, Any]) -> Any:
                return []
            
            def delete_node(self, node_id: str) -> bool:
                return True
            
            def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
                return True
        
        ProviderFactory._default_providers['graph']['complex'] = ComplexProvider
        
        # Should fail without required config
        with pytest.raises(ValueError, match="connection_string required"):
            ProviderFactory.create_graph_provider('complex', {})
        
        # Should succeed with required config
        provider = ProviderFactory.create_graph_provider(
            'complex', 
            {'connection_string': 'test://localhost'}
        )
        assert isinstance(provider, ComplexProvider)
    
    def test_provider_singleton_pattern(self):
        """Test providers that implement singleton pattern."""
        # Use the mock provider which might be singleton
        config = {'test': True}
        
        provider1 = ProviderFactory.create_audio_provider('mock', config)
        provider2 = ProviderFactory.create_audio_provider('mock', config)
        
        # They should be different instances (factory doesn't enforce singleton)
        assert provider1 is not provider2
    
    def test_provider_cleanup_on_error(self):
        """Test that providers clean up resources on initialization error."""
        class CleanupProvider(EmbeddingProvider):
            cleanup_called = False
            
            def __init__(self, config: Dict[str, Any]):
                super().__init__(config)
                self.resource = self._acquire_resource()
                if config.get('fail', False):
                    self._cleanup()
                    raise RuntimeError("Forced failure")
            
            def _acquire_resource(self):
                return Mock()
            
            def _cleanup(self):
                CleanupProvider.cleanup_called = True
                if hasattr(self, 'resource'):
                    self.resource = None
            
            def embed_text(self, text: str) -> Any:
                return [0.1] * 768
            
            def embed_batch(self, texts: list) -> Any:
                return [[0.1] * 768 for _ in texts]
        
        ProviderFactory._default_providers['embedding']['cleanup'] = CleanupProvider
        
        # Reset cleanup flag
        CleanupProvider.cleanup_called = False
        
        # Try to create with failure
        with pytest.raises(RuntimeError, match="Forced failure"):
            ProviderFactory.create_embedding_provider('cleanup', {'fail': True})
        
        # Verify cleanup was called
        assert CleanupProvider.cleanup_called
    
    def test_create_all_provider_types(self):
        """Test creating all provider types with factory methods."""
        # Test audio provider
        audio = ProviderFactory.create_audio_provider('mock', {})
        assert hasattr(audio, 'transcribe')
        
        # Test LLM provider
        llm = ProviderFactory.create_llm_provider('mock', {})
        assert hasattr(llm, 'generate')
        
        # Test graph provider  
        graph = ProviderFactory.create_graph_provider('memory', {})
        assert hasattr(graph, 'create_node')
        
        # Test embedding provider
        embedding = ProviderFactory.create_embedding_provider('mock', {})
        assert hasattr(embedding, 'embed_text')


class TestProviderManagerEdgeCases:
    """Test edge cases for ProviderManager."""
    
    @pytest.fixture
    def manager(self):
        """Create provider manager instance."""
        return ProviderManager()
    
    def test_get_provider_not_initialized(self, manager):
        """Test getting provider that hasn't been initialized."""
        provider = manager.get_provider('audio')
        assert provider is None
    
    def test_add_and_get_provider(self, manager):
        """Test adding and getting a provider."""
        mock_provider = Mock(spec=AudioProvider)
        manager.add_provider('audio', 'test', mock_provider, version="1.0.0")
        
        retrieved = manager.get_provider('audio', 'test')
        assert retrieved == mock_provider
    
    def test_remove_provider(self, manager):
        """Test removing a provider."""
        mock_provider = Mock(spec=AudioProvider)
        manager.add_provider('audio', 'test', mock_provider)
        
        manager.remove_provider('audio', 'test')
        assert manager.get_provider('audio', 'test') is None
    
    def test_list_providers(self, manager):
        """Test listing all providers."""
        # Add some providers
        manager.add_provider('audio', 'test1', Mock())
        manager.add_provider('audio', 'test2', Mock())
        manager.add_provider('llm', 'test3', Mock())
        
        # List should include all types
        providers = manager.get_all_providers()
        assert 'audio' in providers
        assert len(providers['audio']) == 2
        assert 'llm' in providers
        assert len(providers['llm']) == 1
    
    def test_get_provider_metadata(self, manager):
        """Test getting provider metadata."""
        mock_provider = Mock()
        metadata = {
            'version': '1.2.3',
            'author': 'Test Author',
            'description': 'Test provider'
        }
        
        manager.add_provider('audio', 'test', mock_provider, **metadata)
        
        retrieved_metadata = manager.get_provider_metadata('audio', 'test')
        assert retrieved_metadata['version'] == '1.2.3'
        assert retrieved_metadata['author'] == 'Test Author'
    
    def test_concurrent_provider_access(self, manager):
        """Test concurrent access to providers."""
        mock_provider = Mock(spec=AudioProvider)
        manager.add_provider('audio', 'test', mock_provider)
        
        def access_provider():
            return manager.get_provider('audio', 'test')
        
        # Run concurrent access
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(access_provider) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should get the same provider
        assert all(r == mock_provider for r in results)
    
    def test_provider_version_tracking(self, manager):
        """Test provider version tracking."""
        # Add provider with version
        manager.add_provider('llm', 'test', Mock(), version='1.0.0')
        
        # Get version
        version = manager.get_provider_version('llm', 'test')
        assert version == '1.0.0'
        
        # Update to new version
        manager.add_provider('llm', 'test', Mock(), version='2.0.0')
        new_version = manager.get_provider_version('llm', 'test')
        assert new_version == '2.0.0'
    
    def test_invalid_provider_type(self, manager):
        """Test operations with invalid provider type."""
        # Get from invalid type returns None
        assert manager.get_provider('invalid_type') is None
        
        # Remove from invalid type doesn't raise
        manager.remove_provider('invalid_type', 'test')  # Should not raise
    
    def test_list_providers_method(self, manager):
        """Test the get_all_providers method."""
        # Initially empty
        providers = manager.get_all_providers()
        assert all(len(providers[ptype]) == 0 for ptype in providers)
        
        # Add providers
        manager.add_provider('audio', 'provider1', Mock())
        manager.add_provider('audio', 'provider2', Mock())
        
        providers = manager.get_all_providers()
        assert len(providers['audio']) == 2
        assert 'provider1' in providers['audio']
        assert 'provider2' in providers['audio']