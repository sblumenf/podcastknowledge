"""Base storage coordinator with common functionality for all storage implementations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import logging

from ..core.models import Entity
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseStorageCoordinator(ABC):
    """Abstract base class for storage coordinators.
    
    Provides common functionality for storing knowledge graph data,
    with abstract methods for implementation-specific behavior.
    """
    
    def __init__(self, graph_provider: Any, graph_enhancer: Any, config: Any):
        """Initialize base storage coordinator.
        
        Args:
            graph_provider: Graph database provider
            graph_enhancer: Graph enhancement component
            config: Pipeline configuration
        """
        self.graph_provider = graph_provider
        self.graph_enhancer = graph_enhancer
        self.config = config
    
    @abstractmethod
    def _get_podcast_context(self) -> Optional[str]:
        """Get the current podcast context for multi-database routing.
        
        Returns:
            Podcast ID for context-aware routing, or None for single database
        """
        pass
    
    def store_all(self, 
                  podcast_config: Dict[str, Any],
                  episode: Dict[str, Any],
                  segments: List[Dict[str, Any]],
                  extraction_result: Dict[str, Any],
                  resolved_entities: List[Entity]) -> None:
        """Store all extracted data to the knowledge graph.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Extraction results
            resolved_entities: Resolved entities
        """
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
        self._store_emergent_themes(
            episode['id'], 
            extraction_result.get('emergent_themes', {}),
            resolved_entities
        )
        
        # Run post-storage enhancements
        self._run_post_storage_enhancements(episode['id'])
    
    def _run_post_storage_enhancements(self, episode_id: str) -> None:
        """Run graph enhancement and knowledge discovery after storage.
        
        Args:
            episode_id: Episode identifier
        """
        # Enhance graph if configured
        if getattr(self.config, 'enhance_graph', True):
            logger.info("Enhancing knowledge graph...")
            self.graph_enhancer.enhance_episode(episode_id)
        
        # Run knowledge discovery analyses if configured
        if getattr(self.config, 'enable_knowledge_discovery', True):
            self._run_knowledge_discovery(episode_id)
    
    def _run_knowledge_discovery(self, episode_id: str) -> None:
        """Run knowledge discovery analyses.
        
        Args:
            episode_id: Episode identifier
        """
        try:
            from src.analysis.analysis_orchestrator import run_knowledge_discovery
            logger.info(f"Running knowledge discovery for episode {episode_id}...")
            
            # Run analyses with a new session to avoid conflicts
            with self.graph_provider.driver.session() as discovery_session:
                discovery_results = run_knowledge_discovery(episode_id, discovery_session)
                
                if discovery_results.get('summary', {}).get('status') == 'healthy':
                    logger.info(f"Knowledge discovery completed successfully for episode {episode_id}")
                    if discovery_results.get('summary', {}).get('key_findings'):
                        logger.info(f"Key findings: {discovery_results['summary']['key_findings']}")
                else:
                    logger.warning(f"Knowledge discovery partially completed for episode {episode_id}")
                    
        except ImportError:
            logger.warning("Knowledge discovery module not available")
        except Exception as e:
            logger.error(f"Error running knowledge discovery: {e}")
            # Don't fail the pipeline if knowledge discovery fails
    
    def _store_podcast(self, podcast_config: Dict[str, Any]) -> None:
        """Store podcast node.
        
        Args:
            podcast_config: Podcast configuration
        """
        properties = {
            'id': podcast_config['id'],
            'name': podcast_config['name'],
            'description': podcast_config.get('description', ''),
            'host': podcast_config.get('host', ''),
            'url': podcast_config.get('url', ''),
            'category': podcast_config.get('category', ''),
        }
        
        podcast_id = self._get_podcast_context()
        if podcast_id:
            properties['podcast_id'] = podcast_id
        
        self.graph_provider.store_podcast(properties)
    
    def _store_episode(self, episode: Dict[str, Any], extraction_result: Dict[str, Any]) -> None:
        """Store episode node with extraction metadata.
        
        Args:
            episode: Episode information
            extraction_result: Extraction results
        """
        properties = {
            'id': episode['id'],
            'title': episode['title'],
            'description': episode.get('description', ''),
            'air_date': episode.get('air_date', ''),
            'duration': episode.get('duration', 0),
            'url': episode.get('url', ''),
        }
        
        # Add extraction metadata
        if 'metadata' in extraction_result:
            metadata = extraction_result['metadata']
            properties.update({
                'extraction_model': metadata.get('model', 'unknown'),
                'extraction_version': metadata.get('version', '0.0.0'),
                'extraction_timestamp': metadata.get('timestamp', ''),
            })
        
        podcast_id = self._get_podcast_context()
        if podcast_id:
            properties['podcast_id'] = podcast_id
        
        self.graph_provider.store_episode(properties)
    
    def _create_podcast_episode_relationship(self, podcast_id: str, episode_id: str) -> None:
        """Create HAS_EPISODE relationship between podcast and episode.
        
        Args:
            podcast_id: Podcast identifier
            episode_id: Episode identifier
        """
        self.graph_provider.store_relationship(
            source_id=podcast_id,
            source_label='Podcast',
            target_id=episode_id,
            target_label='Episode',
            rel_type='HAS_EPISODE',
            properties={'podcast_id': self._get_podcast_context() or podcast_id}
        )
    
    def _store_segments(self, episode_id: str, segments: List[Dict[str, Any]]) -> None:
        """Store segment nodes and relationships.
        
        Args:
            episode_id: Episode identifier
            segments: List of segments
        """
        podcast_id = self._get_podcast_context()
        
        for segment in segments:
            # Prepare segment properties
            properties = {
                'id': segment['id'],
                'content': segment['text'],
                'start_time': segment['start_time'],
                'end_time': segment['end_time'],
                'speaker': segment.get('speaker', 'Unknown'),
                'segment_number': segment.get('segment_number', segment.get('index', 0)),
            }
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store segment
            self.graph_provider.store_segment(properties)
            
            # Create episode-segment relationship
            self.graph_provider.store_relationship(
                source_id=episode_id,
                source_label='Episode',
                target_id=segment['id'],
                target_label='Segment',
                rel_type='HAS_SEGMENT',
                properties={
                    'order': segment.get('segment_number', segment.get('index', 0)),
                    'podcast_id': podcast_id or episode_id.split('_')[0]
                }
            )
    
    def _store_insights(self, episode_id: str, insights: List[Dict[str, Any]]) -> None:
        """Store insight nodes and relationships.
        
        Args:
            episode_id: Episode identifier
            insights: List of insights
        """
        podcast_id = self._get_podcast_context()
        
        for insight in insights:
            # Prepare insight properties
            properties = {
                'id': insight['id'],
                'content': insight.get('content', insight.get('title', '')),
                'insight_type': insight.get('type', 'general'),
                'confidence': insight.get('confidence', 0.8),
                'evidence': insight.get('evidence', ''),
            }
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store insight
            self.graph_provider.store_insight(properties)
            
            # Create episode-insight relationship
            self.graph_provider.store_relationship(
                source_id=episode_id,
                source_label='Episode',
                target_id=insight['id'],
                target_label='Insight',
                rel_type='HAS_INSIGHT',
                properties={'podcast_id': podcast_id or episode_id.split('_')[0]}
            )
            
            # Create entity-insight relationships
            for entity_id in insight.get('supporting_entities', []):
                self.graph_provider.store_relationship(
                    source_id=entity_id,
                    source_label='Entity',
                    target_id=insight['id'],
                    target_label='Insight',
                    rel_type='SUPPORTS',
                    properties={'podcast_id': podcast_id or episode_id.split('_')[0]}
                )
    
    def _store_entities(self, episode_id: str, entities: List[Entity]) -> None:
        """Store entity nodes and their relationships.
        
        Args:
            episode_id: Episode identifier
            entities: List of resolved entities
        """
        podcast_id = self._get_podcast_context()
        
        for entity in entities:
            # Extract entity properties
            properties = self._extract_entity_properties(entity)
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store entity
            self.graph_provider.store_entity(properties)
            
            # Create episode-entity relationship
            self._store_entity_episode_relationship(episode_id, entity, podcast_id)
            
            # Store entity relationships
            self._store_entity_relationships(entity, podcast_id)
    
    def _extract_entity_properties(self, entity: Entity) -> Dict[str, Any]:
        """Extract properties from entity object.
        
        Args:
            entity: Entity object
            
        Returns:
            Dictionary of entity properties
        """
        properties = {
            'id': entity.properties.get('id', entity.name),
            'name': entity.name,
            'entity_type': entity.entity_type.value if hasattr(entity, 'entity_type') else 'unknown',
            'confidence': entity.confidence,
        }
        
        # Add optional properties
        if hasattr(entity, 'description') and entity.description:
            properties['description'] = entity.description
        
        if hasattr(entity, 'aliases') and entity.aliases:
            properties['aliases'] = entity.aliases
        
        # Add custom properties
        if entity.properties:
            for key, value in entity.properties.items():
                if key not in properties and value is not None:
                    properties[key] = value
        
        return properties
    
    def _store_entity_episode_relationship(self, episode_id: str, entity: Entity, 
                                         podcast_id: Optional[str]) -> None:
        """Store relationship between entity and episode.
        
        Args:
            episode_id: Episode identifier
            entity: Entity object
            podcast_id: Podcast identifier for context
        """
        rel_properties = {
            'mentions': entity.properties.get('mention_count', 1),
            'confidence': entity.confidence,
            'podcast_id': podcast_id or episode_id.split('_')[0]
        }
        
        # Add flow data if available
        if hasattr(entity, 'flow_data') and entity.flow_data:
            rel_properties.update({
                'first_mention': entity.flow_data.get('first_mention_time', 0),
                'last_mention': entity.flow_data.get('last_mention_time', 0),
                'persistence_score': entity.flow_data.get('persistence_score', 0),
            })
        
        self.graph_provider.store_relationship(
            source_id=episode_id,
            source_label='Episode',
            target_id=entity.properties.get('id', entity.name),
            target_label='Entity',
            rel_type='MENTIONS',
            properties=rel_properties
        )
    
    def _store_entity_relationships(self, entity: Entity, podcast_id: Optional[str]) -> None:
        """Store relationships between entities.
        
        Args:
            entity: Entity object
            podcast_id: Podcast identifier for context
        """
        if not hasattr(entity, 'relationships') or not entity.relationships:
            return
        
        for rel in entity.relationships:
            rel_properties = {
                'strength': rel.get('strength', 0.5),
                'context': rel.get('context', ''),
                'podcast_id': podcast_id or ''
            }
            
            self.graph_provider.store_relationship(
                source_id=entity.properties.get('id', entity.name),
                source_label='Entity',
                target_id=rel['target_id'],
                target_label='Entity',
                rel_type=rel['type'],
                properties=rel_properties
            )
    
    def _store_quotes(self, episode_id: str, quotes: List[Dict[str, Any]]) -> None:
        """Store quote nodes and relationships.
        
        Args:
            episode_id: Episode identifier
            quotes: List of quotes
        """
        podcast_id = self._get_podcast_context()
        
        for quote in quotes:
            # Prepare quote properties
            properties = {
                'id': quote['id'],
                'text': quote['text'],
                'speaker': quote.get('speaker', 'Unknown'),
                'context': quote.get('context', ''),
                'significance': quote.get('significance', ''),
                'timestamp': quote.get('timestamp', 0),
            }
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store quote
            self.graph_provider.store_quote(properties)
            
            # Create episode-quote relationship
            self.graph_provider.store_relationship(
                source_id=episode_id,
                source_label='Episode',
                target_id=quote['id'],
                target_label='Quote',
                rel_type='CONTAINS_QUOTE',
                properties={'podcast_id': podcast_id or episode_id.split('_')[0]}
            )
    
    def _store_emergent_themes(self, episode_id: str, themes: Dict[str, Any],
                              entities: List[Entity]) -> None:
        """Store emergent theme nodes and relationships.
        
        Args:
            episode_id: Episode identifier
            themes: Emergent themes data
            entities: List of entities for theme connections
        """
        podcast_id = self._get_podcast_context()
        
        # Store main themes
        for theme in themes.get('themes', []):
            theme_id = f"{episode_id}_theme_{theme.get('name', '').replace(' ', '_').lower()}"
            
            properties = {
                'id': theme_id,
                'name': theme['name'],
                'description': theme.get('description', ''),
                'confidence': theme.get('confidence', 0.7),
                'evidence_strength': theme.get('evidence_strength', 0.5),
            }
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store theme
            self.graph_provider.store_theme(properties)
            
            # Create episode-theme relationship
            self.graph_provider.store_relationship(
                source_id=episode_id,
                source_label='Episode',
                target_id=theme_id,
                target_label='Theme',
                rel_type='EXPLORES_THEME',
                properties={'podcast_id': podcast_id or episode_id.split('_')[0]}
            )
            
            # Connect related entities to theme
            for entity_name in theme.get('related_entities', []):
                # Find matching entity
                matching_entity = next(
                    (e for e in entities if e.name.lower() == entity_name.lower()),
                    None
                )
                if matching_entity:
                    self.graph_provider.store_relationship(
                        source_id=matching_entity.properties.get('id', matching_entity.name),
                        source_label='Entity',
                        target_id=theme_id,
                        target_label='Theme',
                        rel_type='RELATES_TO_THEME',
                        properties={
                            'relevance': 0.8,
                            'podcast_id': podcast_id or episode_id.split('_')[0]
                        }
                    )
    
    def store_entities(self, entities: List[Entity], source_type: str = 'episode',
                      source_id: Optional[str] = None) -> List[str]:
        """Store entities and return their IDs.
        
        Args:
            entities: List of entities to store
            source_type: Type of source (episode, segment, etc.)
            source_id: ID of the source
            
        Returns:
            List of stored entity IDs
        """
        entity_ids = []
        podcast_id = self._get_podcast_context()
        
        for entity in entities:
            properties = self._extract_entity_properties(entity)
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            # Store entity
            self.graph_provider.store_entity(properties)
            entity_ids.append(properties['id'])
            
            # Create source relationship if provided
            if source_id:
                self.graph_provider.store_relationship(
                    source_id=source_id,
                    source_label=source_type.capitalize(),
                    target_id=properties['id'],
                    target_label='Entity',
                    rel_type='HAS_ENTITY',
                    properties={'podcast_id': podcast_id or source_id.split('_')[0]}
                )
        
        return entity_ids
    
    def store_relationships(self, relationships: List[Dict[str, Any]]) -> None:
        """Store entity relationships.
        
        Args:
            relationships: List of relationship dictionaries
        """
        podcast_id = self._get_podcast_context()
        
        for rel in relationships:
            properties = {
                'strength': rel.get('strength', 0.5),
                'evidence': rel.get('evidence', ''),
                'context': rel.get('context', ''),
            }
            
            if podcast_id:
                properties['podcast_id'] = podcast_id
            
            self.graph_provider.store_relationship(
                source_id=rel['source_id'],
                source_label=rel.get('source_label', 'Entity'),
                target_id=rel['target_id'],
                target_label=rel.get('target_label', 'Entity'),
                rel_type=rel['type'],
                properties=properties
            )
    
    def resolve_entities(self, entities: List[Entity]) -> List[Entity]:
        """Resolve entities using entity resolver.
        
        Args:
            entities: List of entities to resolve
            
        Returns:
            List of resolved entities
        """
        # This is typically delegated to an entity resolver component
        # For now, return entities as-is
        return entities