"""Schemaless Neo4j graph provider using SimpleKGPipeline."""

import logging
from typing import Dict, Any, List, Optional, Iterator
from contextlib import contextmanager
import asyncio
import yaml
from pathlib import Path
from datetime import datetime

from src.providers.graph.base import BaseGraphProvider
from src.core.exceptions import ProviderError, ConnectionError
from src.providers.llm.gemini_adapter import create_gemini_adapter
from src.providers.embeddings.sentence_transformer_adapter import create_sentence_transformer_adapter
from src.processing.schemaless_preprocessor import SegmentPreprocessor
from src.processing.schemaless_entity_resolution import SchemalessEntityResolver
from src.providers.graph.metadata_enricher import SchemalessMetadataEnricher
from src.processing.schemaless_quote_extractor import SchemalessQuoteExtractor
from src.core.models import Podcast, Episode, Segment

logger = logging.getLogger(__name__)


class SchemalessNeo4jProvider(BaseGraphProvider):
    """
    Schemaless graph provider using neo4j-graphrag's SimpleKGPipeline.
    
    This provider implements truly schemaless knowledge graph extraction
    by leveraging SimpleKGPipeline and custom pre/post-processing components.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize schemaless provider with configuration."""
        super().__init__(config)
        
        # Initialize adapters
        self.llm_adapter = None
        self.embedding_adapter = None
        
        # Initialize custom components with config
        self.preprocessor = SegmentPreprocessor()
        
        # Create entity resolver with config threshold
        from src.processing.schemaless_entity_resolution import EntityResolutionConfig
        entity_config = EntityResolutionConfig(
            similarity_threshold=config.get('entity_resolution_threshold', 0.85)
        )
        self.entity_resolver = SchemalessEntityResolver(entity_config)
        
        self.metadata_enricher = None
        self.quote_extractor = SchemalessQuoteExtractor()
        
        # SimpleKGPipeline instance
        self.pipeline = None
        
        # Neo4j driver (from base class)
        self._driver = None
        
        # Performance monitoring
        self._extraction_times = []
        self._entity_counts = []
        self._relationship_counts = []
        
    def _initialize_driver(self) -> None:
        """Initialize Neo4j driver and SimpleKGPipeline."""
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
            # Initialize Neo4j driver
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=self.config.get('pool_size', 50),
                max_connection_lifetime=self.config.get('max_connection_lifetime', 3600)
            )
            logger.info(f"Initialized Neo4j driver for {self.uri}")
            
            # Initialize adapters
            self._initialize_adapters()
            
            # Initialize SimpleKGPipeline
            self._initialize_pipeline()
            
            # Load property mappings
            self.load_property_mappings()
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize schemaless provider: {e}")
    
    def _initialize_adapters(self):
        """Initialize LLM and embedding adapters."""
        # Create Gemini adapter
        if 'llm_config' in self.config:
            llm_provider = self.config['llm_config'].get('provider', 'gemini')
            if llm_provider == 'gemini':
                self.llm_adapter = create_gemini_adapter(self.config['llm_config'])
            else:
                raise ProviderError(f"Unsupported LLM provider: {llm_provider}")
        else:
            # Use default Gemini config
            self.llm_adapter = create_gemini_adapter({})
            
        # Create embedding adapter
        if 'embedding_config' in self.config:
            self.embedding_adapter = create_sentence_transformer_adapter(
                self.config['embedding_config']
            )
        else:
            # Use default sentence transformer
            self.embedding_adapter = create_sentence_transformer_adapter({})
            
        # Initialize metadata enricher
        self.metadata_enricher = SchemalessMetadataEnricher()
        
    def _initialize_pipeline(self):
        """Initialize SimpleKGPipeline with adapters and configuration."""
        try:
            from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
            
            # Create pipeline configuration
            pipeline_config = {
                'llm': self.llm_adapter,
                'driver': self._driver,
                'embedder': self.embedding_adapter,
                'database': self.database,
                # Additional configuration
                'entities': {
                    'perform_entity_resolution': False,  # We handle this in post-processing
                },
                'relationships': {
                    'create_relationships': True,
                },
                'from_pdf': False  # We're processing text, not PDFs
            }
            
            # Initialize pipeline
            self.pipeline = SimpleKGPipeline(**pipeline_config)
            logger.info("Initialized SimpleKGPipeline for schemaless extraction")
            
        except ImportError:
            raise ProviderError(
                "neo4j-graphrag is not installed. "
                "Install with: pip install neo4j-graphrag"
            )
        except Exception as e:
            raise ProviderError(f"Failed to initialize SimpleKGPipeline: {e}")
    
    @property
    def driver(self):
        """Public accessor for Neo4j driver."""
        return self._driver
    
    def connect(self) -> None:
        """Connect to Neo4j."""
        self._ensure_initialized()
        
        # Verify connection
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run("RETURN 'Connected' AS status")
                status = result.single()["status"]
                logger.info(f"Schemaless Neo4j connection verified: {status}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from Neo4j."""
        if self._driver:
            try:
                self._driver.close()
                self._driver = None
                self._initialized = False
                logger.info("Disconnected from schemaless Neo4j")
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
    
    def setup_schema(self) -> None:
        """
        Set up minimal schema for schemaless operation.
        
        In schemaless mode, we only create indexes for performance,
        not type constraints.
        """
        with self.session() as session:
            # Create indexes for common lookup patterns
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.id)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATIONSHIP]-() ON (r.type)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.episode_id)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.podcast_id)"
            ]
            
            for index_query in indexes:
                try:
                    session.run(index_query)
                    logger.info(f"Created index: {index_query}")
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
            
            logger.info("Schemaless schema setup complete")
    
    def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """
        Create a node with flexible properties.
        
        In schemaless mode, node_type becomes a property rather than a label.
        """
        with self.session() as session:
            # Ensure node has an ID
            if 'id' not in properties:
                raise ValueError(f"Node must have an 'id' property")
            
            # Add type as a property
            properties['_type'] = node_type
            
            # Enforce property limit
            max_properties = self.config.get('max_properties_per_node', 50)
            if len(properties) > max_properties:
                logger.warning(f"Node has {len(properties)} properties, exceeding limit of {max_properties}. "
                              f"Truncating to most important properties.")
                # Keep essential properties and sort others by importance/name
                essential = {'id', '_type', 'name', 'segment_id', 'episode_id', 'podcast_id'}
                essential_props = {k: v for k, v in properties.items() if k in essential}
                other_props = {k: v for k, v in properties.items() if k not in essential}
                
                # Keep essential + up to remaining limit of other properties
                remaining_limit = max_properties - len(essential_props)
                if remaining_limit > 0:
                    sorted_others = sorted(other_props.items())[:remaining_limit]
                    properties = {**essential_props, **dict(sorted_others)}
                else:
                    properties = essential_props
            
            # Build property string for Cypher
            prop_strings = []
            params = {}
            for key, value in properties.items():
                if value is not None:
                    prop_strings.append(f"{key}: ${key}")
                    params[key] = value
            
            props_str = '{' + ', '.join(prop_strings) + '}'
            
            # Create node with generic Node label
            query = f"""
            CREATE (n:Node {props_str})
            RETURN n.id as id
            """
            
            result = session.run(query, params)
            return result.single()['id']
    
    def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a relationship with flexible properties."""
        with self.session() as session:
            # Normalize relationship type
            normalized_type = self._normalize_relationship_type(rel_type)
            
            # Build properties for relationship
            rel_props = properties or {}
            rel_props['_type'] = normalized_type
            rel_props['created_at'] = rel_props.get('created_at', 
                                                    datetime.now().isoformat())
            
            # Build property string
            prop_strings = []
            params = {
                'source_id': source_id,
                'target_id': target_id
            }
            
            for key, value in rel_props.items():
                if value is not None:
                    prop_strings.append(f"{key}: $rel_{key}")
                    params[f"rel_{key}"] = value
            
            props_str = '{' + ', '.join(prop_strings) + '}' if prop_strings else ''
            
            # Create relationship with generic RELATIONSHIP type
            query = f"""
            MATCH (a:Node {{id: $source_id}})
            MATCH (b:Node {{id: $target_id}})
            CREATE (a)-[r:RELATIONSHIP {props_str}]->(b)
            """
            
            session.run(query, params)
    
    def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        with self.session() as session:
            result = session.run(cypher, parameters or {})
            return [dict(record) for record in result]
    
    def delete_node(self, node_id: str) -> None:
        """Delete a node by ID."""
        with self.session() as session:
            query = "MATCH (n:Node {id: $id}) DETACH DELETE n"
            session.run(query, {'id': node_id})
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Update node properties."""
        with self.session() as session:
            # Build SET clause
            set_strings = []
            params = {'id': node_id}
            
            for key, value in properties.items():
                set_strings.append(f"n.{key} = ${key}")
                params[key] = value
            
            set_clause = ', '.join(set_strings)
            
            query = f"""
            MATCH (n:Node {{id: $id}})
            SET {set_clause}
            """
            
            session.run(query, params)
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        with self.session() as session:
            query = "MATCH (n:Node {id: $id}) RETURN n"
            result = session.run(query, {'id': node_id})
            record = result.single()
            return dict(record['n']) if record else None
    
    def store_podcast(self, podcast: Podcast) -> str:
        """Store podcast with flexible properties."""
        properties = {
            'id': podcast.id,
            'title': podcast.title,
            'description': podcast.description,
            'rss_url': podcast.rss_url,
            'author': podcast.author,
            'categories': podcast.categories,
            'language': getattr(podcast, 'language', None),
            'website': getattr(podcast, 'website', None),
            'created_at': datetime.now().isoformat()
        }
        
        # Remove None values
        properties = {k: v for k, v in properties.items() if v is not None}
        
        return self.create_node('Podcast', properties)
    
    def store_episode(self, episode: Episode, podcast_id: str) -> str:
        """Store episode with all metadata."""
        properties = {
            'id': episode.id,
            'title': episode.title,
            'description': episode.description,
            'audio_url': episode.audio_url,
            'publication_date': episode.publication_date.isoformat() if episode.publication_date else None,
            'duration': episode.duration,
            'podcast_id': podcast_id,
            'created_at': datetime.now().isoformat()
        }
        
        # Remove None values
        properties = {k: v for k, v in properties.items() if v is not None}
        
        # Create episode node
        episode_id = self.create_node('Episode', properties)
        
        # Create relationship to podcast
        self.create_relationship(
            episode_id,
            podcast_id,
            'BELONGS_TO',
            {'created_at': datetime.now().isoformat()}
        )
        
        return episode_id
    
    def store_segments(self, segments: List[Segment], episode: Episode, podcast: Podcast) -> List[Dict[str, Any]]:
        """
        Process segments through SimpleKGPipeline.
        
        This is the main entry point for schemaless extraction.
        """
        results = []
        
        for segment in segments:
            try:
                # Process single segment
                result = self.process_segment_schemaless(segment, episode, podcast)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process segment: {e}")
                results.append({
                    'segment_id': segment.id,
                    'error': str(e),
                    'status': 'failed'
                })
        
        return results
    
    def process_segment_schemaless(self, segment: Segment, episode: Episode, podcast: Podcast) -> Dict[str, Any]:
        """
        Process a single segment through the schemaless pipeline.
        
        Steps:
        1. Preprocess segment text with metadata injection
        2. Run SimpleKGPipeline for extraction
        3. Post-process results with entity resolution
        4. Enrich with metadata
        5. Extract quotes
        6. Store results in graph
        """
        import time
        start_time = time.time()
        
        logger.info(f"Starting schemaless extraction for segment {segment.id} "
                   f"from episode '{episode.title}' of podcast '{podcast.title}'")
        
        # Step 1: Preprocess segment text
        episode_metadata = {
            'title': episode.title,
            'podcast': podcast.title,
            'episode_id': episode.id,
            'podcast_id': podcast.id
        }
        
        preprocessed = self.preprocessor.prepare_segment_text(segment, episode_metadata)
        enriched_text = preprocessed['enriched_text']
        
        # Step 2: Run SimpleKGPipeline
        extraction_start = time.time()
        try:
            # SimpleKGPipeline expects async execution
            import nest_asyncio
            nest_asyncio.apply()  # Allow nested event loops
            
            # Run the async pipeline
            extraction_results = asyncio.run(self.pipeline.run_async(enriched_text))
            extraction_time = time.time() - extraction_start
            
            logger.info(f"SimpleKGPipeline extracted {len(extraction_results.get('entities', []))} entities "
                       f"and {len(extraction_results.get('relationships', []))} relationships "
                       f"in {extraction_time:.2f}s")
            
            # Record metrics
            self._extraction_times.append(extraction_time)
            self._entity_counts.append(len(extraction_results.get('entities', [])))
            self._relationship_counts.append(len(extraction_results.get('relationships', [])))
        except ImportError:
            # If nest_asyncio not available, try alternative approach
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                extraction_results = loop.run_until_complete(self.pipeline.run_async(enriched_text))
                loop.close()
            except Exception as e:
                logger.error(f"SimpleKGPipeline extraction failed: {e}")
                # Fallback to empty results
                extraction_results = {'entities': [], 'relationships': []}
        except Exception as e:
            logger.error(f"SimpleKGPipeline extraction failed: {e}")
            # Fallback to empty results
            extraction_results = {'entities': [], 'relationships': []}
        
        # Step 3: Filter by confidence threshold
        confidence_threshold = self.config.get('schemaless_confidence_threshold', 0.7)
        original_entity_count = len(extraction_results.get('entities', []))
        original_rel_count = len(extraction_results.get('relationships', []))
        
        if extraction_results.get('entities'):
            # Filter entities by confidence
            filtered_entities = [
                e for e in extraction_results['entities']
                if e.get('confidence', 1.0) >= confidence_threshold
            ]
            entities_filtered = len(extraction_results['entities']) - len(filtered_entities)
            if entities_filtered > 0:
                logger.info(f"Filtered {entities_filtered} entities below confidence threshold {confidence_threshold}")
            extraction_results['entities'] = filtered_entities
        
        # Step 4: Entity resolution
        pre_resolution_count = len(extraction_results.get('entities', []))
        if extraction_results.get('entities'):
            resolution_results = self.entity_resolver.resolve_entities(
                extraction_results['entities']
            )
            extraction_results['entities'] = resolution_results['resolved_entities']
            resolved_count = pre_resolution_count - len(extraction_results['entities'])
            if resolved_count > 0:
                logger.info(f"Resolved {resolved_count} duplicate entities through entity resolution")
            extraction_results['resolution_stats'] = resolution_results['metrics']
        
        # Step 4: Metadata enrichment
        episode_metadata = {
            'id': episode.id,
            'title': episode.title,
            'podcast_id': podcast.id
        }
        podcast_metadata = {
            'id': podcast.id,
            'title': podcast.title
        }
        
        enriched_results = self.metadata_enricher.enrich_extraction_results(
            extraction_results,
            segment,
            episode_metadata,
            podcast_metadata,
            embedder=self.embedding_adapter.embed_query if self.embedding_adapter else None
        )
        extraction_results = enriched_results
        
        # Step 5: Quote extraction
        quote_results = self.quote_extractor.extract_quotes(segment, extraction_results)
        
        # Integrate quotes into results
        if quote_results['quotes']:
            extraction_results = quote_results.get('integrated_results', extraction_results)
        
        # Step 6: Store results in graph
        stored_results = self.store_extraction_results(
            extraction_results,
            segment,
            episode,
            podcast
        )
        
        # Log total processing time and performance metrics
        total_time = time.time() - start_time
        logger.info(f"Completed schemaless extraction for segment {segment.id} in {total_time:.2f}s")
        
        # Log performance metrics periodically
        if len(self._extraction_times) % 10 == 0:
            avg_extraction_time = sum(self._extraction_times) / len(self._extraction_times)
            avg_entities = sum(self._entity_counts) / len(self._entity_counts)
            avg_relationships = sum(self._relationship_counts) / len(self._relationship_counts)
            
            logger.info(f"Performance metrics (last {len(self._extraction_times)} segments): "
                       f"Avg extraction time: {avg_extraction_time:.2f}s, "
                       f"Avg entities: {avg_entities:.1f}, "
                       f"Avg relationships: {avg_relationships:.1f}")
        
        return {
            'segment_id': segment.id,
            'status': 'success',
            'entities_extracted': len(extraction_results.get('entities', [])),
            'relationships_extracted': len(extraction_results.get('relationships', [])),
            'quotes_extracted': len(quote_results.get('quotes', [])),
            'preprocessing_metrics': preprocessed.get('metrics', {}),
            'resolution_stats': extraction_results.get('resolution_stats', {}),
            'stored_results': stored_results,
            'metrics': {
                'extraction_time': extraction_time,
                'total_time': total_time,
                'entities_filtered': original_entity_count - len(extraction_results.get('entities', [])),
                'entities_resolved': resolved_count if 'resolved_count' in locals() else 0,
                'relationships_filtered': original_rel_count - len(extraction_results.get('relationships', []))
            }
        }
    
    def store_extraction_results(
        self,
        extraction_results: Dict[str, Any],
        segment: Segment,
        episode: Episode,
        podcast: Podcast
    ) -> Dict[str, Any]:
        """
        Store SimpleKGPipeline extraction results in the graph.
        
        This method handles the flexible schema from SimpleKGPipeline.
        """
        stored_entities = []
        stored_relationships = []
        
        # Store segment first
        segment_properties = {
            'id': segment.id,
            'text': segment.text,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'speaker': segment.speaker,
            'confidence': segment.confidence,
            'episode_id': episode.id,
            'podcast_id': podcast.id
        }
        segment_node_id = self.create_node('Segment', segment_properties)
        
        # Create segment -> episode relationship
        self.create_relationship(
            segment_node_id,
            episode.id,
            'PART_OF',
            {'order': segment.start_time}
        )
        
        # Store entities
        entity_id_map = {}
        for entity in extraction_results.get('entities', []):
            # Use the enriched properties
            node_properties = entity.copy()
            
            # Ensure required fields
            if 'id' not in node_properties:
                node_properties['id'] = f"entity_{segment.id}_{len(stored_entities)}"
            
            # Add segment reference
            node_properties['segment_id'] = segment.id
            node_properties['episode_id'] = episode.id
            node_properties['podcast_id'] = podcast.id
            
            # Store with generic type (actual type is in properties)
            entity_type = node_properties.get('type', 'Entity')
            stored_id = self.create_node(entity_type, node_properties)
            
            # Map for relationships
            entity_id_map[node_properties['id']] = stored_id
            
            # Create entity -> segment relationship
            self.create_relationship(
                stored_id,
                segment_node_id,
                'MENTIONED_IN',
                {'timestamp': segment.start_time}
            )
            
            stored_entities.append(stored_id)
        
        # Store relationships
        for rel in extraction_results.get('relationships', []):
            source = rel.get('source')
            target = rel.get('target')
            rel_type = rel.get('type', 'RELATED_TO')
            
            # Find node IDs
            source_id = entity_id_map.get(source, source)
            target_id = entity_id_map.get(target, target)
            
            # Only create if both nodes exist
            if source_id and target_id:
                rel_properties = {
                    'segment_id': segment.id,
                    'confidence': rel.get('confidence', 1.0)
                }
                
                # Add any additional properties from the relationship
                for key, value in rel.items():
                    if key not in ['source', 'target', 'type']:
                        rel_properties[key] = value
                
                self.create_relationship(
                    source_id,
                    target_id,
                    rel_type,
                    rel_properties
                )
                
                stored_relationships.append({
                    'source': source_id,
                    'target': target_id,
                    'type': rel_type
                })
        
        return {
            'segment_node_id': segment_node_id,
            'stored_entities': stored_entities,
            'stored_relationships': stored_relationships
        }
    
    def _fallback_extraction(self, text: str) -> Dict[str, Any]:
        """
        Fallback extraction method using direct LLM calls.
        
        This is used when SimpleKGPipeline fails but we still want to attempt extraction.
        """
        logger.info("Attempting fallback extraction using direct LLM")
        
        try:
            # Simple prompt for entity and relationship extraction
            prompt = f"""Extract entities and relationships from the following text.

Text: {text[:2000]}  # Limit text length for fallback

Return in this format:
Entities: [list of important people, organizations, concepts]
Relationships: [list of connections between entities]

Be concise and focus on the most important information."""

            response = self.llm_adapter.generate(prompt)
            
            # Parse response into entities and relationships
            entities = []
            relationships = []
            
            # Very basic parsing - in production this would be more sophisticated
            lines = response.split('\n')
            parsing_entities = False
            parsing_relationships = False
            
            for line in lines:
                if 'Entities:' in line:
                    parsing_entities = True
                    parsing_relationships = False
                elif 'Relationships:' in line:
                    parsing_entities = False
                    parsing_relationships = True
                elif parsing_entities and line.strip():
                    # Create basic entity
                    entity_text = line.strip().strip('-').strip('*').strip()
                    if entity_text:
                        entities.append({
                            'id': entity_text.lower().replace(' ', '_'),
                            'name': entity_text,
                            'type': 'Entity',
                            'confidence': 0.5  # Lower confidence for fallback
                        })
                elif parsing_relationships and line.strip():
                    # Very basic relationship parsing
                    rel_text = line.strip().strip('-').strip('*').strip()
                    if rel_text:
                        # Try to extract source and target
                        parts = rel_text.split(' ')
                        if len(parts) >= 3:
                            relationships.append({
                                'source': parts[0].lower().replace(' ', '_'),
                                'target': parts[-1].lower().replace(' ', '_'),
                                'type': 'RELATED_TO',
                                'confidence': 0.5
                            })
            
            logger.info(f"Fallback extraction found {len(entities)} entities and {len(relationships)} relationships")
            return {'entities': entities, 'relationships': relationships}
            
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
            return {'entities': [], 'relationships': []}
    
    def _normalize_relationship_type(self, rel_type: str) -> str:
        """
        Normalize relationship types to consistent format.
        
        Examples:
        - "works at" → "WORKS_AT"
        - "is a" → "IS_A"
        - "related-to" → "RELATED_TO"
        """
        # Check if normalization is enabled in config
        if not self.config.get('relationship_normalization', True):
            return rel_type
            
        # Convert to uppercase and replace spaces/hyphens with underscores
        normalized = rel_type.upper()
        normalized = normalized.replace(' ', '_')
        normalized = normalized.replace('-', '_')
        
        # Remove any non-alphanumeric characters except underscores
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        
        # Check if we have a mapping rule
        if hasattr(self, '_relationship_type_rules'):
            return self._relationship_type_rules.get(rel_type.lower(), normalized)
        
        return normalized
    
    def load_property_mappings(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load property mappings from configuration file."""
        if not config_path:
            config_path = Path(__file__).parent.parent.parent.parent / 'config' / 'schemaless_properties.yml'
        
        try:
            with open(config_path, 'r') as f:
                mappings = yaml.safe_load(f)
                
            # Cache frequently used mappings
            self._entity_mappings = mappings.get('entity_mappings', {})
            self._segment_mappings = mappings.get('segment_mappings', {})
            self._quote_mappings = mappings.get('quote_mappings', {})
            self._relationship_mappings = mappings.get('relationship_mappings', {})
            self._relationship_type_rules = mappings.get('relationship_type_rules', {})
            self._validation_rules = mappings.get('validation_rules', {})
            self._default_values = mappings.get('default_values', {})
            
            logger.info(f"Loaded property mappings from {config_path}")
            return mappings
            
        except Exception as e:
            logger.warning(f"Failed to load property mappings: {e}")
            return {}
    
    def validate_properties(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate properties without strict typing.
        
        This performs loose validation to ensure data quality while
        maintaining flexibility of schemaless approach.
        """
        if not hasattr(self, '_validation_rules'):
            self.load_property_mappings()
        
        validated = properties.copy()
        
        # Check required properties
        required = self._validation_rules.get('required_properties', {}).get(node_type, [])
        for prop in required:
            if prop not in validated:
                # Use default value if available
                if prop in self._default_values:
                    validated[prop] = self._default_values[prop]
                else:
                    logger.warning(f"Missing required property '{prop}' for {node_type}")
        
        # Validate property types (loose validation)
        property_types = self._validation_rules.get('property_types', {})
        
        # Numeric validation
        for prop in property_types.get('numeric', []):
            if prop in validated and validated[prop] is not None:
                try:
                    validated[prop] = float(validated[prop])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric value for '{prop}': {validated[prop]}")
                    validated[prop] = self._default_values.get(prop, 0.0)
        
        # Boolean validation
        for prop in property_types.get('boolean', []):
            if prop in validated and validated[prop] is not None:
                validated[prop] = bool(validated[prop])
        
        # Array validation
        for prop in property_types.get('array', []):
            if prop in validated and validated[prop] is not None:
                if not isinstance(validated[prop], list):
                    validated[prop] = [validated[prop]]
        
        return validated
    
    def generate_property_documentation(self, output_path: Optional[str] = None) -> str:
        """
        Generate documentation for all properties in the schemaless graph.
        
        This helps maintain understanding of the flexible schema.
        """
        if not hasattr(self, '_validation_rules'):
            self.load_property_mappings()
        
        doc_lines = [
            "# Schemaless Graph Property Documentation",
            f"\nGenerated on: {datetime.now().isoformat()}",
            "\n## Property Mappings\n"
        ]
        
        # Document entity properties
        doc_lines.append("### Entity Properties")
        for old_prop, new_prop in self._entity_mappings.items():
            doc_lines.append(f"- `{old_prop}` → `{new_prop}`")
        
        # Document segment properties
        doc_lines.append("\n### Segment Properties")
        for old_prop, new_prop in self._segment_mappings.items():
            doc_lines.append(f"- `{old_prop}` → `{new_prop}`")
        
        # Document quote properties
        doc_lines.append("\n### Quote Properties")
        for old_prop, new_prop in self._quote_mappings.items():
            doc_lines.append(f"- `{old_prop}` → `{new_prop}`")
        
        # Document relationship properties
        doc_lines.append("\n### Relationship Properties")
        for old_prop, new_prop in self._relationship_mappings.items():
            doc_lines.append(f"- `{old_prop}` → `{new_prop}`")
        
        # Document relationship type normalization
        doc_lines.append("\n## Relationship Type Normalization")
        for original, normalized in self._relationship_type_rules.items():
            doc_lines.append(f"- `{original}` → `{normalized}`")
        
        # Document validation rules
        doc_lines.append("\n## Validation Rules")
        doc_lines.append("\n### Required Properties")
        for node_type, props in self._validation_rules.get('required_properties', {}).items():
            doc_lines.append(f"\n**{node_type}**:")
            for prop in props:
                doc_lines.append(f"- {prop}")
        
        # Document default values
        doc_lines.append("\n## Default Values")
        for prop, value in self._default_values.items():
            doc_lines.append(f"- `{prop}`: {value}")
        
        # Get property descriptions
        property_docs = yaml.safe_load(open(config_path, 'r')).get('property_docs', {}) if config_path else {}
        if property_docs:
            doc_lines.append("\n## Property Descriptions")
            for prop, desc in property_docs.items():
                doc_lines.append(f"\n**{prop}**: {desc}")
        
        documentation = '\n'.join(doc_lines)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(documentation)
            logger.info(f"Property documentation saved to {output_path}")
        
        return documentation