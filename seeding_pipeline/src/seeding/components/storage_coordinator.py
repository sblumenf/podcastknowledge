"""Storage coordination component for managing graph database operations."""

import logging
from typing import Dict, Any, List, Optional

from src.providers.graph.base import GraphProvider
from src.providers.graph.enhancements import GraphEnhancements
from src.core.models import Entity
from src.tracing import trace_method, create_span, add_span_attributes
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StorageCoordinator:
    """Coordinates all storage operations to the knowledge graph."""
    
    def __init__(self, graph_provider: GraphProvider, graph_enhancer: GraphEnhancements, config):
        """Initialize storage coordinator.
        
        Args:
            graph_provider: Graph database provider
            graph_enhancer: Graph enhancement component
            config: Pipeline configuration
        """
        self.graph_provider = graph_provider
        self.graph_enhancer = graph_enhancer
        self.config = config
    
    @trace_method(name="storage.store_all")
    def store_all(self, podcast_config: Dict[str, Any],
                  episode: Dict[str, Any],
                  segments: List[Dict[str, Any]],
                  extraction_result: Dict[str, Any],
                  resolved_entities: List[Entity]):
        """Store all extracted data to the knowledge graph.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Extraction results
            resolved_entities: Resolved entities
        """
        with create_span("graph_storage"):
            logger.info("Saving to knowledge graph...")
            
            # Store podcast
            self._store_podcast(podcast_config)
            
            # Store episode
            self._store_episode(episode, extraction_result)
            
            # Create podcast-episode relationship
            self._create_podcast_episode_relationship(podcast_config['id'], episode['id'])
            
            # Store segments
            self._store_segments(episode['id'], segments)
            
            # Store insights
            self._store_insights(episode['id'], extraction_result.get('insights', []))
            
            # Store entities
            self._store_entities(episode['id'], resolved_entities)
            
            # Store quotes
            self._store_quotes(episode['id'], extraction_result.get('quotes', []))
            
            # Store emergent themes
            self._store_emergent_themes(episode['id'], 
                                      extraction_result.get('emergent_themes', {}),
                                      resolved_entities)
            
            # Enhance graph if configured
            if getattr(self.config, 'enhance_graph', True):
                logger.info("Enhancing knowledge graph...")
                self.graph_enhancer.enhance_episode(episode['id'])
    
    def _store_podcast(self, podcast_config: Dict[str, Any]):
        """Store podcast node.
        
        Args:
            podcast_config: Podcast configuration
        """
        self.graph_provider.create_node(
            'Podcast',
            {
                'id': podcast_config['id'],
                'name': podcast_config.get('name', podcast_config['id']),
                'description': podcast_config.get('description', ''),
                'rss_url': podcast_config.get('rss_url', '')
            }
        )
    
    def _store_episode(self, episode: Dict[str, Any], extraction_result: Dict[str, Any]):
        """Store episode node with flow data.
        
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
            'audio_url': episode.get('audio_url', '')
        }
        
        # Add episode flow data if available
        if 'episode_flow' in extraction_result:
            episode_flow_data = extraction_result['episode_flow']
            episode_data['discourse_flow_pattern'] = episode_flow_data.get('pattern', 'unknown')
            episode_data['flow_quality'] = episode_flow_data.get('flow_quality', 0.5)
            episode_data['key_transitions_count'] = len(episode_flow_data.get('key_transitions', []))
        
        self.graph_provider.create_node('Episode', episode_data)
    
    def _create_podcast_episode_relationship(self, podcast_id: str, episode_id: str):
        """Create relationship between podcast and episode.
        
        Args:
            podcast_id: Podcast ID
            episode_id: Episode ID
        """
        self.graph_provider.create_relationship(
            ('Podcast', {'id': podcast_id}),
            'HAS_EPISODE',
            ('Episode', {'id': episode_id}),
            {}
        )
    
    def _store_segments(self, episode_id: str, segments: List[Dict[str, Any]]):
        """Store segment nodes and relationships.
        
        Args:
            episode_id: Episode ID
            segments: List of segments
        """
        for i, segment in enumerate(segments):
            segment_data = {
                'id': f"{episode_id}_segment_{i}",
                'segment_index': i,
                'text': segment['text'],
                'start_time': segment['start'],
                'end_time': segment['end'],
                'speaker': segment.get('speaker', 'Unknown'),
                'sentiment': segment.get('sentiment', 'neutral')
            }
            
            self.graph_provider.create_node('Segment', segment_data)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode_id}),
                'HAS_SEGMENT',
                ('Segment', {'id': segment_data['id']}),
                {'sequence': i}
            )
    
    def _store_insights(self, episode_id: str, insights: List[Dict[str, Any]]):
        """Store insight nodes and relationships.
        
        Args:
            episode_id: Episode ID
            insights: List of insights
        """
        for insight in insights:
            self.graph_provider.create_node('Insight', insight)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode_id}),
                'HAS_INSIGHT',
                ('Insight', {'id': insight['id']}),
                {}
            )
    
    def store_entities(self, episode_id: str, entities: List[Entity]):
        """Store entity nodes with flow data and relationships.
        
        Args:
            episode_id: Episode ID
            entities: List of resolved entities
        """
        self._store_entities(episode_id, entities)
    
    def _store_entities(self, episode_id: str, entities: List[Entity]):
        """Internal method to store entities.
        
        Args:
            episode_id: Episode ID
            entities: List of resolved entities
        """
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
                ('Episode', {'id': episode_id}),
                'MENTIONS',
                ('Entity', {'id': entity.id}),
                {'confidence': entity_data['confidence']}
            )
    
    def store_relationships(self, relationships: List[Dict[str, Any]]):
        """Store relationship data between entities.
        
        Args:
            relationships: List of relationship data
        """
        for rel in relationships:
            self.graph_provider.create_relationship(
                ('Entity', {'id': rel['source_id']}),
                rel['type'],
                ('Entity', {'id': rel['target_id']}),
                rel.get('properties', {})
            )
    
    def _store_quotes(self, episode_id: str, quotes: List[Dict[str, Any]]):
        """Store quote nodes and relationships.
        
        Args:
            episode_id: Episode ID
            quotes: List of quotes
        """
        for quote in quotes:
            quote['id'] = f"{episode_id}_quote_{hash(quote['text'])}"
            self.graph_provider.create_node('Quote', quote)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode_id}),
                'CONTAINS_QUOTE',
                ('Quote', {'id': quote['id']}),
                {}
            )
    
    def _store_emergent_themes(self, episode_id: str, 
                             emergent_themes_data: Dict[str, Any],
                             resolved_entities: List[Entity]):
        """Store emergent theme nodes and relationships.
        
        Args:
            episode_id: Episode ID
            emergent_themes_data: Emergent themes data
            resolved_entities: List of resolved entities for linking
        """
        if not emergent_themes_data or not emergent_themes_data.get('themes'):
            return
        
        logger.info(f"Saving {len(emergent_themes_data['themes'])} emergent themes...")
        
        for theme in emergent_themes_data['themes']:
            # Create theme node
            theme_data = {
                'id': f"{episode_id}_theme_{theme.get('theme_id', hash(theme['semantic_field']))}",
                'semantic_field': theme.get('semantic_field', 'Unknown'),
                'emergence_score': theme.get('emergence_score', 0.5),
                'confidence': theme.get('confidence', 0.5),
                'validation_score': theme.get('validation_score', 0.5),
                'theme_source': theme.get('theme_source', 'unknown'),
                'evolution_pattern': theme.get('evolution_pattern', 'unknown')
            }
            
            self.graph_provider.create_node('EmergentTheme', theme_data)
            
            # Create relationship to episode
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode_id}),
                'HAS_EMERGENT_THEME',
                ('EmergentTheme', {'id': theme_data['id']}),
                {'strength': theme.get('confidence', 0.5)}
            )
            
            # Link theme to its key concepts
            for concept_name in theme.get('key_concepts', [])[:5]:  # Top 5 concepts
                # Find matching entity
                matching_entity = next(
                    (e for e in resolved_entities if e.name.lower() == concept_name.lower()),
                    None
                )
                if matching_entity:
                    self.graph_provider.create_relationship(
                        ('EmergentTheme', {'id': theme_data['id']}),
                        'COMPOSED_OF',
                        ('Entity', {'id': matching_entity.id}),
                        {'role': 'key_concept'}
                    )
    
    def resolve_entities(self, entities: List[Dict[str, Any]], 
                        existing_entities: Optional[List[Entity]] = None) -> List[Entity]:
        """Resolve and deduplicate entities.
        
        This delegates to entity resolver but is included here for convenience.
        
        Args:
            entities: List of entity data
            existing_entities: Optional list of existing entities
            
        Returns:
            List of resolved entities
        """
        # This would typically delegate to EntityResolver
        # For now, just return entities as-is
        resolved = []
        for entity_data in entities:
            entity = Entity(
                id=entity_data.get('id'),
                name=entity_data.get('name'),
                type=entity_data.get('type'),
                description=entity_data.get('description', '')
            )
            resolved.append(entity)
        return resolved