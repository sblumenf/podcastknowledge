"""Comprehensive tests for src/core/models.py - targeting 100% coverage.

This test suite covers:
- All enum types and their values
- All dataclass models and their methods
- Serialization/deserialization (to_dict methods)
- Default values and factory functions
- Edge cases and validation
- Type conversions
"""

from datetime import datetime
from typing import Dict, Any
import json

import pytest

from src.core.models import (
    # Enums
    ComplexityLevel, InsightType, QuoteType, EntityType, SpeakerRole, ProcessingStatus,
    # Main models
    Podcast, Episode, Segment, Speaker, 
    # Knowledge models
    Entity, Quote, Insight, Topic, PotentialConnection,
    # Processing models
    ProcessingResult
)


class TestEnums:
    """Test all enum types."""
    
    def test_complexity_level_values(self):
        """Test ComplexityLevel enum has all expected values."""
        assert ComplexityLevel.LAYPERSON.value == "layperson"
        assert ComplexityLevel.INTERMEDIATE.value == "intermediate"
        assert ComplexityLevel.EXPERT.value == "expert"
        assert ComplexityLevel.UNKNOWN.value == "unknown"
        
        # Test all values
        expected_values = {"layperson", "intermediate", "expert", "unknown"}
        actual_values = {level.value for level in ComplexityLevel}
        assert actual_values == expected_values
    
    def test_insight_type_values(self):
        """Test InsightType enum has all expected values."""
        assert InsightType.FACTUAL.value == "factual"
        assert InsightType.CONCEPTUAL.value == "conceptual"
        assert InsightType.PREDICTION.value == "prediction"
        assert InsightType.RECOMMENDATION.value == "recommendation"
        assert InsightType.KEY_POINT.value == "key_point"
        assert InsightType.TECHNICAL.value == "technical"
        assert InsightType.METHODOLOGICAL.value == "methodological"
        
        # Verify count
        assert len(list(InsightType)) == 7
    
    def test_quote_type_values(self):
        """Test QuoteType enum has all expected values."""
        types = {qt.value for qt in QuoteType}
        expected = {"memorable", "controversial", "humorous", "insightful", "technical", "general"}
        assert types == expected
    
    def test_entity_type_values(self):
        """Test EntityType enum has all expected values."""
        assert EntityType.PERSON.value == "person"
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.PRODUCT.value == "product"
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.TECHNOLOGY.value == "technology"
        assert EntityType.LOCATION.value == "location"
        assert EntityType.EVENT.value == "event"
        assert EntityType.OTHER.value == "other"
    
    def test_speaker_role_values(self):
        """Test SpeakerRole enum has all expected values."""
        assert SpeakerRole.HOST.value == "host"
        assert SpeakerRole.GUEST.value == "guest"
        assert SpeakerRole.RECURRING.value == "recurring"
        assert SpeakerRole.UNKNOWN.value == "unknown"
    
    def test_enum_inheritance(self):
        """Test that enums inherit from str and Enum."""
        # Test string operations work
        assert ComplexityLevel.EXPERT.upper() == "EXPERT"
        assert InsightType.FACTUAL + "_test" == "factual_test"
        
        # Test enum operations work
        assert ComplexityLevel.EXPERT in ComplexityLevel
        assert list(SpeakerRole) == [SpeakerRole.HOST, SpeakerRole.GUEST, 
                                      SpeakerRole.RECURRING, SpeakerRole.UNKNOWN]


class TestPodcast:
    """Test Podcast model."""
    
    def test_podcast_creation_minimal(self):
        """Test creating podcast with minimal required fields."""
        podcast = Podcast(
            id="pod1",
            name="Test Podcast",
            description="A test podcast",
            rss_url="https://example.com/feed.xml"
        )
        
        assert podcast.id == "pod1"
        assert podcast.name == "Test Podcast"
        assert podcast.description == "A test podcast"
        assert podcast.rss_url == "https://example.com/feed.xml"
        assert podcast.website is None
        assert podcast.hosts == []
        assert podcast.categories == []
        assert podcast.created_timestamp is None
        assert podcast.updated_timestamp is None
    
    def test_podcast_creation_full(self):
        """Test creating podcast with all fields."""
        now = datetime.now()
        podcast = Podcast(
            id="pod2",
            name="Full Podcast",
            description="A complete podcast",
            rss_url="https://example.com/feed2.xml",
            website="https://example.com",
            hosts=["Alice", "Bob"],
            categories=["Technology", "Science"],
            created_timestamp=now,
            updated_timestamp=now
        )
        
        assert podcast.website == "https://example.com"
        assert podcast.hosts == ["Alice", "Bob"]
        assert podcast.categories == ["Technology", "Science"]
        assert podcast.created_timestamp == now
        assert podcast.updated_timestamp == now
    
    def test_podcast_to_dict(self):
        """Test podcast serialization to dictionary."""
        podcast = Podcast(
            id="pod3",
            name="Dict Test Podcast",
            description="Testing to_dict",
            rss_url="https://example.com/feed3.xml",
            website="https://example.com",
            hosts=["Charlie"],
            categories=["Education"]
        )
        
        result = podcast.to_dict()
        
        assert result["id"] == "pod3"
        assert result["title"] == "Dict Test Podcast"  # Note: name -> title
        assert result["description"] == "Testing to_dict"
        assert result["rss_url"] == "https://example.com/feed3.xml"
        assert result["website"] == "https://example.com"
        assert result["hosts"] == ["Charlie"]
        assert result["categories"] == ["Education"]
        
        # Timestamps are not included in to_dict
        assert "created_timestamp" not in result
        assert "updated_timestamp" not in result
    
    def test_podcast_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        podcast = Podcast(
            id="pod4",
            name="Minimal",
            description="Minimal podcast",
            rss_url="https://example.com/feed4.xml"
        )
        
        result = podcast.to_dict()
        
        assert result["website"] is None
        assert result["hosts"] == []
        assert result["categories"] == []


class TestEpisode:
    """Test Episode model."""
    
    def test_episode_creation_minimal(self):
        """Test creating episode with minimal fields."""
        episode = Episode(
            id="ep1",
            title="Episode 1",
            description="First episode",
            published_date="2024-01-01"
        )
        
        assert episode.id == "ep1"
        assert episode.title == "Episode 1"
        assert episode.description == "First episode"
        assert episode.published_date == "2024-01-01"
        assert episode.audio_url is None
        assert episode.duration is None
        assert episode.episode_number is None
        # Check default complexity metrics
        assert episode.avg_complexity is None
        assert episode.dominant_complexity_level is None
        assert episode.technical_density is None
        assert episode.layperson_percentage == 0.0
        assert episode.intermediate_percentage == 0.0
        assert episode.expert_percentage == 0.0
    
    def test_episode_creation_full(self):
        """Test creating episode with all fields."""
        episode = Episode(
            id="ep2",
            title="Episode 2",
            description="Second episode",
            published_date="2024-01-02",
            audio_url="https://example.com/episode2.mp3",
            duration=3600,
            episode_number=2,
            season_number=1,
            avg_complexity=0.7,
            dominant_complexity_level=ComplexityLevel.INTERMEDIATE,
            technical_density=0.5,
            is_technical=True
        )
        
        assert episode.audio_url == "https://example.com/episode2.mp3"
        assert episode.duration == 3600
        assert episode.episode_number == 2
        assert episode.season_number == 1
        assert episode.avg_complexity == 0.7
        assert episode.dominant_complexity_level == ComplexityLevel.INTERMEDIATE
        assert episode.technical_density == 0.5
        assert episode.is_technical is True
    
    def test_episode_to_dict(self):
        """Test episode serialization to dictionary."""
        episode = Episode(
            id="ep3",
            title="Test Episode",
            description="Testing serialization",
            published_date="2024-01-03",
            audio_url="https://example.com/ep3.mp3",
            duration=1800,
            episode_number=3,
            season_number=2
        )
        
        result = episode.to_dict()
        
        assert result["id"] == "ep3"
        assert result["title"] == "Test Episode"
        assert result["description"] == "Testing serialization"
        assert result["published_date"] == "2024-01-03"
        assert result["audio_url"] == "https://example.com/ep3.mp3"
        assert result["duration"] == 1800
        assert result["episode_number"] == 3
        assert result["season_number"] == 2
        
        # These fields should be in the dict
        assert "audio_url" in result
        assert "duration" in result


class TestSegment:
    """Test Segment model."""
    
    def test_segment_creation_minimal(self):
        """Test creating segment with minimal fields."""
        segment = Segment(
            id="seg1",
            text="Segment text",
            start_time=0.0,
            end_time=60.0,
            episode_id="ep1"
        )
        
        assert segment.id == "seg1"
        assert segment.episode_id == "ep1"
        assert segment.segment_index == 0  # Default value
        assert segment.start_time == 0.0
        assert segment.end_time == 60.0
        assert segment.text == "Segment text"
        assert segment.speaker is None
        assert segment.embedding is None
        assert segment.is_advertisement is False
        assert segment.word_count == 0
        assert segment.complexity_score is None
    
    def test_segment_creation_full(self):
        """Test creating segment with all fields."""
        embedding = [0.1, 0.2, 0.3]
        segment = Segment(
            id="seg2",
            text="Full segment text",
            start_time=60.0,
            end_time=120.0,
            episode_id="ep1",
            segment_index=1,
            speaker="Speaker One",
            embedding=embedding,
            is_advertisement=False,
            word_count=3,
            complexity_score=0.7
        )
        
        assert segment.speaker == "Speaker One"
        assert segment.embedding == embedding
        assert segment.is_advertisement is False
        assert segment.word_count == 3
        assert segment.complexity_score == 0.7
    
    def test_segment_to_dict(self):
        """Test segment serialization to dictionary."""
        segment = Segment(
            id="seg3",
            text="Serialization test",
            start_time=120.0,
            end_time=180.0,
            episode_id="ep1",
            segment_index=2,
            speaker="Speaker Two"
        )
        
        result = segment.to_dict()
        
        assert result["id"] == "seg3"
        assert result["episode_id"] == "ep1"
        assert result["segment_index"] == 2
        assert result["start_time"] == 120.0
        assert result["end_time"] == 180.0
        assert result["text"] == "Serialization test"
        assert result["speaker"] == "Speaker Two"
        assert result["is_advertisement"] is False
        assert result["word_count"] == 0
        
        # Embedding field is included in to_dict
        assert result["embedding"] is None
    
    def test_segment_to_dict_with_optional_fields(self):
        """Test segment to_dict includes optional fields when present."""
        segment = Segment(
            id="seg4",
            text="Optional fields test",
            start_time=180.0,
            end_time=240.0,
            episode_id="ep1",
            segment_index=3,
            embedding=[0.5, 0.6]
        )
        
        result = segment.to_dict()
        
        # Embedding is included in to_dict
        assert result["embedding"] == [0.5, 0.6]


class TestSpeaker:
    """Test Speaker model."""
    
    def test_speaker_creation(self):
        """Test creating speaker."""
        speaker = Speaker(
            id="speaker1",
            name="John Doe",
            role=SpeakerRole.HOST,
            bio="Host of the show"
        )
        
        assert speaker.id == "speaker1"
        assert speaker.name == "John Doe"
        assert speaker.role == SpeakerRole.HOST
        assert speaker.bio == "Host of the show"
    
    def test_speaker_with_guest_role(self):
        """Test speaker with guest role."""
        speaker = Speaker(
            id="speaker2",
            name="Jane Smith",
            role=SpeakerRole.GUEST,
            bio=None
        )
        
        assert speaker.role == SpeakerRole.GUEST
        assert speaker.bio is None
    
    def test_speaker_to_dict(self):
        """Test speaker serialization."""
        speaker = Speaker(
            id="speaker3",
            name="Bob Johnson",
            role=SpeakerRole.RECURRING,
            bio="Regular co-host"
        )
        
        result = speaker.to_dict()
        
        assert result["id"] == "speaker3"
        assert result["name"] == "Bob Johnson"
        assert result["role"] == "recurring"  # Enum value as string
        assert result["bio"] == "Regular co-host"
    
    def test_speaker_to_dict_with_none_bio(self):
        """Test speaker to_dict with None bio."""
        speaker = Speaker(
            id="speaker4",
            name="Unknown Speaker",
            role=SpeakerRole.UNKNOWN
        )
        
        result = speaker.to_dict()
        assert result["bio"] is None


class TestEntity:
    """Test Entity model."""
    
    def test_entity_creation_minimal(self):
        """Test creating entity with minimal fields."""
        entity = Entity(
            id="entity1",
            name="OpenAI",
            entity_type=EntityType.ORGANIZATION
        )
        
        assert entity.id == "entity1"
        assert entity.name == "OpenAI"
        assert entity.entity_type == EntityType.ORGANIZATION
        assert entity.description is None
        assert entity.mention_count == 1
        assert entity.source_podcasts == []
        assert entity.source_episodes == []
    
    def test_entity_creation_full(self):
        """Test creating entity with all fields."""
        metadata = {"founded": "2015", "location": "San Francisco"}
        mentions = ["ep1_seg1", "ep1_seg5"]
        
        entity = Entity(
            id="entity2",
            name="GPT-4",
            entity_type=EntityType.CONCEPT,
            description="Large language model",
            source_podcasts=["pod1"],
            source_episodes=["ep1", "ep2"],
            mention_count=2
        )
        
        assert entity.description == "Large language model"
        assert entity.source_podcasts == ["pod1"]
        assert entity.source_episodes == ["ep1", "ep2"]
        assert entity.mention_count == 2
    
    def test_entity_default_importance(self):
        """Test that importance defaults work correctly."""
        entity = Entity(
            id="entity3",
            name="Test",
            entity_type=EntityType.OTHER
        )
        
        assert entity.importance_score == 0.5  # Default importance
        assert entity.importance_factors == {}
        # Should be mutable
        entity.importance_factors["frequency"] = 0.8
        assert entity.importance_factors == {"frequency": 0.8}
    
    def test_entity_to_dict(self):
        """Test entity serialization."""
        entity = Entity(
            id="entity4",
            name="Python",
            entity_type=EntityType.TECHNOLOGY,
            description="Programming language",
            importance_score=0.8,
            importance_factors={"centrality": 0.7}
        )
        
        result = entity.to_dict()
        
        assert result["id"] == "entity4"
        assert result["name"] == "Python"
        assert result["type"] == "technology"  # Note: to_dict uses "type" not "entity_type"
        assert result["description"] == "Programming language"
        assert result["importance_score"] == 0.8
        assert result["importance_factors"] == {"centrality": 0.7}


class TestQuote:
    """Test Quote model."""
    
    def test_quote_creation_minimal(self):
        """Test creating quote with required fields."""
        quote = Quote(
            id="quote1",
            text="This is a memorable quote",
            speaker="Speaker One",
            quote_type=QuoteType.MEMORABLE
        )
        
        assert quote.id == "quote1"
        assert quote.text == "This is a memorable quote"
        assert quote.speaker == "Speaker One"
        assert quote.quote_type == QuoteType.MEMORABLE
        assert quote.context is None
        assert quote.impact_score == 0.5  # Default value
        assert quote.word_count == 0
        assert quote.episode_id is None
    
    def test_quote_creation_full(self):
        """Test creating quote with all fields."""
        quote = Quote(
            id="quote2",
            text="A technical explanation",
            speaker="Speaker Two",
            quote_type=QuoteType.TECHNICAL,
            context="During discussion of algorithms",
            impact_score=0.85,
            word_count=3,
            estimated_timestamp=120.0,
            episode_id="ep2",
            segment_id="seg2"
        )
        
        assert quote.context == "During discussion of algorithms"
        assert quote.impact_score == 0.85
        assert quote.word_count == 3
        assert quote.estimated_timestamp == 120.0
        assert quote.episode_id == "ep2"
        assert quote.segment_id == "seg2"
    
    def test_quote_to_dict(self):
        """Test quote serialization."""
        quote = Quote(
            id="quote3",
            text="Funny moment",
            speaker="Speaker Three",
            quote_type=QuoteType.HUMOROUS,
            episode_id="ep3",
            segment_id="seg3",
            estimated_timestamp=200.0
        )
        
        result = quote.to_dict()
        
        assert result["id"] == "quote3"
        assert result["text"] == "Funny moment"
        assert result["speaker"] == "Speaker Three"
        assert result["episode_id"] == "ep3"
        assert result["segment_id"] == "seg3"
        assert result["estimated_timestamp"] == 200.0
        assert result["quote_type"] == "humorous"
        assert result["context"] is None
        assert result["impact_score"] == 0.5  # Default value


class TestInsight:
    """Test Insight model."""
    
    def test_insight_creation_minimal(self):
        """Test creating insight with required fields."""
        insight = Insight(
            id="insight1",
            title="Key Finding",
            description="Key finding from discussion",
            insight_type=InsightType.KEY_POINT
        )
        
        assert insight.id == "insight1"
        assert insight.title == "Key Finding"
        assert insight.description == "Key finding from discussion"
        assert insight.insight_type == InsightType.KEY_POINT
        assert insight.confidence_score == 1.0  # Default
        assert insight.extracted_from_segment is None
        assert insight.supporting_entities == []
        assert insight.supporting_quotes == []
        assert insight.is_bridge_insight is False
    
    def test_insight_creation_full(self):
        """Test creating insight with all fields."""
        insight = Insight(
            id="insight2",
            title="ML Technical Insight",
            description="Technical insight about ML",
            insight_type=InsightType.TECHNICAL,
            confidence_score=0.92,
            extracted_from_segment="seg3",
            supporting_entities=["entity1", "entity2"],
            supporting_quotes=["quote1", "quote2"],
            is_bridge_insight=True
        )
        
        assert insight.confidence_score == 0.92
        assert insight.extracted_from_segment == "seg3"
        assert insight.supporting_entities == ["entity1", "entity2"]
        assert insight.supporting_quotes == ["quote1", "quote2"]
        assert insight.is_bridge_insight is True
    
    def test_insight_to_dict(self):
        """Test insight serialization."""
        insight = Insight(
            id="insight3",
            title="Future Prediction",
            description="Prediction about future",
            insight_type=InsightType.PREDICTION,
            confidence_score=0.75,
            extracted_from_segment="seg4"
        )
        
        result = insight.to_dict()
        
        assert result["id"] == "insight3"
        assert result["content"] == "Future Prediction: Prediction about future"
        assert result["insight_type"] == "prediction"
        assert result["confidence_score"] == 0.75
        assert result["extracted_from_segment"] == "seg4"
        assert result["is_bridge_insight"] is False


class TestTopic:
    """Test Topic model."""
    
    def test_topic_creation(self):
        """Test creating topic."""
        topic = Topic(
            id="topic1",
            name="Machine Learning",
            description="Discussion about ML concepts",
            keywords=["AI", "neural networks", "deep learning"]
        )
        
        assert topic.id == "topic1"
        assert topic.name == "Machine Learning"
        assert topic.description == "Discussion about ML concepts"
        assert topic.keywords == ["AI", "neural networks", "deep learning"]
    
    def test_topic_minimal(self):
        """Test topic with minimal fields."""
        topic = Topic(
            id="topic2",
            name="Technology"
        )
        
        assert topic.id == "topic2"
        assert topic.name == "Technology"
        assert topic.description is None
        assert topic.keywords == []
    
    def test_topic_to_dict(self):
        """Test topic serialization."""
        topic = Topic(
            id="topic3",
            name="Future Tech",
            description="Future technology trends",
            keywords=["quantum", "biotech"]
        )
        
        result = topic.to_dict()
        
        assert result["id"] == "topic3"
        assert result["name"] == "Future Tech"
        assert result["description"] == "Future technology trends"
        assert result["keywords"] == ["quantum", "biotech"]


class TestPotentialConnection:
    """Test PotentialConnection model."""
    
    def test_potential_connection_creation(self):
        """Test creating potential connection."""
        connection = PotentialConnection(
            id="conn1",
            source_id="entity1",
            target_id="entity2",
            description="related_to",
            strength=0.78,
            entities=["entity1", "entity2"]
        )
        
        assert connection.source_id == "entity1"
        assert connection.target_id == "entity2"
        assert connection.description == "related_to"
        assert connection.strength == 0.78
        assert connection.entities == ["entity1", "entity2"]
    
    def test_potential_connection_minimal(self):
        """Test potential connection with minimal fields."""
        connection = PotentialConnection(
            id="conn2",
            source_id="e1",
            target_id="e2",
            description="mentions",
            strength=0.5
        )
        
        assert connection.source_id == "e1"
        assert connection.target_id == "e2"
        assert connection.description == "mentions"
        assert connection.strength == 0.5
        assert connection.entities == []


class TestProcessingResult:
    """Test ProcessingResult model."""
    
    def test_processing_result_creation(self):
        """Test creating processing result."""
        segments = [Segment(
            id="seg1",
            episode_id="ep1",
            segment_number=1,
            start_time=0.0,
            end_time=60.0,
            text="Test segment"
        )]
        entities = [Entity(
            id="ent1",
            name="Test Entity",
            entity_type=EntityType.ORGANIZATION
        )]
        
        result = ProcessingResult(
            episode_id="ep1",
            success=True,
            segments=segments,
            entities=entities,
            insights=[],
            quotes=[],
            topics=[],
            error=None
        )
        
        assert result.episode_id == "ep1"
        assert result.success is True
        assert len(result.segments) == 1
        assert len(result.entities) == 1
        assert result.insights == []
        assert result.quotes == []
        assert result.topics == []
        assert result.error is None
    
    def test_processing_result_failed(self):
        """Test failed processing result."""
        result = ProcessingResult(
            episode_id="ep2",
            success=False,
            segments=[],
            entities=[],
            insights=[],
            quotes=[],
            topics=[],
            error="Processing failed: timeout"
        )
        
        assert result.success is False
        assert result.error == "Processing failed: timeout"
        assert result.segments == []
        assert result.entities == []


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_lists_remain_independent(self):
        """Test that default empty lists are independent instances."""
        ep1 = Episode(
            id="ep1",
            title="Episode 1",
            description="First",
            published_date="2024-01-01"
        )
        ep2 = Episode(
            id="ep2",
            title="Episode 2",
            description="Second",
            published_date="2024-01-02"
        )
        
        # Modify one episode's lists
        ep1.guests.append("Guest A")
        
        # Other episode's lists should be unaffected
        assert ep2.guests == []
    
    def test_enum_string_comparison(self):
        """Test that enum values can be compared with strings."""
        assert ComplexityLevel.EXPERT == "expert"
        assert EntityType.PERSON == "person"
        assert ProcessingStatus.COMPLETED == "completed"
    
    def test_dataclass_equality(self):
        """Test dataclass equality comparison."""
        pod1 = Podcast(
            id="pod1",
            name="Test",
            description="Test",
            rss_url="https://example.com"
        )
        pod2 = Podcast(
            id="pod1",
            name="Test",
            description="Test",
            rss_url="https://example.com"
        )
        pod3 = Podcast(
            id="pod2",  # Different ID
            name="Test",
            description="Test",
            rss_url="https://example.com"
        )
        
        assert pod1 == pod2
        assert pod1 != pod3
    
    def test_to_dict_methods_json_serializable(self):
        """Test that to_dict outputs are JSON serializable."""
        # Create instances with various types
        podcast = Podcast(
            id="pod1",
            name="Test",
            description="Test",
            rss_url="https://example.com",
            hosts=["Host 1", "Host 2"]
        )
        
        episode = Episode(
            id="ep1",
            title="Episode",
            description="Test episode",
            published_date="2024-01-01",
            duration=3600,
            guests=["Guest"]
        )
        
        entity = Entity(
            id="ent1",
            name="Entity",
            entity_type=EntityType.ORGANIZATION
        )
        
        # Should not raise exception
        json.dumps(podcast.to_dict())
        json.dumps(episode.to_dict())
        json.dumps(entity.to_dict())
    
    def test_optional_field_handling(self):
        """Test that optional fields handle None properly."""
        segment = Segment(
            id="seg1",
            text="Text",
            start_time=0.0,
            end_time=60.0,
            speaker=None,
            episode_id="ep1",
            segment_number=1
        )
        
        result = segment.to_dict()
        
        # None values should be included in the dict
        assert result["speaker"] is None
        assert result["content_hash"] is None
        
        # Some fields are included even when None
        assert "embedding" in result
        assert result["embedding"] is None
    
    def test_float_timestamp_handling(self):
        """Test that float timestamps work correctly."""
        quote = Quote(
            id="q1",
            text="Quote",
            speaker="Speaker Name",
            speaker_id="s1",
            episode_id="e1",
            segment_id="seg1",
            estimated_timestamp=123.456,  # Float with decimals
            quote_type=QuoteType.GENERAL
        )
        
        assert quote.estimated_timestamp == 123.456
        assert quote.to_dict()["estimated_timestamp"] == 123.456
    
    def test_large_embedding_vectors(self):
        """Test handling of large embedding vectors."""
        # Create a large embedding (e.g., 1536 dimensions like OpenAI)
        large_embedding = [0.1] * 1536
        
        segment = Segment(
            id="seg1",
            episode_id="ep1",
            segment_number=1,
            start_time=0.0,
            end_time=60.0,
            text="Text",
            embedding=large_embedding
        )
        
        assert len(segment.embedding) == 1536
        assert segment.embedding[0] == 0.1
        assert segment.embedding[-1] == 0.1
        
        # to_dict should include embedding
        result = segment.to_dict()
        assert "embedding" in result
        assert len(result["embedding"]) == 1536