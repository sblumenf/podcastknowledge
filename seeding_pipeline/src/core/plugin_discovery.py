"""Plugin discovery system for automatic provider registration."""

from pathlib import Path
from typing import Dict, Type, Any, List, Optional, Callable
import logging
import os

import importlib
import inspect
logger = logging.getLogger(__name__)


def provider_plugin(provider_type: str, name: str, version: str = "1.0.0", 
                   author: str = "Unknown", description: str = ""):
    """Decorator for marking a class as a provider plugin.
    
    Args:
        provider_type: Type of provider ('llm', 'graph', 'embedding')
        name: Name for the provider
        version: Provider version
        author: Provider author
        description: Provider description
        
    Example:
        @provider_plugin('llm', 'gemini', version='1.2.0', author='Google')
        class GeminiProvider(LLMProvider):
            pass
    """
    def decorator(cls: Type) -> Type:
        # Add metadata to the class
        cls._plugin_metadata = {
            'provider_type': provider_type,
            'name': name,
            'version': version,
            'author': author,
            'description': description,
            'module': cls.__module__,
            'class_name': cls.__name__
        }
        cls._is_provider_plugin = True
        return cls
    
    return decorator


class PluginDiscovery:
    """Discovers and loads provider plugins automatically."""
    
    def __init__(self, provider_dirs: Optional[List[str]] = None):
        """Initialize plugin discovery.
        
        Args:
            provider_dirs: List of directories to scan for providers
        """
        self.provider_dirs = provider_dirs or ['src/providers']
        self.discovered_plugins: Dict[str, Dict[str, Type]] = {
            'llm': {},
            'graph': {},
            'embedding': {}
        }
        self.plugin_metadata: Dict[str, Dict[str, Dict[str, Any]]] = {
            'llm': {},
            'graph': {},
            'embedding': {}
        }
    
    def discover_plugins(self) -> Dict[str, Dict[str, Type]]:
        """Scan directories and discover all provider plugins.
        
        Returns:
            Dictionary of discovered plugins organized by type and name
        """
        logger.info(f"Starting plugin discovery in directories: {self.provider_dirs}")
        
        for provider_dir in self.provider_dirs:
            if not os.path.exists(provider_dir):
                logger.warning(f"Provider directory does not exist: {provider_dir}")
                continue
                
            self._scan_directory(provider_dir)
        
        logger.info(f"Plugin discovery complete. Found {self._count_plugins()} plugins")
        return self.discovered_plugins
    
    def _scan_directory(self, directory: str):
        """Scan a directory recursively for provider plugins.
        
        Args:
            directory: Directory path to scan
        """
        for root, dirs, files in os.walk(directory):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    module_path = self._get_module_path(root, file)
                    self._try_import_module(module_path)
    
    def _get_module_path(self, root: str, file: str) -> str:
        """Convert file path to module path.
        
        Args:
            root: Root directory
            file: Python file name
            
        Returns:
            Module import path
        """
        # Remove .py extension
        module_name = file[:-3]
        
        # Convert path to module notation
        path_parts = Path(root).parts
        
        # Find where 'src' starts in the path
        try:
            src_index = path_parts.index('src')
            module_parts = path_parts[src_index:] + (module_name,)
            return '.'.join(module_parts)
        except ValueError:
            # If 'src' not in path, use relative path from current directory
            rel_path = os.path.relpath(root).replace(os.sep, '.')
            return f"{rel_path}.{module_name}"
    
    def _try_import_module(self, module_path: str):
        """Try to import a module and find provider plugins.
        
        Args:
            module_path: Module import path
        """
        try:
            module = importlib.import_module(module_path)
            
            # Scan module for classes with provider plugin decorator
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and hasattr(obj, '_is_provider_plugin'):
                    self._register_plugin(obj)
                    
        except Exception as e:
            # Log at debug level to avoid noise from non-provider modules
            logger.debug(f"Failed to import module {module_path}: {e}")
    
    def _register_plugin(self, plugin_class: Type):
        """Register a discovered plugin.
        
        Args:
            plugin_class: Plugin class with metadata
        """
        metadata = plugin_class._plugin_metadata
        provider_type = metadata['provider_type']
        name = metadata['name']
        
        if provider_type not in self.discovered_plugins:
            logger.warning(f"Invalid provider type '{provider_type}' for plugin {name}")
            return
            
        # Register the plugin
        self.discovered_plugins[provider_type][name] = plugin_class
        self.plugin_metadata[provider_type][name] = metadata
        
        logger.info(f"Discovered {provider_type} provider plugin: {name} "
                   f"(version: {metadata['version']}, author: {metadata['author']})")
    
    def _count_plugins(self) -> int:
        """Count total number of discovered plugins.
        
        Returns:
            Total plugin count
        """
        return sum(len(plugins) for plugins in self.discovered_plugins.values())
    
    def get_plugin(self, provider_type: str, name: str) -> Optional[Type]:
        """Get a specific plugin class.
        
        Args:
            provider_type: Type of provider
            name: Provider name
            
        Returns:
            Plugin class or None if not found
        """
        return self.discovered_plugins.get(provider_type, {}).get(name)
    
    def get_plugin_metadata(self, provider_type: str, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific plugin.
        
        Args:
            provider_type: Type of provider
            name: Provider name
            
        Returns:
            Plugin metadata or None if not found
        """
        return self.plugin_metadata.get(provider_type, {}).get(name)
    
    def discover_providers(self, provider_type: str) -> Dict[str, Type]:
        """Discover providers of a specific type.
        
        Args:
            provider_type: Type of provider to discover
            
        Returns:
            Dictionary of provider name to class mappings
        """
        # First run discovery if not done yet
        if not any(self.discovered_plugins.values()):
            self.discover_plugins()
        
        return self.discovered_plugins.get(provider_type, {})
    
    def get_all_plugins(self) -> Dict[str, Dict[str, Type]]:
        """Get all discovered plugins.
        
        Returns:
            Dictionary of all plugins organized by type and name
        """
        return self.discovered_plugins.copy()
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get metadata for all discovered plugins.
        
        Returns:
            Dictionary of all plugin metadata
        """
        return self.plugin_metadata.copy()


# Global plugin discovery instance
_global_discovery = None


def get_plugin_discovery() -> PluginDiscovery:
    """Get the global plugin discovery instance.
    
    Returns:
        Global PluginDiscovery instance
    """
    global _global_discovery
    if _global_discovery is None:
        _global_discovery = PluginDiscovery()
        _global_discovery.discover_plugins()
    return _global_discovery


def register_provider_plugin(provider_type: str, name: str, plugin_class: Type,
                           version: str = "1.0.0", author: str = "Unknown", 
                           description: str = ""):
    """Manually register a provider plugin.
    
    Args:
        provider_type: Type of provider
        name: Provider name
        plugin_class: Provider class
        version: Provider version
        author: Provider author
        description: Provider description
    """
    discovery = get_plugin_discovery()
    
    # Add metadata to class
    plugin_class._plugin_metadata = {
        'provider_type': provider_type,
        'name': name,
        'version': version,
        'author': author,
        'description': description,
        'module': plugin_class.__module__,
        'class_name': plugin_class.__name__
    }
    plugin_class._is_provider_plugin = True
    
    # Register in discovery
    discovery.discovered_plugins[provider_type][name] = plugin_class
    discovery.plugin_metadata[provider_type][name] = plugin_class._plugin_metadata
    
    logger.info(f"Manually registered {provider_type} provider plugin: {name}")