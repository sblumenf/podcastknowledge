"""Test that core module imports work correctly."""

import pytest


def test_core_interfaces_import():
    """Test that interfaces can be imported."""
    from src.core import (
        HealthCheckable,
        AudioProvider,
        LLMProvider,
        GraphProvider,
        EmbeddingProvider,
        KnowledgeExtractor,
        Neo4jManager,
    )
    
    # Verify they exist
    assert HealthCheckable is not None
    assert AudioProvider is not None
    assert LLMProvider is not None
    assert GraphProvider is not None
    assert EmbeddingProvider is not None
    assert KnowledgeExtractor is not None
    assert Neo4jManager is not None


def test_core_exceptions_import():
    """Test that exceptions can be imported."""
    from src.core import (
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
    
    # Verify exception hierarchy
    assert issubclass(DatabaseConnectionError, PodcastProcessingError)
    assert issubclass(AudioProcessingError, PodcastProcessingError)
    assert issubclass(LLMProcessingError, PodcastProcessingError)
    assert issubclass(ConfigurationError, PodcastProcessingError)
    assert issubclass(ValidationError, PodcastProcessingError)
    assert issubclass(ProviderError, PodcastProcessingError)
    assert issubclass(CriticalError, PodcastProcessingError)


def test_core_models_import():
    """Test that models can be imported."""
    from src.core import (
        Podcast,
        Episode,
        Segment,
        Entity,
        Insight,
        Quote,
        Topic,
        Speaker,
        ProcessingResult,
    )
    
    # Create simple instances
    podcast = Podcast(
        id="test_podcast",
        name="Test Podcast",
        description="Test Description",
        rss_url="https://example.com/rss"
    )
    assert podcast.id == "test_podcast"
    assert podcast.name == "Test Podcast"


def test_core_config_import():
    """Test that configuration can be imported."""
    from src.core import (
        PipelineConfig,
        SeedingConfig,
        load_config,
    )
    
    # Create config instance
    config = PipelineConfig()
    assert config.min_segment_tokens == 150
    assert config.max_segment_tokens == 800
    
    # Test seeding config inherits
    seeding_config = SeedingConfig()
    assert seeding_config.batch_size == 10
    assert seeding_config.save_checkpoints is True


def test_core_constants_import():
    """Test that constants can be imported."""
    from src.core import constants
    
    assert constants.VERSION == "0.1.0"
    assert constants.DEFAULT_WHISPER_MODEL == "large-v3"
    assert constants.MAX_TRANSCRIPT_LENGTH == 500000


def test_model_validation():
    """Test model validation functions."""
    from src.core import (
        Podcast,
        Episode,
        Segment,
        validate_podcast,
        validate_episode,
        validate_segment,
    )
    
    # Test podcast validation
    invalid_podcast = Podcast(id="", name="", description="Test", rss_url="")
    errors = validate_podcast(invalid_podcast)
    assert len(errors) == 3  # ID, name, and RSS URL errors
    
    # Test valid podcast
    valid_podcast = Podcast(
        id="test",
        name="Test",
        description="Test",
        rss_url="https://example.com/rss"
    )
    errors = validate_podcast(valid_podcast)
    assert len(errors) == 0


def test_exception_severity():
    """Test exception severity levels."""
    from src.core import (
        ErrorSeverity,
        ConfigurationError,
        ValidationError,
        AudioProcessingError,
    )
    
    # Test critical error
    config_error = ConfigurationError("Test error")
    assert config_error.severity == ErrorSeverity.CRITICAL
    
    # Test warning error
    validation_error = ValidationError("Test validation")
    assert validation_error.severity == ErrorSeverity.WARNING
    
    # Test custom severity
    audio_error = AudioProcessingError("Test audio", severity=ErrorSeverity.CRITICAL)
    assert audio_error.severity == ErrorSeverity.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])