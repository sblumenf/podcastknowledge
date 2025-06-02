"""
Test helper utilities for standardized testing patterns.

This module provides common fixtures, mocks, and utilities to ensure
consistent testing patterns across the test suite.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from unittest.mock import Mock, MagicMock
import json
import random
import pytest

from src.core.extraction_interface import (
    EntityType, InsightType, QuoteType, RelationshipType, ComplexityLevel
)
from src.core.models import (
    Speaker, SpeakerRole, Topic, Segment, Episode, Quote as QuoteModel, 
    Entity as EntityModel, PotentialConnection, ProcessingStatus
)


# Valid enum values for tests
VALID_ENTITY_TYPES = [e.value for e in EntityType]
VALID_INSIGHT_TYPES = [e.value for e in InsightType]  
VALID_QUOTE_TYPES = [e.value for e in QuoteType]
VALID_RELATIONSHIP_TYPES = [e.value for e in RelationshipType]
VALID_COMPLEXITY_LEVELS = [e.value for e in ComplexityLevel]


class TestDataFactory:
    """Factory for creating test data with valid values."""
    
    @staticmethod
    def create_speaker(
        name: str = "Test Speaker",
        role: SpeakerRole = SpeakerRole.HOST,
        bio: Optional[str] = None
    ) -> Speaker:
        """Create a test speaker."""
        return Speaker(
            id=f"speaker-{random.randint(1000, 9999)}",
            name=name,
            role=role,
            bio=bio or f"Bio for {name}"
        )
    
    @staticmethod
    def create_segment(
        text: str = "This is test segment content.",
        start_time: float = 0.0,
        end_time: float = 10.0,
        speaker: Optional[str] = "Test Speaker",
        segment_number: int = 1
    ) -> Segment:
        """Create a test segment."""
        return Segment(
            id=f"segment-{random.randint(1000, 9999)}",
            text=text,
            start_time=start_time,
            end_time=end_time,
            speaker=speaker,
            episode_id="test-episode",
            segment_index=segment_number - 1,
            segment_number=segment_number
        )
    
    @staticmethod
    def create_episode(
        title: str = "Test Episode",
        description: str = "Test episode description",
        published_date: str = "2024-01-01",
        guests: Optional[List[str]] = None
    ) -> Episode:
        """Create a test episode."""
        return Episode(
            id=f"episode-{random.randint(1000, 9999)}",
            title=title,
            description=description,
            published_date=published_date,
            audio_url="https://example.com/episode.mp3",
            duration=1800,  # 30 minutes
            episode_number=1,
            guests=guests or []
        )
    
    @staticmethod
    def create_entity(
        name: str = "Test Entity",
        entity_type: EntityType = EntityType.PERSON,
        description: Optional[str] = None,
        confidence: float = 0.9
    ) -> Dict[str, Any]:
        """Create a test entity as dict (for ExtractionResult)."""
        return {
            "name": name,
            "type": entity_type.value,
            "description": description or f"Description for {name}",
            "confidence": confidence,
            "properties": {}
        }
    
    @staticmethod
    def create_entity_model(
        name: str = "Test Entity",
        entity_type: EntityType = EntityType.PERSON,
        attributes: Optional[Dict[str, Any]] = None
    ) -> EntityModel:
        """Create a test entity model object."""
        return EntityModel(
            id=f"entity-{random.randint(1000, 9999)}",
            name=name,
            entity_type=entity_type.value,
            attributes=attributes or {}
        )
    
    @staticmethod
    def create_quote(
        text: str = "This is a notable quote.",
        speaker: str = "Test Speaker",
        quote_type: QuoteType = QuoteType.NOTABLE,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a test quote as dict (for ExtractionResult)."""
        return {
            "text": text,
            "speaker": speaker,
            "type": quote_type.value,
            "context": context or "In a discussion about testing",
            "timestamp": 5.0
        }
    
    @staticmethod
    def create_quote_model(
        text: str = "This is a notable quote.",
        speaker: str = "Test Speaker",
        speaker_id: Optional[str] = None,
        quote_type: str = "notable"
    ) -> QuoteModel:
        """Create a test quote model object."""
        return QuoteModel(
            id=f"quote-{random.randint(1000, 9999)}",
            text=text,
            speaker=speaker,
            speaker_id=speaker_id,
            quote_type=quote_type,
            context="Test context"
        )
    
    @staticmethod
    def create_relationship(
        source: str = "Entity1",
        target: str = "Entity2",
        rel_type: RelationshipType = RelationshipType.RELATED_TO,
        confidence: float = 0.8
    ) -> Dict[str, Any]:
        """Create a test relationship as dict."""
        return {
            "source": source,
            "target": target,
            "type": rel_type.value,
            "confidence": confidence,
            "properties": {}
        }
    
    @staticmethod
    def create_topic(
        name: str = "Test Topic",
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> Topic:
        """Create a test topic."""
        return Topic(
            id=f"topic-{random.randint(1000, 9999)}",
            name=name,
            description=description,
            keywords=keywords or [name.lower(), "test"]
        )
    
    @staticmethod
    def create_extraction_result(
        entities: Optional[List[Dict[str, Any]]] = None,
        quotes: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a test extraction result."""
        return {
            "entities": entities or [TestDataFactory.create_entity()],
            "quotes": quotes or [TestDataFactory.create_quote()],
            "relationships": relationships or [TestDataFactory.create_relationship()],
            "metadata": metadata or {"extracted_at": "2024-01-01T00:00:00Z"}
        }


class MockFactory:
    """Factory for creating common mocks."""
    
    @staticmethod
    def create_llm_provider_mock() -> Mock:
        """Create a mock LLM provider."""
        mock = Mock()
        mock.complete.return_value = TestDataFactory.create_extraction_result()
        mock.generate.return_value = "Mock generated text"
        return mock
    
    @staticmethod
    def create_neo4j_session_mock() -> Mock:
        """Create a mock Neo4j session."""
        mock = Mock()
        mock.run.return_value = Mock(single=lambda: {"count": 1})
        mock.__enter__ = Mock(return_value=mock)
        mock.__exit__ = Mock(return_value=None)
        return mock
    
    @staticmethod
    def create_neo4j_driver_mock() -> Mock:
        """Create a mock Neo4j driver."""
        mock = Mock()
        mock.session.return_value = MockFactory.create_neo4j_session_mock()
        mock.close = Mock()
        return mock
    
    @staticmethod
    def create_embedding_service_mock() -> Mock:
        """Create a mock embedding service."""
        mock = Mock()
        # Return 384-dimensional embeddings (standard for MiniLM)
        mock.encode.return_value = [[0.1] * 384]
        mock.get_embedding.return_value = [0.1] * 384
        mock.get_embeddings.return_value = [[0.1] * 384]
        return mock
    
    @staticmethod
    def create_checkpoint_mock() -> Mock:
        """Create a mock checkpoint manager."""
        mock = Mock()
        mock.get_checkpoint.return_value = None
        mock.save_checkpoint = Mock()
        mock.is_processed.return_value = False
        mock.mark_processed = Mock()
        return mock


# Common test fixtures
@pytest.fixture
def test_speaker():
    """Fixture for a test speaker."""
    return TestDataFactory.create_speaker()


@pytest.fixture
def test_segment():
    """Fixture for a test segment."""
    return TestDataFactory.create_segment()


@pytest.fixture
def test_episode():
    """Fixture for a test episode."""
    return TestDataFactory.create_episode()


@pytest.fixture
def test_entity():
    """Fixture for a test entity."""
    return TestDataFactory.create_entity()


@pytest.fixture
def test_quote():
    """Fixture for a test quote."""
    return TestDataFactory.create_quote()


@pytest.fixture
def test_extraction_result():
    """Fixture for a test extraction result."""
    return TestDataFactory.create_extraction_result()


@pytest.fixture
def mock_llm_provider():
    """Fixture for a mock LLM provider."""
    return MockFactory.create_llm_provider_mock()


@pytest.fixture
def mock_neo4j_driver():
    """Fixture for a mock Neo4j driver."""
    return MockFactory.create_neo4j_driver_mock()


@pytest.fixture
def mock_embedding_service():
    """Fixture for a mock embedding service."""
    return MockFactory.create_embedding_service_mock()


# Test assertion helpers
def assert_valid_entity(entity: Union[Dict[str, Any], EntityModel]) -> None:
    """Assert that an entity has valid structure and values."""
    if isinstance(entity, dict):
        assert "name" in entity
        assert "type" in entity
        assert entity["type"] in VALID_ENTITY_TYPES
    else:
        assert hasattr(entity, "name")
        assert hasattr(entity, "entity_type")
        assert entity.entity_type in VALID_ENTITY_TYPES


def assert_valid_quote(quote: Union[Dict[str, Any], QuoteModel]) -> None:
    """Assert that a quote has valid structure and values."""
    if isinstance(quote, dict):
        assert "text" in quote
        assert "speaker" in quote
        assert "type" in quote
        assert quote["type"] in VALID_QUOTE_TYPES
    else:
        assert hasattr(quote, "text")
        assert hasattr(quote, "speaker")
        assert hasattr(quote, "quote_type")


def assert_valid_relationship(relationship: Dict[str, Any]) -> None:
    """Assert that a relationship has valid structure and values."""
    assert "source" in relationship
    assert "target" in relationship
    assert "type" in relationship
    assert relationship["type"] in VALID_RELATIONSHIP_TYPES


def assert_valid_extraction_result(result: Dict[str, Any]) -> None:
    """Assert that an extraction result has valid structure."""
    assert "entities" in result
    assert "quotes" in result
    assert "relationships" in result
    assert isinstance(result["entities"], list)
    assert isinstance(result["quotes"], list)
    assert isinstance(result["relationships"], list)
    
    # Validate each component
    for entity in result["entities"]:
        assert_valid_entity(entity)
    
    for quote in result["quotes"]:
        assert_valid_quote(quote)
    
    for rel in result["relationships"]:
        assert_valid_relationship(rel)


# Test data generators for property-based testing
def generate_random_entity_type() -> EntityType:
    """Generate a random valid entity type."""
    return random.choice(list(EntityType))


def generate_random_insight_type() -> InsightType:
    """Generate a random valid insight type."""
    return random.choice(list(InsightType))


def generate_random_quote_type() -> QuoteType:
    """Generate a random valid quote type."""
    return random.choice(list(QuoteType))


def generate_random_relationship_type() -> RelationshipType:
    """Generate a random valid relationship type."""
    return random.choice(list(RelationshipType))


def generate_random_complexity_level() -> ComplexityLevel:
    """Generate a random valid complexity level."""
    return random.choice(list(ComplexityLevel))


# Integration test helpers
def create_test_vtt_content(
    speakers: List[str] = None,
    duration_seconds: int = 60
) -> str:
    """Create test VTT content."""
    if speakers is None:
        speakers = ["Speaker1", "Speaker2"]
    
    vtt_lines = ["WEBVTT", ""]
    
    time_step = 5  # 5 seconds per segment
    for i in range(0, duration_seconds, time_step):
        start = f"{i//60:02d}:{i%60:02d}.000"
        end_sec = min(i + time_step, duration_seconds)
        end = f"{end_sec//60:02d}:{end_sec%60:02d}.000"
        
        speaker = speakers[i // time_step % len(speakers)]
        text = f"This is segment {i // time_step + 1} from {speaker}."
        
        vtt_lines.extend([
            f"{start} --> {end}",
            f"<v {speaker}>{text}",
            ""
        ])
    
    return "\n".join(vtt_lines)


def create_test_rss_feed(
    podcast_title: str = "Test Podcast",
    episode_count: int = 3
) -> str:
    """Create test RSS feed content."""
    items = []
    for i in range(episode_count):
        items.append(f"""
        <item>
            <title>Episode {i+1}: Test Episode</title>
            <description>This is test episode {i+1}</description>
            <pubDate>Mon, {i+1:02d} Jan 2024 00:00:00 GMT</pubDate>
            <enclosure url="https://example.com/episode{i+1}.mp3" 
                       length="{12345678 + i * 1000000}" 
                       type="audio/mpeg"/>
            <guid isPermaLink="false">episode-{i+1}-guid</guid>
        </item>""")
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>{podcast_title}</title>
        <link>https://example.com/podcast</link>
        <description>A test podcast feed</description>
        <language>en-us</language>
        {"".join(items)}
    </channel>
</rss>"""