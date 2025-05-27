"""Main orchestrator for the podcast knowledge extraction pipeline."""

import os
import signal
import sys
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
import logging

from src.core.config import PipelineConfig, SeedingConfig
from src.core.exceptions import PipelineError, ConfigurationError
from src.factories.provider_factory import ProviderFactory
from src.providers.audio.base import AudioProvider
from src.providers.llm.base import LLMProvider
from src.providers.graph.base import GraphProvider
from src.providers.embeddings.base import EmbeddingProvider
from src.processing.segmentation import EnhancedPodcastSegmenter
from src.processing.extraction import KnowledgeExtractor
from src.processing.entity_resolution import EntityResolver
from src.processing.graph_analysis import GraphAnalyzer
from src.processing.discourse_flow import DiscourseFlowTracker
from src.processing.emergent_themes import EmergentThemeDetector
from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.utils.memory import cleanup_memory, monitor_memory
from src.utils.resources import ProgressCheckpoint
from src.utils.feed_processing import fetch_podcast_feed, download_episode_audio
from src.providers.graph.enhancements import GraphEnhancer
from src.utils.logging import get_logger, log_execution_time, log_error_with_context, log_metric
from src.tracing import (
    init_tracing, trace_method, trace_async, add_span_attributes,
    record_exception, set_span_status, create_span, get_current_span,
    trace_business_operation, instrument_all
)
from src.tracing.config import TracingConfig

logger = get_logger(__name__)


class PodcastKnowledgePipeline:
    """Master orchestrator for the podcast knowledge extraction pipeline.
    
    This class coordinates all components of the pipeline using dependency injection
    and provides the main API for seeding the knowledge graph.
    """
    
    def __init__(self, config: Optional[Union[PipelineConfig, SeedingConfig]] = None):
        """Initialize the pipeline with configuration.
        
        Args:
            config: Pipeline or seeding configuration
        """
        self.config = config or SeedingConfig()
        self.factory = ProviderFactory()
        
        # Provider instances
        self.audio_provider: Optional[AudioProvider] = None
        self.llm_provider: Optional[LLMProvider] = None
        self.graph_provider: Optional[GraphProvider] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None
        
        # Processing components
        self.segmenter: Optional[EnhancedPodcastSegmenter] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.entity_resolver: Optional[EntityResolver] = None
        self.graph_analyzer: Optional[GraphAnalyzer] = None
        self.graph_enhancer: Optional[GraphEnhancer] = None
        self.discourse_flow_tracker: Optional[DiscourseFlowTracker] = None
        self.emergent_theme_detector: Optional[EmergentThemeDetector] = None
        self.episode_flow_analyzer: Optional[EpisodeFlowAnalyzer] = None
        
        # Checkpoint manager
        self.checkpoint: Optional[ProgressCheckpoint] = None
        
        # Shutdown handling
        self._shutdown_requested = False
        self._setup_signal_handlers()
        
        # Initialize logging
        self._setup_logging()
        
        # Initialize distributed tracing
        self._setup_tracing()
    
    def _setup_logging(self):
        """Set up comprehensive logging."""
        log_level = getattr(self.config, 'log_level', 'INFO')
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format
        )
        
        # Add file handler if log file specified
        if hasattr(self.config, 'log_file') and self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            logging.getLogger().addHandler(file_handler)
    
    def _setup_signal_handlers(self):
        """Set up graceful shutdown handling."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _setup_tracing(self):
        """Initialize distributed tracing."""
        tracing_config = TracingConfig.from_env()
        
        # Initialize OpenTelemetry tracer
        init_tracing(
            service_name=tracing_config.service_name,
            jaeger_host=tracing_config.jaeger_host,
            jaeger_port=tracing_config.jaeger_port,
            config=self.config,
            enable_console=tracing_config.console_export,
        )
        
        # Enable auto-instrumentation based on config
        if tracing_config.instrument_neo4j:
            from src.tracing.instrumentation import instrument_neo4j
            instrument_neo4j()
        
        if tracing_config.instrument_redis:
            from src.tracing.instrumentation import instrument_redis
            instrument_redis()
        
        if tracing_config.instrument_requests:
            from src.tracing.instrumentation import instrument_requests
            instrument_requests()
        
        if tracing_config.instrument_langchain:
            from src.tracing.instrumentation import instrument_langchain
            instrument_langchain()
        
        if tracing_config.instrument_whisper:
            from src.tracing.instrumentation import instrument_whisper
            instrument_whisper()
        
        logger.info("Distributed tracing initialized")
    
    @trace_method(name="pipeline.initialize_components")
    def initialize_components(self, use_large_context: bool = True) -> bool:
        """Initialize all pipeline components.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing pipeline components...")
            
            # Check extraction mode and log it
            use_schemaless = getattr(self.config, 'use_schemaless_extraction', False)
            if use_schemaless:
                logger.info("🔄 Initializing in SCHEMALESS extraction mode")
                logger.info(f"  - Confidence threshold: {getattr(self.config, 'schemaless_confidence_threshold', 0.7)}")
                logger.info(f"  - Entity resolution threshold: {getattr(self.config, 'entity_resolution_threshold', 0.85)}")
                logger.info(f"  - Max properties per node: {getattr(self.config, 'max_properties_per_node', 50)}")
                logger.info(f"  - Relationship normalization: {getattr(self.config, 'relationship_normalization', True)}")
            else:
                logger.info("📊 Initializing in FIXED SCHEMA extraction mode")
            
            # Initialize providers using factory
            self.audio_provider = self.factory.create_provider(
                'audio',
                getattr(self.config, 'audio_provider', 'whisper'),
                self.config
            )
            
            self.llm_provider = self.factory.create_provider(
                'llm',
                getattr(self.config, 'llm_provider', 'gemini'),
                self.config,
                use_large_context=use_large_context
            )
            
            # Graph provider will automatically use schemaless if configured
            self.graph_provider = self.factory.create_provider(
                'graph',
                getattr(self.config, 'graph_provider', 'neo4j'),
                self.config
            )
            
            self.embedding_provider = self.factory.create_provider(
                'embeddings',
                getattr(self.config, 'embedding_provider', 'sentence_transformer'),
                self.config
            )
            
            # Initialize processing components
            segmenter_config = getattr(self.config, 'segmenter_config', {})
            self.segmenter = EnhancedPodcastSegmenter(
                self.audio_provider,
                config=segmenter_config
            )
            
            self.knowledge_extractor = KnowledgeExtractor(
                self.llm_provider,
                self.embedding_provider
            )
            
            self.entity_resolver = EntityResolver(
                self.graph_provider,
                self.embedding_provider
            )
            
            self.graph_analyzer = GraphAnalyzer(self.graph_provider)
            self.graph_enhancer = GraphEnhancer(self.graph_provider)
            self.discourse_flow_tracker = DiscourseFlowTracker(self.embedding_provider)
            self.emergent_theme_detector = EmergentThemeDetector(
                self.embedding_provider,
                self.llm_provider
            )
            self.episode_flow_analyzer = EpisodeFlowAnalyzer(self.embedding_provider)
            
            # Initialize checkpoint manager
            checkpoint_dir = getattr(self.config, 'checkpoint_dir', 'checkpoints')
            extraction_mode = 'schemaless' if use_schemaless else 'fixed'
            self.checkpoint = ProgressCheckpoint(
                checkpoint_dir,
                extraction_mode=extraction_mode,
                config=self.config.__dict__ if hasattr(self.config, '__dict__') else {}
            )
            
            # Verify all components are healthy
            if not self._verify_components_health():
                raise PipelineError("Component health check failed")
            
            logger.info("✓ All pipeline components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize pipeline components: {e}")
            return False
    
    @trace_method(name="pipeline.verify_components_health")
    def _verify_components_health(self) -> bool:
        """Verify all components are healthy."""
        components = [
            ('Audio Provider', self.audio_provider),
            ('LLM Provider', self.llm_provider),
            ('Graph Provider', self.graph_provider),
            ('Embedding Provider', self.embedding_provider)
        ]
        
        all_healthy = True
        for name, component in components:
            if component is None:
                logger.error(f"{name} not initialized")
                all_healthy = False
                continue
                
            try:
                health = component.health_check()
                if health.get('status') != 'healthy':
                    logger.error(f"{name} unhealthy: {health}")
                    all_healthy = False
                else:
                    logger.info(f"{name} healthy")
            except Exception as e:
                logger.error(f"{name} health check failed: {e}")
                all_healthy = False
        
        return all_healthy
    
    def cleanup(self):
        """Clean up resources and close connections."""
        logger.info("Cleaning up pipeline resources...")
        
        # Close providers
        providers = [
            self.audio_provider,
            self.llm_provider,
            self.graph_provider,
            self.embedding_provider
        ]
        
        for provider in providers:
            if provider:
                try:
                    provider.close()
                except Exception as e:
                    logger.warning(f"Error closing provider: {e}")
        
        # Clean up memory
        cleanup_memory()
        logger.info("Pipeline cleanup completed")
    
    @trace_method(name="pipeline.seed_podcast")
    def seed_podcast(self, 
                    podcast_config: Dict[str, Any],
                    max_episodes: int = 1,
                    use_large_context: bool = True) -> Dict[str, Any]:
        """Seed knowledge graph with a single podcast.
        
        Args:
            podcast_config: Podcast configuration with RSS URL
            max_episodes: Maximum episodes to process
            use_large_context: Whether to use large context models
            
        Returns:
            Processing summary
        """
        return self.seed_podcasts(
            [podcast_config],
            max_episodes_each=max_episodes,
            use_large_context=use_large_context
        )
    
    @trace_method(name="pipeline.seed_podcasts")
    def seed_podcasts(self,
                     podcast_configs: Union[Dict[str, Any], List[Dict[str, Any]]],
                     max_episodes_each: int = 10,
                     use_large_context: bool = True) -> Dict[str, Any]:
        """Seed knowledge graph with multiple podcasts.
        
        Args:
            podcast_configs: List of podcast configurations or single config
            max_episodes_each: Episodes to process per podcast
            use_large_context: Whether to use large context models
            
        Returns:
            Summary dict with processing statistics
        """
        # Ensure podcast_configs is a list
        if isinstance(podcast_configs, dict):
            podcast_configs = [podcast_configs]
        
        # Initialize components if not already done
        if not self.audio_provider:
            if not self.initialize_components(use_large_context):
                raise PipelineError("Failed to initialize pipeline components")
        
        summary = {
            'start_time': datetime.now().isoformat(),
            'podcasts_processed': 0,
            'episodes_processed': 0,
            'episodes_failed': 0,
            'total_segments': 0,
            'total_insights': 0,
            'total_entities': 0,
            'total_relationships': 0,
            'discovered_types': set(),
            'extraction_mode': 'schemaless' if getattr(self.config, 'use_schemaless_extraction', False) else 'fixed',
            'errors': []
        }
        
        try:
            for podcast_config in podcast_configs:
                if self._shutdown_requested:
                    logger.info("Shutdown requested, stopping processing")
                    break
                
                try:
                    result = self._process_podcast(
                        podcast_config,
                        max_episodes_each,
                        use_large_context
                    )
                    
                    # Update summary
                    summary['podcasts_processed'] += 1
                    summary['episodes_processed'] += result['episodes_processed']
                    summary['episodes_failed'] += result['episodes_failed']
                    summary['total_segments'] += result['total_segments']
                    summary['total_insights'] += result['total_insights']
                    summary['total_entities'] += result['total_entities']
                    
                    # Add schemaless-specific metrics
                    if result.get('extraction_mode') == 'schemaless':
                        summary['total_relationships'] += result.get('total_relationships', 0)
                        if 'discovered_types' in result and isinstance(result['discovered_types'], list):
                            summary['discovered_types'].update(result['discovered_types'])
                    
                except Exception as e:
                    logger.error(f"Failed to process podcast: {e}")
                    summary['errors'].append({
                        'podcast': podcast_config.get('id', 'unknown'),
                        'error': str(e)
                    })
            
            summary['end_time'] = datetime.now().isoformat()
            summary['success'] = len(summary['errors']) == 0
            
            # Convert discovered types set to sorted list for JSON serialization
            if isinstance(summary['discovered_types'], set):
                summary['discovered_types'] = sorted(list(summary['discovered_types']))
            
            # Log final schema discovery summary if in schemaless mode
            if summary['extraction_mode'] == 'schemaless' and summary['discovered_types']:
                logger.info(f"Overall Schema Discovery - Found {len(summary['discovered_types'])} unique entity types across all podcasts")
            
            return summary
            
        finally:
            # Always cleanup
            self.cleanup()
    
    def _process_podcast(self,
                        podcast_config: Dict[str, Any],
                        max_episodes: int,
                        use_large_context: bool) -> Dict[str, Any]:
        """Process a single podcast.
        
        Args:
            podcast_config: Podcast configuration
            max_episodes: Maximum episodes to process
            use_large_context: Whether to use large context
            
        Returns:
            Processing results
        """
        logger.info(f"Processing podcast: {podcast_config.get('name', podcast_config['id'])}")
        
        # Fetch podcast feed
        podcast_info = fetch_podcast_feed(podcast_config, max_episodes)
        
        result = {
            'episodes_processed': 0,
            'episodes_failed': 0,
            'total_segments': 0,
            'total_insights': 0,
            'total_entities': 0,
            'total_relationships': 0,
            'discovered_types': set(),
            'extraction_mode': 'schemaless' if getattr(self.config, 'use_schemaless_extraction', False) else 'fixed'
        }
        
        # Process each episode
        for episode in podcast_info['episodes']:
            if self._shutdown_requested:
                break
            
            try:
                episode_result = self._process_episode(
                    podcast_config,
                    episode,
                    use_large_context
                )
                
                result['episodes_processed'] += 1
                result['total_segments'] += episode_result.get('segments', 0)
                result['total_insights'] += episode_result.get('insights', 0)
                result['total_entities'] += episode_result.get('entities', 0)
                
                # Add schemaless-specific metrics
                if episode_result.get('mode') == 'schemaless':
                    result['total_relationships'] += episode_result.get('relationships', 0)
                    if 'discovered_types' in episode_result:
                        result['discovered_types'].update(episode_result['discovered_types'])
                
            except Exception as e:
                logger.error(f"Failed to process episode '{episode['title']}': {e}")
                result['episodes_failed'] += 1
        
        # Convert discovered types set to sorted list for JSON serialization
        if isinstance(result['discovered_types'], set):
            result['discovered_types'] = sorted(list(result['discovered_types']))
        
        # Log schema discovery summary if in schemaless mode
        if result['extraction_mode'] == 'schemaless' and result['discovered_types']:
            logger.info(f"Schema Discovery Summary - Found {len(result['discovered_types'])} unique entity types: {result['discovered_types']}")
        
        return result
    
    @trace_method(name="pipeline.process_episode")
    def _process_episode(self,
                        podcast_config: Dict[str, Any],
                        episode: Dict[str, Any],
                        use_large_context: bool) -> Dict[str, Any]:
        """Process a single episode.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            use_large_context: Whether to use large context
            
        Returns:
            Episode processing results
        """
        episode_id = episode['id']
        logger.info(f"Processing episode: {episode['title']} (ID: {episode_id})")
        
        # Check if already completed
        completed_episodes = self.checkpoint.get_completed_episodes()
        if episode_id in completed_episodes:
            logger.info(f"Episode {episode_id} already completed, skipping")
            return {'segments': 0, 'insights': 0, 'entities': 0}
        
        # Download audio
        audio_path = download_episode_audio(
            episode,
            podcast_config['id'],
            output_dir=getattr(self.config, 'audio_dir', 'audio_files')
        )
        
        if not audio_path:
            raise PipelineError(f"Failed to download audio for episode {episode_id}")
        
        try:
            # Add episode context to current span
            add_span_attributes({
                "episode.id": episode_id,
                "episode.title": episode['title'],
                "podcast.id": podcast_config['id'],
                "podcast.name": podcast_config.get('name', ''),
            })
            
            # Process audio through segmentation
            with create_span("segmentation", attributes={"audio.path": audio_path}):
                logger.info("Segmenting audio...")
                segments = self.segmenter.process_audio(audio_path)
                add_span_attributes({"segments.count": len(segments)})
            
            # Save segments checkpoint
            self.checkpoint.save_episode_progress(episode_id, 'segments', segments)
            
            # Check if using schemaless extraction
            use_schemaless = getattr(self.config, 'use_schemaless_extraction', False)
            
            if use_schemaless:
                # Schemaless extraction path
                logger.info("Using SCHEMALESS extraction pipeline")
                with create_span("schemaless_extraction", attributes={
                    "segments.count": len(segments),
                    "extraction.mode": "schemaless"
                }):
                    # Check if graph provider supports schemaless
                    if hasattr(self.graph_provider, 'process_segment_schemaless'):
                        # Implement graceful degradation flags
                        degradation_flags = {
                            'disable_entity_resolution': False,
                            'disable_metadata_enrichment': False,
                            'disable_quote_extraction': False,
                            'fallback_to_simple_extraction': False
                        }
                        # Process through schemaless pipeline
                        extraction_results = []
                        discovered_types = set()
                        
                        from src.core.models import Podcast, Episode, Segment
                        # Convert to model objects
                        podcast_obj = Podcast(
                            id=podcast_config['id'],
                            title=podcast_config.get('name', podcast_config['id']),
                            description=podcast_config.get('description', ''),
                            rss_url=podcast_config.get('rss_url', '')
                        )
                        episode_obj = Episode(
                            id=episode['id'],
                            title=episode['title'],
                            description=episode.get('description', ''),
                            published_date=episode.get('published_date', ''),
                            audio_url=episode.get('audio_url', '')
                        )
                        
                        for i, segment_data in enumerate(segments):
                            segment_obj = Segment(
                                id=f"{episode_id}_segment_{i}",
                                text=segment_data.get('text', ''),
                                start_time=segment_data.get('start_time', 0),
                                end_time=segment_data.get('end_time', 0),
                                speaker=segment_data.get('speaker', 'Unknown')
                            )
                            
                            try:
                                result = self.graph_provider.process_segment_schemaless(
                                    segment_obj, episode_obj, podcast_obj
                                )
                                extraction_results.append(result)
                                
                                # Track discovered entity types
                                for entity in result.get('entities_extracted', []):
                                    if isinstance(entity, dict) and 'type' in entity:
                                        discovered_types.add(entity['type'])
                                        
                            except AttributeError as e:
                                logger.error(f"SimpleKGPipeline not properly initialized: {e}")
                                raise PipelineError(f"Schemaless extraction failed - SimpleKGPipeline error: {e}")
                            except ImportError as e:
                                logger.error(f"Missing dependency for schemaless extraction: {e}")
                                raise PipelineError(f"Schemaless extraction failed - Missing dependency: {e}")
                            except ValueError as e:
                                logger.error(f"Property validation error in segment {i}: {e}")
                                # Continue with next segment instead of failing
                                extraction_results.append({
                                    'segment_id': segment_obj.id,
                                    'status': 'error',
                                    'error': str(e),
                                    'entities_extracted': 0,
                                    'relationships_extracted': 0
                                })
                            except Exception as e:
                                logger.error(f"Unexpected error in schemaless extraction for segment {i}: {e}")
                                # Try to continue with partial results
                                extraction_results.append({
                                    'segment_id': segment_obj.id,
                                    'status': 'error',
                                    'error': str(e),
                                    'entities_extracted': 0,
                                    'relationships_extracted': 0
                                })
                        
                        # Log schema discovery
                        if discovered_types:
                            logger.info(f"Discovered entity types: {sorted(discovered_types)}")
                            add_span_attributes({
                                "schema.discovered_types": list(discovered_types),
                                "schema.types_count": len(discovered_types)
                            })
                        
                        # Aggregate results for checkpoint
                        total_entities = sum(r.get('entities_extracted', 0) for r in extraction_results)
                        total_relationships = sum(r.get('relationships_extracted', 0) for r in extraction_results)
                        
                        # Count errors
                        error_count = sum(1 for r in extraction_results if r.get('status') == 'error')
                        if error_count > 0:
                            logger.warning(f"Encountered {error_count} errors during schemaless extraction")
                            
                            # Log degradation status if any features were disabled
                            if any(degradation_flags.values()):
                                logger.info(f"Graceful degradation applied: {degradation_flags}")
                        
                        extraction_result = {
                            'mode': 'schemaless',
                            'segments_processed': len(extraction_results),
                            'entities': total_entities,
                            'relationships': total_relationships,
                            'discovered_types': list(discovered_types)
                        }
                        
                        add_span_attributes({
                            "entities.total": total_entities,
                            "relationships.total": total_relationships
                        })
                        
                        # Save extraction checkpoint for schemaless mode
                        self.checkpoint.save_episode_progress(episode_id, 'extraction', extraction_result)
                        
                        # Track schema evolution
                        if discovered_types:
                            self.checkpoint.save_schema_evolution(episode_id, list(discovered_types))
                    else:
                        logger.warning("Graph provider does not support schemaless extraction, falling back to fixed schema")
                        use_schemaless = False
            
            if not use_schemaless:
                # Fixed schema extraction path (original code)
                logger.info("Using FIXED SCHEMA extraction pipeline")
                with create_span("knowledge_extraction", attributes={
                    "segments.count": len(segments),
                    "extraction.mode": "fixed"
                }):
                    logger.info("Extracting knowledge...")
                    extraction_result = self.knowledge_extractor.extract_from_segments(
                        segments,
                        podcast_name=podcast_config.get('name'),
                        episode_title=episode['title']
                    )
                    add_span_attributes({
                        "insights.count": len(extraction_result.get('insights', [])),
                        "entities.count": len(extraction_result.get('entities', [])),
                    })
                
                # Save extraction checkpoint
                self.checkpoint.save_episode_progress(episode_id, 'extraction', extraction_result)
                
                # Resolve entities
                with create_span("entity_resolution", attributes={"entities.input_count": len(extraction_result.get('entities', []))}):
                    logger.info("Resolving entities...")
                    resolved_entities = self.entity_resolver.resolve_entities(
                        extraction_result.get('entities', [])
                    )
                    add_span_attributes({"entities.resolved_count": len(resolved_entities)})
                
                # Analyze discourse flow
                with create_span("discourse_flow_analysis", attributes={"entities.count": len(resolved_entities)}):
                    logger.info("Analyzing discourse flow...")
                    
                    # Convert segment dictionaries to Segment objects for discourse flow
                    from src.core.models import Segment
                    segment_objects = []
                    for i, segment_data in enumerate(segments):
                        segment_obj = Segment(
                            id=f"{episode_id}_segment_{i}",
                            text=segment_data.get('text', ''),
                            start_time=segment_data.get('start', 0),
                            end_time=segment_data.get('end', 0),
                            speaker=segment_data.get('speaker', 'Unknown'),
                            segment_index=i
                        )
                        segment_objects.append(segment_obj)
                    
                    flow_results = self.discourse_flow_tracker.analyze_episode_flow(
                        segment_objects,
                        resolved_entities,
                        extraction_result.get('insights', [])
                    )
                    add_span_attributes({
                        "flow.patterns_detected": len(flow_results.get('discourse_patterns', [])),
                        "flow.narrative_arcs": len(flow_results.get('narrative_arcs', [])),
                        "flow.concept_lifecycles": len(flow_results.get('concept_lifecycles', {}))
                    })
                    
                    # Store flow results in extraction_result for graph storage
                    extraction_result['discourse_flow'] = flow_results
                
                # Detect emergent themes
                with create_span("emergent_theme_detection", attributes={"entities.count": len(resolved_entities)}):
                    logger.info("Detecting emergent themes...")
                    
                    # Build co-occurrence data from segments
                    co_occurrences = self._build_co_occurrence_data(segment_objects, resolved_entities)
                    
                    # Extract explicit topics from the extraction results
                    explicit_topics = extraction_result.get('topics', [])
                    explicit_topic_names = [topic.get('name', '') for topic in explicit_topics if isinstance(topic, dict)]
                    
                    # Detect emergent themes
                    theme_results = self.emergent_theme_detector.detect_themes(
                        entities=resolved_entities,
                        insights=extraction_result.get('insights', []),
                        segments=segment_objects,
                        co_occurrences=co_occurrences,
                        explicit_topics=explicit_topic_names
                    )
                    
                    add_span_attributes({
                        "themes.detected": len(theme_results.get('themes', [])),
                        "themes.meta": len(theme_results.get('hierarchy', {}).get('meta_themes', [])),
                        "themes.primary": len(theme_results.get('hierarchy', {}).get('primary_themes', [])),
                        "themes.implicit_messages": len(theme_results.get('implicit_messages', []))
                    })
                    
                    # Store theme results in extraction_result for graph storage
                    extraction_result['emergent_themes'] = theme_results
                
                # Analyze episode flow
                with create_span("episode_flow_analysis", attributes={"segments.count": len(segment_objects)}):
                    logger.info("Analyzing episode flow...")
                    
                    # Build concept timeline for flow analysis
                    concept_timeline = {}
                    entity_mentions = self.episode_flow_analyzer._find_entity_mentions(
                        segment_objects, 
                        resolved_entities
                    )
                    for entity_id, mentions in entity_mentions.items():
                        concept_timeline[entity_id] = mentions
                    
                    # Run comprehensive flow analysis
                    episode_flow = {
                        "transitions": self.episode_flow_analyzer.classify_segment_transitions(segment_objects),
                        "concept_introductions": self.episode_flow_analyzer.track_concept_introductions(
                            segment_objects, resolved_entities
                        ),
                        "momentum": self.episode_flow_analyzer.analyze_conversation_momentum(segment_objects),
                        "topic_depths": self.episode_flow_analyzer.track_topic_depth(
                            segment_objects, resolved_entities
                        ),
                        "circular_references": self.episode_flow_analyzer.detect_circular_references(
                            concept_timeline
                        ),
                        "resolutions": self.episode_flow_analyzer.analyze_concept_resolution(
                            concept_timeline, segment_objects[-5:]  # Last 5 segments as final
                        ),
                        "speaker_contributions": self.episode_flow_analyzer.analyze_speaker_contribution_flow(
                            segment_objects
                        )
                    }
                    
                    # Generate flow summary
                    flow_summary = self.episode_flow_analyzer.generate_episode_flow_summary(episode_flow)
                    episode_flow["summary"] = flow_summary
                    
                    # Add flow data to entities
                    for entity in resolved_entities:
                        if entity.id in episode_flow["concept_introductions"]:
                            intro_data = episode_flow["concept_introductions"][entity.id]
                            development = self.episode_flow_analyzer.map_concept_development(
                                entity, segment_objects
                            )
                            
                            # Calculate flow position metrics
                            total_segments = len(segment_objects)
                            intro_position = intro_data["introduction_segment"] / total_segments if total_segments > 0 else 0
                            
                            # Find peak discussion segment
                            peak_segment = 0
                            if development.get("phases"):
                                elaboration_phases = [p for p in development["phases"] if p["phase"] == "elaboration"]
                                if elaboration_phases:
                                    peak_segment = elaboration_phases[len(elaboration_phases)//2]["segment_index"]
                            peak_position = peak_segment / total_segments if total_segments > 0 else intro_position
                            
                            # Determine resolution status
                            resolution_status = "unknown"
                            if entity.id in episode_flow["resolutions"]:
                                resolution_status = episode_flow["resolutions"][entity.id]["resolution_type"]
                            
                            # Add flow data to entity
                            entity.flow_data = {
                                "introduction_point": intro_position,
                                "development_duration": len(development.get("phases", [])) * 10.0,  # Approximate seconds
                                "peak_discussion": peak_position,
                                "resolution_status": resolution_status
                            }
                    
                    # Store episode flow data
                    extraction_result['episode_flow'] = {
                        "pattern": flow_summary.get("flow_pattern", "unknown"),
                        "key_transitions": flow_summary.get("key_transitions", []),
                        "flow_quality": flow_summary.get("narrative_coherence", 0.5)
                    }
                    
                    add_span_attributes({
                        "flow.pattern": flow_summary.get("flow_pattern"),
                        "flow.coherence": flow_summary.get("narrative_coherence"),
                        "flow.transitions": len(episode_flow.get("transitions", [])),
                        "flow.circular_refs": len(episode_flow.get("circular_references", []))
                    })
                
                # Save to graph
                with create_span("graph_storage"):
                    logger.info("Saving to knowledge graph...")
                    self._save_to_graph(
                        podcast_config,
                        episode,
                        segments,
                        extraction_result,
                        resolved_entities
                    )
            
            # Mark episode as complete
            self.checkpoint.save_episode_progress(episode_id, 'complete', True)
            
            # Clean up memory
            cleanup_memory()
            
            # Build result based on extraction mode
            if extraction_result.get('mode') == 'schemaless':
                result = {
                    'segments': len(segments),
                    'insights': 0,  # Schemaless mode doesn't track insights separately
                    'entities': extraction_result.get('entities', 0),
                    'relationships': extraction_result.get('relationships', 0),
                    'discovered_types': extraction_result.get('discovered_types', []),
                    'mode': 'schemaless'
                }
            else:
                result = {
                    'segments': len(segments),
                    'insights': len(extraction_result.get('insights', [])),
                    'entities': len(resolved_entities) if 'resolved_entities' in locals() else 0,
                    'mode': 'fixed'
                }
            
            # Add result metrics to span
            add_span_attributes({
                "result.segments": result['segments'],
                "result.insights": result['insights'],
                "result.entities": result['entities'],
                "result.mode": result['mode']
            })
            
            return result
            
        finally:
            # Clean up audio file if configured
            if getattr(self.config, 'delete_audio_after_processing', True):
                try:
                    os.remove(audio_path)
                except:
                    pass
    
    @trace_method(name="pipeline.save_to_graph")
    def _save_to_graph(self,
                      podcast_config: Dict[str, Any],
                      episode: Dict[str, Any],
                      segments: List[Dict[str, Any]],
                      extraction_result: Dict[str, Any],
                      resolved_entities: List[Dict[str, Any]]):
        """Save all data to the knowledge graph.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Extraction results
            resolved_entities: Resolved entities
        """
        # Create podcast node
        self.graph_provider.create_node(
            'Podcast',
            {
                'id': podcast_config['id'],
                'name': podcast_config.get('name', podcast_config['id']),
                'description': podcast_config.get('description', ''),
                'rss_url': podcast_config.get('rss_url', '')
            }
        )
        
        # Create episode node with flow data
        episode_data = {
            'id': episode['id'],
            'title': episode['title'],
            'description': episode.get('description', ''),
            'published_date': episode.get('published_date', ''),
            'duration': episode.get('duration', ''),
            'audio_url': episode.get('audio_url', '')
        }
        
        # Add episode flow data if available
        if 'episode_flow' in extraction_result:
            episode_flow_data = extraction_result['episode_flow']
            episode_data['discourse_flow_pattern'] = episode_flow_data.get('pattern', 'unknown')
            episode_data['flow_quality'] = episode_flow_data.get('flow_quality', 0.5)
            episode_data['key_transitions_count'] = len(episode_flow_data.get('key_transitions', []))
        
        self.graph_provider.create_node('Episode', episode_data)
        
        # Create relationship
        self.graph_provider.create_relationship(
            ('Podcast', {'id': podcast_config['id']}),
            'HAS_EPISODE',
            ('Episode', {'id': episode['id']}),
            {}
        )
        
        # Save segments
        for i, segment in enumerate(segments):
            segment_data = {
                'id': f"{episode['id']}_segment_{i}",
                'segment_index': i,
                'text': segment['text'],
                'start_time': segment['start'],
                'end_time': segment['end'],
                'speaker': segment.get('speaker', 'Unknown'),
                'sentiment': segment.get('sentiment', 'neutral')
            }
            
            self.graph_provider.create_node('Segment', segment_data)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode['id']}),
                'HAS_SEGMENT',
                ('Segment', {'id': segment_data['id']}),
                {'sequence': i}
            )
        
        # Save insights
        for insight in extraction_result.get('insights', []):
            self.graph_provider.create_node('Insight', insight)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode['id']}),
                'HAS_INSIGHT',
                ('Insight', {'id': insight['id']}),
                {}
            )
        
        # Save entities with flow data
        for entity in resolved_entities:
            # Convert entity to dictionary to ensure flow_data is included
            entity_data = {
                'id': entity.id,
                'name': entity.name,
                'type': entity.type,
                'description': entity.description,
                'confidence': getattr(entity, 'confidence', 1.0),
                'importance_score': getattr(entity, 'importance_score', 0.5),
                'importance_factors': getattr(entity, 'importance_factors', {}),
                'discourse_roles': getattr(entity, 'discourse_roles', {})
            }
            
            # Add flow data if present
            if hasattr(entity, 'flow_data') and entity.flow_data:
                entity_data.update({
                    'flow_introduction_point': entity.flow_data.get('introduction_point', 0),
                    'flow_development_duration': entity.flow_data.get('development_duration', 0),
                    'flow_peak_discussion': entity.flow_data.get('peak_discussion', 0),
                    'flow_resolution_status': entity.flow_data.get('resolution_status', 'unknown')
                })
            
            # Add embedding if present
            if hasattr(entity, 'embedding') and entity.embedding:
                entity_data['embedding'] = entity.embedding
            
            # Create or update entity
            self.graph_provider.create_node('Entity', entity_data)
            
            # Create relationship to episode
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode['id']}),
                'MENTIONS',
                ('Entity', {'id': entity.id}),
                {'confidence': entity_data['confidence']}
            )
        
        # Save quotes
        for quote in extraction_result.get('quotes', []):
            quote['id'] = f"{episode['id']}_quote_{hash(quote['text'])}"
            self.graph_provider.create_node('Quote', quote)
            
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode['id']}),
                'CONTAINS_QUOTE',
                ('Quote', {'id': quote['id']}),
                {}
            )
        
        # Save emergent themes
        emergent_themes_data = extraction_result.get('emergent_themes', {})
        if emergent_themes_data and emergent_themes_data.get('themes'):
            logger.info(f"Saving {len(emergent_themes_data['themes'])} emergent themes...")
            
            for theme in emergent_themes_data['themes']:
                # Create theme node
                theme_data = {
                    'id': f"{episode['id']}_theme_{theme.get('theme_id', hash(theme['semantic_field']))}",
                    'semantic_field': theme.get('semantic_field', 'Unknown'),
                    'emergence_score': theme.get('emergence_score', 0.5),
                    'confidence': theme.get('confidence', 0.5),
                    'validation_score': theme.get('validation_score', 0.5),
                    'theme_source': theme.get('theme_source', 'unknown'),
                    'evolution_pattern': theme.get('evolution_pattern', 'unknown')
                }
                
                self.graph_provider.create_node('EmergentTheme', theme_data)
                
                # Create relationship to episode
                self.graph_provider.create_relationship(
                    ('Episode', {'id': episode['id']}),
                    'HAS_EMERGENT_THEME',
                    ('EmergentTheme', {'id': theme_data['id']}),
                    {'strength': theme.get('confidence', 0.5)}
                )
                
                # Link theme to its key concepts
                for concept_name in theme.get('key_concepts', [])[:5]:  # Top 5 concepts
                    # Find matching entity
                    matching_entity = next(
                        (e for e in resolved_entities if e.name.lower() == concept_name.lower()),
                        None
                    )
                    if matching_entity:
                        self.graph_provider.create_relationship(
                            ('EmergentTheme', {'id': theme_data['id']}),
                            'COMPOSED_OF',
                            ('Entity', {'id': matching_entity.id}),
                            {'role': 'key_concept'}
                        )
        
        # Enhance graph if configured
        if getattr(self.config, 'enhance_graph', True):
            logger.info("Enhancing knowledge graph...")
            self.graph_enhancer.enhance_episode(episode['id'])
    
    def resume_from_checkpoints(self) -> Dict[str, Any]:
        """Resume processing from checkpoints after interruption.
        
        Returns:
            Summary of resumed processing
        """
        logger.info("Resuming from checkpoints...")
        
        # Find incomplete episodes
        incomplete_episodes = []
        
        # This would need to be implemented based on checkpoint analysis
        # For now, return empty summary
        return {
            'resumed_episodes': 0,
            'message': 'Checkpoint recovery not fully implemented'
        }
    
    def _build_co_occurrence_data(self, segments: List[Segment], entities: List[Entity]) -> List[Dict]:
        """
        Build co-occurrence data for entities appearing in the same segments.
        
        Args:
            segments: List of segment objects
            entities: List of entity objects
            
        Returns:
            List of co-occurrence relationships
        """
        from collections import defaultdict
        
        # Map entities to segments they appear in
        entity_segments = defaultdict(set)
        
        for entity in entities:
            entity_name_lower = entity.name.lower()
            
            for i, segment in enumerate(segments):
                if entity_name_lower in segment.text.lower():
                    entity_segments[entity.id].add(i)
        
        # Build co-occurrence relationships
        co_occurrences = []
        entities_list = list(entities)
        
        for i, entity1 in enumerate(entities_list):
            for j, entity2 in enumerate(entities_list[i+1:], start=i+1):
                # Find shared segments
                shared_segments = entity_segments[entity1.id] & entity_segments[entity2.id]
                
                if shared_segments:
                    co_occurrences.append({
                        "entity1_id": entity1.id,
                        "entity2_id": entity2.id,
                        "weight": len(shared_segments),
                        "shared_segments": list(shared_segments)
                    })
        
        return co_occurrences