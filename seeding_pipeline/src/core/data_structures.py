"""Canonical data structure definitions for the knowledge extraction pipeline.

This module defines the standard field names and types for all data structures
used throughout the pipeline. These definitions serve as the single source of truth
for field naming conventions and ensure consistency across all components.

IMPORTANT: These structures define the contract between pipeline components.
All components MUST use these field names exactly as defined here.
"""

from typing import TypedDict, List, Optional, Dict, Any


class EntityData(TypedDict):
    """Standard entity data structure.
    
    Required fields:
    - value: The entity name/value (e.g., "Elon Musk", "artificial intelligence")
    - type: Entity type (e.g., "PERSON", "TECHNOLOGY", "ORGANIZATION")
    
    Optional fields:
    - confidence: Confidence score (0.0 to 1.0)
    - description: Brief description of the entity
    - importance: Importance score (0.0 to 1.0)
    - frequency: Number of mentions
    - has_citation: Whether entity has supporting citations
    - start_time: Start timestamp in seconds
    - end_time: End timestamp in seconds
    - properties: Additional properties dict
    """
    value: str  # Entity name/value - REQUIRED
    type: str   # Entity type - REQUIRED
    
    # Optional fields
    confidence: float
    description: str
    importance: float
    frequency: int
    has_citation: bool
    start_time: float
    end_time: float
    properties: Dict[str, Any]


class QuoteData(TypedDict):
    """Standard quote data structure.
    
    Required fields:
    - text: The quote text content
    
    Optional fields:
    - speaker: Speaker name
    - context: Context around the quote
    - quote_type: Type of quote (e.g., "general", "key_point")
    - importance: Importance score (0.0 to 1.0)
    - confidence: Confidence score (0.0 to 1.0)
    - timestamp_start: Start timestamp in seconds
    - timestamp_end: End timestamp in seconds
    - properties: Additional properties dict
    """
    text: str  # Quote text - REQUIRED
    
    # Optional fields
    speaker: str
    context: str
    quote_type: str
    importance: float
    confidence: float
    timestamp_start: float
    timestamp_end: float
    properties: Dict[str, Any]


class InsightData(TypedDict):
    """Standard insight data structure.
    
    Required fields:
    - title: Brief title of the insight
    - description: Detailed description
    
    Optional fields:
    - type: Insight type (e.g., "conceptual", "practical")
    - confidence: Confidence score (0.0 to 1.0)
    - supporting_entities: List of related entity values
    - properties: Additional properties dict
    """
    title: str        # Insight title - REQUIRED
    description: str  # Insight description - REQUIRED
    
    # Optional fields
    type: str
    confidence: float
    supporting_entities: List[str]
    properties: Dict[str, Any]


class RelationshipData(TypedDict):
    """Standard relationship data structure.
    
    Required fields:
    - source: Source entity value
    - target: Target entity value
    - type: Relationship type (e.g., "WORKS_FOR", "CREATED_BY")
    
    Optional fields:
    - confidence: Confidence score (0.0 to 1.0)
    - properties: Additional properties dict
    """
    source: str  # Source entity value - REQUIRED
    target: str  # Target entity value - REQUIRED
    type: str    # Relationship type - REQUIRED
    
    # Optional fields
    confidence: float
    properties: Dict[str, Any]


class ExtractionResult(TypedDict):
    """Standard extraction result structure.
    
    Contains all extracted knowledge from a segment or unit.
    """
    entities: List[EntityData]
    quotes: List[QuoteData]
    insights: List[InsightData]
    relationships: List[RelationshipData]
    
    # Optional conversation structure data
    conversation_structure: Dict[str, Any]


# Field name constants to prevent typos
ENTITY_VALUE_FIELD = 'value'
ENTITY_TYPE_FIELD = 'type'
QUOTE_TEXT_FIELD = 'text'
INSIGHT_TITLE_FIELD = 'title'
INSIGHT_DESCRIPTION_FIELD = 'description'
RELATIONSHIP_SOURCE_FIELD = 'source'
RELATIONSHIP_TARGET_FIELD = 'target'