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
            
            # Initialize checkpoint manager
            checkpoint_dir = getattr(self.config, 'checkpoint_dir', 'checkpoints')
            self.checkpoint = ProgressCheckpoint(checkpoint_dir)
            
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
                    
                except Exception as e:
                    logger.error(f"Failed to process podcast: {e}")
                    summary['errors'].append({
                        'podcast': podcast_config.get('id', 'unknown'),
                        'error': str(e)
                    })
            
            summary['end_time'] = datetime.now().isoformat()
            summary['success'] = len(summary['errors']) == 0
            
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
            'total_entities': 0
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
                
            except Exception as e:
                logger.error(f"Failed to process episode '{episode['title']}': {e}")
                result['episodes_failed'] += 1
        
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
            
            # Extract knowledge
            with create_span("knowledge_extraction", attributes={"segments.count": len(segments)}):
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
            with create_span("entity_resolution", attributes={"entities.input_count": len(extraction_result['entities'])}):
                logger.info("Resolving entities...")
                resolved_entities = self.entity_resolver.resolve_entities(
                    extraction_result['entities']
                )
                add_span_attributes({"entities.resolved_count": len(resolved_entities)})
            
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
            
            result = {
                'segments': len(segments),
                'insights': len(extraction_result.get('insights', [])),
                'entities': len(resolved_entities)
            }
            
            # Add result metrics to span
            add_span_attributes({
                "result.segments": result['segments'],
                "result.insights": result['insights'],
                "result.entities": result['entities'],
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
        
        # Create episode node
        self.graph_provider.create_node(
            'Episode',
            {
                'id': episode['id'],
                'title': episode['title'],
                'description': episode.get('description', ''),
                'published_date': episode.get('published_date', ''),
                'duration': episode.get('duration', ''),
                'audio_url': episode.get('audio_url', '')
            }
        )
        
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
        
        # Save entities
        for entity in resolved_entities:
            # Create or update entity
            self.graph_provider.create_node('Entity', entity)
            
            # Create relationship to episode
            self.graph_provider.create_relationship(
                ('Episode', {'id': episode['id']}),
                'MENTIONS',
                ('Entity', {'id': entity['id']}),
                {'confidence': entity.get('confidence', 1.0)}
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