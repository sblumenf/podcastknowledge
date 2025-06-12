"""Multi-database graph storage service for podcast-specific Neo4j databases."""

from typing import Dict, Any, Optional
import logging
from contextlib import contextmanager

from src.storage.graph_storage import GraphStorageService
from src.config.podcast_databases import PodcastDatabaseConfig
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


class MultiDatabaseGraphStorage:
    """Graph storage service that routes to different databases based on podcast ID."""
    
    def __init__(self, uri: str, username: str, password: str,
                 config_path: Optional[str] = None, **kwargs):
        """Initialize multi-database graph storage.
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            config_path: Path to podcast configuration file
            **kwargs: Additional arguments passed to GraphStorageService
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.default_kwargs = kwargs
        
        # Load podcast database configuration
        self.podcast_config = PodcastDatabaseConfig(config_path)
        
        # Cache of database connections
        self._connections: Dict[str, GraphStorageService] = {}
        
        # Current podcast context
        self._current_podcast_id: Optional[str] = None
        
    def set_podcast_context(self, podcast_id: str) -> None:
        """Set the current podcast context for database routing.
        
        Args:
            podcast_id: Podcast identifier
        """
        self._current_podcast_id = podcast_id
        logger.info(f"Set podcast context to: {podcast_id}")
        
    def get_connection(self, podcast_id: Optional[str] = None) -> GraphStorageService:
        """Get database connection for a specific podcast.
        
        Args:
            podcast_id: Podcast identifier (uses current context if not provided)
            
        Returns:
            GraphStorageService instance for the podcast's database
        """
        # Use provided podcast_id or fall back to current context
        pid = podcast_id or self._current_podcast_id or 'unknown_podcast'
        
        # Check cache
        if pid in self._connections:
            return self._connections[pid]
            
        # Create new connection
        database_name = self.podcast_config.get_database_for_podcast(pid)
        
        # Create connection with podcast-specific database
        connection_kwargs = self.default_kwargs.copy()
        connection_kwargs['database'] = database_name
        
        logger.info(f"Creating connection for podcast '{pid}' to database '{database_name}'")
        
        connection = GraphStorageService(
            uri=self.uri,
            username=self.username,
            password=self.password,
            **connection_kwargs
        )
        
        # Initialize connection
        connection.connect()
        
        # Cache connection
        self._connections[pid] = connection
        
        return connection
        
    @contextmanager
    def podcast_context(self, podcast_id: str):
        """Context manager for podcast-specific operations.
        
        Args:
            podcast_id: Podcast identifier
        """
        old_podcast_id = self._current_podcast_id
        try:
            self.set_podcast_context(podcast_id)
            yield self.get_connection(podcast_id)
        finally:
            self._current_podcast_id = old_podcast_id
            
    # Delegate methods to current podcast connection
    def store_podcast(self, podcast: Any) -> None:
        """Store podcast in appropriate database."""
        podcast_id = getattr(podcast, 'podcast_id', None) or self._current_podcast_id
        connection = self.get_connection(podcast_id)
        connection.store_podcast(podcast)
        
    def store_episode(self, episode: Any) -> None:
        """Store episode in appropriate database."""
        podcast_id = getattr(episode, 'podcast_id', None) or self._current_podcast_id
        connection = self.get_connection(podcast_id)
        connection.store_episode(episode)
        
    def store_segment(self, segment: Any) -> None:
        """Store segment in appropriate database."""
        podcast_id = getattr(segment, 'podcast_id', None) or self._current_podcast_id
        connection = self.get_connection(podcast_id)
        connection.store_segment(segment)
        
    def store_entities(self, entities: list, episode_id: str, 
                      segment_id: Optional[str] = None) -> None:
        """Store entities in appropriate database."""
        # Extract podcast_id from episode_id if possible
        podcast_id = self._current_podcast_id
        if not podcast_id and entities:
            # Try to get from first entity
            podcast_id = getattr(entities[0], 'podcast_id', None)
            
        connection = self.get_connection(podcast_id)
        connection.store_entities(entities, episode_id, segment_id)
        
    def store_concepts(self, concepts: list, episode_id: str,
                      segment_id: Optional[str] = None) -> None:
        """Store concepts in appropriate database."""
        connection = self.get_connection()
        connection.store_concepts(concepts, episode_id, segment_id)
        
    def store_claims(self, claims: list, episode_id: str,
                    segment_id: Optional[str] = None) -> None:
        """Store claims in appropriate database."""
        connection = self.get_connection()
        connection.store_claims(claims, episode_id, segment_id)
        
    def store_extraction_results(self, results: Dict[str, Any]) -> None:
        """Store extraction results in appropriate database."""
        # Try to extract podcast_id from results
        podcast_id = results.get('podcast_id') or self._current_podcast_id
        connection = self.get_connection(podcast_id)
        connection.store_extraction_results(results)
        
    def clear_database(self, podcast_id: Optional[str] = None) -> None:
        """Clear a specific podcast database."""
        connection = self.get_connection(podcast_id)
        connection.clear_database()
        
    def get_database_stats(self, podcast_id: Optional[str] = None) -> Dict[str, int]:
        """Get statistics for a specific podcast database."""
        connection = self.get_connection(podcast_id)
        return connection.get_database_stats()
        
    def close(self) -> None:
        """Close all database connections."""
        for podcast_id, connection in self._connections.items():
            try:
                connection.close()
                logger.info(f"Closed connection for podcast: {podcast_id}")
            except Exception as e:
                logger.error(f"Error closing connection for podcast {podcast_id}: {e}")
                
        self._connections.clear()
        
    def create_indexes(self, podcast_id: Optional[str] = None) -> None:
        """Create indexes for a specific podcast database."""
        connection = self.get_connection(podcast_id)
        connection.create_indexes()
        
    def verify_connection(self, podcast_id: Optional[str] = None) -> bool:
        """Verify connection to a specific podcast database."""
        try:
            connection = self.get_connection(podcast_id)
            return connection.verify_connection()
        except Exception as e:
            logger.error(f"Failed to verify connection for podcast {podcast_id}: {e}")
            return False
            
    def list_databases(self) -> Dict[str, str]:
        """List all configured podcast databases.
        
        Returns:
            Dictionary mapping podcast IDs to database names
        """
        return self.podcast_config.list_podcasts()
        
    def add_podcast_database(self, podcast_id: str, database_name: str,
                           podcast_name: str, description: str = "") -> None:
        """Add a new podcast database configuration.
        
        Args:
            podcast_id: Unique podcast identifier
            database_name: Neo4j database name
            podcast_name: Human-readable podcast name
            description: Podcast description
        """
        config = {
            'database': database_name,
            'name': podcast_name,
            'description': description,
            'settings': {
                'batch_size': 50,
                'parallel_workers': 2
            }
        }
        
        self.podcast_config.add_podcast(podcast_id, config)
        self.podcast_config.save_config()
        
        logger.info(f"Added podcast database config: {podcast_id} -> {database_name}")