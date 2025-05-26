"""Result standardization for schemaless to fixed schema conversion."""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class ResultStandardizer:
    """
    Standardizes schemaless query results to match expected fixed schema format.
    
    This enables backward compatibility by transforming flexible schemaless
    results into the structure expected by existing code.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize result standardizer with configuration."""
        self.config = config or {}
        
        # Property mappings (schemaless to fixed)
        self.property_mappings = {
            'importance_score': 'importance',
            'speaker_name': 'speaker',
            'vector_embedding': 'embedding',
            'first_mentioned_at': 'first_mentioned',
            'total_mentions': 'mention_count',
            'is_peripheral_node': 'is_peripheral',
            'attributed_to': 'speaker',
            'quote_text': 'text',
            'transcription_confidence': 'confidence',
            'segment_embedding': 'embedding'
        }
        
        # Default values for missing properties
        self.default_values = {
            'confidence': 1.0,
            'importance': 0.5,
            'mention_count': 1,
            'is_peripheral': False,
            'bridge_score': 0.0,
            'sentiment': 0.0,
            'complexity_score': 0.5
        }
        
        # Track schema evolution
        self.discovered_types = set()
        self.discovered_properties = defaultdict(set)
        self.evolution_log = []
    
    def standardize_results(self, results: List[Dict[str, Any]], expected_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Convert schemaless results to current expected format.
        
        Args:
            results: List of result records from schemaless query
            expected_type: Expected node type (Entity, Quote, etc.)
            
        Returns:
            Standardized results matching fixed schema expectations
        """
        standardized = []
        
        for result in results:
            # Handle different result structures
            if isinstance(result, dict):
                if 'n' in result:  # Node result
                    standardized_node = self._standardize_node(result['n'], expected_type)
                    standardized.append({'n': standardized_node})
                elif 'r' in result:  # Relationship result
                    standardized_rel = self._standardize_relationship(result['r'])
                    standardized.append({'r': standardized_rel})
                elif 'path' in result:  # Path result
                    standardized_path = self._standardize_path(result['path'])
                    standardized.append({'path': standardized_path})
                else:
                    # Direct property result
                    standardized.append(self._standardize_node(result, expected_type))
            else:
                # Simple value result
                standardized.append(result)
        
        return standardized
    
    def _standardize_node(self, node: Dict[str, Any], expected_type: Optional[str] = None) -> Dict[str, Any]:
        """Standardize a single node."""
        # Get node type from _type property
        node_type = node.get('_type', expected_type or 'Unknown')
        
        # Track discovered type
        if node_type not in self.discovered_types:
            self.discovered_types.add(node_type)
            self._log_evolution('new_type', node_type)
        
        # Create standardized node
        standardized = {
            'id': node.get('id'),
            'labels': [node_type],  # Simulate label for compatibility
        }
        
        # Map properties based on node type
        if node_type == 'Entity':
            standardized.update(self._standardize_entity_properties(node))
        elif node_type == 'Quote':
            standardized.update(self._standardize_quote_properties(node))
        elif node_type == 'Segment':
            standardized.update(self._standardize_segment_properties(node))
        elif node_type == 'Episode':
            standardized.update(self._standardize_episode_properties(node))
        elif node_type == 'Podcast':
            standardized.update(self._standardize_podcast_properties(node))
        else:
            # Generic property mapping
            standardized.update(self._map_properties(node))
        
        # Track discovered properties
        for prop in node.keys():
            if prop not in ['id', '_type'] and prop not in self.discovered_properties[node_type]:
                self.discovered_properties[node_type].add(prop)
                self._log_evolution('new_property', f"{node_type}.{prop}")
        
        return standardized
    
    def _standardize_entity_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize entity-specific properties."""
        props = {
            'name': node.get('name', ''),
            'type': node.get('entity_type', node.get('_entity_type', 'UNKNOWN')),
            'description': node.get('description'),
            'confidence': self._get_mapped_property(node, 'confidence'),
            'importance': self._get_mapped_property(node, 'importance_score', 'importance'),
            'first_mentioned': self._get_mapped_property(node, 'first_mentioned_at', 'first_mentioned'),
            'mention_count': self._get_mapped_property(node, 'total_mentions', 'mention_count'),
            'bridge_score': node.get('bridge_score', self.default_values['bridge_score']),
            'is_peripheral': self._get_mapped_property(node, 'is_peripheral_node', 'is_peripheral')
        }
        
        # Add embedding if present
        embedding = self._get_mapped_property(node, 'vector_embedding', 'embedding')
        if embedding:
            props['embedding'] = embedding
            
        return props
    
    def _standardize_quote_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize quote-specific properties."""
        return {
            'text': self._get_mapped_property(node, 'quote_text', 'text'),
            'speaker': self._get_mapped_property(node, 'attributed_to', 'speaker'),
            'context': node.get('surrounding_context', node.get('context')),
            'quote_type': node.get('quote_category', node.get('quote_type', 'general')),
            'timestamp': node.get('spoken_at', node.get('timestamp')),
            'segment_id': node.get('source_segment', node.get('segment_id')),
            'importance': self._get_mapped_property(node, 'quote_importance', 'importance_score')
        }
    
    def _standardize_segment_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize segment-specific properties."""
        props = {
            'text': node.get('text', ''),
            'start_time': node.get('start_time', 0.0),
            'end_time': node.get('end_time', 0.0),
            'speaker': self._get_mapped_property(node, 'speaker_name', 'speaker'),
            'confidence': self._get_mapped_property(node, 'transcription_confidence', 'confidence'),
            'sentiment': node.get('sentiment_score', node.get('sentiment', self.default_values['sentiment'])),
            'complexity_score': node.get('text_complexity', node.get('complexity_score', self.default_values['complexity_score'])),
            'is_advertisement': node.get('is_ad_content', node.get('is_advertisement', False))
        }
        
        # Add duration if not present
        if 'duration' not in node and props['end_time'] > props['start_time']:
            props['duration'] = props['end_time'] - props['start_time']
        
        # Add embedding if present
        embedding = self._get_mapped_property(node, 'segment_embedding', 'embedding')
        if embedding:
            props['embedding'] = embedding
            
        return props
    
    def _standardize_episode_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize episode-specific properties."""
        return {
            'title': node.get('title', ''),
            'description': node.get('description'),
            'audio_url': node.get('audio_url'),
            'publication_date': node.get('publication_date'),
            'duration': node.get('duration'),
            'episode_number': node.get('episode_number'),
            'season_number': node.get('season_number'),
            'processed_timestamp': node.get('processed_timestamp', datetime.now().isoformat())
        }
    
    def _standardize_podcast_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize podcast-specific properties."""
        return {
            'title': node.get('title', node.get('name', '')),
            'description': node.get('description'),
            'rss_url': node.get('rss_url', node.get('feed_url')),
            'website': node.get('website'),
            'author': node.get('author'),
            'categories': node.get('categories', []),
            'language': node.get('language'),
            'created_at': node.get('created_at', datetime.now().isoformat())
        }
    
    def _standardize_relationship(self, rel: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize a relationship."""
        # Get actual relationship type from _type property
        rel_type = rel.get('_type', 'RELATED_TO')
        
        return {
            'type': rel_type,
            'properties': {
                'confidence': rel.get('confidence', rel.get('relationship_confidence', 1.0)),
                'created_at': rel.get('created_at'),
                'source_segment': rel.get('segment_id', rel.get('extracted_from_segment'))
            }
        }
    
    def _standardize_path(self, path: Any) -> Any:
        """Standardize a path result."""
        # For now, return path as-is
        # In a full implementation, would standardize nodes and relationships in path
        return path
    
    def _get_mapped_property(self, node: Dict[str, Any], *property_names: str) -> Any:
        """
        Get property value trying multiple possible names.
        
        Args:
            node: Node dictionary
            *property_names: Property names to try in order
            
        Returns:
            Property value or default
        """
        for prop_name in property_names:
            if prop_name in node:
                return node[prop_name]
        
        # Try reverse mapping
        for prop_name in property_names:
            if prop_name in self.property_mappings:
                mapped_name = self.property_mappings[prop_name]
                if mapped_name in node:
                    return node[mapped_name]
        
        # Return default if available
        for prop_name in property_names:
            if prop_name in self.default_values:
                return self.default_values[prop_name]
        
        return None
    
    def _map_properties(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generic property mapping for unknown node types."""
        mapped = {}
        
        for key, value in node.items():
            if key in ['id', '_type']:
                continue
                
            # Check if we have a mapping
            if key in self.property_mappings:
                mapped[self.property_mappings[key]] = value
            else:
                # Check reverse mapping
                reverse_mapped = False
                for new_prop, old_prop in self.property_mappings.items():
                    if old_prop == key:
                        mapped[new_prop] = value
                        reverse_mapped = True
                        break
                
                if not reverse_mapped:
                    # Keep original property
                    mapped[key] = value
        
        return mapped
    
    def handle_missing_properties(self, node: Dict[str, Any], required_properties: List[str]) -> Dict[str, Any]:
        """
        Handle missing properties gracefully.
        
        Args:
            node: Node dictionary
            required_properties: List of required property names
            
        Returns:
            Node with missing properties filled with defaults
        """
        for prop in required_properties:
            if prop not in node:
                if prop in self.default_values:
                    node[prop] = self.default_values[prop]
                    logger.debug(f"Added default value for missing property '{prop}': {self.default_values[prop]}")
                else:
                    logger.warning(f"Missing required property '{prop}' with no default value")
        
        return node
    
    def _log_evolution(self, evolution_type: str, details: str):
        """Log schema evolution discovery."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': evolution_type,
            'details': details
        }
        self.evolution_log.append(log_entry)
        logger.info(f"Schema evolution: {evolution_type} - {details}")
    
    def get_evolution_report(self) -> Dict[str, Any]:
        """
        Get report of discovered schema evolution.
        
        Returns:
            Dictionary with discovered types, properties, and evolution log
        """
        return {
            'discovered_types': list(self.discovered_types),
            'discovered_properties': {
                node_type: list(props) 
                for node_type, props in self.discovered_properties.items()
            },
            'evolution_log': self.evolution_log,
            'summary': {
                'new_types_count': len(self.discovered_types),
                'total_new_properties': sum(
                    len(props) for props in self.discovered_properties.values()
                ),
                'evolution_events': len(self.evolution_log)
            }
        }
    
    def validate_standardized_result(self, result: Dict[str, Any], expected_schema: Dict[str, Any]) -> bool:
        """
        Validate that standardized result matches expected schema.
        
        Args:
            result: Standardized result
            expected_schema: Expected schema definition
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation - check required properties exist
        if 'required' in expected_schema:
            for prop in expected_schema['required']:
                if prop not in result:
                    logger.error(f"Missing required property in standardized result: {prop}")
                    return False
        
        # Type validation
        if 'types' in expected_schema:
            for prop, expected_type in expected_schema['types'].items():
                if prop in result and not isinstance(result[prop], expected_type):
                    logger.error(f"Property {prop} has wrong type: expected {expected_type}, got {type(result[prop])}")
                    return False
        
        return True