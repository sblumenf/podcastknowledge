"""Provider factory for creating and managing providers."""

import logging
import os
import yaml
from datetime import datetime
from typing import Dict, Any, Type, Optional, List, Tuple
from importlib import import_module

from src.core.interfaces import (
    AudioProvider, LLMProvider, GraphProvider, 
    EmbeddingProvider, HealthCheckable
)
from src.core.exceptions import ConfigurationError, ProviderError
from src.core.plugin_discovery import get_plugin_discovery, PluginDiscovery


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
    
    # Provider metadata registry (author, version, description)
    _provider_metadata: Dict[str, Dict[str, Dict[str, Any]]] = {
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
            'schemaless': 'src.providers.graph.schemaless_neo4j.SchemalessNeo4jProvider',
            'compatible': 'src.providers.graph.compatible_neo4j.CompatibleNeo4jProvider',
            'memory': 'src.providers.graph.memory.InMemoryGraphProvider'
        },
        'embedding': {
            'sentence_transformer': 'src.providers.embeddings.sentence_transformer.SentenceTransformerProvider',
            'openai': 'src.providers.embeddings.sentence_transformer.OpenAIEmbeddingProvider',
            'mock': 'src.providers.embeddings.mock.MockEmbeddingProvider'
        }
    }
    
    # Configuration loaded from providers.yml
    _config_providers: Optional[Dict[str, Any]] = None
    _config_loaded: bool = False
    
    # Plugin discovery instance
    _plugin_discovery: Optional[PluginDiscovery] = None
    
    @classmethod
    def _load_config(cls):
        """Load provider configuration from providers.yml if it exists."""
        if cls._config_loaded:
            return
            
        config_path = os.path.join('config', 'providers.yml')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    cls._config_providers = yaml.safe_load(f)
                logger.info(f"Loaded provider configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load providers.yml: {e}")
                cls._config_providers = None
        else:
            logger.debug(f"No providers.yml found at {config_path}")
            
        cls._config_loaded = True
    
    @classmethod
    def _get_plugin_discovery(cls) -> PluginDiscovery:
        """Get or initialize the plugin discovery instance."""
        if cls._plugin_discovery is None:
            cls._plugin_discovery = get_plugin_discovery()
        return cls._plugin_discovery
    
    @classmethod
    def register_provider(
        cls, 
        provider_type: str, 
        provider_name: str, 
        provider_class: Type,
        version: str = "1.0.0",
        author: str = "Unknown",
        description: str = ""
    ) -> None:
        """
        Register a provider implementation with metadata.
        
        Args:
            provider_type: Type of provider ('audio', 'llm', 'graph', 'embedding')
            provider_name: Name for the provider implementation
            provider_class: Provider class to register
            version: Provider version
            author: Provider author
            description: Provider description
        """
        if provider_type not in cls._provider_registry:
            raise ValueError(f"Invalid provider type: {provider_type}")
            
        cls._provider_registry[provider_type][provider_name] = provider_class
        
        # Store metadata
        cls._provider_metadata[provider_type][provider_name] = {
            'version': version,
            'author': author,
            'description': description,
            'class': provider_class.__name__,
            'module': provider_class.__module__
        }
        
        logger.info(f"Registered {provider_type} provider: {provider_name} (v{version})")
        
    @classmethod
    def create_provider(
        cls, 
        provider_type: str, 
        provider_name: str, 
        config: Dict[str, Any],
        **kwargs
    ) -> Any:
        """
        Create a provider instance.
        
        Args:
            provider_type: Type of provider to create
            provider_name: Name of the provider implementation
            config: Configuration for the provider
            **kwargs: Additional arguments passed to specific provider types
            
        Returns:
            Provider instance
        """
        # Load configuration if not already loaded
        cls._load_config()
        
        provider_class = None
        provider_source = None
        
        # 1. Check configuration from providers.yml
        if cls._config_providers:
            provider_config = cls._config_providers.get('providers', {}).get(provider_type, {})
            available = provider_config.get('available', {})
            
            if provider_name in available:
                provider_info = available[provider_name]
                try:
                    module_path = f"{provider_info['module']}.{provider_info['class']}"
                    provider_class = cls._import_provider_class(module_path)
                    provider_source = 'config'
                    logger.info(f"Loaded {provider_type} provider '{provider_name}' from config")
                except Exception as e:
                    logger.warning(f"Failed to load provider from config: {e}")
        
        # 2. Check plugin discovery
        if provider_class is None:
            discovery = cls._get_plugin_discovery()
            plugin_class = discovery.get_plugin(provider_type, provider_name)
            if plugin_class:
                provider_class = plugin_class
                provider_source = 'plugin'
                
                # Get and store metadata from plugin
                metadata = discovery.get_plugin_metadata(provider_type, provider_name)
                if metadata:
                    cls._provider_metadata[provider_type][provider_name] = metadata
                    
                logger.info(f"Loaded {provider_type} provider '{provider_name}' from plugin discovery")
        
        # 3. Check registry
        if provider_class is None and provider_name in cls._provider_registry.get(provider_type, {}):
            provider_class = cls._provider_registry[provider_type][provider_name]
            provider_source = 'registry'
        
        # 4. Try default providers
        if provider_class is None:
            if provider_type not in cls._default_providers:
                raise ValueError(f"Invalid provider type: {provider_type}")
                
            if provider_name not in cls._default_providers[provider_type]:
                # Show migration warning if using deprecated name
                cls._show_migration_warning(provider_type, provider_name)
                
                raise ValueError(
                    f"Unknown {provider_type} provider: {provider_name}. "
                    f"Available: {list(cls._default_providers[provider_type].keys())}"
                )
                
            # Dynamic import
            module_path = cls._default_providers[provider_type][provider_name]
            provider_class = cls._import_provider_class(module_path)
            provider_source = 'default'
            
            # Cache in registry
            cls.register_provider(provider_type, provider_name, provider_class)
            
        # Create instance
        try:
            # Pass kwargs for specific provider types (e.g., use_large_context for LLM)
            if kwargs:
                provider = provider_class(config, **kwargs)
            else:
                provider = provider_class(config)
                
            logger.info(f"Created {provider_type} provider: {provider_name} (source: {provider_source})")
            return provider
        except Exception as e:
            raise ProviderError(
                provider_name,
                f"Failed to create {provider_type} provider: {e}"
            )
            
    @classmethod
    def _show_migration_warning(cls, provider_type: str, provider_name: str):
        """Show migration warning for deprecated provider names."""
        # Define deprecated provider mappings
        deprecated_mappings = {
            'embedding': {
                'embeddings': 'sentence_transformer',
                'openai_embeddings': 'openai'
            }
        }
        
        if provider_type in deprecated_mappings:
            type_mappings = deprecated_mappings[provider_type]
            if provider_name in type_mappings:
                new_name = type_mappings[provider_name]
                logger.warning(
                    f"Provider name '{provider_name}' is deprecated. "
                    f"Please use '{new_name}' instead. "
                    f"Consider updating your configuration or creating a providers.yml file."
                )
    
    @classmethod
    def get_provider_metadata(cls, provider_type: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific provider.
        
        Args:
            provider_type: Type of provider
            provider_name: Provider name
            
        Returns:
            Provider metadata or None if not found
        """
        return cls._provider_metadata.get(provider_type, {}).get(provider_name)
    
    @classmethod
    def get_all_provider_metadata(cls) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get metadata for all registered providers.
        
        Returns:
            Dictionary of all provider metadata organized by type and name
        """
        # Include metadata from plugin discovery
        discovery = cls._get_plugin_discovery()
        plugin_metadata = discovery.get_all_metadata()
        
        # Merge with registered metadata
        all_metadata = {}
        for provider_type in ['audio', 'llm', 'graph', 'embedding']:
            all_metadata[provider_type] = {}
            
            # Add registered metadata
            all_metadata[provider_type].update(cls._provider_metadata.get(provider_type, {}))
            
            # Add plugin metadata
            all_metadata[provider_type].update(plugin_metadata.get(provider_type, {}))
            
        return all_metadata
    
    @classmethod
    def create_audio_provider(cls, provider_name: str, config: Dict[str, Any]) -> AudioProvider:
        """Create an audio provider."""
        return cls.create_provider('audio', provider_name, config)
        
    @classmethod
    def create_llm_provider(cls, provider_name: str, config: Dict[str, Any], **kwargs) -> LLMProvider:
        """Create an LLM provider."""
        return cls.create_provider('llm', provider_name, config, **kwargs)
        
    @classmethod
    def create_graph_provider(cls, provider_name: str, config: Dict[str, Any]) -> GraphProvider:
        """Create a graph database provider."""
        # Override provider_name based on config
        if config.get('use_schemaless_extraction', False):
            if provider_name == 'neo4j':
                provider_name = 'schemaless'
                logger.info("Config has use_schemaless_extraction=True, using schemaless provider")
        
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
        self.metadata: Dict[str, Dict[str, Dict[str, Any]]] = {
            'audio': {},
            'llm': {},
            'graph': {},
            'embedding': {}
        }
        
    def add_provider(
        self, 
        provider_type: str, 
        name: str, 
        provider: Any, 
        version: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """Add a provider instance to the manager with metadata.
        
        Args:
            provider_type: Type of provider
            name: Provider name
            provider: Provider instance
            version: Provider version
            author: Provider author
            description: Provider description
        """
        if provider_type not in self.providers:
            raise ValueError(f"Invalid provider type: {provider_type}")
            
        self.providers[provider_type][name] = provider
        
        # Store metadata
        metadata = {
            'version': version or '1.0.0',
            'author': author or 'Unknown',
            'description': description or '',
            'class': provider.__class__.__name__,
            'module': provider.__class__.__module__,
            'added_at': datetime.now().isoformat()
        }
        
        # Try to get metadata from factory if not provided
        if not version and not author and not description:
            factory_metadata = ProviderFactory.get_provider_metadata(provider_type, name)
            if factory_metadata:
                metadata.update(factory_metadata)
        
        self.metadata[provider_type][name] = metadata
            
        logger.info(f"Added {provider_type} provider '{name}' (version: {metadata['version']})")
        
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
            
    def get_provider_metadata(self, provider_type: str, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific provider.
        
        Args:
            provider_type: Type of provider
            name: Provider name
            
        Returns:
            Provider metadata or None if not found
        """
        return self.metadata.get(provider_type, {}).get(name)
    
    def get_provider_version(self, provider_type: str, name: str) -> Optional[str]:
        """Get version for a specific provider.
        
        Args:
            provider_type: Type of provider
            name: Provider name
            
        Returns:
            Provider version or None if not found
        """
        metadata = self.get_provider_metadata(provider_type, name)
        return metadata.get('version') if metadata else None
    
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
                    
            # Remove metadata
            if provider_type in self.metadata and name in self.metadata[provider_type]:
                self.metadata[provider_type].pop(name)
                
            logger.info(f"Removed {provider_type} provider '{name}'")
            
    def get_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all providers organized by type."""
        return self.providers.copy()
    
    def get_all_providers_with_metadata(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get all providers with their metadata.
        
        Returns:
            Dictionary with structure: {provider_type: {name: {'instance': provider, 'metadata': {...}}}}
        """
        result = {}
        for provider_type in self.providers:
            result[provider_type] = {}
            for name, provider in self.providers[provider_type].items():
                result[provider_type][name] = {
                    'instance': provider,
                    'metadata': self.metadata.get(provider_type, {}).get(name, {})
                }
        return result
        
    def health_check_all(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Run health checks on all managed providers."""
        results = {}
        
        for provider_type, type_providers in self.providers.items():
            results[provider_type] = {}
            
            for name, provider in type_providers.items():
                if isinstance(provider, HealthCheckable):
                    try:
                        health_result = provider.health_check()
                        # Add version info to health check
                        metadata = self.get_provider_metadata(provider_type, name)
                        if metadata:
                            health_result['version'] = metadata.get('version', 'unknown')
                        results[provider_type][name] = health_result
                    except Exception as e:
                        results[provider_type][name] = {
                            'healthy': False,
                            'error': str(e)
                        }
                        
        return results