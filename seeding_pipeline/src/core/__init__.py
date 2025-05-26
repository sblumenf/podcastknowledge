"""Core module for podcast knowledge pipeline."""

from .interfaces import (
    HealthCheckable,
    AudioProvider,
    LLMProvider,
    GraphProvider,
    EmbeddingProvider,
    KnowledgeExtractor,
    Neo4jManager,
    # Data classes
    DiarizationSegment,
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
    AudioProcessingError,
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

from . import constants

__all__ = [
    # Protocols
    "HealthCheckable",
    "AudioProvider",
    "LLMProvider", 
    "GraphProvider",
    "EmbeddingProvider",
    "KnowledgeExtractor",
    "Neo4jManager",
    # Interface data classes
    "DiarizationSegment",
    "TranscriptSegment",
    "LLMResponse",
    "ExtractedEntity",
    "ExtractedInsight",
    "ExtractedQuote",
    # Exceptions
    "ErrorSeverity",
    "PodcastProcessingError",
    "DatabaseConnectionError",
    "AudioProcessingError",
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
    # Constants module
    "constants",
]