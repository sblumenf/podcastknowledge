"""
Extraction interface abstraction for unified extraction modes.

This module defines the protocol that both fixed schema and schemaless
extraction modes must implement, enabling seamless switching between modes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, List, Dict, Any, Optional
class EntityType(Enum):
    """Types of entities that can be extracted."""
    PERSON = "person"
    ORGANIZATION = "organization"
    TOPIC = "topic"
    CONCEPT = "concept"
    LOCATION = "location"
    PRODUCT = "product"
    EVENT = "event"
    OTHER = "other"


class InsightType(Enum):
    """Types of insights that can be extracted."""
    KEY_POINT = "key_point"
    SUMMARY = "summary"
    OPINION = "opinion"
    FACT = "fact"
    PREDICTION = "prediction"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


class QuoteType(Enum):
    """Types of quotes that can be extracted."""
    NOTABLE = "notable"
    CONTROVERSIAL = "controversial"
    INSIGHTFUL = "insightful"
    HUMOROUS = "humorous"
    TECHNICAL = "technical"
    OTHER = "other"


class RelationshipType(Enum):
    """Types of relationships between entities."""
    MENTIONS = "mentions"
    DISCUSSES = "discusses"
    WORKS_FOR = "works_for"
    CREATED_BY = "created_by"
    RELATED_TO = "related_to"
    DISAGREES_WITH = "disagrees_with"
    AGREES_WITH = "agrees_with"
    OTHER = "other"


class ComplexityLevel(Enum):
    """Complexity levels for content."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
@dataclass
class Segment:
    """Represents a transcript segment."""
    text: str
    start: float
    end: float
    speaker: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Entity:
    """Represents an extracted entity."""
    name: str
    type: str
    description: Optional[str] = None
    confidence: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None


@dataclass
class Relationship:
    """Represents a relationship between entities."""
    source: str
    target: str
    type: str
    confidence: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None


@dataclass
class Quote:
    """Represents a notable quote."""
    text: str
    speaker: str
    timestamp: float
    context: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class Insight:
    """Represents an insight or key finding."""
    content: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None
    category: Optional[str] = None


class ExtractionInterface(Protocol):
    """
    Protocol defining the interface for all extraction modes.
    
    Both fixed schema and schemaless extractors must implement this interface
    to ensure compatibility with the pipeline.
    """
    
    def extract_entities(self, segment: Segment) -> List[Entity]:
        """
        Extract entities from a segment.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            List of extracted entities
        """
        ...
    
    def extract_relationships(self, segment: Segment) -> List[Relationship]:
        """
        Extract relationships from a segment.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            List of extracted relationships
        """
        ...
    
    def extract_quotes(self, segment: Segment) -> List[Quote]:
        """
        Extract notable quotes from a segment.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            List of extracted quotes
        """
        ...
    
    def extract_insights(self, segment: Segment) -> List[Insight]:
        """
        Extract insights from a segment.
        
        Note: This may return empty list for schemaless mode
        as insights are a fixed schema concept.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            List of extracted insights
        """
        ...
    
    def extract_all(self, segment: Segment) -> Dict[str, Any]:
        """
        Extract all information from a segment.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            Dictionary containing all extracted information:
            {
                'entities': List[Entity],
                'relationships': List[Relationship],
                'quotes': List[Quote],
                'insights': List[Insight],
                'metadata': Dict[str, Any]
            }
        """
        ...
    
    def get_extraction_mode(self) -> str:
        """
        Get the extraction mode identifier.
        
        Returns:
            Mode identifier: 'fixed', 'schemaless', or 'migration'
        """
        ...
    
    def get_discovered_types(self) -> Optional[List[str]]:
        """
        Get discovered entity types (for schemaless mode).
        
        Returns:
            List of discovered entity types or None for fixed schema
        """
        ...