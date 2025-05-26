"""Neo4j graph database provider implementation."""

import logging
from typing import Dict, Any, List, Optional, Iterator
from contextlib import contextmanager
import threading
from queue import Queue

from src.providers.graph.base import BaseGraphProvider
from src.core.exceptions import ProviderError, ConnectionError
from src.tracing import trace_method, add_span_attributes, trace_database


logger = logging.getLogger(__name__)


class Neo4jProvider(BaseGraphProvider):
    """Neo4j graph database provider with connection pooling and thread safety."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Neo4j provider with configuration."""
        super().__init__(config)
        self._lock = threading.Lock()
        self._pool_size = config.get('pool_size', 50)
        self._max_connection_lifetime = config.get('max_connection_lifetime', 3600)
        
    def _initialize_driver(self) -> None:
        """Initialize the Neo4j driver."""
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ProviderError(
                "neo4j is not installed. "
                "Install with: pip install neo4j"
            )
            
        if not self.uri:
            raise ProviderError("Neo4j URI is required")
        if not self.username or not self.password:
            raise ProviderError("Neo4j username and password are required")
            
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=self._pool_size,
                max_connection_lifetime=self._max_connection_lifetime,
                connection_acquisition_timeout=30.0
            )
            logger.info(f"Initialized Neo4j driver for {self.uri}")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Neo4j driver: {e}")
            
    def connect(self) -> None:
        """Connect to Neo4j (driver handles connection pooling)."""
        self._ensure_initialized()
        
        # Verify connection
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run("RETURN 'Connected' AS status")
                status = result.single()["status"]
                logger.info(f"Neo4j connection verified: {status}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")
            
    def disconnect(self) -> None:
        """Disconnect from Neo4j."""
        if self._driver:
            try:
                self._driver.close()
                self._driver = None
                self._initialized = False
                logger.info("Disconnected from Neo4j")
            except Exception as e:
                logger.warning(f"Error closing Neo4j connection: {e}")
                
    @contextmanager
    def session(self):
        """Create a Neo4j session context manager."""
        self._ensure_initialized()
        
        session = None
        try:
            session = self._driver.session(database=self.database)
            yield session
        finally:
            if session:
                session.close()
                
    @trace_method(name="neo4j.create_node")
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a node in Neo4j."""
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
                
                # Add span attributes
                add_span_attributes({
                    "neo4j.node_type": node_type,
                    "neo4j.node_id": properties.get('id'),
                    "neo4j.properties_count": len(properties),
                })
                
                try:
                    result = session.run(cypher, **params)
                    return result.single()["id"]
                except Exception as e:
                    raise ProviderError(f"Failed to create {node_type} node: {e}")
                    
    @trace_method(name="neo4j.create_relationship")
    def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a relationship between nodes."""
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
                        f"Failed to create relationship {rel_type} "
                        f"between {source_id} and {target_id}: {e}"
                    )
                    
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
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
                raise ProviderError(f"Query execution failed: {e}")
                
    def delete_node(self, node_id: str) -> None:
        """Delete a node and its relationships."""
        with self._lock:
            with self.session() as session:
                cypher = """
                MATCH (n {id: $node_id})
                DETACH DELETE n
                """
                try:
                    session.run(cypher, node_id=node_id)
                except Exception as e:
                    raise ProviderError(f"Failed to delete node {node_id}: {e}")
                    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Update node properties."""
        with self._lock:
            with self.session() as session:
                # Build SET clauses
                set_clauses = []
                params = {'node_id': node_id}
                
                for key, value in properties.items():
                    if key != 'id':  # Don't update ID
                        set_clauses.append(f"n.{key} = ${key}")
                        params[key] = value
                        
                if not set_clauses:
                    return  # Nothing to update
                    
                set_string = ", ".join(set_clauses)
                cypher = f"""
                MATCH (n {{id: $node_id}})
                SET {set_string}
                RETURN n.id AS id
                """
                
                try:
                    result = session.run(cypher, **params)
                    if not result.single():
                        raise ProviderError(f"Node with id {node_id} not found")
                except Exception as e:
                    raise ProviderError(f"Failed to update node {node_id}: {e}")
                    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        with self.session() as session:
            cypher = """
            MATCH (n {id: $node_id})
            RETURN n, labels(n) AS labels
            """
            try:
                result = session.run(cypher, node_id=node_id)
                record = result.single()
                
                if record:
                    node_data = dict(record["n"])
                    node_data['_labels'] = record["labels"]
                    return node_data
                return None
                
            except Exception as e:
                raise ProviderError(f"Failed to get node {node_id}: {e}")
                
    def setup_schema(self) -> None:
        """Set up Neo4j schema with constraints and indexes."""
        with self._lock:
            with self.session() as session:
                schema_queries = [
                    # Constraints
                    "CREATE CONSTRAINT podcast_id IF NOT EXISTS FOR (p:Podcast) REQUIRE p.id IS UNIQUE",
                    "CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE",
                    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT insight_id IF NOT EXISTS FOR (i:Insight) REQUIRE i.id IS UNIQUE",
                    "CREATE CONSTRAINT quote_id IF NOT EXISTS FOR (q:Quote) REQUIRE q.id IS UNIQUE",
                    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
                    "CREATE CONSTRAINT connection_id IF NOT EXISTS FOR (c:PotentialConnection) REQUIRE c.id IS UNIQUE",
                    
                    # Indexes
                    "CREATE INDEX podcast_name IF NOT EXISTS FOR (p:Podcast) ON (p.name)",
                    "CREATE INDEX episode_title IF NOT EXISTS FOR (e:Episode) ON (e.title)",
                    "CREATE INDEX segment_text IF NOT EXISTS FOR (s:Segment) ON (s.text)",
                    "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                    "CREATE INDEX entity_bridge IF NOT EXISTS FOR (e:Entity) ON (e.bridge_score)",
                    "CREATE INDEX entity_peripheral IF NOT EXISTS FOR (e:Entity) ON (e.is_peripheral)",
                    "CREATE INDEX insight_type IF NOT EXISTS FOR (i:Insight) ON (i.insight_type)",
                    "CREATE INDEX insight_bridge IF NOT EXISTS FOR (i:Insight) ON (i.is_bridge_insight)",
                    "CREATE INDEX quote_type IF NOT EXISTS FOR (q:Quote) ON (q.quote_type)",
                    "CREATE INDEX quote_speaker IF NOT EXISTS FOR (q:Quote) ON (q.speaker)",
                    "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
                    "CREATE INDEX topic_trend IF NOT EXISTS FOR (t:Topic) ON (t.trend)",
                    
                    # Schema version
                    """
                    MERGE (v:SchemaVersion {id: 'current'})
                    SET v.version = '1.0.0',
                        v.updated_at = datetime(),
                        v.description = 'Modular refactoring schema'
                    RETURN v
                    """
                ]
                
                for query in schema_queries:
                    try:
                        session.run(query)
                        logger.debug(f"Executed schema query: {query[:50]}...")
                    except Exception as e:
                        # Log but don't fail - constraints/indexes might already exist
                        logger.warning(f"Schema query warning: {e}")
                        
                logger.info("Neo4j schema setup completed")
                
    # Additional Neo4j specific methods
    
    def execute_transaction(self, transaction_func, **kwargs):
        """Execute a function within a transaction."""
        with self.session() as session:
            return session.execute_write(transaction_func, **kwargs)
            
    def execute_read_transaction(self, transaction_func, **kwargs):
        """Execute a read-only function within a transaction."""
        with self.session() as session:
            return session.execute_read(transaction_func, **kwargs)
            
    def bulk_create_nodes(self, node_type: str, properties_list: List[Dict[str, Any]]) -> List[str]:
        """Bulk create nodes for better performance."""
        with self._lock:
            with self.session() as session:
                ids = []
                
                # Use UNWIND for bulk creation
                cypher = f"""
                UNWIND $props_list AS props
                CREATE (n:{node_type})
                SET n = props
                RETURN n.id AS id
                """
                
                try:
                    result = session.run(cypher, props_list=properties_list)
                    for record in result:
                        ids.append(record["id"])
                    return ids
                except Exception as e:
                    raise ProviderError(f"Failed to bulk create {node_type} nodes: {e}")
                    
    def get_connection_count(self) -> int:
        """Get current number of connections in the pool."""
        if self._driver:
            # This is a simplified version - actual implementation depends on Neo4j driver version
            return self._pool_size
        return 0