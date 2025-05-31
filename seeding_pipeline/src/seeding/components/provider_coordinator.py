"""Provider coordination component for managing all pipeline providers."""

import logging
from typing import Dict, Any, Optional
from dataclasses import asdict

from src.services import LLMService, EmbeddingsService
from src.storage import GraphStorageService
from src.processing.segmentation import VTTTranscriptSegmenter
from src.extraction import KnowledgeExtractor, EntityResolver
# Analytics components removed in Phase 3.3.1
# Graph enhancements removed with provider pattern
from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.core.config import PipelineConfig
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ProviderCoordinator:
    """Coordinates initialization and management of all pipeline providers."""
    
    def __init__(self, config: PipelineConfig):
        """Initialize the provider coordinator.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config
        
        # Services
        self.llm_service: Optional[LLMService] = None
        self.graph_service: Optional[GraphStorageService] = None
        self.embedding_service: Optional[EmbeddingsService] = None
        
        # Processing components
        self.segmenter: Optional[EnhancedPodcastSegmenter] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.entity_resolver: Optional[EntityResolver] = None
        # Analytics components removed in Phase 3.3.1
        self.graph_enhancer: Optional[Any] = None  # Removed with provider pattern
        self.episode_flow_analyzer: Optional[EpisodeFlowAnalyzer] = None
    
    def initialize_providers(self, use_large_context: bool = True) -> bool:
        """Initialize all providers and processing components.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing pipeline providers...")
            
            # Log extraction mode (always schemaless now)
            logger.info("🔄 Initializing services in SCHEMALESS extraction mode")
            logger.info(f"  - Entity resolution threshold: {getattr(self.config, 'entity_resolution_threshold', 0.85)}")
            logger.info(f"  - Max properties per node: {getattr(self.config, 'max_properties_per_node', 50)}")
            logger.info(f"  - Relationship normalization: {getattr(self.config, 'relationship_normalization', True)}")
            
            # Convert config to dict for providers
            config_dict = asdict(self.config) if hasattr(self.config, '__dataclass_fields__') else self.config
            
            # Initialize services directly
            # Get API key from config
            api_key = getattr(self.config, 'google_api_key', None) or getattr(self.config, 'api_key', None)
            if not api_key:
                raise ConfigurationError("Google API key is required for LLM service")
            
            # Initialize LLM service
            self.llm_service = LLMService(
                api_key=api_key,
                model_name=getattr(self.config, 'model_name', 'gemini-2.5-flash'),
                temperature=getattr(self.config, 'temperature', 0.7),
                max_tokens=getattr(self.config, 'max_tokens', 4096)
            )
            
            # Initialize graph storage service
            self.graph_service = GraphStorageService(
                uri=getattr(self.config, 'neo4j_uri', None),
                username=getattr(self.config, 'neo4j_username', None),
                password=getattr(self.config, 'neo4j_password', None),
                database=getattr(self.config, 'neo4j_database', 'neo4j'),
                pool_size=getattr(self.config, 'pool_size', 50)
            )
            
            # Initialize embeddings service
            self.embedding_service = EmbeddingsService(
                model_name=getattr(self.config, 'embedding_model', 'all-MiniLM-L6-v2'),
                device=getattr(self.config, 'device', 'cpu'),
                batch_size=getattr(self.config, 'embedding_batch_size', 32),
                normalize_embeddings=getattr(self.config, 'normalize_embeddings', True)
            )
            
            # Initialize processing components
            segmenter_config = getattr(self.config, 'segmenter_config', {})
            if hasattr(segmenter_config, '__dataclass_fields__'):
                segmenter_config = asdict(segmenter_config)
            # Note: Audio provider removed with provider pattern
            # Segmenter will need to be updated to work without it
            self.segmenter = None  # TODO: Update segmenter for direct usage
            
            self.knowledge_extractor = KnowledgeExtractor(
                self.llm_service,
                self.embedding_service
            )
            
            self.entity_resolver = EntityResolver()
            
            # Analytics components removed in Phase 3.3.1
            self.graph_enhancer = None  # Removed with provider pattern
            self.episode_flow_analyzer = EpisodeFlowAnalyzer(self.embedding_service)
            
            logger.info("All providers initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize providers: {e}")
            return False
    
    def check_health(self) -> bool:
        """Verify all providers are healthy.
        
        Returns:
            True if all providers healthy, False otherwise
        """
        components = [
            ('LLM Service', self.llm_service),
            ('Graph Service', self.graph_service),
            ('Embedding Service', self.embedding_service)
        ]
        
        all_healthy = True
        for name, component in components:
            if component is None:
                logger.error(f"{name} not initialized")
                all_healthy = False
                continue
                
            try:
                health = component.health_check()
                if not health.get('healthy', False):
                    logger.error(f"{name} unhealthy: {health}")
                    all_healthy = False
                else:
                    logger.info(f"{name} healthy")
            except Exception as e:
                logger.error(f"{name} health check failed: {e}")
                all_healthy = False
        
        return all_healthy
    
    def cleanup(self):
        """Close all services and clean up resources."""
        logger.info("Cleaning up services...")
        
        # Close graph service (only one that needs explicit cleanup)
        if self.graph_service:
            try:
                self.graph_service.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting graph service: {e}")