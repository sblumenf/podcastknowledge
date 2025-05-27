"""In-memory graph database provider for testing."""

import logging
from typing import Dict, Any, List, Optional, Set
from contextlib import contextmanager
import uuid
import re
from collections import defaultdict

from src.providers.graph.base import BaseGraphProvider
from src.core.exceptions import ProviderError
from src.core.plugin_discovery import provider_plugin


logger = logging.getLogger(__name__)


@provider_plugin('graph', 'memory', version='1.0.0', author='Test', 
                description='In-memory graph provider for testing')
class InMemoryGraphProvider(BaseGraphProvider):
    """In-memory graph database provider for testing and development."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize in-memory provider."""
        super().__init__(config)
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.node_labels: Dict[str, Set[str]] = defaultdict(set)
        self.indexes: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
    def _initialize_driver(self) -> None:
        """No driver initialization needed for in-memory provider."""
        pass
        
    def connect(self) -> None:
        """No connection needed for in-memory provider."""
        self._initialized = True
        logger.info("In-memory graph provider connected")
        
    def disconnect(self) -> None:
        """Clear in-memory data."""
        self.nodes.clear()
        self.relationships.clear()
        self.node_labels.clear()
        self.indexes.clear()
        self._initialized = False
        logger.info("In-memory graph provider disconnected")
        
    @contextmanager
    def session(self):
        """Mock session context manager."""
        self._ensure_initialized()
        
        class MockSession:
            def __init__(self, provider):
                self.provider = provider
                
            def run(self, cypher: str, **params):
                """Execute Cypher-like query."""
                return self.provider._execute_query(cypher, params)
                
        yield MockSession(self)
        
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a node in memory."""
        # Ensure node has an ID
        if 'id' not in properties:
            properties['id'] = str(uuid.uuid4())
            
        node_id = properties['id']
        
        # Store node
        self.nodes[node_id] = properties.copy()
        self.node_labels[node_id].add(node_type)
        
        # Update indexes
        for prop_name, prop_value in properties.items():
            if prop_value is not None:
                self.indexes[node_type][prop_name].add(node_id)
                
        logger.debug(f"Created {node_type} node with id {node_id}")
        return node_id
        
    def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a relationship in memory."""
        # Verify nodes exist
        if source_id not in self.nodes:
            raise ProviderError(f"Source node {source_id} not found")
        if target_id not in self.nodes:
            raise ProviderError(f"Target node {target_id} not found")
            
        relationship = {
            'source_id': source_id,
            'target_id': target_id,
            'type': rel_type,
            'properties': properties or {}
        }
        
        self.relationships.append(relationship)
        logger.debug(f"Created relationship {rel_type} from {source_id} to {target_id}")
        
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a simple Cypher-like query."""
        return self._execute_query(cypher, parameters or {})
        
    def delete_node(self, node_id: str) -> None:
        """Delete a node and its relationships."""
        if node_id not in self.nodes:
            raise ProviderError(f"Node {node_id} not found")
            
        # Remove from nodes
        node_data = self.nodes.pop(node_id)
        
        # Remove from labels
        labels = self.node_labels.pop(node_id, set())
        
        # Remove from indexes
        for label in labels:
            for prop_name, prop_value in node_data.items():
                if prop_value is not None:
                    self.indexes[label][prop_name].discard(node_id)
                    
        # Remove relationships
        self.relationships = [
            rel for rel in self.relationships
            if rel['source_id'] != node_id and rel['target_id'] != node_id
        ]
        
        logger.debug(f"Deleted node {node_id}")
        
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Update node properties."""
        if node_id not in self.nodes:
            raise ProviderError(f"Node {node_id} not found")
            
        # Update properties
        self.nodes[node_id].update(properties)
        
        # Update indexes
        labels = self.node_labels.get(node_id, set())
        for label in labels:
            for prop_name, prop_value in properties.items():
                if prop_value is not None:
                    self.indexes[label][prop_name].add(node_id)
                    
        logger.debug(f"Updated node {node_id}")
        
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        if node_id not in self.nodes:
            return None
            
        node_data = self.nodes[node_id].copy()
        node_data['_labels'] = list(self.node_labels.get(node_id, set()))
        return node_data
        
    def setup_schema(self) -> None:
        """No schema setup needed for in-memory provider."""
        logger.info("In-memory schema setup (no-op)")
        
    def _execute_query(self, cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a simple Cypher-like query."""
        # Very basic Cypher parsing for testing
        cypher_lower = cypher.lower()
        
        if "return 'ok' as status" in cypher_lower:
            return [{'status': 'OK'}]
            
        if "return 'connected' as status" in cypher_lower:
            return [{'status': 'Connected'}]
            
        # Simple MATCH queries
        if cypher_lower.startswith("match"):
            return self._execute_match_query(cypher, params)
            
        # CREATE queries are handled by create_node/create_relationship
        if cypher_lower.startswith("create"):
            return []
            
        # Default empty result
        return []
        
    def _execute_match_query(self, cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a simple MATCH query."""
        # Extract node pattern
        match_pattern = re.search(r'match\s*\((\w+)(?:\s*:\s*(\w+))?\s*{([^}]+)}\)', cypher, re.IGNORECASE)
        
        if match_pattern:
            var_name = match_pattern.group(1)
            label = match_pattern.group(2)
            props_str = match_pattern.group(3)
            
            # Parse properties
            prop_match = re.search(r'(\w+):\s*\$(\w+)', props_str)
            if prop_match:
                prop_name = prop_match.group(1)
                param_name = prop_match.group(2)
                prop_value = params.get(param_name)
                
                # Find matching nodes
                results = []
                for node_id, node_data in self.nodes.items():
                    if label and label not in self.node_labels.get(node_id, set()):
                        continue
                    if node_data.get(prop_name) == prop_value:
                        result_row = {var_name: node_data}
                        
                        # Handle RETURN clause
                        return_match = re.search(r'return\s+(.+)', cypher, re.IGNORECASE)
                        if return_match:
                            return_clause = return_match.group(1)
                            if f'{var_name}.id as id' in return_clause.lower():
                                result_row = {'id': node_data['id']}
                            elif 'labels(' in return_clause.lower():
                                result_row['labels'] = list(self.node_labels.get(node_id, set()))
                                
                        results.append(result_row)
                        
                return results
                
        # Handle relationship queries
        rel_pattern = re.search(r'match\s*\((\w+)\)-\[(\w+):?(\w+)?\]-[>]?\((\w+)\)', cypher, re.IGNORECASE)
        
        if rel_pattern:
            source_var = rel_pattern.group(1)
            rel_var = rel_pattern.group(2)
            rel_type = rel_pattern.group(3)
            target_var = rel_pattern.group(4)
            
            results = []
            for rel in self.relationships:
                if rel_type and rel['type'] != rel_type:
                    continue
                    
                source_node = self.nodes.get(rel['source_id'])
                target_node = self.nodes.get(rel['target_id'])
                
                if source_node and target_node:
                    result_row = {
                        source_var: source_node,
                        target_var: target_node,
                        rel_var: rel
                    }
                    
                    # Handle RETURN clause
                    return_match = re.search(r'return\s+(.+)', cypher, re.IGNORECASE)
                    if return_match:
                        return_clause = return_match.group(1)
                        # Parse specific return items
                        if 'as source' in return_clause:
                            result_row = {
                                'source': source_node.get('id'),
                                'target': target_node.get('id'),
                                'rel_type': rel['type'],
                                'weight': rel['properties'].get('weight', 1)
                            }
                            
                    results.append(result_row)
                    
            return results
            
        return []
        
    # Testing utilities
    
    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get all nodes (for testing)."""
        return self.nodes.copy()
        
    def get_all_relationships(self) -> List[Dict[str, Any]]:
        """Get all relationships (for testing)."""
        return self.relationships.copy()
        
    def clear(self) -> None:
        """Clear all data."""
        self.nodes.clear()
        self.relationships.clear()
        self.node_labels.clear()
        self.indexes.clear()
        
    def get_node_count(self) -> int:
        """Get total number of nodes."""
        return len(self.nodes)
        
    def get_relationship_count(self) -> int:
        """Get total number of relationships."""
        return len(self.relationships)