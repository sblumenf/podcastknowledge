"""Base graph database provider implementation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Iterator
from contextlib import contextmanager

from src.core.interfaces import GraphProvider, HealthCheckable
from src.core.models import (
    Podcast, Episode, Segment, Entity, 
    Insight, Quote, Topic, Speaker
)


class BaseGraphProvider(GraphProvider, HealthCheckable, ABC):
    """Base implementation for graph database providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the graph provider with configuration."""
        self.config = config
        self.uri = config.get('uri')
        self.username = config.get('username')
        self.password = config.get('password')
        self.database = config.get('database', 'neo4j')
        self._driver = None
        self._initialized = False
        
    @abstractmethod
    def _initialize_driver(self) -> None:
        """Initialize the database driver."""
        pass
        
    def _ensure_initialized(self) -> None:
        """Ensure the provider is initialized."""
        if not self._initialized:
            self._initialize_driver()
            self._initialized = True
            
    @abstractmethod
    def connect(self) -> None:
        """Connect to the graph database."""
        pass
        
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the graph database."""
        pass
        
    @abstractmethod
    @contextmanager
    def session(self):
        """Create a database session context manager."""
        pass
        
    @abstractmethod
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a node in the graph."""
        pass
        
    @abstractmethod
    def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a relationship between nodes."""
        pass
        
    @abstractmethod
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        pass
        
    @abstractmethod
    def delete_node(self, node_id: str) -> None:
        """Delete a node by ID."""
        pass
        
    @abstractmethod
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Update node properties."""
        pass
        
    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        pass
        
    @abstractmethod
    def setup_schema(self) -> None:
        """Set up database schema with constraints and indexes."""
        pass
        
    def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        try:
            self._ensure_initialized()
            # Try a simple query
            with self.session() as session:
                result = session.run("RETURN 'OK' AS status")
                
                # Handle different provider responses
                if hasattr(result, 'single'):
                    # Neo4j style
                    status = result.single()["status"]
                elif isinstance(result, list) and len(result) > 0:
                    # InMemory style
                    status = result[0]["status"]
                else:
                    status = "OK"
                
            return {
                'healthy': True,
                'provider': self.__class__.__name__,
                'database': self.database,
                'status': status,
                'initialized': self._initialized
            }
        except Exception as e:
            return {
                'healthy': False,
                'provider': self.__class__.__name__,
                'database': self.database,
                'error': str(e),
                'initialized': self._initialized
            }
            
    # High-level convenience methods
    
    def create_podcast(self, podcast: Podcast) -> str:
        """Create a podcast node."""
        properties = {
            'id': podcast.id,
            'name': podcast.name,
            'description': podcast.description,
            'feed_url': podcast.feed_url,
            'website': podcast.website,
            'hosts': podcast.hosts,
            'categories': podcast.categories,
            'created_timestamp': podcast.created_timestamp,
            'updated_timestamp': podcast.updated_timestamp
        }
        return self.create_node('Podcast', properties)
        
    def create_episode(self, episode: Episode) -> str:
        """Create an episode node."""
        properties = {
            'id': episode.id,
            'title': episode.title,
            'description': episode.description,
            'published_date': episode.published_date,
            'audio_url': episode.audio_url,
            'duration': episode.duration,
            'episode_number': episode.episode_number,
            'season_number': episode.season_number,
            'processed_timestamp': episode.processed_timestamp
        }
        if episode.sentiment_evolution:
            properties['sentiment_evolution'] = episode.sentiment_evolution
        return self.create_node('Episode', properties)
        
    def create_segment(self, segment: Segment) -> str:
        """Create a segment node."""
        properties = {
            'id': segment.id,
            'text': segment.text,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'speaker': segment.speaker,
            'sentiment': segment.sentiment,
            'complexity_score': segment.complexity_score,
            'is_advertisement': segment.is_advertisement
        }
        if segment.embedding:
            properties['embedding'] = segment.embedding
        return self.create_node('Segment', properties)
        
    def create_entity(self, entity: Entity) -> str:
        """Create an entity node."""
        properties = {
            'id': entity.id,
            'name': entity.name,
            'type': entity.entity_type.value if entity.entity_type else None,
            'description': entity.description,
            'first_mentioned': entity.first_mentioned,
            'mention_count': entity.mention_count,
            'bridge_score': entity.bridge_score,
            'is_peripheral': entity.is_peripheral
        }
        if entity.embedding:
            properties['embedding'] = entity.embedding
        return self.create_node('Entity', properties)
        
    def create_insight(self, insight: Insight) -> str:
        """Create an insight node."""
        properties = {
            'id': insight.id,
            'insight_type': insight.insight_type,
            'content': insight.content,
            'confidence_score': insight.confidence_score,
            'extracted_from_segment': insight.extracted_from_segment,
            'is_bridge_insight': insight.is_bridge_insight,
            'timestamp': insight.timestamp
        }
        return self.create_node('Insight', properties)
        
    def create_quote(self, quote: Quote) -> str:
        """Create a quote node."""
        properties = {
            'id': quote.id,
            'text': quote.text,
            'speaker': quote.speaker,
            'quote_type': quote.quote_type,
            'context': quote.context,
            'timestamp': quote.timestamp,
            'segment_id': quote.segment_id
        }
        return self.create_node('Quote', properties)