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
from src.providers.graph.enhancements import GraphEnhancements
from src.utils.logging import get_logger, log_execution_time, log_error_with_context, log_metric
from src.tracing import (
    init_tracing, trace_method, trace_async, add_span_attributes,
    record_exception, set_span_status, create_span, get_current_span,
    trace_business_operation, instrument_all
)
from src.tracing.config import TracingConfig

# Import new components
from src.seeding.components import (
    SignalManager,
    ProviderCoordinator,
    CheckpointManager,
    PipelineExecutor,
    StorageCoordinator
)

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
        
        # Initialize components
        self.signal_manager = SignalManager()
        self.provider_coordinator = ProviderCoordinator(self.factory, self.config)
        self.checkpoint_manager = CheckpointManager(self.config)
        
        # The pipeline executor and storage coordinator will be initialized after providers
        self.pipeline_executor = None
        self.storage_coordinator = None
        
        # Provider instances - maintain references for backward compatibility
        self.llm_provider: Optional[LLMProvider] = None
        self.graph_provider: Optional[GraphProvider] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None
        
        # Processing components - maintain references for backward compatibility
        self.segmenter: Optional[EnhancedPodcastSegmenter] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.entity_resolver: Optional[EntityResolver] = None
        self.graph_analyzer: Optional[GraphAnalyzer] = None
        self.graph_enhancer: Optional[GraphEnhancements] = None
        self.discourse_flow_tracker: Optional[DiscourseFlowTracker] = None
        self.emergent_theme_detector: Optional[EmergentThemeDetector] = None
        self.episode_flow_analyzer: Optional[EpisodeFlowAnalyzer] = None
        
        # Checkpoint manager - maintain reference for backward compatibility
        self.checkpoint: Optional[ProgressCheckpoint] = None
        
        # Shutdown handling - now managed by signal_manager
        self._shutdown_requested = False
        self.signal_manager.setup(cleanup_callback=self.cleanup)
        
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
            # Delegate to provider coordinator
            success = self.provider_coordinator.initialize_providers(use_large_context)
            if not success:
                return False
            
            # Set up backward compatibility references
            self.llm_provider = self.provider_coordinator.llm_provider
            self.graph_provider = self.provider_coordinator.graph_provider
            self.embedding_provider = self.provider_coordinator.embedding_provider
            
            self.segmenter = self.provider_coordinator.segmenter
            self.knowledge_extractor = self.provider_coordinator.knowledge_extractor
            self.entity_resolver = self.provider_coordinator.entity_resolver
            self.graph_analyzer = self.provider_coordinator.graph_analyzer
            self.graph_enhancer = self.provider_coordinator.graph_enhancer
            self.discourse_flow_tracker = self.provider_coordinator.discourse_flow_tracker
            self.emergent_theme_detector = self.provider_coordinator.emergent_theme_detector
            self.episode_flow_analyzer = self.provider_coordinator.episode_flow_analyzer
            
            # Set up checkpoint reference for backward compatibility
            self.checkpoint = self.checkpoint_manager.checkpoint
            
            # Initialize storage coordinator first
            self.storage_coordinator = StorageCoordinator(
                self.graph_provider,
                self.graph_enhancer,
                self.config
            )
            
            # Initialize pipeline executor with storage coordinator
            self.pipeline_executor = PipelineExecutor(
                self.config, 
                self.provider_coordinator,
                self.checkpoint_manager,
                self.storage_coordinator
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
        # Delegate to provider coordinator
        return self.provider_coordinator.check_health()
    
    def cleanup(self):
        """Clean up resources and close connections."""
        logger.info("Cleaning up pipeline resources...")
        
        # Delegate to provider coordinator
        self.provider_coordinator.cleanup()
        
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
        if not self.llm_provider:
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
        # Delegate to pipeline executor
        return self.pipeline_executor.process_episode(
            podcast_config,
            episode,
            use_large_context
        )
    
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