"""Base graph storage with common Neo4j operations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import logging
import time
from contextlib import contextmanager

from ..utils.logging import get_logger
from ..monitoring import get_metrics_collector

logger = get_logger(__name__)


class BaseGraphStorage(ABC):
    """Abstract base class for graph storage implementations.
    
    Provides common Neo4j operations and patterns, with abstract
    methods for implementation-specific behavior.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize base graph storage.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.metrics = get_metrics_collector()
        self._failed_writes = []
        self._query_cache = {}
        
        # Configuration
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        self.cache_ttl = self.config.get('cache_ttl', 300)  # 5 minutes
        self.batch_size = self.config.get('batch_size', 1000)
    
    @abstractmethod
    def _get_session(self, database: Optional[str] = None):
        """Get a Neo4j session for the specified database.
        
        Args:
            database: Database name (for multi-database implementations)
            
        Returns:
            Neo4j session object
        """
        pass
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to Neo4j."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to Neo4j."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to Neo4j.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    def create_node(self, label: str, properties: Dict[str, Any], 
                   database: Optional[str] = None) -> Optional[str]:
        """Create a node in the graph.
        
        Args:
            label: Node label
            properties: Node properties
            database: Target database (for multi-database)
            
        Returns:
            Node ID if created, None on failure
        """
        if not properties.get('id'):
            logger.error(f"Cannot create {label} node without 'id' property")
            return None
        
        # Build query
        query = f"""
        CREATE (n:{label} $props)
        RETURN n.id as node_id
        """
        
        try:
            result = self._execute_with_retry(
                query, 
                {'props': properties},
                database=database
            )
            
            if result:
                node_id = result[0]['node_id']
                logger.debug(f"Created {label} node: {node_id}")
                self.metrics.nodes_created.inc(labels={'type': label})
                return node_id
            
        except Exception as e:
            logger.error(f"Failed to create {label} node: {e}")
            self._queue_failed_write('create_node', label, properties)
        
        return None
    
    def create_nodes_bulk(self, label: str, nodes_data: List[Dict[str, Any]],
                         database: Optional[str] = None) -> int:
        """Create multiple nodes in a single transaction.
        
        Args:
            label: Node label
            nodes_data: List of node properties
            database: Target database (for multi-database)
            
        Returns:
            Number of nodes created
        """
        if not nodes_data:
            return 0
        
        # Filter out nodes without IDs
        valid_nodes = [n for n in nodes_data if n.get('id')]
        if len(valid_nodes) < len(nodes_data):
            logger.warning(f"Skipping {len(nodes_data) - len(valid_nodes)} nodes without IDs")
        
        if not valid_nodes:
            return 0
        
        created = 0
        
        # Process in batches
        for i in range(0, len(valid_nodes), self.batch_size):
            batch = valid_nodes[i:i + self.batch_size]
            
            query = f"""
            UNWIND $nodes as node
            CREATE (n:{label})
            SET n = node
            """
            
            try:
                self._execute_with_retry(
                    query,
                    {'nodes': batch},
                    database=database
                )
                created += len(batch)
                logger.debug(f"Created batch of {len(batch)} {label} nodes")
                
            except Exception as e:
                logger.error(f"Failed to create batch of {label} nodes: {e}")
                # Queue individual nodes for retry
                for node in batch:
                    self._queue_failed_write('create_node', label, node)
        
        self.metrics.nodes_created.inc(amount=created, labels={'type': label})
        return created
    
    def merge_node(self, label: str, match_properties: Dict[str, Any],
                  update_properties: Optional[Dict[str, Any]] = None,
                  database: Optional[str] = None) -> Optional[str]:
        """Merge (create or update) a node.
        
        Args:
            label: Node label
            match_properties: Properties to match node
            update_properties: Properties to update/set
            database: Target database (for multi-database)
            
        Returns:
            Node ID if successful
        """
        if not match_properties.get('id'):
            logger.error(f"Cannot merge {label} node without 'id' in match properties")
            return None
        
        # Build query
        set_clause = ""
        if update_properties:
            set_clause = "ON CREATE SET n += $update_props ON MATCH SET n += $update_props"
        
        query = f"""
        MERGE (n:{label} {{id: $id}})
        {set_clause}
        RETURN n.id as node_id
        """
        
        params = {'id': match_properties['id']}
        if update_properties:
            params['update_props'] = update_properties
        
        try:
            result = self._execute_with_retry(query, params, database=database)
            if result:
                return result[0]['node_id']
                
        except Exception as e:
            logger.error(f"Failed to merge {label} node: {e}")
            self._queue_failed_write('merge_node', label, match_properties)
        
        return None
    
    def create_relationship(self, source_id: str, source_label: str,
                          target_id: str, target_label: str,
                          rel_type: str, properties: Optional[Dict[str, Any]] = None,
                          database: Optional[str] = None) -> bool:
        """Create a relationship between two nodes.
        
        Args:
            source_id: Source node ID
            source_label: Source node label
            target_id: Target node ID
            target_label: Target node label
            rel_type: Relationship type
            properties: Relationship properties
            database: Target database (for multi-database)
            
        Returns:
            True if created, False otherwise
        """
        # Build query
        props_clause = ""
        if properties:
            props_clause = " {props}"
        
        query = f"""
        MATCH (source:{source_label} {{id: $source_id}})
        MATCH (target:{target_label} {{id: $target_id}})
        CREATE (source)-[r:{rel_type}{props_clause}]->(target)
        RETURN r
        """
        
        params = {
            'source_id': source_id,
            'target_id': target_id
        }
        if properties:
            params['props'] = properties
        
        try:
            result = self._execute_with_retry(query, params, database=database)
            if result:
                logger.debug(f"Created {rel_type} relationship: {source_id} -> {target_id}")
                self.metrics.relationships_created.inc(labels={'type': rel_type})
                return True
                
        except Exception as e:
            logger.error(f"Failed to create {rel_type} relationship: {e}")
            self._queue_failed_write('create_relationship', rel_type, {
                'source_id': source_id,
                'source_label': source_label,
                'target_id': target_id,
                'target_label': target_label,
                'properties': properties
            })
        
        return False
    
    def create_relationships_bulk(self, relationships: List[Dict[str, Any]],
                                database: Optional[str] = None) -> int:
        """Create multiple relationships in batch.
        
        Args:
            relationships: List of relationship definitions
            database: Target database (for multi-database)
            
        Returns:
            Number of relationships created
        """
        if not relationships:
            return 0
        
        created = 0
        
        # Group by relationship type for efficiency
        rel_groups = {}
        for rel in relationships:
            rel_type = rel['type']
            if rel_type not in rel_groups:
                rel_groups[rel_type] = []
            rel_groups[rel_type].append(rel)
        
        # Process each group
        for rel_type, rels in rel_groups.items():
            # Process in batches
            for i in range(0, len(rels), self.batch_size):
                batch = rels[i:i + self.batch_size]
                
                query = f"""
                UNWIND $rels as rel
                MATCH (source {{id: rel.source_id}})
                MATCH (target {{id: rel.target_id}})
                CREATE (source)-[r:{rel_type}]->(target)
                SET r = rel.properties
                """
                
                try:
                    self._execute_with_retry(
                        query,
                        {'rels': batch},
                        database=database
                    )
                    created += len(batch)
                    logger.debug(f"Created batch of {len(batch)} {rel_type} relationships")
                    
                except Exception as e:
                    logger.error(f"Failed to create batch of {rel_type} relationships: {e}")
                    # Queue individual relationships for retry
                    for rel in batch:
                        self._queue_failed_write('create_relationship', rel_type, rel)
        
        self.metrics.relationships_created.inc(amount=created)
        return created
    
    def query(self, cypher_query: str, parameters: Optional[Dict[str, Any]] = None,
             database: Optional[str] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results.
        
        Args:
            cypher_query: Cypher query string
            parameters: Query parameters
            database: Target database (for multi-database)
            use_cache: Whether to use query cache
            
        Returns:
            List of result records as dictionaries
        """
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(cypher_query, parameters, database)
            cached = self._get_cached_result(cache_key)
            if cached is not None:
                return cached
        
        # Execute query
        results = self._execute_with_retry(
            cypher_query,
            parameters or {},
            database=database
        )
        
        # Cache results
        if use_cache and results is not None:
            self._cache_result(cache_key, results)
        
        return results or []
    
    def _execute_with_retry(self, query: str, parameters: Dict[str, Any],
                          database: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Execute query with retry logic.
        
        Args:
            query: Cypher query
            parameters: Query parameters
            database: Target database
            
        Returns:
            Query results or None on failure
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                with self._get_session(database) as session:
                    start_time = time.time()
                    
                    result = session.run(query, parameters)
                    records = [dict(record) for record in result]
                    
                    # Record metrics
                    duration = time.time() - start_time
                    self.metrics.query_duration.observe(duration, labels={'operation': 'query'})
                    
                    return records
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Query attempt {attempt + 1} failed: {e}")
                
                # Check if retryable
                if not self._is_retryable_error(e):
                    raise
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        logger.error(f"Query failed after {self.max_retries} attempts: {last_error}")
        raise last_error
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable.
        
        Args:
            error: The exception
            
        Returns:
            True if retryable
        """
        error_msg = str(error).lower()
        retryable_patterns = [
            'transient',
            'temporarily',
            'timeout',
            'deadlock',
            'connection',
            'unavailable'
        ]
        return any(pattern in error_msg for pattern in retryable_patterns)
    
    def _queue_failed_write(self, operation: str, entity_type: str, data: Dict[str, Any]) -> None:
        """Queue a failed write operation for later retry.
        
        Args:
            operation: Operation type
            entity_type: Entity type
            data: Operation data
        """
        self._failed_writes.append({
            'operation': operation,
            'entity_type': entity_type,
            'data': data,
            'timestamp': time.time()
        })
        
        # Limit queue size
        if len(self._failed_writes) > 1000:
            self._failed_writes = self._failed_writes[-500:]  # Keep most recent
    
    def retry_failed_writes(self) -> Tuple[int, int]:
        """Retry failed write operations.
        
        Returns:
            Tuple of (successful_retries, failed_retries)
        """
        if not self._failed_writes:
            return 0, 0
        
        logger.info(f"Retrying {len(self._failed_writes)} failed writes...")
        successful = 0
        failed = 0
        
        # Process failed writes
        remaining = []
        for write in self._failed_writes:
            try:
                if write['operation'] == 'create_node':
                    result = self.create_node(
                        write['entity_type'],
                        write['data']
                    )
                    if result:
                        successful += 1
                    else:
                        remaining.append(write)
                        failed += 1
                        
                elif write['operation'] == 'create_relationship':
                    result = self.create_relationship(
                        write['data']['source_id'],
                        write['data']['source_label'],
                        write['data']['target_id'],
                        write['data']['target_label'],
                        write['entity_type'],
                        write['data'].get('properties')
                    )
                    if result:
                        successful += 1
                    else:
                        remaining.append(write)
                        failed += 1
                        
            except Exception as e:
                logger.error(f"Failed to retry write operation: {e}")
                remaining.append(write)
                failed += 1
        
        self._failed_writes = remaining
        logger.info(f"Retry complete: {successful} successful, {failed} failed")
        
        return successful, failed
    
    def _get_cache_key(self, query: str, parameters: Optional[Dict[str, Any]],
                      database: Optional[str]) -> str:
        """Generate cache key for query.
        
        Args:
            query: Cypher query
            parameters: Query parameters
            database: Database name
            
        Returns:
            Cache key string
        """
        import hashlib
        import json
        
        key_parts = [
            query,
            json.dumps(parameters or {}, sort_keys=True),
            database or 'default'
        ]
        
        key_string = '|'.join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached query result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if cache_key in self._query_cache:
            entry = self._query_cache[cache_key]
            if time.time() - entry['timestamp'] < self.cache_ttl:
                return entry['result']
            else:
                # Expired
                del self._query_cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: List[Dict[str, Any]]) -> None:
        """Cache query result.
        
        Args:
            cache_key: Cache key
            result: Query result
        """
        self._query_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        # Limit cache size
        if len(self._query_cache) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._query_cache.keys(),
                key=lambda k: self._query_cache[k]['timestamp']
            )
            for key in sorted_keys[:500]:
                del self._query_cache[key]
    
    def clear_cache(self) -> None:
        """Clear query cache."""
        self._query_cache.clear()
        logger.debug("Query cache cleared")
    
    # High-level storage methods using the primitives above
    
    def store_podcast(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store a podcast node."""
        return self.merge_node('Podcast', {'id': properties['id']}, properties)
    
    def store_episode(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store an episode node."""
        return self.merge_node('Episode', {'id': properties['id']}, properties)
    
    def store_segment(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store a segment node."""
        return self.create_node('Segment', properties)
    
    def store_entity(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store an entity node."""
        return self.merge_node('Entity', {'id': properties['id']}, properties)
    
    def store_insight(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store an insight node."""
        return self.create_node('Insight', properties)
    
    def store_quote(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store a quote node."""
        return self.create_node('Quote', properties)
    
    def store_theme(self, properties: Dict[str, Any]) -> Optional[str]:
        """Store a theme node."""
        return self.merge_node('Theme', {'id': properties['id']}, properties)
    
    def store_relationship(self, source_id: str, source_label: str,
                         target_id: str, target_label: str,
                         rel_type: str, properties: Optional[Dict[str, Any]] = None) -> bool:
        """Store a relationship between nodes."""
        return self.create_relationship(
            source_id, source_label,
            target_id, target_label,
            rel_type, properties
        )