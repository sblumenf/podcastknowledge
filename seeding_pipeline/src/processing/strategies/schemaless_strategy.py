"""
Schemaless extraction strategy implementation.

This strategy wraps the schemaless extraction logic using the graph provider's
SimpleKGPipeline integration for dynamic schema discovery.
"""

import logging
from typing import Dict, Any, Optional, List

from src.processing.strategies import ExtractedData
from src.core.models import Segment, Entity, Insight, Quote
# Provider imports removed - using services directly

logger = logging.getLogger(__name__)


class SchemalessStrategy:
    """
    Extraction strategy using schemaless approach.
    
    This strategy leverages the graph provider's schemaless extraction
    capabilities to dynamically discover entities and relationships.
    """
    
    def __init__(
        self,
        graph_provider: Any,  # GraphStorageService
        podcast_id: str,
        episode_id: str
    ):
        """
        Initialize schemaless strategy.
        
        Args:
            graph_provider: Graph provider with schemaless support
            podcast_id: ID of the podcast being processed
            episode_id: ID of the episode being processed
        """
        if not hasattr(graph_provider, 'process_segment_schemaless'):
            raise ValueError("Graph provider does not support schemaless extraction")
            
        self.graph_provider = graph_provider
        self.podcast_id = podcast_id
        self.episode_id = episode_id
        self.discovered_types = set()
        logger.info("Initialized SchemalessStrategy")
    
    def extract(self, segment: Segment) -> ExtractedData:
        """
        Extract knowledge from a segment using schemaless approach.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            ExtractedData containing all extracted information
        """
        # Create minimal podcast and episode objects for the graph provider
        from src.core.models import Podcast, Episode
        
        podcast_obj = Podcast(
            id=self.podcast_id,
            title=f"Podcast {self.podcast_id}",
            description="",
            rss_url=""
        )
        
        episode_obj = Episode(
            id=self.episode_id,
            title=f"Episode {self.episode_id}",
            description="",
            published_date="",
            audio_url=""
        )
        
        try:
            # Use graph provider's schemaless extraction
            result = self.graph_provider.process_segment_schemaless(
                segment, episode_obj, podcast_obj
            )
            
            # Track discovered types
            if 'discovered_types' in result:
                self.discovered_types.update(result['discovered_types'])
            
            # Convert schemaless result to ExtractedData
            # Note: Schemaless mode doesn't extract insights or quotes in the same way
            entities = []
            relationships = []
            
            # Extract entity information from result
            if 'entities' in result and isinstance(result['entities'], list):
                for entity_data in result['entities']:
                    entity = Entity(
                        id=entity_data.get('id', ''),
                        name=entity_data.get('name', ''),
                        type=entity_data.get('type', 'UNKNOWN'),
                        description=entity_data.get('description'),
                        metadata=entity_data.get('properties', {})
                    )
                    entities.append(entity)
            
            # Extract relationship information
            if 'relationships' in result and isinstance(result['relationships'], list):
                relationships = result['relationships']
            
            # Build metadata
            metadata = {
                'extraction_mode': 'schemaless',
                'segment_id': segment.id,
                'entities_extracted': result.get('entities', 0),
                'relationships_extracted': result.get('relationships', 0),
                'discovered_types': list(self.discovered_types)
            }
            
            # Schemaless doesn't typically extract quotes/insights in fixed format
            quotes = []
            insights = []
            topics = []
            
            return ExtractedData(
                entities=entities,
                relationships=relationships,
                quotes=quotes,
                insights=insights,
                topics=topics,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Schemaless extraction failed: {e}")
            # Return empty result on failure
            return ExtractedData(
                entities=[],
                relationships=[],
                quotes=[],
                insights=[],
                topics=[],
                metadata={
                    'extraction_mode': 'schemaless',
                    'error': str(e)
                }
            )
    
    def get_extraction_mode(self) -> str:
        """
        Get the extraction mode identifier.
        
        Returns:
            'schemaless' - indicating schemaless extraction
        """
        return 'schemaless'
    
    def get_discovered_types(self) -> List[str]:
        """
        Get the list of discovered entity types.
        
        Returns:
            List of discovered entity type names
        """
        return list(self.discovered_types)


__all__ = ['SchemalessStrategy']