"""Multi-database storage coordination component for managing graph database operations."""

from typing import Dict, Any, List, Optional
import logging
import os

from src.core.models import Entity
from src.storage.storage_coordinator import StorageCoordinator
from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


class MultiDatabaseStorageCoordinator(StorageCoordinator):
    """Storage coordinator with multi-database support for different podcasts."""
    
    def __init__(self, graph_provider: Any, graph_enhancer: Any, config):
        """Initialize multi-database storage coordinator.
        
        Args:
            graph_provider: Graph database provider (can be MultiDatabaseGraphStorage)
            graph_enhancer: Graph enhancement component
            config: Pipeline configuration
        """
        super().__init__(graph_provider, graph_enhancer, config)
        
        # Check if we're in multi-database mode
        self.multi_db_mode = (
            isinstance(graph_provider, MultiDatabaseGraphStorage) or
            hasattr(graph_provider, 'set_podcast_context') or
            os.getenv('PODCAST_MODE', 'single') == 'multi'
        )
        
        if self.multi_db_mode:
            logger.info("Multi-database mode enabled for storage coordinator")
        
    def store_all(self, podcast_config: Dict[str, Any],
                  episode: Dict[str, Any],
                  segments: List[Dict[str, Any]],
                  extraction_result: Dict[str, Any],
                  resolved_entities: List[Entity]):
        """Store all extracted data to the knowledge graph with podcast routing.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Extraction results
            resolved_entities: Resolved entities
        """
        # Extract podcast ID for routing
        podcast_id = (
            podcast_config.get('podcast_id') or 
            podcast_config.get('id') or 
            episode.get('podcast_id') or
            'unknown_podcast'
        )
        
        # Set podcast context if in multi-db mode
        if self.multi_db_mode and hasattr(self.graph_provider, 'set_podcast_context'):
            self.graph_provider.set_podcast_context(podcast_id)
            logger.info(f"Set podcast context to: {podcast_id}")
        
        # Ensure podcast_config has an id before calling parent
        if 'id' not in podcast_config:
            podcast_config = podcast_config.copy()
            podcast_config['id'] = podcast_id
            
        # Call parent implementation
        super().store_all(podcast_config, episode, segments, extraction_result, resolved_entities)
        
    def _store_podcast(self, podcast_config: Dict[str, Any]):
        """Store podcast node with multi-db support.
        
        Args:
            podcast_config: Podcast configuration
        """
        # Get podcast ID with fallback
        podcast_id = podcast_config.get('id', 'unknown_podcast')
        
        # Ensure podcast_id is in the data
        podcast_data = {
            'id': podcast_id,
            'podcast_id': podcast_config.get('podcast_id', podcast_id),
            'name': podcast_config.get('name', podcast_id),
            'description': podcast_config.get('description', ''),
            'rss_url': podcast_config.get('rss_url', '')
        }
        
        # In multi-db mode, the graph provider will route to correct database
        self.graph_provider.create_node('Podcast', podcast_data)
        
    def _store_episode(self, episode: Dict[str, Any], extraction_result: Dict[str, Any]):
        """Store episode node with podcast context.
        
        Args:
            episode: Episode information
            extraction_result: Extraction results containing flow data
        """
        episode_data = {
            'id': episode['id'],
            'title': episode['title'],
            'description': episode.get('description', ''),
            'published_date': episode.get('published_date', ''),
            'duration': episode.get('duration', ''),
            'audio_url': episode.get('audio_url', ''),
            'youtube_url': episode.get('youtube_url', ''),
            'podcast_id': episode.get('podcast_id', 'unknown_podcast')  # Add podcast ID
        }
        
        # Add episode flow data if available
        if 'episode_flow' in extraction_result:
            episode_flow_data = extraction_result['episode_flow']
            episode_data['discourse_flow_pattern'] = episode_flow_data.get('pattern', 'unknown')
            episode_data['flow_quality'] = episode_flow_data.get('flow_quality', 0.5)
            episode_data['key_transitions_count'] = len(episode_flow_data.get('key_transitions', []))
        
        self.graph_provider.create_node('Episode', episode_data)
        
    def _store_entities(self, episode_id: str, entities: List[Entity]):
        """Store entities with podcast context.
        
        Args:
            episode_id: Episode ID
            entities: List of resolved entities
        """
        # Extract podcast_id from episode_id if possible
        podcast_id = None
        if '_' in episode_id:
            # Try to extract podcast_id from episode_id pattern
            parts = episode_id.split('_')
            if len(parts) > 1:
                podcast_id = parts[0]
        
        for entity in entities:
            # Convert entity to dictionary to ensure flow_data is included
            entity_data = {
                'id': entity.id,
                'name': entity.name,
                'type': entity.type,
                'description': entity.description,
                'confidence': getattr(entity, 'confidence', 1.0),
                'importance_score': getattr(entity, 'importance_score', 0.5),
                'importance_factors': getattr(entity, 'importance_factors', {}),
                'discourse_roles': getattr(entity, 'discourse_roles', {})
            }
            
            # Add podcast_id if available
            if podcast_id:
                entity_data['podcast_id'] = podcast_id
            
            # Add flow data if present
            if hasattr(entity, 'flow_data') and entity.flow_data:
                entity_data.update({
                    'flow_introduction_point': entity.flow_data.get('introduction_point', 0),
                    'flow_development_duration': entity.flow_data.get('development_duration', 0),
                    'flow_peak_discussion': entity.flow_data.get('peak_discussion', 0),
                    'flow_resolution_status': entity.flow_data.get('resolution_status', 'unknown')
                })
            
            # Add embedding if present
            if hasattr(entity, 'embedding') and entity.embedding:
                entity_data['embedding'] = entity.embedding
            
            # Create or update entity
            self.graph_provider.create_node('Entity', entity_data)
            
            # Create relationship to episode
            self.graph_provider.create_relationship(
                episode_id,                              # source_id: str
                entity.id,                               # target_id: str
                'MENTIONS',                              # rel_type: str
                {'confidence': entity_data['confidence']}  # properties: dict
            )
            
    def switch_podcast_context(self, podcast_id: str):
        """Switch to a different podcast context.
        
        Args:
            podcast_id: Podcast identifier
        """
        if self.multi_db_mode and hasattr(self.graph_provider, 'set_podcast_context'):
            self.graph_provider.set_podcast_context(podcast_id)
            logger.info(f"Switched podcast context to: {podcast_id}")
            
    def get_current_podcast_context(self) -> Optional[str]:
        """Get the current podcast context.
        
        Returns:
            Current podcast ID or None
        """
        if self.multi_db_mode and hasattr(self.graph_provider, '_current_podcast_id'):
            return self.graph_provider._current_podcast_id
        return None