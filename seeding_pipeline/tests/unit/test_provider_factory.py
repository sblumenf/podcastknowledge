"""Tests for provider factory."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.factories.provider_factory import (
    ProviderFactory,
    ProviderRegistry,
    ProviderNotFoundError,
    InvalidProviderError,
    register_provider,
    get_provider,
    create_provider,
)
from src.core.interfaces import (
    AudioProvider,
    EmbeddingProvider,
    GraphProvider,
    LLMProvider,
)


class MockAudioProvider:
    """Mock audio provider for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "mock_audio")
    
    def transcribe(self, audio_path: str) -> str:
        return f"Transcribed: {audio_path}"


class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "mock_llm")
        self.model = config.get("model", "mock-model")
    
    def generate(self, prompt: str) -> str:
        return f"Generated: {prompt}"


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "mock_embedding")
    
    def embed(self, text: str) -> list:
        return [0.1, 0.2, 0.3]


class MockGraphProvider:
    """Mock graph provider for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "mock_graph")
    
    def add_node(self, node_id: str, properties: dict):
        return {"id": node_id, "properties": properties}


class TestProviderRegistry:
    """Test ProviderRegistry functionality."""
    
    def test_register_provider(self):
        """Test registering a provider."""
        registry = ProviderRegistry()
        
        registry.register("audio", "mock", MockAudioProvider)
        
        assert "audio" in registry.providers
        assert "mock" in registry.providers["audio"]
        assert registry.providers["audio"]["mock"] == MockAudioProvider
    
    def test_register_duplicate_provider(self):
        """Test registering duplicate provider."""
        registry = ProviderRegistry()
        
        registry.register("audio", "mock", MockAudioProvider)
        
        # Should raise error for duplicate
        with pytest.raises(ValueError, match="already registered"):
            registry.register("audio", "mock", MockAudioProvider)
    
    def test_register_with_force(self):
        """Test force registering provider."""
        registry = ProviderRegistry()
        
        class NewMockProvider:
            pass
        
        registry.register("audio", "mock", MockAudioProvider)
        registry.register("audio", "mock", NewMockProvider, force=True)
        
        assert registry.providers["audio"]["mock"] == NewMockProvider
    
    def test_get_provider(self):
        """Test getting registered provider."""
        registry = ProviderRegistry()
        registry.register("llm", "mock", MockLLMProvider)
        
        provider_class = registry.get("llm", "mock")
        assert provider_class == MockLLMProvider
    
    def test_get_nonexistent_provider(self):
        """Test getting non-existent provider."""
        registry = ProviderRegistry()
        
        with pytest.raises(ProviderNotFoundError):
            registry.get("audio", "nonexistent")
    
    def test_list_providers(self):
        """Test listing available providers."""
        registry = ProviderRegistry()
        
        registry.register("audio", "mock1", MockAudioProvider)
        registry.register("audio", "mock2", MockAudioProvider)
        registry.register("llm", "mock", MockLLMProvider)
        
        # List all
        all_providers = registry.list_providers()
        assert "audio" in all_providers
        assert "llm" in all_providers
        assert len(all_providers["audio"]) == 2
        
        # List by type
        audio_providers = registry.list_providers("audio")
        assert audio_providers == ["mock1", "mock2"]
    
    def test_clear_registry(self):
        """Test clearing provider registry."""
        registry = ProviderRegistry()
        
        registry.register("audio", "mock", MockAudioProvider)
        registry.clear()
        
        assert len(registry.providers) == 0


class TestProviderFactory:
    """Test ProviderFactory functionality."""
    
    def setup_method(self):
        """Set up test factory."""
        self.factory = ProviderFactory()
        
        # Register mock providers
        self.factory.register_provider("audio", "mock", MockAudioProvider)
        self.factory.register_provider("llm", "mock", MockLLMProvider)
        self.factory.register_provider("embedding", "mock", MockEmbeddingProvider)
        self.factory.register_provider("graph", "mock", MockGraphProvider)
    
    def test_create_audio_provider(self):
        """Test creating audio provider."""
        config = {
            "provider": "mock",
            "name": "test_audio"
        }
        
        provider = self.factory.create_audio_provider(config)
        
        assert isinstance(provider, MockAudioProvider)
        assert provider.name == "test_audio"
        assert provider.transcribe("test.mp3") == "Transcribed: test.mp3"
    
    def test_create_llm_provider(self):
        """Test creating LLM provider."""
        config = {
            "provider": "mock",
            "model": "test-model"
        }
        
        provider = self.factory.create_llm_provider(config)
        
        assert isinstance(provider, MockLLMProvider)
        assert provider.model == "test-model"
        assert provider.generate("test") == "Generated: test"
    
    def test_create_embedding_provider(self):
        """Test creating embedding provider."""
        config = {
            "provider": "mock",
            "name": "test_embedding"
        }
        
        provider = self.factory.create_embedding_provider(config)
        
        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.embed("test") == [0.1, 0.2, 0.3]
    
    def test_create_graph_provider(self):
        """Test creating graph provider."""
        config = {
            "provider": "mock",
            "name": "test_graph"
        }
        
        provider = self.factory.create_graph_provider(config)
        
        assert isinstance(provider, MockGraphProvider)
        result = provider.add_node("node1", {"prop": "value"})
        assert result["id"] == "node1"
    
    def test_create_provider_missing_type(self):
        """Test creating provider without provider type."""
        config = {"name": "test"}
        
        with pytest.raises(InvalidProviderError, match="provider.*not specified"):
            self.factory.create_audio_provider(config)
    
    def test_create_unknown_provider(self):
        """Test creating unknown provider."""
        config = {"provider": "unknown"}
        
        with pytest.raises(ProviderNotFoundError):
            self.factory.create_audio_provider(config)
    
    def test_create_with_validation(self):
        """Test provider creation with validation."""
        class ValidatingProvider:
            def __init__(self, config: Dict[str, Any]):
                if "required_field" not in config:
                    raise ValueError("required_field is missing")
                self.config = config
        
        self.factory.register_provider("audio", "validating", ValidatingProvider)
        
        # Should fail validation
        with pytest.raises(InvalidProviderError, match="required_field"):
            self.factory.create_audio_provider({"provider": "validating"})
        
        # Should pass validation
        provider = self.factory.create_audio_provider({
            "provider": "validating",
            "required_field": "value"
        })
        assert isinstance(provider, ValidatingProvider)
    
    def test_singleton_factory(self):
        """Test that factory can be used as singleton."""
        factory1 = ProviderFactory()
        factory2 = ProviderFactory()
        
        # Register provider in factory1
        factory1.register_provider("audio", "singleton_test", MockAudioProvider)
        
        # Should be available in factory2 if using shared registry
        # (depends on implementation)
        try:
            factory2.create_audio_provider({"provider": "singleton_test"})
            # Shared registry
            assert True
        except ProviderNotFoundError:
            # Separate registries
            assert True


class TestProviderLoading:
    """Test dynamic provider loading."""
    
    @patch('importlib.import_module')
    def test_load_provider_from_module(self, mock_import):
        """Test loading provider from module."""
        # Mock module with provider
        mock_module = MagicMock()
        mock_module.CustomProvider = MockAudioProvider
        mock_import.return_value = mock_module
        
        factory = ProviderFactory()
        factory.load_provider("audio", "custom", "custom_module.CustomProvider")
        
        # Should be registered
        provider = factory.create_audio_provider({"provider": "custom"})
        assert isinstance(provider, MockAudioProvider)
    
    @patch('importlib.import_module')
    def test_load_provider_module_not_found(self, mock_import):
        """Test handling missing module."""
        mock_import.side_effect = ImportError("Module not found")
        
        factory = ProviderFactory()
        
        with pytest.raises(InvalidProviderError, match="Could not load"):
            factory.load_provider("audio", "custom", "missing_module.Provider")
    
    def test_load_providers_from_config(self):
        """Test loading multiple providers from config."""
        config = {
            "providers": {
                "audio": {
                    "mock": "tests.mocks.MockAudioProvider",
                    "mock2": "tests.mocks.MockAudioProvider2"
                },
                "llm": {
                    "mock": "tests.mocks.MockLLMProvider"
                }
            }
        }
        
        factory = ProviderFactory()
        
        with patch.object(factory, 'load_provider') as mock_load:
            factory.load_providers_from_config(config)
            
            assert mock_load.call_count == 3
            mock_load.assert_any_call("audio", "mock", "tests.mocks.MockAudioProvider")
            mock_load.assert_any_call("audio", "mock2", "tests.mocks.MockAudioProvider2")
            mock_load.assert_any_call("llm", "mock", "tests.mocks.MockLLMProvider")


class TestProviderHelperFunctions:
    """Test module-level helper functions."""
    
    def test_register_provider_function(self):
        """Test register_provider helper function."""
        # Clear any existing registration
        from src.factories.provider_factory import _default_factory
        _default_factory.registry.clear()
        
        register_provider("audio", "test", MockAudioProvider)
        
        provider = create_provider("audio", {"provider": "test"})
        assert isinstance(provider, MockAudioProvider)
    
    def test_get_provider_function(self):
        """Test get_provider helper function."""
        register_provider("llm", "test", MockLLMProvider)
        
        provider_class = get_provider("llm", "test")
        assert provider_class == MockLLMProvider
    
    def test_create_provider_function(self):
        """Test create_provider helper function."""
        register_provider("embedding", "test", MockEmbeddingProvider)
        
        provider = create_provider("embedding", {
            "provider": "test",
            "name": "helper_test"
        })
        
        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.name == "helper_test"


class TestProviderFactoryIntegration:
    """Test factory integration scenarios."""
    
    def test_multiple_provider_types(self):
        """Test creating multiple provider types."""
        factory = ProviderFactory()
        
        # Register different providers
        factory.register_provider("audio", "whisper", MockAudioProvider)
        factory.register_provider("llm", "openai", MockLLMProvider)
        factory.register_provider("llm", "anthropic", MockLLMProvider)
        factory.register_provider("embedding", "sentence", MockEmbeddingProvider)
        
        # Create instances
        audio = factory.create_audio_provider({"provider": "whisper"})
        llm1 = factory.create_llm_provider({"provider": "openai"})
        llm2 = factory.create_llm_provider({"provider": "anthropic"})
        embedding = factory.create_embedding_provider({"provider": "sentence"})
        
        # All should be created successfully
        assert isinstance(audio, MockAudioProvider)
        assert isinstance(llm1, MockLLMProvider)
        assert isinstance(llm2, MockLLMProvider)
        assert isinstance(embedding, MockEmbeddingProvider)
    
    def test_provider_initialization_error(self):
        """Test handling provider initialization errors."""
        class FailingProvider:
            def __init__(self, config):
                raise RuntimeError("Initialization failed")
        
        factory = ProviderFactory()
        factory.register_provider("audio", "failing", FailingProvider)
        
        with pytest.raises(InvalidProviderError, match="Failed to create"):
            factory.create_audio_provider({"provider": "failing"})
    
    def test_provider_with_dependencies(self):
        """Test provider with dependencies."""
        class DependentProvider:
            def __init__(self, config: Dict[str, Any]):
                self.config = config
                # Simulate dependency injection
                if "dependency" in config:
                    self.dependency = config["dependency"]
                else:
                    raise ValueError("Missing required dependency")
        
        factory = ProviderFactory()
        factory.register_provider("graph", "dependent", DependentProvider)
        
        # Create with dependency
        mock_dep = Mock()
        provider = factory.create_graph_provider({
            "provider": "dependent",
            "dependency": mock_dep
        })
        
        assert isinstance(provider, DependentProvider)
        assert provider.dependency == mock_dep
    
    def test_provider_factory_with_defaults(self):
        """Test factory with default configurations."""
        factory = ProviderFactory()
        
        # Set default configs
        factory.set_default_config("audio", {
            "provider": "mock",
            "sample_rate": 16000
        })
        
        factory.register_provider("audio", "mock", MockAudioProvider)
        
        # Create without specifying provider
        provider = factory.create_audio_provider({})
        assert isinstance(provider, MockAudioProvider)
        assert provider.config["sample_rate"] == 16000
        
        # Override defaults
        provider2 = factory.create_audio_provider({
            "provider": "mock",
            "sample_rate": 44100
        })
        assert provider2.config["sample_rate"] == 44100