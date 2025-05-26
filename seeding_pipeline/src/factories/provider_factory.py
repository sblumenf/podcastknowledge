"""Provider factory for creating and managing providers."""

import logging
from typing import Dict, Any, Type, Optional, List
from importlib import import_module

from src.core.interfaces import (
    AudioProvider, LLMProvider, GraphProvider, 
    EmbeddingProvider, HealthCheckable
)
from src.core.exceptions import ConfigurationError, ProviderError


logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating and managing different types of providers."""
    
    # Registry of provider types and their implementations
    _provider_registry: Dict[str, Dict[str, Type]] = {
        'audio': {},
        'llm': {},
        'graph': {},
        'embedding': {}
    }
    
    # Default provider mappings
    _default_providers = {
        'audio': {
            'whisper': 'src.providers.audio.whisper.WhisperAudioProvider',
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
            'openai': 'src.providers.embeddings.sentence_transformer.OpenAIEmbeddingProvider',
            'mock': 'src.providers.embeddings.mock.MockEmbeddingProvider'
        }
    }
    
    @classmethod
    def register_provider(
        cls, 
        provider_type: str, 
        provider_name: str, 
        provider_class: Type
    ) -> None:
        """
        Register a provider implementation.
        
        Args:
            provider_type: Type of provider ('audio', 'llm', 'graph', 'embedding')
            provider_name: Name for the provider implementation
            provider_class: Provider class to register
        """
        if provider_type not in cls._provider_registry:
            raise ValueError(f"Invalid provider type: {provider_type}")
            
        cls._provider_registry[provider_type][provider_name] = provider_class
        logger.info(f"Registered {provider_type} provider: {provider_name}")
        
    @classmethod
    def create_provider(
        cls, 
        provider_type: str, 
        provider_name: str, 
        config: Dict[str, Any]
    ) -> Any:
        """
        Create a provider instance.
        
        Args:
            provider_type: Type of provider to create
            provider_name: Name of the provider implementation
            config: Configuration for the provider
            
        Returns:
            Provider instance
        """
        # Check registry first
        if provider_name in cls._provider_registry.get(provider_type, {}):
            provider_class = cls._provider_registry[provider_type][provider_name]
        else:
            # Try to load from default mappings
            if provider_type not in cls._default_providers:
                raise ValueError(f"Invalid provider type: {provider_type}")
                
            if provider_name not in cls._default_providers[provider_type]:
                raise ValueError(
                    f"Unknown {provider_type} provider: {provider_name}. "
                    f"Available: {list(cls._default_providers[provider_type].keys())}"
                )
                
            # Dynamic import
            module_path = cls._default_providers[provider_type][provider_name]
            provider_class = cls._import_provider_class(module_path)
            
            # Cache in registry
            cls.register_provider(provider_type, provider_name, provider_class)
            
        # Create instance
        try:
            provider = provider_class(config)
            logger.info(f"Created {provider_type} provider: {provider_name}")
            return provider
        except Exception as e:
            raise ProviderError(
                provider_name,
                f"Failed to create {provider_type} provider: {e}"
            )
            
    @classmethod
    def create_audio_provider(cls, provider_name: str, config: Dict[str, Any]) -> AudioProvider:
        """Create an audio provider."""
        return cls.create_provider('audio', provider_name, config)
        
    @classmethod
    def create_llm_provider(cls, provider_name: str, config: Dict[str, Any]) -> LLMProvider:
        """Create an LLM provider."""
        return cls.create_provider('llm', provider_name, config)
        
    @classmethod
    def create_graph_provider(cls, provider_name: str, config: Dict[str, Any]) -> GraphProvider:
        """Create a graph database provider."""
        return cls.create_provider('graph', provider_name, config)
        
    @classmethod
    def create_embedding_provider(cls, provider_name: str, config: Dict[str, Any]) -> EmbeddingProvider:
        """Create an embedding provider."""
        return cls.create_provider('embedding', provider_name, config)
        
    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create all providers from a configuration dictionary.
        
        Args:
            config: Configuration with provider settings
            
        Returns:
            Dictionary of provider instances
        """
        providers = {}
        
        # Create each type of provider if configured
        if 'audio' in config:
            audio_config = config['audio']
            provider_name = audio_config.get('provider', 'whisper')
            providers['audio'] = cls.create_audio_provider(provider_name, audio_config)
            
        if 'llm' in config:
            llm_config = config['llm']
            provider_name = llm_config.get('provider', 'gemini')
            providers['llm'] = cls.create_llm_provider(provider_name, llm_config)
            
        if 'graph' in config:
            graph_config = config['graph']
            provider_name = graph_config.get('provider', 'neo4j')
            providers['graph'] = cls.create_graph_provider(provider_name, graph_config)
            
        if 'embedding' in config:
            embedding_config = config['embedding']
            provider_name = embedding_config.get('provider', 'sentence_transformer')
            providers['embedding'] = cls.create_embedding_provider(provider_name, embedding_config)
            
        return providers
        
    @classmethod
    def _import_provider_class(cls, module_path: str) -> Type:
        """Import a provider class from a module path."""
        try:
            module_name, class_name = module_path.rsplit('.', 1)
            module = import_module(module_name)
            provider_class = getattr(module, class_name)
            return provider_class
        except Exception as e:
            raise ImportError(f"Failed to import provider from {module_path}: {e}")
            
    @classmethod
    def get_available_providers(cls, provider_type: Optional[str] = None) -> Dict[str, List[str]]:
        """Get list of available providers."""
        if provider_type:
            if provider_type not in cls._default_providers:
                raise ValueError(f"Invalid provider type: {provider_type}")
            return {provider_type: list(cls._default_providers[provider_type].keys())}
        else:
            return {
                ptype: list(providers.keys())
                for ptype, providers in cls._default_providers.items()
            }
            
    @classmethod
    def health_check_all(cls, providers: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Run health checks on all providers.
        
        Args:
            providers: Dictionary of provider instances
            
        Returns:
            Dictionary of health check results
        """
        results = {}
        
        for name, provider in providers.items():
            if isinstance(provider, HealthCheckable):
                try:
                    results[name] = provider.health_check()
                except Exception as e:
                    results[name] = {
                        'healthy': False,
                        'error': str(e),
                        'provider': provider.__class__.__name__
                    }
            else:
                results[name] = {
                    'healthy': 'unknown',
                    'message': 'Provider does not support health checks'
                }
                
        return results


class ProviderManager:
    """Manager for provider lifecycle and versioning."""
    
    def __init__(self):
        """Initialize provider manager."""
        self.providers: Dict[str, Dict[str, Any]] = {
            'audio': {},
            'llm': {},
            'graph': {},
            'embedding': {}
        }
        self.versions: Dict[str, Dict[str, str]] = {}
        
    def add_provider(
        self, 
        provider_type: str, 
        name: str, 
        provider: Any, 
        version: Optional[str] = None
    ) -> None:
        """Add a provider instance to the manager."""
        if provider_type not in self.providers:
            raise ValueError(f"Invalid provider type: {provider_type}")
            
        self.providers[provider_type][name] = provider
        
        if version:
            if provider_type not in self.versions:
                self.versions[provider_type] = {}
            self.versions[provider_type][name] = version
            
        logger.info(f"Added {provider_type} provider '{name}' (version: {version or 'unknown'})")
        
    def get_provider(self, provider_type: str, name: Optional[str] = None) -> Any:
        """Get a provider instance."""
        if provider_type not in self.providers:
            raise ValueError(f"Invalid provider type: {provider_type}")
            
        type_providers = self.providers[provider_type]
        
        if name:
            if name not in type_providers:
                raise KeyError(f"No {provider_type} provider named '{name}'")
            return type_providers[name]
        else:
            # Return first available provider of this type
            if not type_providers:
                raise KeyError(f"No {provider_type} providers available")
            return next(iter(type_providers.values()))
            
    def remove_provider(self, provider_type: str, name: str) -> None:
        """Remove a provider from the manager."""
        if provider_type in self.providers and name in self.providers[provider_type]:
            provider = self.providers[provider_type].pop(name)
            
            # Clean up if provider has disconnect method
            if hasattr(provider, 'disconnect'):
                try:
                    provider.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting provider {name}: {e}")
                    
            # Remove version info
            if provider_type in self.versions and name in self.versions[provider_type]:
                self.versions[provider_type].pop(name)
                
            logger.info(f"Removed {provider_type} provider '{name}'")
            
    def get_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all providers organized by type."""
        return self.providers.copy()
        
    def health_check_all(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Run health checks on all managed providers."""
        results = {}
        
        for provider_type, type_providers in self.providers.items():
            results[provider_type] = {}
            
            for name, provider in type_providers.items():
                if isinstance(provider, HealthCheckable):
                    try:
                        results[provider_type][name] = provider.health_check()
                    except Exception as e:
                        results[provider_type][name] = {
                            'healthy': False,
                            'error': str(e)
                        }
                        
        return results