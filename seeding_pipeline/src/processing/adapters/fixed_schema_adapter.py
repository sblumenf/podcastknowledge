"""
Fixed schema adapter implementing the extraction interface.

This adapter wraps the existing KnowledgeExtractor to conform to the
unified extraction interface.
"""

from typing import List, Dict, Any, Optional
import logging

from ...core.extraction_interface import (
    ExtractionInterface, Segment, Entity, Relationship, 
    Quote, Insight
)
from ..extraction import KnowledgeExtractor


logger = logging.getLogger(__name__)


class FixedSchemaAdapter:
    """
    Adapter for fixed schema extraction mode.
    
    Wraps the existing KnowledgeExtractor to implement the unified
    extraction interface protocol.
    """
    
    def __init__(self, knowledge_extractor: KnowledgeExtractor):
        """
        Initialize the adapter with a KnowledgeExtractor instance.
        
        Args:
            knowledge_extractor: The existing KnowledgeExtractor to wrap
        """
        self.extractor = knowledge_extractor
        self._extraction_mode = "fixed"
        
    def extract_entities(self, segment: Segment) -> List[Entity]:
        """Extract entities using fixed schema."""
        # Convert segment to format expected by KnowledgeExtractor
        segment_dict = {
            'text': segment.text,
            'start': segment.start,
            'end': segment.end,
            'speaker': segment.speaker or 'Unknown'
        }
        
        # Extract knowledge using existing extractor
        result = self.extractor.extract_knowledge(segment_dict)
        
        # Convert to Entity objects
        entities = []
        for entity_data in result.get('entities', []):
            entity = Entity(
                name=entity_data.get('name'),
                type=entity_data.get('type'),
                description=entity_data.get('description'),
                confidence=entity_data.get('confidence', 0.8),
                properties=entity_data.get('properties', {})
            )
            entities.append(entity)
            
        return entities
    
    def extract_relationships(self, segment: Segment) -> List[Relationship]:
        """Extract relationships using fixed schema."""
        segment_dict = {
            'text': segment.text,
            'start': segment.start,
            'end': segment.end,
            'speaker': segment.speaker or 'Unknown'
        }
        
        result = self.extractor.extract_knowledge(segment_dict)
        
        # Convert to Relationship objects
        relationships = []
        for rel_data in result.get('relationships', []):
            relationship = Relationship(
                source=rel_data.get('source'),
                target=rel_data.get('target'),
                type=rel_data.get('type'),
                confidence=rel_data.get('confidence', 0.75),
                properties=rel_data.get('properties', {})
            )
            relationships.append(relationship)
            
        return relationships
    
    def extract_quotes(self, segment: Segment) -> List[Quote]:
        """Extract quotes using fixed schema."""
        segment_dict = {
            'text': segment.text,
            'start': segment.start,
            'end': segment.end,
            'speaker': segment.speaker or 'Unknown'
        }
        
        result = self.extractor.extract_knowledge(segment_dict)
        
        # Convert quotes if present
        quotes = []
        for quote_data in result.get('quotes', []):
            quote = Quote(
                text=quote_data.get('text'),
                speaker=quote_data.get('speaker', segment.speaker or 'Unknown'),
                timestamp=segment.start,
                context=quote_data.get('context'),
                confidence=quote_data.get('confidence', 0.8)
            )
            quotes.append(quote)
            
        return quotes
    
    def extract_insights(self, segment: Segment) -> List[Insight]:
        """Extract insights using fixed schema."""
        segment_dict = {
            'text': segment.text,
            'start': segment.start,
            'end': segment.end,
            'speaker': segment.speaker or 'Unknown'
        }
        
        result = self.extractor.extract_knowledge(segment_dict)
        
        # Convert insights
        insights = []
        for insight_data in result.get('insights', []):
            insight = Insight(
                content=insight_data.get('content'),
                speaker=insight_data.get('speaker'),
                confidence=insight_data.get('confidence', 0.8),
                category=insight_data.get('category')
            )
            insights.append(insight)
            
        return insights
    
    def extract_all(self, segment: Segment) -> Dict[str, Any]:
        """Extract all information from a segment."""
        segment_dict = {
            'text': segment.text,
            'start': segment.start,
            'end': segment.end,
            'speaker': segment.speaker or 'Unknown'
        }
        
        # Get raw extraction result
        result = self.extractor.extract_knowledge(segment_dict)
        
        # Convert to standardized format
        return {
            'entities': self.extract_entities(segment),
            'relationships': self.extract_relationships(segment),
            'quotes': self.extract_quotes(segment),
            'insights': self.extract_insights(segment),
            'metadata': {
                'themes': result.get('themes', []),
                'topics': result.get('topics', []),
                'extraction_mode': self._extraction_mode,
                'segment_duration': segment.end - segment.start
            }
        }
    
    def get_extraction_mode(self) -> str:
        """Get the extraction mode identifier."""
        return self._extraction_mode
    
    def get_discovered_types(self) -> Optional[List[str]]:
        """Fixed schema doesn't discover new types."""
        return None