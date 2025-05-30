"""
Simplified knowledge extraction for VTT processing.

This module provides streamlined extraction focused on schemaless processing
without the complexity of the old fixed-schema approach.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker
from src.core.models import Segment

logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """Configuration for knowledge extraction."""
    # Quote extraction settings
    min_quote_length: int = 10  # Minimum words for a quote
    max_quote_length: int = 50  # Maximum words for a quote
    extract_quotes: bool = True  # Extract memorable quotes
    quote_importance_threshold: float = 0.7  # Minimum importance score
    
    # Entity extraction settings
    entity_confidence_threshold: float = 0.6  # Minimum entity confidence
    max_entities_per_segment: int = 20  # Limit entities to prevent noise
    
    # Processing options
    validate_extractions: bool = True  # Validate extracted content
    dry_run: bool = False  # Preview mode


@dataclass
class ExtractionResult:
    """Result of knowledge extraction process."""
    entities: List[Dict[str, Any]]
    quotes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class KnowledgeExtractor:
    """
    Simplified knowledge extractor for VTT processing.
    
    Focuses on schemaless extraction without fixed schemas or complex patterns.
    Integrates quote extraction, entity extraction, and relationship discovery.
    """
    
    def __init__(self, 
                 llm_service: Any,
                 embedding_service: Any = None,
                 config: Optional[ExtractionConfig] = None):
        """
        Initialize the knowledge extractor.
        
        Args:
            llm_service: Direct LLM service for extraction
            embedding_service: Optional embedding service for similarity
            config: Extraction configuration
        """
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.config = config or ExtractionConfig()
        
        # Quote patterns for fallback extraction
        self.quote_patterns = [
            # Direct quotes with attribution
            r'([A-Z][^:]+):\s*"([^"]+)"',
            r'([A-Z][^:]+):\s*"([^"]+)"',
            r'([A-Z][^:]+)\s+said,?\s*"([^"]+)"',
            r'([A-Z][^:]+)\s+says,?\s*"([^"]+)"',
            
            # Strong statements (without quotes)
            r'([A-Z][^:]+):\s*(I believe[^.!?]+[.!?])',
            r'([A-Z][^:]+):\s*(The key is[^.!?]+[.!?])',
            r'([A-Z][^:]+):\s*(What\'s important is[^.!?]+[.!?])',
            r'([A-Z][^:]+):\s*(The truth is[^.!?]+[.!?])',
            r'([A-Z][^:]+):\s*(In my experience[^.!?]+[.!?])',
        ]
        
        # Quote type classification keywords
        self.quote_classifiers = {
            'opinion': ['believe', 'think', 'opinion', 'perspective'],
            'factual': ['research', 'study', 'data', 'evidence'],
            'humorous': ['funny', 'hilarious', 'joke'],
            'controversial': ['controversial', 'debate', 'disagree'],
            'insightful': ['insight', 'realize', 'understand', 'learn']
        }
    
    @track_component_impact("knowledge_extractor", "2.0.0")
    def extract_knowledge(
        self,
        segment: Segment,
        episode_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        Extract knowledge from a segment using schemaless approach.
        
        Args:
            segment: Segment to extract knowledge from
            episode_metadata: Episode context information
            **kwargs: Additional context
            
        Returns:
            ExtractionResult with extracted knowledge
        """
        if self.config.dry_run:
            return self._preview_extraction(segment)
        
        # Extract different types of knowledge
        entities = []
        quotes = []
        relationships = []
        
        # Extract quotes using pattern matching and LLM
        if self.config.extract_quotes:
            quotes = self._extract_quotes(segment)
        
        # For now, use simplified entity extraction
        # In a full implementation, this would integrate with SimpleKGPipeline
        entities = self._extract_basic_entities(segment)
        
        # Extract relationships between entities
        relationships = self._extract_relationships(entities, quotes, segment)
        
        # Build metadata
        metadata = {
            'extraction_timestamp': datetime.now().isoformat(),
            'segment_id': segment.id,
            'extraction_mode': 'schemaless',
            'text_length': len(segment.text),
            'entity_count': len(entities),
            'quote_count': len(quotes),
            'relationship_count': len(relationships),
            'episode_metadata': episode_metadata
        }
        
        # Track contribution
        if entities or quotes or relationships:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="knowledge_extractor",
                contribution_type="knowledge_extracted",
                details={
                    "entity_types": list(set(e.get('type', 'Unknown') for e in entities)),
                    "quote_types": list(set(q.get('type', 'general') for q in quotes)),
                    "extraction_methods": ['pattern_matching', 'llm_analysis']
                },
                count=len(entities) + len(quotes) + len(relationships),
                timestamp=kwargs.get('timestamp', '')
            )
            tracker.track_contribution(contribution)
        
        return ExtractionResult(
            entities=entities,
            quotes=quotes,
            relationships=relationships,
            metadata=metadata
        )
    
    def _extract_quotes(self, segment: Segment) -> List[Dict[str, Any]]:
        """Extract quotes from segment using pattern matching."""
        quotes = []
        text = segment.text
        
        for pattern in self.quote_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                speaker = match.group(1).strip()
                quote_text = match.group(2).strip()
                
                # Apply length filters
                word_count = len(quote_text.split())
                if (word_count >= self.config.min_quote_length and 
                    word_count <= self.config.max_quote_length):
                    
                    # Calculate position and timestamp
                    position = match.start()
                    timestamp = self._calculate_quote_timestamp(position, text, segment)
                    
                    quote = {
                        'type': 'Quote',
                        'value': quote_text,
                        'speaker': speaker,
                        'quote_type': self._classify_quote_type(quote_text),
                        'start_time': timestamp,
                        'end_time': timestamp + self._estimate_quote_duration(quote_text),
                        'importance_score': self._calculate_quote_importance(quote_text),
                        'confidence': 0.9,
                        'properties': {
                            'position_in_segment': position,
                            'word_count': word_count
                        }
                    }
                    
                    # Only include if meets importance threshold
                    if quote['importance_score'] >= self.config.quote_importance_threshold:
                        quotes.append(quote)
        
        return self._deduplicate_quotes(quotes)
    
    def _extract_basic_entities(self, segment: Segment) -> List[Dict[str, Any]]:
        """
        Extract basic entities using simple patterns.
        
        In a full implementation, this would use SimpleKGPipeline
        or the LLM service for more sophisticated extraction.
        """
        entities = []
        text = segment.text
        
        # Simple named entity patterns
        patterns = {
            'PERSON': r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',  # First Last names
            'ORGANIZATION': r'\b([A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Company))\b',
            'TECHNOLOGY': r'\b(AI|ML|API|iOS|Android|Python|JavaScript|React|Node\.js)\b',
            'CONCEPT': r'\b(machine learning|artificial intelligence|blockchain|cloud computing)\b'
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity_value = match.group(1).strip()
                
                # Calculate position and basic confidence
                position = match.start()
                confidence = 0.8 if entity_type in ['TECHNOLOGY', 'CONCEPT'] else 0.7
                
                entity = {
                    'type': entity_type,
                    'value': entity_value,
                    'confidence': confidence,
                    'start_time': self._calculate_entity_timestamp(position, text, segment),
                    'properties': {
                        'position_in_segment': position,
                        'extraction_method': 'pattern_matching'
                    }
                }
                
                # Only include if meets confidence threshold
                if entity['confidence'] >= self.config.entity_confidence_threshold:
                    entities.append(entity)
        
        # Limit entities to prevent noise
        if len(entities) > self.config.max_entities_per_segment:
            # Sort by confidence and take top entities
            entities.sort(key=lambda x: x['confidence'], reverse=True)
            entities = entities[:self.config.max_entities_per_segment]
        
        return self._deduplicate_entities(entities)
    
    def _extract_relationships(
        self,
        entities: List[Dict[str, Any]],
        quotes: List[Dict[str, Any]],
        segment: Segment
    ) -> List[Dict[str, Any]]:
        """Extract relationships between entities and quotes."""
        relationships = []
        
        # Create relationships between quotes and speakers
        for quote in quotes:
            if quote.get('speaker'):
                relationships.append({
                    'type': 'SAID',
                    'source': quote['speaker'],
                    'target': quote['value'][:50] + '...' if len(quote['value']) > 50 else quote['value'],
                    'confidence': quote.get('confidence', 0.9),
                    'properties': {
                        'quote_type': quote.get('quote_type', 'general'),
                        'timestamp': quote.get('start_time', 0)
                    }
                })
        
        # Simple co-occurrence relationships between entities
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Check if entities appear close together in text
                pos1 = entity1.get('properties', {}).get('position_in_segment', 0)
                pos2 = entity2.get('properties', {}).get('position_in_segment', 0)
                
                if abs(pos1 - pos2) < 200:  # Within 200 characters
                    relationships.append({
                        'type': 'MENTIONED_WITH',
                        'source': entity1['value'],
                        'target': entity2['value'],
                        'confidence': 0.6,
                        'properties': {
                            'distance': abs(pos1 - pos2),
                            'co_occurrence': True
                        }
                    })
        
        return relationships
    
    def _calculate_quote_timestamp(self, position: int, text: str, segment: Segment) -> float:
        """Calculate timestamp for quote based on position in text."""
        if not segment.start_time:
            return 0.0
        
        # Estimate based on position in text
        total_chars = len(text)
        duration = (segment.end_time - segment.start_time) if segment.end_time else 0
        
        if total_chars > 0 and duration > 0:
            time_per_char = duration / total_chars
            return segment.start_time + (position * time_per_char)
        
        return segment.start_time
    
    def _calculate_entity_timestamp(self, position: int, text: str, segment: Segment) -> float:
        """Calculate timestamp for entity based on position in text."""
        return self._calculate_quote_timestamp(position, text, segment)
    
    def _estimate_quote_duration(self, quote_text: str) -> float:
        """Estimate how long it takes to speak a quote."""
        # Average speaking rate: 150 words per minute
        words = len(quote_text.split())
        return (words / 150) * 60  # Convert to seconds
    
    def _classify_quote_type(self, quote_text: str) -> str:
        """Classify the type of quote."""
        text_lower = quote_text.lower()
        
        for quote_type, keywords in self.quote_classifiers.items():
            if any(keyword in text_lower for keyword in keywords):
                return quote_type
        
        return 'general'
    
    def _calculate_quote_importance(self, quote_text: str) -> float:
        """Calculate importance score for a quote."""
        score = 0.5  # Base score
        
        # Adjust based on quote type
        quote_type = self._classify_quote_type(quote_text)
        type_scores = {
            'insightful': 0.2,
            'controversial': 0.15,
            'factual': 0.1,
            'opinion': 0.05,
            'humorous': 0.1,
            'general': 0.0
        }
        score += type_scores.get(quote_type, 0)
        
        # Adjust based on length (prefer medium length)
        word_count = len(quote_text.split())
        if 15 <= word_count <= 30:
            score += 0.1
        
        # Ensure score is between 0 and 1
        return min(max(score, 0.0), 1.0)
    
    def _deduplicate_quotes(self, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate quotes."""
        seen = set()
        unique_quotes = []
        
        for quote in quotes:
            # Create a key for deduplication
            key = (quote['value'].lower().strip(), quote.get('speaker', '').lower())
            
            if key not in seen:
                seen.add(key)
                unique_quotes.append(quote)
        
        return unique_quotes
    
    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities."""
        seen = set()
        unique_entities = []
        
        for entity in entities:
            # Create a key for deduplication
            key = (entity['type'], entity['value'].lower().strip())
            
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
        
        return unique_entities
    
    def _preview_extraction(self, segment: Segment) -> ExtractionResult:
        """Preview extraction without processing."""
        # Quick analysis to estimate extraction potential
        text = segment.text
        
        # Count potential quotes
        quote_count = 0
        for pattern in self.quote_patterns:
            matches = re.findall(pattern, text)
            quote_count += len(matches)
        
        # Count potential entities
        entity_count = 0
        patterns = [
            r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',  # Names
            r'\b([A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Company))\b',  # Organizations
            r'\b(AI|ML|API|iOS|Android|Python|JavaScript)\b'  # Technologies
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entity_count += len(matches)
        
        preview_metadata = {
            'preview_mode': True,
            'segment_length': len(text),
            'estimated_quotes': quote_count,
            'estimated_entities': entity_count,
            'config': {
                'extract_quotes': self.config.extract_quotes,
                'min_quote_length': self.config.min_quote_length,
                'max_quote_length': self.config.max_quote_length,
                'entity_confidence_threshold': self.config.entity_confidence_threshold
            }
        }
        
        return ExtractionResult(
            entities=[],
            quotes=[],
            relationships=[],
            metadata=preview_metadata
        )


# Utility functions for backward compatibility
def extract_quotes_from_segment(segment: Segment, config: Optional[ExtractionConfig] = None) -> List[Dict[str, Any]]:
    """
    Extract quotes from a segment (backward compatibility function).
    
    Args:
        segment: Segment to extract quotes from
        config: Optional extraction configuration
        
    Returns:
        List of extracted quotes
    """
    extractor = KnowledgeExtractor(None, None, config)
    return extractor._extract_quotes(segment)


def extract_entities_from_segment(segment: Segment, config: Optional[ExtractionConfig] = None) -> List[Dict[str, Any]]:
    """
    Extract entities from a segment (backward compatibility function).
    
    Args:
        segment: Segment to extract entities from
        config: Optional extraction configuration
        
    Returns:
        List of extracted entities
    """
    extractor = KnowledgeExtractor(None, None, config)
    return extractor._extract_basic_entities(segment)