"""
Dual mode extraction strategy implementation.

This strategy runs both fixed schema and schemaless extraction for migration
and comparison purposes, combining the results from both approaches.
"""

import logging
from typing import Dict, Any, Optional, List

from src.processing.strategies import ExtractedData
from src.processing.strategies.fixed_schema_strategy import FixedSchemaStrategy
from src.processing.strategies.schemaless_strategy import SchemalessStrategy
from src.core.models import Segment
from src.core.interfaces import LLMProvider
from src.providers.graph.base import GraphProvider

logger = logging.getLogger(__name__)


class DualModeStrategy:
    """
    Extraction strategy that runs both fixed and schemaless approaches.
    
    This strategy is designed for migration scenarios where you want to
    compare results from both extraction methods and gradually transition
    from fixed to schemaless extraction.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        graph_provider: GraphProvider,
        podcast_id: str,
        episode_id: str,
        use_large_context: bool = True,
        enable_cache: bool = True
    ):
        """
        Initialize dual mode strategy.
        
        Args:
            llm_provider: LLM provider for fixed schema extraction
            graph_provider: Graph provider with schemaless support
            podcast_id: ID of the podcast being processed
            episode_id: ID of the episode being processed
            use_large_context: Whether to use large context for fixed extraction
            enable_cache: Whether to enable caching for fixed extraction
        """
        # Initialize both strategies
        self.fixed_strategy = FixedSchemaStrategy(
            llm_provider=llm_provider,
            use_large_context=use_large_context,
            enable_cache=enable_cache
        )
        
        self.schemaless_strategy = SchemalessStrategy(
            graph_provider=graph_provider,
            podcast_id=podcast_id,
            episode_id=episode_id
        )
        
        logger.info("Initialized DualModeStrategy")
    
    def extract(self, segment: Segment) -> ExtractedData:
        """
        Extract knowledge from a segment using both approaches.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            ExtractedData containing combined results from both methods
        """
        # Run fixed schema extraction
        fixed_result = self.fixed_strategy.extract(segment)
        
        # Run schemaless extraction
        schemaless_result = self.schemaless_strategy.extract(segment)
        
        # Combine results
        # Use entities from fixed schema (more structured)
        combined_entities = fixed_result.entities
        
        # Add any unique entities from schemaless that aren't in fixed
        fixed_entity_names = {e.name.lower() for e in fixed_result.entities}
        for entity in schemaless_result.entities:
            if entity.name.lower() not in fixed_entity_names:
                combined_entities.append(entity)
        
        # Use relationships from schemaless (more comprehensive)
        relationships = schemaless_result.relationships
        
        # Use quotes and insights from fixed schema (better structured)
        quotes = fixed_result.quotes
        insights = fixed_result.insights
        topics = fixed_result.topics
        
        # Build combined metadata
        metadata = {
            'extraction_mode': 'dual',
            'fixed_metadata': fixed_result.metadata,
            'schemaless_metadata': schemaless_result.metadata,
            'entity_comparison': {
                'fixed_count': len(fixed_result.entities),
                'schemaless_count': len(schemaless_result.entities),
                'combined_count': len(combined_entities)
            },
            'relationship_comparison': {
                'fixed_count': len(fixed_result.relationships),
                'schemaless_count': len(schemaless_result.relationships)
            },
            'discovered_types': self.schemaless_strategy.get_discovered_types()
        }
        
        # Log comparison for monitoring
        logger.info(f"Dual mode extraction comparison for segment {segment.id}:")
        logger.info(f"  Fixed: {len(fixed_result.entities)} entities, "
                   f"{len(fixed_result.quotes)} quotes, {len(fixed_result.insights)} insights")
        logger.info(f"  Schemaless: {len(schemaless_result.entities)} entities, "
                   f"{len(schemaless_result.relationships)} relationships")
        logger.info(f"  Combined: {len(combined_entities)} entities")
        
        return ExtractedData(
            entities=combined_entities,
            relationships=relationships,
            quotes=quotes,
            insights=insights,
            topics=topics,
            metadata=metadata
        )
    
    def get_extraction_mode(self) -> str:
        """
        Get the extraction mode identifier.
        
        Returns:
            'dual' - indicating dual mode extraction
        """
        return 'dual'
    
    def get_discovered_types(self) -> List[str]:
        """
        Get the list of discovered entity types from schemaless extraction.
        
        Returns:
            List of discovered entity type names
        """
        return self.schemaless_strategy.get_discovered_types()


__all__ = ['DualModeStrategy']