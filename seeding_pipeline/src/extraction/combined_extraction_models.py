"""
Combined extraction models for optimized single-pass extraction.

This module defines the data models for the combined extraction approach
that extracts all knowledge types (entities, quotes, insights, relationships)
in a single LLM call per MeaningfulUnit.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class EntityType(str, Enum):
    """Entity types that can be discovered by the LLM."""
    # People & Organizations
    PERSON = "Person"
    COMPANY = "Company"
    INSTITUTION = "Institution"
    
    # Concepts & Ideas
    CONCEPT = "Concept"
    FRAMEWORK = "Framework"
    METHOD = "Method"
    THEORY = "Theory"
    
    # Technology & Products
    TECHNOLOGY = "Technology"
    PRODUCT = "Product"
    TOOL = "Tool"
    PLATFORM = "Platform"
    
    # Content & Media
    BOOK = "Book"
    STUDY = "Study"
    RESEARCH = "Research"
    ARTICLE = "Article"
    
    # Medical & Scientific
    MEDICATION = "Medication"
    CONDITION = "Condition"
    TREATMENT = "Treatment"
    BIOLOGICAL_PROCESS = "Biological_Process"
    CHEMICAL = "Chemical"
    
    # Other
    LOCATION = "Location"
    EVENT = "Event"
    OTHER = "Other"


class InsightType(str, Enum):
    """Types of insights that can be extracted."""
    ACTIONABLE = "actionable"  # Practical advice
    CONCEPTUAL = "conceptual"  # Theory, explanations
    EXPERIENTIAL = "experiential"  # Stories, examples
    PREDICTIVE = "predictive"  # Predictions, forecasts
    ANALYTICAL = "analytical"  # Analysis, comparisons


@dataclass
class ExtractedEntity:
    """Entity extracted from a MeaningfulUnit."""
    name: str
    type: str  # Can be any type, not limited to EntityType enum
    description: str
    importance: float  # 1-10 score
    frequency: int  # Number of mentions
    has_citation: bool
    context_snippet: Optional[str] = None  # Where it was mentioned


@dataclass
class ExtractedQuote:
    """Quote extracted from a MeaningfulUnit."""
    text: str
    speaker: str
    context: str
    is_memorable: bool
    theme: Optional[str] = None


@dataclass
class ExtractedInsight:
    """Insight extracted from a MeaningfulUnit."""
    title: str  # Brief 3-5 word title
    description: str  # One sentence description
    insight_type: InsightType
    confidence: float  # 1-10 score
    supporting_entities: List[str] = None  # Entity names that support this insight


@dataclass
class ExtractedRelationship:
    """Relationship between entities."""
    source_entity: str
    target_entity: str
    relationship_type: str  # e.g., "works_for", "created_by", "influences"
    description: str
    confidence: float  # 0-1 score
    evidence: Optional[str] = None  # Supporting evidence


@dataclass
class ConversationAnalysis:
    """Analysis of conversation structure within the unit."""
    topic_summary: str
    completeness: str  # "complete", "incomplete", "fragmented"
    key_themes: List[str]
    speaker_dynamics: Dict[str, str]  # speaker -> role description
    structural_notes: Optional[str] = None


@dataclass
class CombinedExtractionResult:
    """
    Combined result from single-pass extraction.
    
    This contains all knowledge extracted from a MeaningfulUnit
    in a single LLM call.
    """
    # Core extractions
    entities: List[ExtractedEntity]
    quotes: List[ExtractedQuote]
    insights: List[ExtractedInsight]
    relationships: List[ExtractedRelationship]
    
    # Conversation analysis
    conversation_analysis: ConversationAnalysis
    
    # Metadata
    unit_id: str
    extraction_timestamp: str
    token_count: Optional[int] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "unit_id": self.unit_id,
            "entities": [
                {
                    "name": e.name,
                    "type": e.type,
                    "description": e.description,
                    "importance": e.importance,
                    "frequency": e.frequency,
                    "has_citation": e.has_citation,
                    "context_snippet": e.context_snippet
                }
                for e in self.entities
            ],
            "quotes": [
                {
                    "text": q.text,
                    "speaker": q.speaker,
                    "context": q.context,
                    "is_memorable": q.is_memorable,
                    "theme": q.theme
                }
                for q in self.quotes
            ],
            "insights": [
                {
                    "title": i.title,
                    "description": i.description,
                    "insight_type": i.insight_type.value,
                    "confidence": i.confidence,
                    "supporting_entities": i.supporting_entities or []
                }
                for i in self.insights
            ],
            "relationships": [
                {
                    "source_entity": r.source_entity,
                    "target_entity": r.target_entity,
                    "relationship_type": r.relationship_type,
                    "description": r.description,
                    "confidence": r.confidence,
                    "evidence": r.evidence
                }
                for r in self.relationships
            ],
            "conversation_analysis": {
                "topic_summary": self.conversation_analysis.topic_summary,
                "completeness": self.conversation_analysis.completeness,
                "key_themes": self.conversation_analysis.key_themes,
                "speaker_dynamics": self.conversation_analysis.speaker_dynamics,
                "structural_notes": self.conversation_analysis.structural_notes
            },
            "extraction_timestamp": self.extraction_timestamp,
            "token_count": self.token_count,
            "processing_time": self.processing_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CombinedExtractionResult":
        """Create from dictionary."""
        return cls(
            unit_id=data["unit_id"],
            entities=[
                ExtractedEntity(**e) for e in data.get("entities", [])
            ],
            quotes=[
                ExtractedQuote(**q) for q in data.get("quotes", [])
            ],
            insights=[
                ExtractedInsight(
                    title=i["title"],
                    description=i["description"],
                    insight_type=InsightType(i["insight_type"]),
                    confidence=i["confidence"],
                    supporting_entities=i.get("supporting_entities")
                )
                for i in data.get("insights", [])
            ],
            relationships=[
                ExtractedRelationship(**r) for r in data.get("relationships", [])
            ],
            conversation_analysis=ConversationAnalysis(
                **data.get("conversation_analysis", {})
            ),
            extraction_timestamp=data["extraction_timestamp"],
            token_count=data.get("token_count"),
            processing_time=data.get("processing_time")
        )