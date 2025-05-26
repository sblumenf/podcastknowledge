"""Unit tests for data models."""

import pytest
from datetime import datetime

from src.core import (
    # Enums
    ComplexityLevel,
    InsightType,
    QuoteType,
    EntityType,
    SpeakerRole,
    # Models
    Podcast,
    Episode,
    Segment,
    Entity,
    Insight,
    Quote,
    Topic,
    Speaker,
    ProcessingResult,
    # Validation
    validate_podcast,
    validate_episode,
    validate_segment,
)


class TestPodcastModel:
    """Test Podcast model."""
    
    def test_podcast_creation(self):
        """Test creating a podcast instance."""
        podcast = Podcast(
            id="podcast_123",
            name="Test Podcast",
            description="A test podcast",
            rss_url="https://example.com/rss",
            website="https://example.com",
            hosts=["Alice", "Bob"],
            categories=["Technology", "Science"]
        )
        
        assert podcast.id == "podcast_123"
        assert podcast.name == "Test Podcast"
        assert podcast.description == "A test podcast"
        assert podcast.rss_url == "https://example.com/rss"
        assert podcast.website == "https://example.com"
        assert len(podcast.hosts) == 2
        assert "Alice" in podcast.hosts
        assert len(podcast.categories) == 2
        
    def test_podcast_to_dict(self):
        """Test podcast serialization."""
        podcast = Podcast(
            id="podcast_123",
            name="Test Podcast",
            description="A test podcast",
            rss_url="https://example.com/rss"
        )
        
        data = podcast.to_dict()
        assert data["id"] == "podcast_123"
        assert data["title"] == "Test Podcast"  # Note: uses 'title' for Neo4j
        assert data["description"] == "A test podcast"
        assert data["rss_url"] == "https://example.com/rss"
        
    def test_podcast_validation(self):
        """Test podcast validation."""
        # Valid podcast
        valid_podcast = Podcast(
            id="test",
            name="Test",
            description="Test",
            rss_url="https://example.com/rss"
        )
        assert validate_podcast(valid_podcast) == []
        
        # Invalid podcast
        invalid_podcast = Podcast(
            id="",
            name="",
            description="Test",
            rss_url=""
        )
        errors = validate_podcast(invalid_podcast)
        assert len(errors) == 3
        assert any("ID" in e for e in errors)
        assert any("name" in e for e in errors)
        assert any("RSS" in e for e in errors)


class TestEpisodeModel:
    """Test Episode model."""
    
    def test_episode_creation(self):
        """Test creating an episode instance."""
        episode = Episode(
            id="episode_123",
            title="Episode 1: Introduction",
            description="First episode",
            published_date="2024-01-24",
            audio_url="https://example.com/ep1.mp3",
            duration=3600,
            episode_number=1,
            season_number=1
        )
        
        assert episode.id == "episode_123"
        assert episode.title == "Episode 1: Introduction"
        assert episode.duration == 3600
        assert episode.episode_number == 1
        
    def test_episode_complexity_metrics(self):
        """Test episode complexity metrics."""
        episode = Episode(
            id="ep_123",
            title="Test",
            description="Test",
            published_date="2024-01-24",
            avg_complexity=0.75,
            dominant_complexity_level=ComplexityLevel.EXPERT,
            is_technical=True,
            layperson_percentage=20.0,
            intermediate_percentage=30.0,
            expert_percentage=50.0
        )
        
        assert episode.avg_complexity == 0.75
        assert episode.dominant_complexity_level == ComplexityLevel.EXPERT
        assert episode.is_technical is True
        assert episode.expert_percentage == 50.0
        
    def test_episode_validation(self):
        """Test episode validation."""
        # Valid episode
        valid_episode = Episode(
            id="ep1",
            title="Episode 1",
            description="Test",
            published_date="2024-01-24"
        )
        assert validate_episode(valid_episode) == []
        
        # Invalid episode
        invalid_episode = Episode(
            id="",
            title="",
            description="Test",
            published_date=""
        )
        errors = validate_episode(invalid_episode)
        assert len(errors) == 3


class TestSegmentModel:
    """Test Segment model."""
    
    def test_segment_creation(self):
        """Test creating a segment instance."""
        segment = Segment(
            id="segment_123",
            text="Hello, this is a test segment.",
            start_time=0.0,
            end_time=10.5,
            speaker="Alice",
            episode_id="episode_123",
            segment_index=0,
            word_count=6,
            duration_seconds=10.5
        )
        
        assert segment.id == "segment_123"
        assert segment.text == "Hello, this is a test segment."
        assert segment.start_time == 0.0
        assert segment.end_time == 10.5
        assert segment.speaker == "Alice"
        assert segment.duration_seconds == 10.5
        
    def test_segment_analysis_properties(self):
        """Test segment analysis properties."""
        segment = Segment(
            id="seg_123",
            text="Test",
            start_time=0.0,
            end_time=5.0,
            complexity_score=0.8,
            complexity_level=ComplexityLevel.EXPERT,
            is_advertisement=True,
            sentiment={"score": 0.5, "polarity": "positive"}
        )
        
        assert segment.complexity_score == 0.8
        assert segment.complexity_level == ComplexityLevel.EXPERT
        assert segment.is_advertisement is True
        assert segment.sentiment["polarity"] == "positive"
        
    def test_segment_validation(self):
        """Test segment validation."""
        # Valid segment
        valid_segment = Segment(
            id="seg1",
            text="Hello",
            start_time=0.0,
            end_time=1.0
        )
        assert validate_segment(valid_segment) == []
        
        # Invalid segment - negative start time
        invalid_segment1 = Segment(
            id="seg1",
            text="Hello",
            start_time=-1.0,
            end_time=1.0
        )
        errors = validate_segment(invalid_segment1)
        assert any("Start time" in e for e in errors)
        
        # Invalid segment - end before start
        invalid_segment2 = Segment(
            id="seg1",
            text="Hello",
            start_time=5.0,
            end_time=3.0
        )
        errors = validate_segment(invalid_segment2)
        assert any("End time" in e for e in errors)


class TestEntityModel:
    """Test Entity model."""
    
    def test_entity_creation(self):
        """Test creating an entity instance."""
        entity = Entity(
            id="entity_123",
            name="OpenAI",
            entity_type=EntityType.ORGANIZATION,
            description="AI research company",
            mention_count=5,
            bridge_score=0.85,
            is_peripheral=False
        )
        
        assert entity.id == "entity_123"
        assert entity.name == "OpenAI"
        assert entity.entity_type == EntityType.ORGANIZATION
        assert entity.mention_count == 5
        assert entity.bridge_score == 0.85
        assert entity.is_peripheral is False
        
    def test_entity_aliases(self):
        """Test entity with aliases."""
        entity = Entity(
            id="entity_123",
            name="GPT-4",
            entity_type=EntityType.TECHNOLOGY,
            aliases=["ChatGPT-4", "GPT4", "GPT 4"]
        )
        
        assert len(entity.aliases) == 3
        assert "ChatGPT-4" in entity.aliases


class TestInsightModel:
    """Test Insight model."""
    
    def test_insight_creation(self):
        """Test creating an insight instance."""
        insight = Insight(
            id="insight_123",
            title="AI Progress",
            description="AI models are improving rapidly",
            insight_type=InsightType.FACTUAL,
            confidence_score=0.9,
            is_bridge_insight=True
        )
        
        assert insight.id == "insight_123"
        assert insight.title == "AI Progress"
        assert insight.insight_type == InsightType.FACTUAL
        assert insight.confidence_score == 0.9
        assert insight.is_bridge_insight is True
        
    def test_insight_to_dict(self):
        """Test insight serialization."""
        insight = Insight(
            id="insight_123",
            title="Test Insight",
            description="Test description",
            insight_type=InsightType.CONCEPTUAL
        )
        
        data = insight.to_dict()
        assert data["id"] == "insight_123"
        assert data["insight_type"] == "conceptual"
        assert "Test Insight" in data["content"]
        assert "Test description" in data["content"]


class TestQuoteModel:
    """Test Quote model."""
    
    def test_quote_creation(self):
        """Test creating a quote instance."""
        quote = Quote(
            id="quote_123",
            text="This is a memorable quote.",
            speaker="Alice",
            quote_type=QuoteType.MEMORABLE,
            context="During the introduction",
            impact_score=0.8,
            word_count=5
        )
        
        assert quote.id == "quote_123"
        assert quote.text == "This is a memorable quote."
        assert quote.speaker == "Alice"
        assert quote.quote_type == QuoteType.MEMORABLE
        assert quote.impact_score == 0.8


class TestProcessingResult:
    """Test ProcessingResult model."""
    
    def test_processing_result_creation(self):
        """Test creating a processing result."""
        result = ProcessingResult(
            episode_id="episode_123",
            success=True,
            processing_time=120.5,
            tokens_used=5000
        )
        
        assert result.episode_id == "episode_123"
        assert result.success is True
        assert result.processing_time == 120.5
        assert result.tokens_used == 5000
        
    def test_processing_result_with_data(self):
        """Test processing result with extracted data."""
        result = ProcessingResult(
            episode_id="episode_123",
            success=True,
            segments=[
                Segment(id="s1", text="Test", start_time=0, end_time=1)
            ],
            entities=[
                Entity(id="e1", name="Test Entity", entity_type=EntityType.OTHER)
            ],
            insights=[
                Insight(id="i1", title="Test", description="Test", 
                       insight_type=InsightType.FACTUAL)
            ],
            errors=["Warning: Some issue"],
            warnings=["Info: Something to note"]
        )
        
        assert len(result.segments) == 1
        assert len(result.entities) == 1
        assert len(result.insights) == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        
    def test_processing_result_to_dict(self):
        """Test processing result serialization."""
        result = ProcessingResult(
            episode_id="episode_123",
            success=False,
            errors=["Error 1", "Error 2"]
        )
        
        data = result.to_dict()
        assert data["episode_id"] == "episode_123"
        assert data["success"] is False
        assert data["segment_count"] == 0
        assert len(data["errors"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])