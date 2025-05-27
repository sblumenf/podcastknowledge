"""
Schemaless adapter implementing the extraction interface.

This adapter wraps schemaless extraction functionality to conform to the
unified extraction interface.
"""

from typing import List, Dict, Any, Optional, Set
import json
import logging

from ...core.extraction_interface import (
    ExtractionInterface, Segment, Entity, Relationship, 
    Quote, Insight
)


logger = logging.getLogger(__name__)


class SchemalessAdapter:
    """
    Adapter for schemaless extraction mode.
    
    Implements the unified extraction interface for schemaless extraction,
    allowing discovery of new entity types and relationships.
    """
    
    def __init__(self, llm_provider, embedding_provider=None):
        """
        Initialize the adapter with required providers.
        
        Args:
            llm_provider: The LLM provider for extraction
            embedding_provider: Optional embedding provider
        """
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self._extraction_mode = "schemaless"
        self._discovered_types: Set[str] = set()
        
    def extract_entities(self, segment: Segment) -> List[Entity]:
        """Extract entities without fixed schema constraints."""
        prompt = self._build_entity_prompt(segment)
        
        try:
            response = self.llm_provider.generate(prompt)
            result = json.loads(response)
            
            entities = []
            for entity_data in result.get('entities', []):
                entity_type = entity_data.get('type', 'Unknown')
                self._discovered_types.add(entity_type)
                
                entity = Entity(
                    name=entity_data.get('name'),
                    type=entity_type,
                    description=entity_data.get('description'),
                    confidence=entity_data.get('confidence', 0.7),
                    properties=entity_data.get('properties', {})
                )
                entities.append(entity)
                
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def extract_relationships(self, segment: Segment) -> List[Relationship]:
        """Extract relationships without fixed schema constraints."""
        # First extract entities to understand context
        entities = self.extract_entities(segment)
        entity_names = [e.name for e in entities]
        
        prompt = self._build_relationship_prompt(segment, entity_names)
        
        try:
            response = self.llm_provider.generate(prompt)
            result = json.loads(response)
            
            relationships = []
            for rel_data in result.get('relationships', []):
                relationship = Relationship(
                    source=rel_data.get('source'),
                    target=rel_data.get('target'),
                    type=rel_data.get('type', 'RELATES_TO'),
                    confidence=rel_data.get('confidence', 0.7),
                    properties=rel_data.get('properties', {})
                )
                relationships.append(relationship)
                
            return relationships
            
        except Exception as e:
            logger.error(f"Error extracting relationships: {e}")
            return []
    
    def extract_quotes(self, segment: Segment) -> List[Quote]:
        """Extract notable quotes from the segment."""
        prompt = self._build_quotes_prompt(segment)
        
        try:
            response = self.llm_provider.generate(prompt)
            result = json.loads(response)
            
            quotes = []
            for quote_data in result.get('quotes', []):
                quote = Quote(
                    text=quote_data.get('text'),
                    speaker=quote_data.get('speaker', segment.speaker or 'Unknown'),
                    timestamp=segment.start,
                    context=quote_data.get('context'),
                    confidence=quote_data.get('confidence', 0.7)
                )
                quotes.append(quote)
                
            return quotes
            
        except Exception as e:
            logger.error(f"Error extracting quotes: {e}")
            return []
    
    def extract_insights(self, segment: Segment) -> List[Insight]:
        """Extract insights (limited in schemaless mode)."""
        # Schemaless mode focuses on entities and relationships
        # but can still extract key observations
        prompt = self._build_insights_prompt(segment)
        
        try:
            response = self.llm_provider.generate(prompt)
            result = json.loads(response)
            
            insights = []
            for insight_data in result.get('insights', []):
                insight = Insight(
                    content=insight_data.get('content'),
                    speaker=insight_data.get('speaker'),
                    confidence=insight_data.get('confidence', 0.7),
                    category=insight_data.get('category', 'observation')
                )
                insights.append(insight)
                
            return insights
            
        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return []
    
    def extract_all(self, segment: Segment) -> Dict[str, Any]:
        """Extract all information from a segment."""
        # Extract all components
        entities = self.extract_entities(segment)
        relationships = self.extract_relationships(segment)
        quotes = self.extract_quotes(segment)
        insights = self.extract_insights(segment)
        
        return {
            'entities': entities,
            'relationships': relationships,
            'quotes': quotes,
            'insights': insights,
            'metadata': {
                'extraction_mode': self._extraction_mode,
                'discovered_types': list(self._discovered_types),
                'segment_duration': segment.end - segment.start,
                'entity_count': len(entities),
                'relationship_count': len(relationships)
            }
        }
    
    def get_extraction_mode(self) -> str:
        """Get the extraction mode identifier."""
        return self._extraction_mode
    
    def get_discovered_types(self) -> Optional[List[str]]:
        """Get discovered entity types."""
        return sorted(list(self._discovered_types))
    
    def _build_entity_prompt(self, segment: Segment) -> str:
        """Build prompt for entity extraction."""
        return f"""
Extract all entities from this transcript segment. Be creative and comprehensive in identifying entity types.
Do not limit yourself to traditional types like Person/Organization. Consider domain-specific entities.

Transcript segment:
Speaker: {segment.speaker or 'Unknown'}
Text: {segment.text}

Return JSON with this structure:
{{
    "entities": [
        {{
            "name": "entity name",
            "type": "specific entity type (be creative)",
            "description": "brief description",
            "confidence": 0.0-1.0,
            "properties": {{}}
        }}
    ]
}}

Examples of creative entity types: "AI Technology", "Research Method", "Industry Trend", "Technical Concept", "Business Model", etc.
"""
    
    def _build_relationship_prompt(self, segment: Segment, entity_names: List[str]) -> str:
        """Build prompt for relationship extraction."""
        return f"""
Extract relationships between entities in this transcript segment. Be specific about relationship types.

Known entities: {', '.join(entity_names)}

Transcript segment:
{segment.text}

Return JSON with this structure:
{{
    "relationships": [
        {{
            "source": "entity name",
            "target": "entity name",
            "type": "SPECIFIC_RELATIONSHIP_TYPE",
            "confidence": 0.0-1.0,
            "properties": {{}}
        }}
    ]
}}

Use descriptive relationship types like: INVENTED_BY, COMPETES_WITH, FUNDED_BY, RESEARCHES, etc.
"""
    
    def _build_quotes_prompt(self, segment: Segment) -> str:
        """Build prompt for quote extraction."""
        return f"""
Extract notable or insightful quotes from this transcript segment.

Transcript segment:
Speaker: {segment.speaker or 'Unknown'}
Text: {segment.text}

Return JSON with this structure:
{{
    "quotes": [
        {{
            "text": "exact quote text",
            "speaker": "speaker name",
            "context": "what makes this quote notable",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""
    
    def _build_insights_prompt(self, segment: Segment) -> str:
        """Build prompt for insight extraction."""
        return f"""
Extract key insights or observations from this transcript segment.

Transcript segment:
{segment.text}

Return JSON with this structure:
{{
    "insights": [
        {{
            "content": "key insight or observation",
            "speaker": "who made this observation (if clear)",
            "category": "type of insight",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""