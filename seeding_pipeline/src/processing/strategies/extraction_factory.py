"""
Extraction strategy factory for creating appropriate extraction strategies.

This factory creates the correct extraction strategy based on configuration,
supporting fixed schema, schemaless, and dual mode extraction.
"""

import logging
from typing import Dict, Any, Optional, Union

from src.processing.strategies import ExtractionStrategy
from src.processing.strategies.fixed_schema_strategy import FixedSchemaStrategy
from src.processing.strategies.schemaless_strategy import SchemalessStrategy
from src.processing.strategies.dual_mode_strategy import DualModeStrategy
from src.core.interfaces import LLMProvider
from src.providers.graph.base import GraphProvider
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ExtractionFactory:
    """Factory for creating extraction strategies based on configuration."""
    
    # Strategy mode constants
    FIXED_MODE = 'fixed'
    SCHEMALESS_MODE = 'schemaless'
    DUAL_MODE = 'dual'
    MIGRATION_MODE = 'migration'  # Alias for dual mode
    
    @classmethod
    def create_strategy(
        cls,
        mode: str,
        llm_provider: Optional[LLMProvider] = None,
        graph_provider: Optional[GraphProvider] = None,
        podcast_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ExtractionStrategy:
        """
        Create an extraction strategy based on the specified mode.
        
        Args:
            mode: Extraction mode ('fixed', 'schemaless', 'dual', 'migration')
            llm_provider: LLM provider (required for fixed and dual modes)
            graph_provider: Graph provider (required for schemaless and dual modes)
            podcast_id: Podcast ID (required for schemaless and dual modes)
            episode_id: Episode ID (required for schemaless and dual modes)
            config: Additional configuration options
            
        Returns:
            Configured extraction strategy
            
        Raises:
            ConfigurationError: If required parameters are missing
        """
        config = config or {}
        
        # Normalize mode
        mode = mode.lower()
        if mode == cls.MIGRATION_MODE:
            mode = cls.DUAL_MODE  # Migration is an alias for dual
            
        logger.info(f"Creating extraction strategy for mode: {mode}")
        
        if mode == cls.FIXED_MODE:
            return cls._create_fixed_strategy(llm_provider, config)
        elif mode == cls.SCHEMALESS_MODE:
            return cls._create_schemaless_strategy(
                graph_provider, podcast_id, episode_id, config
            )
        elif mode == cls.DUAL_MODE:
            return cls._create_dual_strategy(
                llm_provider, graph_provider, podcast_id, episode_id, config
            )
        else:
            raise ConfigurationError(
                f"Unknown extraction mode: {mode}. "
                f"Valid modes: {cls.FIXED_MODE}, {cls.SCHEMALESS_MODE}, {cls.DUAL_MODE}"
            )
    
    @classmethod
    def _create_fixed_strategy(
        cls,
        llm_provider: Optional[LLMProvider],
        config: Dict[str, Any]
    ) -> FixedSchemaStrategy:
        """Create fixed schema strategy."""
        if not llm_provider:
            raise ConfigurationError(
                "LLM provider is required for fixed schema extraction"
            )
            
        return FixedSchemaStrategy(
            llm_provider=llm_provider,
            use_large_context=config.get('use_large_context', True),
            max_retries=config.get('max_retries', 3),
            enable_cache=config.get('enable_cache', True)
        )
    
    @classmethod
    def _create_schemaless_strategy(
        cls,
        graph_provider: Optional[GraphProvider],
        podcast_id: Optional[str],
        episode_id: Optional[str],
        config: Dict[str, Any]
    ) -> SchemalessStrategy:
        """Create schemaless strategy."""
        if not graph_provider:
            raise ConfigurationError(
                "Graph provider is required for schemaless extraction"
            )
        if not podcast_id or not episode_id:
            raise ConfigurationError(
                "Podcast ID and Episode ID are required for schemaless extraction"
            )
            
        return SchemalessStrategy(
            graph_provider=graph_provider,
            podcast_id=podcast_id,
            episode_id=episode_id
        )
    
    @classmethod
    def _create_dual_strategy(
        cls,
        llm_provider: Optional[LLMProvider],
        graph_provider: Optional[GraphProvider],
        podcast_id: Optional[str],
        episode_id: Optional[str],
        config: Dict[str, Any]
    ) -> DualModeStrategy:
        """Create dual mode strategy."""
        if not llm_provider:
            raise ConfigurationError(
                "LLM provider is required for dual mode extraction"
            )
        if not graph_provider:
            raise ConfigurationError(
                "Graph provider is required for dual mode extraction"
            )
        if not podcast_id or not episode_id:
            raise ConfigurationError(
                "Podcast ID and Episode ID are required for dual mode extraction"
            )
            
        return DualModeStrategy(
            llm_provider=llm_provider,
            graph_provider=graph_provider,
            podcast_id=podcast_id,
            episode_id=episode_id,
            use_large_context=config.get('use_large_context', True),
            enable_cache=config.get('enable_cache', True)
        )
    
    @classmethod
    def create_from_config(
        cls,
        config: Dict[str, Any],
        llm_provider: Optional[LLMProvider] = None,
        graph_provider: Optional[GraphProvider] = None
    ) -> ExtractionStrategy:
        """
        Create extraction strategy from configuration dictionary.
        
        Args:
            config: Configuration containing extraction settings
            llm_provider: LLM provider instance
            graph_provider: Graph provider instance
            
        Returns:
            Configured extraction strategy
        """
        # Determine extraction mode from config
        mode = cls._determine_mode_from_config(config)
        
        # Extract required IDs from config
        podcast_id = config.get('podcast', {}).get('id')
        episode_id = config.get('episode', {}).get('id')
        
        # Get extraction config
        extraction_config = config.get('extraction', {})
        
        return cls.create_strategy(
            mode=mode,
            llm_provider=llm_provider,
            graph_provider=graph_provider,
            podcast_id=podcast_id,
            episode_id=episode_id,
            config=extraction_config
        )
    
    @classmethod
    def _determine_mode_from_config(cls, config: Dict[str, Any]) -> str:
        """
        Determine extraction mode from configuration.
        
        Priority order:
        1. Explicit extraction_mode setting
        2. Feature flags (ENABLE_SCHEMALESS_EXTRACTION, MIGRATION_MODE)
        3. Default to fixed
        """
        # Check explicit mode
        extraction_config = config.get('extraction', {})
        if 'mode' in extraction_config:
            return extraction_config['mode']
            
        # Check feature flags
        if config.get('MIGRATION_MODE', False):
            return cls.DUAL_MODE
        elif config.get('ENABLE_SCHEMALESS_EXTRACTION', False):
            return cls.SCHEMALESS_MODE
        else:
            return cls.FIXED_MODE
    
    @classmethod
    def supports_runtime_switching(cls) -> bool:
        """
        Check if runtime strategy switching is supported.
        
        Returns:
            True - runtime switching is supported
        """
        return True
    
    @classmethod
    def switch_strategy(
        cls,
        current_strategy: ExtractionStrategy,
        new_mode: str,
        **kwargs
    ) -> ExtractionStrategy:
        """
        Switch to a different extraction strategy at runtime.
        
        Args:
            current_strategy: Current extraction strategy
            new_mode: New extraction mode to switch to
            **kwargs: Additional parameters for the new strategy
            
        Returns:
            New extraction strategy instance
        """
        logger.info(f"Switching extraction strategy from {current_strategy.get_extraction_mode()} to {new_mode}")
        
        # Extract parameters from current strategy if possible
        llm_provider = kwargs.get('llm_provider')
        graph_provider = kwargs.get('graph_provider')
        podcast_id = kwargs.get('podcast_id')
        episode_id = kwargs.get('episode_id')
        config = kwargs.get('config', {})
        
        # Try to extract from current strategy
        if hasattr(current_strategy, 'llm_provider'):
            llm_provider = llm_provider or current_strategy.llm_provider
        if hasattr(current_strategy, 'graph_provider'):
            graph_provider = graph_provider or current_strategy.graph_provider
        if hasattr(current_strategy, 'podcast_id'):
            podcast_id = podcast_id or current_strategy.podcast_id
        if hasattr(current_strategy, 'episode_id'):
            episode_id = episode_id or current_strategy.episode_id
            
        # Create new strategy
        return cls.create_strategy(
            mode=new_mode,
            llm_provider=llm_provider,
            graph_provider=graph_provider,
            podcast_id=podcast_id,
            episode_id=episode_id,
            config=config
        )


__all__ = ["ExtractionFactory"]
