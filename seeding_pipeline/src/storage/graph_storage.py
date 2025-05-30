"""Direct graph storage service for Neo4j interaction."""

import logging
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
import threading
from datetime import datetime

from src.core.exceptions import ProviderError, ConnectionError
from src.core.models import Podcast, Episode, Segment

logger = logging.getLogger(__name__)


class GraphStorageService:
    """Direct Neo4j graph storage service for schemaless operations."""
    
    def __init__(self, uri: str, username: str, password: str, 
                 database: str = 'neo4j', pool_size: int = 50):
        """Initialize graph storage service.
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: neo4j)
            pool_size: Connection pool size (default: 50)
        """
        if not uri:
            raise ValueError("Neo4j URI is required")
        if not username or not password:
            raise ValueError("Neo4j username and password are required")
            
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.pool_size = pool_size
        self._driver = None
        self._lock = threading.Lock()
        
        # Performance monitoring
        self._extraction_times = []
        self._entity_counts = []
        self._relationship_counts = []
        
    def _ensure_driver(self) -> None:
        """Ensure Neo4j driver is initialized."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError:
                raise ImportError(
                    "neo4j is not installed. "
                    "Install with: pip install neo4j"
                )
                
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=self.pool_size,
                max_connection_lifetime=3600,
                connection_acquisition_timeout=30.0
            )
            logger.info(f"Initialized Neo4j driver for {self.uri}")
            
    def connect(self) -> None:
        """Verify connection to Neo4j."""
        self._ensure_driver()
        
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run("RETURN 'Connected' AS status")
                status = result.single()["status"]
                logger.info(f"Neo4j connection verified: {status}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")
            
    def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            try:
                self._driver.close()
                self._driver = None
                logger.info("Disconnected from Neo4j")
            except Exception as e:
                logger.warning(f"Error closing Neo4j connection: {e}")
                
    @contextmanager
    def session(self):
        """Create a Neo4j session context manager."""
        self._ensure_driver()
        
        session = None
        try:
            session = self._driver.session(database=self.database)
            yield session
        finally:
            if session:
                session.close()
                
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a node in Neo4j.
        
        Args:
            node_type: Type/label of the node
            properties: Node properties
            
        Returns:
            Node ID
        """
        with self._lock:
            with self.session() as session:
                # Ensure node has an ID
                if 'id' not in properties:
                    raise ValueError(f"Node of type {node_type} must have an 'id' property")
                    
                # Build property string for Cypher
                prop_strings = []
                params = {}
                for key, value in properties.items():
                    if value is not None:
                        prop_strings.append(f"{key}: ${key}")
                        params[key] = value
                        
                prop_string = "{" + ", ".join(prop_strings) + "}"
                
                # Create node
                cypher = f"CREATE (n:{node_type} {prop_string}) RETURN n.id AS id"
                
                try:
                    result = session.run(cypher, **params)
                    return result.single()["id"]
                except Exception as e:
                    raise ProviderError("neo4j", f"Failed to create {node_type} node: {e}")
                    
    def create_relationship(self, source_id: str, target_id: str, 
                          rel_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Create a relationship between nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            rel_type: Relationship type
            properties: Optional relationship properties
        """
        with self._lock:
            with self.session() as session:
                # Build property string if properties provided
                if properties:
                    prop_strings = []
                    params = {
                        'source_id': source_id,
                        'target_id': target_id
                    }
                    for key, value in properties.items():
                        if value is not None:
                            prop_strings.append(f"{key}: ${key}")
                            params[key] = value
                    prop_string = " {" + ", ".join(prop_strings) + "}"
                else:
                    prop_string = ""
                    params = {'source_id': source_id, 'target_id': target_id}
                    
                # Create relationship
                cypher = f"""
                MATCH (a {{id: $source_id}})
                MATCH (b {{id: $target_id}})
                CREATE (a)-[r:{rel_type}{prop_string}]->(b)
                RETURN type(r) AS rel_type
                """
                
                try:
                    result = session.run(cypher, **params)
                    result.single()  # Consume result
                except Exception as e:
                    raise ProviderError(
                        "neo4j",
                        f"Failed to create relationship {rel_type} "
                        f"between {source_id} and {target_id}: {e}"
                    )
                    
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query.
        
        Args:
            cypher: Cypher query string
            parameters: Optional query parameters
            
        Returns:
            List of result dictionaries
        """
        with self.session() as session:
            try:
                if parameters:
                    result = session.run(cypher, **parameters)
                else:
                    result = session.run(cypher)
                    
                # Convert to list of dictionaries
                records = []
                for record in result:
                    records.append(dict(record))
                return records
                
            except Exception as e:
                raise ProviderError("neo4j", f"Query execution failed: {e}")
                
    def process_segment_schemaless(self, segment: Segment, episode: Episode, 
                                 podcast: Podcast) -> Dict[str, Any]:
        """Process a segment for schemaless extraction.
        
        This is a simplified version that creates basic nodes and relationships
        without complex pipeline processing.
        
        Args:
            segment: Segment to process
            episode: Episode containing the segment
            podcast: Podcast containing the episode
            
        Returns:
            Processing results
        """
        start_time = datetime.now()
        
        try:
            # Create podcast node if not exists
            with self.session() as session:
                session.run("""
                    MERGE (p:Podcast {id: $id})
                    ON CREATE SET p.title = $title, p.description = $description
                """, id=podcast.id, title=podcast.title, description=podcast.description)
                
                # Create episode node if not exists
                session.run("""
                    MERGE (e:Episode {id: $id})
                    ON CREATE SET e.title = $title, e.description = $description,
                                  e.published_date = $published_date
                    WITH e
                    MATCH (p:Podcast {id: $podcast_id})
                    MERGE (p)-[:HAS_EPISODE]->(e)
                """, id=episode.id, title=episode.title, description=episode.description,
                    published_date=episode.published_date, podcast_id=podcast.id)
                
                # Create segment node
                segment_id = f"{episode.id}_seg_{segment.start_time}"
                session.run("""
                    CREATE (s:Segment {
                        id: $id,
                        text: $text,
                        start_time: $start_time,
                        end_time: $end_time,
                        speaker: $speaker
                    })
                    WITH s
                    MATCH (e:Episode {id: $episode_id})
                    CREATE (e)-[:HAS_SEGMENT]->(s)
                """, id=segment_id, text=segment.text, start_time=segment.start_time,
                    end_time=segment.end_time, speaker=segment.speaker, episode_id=episode.id)
                
            # Record performance metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self._extraction_times.append(processing_time)
            
            return {
                'segment_id': segment_id,
                'entities': 0,  # Simplified - no entity extraction
                'relationships': 0,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error(f"Failed to process segment: {e}")
            raise ProviderError("neo4j", f"Segment processing failed: {e}")
            
    def setup_schema(self) -> None:
        """Set up basic indexes and constraints."""
        with self.session() as session:
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Podcast) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint already exists or failed: {e}")
                    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.
        
        Returns:
            Performance statistics
        """
        if not self._extraction_times:
            return {
                'avg_extraction_time': 0,
                'total_segments': 0,
                'total_entities': 0,
                'total_relationships': 0
            }
            
        return {
            'avg_extraction_time': sum(self._extraction_times) / len(self._extraction_times),
            'total_segments': len(self._extraction_times),
            'total_entities': sum(self._entity_counts) if self._entity_counts else 0,
            'total_relationships': sum(self._relationship_counts) if self._relationship_counts else 0
        }
        
    def health_check(self) -> Dict[str, Any]:
        """Check service health.
        
        Returns:
            Health status dictionary
        """
        try:
            self.connect()
            
            # Try a simple query
            with self.session() as session:
                result = session.run("MATCH (n) RETURN count(n) AS count LIMIT 1")
                count = result.single()["count"]
                
            return {
                'healthy': True,
                'service': 'GraphStorageService',
                'database': self.database,
                'node_count': count
            }
        except Exception as e:
            return {
                'healthy': False,
                'service': 'GraphStorageService',
                'database': self.database,
                'error': str(e)
            }