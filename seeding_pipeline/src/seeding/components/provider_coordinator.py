"""Service coordination component for managing all pipeline services."""

from dataclasses import asdict
from typing import Dict, Any, Optional
import logging

from src.core.config import PipelineConfig
from src.core.exceptions import ConfigurationError
from src.extraction import KnowledgeExtractor, EntityResolver
from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.processing.segmentation import VTTTranscriptSegmenter
from src.services import create_gemini_services, LLMService, GeminiEmbeddingsService
from src.storage import GraphStorageService
from src.core.env_config import EnvironmentConfig
logger = logging.getLogger(__name__)


class ProviderCoordinator:
    """Coordinates initialization and management of all pipeline services."""
    
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
        """Initialize all services and processing components.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing pipeline services...")
            
            # Log extraction mode (always schemaless now)
            logger.info("🔄 Initializing services in SCHEMALESS extraction mode")
            logger.info(f"  - Entity resolution threshold: {getattr(self.config, 'entity_resolution_threshold', 0.85)}")
            logger.info(f"  - Max properties per node: {getattr(self.config, 'max_properties_per_node', 50)}")
            logger.info(f"  - Relationship normalization: {getattr(self.config, 'relationship_normalization', True)}")
            
            # Convert config to dict for services
            config_dict = asdict(self.config) if hasattr(self.config, '__dataclass_fields__') else self.config
            
            # Initialize services using factory function with key rotation
            try:
                # Create Gemini services with shared key rotation
                self.llm_service, self.embedding_service = create_gemini_services(
                    llm_model=getattr(self.config, 'model_name', None) or EnvironmentConfig.get_flash_model(),
                    embeddings_model=getattr(self.config, 'embedding_model', None) or EnvironmentConfig.get_embedding_model(),
                    temperature=getattr(self.config, 'temperature', 0.7),
                    max_tokens=getattr(self.config, 'max_tokens', 4096),
                    embeddings_batch_size=getattr(self.config, 'embedding_batch_size', 100),
                    enable_cache=getattr(self.config, 'enable_cache', True),
                    cache_ttl=getattr(self.config, 'cache_ttl', 3600)
                )
                logger.info("✓ Initialized Gemini services with API key rotation")
            except ValueError as e:
                # Fall back to direct API key if rotation not available
                api_key = getattr(self.config, 'google_api_key', None) or getattr(self.config, 'api_key', None)
                if not api_key:
                    raise ConfigurationError("No API keys found. Please set GOOGLE_API_KEY or GEMINI_API_KEY_1-9")
                raise ConfigurationError(f"Failed to initialize services: {e}")
            
            # Initialize graph storage service
            self.graph_service = GraphStorageService(
                uri=getattr(self.config, 'neo4j_uri', None),
                username=getattr(self.config, 'neo4j_username', None),
                password=getattr(self.config, 'neo4j_password', None),
                database=getattr(self.config, 'neo4j_database', 'neo4j'),
                pool_size=getattr(self.config, 'pool_size', 50)
            )
            
            # Initialize processing components
            # Note: Audio provider and segmenter removed with provider pattern migration
            
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
    
    def cleanup(self):
        """Close all services and clean up resources."""
        logger.info("Cleaning up services...")
        
        # Close graph service (only one that needs explicit cleanup)
        if self.graph_service:
            try:
                self.graph_service.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting graph service: {e}")