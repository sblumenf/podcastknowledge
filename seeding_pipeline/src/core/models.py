"""
Data models for the podcast knowledge pipeline.

This module defines all the data structures used throughout the system,
representing podcasts, episodes, segments, and extracted knowledge.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum


# Enums for various types
class ComplexityLevel(str, Enum):
    """Complexity levels for content classification."""
    LAYPERSON = "layperson"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"
    UNKNOWN = "unknown"


class InsightType(str, Enum):
    """Types of insights that can be extracted."""
    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    PREDICTION = "prediction"
    RECOMMENDATION = "recommendation"
    KEY_POINT = "key_point"
    TECHNICAL = "technical"
    METHODOLOGICAL = "methodological"


class QuoteType(str, Enum):
    """Types of quotes that can be extracted."""
    MEMORABLE = "memorable"
    CONTROVERSIAL = "controversial"
    HUMOROUS = "humorous"
    INSIGHTFUL = "insightful"
    TECHNICAL = "technical"
    GENERAL = "general"


class EntityType(str, Enum):
    """Types of entities that can be extracted."""
    PERSON = "person"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    CONCEPT = "concept"
    TECHNOLOGY = "technology"
    LOCATION = "location"
    EVENT = "event"
    OTHER = "other"


class SpeakerRole(str, Enum):
    """Role of a speaker in a podcast."""
    HOST = "host"
    GUEST = "guest"
    RECURRING = "recurring"
    UNKNOWN = "unknown"


# Main data models
@dataclass
class Podcast:
    """Represents a podcast series."""
    id: str
    name: str
    description: str
    rss_url: str
    website: Optional[str] = None
    hosts: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    created_timestamp: Optional[datetime] = None
    updated_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "title": self.name,  # Note: Neo4j uses 'title' but model uses 'name'
            "description": self.description,
            "rss_url": self.rss_url,
            "website": self.website,
            "hosts": self.hosts,
            "categories": self.categories
        }


@dataclass
class Episode:
    """Represents a podcast episode."""
    id: str
    title: str
    description: str
    published_date: str
    audio_url: Optional[str] = None
    duration: Optional[int] = None  # in seconds
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    processed_timestamp: Optional[datetime] = None
    
    # Complexity metrics
    avg_complexity: Optional[float] = None
    dominant_complexity_level: Optional[ComplexityLevel] = None
    technical_density: Optional[float] = None
    complexity_variance: Optional[float] = None
    is_mixed_complexity: bool = False
    is_technical: bool = False
    layperson_percentage: float = 0.0
    intermediate_percentage: float = 0.0
    expert_percentage: float = 0.0
    
    # Information density metrics
    avg_information_score: Optional[float] = None
    total_insights: int = 0
    total_entities: int = 0
    avg_accessibility: Optional[float] = None
    information_variance: Optional[float] = None
    has_consistent_density: bool = False
    
    # Sentiment evolution
    sentiment_evolution: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "published_date": self.published_date,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "episode_number": self.episode_number,
            "season_number": self.season_number
        }


@dataclass
class Segment:
    """Represents a segment of transcript."""
    id: str
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    episode_id: str = ""
    segment_index: int = 0
    
    # Content properties
    is_advertisement: bool = False
    word_count: int = 0
    duration_seconds: float = 0.0
    content_hash: Optional[str] = None
    
    # Analysis results
    sentiment: Optional[Dict[str, Any]] = None
    complexity_score: Optional[float] = None
    complexity_level: Optional[ComplexityLevel] = None
    technical_density: Optional[float] = None
    information_score: Optional[float] = None
    accessibility_score: Optional[float] = None
    
    # Embeddings
    embedding: Optional[List[float]] = None
    
    # Timestamps
    created_timestamp: Optional[datetime] = None
    updated_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "speaker": self.speaker,
            "episode_id": self.episode_id,
            "segment_index": self.segment_index,
            "is_advertisement": self.is_advertisement,
            "word_count": self.word_count,
            "duration_seconds": self.duration_seconds,
            "content_hash": self.content_hash,
            "embedding": self.embedding
        }


@dataclass
class Entity:
    """Represents an extracted entity."""
    id: str
    name: str
    entity_type: EntityType
    description: Optional[str] = None
    
    # Occurrence tracking
    first_mentioned: Optional[str] = None  # Episode ID
    mention_count: int = 1
    source_podcasts: List[str] = field(default_factory=list)
    source_episodes: List[str] = field(default_factory=list)
    
    # Graph analysis properties
    bridge_score: Optional[float] = None
    is_peripheral: bool = False
    is_multi_source: bool = False
    
    # Additional properties
    aliases: List[str] = field(default_factory=list)
    wikipedia_url: Optional[str] = None
    confidence_score: float = 1.0
    
    # Multi-factor importance scoring
    importance_score: float = 0.5  # Composite importance score 0-1
    importance_factors: Dict[str, float] = field(default_factory=dict)  # Breakdown of importance factors
    discourse_roles: Dict[str, float] = field(default_factory=dict)  # Entity's discourse functions
    
    # Embeddings
    embedding: Optional[List[float]] = None
    
    # Timestamps
    created_timestamp: Optional[datetime] = None
    updated_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type.value,
            "description": self.description,
            "first_mentioned": self.first_mentioned,
            "mention_count": self.mention_count,
            "bridge_score": self.bridge_score,
            "is_peripheral": self.is_peripheral,
            "importance_score": self.importance_score,
            "importance_factors": self.importance_factors,
            "discourse_roles": self.discourse_roles,
            "embedding": self.embedding
        }


@dataclass
class Insight:
    """Represents an extracted insight."""
    id: str
    title: str
    description: str
    insight_type: InsightType
    confidence_score: float = 1.0
    
    # Source tracking
    extracted_from_segment: Optional[str] = None
    supporting_entities: List[str] = field(default_factory=list)
    supporting_quotes: List[str] = field(default_factory=list)
    
    # Graph analysis
    is_bridge_insight: bool = False
    
    # Timestamps
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "insight_type": self.insight_type.value,
            "content": f"{self.title}: {self.description}",
            "confidence_score": self.confidence_score,
            "extracted_from_segment": self.extracted_from_segment,
            "is_bridge_insight": self.is_bridge_insight,
            "timestamp": self.timestamp
        }


@dataclass
class Quote:
    """Represents an extracted quote."""
    id: str
    text: str
    speaker: str
    quote_type: QuoteType = QuoteType.GENERAL
    context: Optional[str] = None
    
    # Metadata
    impact_score: float = 0.5
    word_count: int = 0
    estimated_timestamp: Optional[float] = None
    segment_id: Optional[str] = None
    episode_id: Optional[str] = None
    
    # Embedding
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "text": self.text,
            "speaker": self.speaker,
            "quote_type": self.quote_type.value,
            "context": self.context,
            "impact_score": self.impact_score,
            "word_count": self.word_count,
            "estimated_timestamp": self.estimated_timestamp,
            "segment_id": self.segment_id,
            "episode_id": self.episode_id,
            "embedding": self.embedding
        }


@dataclass
class Topic:
    """Represents a topic or theme."""
    id: str
    name: str
    description: Optional[str] = None
    trend: Optional[str] = None  # "emerging", "established", "declining"
    
    # Hierarchy
    hierarchy_level: int = 0
    parent_topics: List[str] = field(default_factory=list)
    child_topics: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trend": self.trend,
            "hierarchy_level": self.hierarchy_level,
            "parent_topics": self.parent_topics,
            "child_topics": self.child_topics
        }


@dataclass
class Speaker:
    """Represents a speaker in podcasts."""
    id: str
    name: str
    role: SpeakerRole = SpeakerRole.UNKNOWN
    
    # Statistics
    episode_count: int = 1
    total_speaking_time: float = 0.0
    
    # Timestamps
    created_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "created_timestamp": self.created_timestamp
        }


@dataclass
class PotentialConnection:
    """Represents a potential connection between entities."""
    id: str
    description: str
    strength: float
    entities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j."""
        return {
            "id": self.id,
            "description": self.description,
            "strength": self.strength,
            "entities": self.entities
        }


@dataclass
class ProcessingResult:
    """Result of processing a podcast episode."""
    episode_id: str
    success: bool
    
    # Extracted data
    segments: List[Segment] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    insights: List[Insight] = field(default_factory=list)
    quotes: List[Quote] = field(default_factory=list)
    topics: List[Topic] = field(default_factory=list)
    
    # Metrics
    processing_time: float = 0.0
    tokens_used: int = 0
    
    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "episode_id": self.episode_id,
            "success": self.success,
            "segment_count": len(self.segments),
            "entity_count": len(self.entities),
            "insight_count": len(self.insights),
            "quote_count": len(self.quotes),
            "topic_count": len(self.topics),
            "processing_time": self.processing_time,
            "tokens_used": self.tokens_used,
            "errors": self.errors,
            "warnings": self.warnings
        }


# Validation functions
def validate_podcast(podcast: Podcast) -> List[str]:
    """Validate podcast data."""
    errors = []
    if not podcast.id:
        errors.append("Podcast ID is required")
    if not podcast.name:
        errors.append("Podcast name is required")
    if not podcast.rss_url:
        errors.append("RSS URL is required")
    return errors


def validate_episode(episode: Episode) -> List[str]:
    """Validate episode data."""
    errors = []
    if not episode.id:
        errors.append("Episode ID is required")
    if not episode.title:
        errors.append("Episode title is required")
    if not episode.published_date:
        errors.append("Published date is required")
    return errors


def validate_segment(segment: Segment) -> List[str]:
    """Validate segment data."""
    errors = []
    if not segment.id:
        errors.append("Segment ID is required")
    if not segment.text:
        errors.append("Segment text is required")
    if segment.start_time < 0:
        errors.append("Start time must be non-negative")
    if segment.end_time <= segment.start_time:
        errors.append("End time must be after start time")
    return errors