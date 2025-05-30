"""Core module for podcast knowledge pipeline."""

from .interfaces import (
    HealthCheckable,
    LLMProvider,
    GraphProvider,
    EmbeddingProvider,
    KnowledgeExtractor,
    Neo4jManager,
    # Data classes
    TranscriptSegment,
    LLMResponse,
    ExtractedEntity,
    ExtractedInsight,
    ExtractedQuote,
)

from .exceptions import (
    ErrorSeverity,
    PodcastProcessingError,
    DatabaseConnectionError,
    LLMProcessingError,
    ConfigurationError,
    ValidationError,
    ProviderError,
    CriticalError,
)

from .models import (
    # Enums
    ComplexityLevel,
    InsightType,
    QuoteType,
    EntityType,
    SpeakerRole,
    # Data models
    Podcast,
    Episode,
    Segment,
    Entity,
    Insight,
    Quote,
    Topic,
    Speaker,
    PotentialConnection,
    ProcessingResult,
    # Validation
    validate_podcast,
    validate_episode,
    validate_segment,
)

from .config import (
    PipelineConfig,
    SeedingConfig,
    load_config,
    get_neo4j_config,
    get_llm_config,
)

from .feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    get_feature_flag_manager,
    is_enabled,
    set_flag,
    get_all_flags,
    requires_flag,
)

from . import constants

__all__ = [
    # Protocols
    "HealthCheckable",
    "LLMProvider", 
    "GraphProvider",
    "EmbeddingProvider",
    "KnowledgeExtractor",
    "Neo4jManager",
    # Interface data classes
    "TranscriptSegment",
    "LLMResponse",
    "ExtractedEntity",
    "ExtractedInsight",
    "ExtractedQuote",
    # Exceptions
    "ErrorSeverity",
    "PodcastProcessingError",
    "DatabaseConnectionError",
    "LLMProcessingError",
    "ConfigurationError",
    "ValidationError",
    "ProviderError",
    "CriticalError",
    # Enums
    "ComplexityLevel",
    "InsightType",
    "QuoteType",
    "EntityType",
    "SpeakerRole",
    # Data models
    "Podcast",
    "Episode",
    "Segment",
    "Entity",
    "Insight",
    "Quote",
    "Topic",
    "Speaker",
    "PotentialConnection",
    "ProcessingResult",
    # Validation
    "validate_podcast",
    "validate_episode",
    "validate_segment",
    # Configuration
    "PipelineConfig",
    "SeedingConfig",
    "load_config",
    "get_neo4j_config",
    "get_llm_config",
    # Feature flags
    "FeatureFlag",
    "FeatureFlagManager",
    "get_feature_flag_manager",
    "is_enabled",
    "set_flag",
    "get_all_flags",
    "requires_flag",
    # Constants module
    "constants",
]