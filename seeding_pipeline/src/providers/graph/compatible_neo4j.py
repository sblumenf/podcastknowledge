"""Backwards compatible Neo4j provider supporting both fixed and schemaless modes."""

import logging
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager

from src.providers.graph.base import BaseGraphProvider
from src.providers.graph.neo4j import Neo4jProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.core.plugin_discovery import provider_plugin
from src.migration.query_translator import QueryTranslator
from src.migration.result_standardizer import ResultStandardizer
from src.core.models import Podcast, Episode, Segment

logger = logging.getLogger(__name__)


@provider_plugin('graph', 'compatible', version='1.0.0', author='Neo4j', 
                description='Compatible Neo4j provider for mixed mode')
class CompatibleNeo4jProvider(BaseGraphProvider):
    """
    Backwards compatible graph provider that supports both fixed and schemaless schemas.
    
    This provider enables gradual migration by:
    - Accepting both fixed and schemaless storage requests
    - Routing to appropriate implementation based on configuration
    - Providing unified query interface
    - Handling mixed-schema graphs
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize compatible provider with configuration."""
        super().__init__(config)
        
        # Migration configuration
        self.schema_mode = config.get('schema_mode', 'fixed')  # 'fixed', 'schemaless', 'mixed'
        self.migration_mode = config.get('migration_mode', False)  # Dual write mode
        self.prefer_schemaless = config.get('prefer_schemaless', False)
        
        # Initialize providers based on mode
        self.fixed_provider = None
        self.schemaless_provider = None
        
        # Migration utilities
        self.query_translator = QueryTranslator()
        self.result_standardizer = ResultStandardizer()
        
        # Feature flags
        self.feature_flags = {
            'use_schemaless_extraction': config.get('use_schemaless_extraction', False),
            'use_schemaless_query': config.get('use_schemaless_query', False),
            'log_migration_operations': config.get('log_migration_operations', True),
            'validate_dual_writes': config.get('validate_dual_writes', False)
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize the appropriate providers based on configuration."""
        if self.schema_mode in ['fixed', 'mixed']:
            self.fixed_provider = Neo4jProvider(self.config)
            
        if self.schema_mode in ['schemaless', 'mixed']:
            self.schemaless_provider = SchemalessNeo4jProvider(self.config)
            
        if self.schema_mode == 'mixed' and not (self.fixed_provider and self.schemaless_provider):
            raise ValueError("Mixed mode requires both fixed and schemaless providers")
    
    def _initialize_driver(self) -> None:
        """Initialize driver(s) based on mode."""
        if self.fixed_provider:
            self.fixed_provider._initialize_driver()
            
        if self.schemaless_provider:
            self.schemaless_provider._initialize_driver()
            
        self._initialized = True
    
    def connect(self) -> None:
        """Connect to Neo4j."""
        self._ensure_initialized()
        
        if self.fixed_provider:
            self.fixed_provider.connect()
            
        if self.schemaless_provider:
            self.schemaless_provider.connect()
            
        logger.info(f"Compatible provider connected in {self.schema_mode} mode")
    
    def disconnect(self) -> None:
        """Disconnect from Neo4j."""
        if self.fixed_provider:
            self.fixed_provider.disconnect()
            
        if self.schemaless_provider:
            self.schemaless_provider.disconnect()
            
        self._initialized = False
    
    @contextmanager
    def session(self):
        """Create a session with the active provider."""
        provider = self._get_active_provider()
        with provider.session() as session:
            yield session
    
    def setup_schema(self) -> None:
        """Set up schema for both fixed and schemaless modes."""
        if self.fixed_provider:
            logger.info("Setting up fixed schema...")
            self.fixed_provider.setup_schema()
            
        if self.schemaless_provider:
            logger.info("Setting up schemaless indexes...")
            self.schemaless_provider.setup_schema()
    
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """
        Create a node, routing to appropriate provider.
        
        In migration mode, writes to both schemas.
        """
        node_id = None
        
        if self.migration_mode:
            # Dual write mode
            if self.fixed_provider:
                node_id = self.fixed_provider.create_node(node_type, properties)
                
            if self.schemaless_provider:
                schemaless_id = self.schemaless_provider.create_node(node_type, properties)
                
                # Validate consistency if enabled
                if self.feature_flags['validate_dual_writes'] and node_id != schemaless_id:
                    logger.warning(f"ID mismatch in dual write: fixed={node_id}, schemaless={schemaless_id}")
                    
            if self.feature_flags['log_migration_operations']:
                logger.debug(f"Dual write node: type={node_type}, id={node_id}")
        else:
            # Single mode write
            provider = self._get_write_provider()
            node_id = provider.create_node(node_type, properties)
            
        return node_id
    
    def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a relationship, routing to appropriate provider."""
        if self.migration_mode:
            # Dual write mode
            if self.fixed_provider:
                self.fixed_provider.create_relationship(source_id, target_id, rel_type, properties)
                
            if self.schemaless_provider:
                self.schemaless_provider.create_relationship(source_id, target_id, rel_type, properties)
                
            if self.feature_flags['log_migration_operations']:
                logger.debug(f"Dual write relationship: {source_id}-[{rel_type}]->{target_id}")
        else:
            # Single mode write
            provider = self._get_write_provider()
            provider.create_relationship(source_id, target_id, rel_type, properties)
    
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a query with appropriate translation.
        
        Handles query translation and result standardization transparently.
        """
        if self.feature_flags['use_schemaless_query'] and self.schemaless_provider:
            # Translate query if needed
            if self._is_fixed_schema_query(cypher):
                translated_query = self.query_translator.translate_fixed_to_schemaless(cypher)
                if self.feature_flags['log_migration_operations']:
                    logger.debug(f"Translated query: {cypher} -> {translated_query}")
                cypher = translated_query
            
            # Execute on schemaless
            results = self.schemaless_provider.query(cypher, parameters)
            
            # Standardize results if needed
            if self._needs_standardization(results):
                results = self.result_standardizer.standardize_results(results)
                
            return results
        else:
            # Use fixed provider
            provider = self._get_query_provider()
            return provider.query(cypher, parameters)
    
    def delete_node(self, node_id: str) -> None:
        """Delete a node from appropriate provider(s)."""
        if self.migration_mode:
            # Delete from both
            if self.fixed_provider:
                self.fixed_provider.delete_node(node_id)
                
            if self.schemaless_provider:
                self.schemaless_provider.delete_node(node_id)
        else:
            provider = self._get_write_provider()
            provider.delete_node(node_id)
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Update node in appropriate provider(s)."""
        if self.migration_mode:
            # Update in both
            if self.fixed_provider:
                self.fixed_provider.update_node(node_id, properties)
                
            if self.schemaless_provider:
                self.schemaless_provider.update_node(node_id, properties)
        else:
            provider = self._get_write_provider()
            provider.update_node(node_id, properties)
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node from appropriate provider."""
        provider = self._get_query_provider()
        node = provider.get_node(node_id)
        
        # Standardize if from schemaless
        if node and self.feature_flags['use_schemaless_query'] and self.schemaless_provider:
            standardized = self.result_standardizer.standardize_results([node])
            return standardized[0] if standardized else None
            
        return node
    
    def store_podcast(self, podcast: Podcast) -> str:
        """Store podcast using extraction mode preference."""
        if self.feature_flags['use_schemaless_extraction'] and self.schemaless_provider:
            return self.schemaless_provider.store_podcast(podcast)
        elif self.fixed_provider:
            # Use base class method which calls create_node
            return self.fixed_provider.create_podcast(podcast)
        else:
            raise RuntimeError("No provider available for storing podcast")
    
    def store_episode(self, episode: Episode, podcast_id: str) -> str:
        """Store episode using extraction mode preference."""
        if self.feature_flags['use_schemaless_extraction'] and self.schemaless_provider:
            return self.schemaless_provider.store_episode(episode, podcast_id)
        elif self.fixed_provider:
            # Use base class method
            return self.fixed_provider.create_episode(episode)
        else:
            raise RuntimeError("No provider available for storing episode")
    
    def store_segments(self, segments: List[Segment], episode: Episode, podcast: Podcast) -> List[Dict[str, Any]]:
        """
        Store segments using extraction mode preference.
        
        This is where schemaless extraction happens if enabled.
        """
        if self.feature_flags['use_schemaless_extraction'] and self.schemaless_provider:
            logger.info(f"Processing {len(segments)} segments with schemaless extraction")
            return self.schemaless_provider.store_segments(segments, episode, podcast)
        elif self.fixed_provider:
            # Fixed schema doesn't have store_segments, use create_segment
            results = []
            for segment in segments:
                segment_id = self.fixed_provider.create_segment(segment)
                results.append({
                    'segment_id': segment_id,
                    'status': 'stored',
                    'mode': 'fixed'
                })
            return results
        else:
            raise RuntimeError("No provider available for storing segments")
    
    def _get_active_provider(self) -> BaseGraphProvider:
        """Get the currently active provider."""
        if self.schema_mode == 'fixed':
            return self.fixed_provider
        elif self.schema_mode == 'schemaless':
            return self.schemaless_provider
        else:  # mixed mode
            return self.schemaless_provider if self.prefer_schemaless else self.fixed_provider
    
    def _get_write_provider(self) -> BaseGraphProvider:
        """Get provider for write operations."""
        if self.schema_mode == 'mixed':
            return self.schemaless_provider if self.prefer_schemaless else self.fixed_provider
        return self._get_active_provider()
    
    def _get_query_provider(self) -> BaseGraphProvider:
        """Get provider for query operations."""
        if self.feature_flags['use_schemaless_query'] and self.schemaless_provider:
            return self.schemaless_provider
        return self._get_active_provider()
    
    def _is_fixed_schema_query(self, cypher: str) -> bool:
        """Check if query uses fixed schema patterns."""
        fixed_patterns = [
            r'\b(Entity|Quote|Segment|Episode|Podcast|Insight|Topic|Speaker)\b',
            r':\s*(Entity|Quote|Segment|Episode|Podcast|Insight|Topic|Speaker)',
        ]
        
        import re
        for pattern in fixed_patterns:
            if re.search(pattern, cypher):
                return True
        return False
    
    def _needs_standardization(self, results: List[Dict[str, Any]]) -> bool:
        """Check if results need standardization."""
        if not results:
            return False
            
        # Check first result for schemaless indicators
        first = results[0]
        if isinstance(first, dict):
            # Look for _type property indicating schemaless
            if 'n' in first and isinstance(first['n'], dict):
                return '_type' in first['n']
            elif '_type' in first:
                return True
                
        return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status and statistics."""
        status = {
            'mode': self.schema_mode,
            'migration_mode': self.migration_mode,
            'feature_flags': self.feature_flags,
            'providers': {
                'fixed': self.fixed_provider is not None,
                'schemaless': self.schemaless_provider is not None
            }
        }
        
        # Add evolution report if available
        if hasattr(self.result_standardizer, 'get_evolution_report'):
            status['schema_evolution'] = self.result_standardizer.get_evolution_report()
            
        return status
    
    def enable_feature(self, feature: str, enabled: bool = True):
        """Enable or disable a feature flag."""
        if feature in self.feature_flags:
            self.feature_flags[feature] = enabled
            logger.info(f"Feature '{feature}' {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning(f"Unknown feature flag: {feature}")
    
    def set_migration_mode(self, mode: str):
        """
        Set the migration mode.
        
        Args:
            mode: One of 'fixed', 'schemaless', 'mixed'
        """
        if mode not in ['fixed', 'schemaless', 'mixed']:
            raise ValueError(f"Invalid migration mode: {mode}")
            
        self.schema_mode = mode
        logger.info(f"Migration mode set to: {mode}")