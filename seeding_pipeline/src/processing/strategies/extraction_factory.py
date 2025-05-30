"""
Extraction strategy factory for creating appropriate extraction strategies.

This factory creates the correct extraction strategy based on configuration,
supporting fixed schema, schemaless, and dual mode extraction.
"""

import logging
from typing import Dict, Any, Optional, Union

from src.processing.strategies import ExtractionStrategy
from src.processing.strategies.schemaless_strategy import SchemalessStrategy
# Provider imports removed - using services directly
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ExtractionFactory:
    """Factory for creating extraction strategies based on configuration."""
    
    # Strategy mode constants
    SCHEMALESS_MODE = 'schemaless'
    
    @classmethod
    def create_strategy(
        cls,
        mode: str,
        llm_provider: Optional[Any] = None,
        graph_provider: Optional[Any] = None,
        podcast_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ExtractionStrategy:
        """
        Create an extraction strategy based on the specified mode.
        
        Args:
            mode: Extraction mode (only 'schemaless' supported)
            llm_provider: LLM provider (unused, kept for compatibility)
            graph_provider: Graph provider (required)
            podcast_id: Podcast ID (required)
            episode_id: Episode ID (required)
            config: Additional configuration options
            
        Returns:
            Configured extraction strategy
            
        Raises:
            ConfigurationError: If required parameters are missing
        """
        config = config or {}
        
        # Normalize mode
        mode = mode.lower()
            
        logger.info(f"Creating extraction strategy for mode: {mode}")
        
        if mode == cls.SCHEMALESS_MODE:
            return cls._create_schemaless_strategy(
                graph_provider, podcast_id, episode_id, config
            )
        else:
            raise ConfigurationError(
                f"Only 'schemaless' mode is supported. Got: {mode}"
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
    def create_from_config(
        cls,
        config: Dict[str, Any],
        llm_provider: Optional[Any] = None,
        graph_provider: Optional[Any] = None
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
        
        Always returns 'schemaless' mode
        """
        # Always return schemaless mode
        return cls.SCHEMALESS_MODE
    
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
