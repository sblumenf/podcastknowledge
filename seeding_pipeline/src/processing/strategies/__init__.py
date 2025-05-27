"""
Extraction strategies for unified extraction interface.

This module defines the protocol and data structures for the extraction strategy pattern,
enabling seamless switching between fixed schema, schemaless, and dual mode extraction.
"""

from typing import Protocol, Dict, Any, List, Optional
from dataclasses import dataclass

from src.core.models import Segment, Entity, Insight, Quote


@dataclass
class ExtractedData:
    """Unified data structure for extraction results."""
    entities: List[Entity]
    relationships: List[Dict[str, Any]]
    quotes: List[Quote]
    insights: List[Insight]
    topics: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'entities': [e.__dict__ for e in self.entities],
            'relationships': self.relationships,
            'quotes': [q.__dict__ for q in self.quotes],
            'insights': [i.__dict__ for i in self.insights],
            'topics': self.topics,
            'metadata': self.metadata
        }


class ExtractionStrategy(Protocol):
    """Protocol defining the interface for extraction strategies."""
    
    def extract(self, segment: Segment) -> ExtractedData:
        """
        Extract knowledge from a segment using the strategy's approach.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            ExtractedData containing all extracted information
        """
        ...
    
    def get_extraction_mode(self) -> str:
        """
        Get the extraction mode identifier.
        
        Returns:
            Mode identifier: 'fixed', 'schemaless', or 'dual'
        """
        ...


# Re-export for convenient imports
__all__ = ['ExtractionStrategy', 'ExtractedData']