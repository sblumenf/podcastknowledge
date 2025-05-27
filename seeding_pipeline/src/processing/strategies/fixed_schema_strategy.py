"""
Fixed schema extraction strategy implementation.

This strategy wraps the existing KnowledgeExtractor to maintain backward compatibility
while conforming to the unified ExtractionStrategy interface.
"""

import logging
from typing import Dict, Any, Optional

from src.processing.strategies import ExtractedData
from src.processing.extraction import KnowledgeExtractor, ExtractionResult
from src.core.models import Segment
from src.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)


class FixedSchemaStrategy:
    """
    Extraction strategy using fixed schema approach.
    
    This strategy wraps the existing KnowledgeExtractor to provide
    backward compatibility while implementing the ExtractionStrategy protocol.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        use_large_context: bool = True,
        max_retries: int = 3,
        enable_cache: bool = True
    ):
        """
        Initialize fixed schema strategy.
        
        Args:
            llm_provider: LLM provider for extraction
            use_large_context: Whether to use large context prompts
            max_retries: Maximum retries for failed extractions
            enable_cache: Whether to enable result caching
        """
        self.extractor = KnowledgeExtractor(
            llm_provider=llm_provider,
            use_large_context=use_large_context,
            max_retries=max_retries,
            enable_cache=enable_cache
        )
        logger.info("Initialized FixedSchemaStrategy")
    
    def extract(self, segment: Segment) -> ExtractedData:
        """
        Extract knowledge from a segment using fixed schema approach.
        
        Args:
            segment: The transcript segment to process
            
        Returns:
            ExtractedData containing all extracted information
        """
        # Build context from segment metadata
        context = {
            'segment_id': segment.id,
            'episode_id': segment.episode_id,
            'speaker': segment.speaker,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'segment_index': segment.segment_index
        }
        
        # Use existing extractor
        extraction_result: ExtractionResult = self.extractor.extract_all(
            text=segment.text,
            context=context
        )
        
        # Convert ExtractionResult to ExtractedData
        # Note: Fixed schema doesn't extract relationships separately
        relationships = []
        
        # Add segment metadata to extraction metadata
        metadata = extraction_result.metadata.copy()
        metadata['segment_metadata'] = context
        metadata['extraction_mode'] = 'fixed'
        
        return ExtractedData(
            entities=extraction_result.entities,
            relationships=relationships,
            quotes=extraction_result.quotes,
            insights=extraction_result.insights,
            topics=extraction_result.topics,
            metadata=metadata
        )
    
    def get_extraction_mode(self) -> str:
        """
        Get the extraction mode identifier.
        
        Returns:
            'fixed' - indicating fixed schema extraction
        """
        return 'fixed'


__all__ = ['FixedSchemaStrategy']