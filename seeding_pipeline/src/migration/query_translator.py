"""Query translation layer for fixed to schemaless migration."""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class QueryTranslator:
    """
    Translates between fixed schema and schemaless Cypher queries.
    
    This enables gradual migration by allowing old queries to work
    with the new schemaless graph structure.
    """
    
    def __init__(self):
        """Initialize query translator with pattern mappings."""
        # Node label to property mappings
        self.label_to_property = {
            'Podcast': {'_type': 'Podcast'},
            'Episode': {'_type': 'Episode'},
            'Segment': {'_type': 'Segment'},
            'Entity': {'_type': 'Entity'},
            'Quote': {'_type': 'Quote'},
            'Insight': {'_type': 'Insight'},
            'Topic': {'_type': 'Topic'},
            'Speaker': {'_type': 'Speaker'}
        }
        
        # Property name mappings (old to new)
        self.property_mappings = {
            'name': 'name',
            'title': 'title',
            'description': 'description',
            'confidence': 'confidence',
            'importance': 'importance_score',
            'start_time': 'start_time',
            'end_time': 'end_time',
            'speaker': 'speaker_name',
            'embedding': 'vector_embedding',
            'first_mentioned': 'first_mentioned_at',
            'mention_count': 'total_mentions',
            'bridge_score': 'bridge_score',
            'is_peripheral': 'is_peripheral_node'
        }
        
        # Relationship type mappings
        self.relationship_mappings = {
            'BELONGS_TO': 'BELONGS_TO',
            'PART_OF': 'PART_OF',
            'MENTIONS': 'MENTIONS',
            'DISCUSSES': 'DISCUSSES',
            'REFERENCES': 'REFERENCES',
            'KNOWS': 'KNOWS',
            'WORKS_WITH': 'WORKS_WITH',
            'RELATED_TO': 'RELATED_TO'
        }
        
        # Common query patterns
        self.query_patterns = self._build_query_patterns()
    
    def translate_fixed_to_schemaless(self, cypher_query: str) -> str:
        """
        Convert a fixed schema Cypher query to work with schemaless structure.
        
        Args:
            cypher_query: Original query using fixed schema
            
        Returns:
            Translated query for schemaless structure
        """
        translated = cypher_query
        
        # Step 1: Replace node labels with Node + property filter
        translated = self._translate_node_labels(translated)
        
        # Step 2: Translate property names
        translated = self._translate_properties(translated)
        
        # Step 3: Translate relationship types
        translated = self._translate_relationships(translated)
        
        # Step 4: Handle special patterns
        translated = self._handle_special_patterns(translated)
        
        logger.debug(f"Translated query: {cypher_query} -> {translated}")
        return translated
    
    def _translate_node_labels(self, query: str) -> str:
        """Replace node labels with Node label and property filters."""
        # Pattern to match node patterns like (n:Entity) or (p:Podcast)
        node_pattern = r'\((\w+):(\w+)(?:\s*{[^}]*})?\)'
        
        def replace_node(match):
            var_name = match.group(1)
            label = match.group(2)
            
            if label in self.label_to_property:
                # Get the property filter for this label
                prop_filter = self.label_to_property[label]
                prop_str = ', '.join([f'{k}: "{v}"' for k, v in prop_filter.items()])
                
                # Check if there are existing properties in the pattern
                if '{' in match.group(0):
                    # Insert our type filter into existing properties
                    return match.group(0).replace(f':{label}', ':Node').replace('{', f'{{{prop_str}, ')
                else:
                    # Add property filter
                    return f'({var_name}:Node {{{prop_str}}})'
            else:
                # Unknown label, leave as is but log warning
                logger.warning(f"Unknown node label in query: {label}")
                return match.group(0)
        
        return re.sub(node_pattern, replace_node, query)
    
    def _translate_properties(self, query: str) -> str:
        """Translate property names from fixed to schemaless."""
        translated = query
        
        # Replace property names in various contexts
        for old_prop, new_prop in self.property_mappings.items():
            if old_prop != new_prop:
                # Property in WHERE clause or SET clause
                translated = re.sub(
                    rf'\b{old_prop}\b(?=\s*[=:<>])',
                    new_prop,
                    translated
                )
                # Property in RETURN clause
                translated = re.sub(
                    rf'\.{old_prop}\b',
                    f'.{new_prop}',
                    translated
                )
        
        return translated
    
    def _translate_relationships(self, query: str) -> str:
        """Translate relationship types."""
        # For schemaless, relationships use generic RELATIONSHIP type
        # with actual type in _type property
        
        # Pattern to match relationships like -[:KNOWS]->
        rel_pattern = r'-\[:(\w+)\]-'
        
        def replace_rel(match):
            rel_type = match.group(1)
            if rel_type in self.relationship_mappings:
                # In schemaless, we filter by _type property
                return f'-[:RELATIONSHIP {{_type: "{rel_type}"}}]-'
            else:
                logger.warning(f"Unknown relationship type: {rel_type}")
                return f'-[:RELATIONSHIP {{_type: "{rel_type}"}}]-'
        
        return re.sub(rel_pattern, replace_rel, query)
    
    def _handle_special_patterns(self, query: str) -> str:
        """Handle special query patterns that need custom translation."""
        # Handle COUNT(DISTINCT n) patterns
        query = re.sub(
            r'COUNT\(DISTINCT\s+(\w+)\)',
            r'COUNT(DISTINCT \1.id)',
            query
        )
        
        # Handle node type checks in WHERE clauses
        # e.g., WHERE n:Entity -> WHERE n._type = 'Entity'
        query = re.sub(
            r'WHERE\s+(\w+):(\w+)',
            r'WHERE \1._type = "\2"',
            query
        )
        
        return query
    
    def build_type_agnostic_query(self, intent: Dict[str, Any]) -> str:
        """
        Create a new flexible query based on intent rather than fixed structure.
        
        Args:
            intent: Dictionary describing query intent with keys like:
                - action: 'find', 'count', 'match', etc.
                - target: what to find (entities, relationships, etc.)
                - filters: conditions to apply
                - return: what to return
                
        Returns:
            Flexible Cypher query
        """
        action = intent.get('action', 'find')
        target = intent.get('target', 'nodes')
        filters = intent.get('filters', {})
        return_clause = intent.get('return', '*')
        
        # Build query parts
        match_clause = self._build_match_clause(target, filters)
        where_clause = self._build_where_clause(filters)
        return_clause = self._build_return_clause(action, return_clause)
        
        # Combine parts
        query_parts = [match_clause]
        if where_clause:
            query_parts.append(where_clause)
        query_parts.append(return_clause)
        
        return '\n'.join(query_parts)
    
    def _build_match_clause(self, target: str, filters: Dict[str, Any]) -> str:
        """Build MATCH clause for type-agnostic query."""
        if target == 'nodes':
            return "MATCH (n:Node)"
        elif target == 'relationships':
            return "MATCH (a:Node)-[r:RELATIONSHIP]->(b:Node)"
        elif target == 'path':
            return "MATCH path = (a:Node)-[*]-(b:Node)"
        else:
            return "MATCH (n:Node)"
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> str:
        """Build WHERE clause from filters."""
        if not filters:
            return ""
        
        conditions = []
        for key, value in filters.items():
            if key == 'type':
                conditions.append(f'n._type = "{value}"')
            elif key == 'properties':
                for prop, val in value.items():
                    if isinstance(val, str):
                        conditions.append(f'n.{prop} = "{val}"')
                    else:
                        conditions.append(f'n.{prop} = {val}')
            elif key == 'text_contains':
                conditions.append(f'n.text CONTAINS "{value}"')
        
        if conditions:
            return "WHERE " + " AND ".join(conditions)
        return ""
    
    def _build_return_clause(self, action: str, return_spec: str) -> str:
        """Build RETURN clause based on action."""
        if action == 'count':
            return f"RETURN COUNT({return_spec}) as count"
        elif action == 'find':
            return f"RETURN {return_spec}"
        elif action == 'exists':
            return f"RETURN COUNT({return_spec}) > 0 as exists"
        else:
            return f"RETURN {return_spec}"
    
    def handle_property_variations(self, property_name: str) -> List[str]:
        """
        Manage property aliases and variations.
        
        Args:
            property_name: Original property name
            
        Returns:
            List of possible property names including aliases
        """
        variations = [property_name]
        
        # Add mapped version if exists
        if property_name in self.property_mappings:
            variations.append(self.property_mappings[property_name])
        
        # Add reverse mapping
        for old, new in self.property_mappings.items():
            if new == property_name and old not in variations:
                variations.append(old)
        
        # Add common variations
        if property_name.endswith('_id'):
            variations.append(property_name[:-3])  # Remove _id
        elif not property_name.endswith('_id'):
            variations.append(f"{property_name}_id")  # Add _id
        
        # Add snake_case / camelCase variations
        if '_' in property_name:
            # Convert snake_case to camelCase
            parts = property_name.split('_')
            camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
            variations.append(camel)
        else:
            # Convert camelCase to snake_case
            snake = re.sub(r'(?<!^)(?=[A-Z])', '_', property_name).lower()
            if snake != property_name:
                variations.append(snake)
        
        return list(set(variations))  # Remove duplicates
    
    def _build_query_patterns(self) -> Dict[str, str]:
        """Build library of common query patterns."""
        return {
            # Find entities by type
            'find_entities_by_type': """
                MATCH (n:Node {_type: $type})
                RETURN n
                ORDER BY n.importance_score DESC
                LIMIT $limit
            """,
            
            # Find related entities
            'find_related_entities': """
                MATCH (a:Node {id: $entity_id})-[r:RELATIONSHIP]-(b:Node)
                RETURN b, r._type as relationship_type
                ORDER BY r.confidence DESC
            """,
            
            # Find entities in episode
            'find_entities_in_episode': """
                MATCH (n:Node {episode_id: $episode_id})
                WHERE n._type IN ['Entity', 'Quote', 'Insight']
                RETURN n
                ORDER BY n.first_mentioned_at
            """,
            
            # Count entities by type
            'count_by_type': """
                MATCH (n:Node)
                RETURN n._type as type, COUNT(*) as count
                ORDER BY count DESC
            """,
            
            # Find quotes by speaker
            'find_quotes_by_speaker': """
                MATCH (q:Node {_type: 'Quote', attributed_to: $speaker})
                RETURN q
                ORDER BY q.importance_score DESC
            """,
            
            # Find bridge entities
            'find_bridge_entities': """
                MATCH (n:Node {_type: 'Entity'})
                WHERE n.bridge_score > $threshold
                RETURN n
                ORDER BY n.bridge_score DESC
            """,
            
            # Find peripheral entities
            'find_peripheral_entities': """
                MATCH (n:Node {_type: 'Entity', is_peripheral_node: true})
                RETURN n
            """,
            
            # Search by text
            'search_text': """
                MATCH (n:Node)
                WHERE n.text CONTAINS $search_term
                   OR n.name CONTAINS $search_term
                   OR n.description CONTAINS $search_term
                RETURN n
                LIMIT $limit
            """,
            
            # Find shortest path
            'find_shortest_path': """
                MATCH path = shortestPath(
                    (a:Node {id: $source_id})-[*]-(b:Node {id: $target_id})
                )
                RETURN path
            """,
            
            # Get episode timeline
            'get_episode_timeline': """
                MATCH (s:Node {_type: 'Segment', episode_id: $episode_id})
                RETURN s
                ORDER BY s.start_time
            """
        }
    
    def get_query_pattern(self, pattern_name: str, **kwargs) -> str:
        """
        Get a pre-built query pattern with parameters.
        
        Args:
            pattern_name: Name of the pattern to retrieve
            **kwargs: Parameters to substitute in the query
            
        Returns:
            Query string with parameters
        """
        if pattern_name not in self.query_patterns:
            raise ValueError(f"Unknown query pattern: {pattern_name}")
        
        query = self.query_patterns[pattern_name]
        
        # Simple parameter substitution for demonstration
        # In production, use proper parameterized queries
        for key, value in kwargs.items():
            if isinstance(value, str):
                query = query.replace(f'${key}', f'"{value}"')
            else:
                query = query.replace(f'${key}', str(value))
        
        return query