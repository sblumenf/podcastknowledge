"""Direct graph storage service for Neo4j interaction with error resilience."""

from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import logging
import threading
import time
from queue import Queue, Empty

from src.core.exceptions import ProviderError, ConnectionError
from src.core.models import Podcast, Episode, Segment
from src.utils.retry import retry, ExponentialBackoff
from src.utils.logging import get_logger
from src.utils.logging import (
    trace_operation,
    log_performance_metric,
    ProcessingTraceLogger
)
from src.monitoring import get_pipeline_metrics

logger = get_logger(__name__)


class GraphStorageService:
    """Direct Neo4j graph storage service for schemaless operations."""
    
    def __init__(self, uri: str, username: str, password: str, 
                 database: str = 'neo4j', pool_size: int = 50,
                 max_retries: int = 5, connection_timeout: float = 30.0):
        """Initialize graph storage service with resilience features.
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: neo4j)
            pool_size: Connection pool size (default: 50)
            max_retries: Maximum retry attempts (default: 5)
            connection_timeout: Connection timeout in seconds (default: 30.0)
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
        self.max_retries = max_retries
        self.connection_timeout = connection_timeout
        self._driver = None
        self._lock = threading.Lock()
        
        # Resilience features
        self._backoff = ExponentialBackoff(base=2.0, max_delay=8.0)
        self._failed_writes = Queue(maxsize=1000)  # Queue for failed write operations
        self._connection_healthy = True
        self._last_health_check = None
        self._health_check_interval = 30  # seconds
        
        # Performance monitoring
        self._extraction_times = []
        self._entity_counts = []
        self._relationship_counts = []
        
        # Query cache for frequently accessed data
        self._query_cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_lock = threading.Lock()
        
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
                connection_acquisition_timeout=self.connection_timeout,
                connection_timeout=self.connection_timeout,
                encrypted=False  # For local development
            )
            logger.info(f"Initialized Neo4j driver for {self.uri}")
            
    def connect(self) -> None:
        """Verify connection to Neo4j with retry logic."""
        self._backoff.reset()
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                self._ensure_driver()
                
                with self._driver.session(database=self.database) as session:
                    result = session.run("RETURN 'Connected' AS status")
                    status = result.single()["status"]
                    logger.info(f"Neo4j connection verified: {status}")
                    self._connection_healthy = True
                    self._last_health_check = datetime.now()
                    return
                    
            except Exception as e:
                last_exception = e
                self._connection_healthy = False
                
                if attempt < self.max_retries - 1:
                    delay = self._backoff.get_next_delay()
                    logger.warning(
                        f"Connection attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to connect after {self.max_retries} attempts")
                    
        raise ConnectionError(f"Failed to connect to Neo4j after {self.max_retries} attempts: {last_exception}")
            
    def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            try:
                self._driver.close()
                self._driver = None
                logger.info("Disconnected from Neo4j")
            except Exception as e:
                logger.warning(f"Error closing Neo4j connection: {e}")
                
    def close(self) -> None:
        """Close Neo4j connection (alias for disconnect)."""
        self.disconnect()
                
    def _check_health(self) -> bool:
        """Check if connection is healthy."""
        if self._last_health_check:
            time_since_check = (datetime.now() - self._last_health_check).total_seconds()
            if time_since_check < self._health_check_interval and self._connection_healthy:
                return True
        
        try:
            with self._driver.session(database=self.database) as session:
                session.run("RETURN 1").single()
                self._connection_healthy = True
                self._last_health_check = datetime.now()
                return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._connection_healthy = False
            return False
    
    def _queue_failed_write(self, operation: Dict[str, Any]) -> None:
        """Queue a failed write operation for retry."""
        try:
            self._failed_writes.put_nowait(operation)
            logger.info(f"Queued failed write operation: {operation.get('type', 'unknown')}")
        except:
            logger.warning("Failed write queue is full, dropping operation")
    
    def process_failed_writes(self) -> int:
        """Process queued failed write operations."""
        processed = 0
        
        while not self._failed_writes.empty():
            if not self._connection_healthy:
                break
                
            try:
                operation = self._failed_writes.get_nowait()
                # Re-execute the operation
                if self._execute_write_operation(operation):
                    processed += 1
            except Empty:
                break
            except Exception as e:
                logger.error(f"Error processing failed write: {e}")
                
        if processed > 0:
            logger.info(f"Processed {processed} failed write operations")
            
        return processed
    
    def _execute_write_operation(self, operation: Dict[str, Any]) -> bool:
        """Execute a write operation with error handling."""
        # This is a placeholder - actual implementation would depend on operation type
        # For now, we'll just log it
        logger.debug(f"Executing write operation: {operation}")
        return True
    
    @contextmanager
    def session(self):
        """Create a Neo4j session context manager with health checks."""
        self._ensure_driver()
        
        # Perform health check
        if not self._connection_healthy and not self._check_health():
            logger.warning("Connection unhealthy, attempting to process writes in degraded mode")
            # In degraded mode, we queue the write for later
            yield None
            return
        
        session = None
        try:
            session = self._driver.session(database=self.database)
            yield session
        except Exception as e:
            logger.error(f"Session error: {e}")
            self._connection_healthy = False
            raise
        finally:
            if session:
                session.close()
    
    def get_session(self):
        """Get a Neo4j session context manager (alias for session)."""
        return self.session()
                
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a node in Neo4j with resilience.
        
        Args:
            node_type: Type/label of the node
            properties: Node properties
            
        Returns:
            Node ID
        """
        with self._lock:
            # Ensure node has an ID
            if 'id' not in properties:
                raise ValueError(f"Node of type {node_type} must have an 'id' property")
            
            # Try with retry logic
            self._backoff.reset()
            last_exception = None
            
            for attempt in range(self.max_retries):
                try:
                    with self.session() as session:
                        if session is None:
                            # Connection unhealthy, queue for later
                            self._queue_failed_write({
                                'type': 'create_node',
                                'node_type': node_type,
                                'properties': properties
                            })
                            logger.warning(f"Queued node creation for {node_type} due to unhealthy connection")
                            return properties['id']  # Return the ID to allow processing to continue
                        
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
                        
                        result = session.run(cypher, **params)
                        return result.single()["id"]
                        
                except Exception as e:
                    last_exception = e
                    
                    if attempt < self.max_retries - 1:
                        delay = self._backoff.get_next_delay()
                        logger.warning(
                            f"Node creation attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        # Final attempt failed, queue for later
                        self._queue_failed_write({
                            'type': 'create_node',
                            'node_type': node_type,
                            'properties': properties
                        })
                        logger.error(f"Failed to create {node_type} node after {self.max_retries} attempts, queued for retry")
                        return properties['id']  # Allow processing to continue
                        
            raise ProviderError("neo4j", f"Failed to create {node_type} node: {last_exception}")
                    
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
                    
    @trace_operation("neo4j_query")
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None,
              use_cache: bool = False, cache_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query with optional caching.
        
        Args:
            cypher: Cypher query string
            parameters: Optional query parameters
            use_cache: Whether to use caching for this query
            cache_key: Optional custom cache key (auto-generated if not provided)
            
        Returns:
            List of result dictionaries
        """
        start_time = time.time()
        
        # Check cache if enabled
        if use_cache:
            cache_key = cache_key or self._generate_cache_key(cypher, parameters)
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                log_performance_metric(
                    "neo4j_query_cache_hit",
                    0.001,  # Cache hit is very fast
                    success=True,
                    metadata={'cached': 'true'}
                )
                return cached_result
        
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
                
                # Cache result if enabled
                if use_cache:
                    self._cache_result(cache_key, records)
                
                # Log query performance
                query_time = time.time() - start_time
                log_performance_metric(
                    "neo4j_query",
                    query_time,
                    success=True,
                    metadata={
                        'cached': 'false',
                        'result_count': str(len(records))
                    }
                )
                
                # Record database metrics
                metrics = get_pipeline_metrics()
                metrics.record_db_operation("query", query_time, success=True)
                
                return records
                
            except Exception as e:
                # Record failed database operation
                query_time = time.time() - start_time
                metrics = get_pipeline_metrics()
                metrics.record_db_operation("query", query_time, success=False)
                
                raise ProviderError("neo4j", f"Query execution failed: {e}")
    
    def _generate_cache_key(self, cypher: str, parameters: Optional[Dict[str, Any]]) -> str:
        """Generate cache key from query and parameters."""
        import hashlib
        key_str = cypher
        if parameters:
            # Sort parameters for consistent hashing
            param_str = json.dumps(parameters, sort_keys=True)
            key_str += param_str
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached query result if available and not expired."""
        with self._cache_lock:
            if cache_key in self._query_cache:
                cached = self._query_cache[cache_key]
                if time.time() - cached['timestamp'] < self._cache_ttl:
                    logger.debug(f"Cache hit for query: {cache_key}")
                    return cached['result']
                else:
                    # Expired
                    del self._query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: List[Dict[str, Any]]):
        """Cache query result with timestamp."""
        with self._cache_lock:
            self._query_cache[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }
            
            # Clean old entries if cache is getting large
            if len(self._query_cache) > 1000:
                self._clean_expired_cache()
    
    def _clean_expired_cache(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, cached in self._query_cache.items():
            if current_time - cached['timestamp'] >= self._cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._query_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
                
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
            # Constraints for uniqueness
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Podcast) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
                # "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE",  # REMOVED - only MeaningfulUnit
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MeaningfulUnit) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (en:Entity) REQUIRE en.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE"
            ]
            
            # Indexes for common lookups
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (p:Podcast) ON (p.title)",
                "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.title)",
                "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.published_date)",
                "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.youtube_url)",
                # "CREATE INDEX IF NOT EXISTS FOR (s:Segment) ON (s.speaker)",  # REMOVED - only MeaningfulUnit
                # "CREATE INDEX IF NOT EXISTS FOR (s:Segment) ON (s.start_time)",  # REMOVED - only MeaningfulUnit
                "CREATE INDEX IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.start_time)",
                "CREATE INDEX IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.speaker_distribution)",
                "CREATE INDEX IF NOT EXISTS FOR (en:Entity) ON (en.name)",
                "CREATE INDEX IF NOT EXISTS FOR (en:Entity) ON (en.type)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:MENTIONED_IN]-() ON (r.confidence)"
            ]
            
            # Create constraints
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint already exists or failed: {e}")
            
            # Create indexes
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"Created index: {index}")
                except Exception as e:
                    logger.warning(f"Index already exists or failed: {e}")
                    
    @trace_operation("neo4j_create_nodes_bulk")
    def create_nodes_bulk(self, node_type: str, nodes_data: List[Dict[str, Any]]) -> List[str]:
        """Create multiple nodes in a single transaction using UNWIND.
        
        Args:
            node_type: Type/label of the nodes
            nodes_data: List of node properties dictionaries
            
        Returns:
            List of created node IDs
        """
        if not nodes_data:
            return []
        
        start_time = time.time()
        node_count = len(nodes_data)
        
        # Ensure all nodes have IDs
        for node in nodes_data:
            if 'id' not in node:
                raise ValueError(f"All nodes of type {node_type} must have an 'id' property")
        
        with self._lock:
            try:
                with self.session() as session:
                    # Use UNWIND for bulk creation
                    cypher = f"""
                    UNWIND $nodes AS node
                    CREATE (n:{node_type})
                    SET n = node
                    RETURN n.id AS id
                    """
                    
                    result = session.run(cypher, nodes=nodes_data)
                    created_ids = [record["id"] for record in result]
                    
                    # Log performance metrics
                    operation_time = time.time() - start_time
                    log_performance_metric(
                        "neo4j_create_nodes_bulk",
                        operation_time,
                        success=True,
                        metadata={
                            'node_type': node_type,
                            'node_count': str(node_count)
                        }
                    )
                    
                    # Record database metrics
                    metrics = get_pipeline_metrics()
                    metrics.record_db_operation("bulk_create_nodes", operation_time, success=True)
                    
                    return created_ids
                    
            except Exception as e:
                logger.error(f"Bulk node creation failed for {node_type}: {e}")
                
                # Log bulk failure metric
                log_performance_metric(
                    "neo4j_create_nodes_bulk",
                    time.time() - start_time,
                    success=False,
                    metadata={
                        'node_type': node_type,
                        'node_count': str(node_count),
                        'error': str(type(e).__name__)
                    }
                )
                
                # Fall back to individual creation
                ids = []
                for node_data in nodes_data:
                    try:
                        node_id = self.create_node(node_type, node_data)
                        ids.append(node_id)
                    except Exception as node_e:
                        logger.error(f"Failed to create individual node: {node_e}")
                        ids.append(node_data.get('id', 'unknown'))
                return ids
    
    @trace_operation("neo4j_create_relationships_bulk")
    def create_relationships_bulk(self, relationships: List[Dict[str, Any]]) -> int:
        """Create multiple relationships in a single transaction using UNWIND.
        
        Supports all node types including MeaningfulUnit as source or target.
        
        Args:
            relationships: List of relationship dictionaries with:
                - source_id: Source node ID (any node type)
                - target_id: Target node ID (any node type including MeaningfulUnit)
                - rel_type: Relationship type (e.g., MENTIONED_IN, EXTRACTED_FROM)
                - properties: Optional relationship properties
                
        Returns:
            Number of relationships created
        """
        if not relationships:
            return 0
        
        with self._lock:
            try:
                with self.session() as session:
                    # Group by relationship type for more efficient processing
                    rel_by_type = {}
                    for rel in relationships:
                        rel_type = rel['rel_type']
                        if rel_type not in rel_by_type:
                            rel_by_type[rel_type] = []
                        rel_by_type[rel_type].append(rel)
                    
                    total_created = 0
                    
                    # Process each relationship type
                    for rel_type, rels in rel_by_type.items():
                        cypher = f"""
                        UNWIND $rels AS rel
                        MATCH (a {{id: rel.source_id}})
                        MATCH (b {{id: rel.target_id}})
                        CREATE (a)-[r:{rel_type}]->(b)
                        SET r = rel.properties
                        RETURN count(r) AS count
                        """
                        
                        # Prepare data
                        rel_data = [
                            {
                                'source_id': r['source_id'],
                                'target_id': r['target_id'],
                                'properties': r.get('properties', {})
                            }
                            for r in rels
                        ]
                        
                        result = session.run(cypher, rels=rel_data)
                        count = result.single()["count"]
                        total_created += count
                    
                    return total_created
                    
            except Exception as e:
                logger.error(f"Bulk relationship creation failed: {e}")
                # Fall back to individual creation
                created = 0
                for rel in relationships:
                    try:
                        self.create_relationship(
                            rel['source_id'],
                            rel['target_id'],
                            rel['rel_type'],
                            rel.get('properties')
                        )
                        created += 1
                    except Exception as rel_e:
                        logger.error(f"Failed to create individual relationship: {rel_e}")
                return created
    
    def merge_nodes_bulk(self, node_type: str, nodes_data: List[Dict[str, Any]], 
                        merge_keys: List[str]) -> List[str]:
        """Merge multiple nodes in a single transaction using UNWIND.
        
        Args:
            node_type: Type/label of the nodes
            nodes_data: List of node properties dictionaries
            merge_keys: Keys to use for matching existing nodes
            
        Returns:
            List of node IDs (existing or created)
        """
        if not nodes_data:
            return []
        
        with self._lock:
            try:
                with self.session() as session:
                    # Build MERGE clause with specified keys
                    merge_props = ", ".join([f"{key}: node.{key}" for key in merge_keys])
                    
                    cypher = f"""
                    UNWIND $nodes AS node
                    MERGE (n:{node_type} {{{merge_props}}})
                    ON CREATE SET n = node
                    ON MATCH SET n += node
                    RETURN n.id AS id
                    """
                    
                    result = session.run(cypher, nodes=nodes_data)
                    return [record["id"] for record in result]
                    
            except Exception as e:
                logger.error(f"Bulk node merge failed for {node_type}: {e}")
                raise ProviderError("neo4j", f"Bulk merge failed: {e}")
    
    def create_meaningful_unit(self, unit_data: Dict[str, Any], episode_id: str) -> str:
        """Create a MeaningfulUnit node and link it to an episode.
        
        Args:
            unit_data: Dictionary containing:
                - id: Unique identifier
                - text: Full consolidated text
                - start_time: Start timestamp (adjusted for YouTube)
                - end_time: End timestamp
                - summary: Brief summary of content
                - speaker_distribution: Dict of speaker percentages
                - unit_type: Type of unit (e.g., "topic_discussion", "q&a")
                - themes: List of related themes
                - segment_indices: List of original segment IDs
            episode_id: ID of the episode this unit belongs to
            
        Returns:
            ID of the created MeaningfulUnit
            
        Raises:
            ProviderError: If creation fails
        """
        # Validate required fields
        required_fields = ['id', 'text', 'start_time', 'end_time']
        for field in required_fields:
            if field not in unit_data:
                raise ValueError(f"MeaningfulUnit missing required field: {field}")
        
        with self._lock:
            try:
                with self.session() as session:
                    # Convert speaker_distribution dict to JSON string for storage
                    if 'speaker_distribution' in unit_data and isinstance(unit_data['speaker_distribution'], dict):
                        unit_data['speaker_distribution'] = json.dumps(unit_data['speaker_distribution'])
                    
                    # Convert themes list to JSON string for storage
                    if 'themes' in unit_data and isinstance(unit_data['themes'], list):
                        unit_data['themes'] = json.dumps(unit_data['themes'])
                    
                    # Convert segment_indices list to JSON string for storage
                    if 'segment_indices' in unit_data and isinstance(unit_data['segment_indices'], list):
                        unit_data['segment_indices'] = json.dumps(unit_data['segment_indices'])
                    
                    # Create MeaningfulUnit node and relationship to episode
                    cypher = """
                    CREATE (m:MeaningfulUnit {
                        id: $id,
                        text: $text,
                        start_time: $start_time,
                        end_time: $end_time,
                        summary: $summary,
                        speaker_distribution: $speaker_distribution,
                        unit_type: $unit_type,
                        themes: $themes,
                        segment_indices: $segment_indices
                    })
                    WITH m
                    MATCH (e:Episode {id: $episode_id})
                    CREATE (m)-[:PART_OF]->(e)
                    RETURN m.id AS id
                    """
                    
                    # Set defaults for optional fields
                    params = {
                        'id': unit_data['id'],
                        'text': unit_data['text'],
                        'start_time': unit_data['start_time'],
                        'end_time': unit_data['end_time'],
                        'summary': unit_data.get('summary', ''),
                        'speaker_distribution': unit_data.get('speaker_distribution', '{}'),
                        'unit_type': unit_data.get('unit_type', 'unknown'),
                        'themes': unit_data.get('themes', '[]'),
                        'segment_indices': unit_data.get('segment_indices', '[]'),
                        'episode_id': episode_id
                    }
                    
                    result = session.run(cypher, **params)
                    record = result.single()
                    
                    if not record:
                        raise ProviderError("neo4j", "Failed to create MeaningfulUnit - no result returned")
                    
                    unit_id = record['id']
                    logger.info(f"Created MeaningfulUnit {unit_id} for episode {episode_id}")
                    
                    return unit_id
                    
            except Exception as e:
                logger.error(f"Failed to create MeaningfulUnit: {e}")
                raise ProviderError("neo4j", f"MeaningfulUnit creation failed: {e}")
    
    def create_meaningful_unit_relationship(self, source_id: str, unit_id: str, 
                                          rel_type: str = "MENTIONED_IN", 
                                          properties: Optional[Dict[str, Any]] = None) -> None:
        """Create a relationship from an entity/insight/quote to a MeaningfulUnit.
        
        This is a convenience method that wraps create_relationship to make it clear
        that MeaningfulUnits are supported as relationship targets.
        
        Args:
            source_id: ID of the source node (Entity, Insight, Quote, etc.)
            unit_id: ID of the target MeaningfulUnit
            rel_type: Relationship type (default: MENTIONED_IN)
            properties: Optional relationship properties
            
        Common relationship types:
            - MENTIONED_IN: Entity mentioned in MeaningfulUnit
            - EXTRACTED_FROM: Insight/Quote extracted from MeaningfulUnit
        """
            
        # Use the generic create_relationship method which works with any node type
        self.create_relationship(source_id, unit_id, rel_type, properties)
        logger.debug(f"Created {rel_type} relationship from {source_id} to MeaningfulUnit {unit_id}")
    
    def create_episode(self, episode_metadata: Dict[str, Any]) -> str:
        """Create or retrieve an episode node in Neo4j.
        
        This method is idempotent - if the episode already exists, it returns the existing ID.
        
        Args:
            episode_metadata: Dictionary containing:
                - episode_id: Unique identifier (required)
                - title: Episode title
                - description: Episode description
                - published_date: Publication date
                - youtube_url: YouTube URL
                - podcast_info: Optional podcast metadata dict
                
        Returns:
            Episode ID
            
        Raises:
            ValueError: If episode_id is missing
            ProviderError: If creation fails
        """
        if 'episode_id' not in episode_metadata:
            raise ValueError("episode_metadata must contain 'episode_id'")
            
        episode_id = episode_metadata['episode_id']
        
        with self._lock:
            try:
                with self.session() as session:
                    # First check if episode already exists
                    check_query = """
                    MATCH (e:Episode {id: $episode_id})
                    RETURN e.id AS id
                    """
                    result = session.run(check_query, episode_id=episode_id)
                    existing = result.single()
                    
                    if existing:
                        logger.debug(f"Episode {episode_id} already exists")
                        return existing['id']
                    
                    # Create new episode
                    episode_data = {
                        'id': episode_id,
                        'title': episode_metadata.get('title', ''),
                        'description': episode_metadata.get('description', ''),
                        'published_date': episode_metadata.get('published_date', ''),
                        'youtube_url': episode_metadata.get('youtube_url', ''),
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # Handle podcast relationship if podcast_info provided
                    podcast_info = episode_metadata.get('podcast_info', {})
                    if podcast_info and 'name' in podcast_info:
                        # Create episode and podcast, link them
                        cypher = """
                        MERGE (p:Podcast {id: $podcast_id})
                        ON CREATE SET p.name = $podcast_name, p.host = $podcast_host
                        CREATE (e:Episode {
                            id: $id,
                            title: $title,
                            description: $description,
                            published_date: $published_date,
                            youtube_url: $youtube_url,
                            created_at: $created_at,
                            updated_at: $updated_at
                        })
                        CREATE (e)-[:PART_OF]->(p)
                        RETURN e.id AS id
                        """
                        params = {
                            **episode_data,
                            'podcast_id': podcast_info['name'],
                            'podcast_name': podcast_info['name'],
                            'podcast_host': podcast_info.get('host', '')
                        }
                    else:
                        # Just create episode
                        cypher = """
                        CREATE (e:Episode {
                            id: $id,
                            title: $title,
                            description: $description,
                            published_date: $published_date,
                            youtube_url: $youtube_url,
                            created_at: $created_at,
                            updated_at: $updated_at
                        })
                        RETURN e.id AS id
                        """
                        params = episode_data
                    
                    result = session.run(cypher, **params)
                    created = result.single()
                    
                    if not created:
                        raise ProviderError("neo4j", "Failed to create episode")
                        
                    logger.info(f"Created episode {episode_id}")
                    return created['id']
                    
            except Exception as e:
                logger.error(f"Failed to create episode: {e}")
                raise ProviderError("neo4j", f"Failed to create episode: {e}") from e
    
    def create_entity(self, entity_data: Dict[str, Any], episode_id: str) -> str:
        """Create an entity node with schema-less type support.
        
        Args:
            entity_data: Dictionary containing:
                - type: Entity type (schema-less, e.g., PERSON, TECHNOLOGY, QUANTUM_RESEARCHER)
                - value: Entity name/value
                - confidence: Confidence score
                - start_time/end_time: Timing information
                - properties: Additional properties dict
            episode_id: ID of the episode this entity belongs to
            
        Returns:
            Generated entity ID
            
        Raises:
            ValueError: If required fields are missing
            ProviderError: If creation fails
        """
        # Validate required fields
        required_fields = ['type', 'value']
        for field in required_fields:
            if field not in entity_data:
                raise ValueError(f"entity_data missing required field: {field}")
        
        # Generate unique ID
        entity_type = entity_data['type'].upper()
        entity_value = entity_data['value']
        entity_hash = hashlib.md5(f"{entity_value}{entity_type}".encode()).hexdigest()[:8]
        entity_id = f"entity_{episode_id}_{entity_type.lower()}_{entity_hash}"
        
        with self._lock:
            try:
                with self.session() as session:
                    # Flatten properties for storage
                    properties = entity_data.get('properties', {})
                    
                    # Build entity node properties
                    node_props = {
                        'id': entity_id,
                        'name': entity_value,
                        'entity_type': entity_type,
                        'confidence': float(entity_data.get('confidence', 0.85)),
                        'start_time': float(entity_data.get('start_time', 0)),
                        'end_time': float(entity_data.get('end_time', 0)),
                        'extraction_method': properties.get('extraction_method', 'unknown'),
                        'description': properties.get('description', ''),
                        'meaningful_unit_id': properties.get('meaningful_unit_id', '')
                    }
                    
                    # Add any additional properties
                    for key, value in properties.items():
                        if key not in node_props and value is not None:
                            # Convert complex types to JSON strings
                            if isinstance(value, (dict, list)):
                                node_props[key] = json.dumps(value)
                            else:
                                node_props[key] = value
                    
                    # Create entity node and relationship to episode
                    cypher = """
                    MATCH (e:Episode {id: $episode_id})
                    CREATE (en:Entity {
                        id: $id,
                        name: $name,
                        entity_type: $entity_type,
                        confidence: $confidence,
                        start_time: $start_time,
                        end_time: $end_time,
                        extraction_method: $extraction_method,
                        description: $description,
                        meaningful_unit_id: $meaningful_unit_id
                    })
                    CREATE (en)-[:MENTIONED_IN {confidence: $confidence}]->(e)
                    RETURN en.id AS id
                    """
                    
                    result = session.run(cypher, episode_id=episode_id, **node_props)
                    created = result.single()
                    
                    if not created:
                        raise ProviderError("neo4j", "Failed to create entity")
                    
                    logger.debug(f"Created entity {entity_id} of type {entity_type}")
                    return created['id']
                    
            except Exception as e:
                logger.error(f"Failed to create entity: {e}")
                raise ProviderError("neo4j", f"Failed to create entity: {e}") from e
    
    def create_quote(self, quote_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str:
        """Create a quote node linked to a MeaningfulUnit.
        
        Args:
            quote_data: Dictionary containing quote information
            episode_id: ID of the episode
            meaningful_unit_id: ID of the source MeaningfulUnit
            
        Returns:
            Generated quote ID
            
        Raises:
            ValueError: If required fields are missing
            ProviderError: If creation fails
        """
        # Validate required fields
        if 'text' not in quote_data:
            raise ValueError("quote_data must contain 'text'")
        
        # Generate unique ID
        quote_text = quote_data['text']
        quote_hash = hashlib.md5(quote_text[:50].encode()).hexdigest()[:8]
        quote_id = f"quote_{episode_id}_{meaningful_unit_id}_{quote_hash}"
        
        with self._lock:
            try:
                with self.session() as session:
                    # Get properties
                    properties = quote_data.get('properties', {})
                    
                    # Build quote node properties
                    node_props = {
                        'id': quote_id,
                        'text': quote_text,
                        'speaker': quote_data.get('speaker', 'Unknown'),
                        'quote_type': quote_data.get('quote_type', 'general'),
                        'importance_score': float(quote_data.get('importance_score', 0.7)),
                        'confidence': float(quote_data.get('confidence', 0.85)),
                        'timestamp_start': float(quote_data.get('timestamp_start', 0)),
                        'timestamp_end': float(quote_data.get('timestamp_end', 0)),
                        'word_count': int(properties.get('word_count', len(quote_text.split()))),
                        'context': properties.get('context', ''),
                        'extraction_method': properties.get('extraction_method', 'unknown')
                    }
                    
                    # Create quote with relationships to both MeaningfulUnit and Episode
                    cypher = """
                    MATCH (e:Episode {id: $episode_id})
                    MATCH (m:MeaningfulUnit {id: $meaningful_unit_id})
                    CREATE (q:Quote {
                        id: $id,
                        text: $text,
                        speaker: $speaker,
                        quote_type: $quote_type,
                        importance_score: $importance_score,
                        confidence: $confidence,
                        timestamp_start: $timestamp_start,
                        timestamp_end: $timestamp_end,
                        word_count: $word_count,
                        context: $context,
                        extraction_method: $extraction_method
                    })
                    CREATE (q)-[:EXTRACTED_FROM]->(m)
                    CREATE (q)-[:PART_OF]->(e)
                    RETURN q.id AS id
                    """
                    
                    result = session.run(
                        cypher,
                        episode_id=episode_id,
                        meaningful_unit_id=meaningful_unit_id,
                        **node_props
                    )
                    created = result.single()
                    
                    if not created:
                        raise ProviderError("neo4j", "Failed to create quote")
                    
                    logger.debug(f"Created quote {quote_id} from unit {meaningful_unit_id}")
                    return created['id']
                    
            except Exception as e:
                logger.error(f"Failed to create quote: {e}")
                raise ProviderError("neo4j", f"Failed to create quote: {e}") from e
    
    def create_insight(self, insight_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str:
        """Create an insight node linked to a MeaningfulUnit.
        
        Args:
            insight_data: Dictionary containing insight information
            episode_id: ID of the episode
            meaningful_unit_id: ID of the source MeaningfulUnit
            
        Returns:
            Generated insight ID
            
        Raises:
            ValueError: If required fields are missing
            ProviderError: If creation fails
        """
        # Validate required fields
        if 'text' not in insight_data:
            raise ValueError("insight_data must contain 'text'")
        
        # Generate unique ID
        insight_text = insight_data['text']
        insight_hash = hashlib.md5(insight_text[:50].encode()).hexdigest()[:8]
        insight_id = f"insight_{episode_id}_{meaningful_unit_id}_{insight_hash}"
        
        with self._lock:
            try:
                with self.session() as session:
                    # Get properties
                    properties = insight_data.get('properties', {})
                    
                    # Build insight node properties
                    node_props = {
                        'id': insight_id,
                        'text': insight_text,
                        'insight_type': insight_data.get('insight_type', 'observation'),
                        'importance': float(insight_data.get('importance', 0.7)),
                        'confidence': float(insight_data.get('confidence', 0.85)),
                        'timestamp': float(insight_data.get('timestamp', 0)),
                        'supporting_evidence': properties.get('supporting_evidence', ''),
                        'extraction_method': properties.get('extraction_method', 'unknown')
                    }
                    
                    # Handle themes list
                    themes = properties.get('themes', [])
                    if themes:
                        node_props['themes'] = json.dumps(themes)
                    
                    # Create insight with relationships to both MeaningfulUnit and Episode
                    cypher = """
                    MATCH (e:Episode {id: $episode_id})
                    MATCH (m:MeaningfulUnit {id: $meaningful_unit_id})
                    CREATE (i:Insight {
                        id: $id,
                        text: $text,
                        insight_type: $insight_type,
                        importance: $importance,
                        confidence: $confidence,
                        timestamp: $timestamp,
                        supporting_evidence: $supporting_evidence,
                        extraction_method: $extraction_method
                    })
                    CREATE (i)-[:EXTRACTED_FROM]->(m)
                    CREATE (i)-[:PART_OF]->(e)
                    RETURN i.id AS id
                    """
                    
                    result = session.run(
                        cypher,
                        episode_id=episode_id,
                        meaningful_unit_id=meaningful_unit_id,
                        **node_props
                    )
                    created = result.single()
                    
                    if not created:
                        raise ProviderError("neo4j", "Failed to create insight")
                    
                    logger.debug(f"Created insight {insight_id} from unit {meaningful_unit_id}")
                    return created['id']
                    
            except Exception as e:
                logger.error(f"Failed to create insight: {e}")
                raise ProviderError("neo4j", f"Failed to create insight: {e}") from e
    
    def create_sentiment(self, sentiment_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str:
        """Create a sentiment analysis node linked to a MeaningfulUnit.
        
        Args:
            sentiment_data: Dictionary containing sentiment analysis results
            episode_id: ID of the episode
            meaningful_unit_id: ID of the analyzed MeaningfulUnit
            
        Returns:
            Generated sentiment ID
            
        Raises:
            ProviderError: If creation fails
        """
        # Generate unique ID
        sentiment_id = f"sentiment_{episode_id}_{meaningful_unit_id}"
        
        with self._lock:
            try:
                with self.session() as session:
                    # Build sentiment node properties
                    node_props = {
                        'id': sentiment_id,
                        'polarity': sentiment_data.get('overall_polarity', 'neutral'),
                        'score': float(sentiment_data.get('overall_score', 0.0)),
                        'energy_level': float(sentiment_data.get('energy_level', 0.5)),
                        'engagement_level': float(sentiment_data.get('engagement_level', 0.5)),
                        'sentiment_flow': sentiment_data.get('sentiment_flow', 'stable'),
                        'interaction_harmony': float(sentiment_data.get('interaction_harmony', 0.5)),
                        'confidence': float(sentiment_data.get('confidence', 0.85))
                    }
                    
                    # Store complex properties as JSON strings
                    complex_props = ['emotions', 'attitudes', 'speaker_sentiments', 
                                   'emotional_moments', 'discovered_sentiments']
                    for prop in complex_props:
                        if prop in sentiment_data and sentiment_data[prop]:
                            node_props[prop] = json.dumps(sentiment_data[prop])
                    
                    # Create sentiment with relationship to MeaningfulUnit
                    cypher = """
                    MATCH (m:MeaningfulUnit {id: $meaningful_unit_id})
                    CREATE (s:Sentiment {
                        id: $id,
                        polarity: $polarity,
                        score: $score,
                        energy_level: $energy_level,
                        engagement_level: $engagement_level,
                        sentiment_flow: $sentiment_flow,
                        interaction_harmony: $interaction_harmony,
                        confidence: $confidence
                    })
                    CREATE (s)-[:ANALYZED_FROM]->(m)
                    RETURN s.id AS id
                    """
                    
                    result = session.run(
                        cypher,
                        meaningful_unit_id=meaningful_unit_id,
                        **node_props
                    )
                    created = result.single()
                    
                    if not created:
                        raise ProviderError("neo4j", "Failed to create sentiment")
                    
                    logger.debug(f"Created sentiment {sentiment_id} for unit {meaningful_unit_id}")
                    return created['id']
                    
            except Exception as e:
                logger.error(f"Failed to create sentiment: {e}")
                raise ProviderError("neo4j", f"Failed to create sentiment: {e}") from e
    
    def create_topic_for_episode(self, topic_name: str, episode_id: str) -> bool:
        """Create a Topic node and link it to an Episode.
        
        This method is idempotent - it creates the Topic if it doesn't exist
        and creates the HAS_TOPIC relationship if it doesn't exist.
        
        Args:
            topic_name: Name of the topic/theme
            episode_id: ID of the episode
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                with self.session() as session:
                    # Create topic and relationship in one query
                    cypher = """
                    MATCH (e:Episode {id: $episode_id})
                    MERGE (t:Topic {name: $topic_name})
                    MERGE (e)-[:HAS_TOPIC]->(t)
                    RETURN t.name AS topic
                    """
                    
                    result = session.run(
                        cypher,
                        episode_id=episode_id,
                        topic_name=topic_name
                    )
                    
                    if result.single():
                        logger.debug(f"Created/linked topic '{topic_name}' to episode {episode_id}")
                        return True
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to create topic: {e}")
                return False
    
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
