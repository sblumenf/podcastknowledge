"""Provider coordination component for managing all pipeline providers."""

import logging
from typing import Dict, Any, Optional

from src.factories.provider_factory import ProviderFactory
from src.providers.audio.base import AudioProvider
from src.providers.llm.base import LLMProvider
from src.providers.graph.base import GraphProvider
from src.providers.embeddings.base import EmbeddingProvider
from src.processing.segmentation import EnhancedPodcastSegmenter
from src.processing.extraction import KnowledgeExtractor
from src.processing.entity_resolution import EntityResolver
from src.processing.graph_analysis import GraphAnalyzer
from src.providers.graph.enhancements import GraphEnhancer
from src.processing.discourse_flow import DiscourseFlowTracker
from src.processing.emergent_themes import EmergentThemeDetector
from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.core.config import PipelineConfig
from src.tracing import trace_method, add_span_attributes

logger = logging.getLogger(__name__)


class ProviderCoordinator:
    """Coordinates initialization and management of all pipeline providers."""
    
    def __init__(self, factory: ProviderFactory, config: PipelineConfig):
        """Initialize the provider coordinator.
        
        Args:
            factory: Provider factory for creating providers
            config: Pipeline configuration
        """
        self.factory = factory
        self.config = config
        
        # Providers
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
    
    @trace_method(name="provider_coordinator.initialize_providers")
    def initialize_providers(self, use_large_context: bool = True) -> bool:
        """Initialize all providers and processing components.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing pipeline providers...")
            
            # Check extraction mode and log it
            use_schemaless = getattr(self.config, 'use_schemaless_extraction', False)
            if use_schemaless:
                logger.info("🔄 Initializing providers in SCHEMALESS extraction mode")
                logger.info(f"  - Confidence threshold: {getattr(self.config, 'schemaless_confidence_threshold', 0.7)}")
                logger.info(f"  - Entity resolution threshold: {getattr(self.config, 'entity_resolution_threshold', 0.85)}")
                logger.info(f"  - Max properties per node: {getattr(self.config, 'max_properties_per_node', 50)}")
                logger.info(f"  - Relationship normalization: {getattr(self.config, 'relationship_normalization', True)}")
            else:
                logger.info("📊 Initializing providers in FIXED SCHEMA extraction mode")
            
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
            
            logger.info("All providers initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize providers: {e}")
            return False
    
    @trace_method(name="provider_coordinator.check_health")
    def check_health(self) -> bool:
        """Verify all providers are healthy.
        
        Returns:
            True if all providers healthy, False otherwise
        """
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
        """Close all providers and clean up resources."""
        logger.info("Cleaning up providers...")
        
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