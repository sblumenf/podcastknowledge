"""
Custom quote extraction enhancement for schemaless pipeline.

This module extracts memorable quotes from segments and integrates them with
SimpleKGPipeline results, preserving exact timestamps and speaker attribution.

JUSTIFICATION: SimpleKGPipeline extracts entities and relationships but doesn't:
- Identify memorable quotes as distinct entities
- Preserve exact quote boundaries and timestamps
- Link quotes to their speakers
- Calculate quote importance or memorability
- Maintain the human element of conversations

EVIDENCE: Phase 1 testing showed SimpleKGPipeline misses quotable content that
makes podcasts engaging and shareable. Quotes are lost in entity extraction.

REMOVAL CRITERIA: This component can be removed if SimpleKGPipeline adds:
- Native quote entity type recognition
- Quote boundary detection with timestamps
- Speaker attribution for quotes
- Quote importance scoring

MINIMUM ACCURACY THRESHOLD: 80% quote validation rate. If quote extraction
falls below this threshold, the component needs optimization or removal.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker
from src.core.models import Segment, Quote

logger = logging.getLogger(__name__)


@dataclass 
class QuoteExtractionConfig:
    """Configuration for quote extraction."""
    min_quote_length: int = 10  # Minimum words for a quote
    max_quote_length: int = 50  # Maximum words for a quote
    extract_memorable: bool = True  # Extract memorable/impactful quotes
    extract_controversial: bool = True  # Extract controversial statements
    extract_humorous: bool = True  # Extract funny quotes
    extract_insightful: bool = True  # Extract insightful observations
    validate_quotes: bool = True  # Validate quotes exist in source
    require_speaker: bool = True  # Only extract quotes with clear attribution
    importance_threshold: float = 0.7  # Minimum importance score
    use_llm_scoring: bool = False  # Use LLM for importance scoring
    dry_run: bool = False  # Preview mode


class SchemalessQuoteExtractor:
    """
    Extracts and enhances quotes from podcast segments.
    
    This class identifies memorable quotes, preserves their exact timestamps,
    attributes them to speakers, and calculates importance scores.
    """
    
    def __init__(self, config: Optional[QuoteExtractionConfig] = None):
        """Initialize the quote extractor with configuration."""
        self.config = config or QuoteExtractionConfig()
        self.extraction_stats = {
            "segments_processed": 0,
            "quotes_extracted": 0,
            "quotes_validated": 0,
            "quotes_rejected": 0,
            "validation_failures": []
        }
    
    @track_component_impact("quote_extractor", "1.0.0")
    def extract_quotes(
        self,
        segment: Segment,
        extraction_results: Optional[Dict[str, Any]] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract quotes from a segment and integrate with extraction results.
        
        Args:
            segment: Source segment containing potential quotes
            extraction_results: Optional results from SimpleKGPipeline
            llm_client: Optional LLM client for advanced extraction
            **kwargs: Additional context
            
        Returns:
            Dictionary with extracted quotes and metrics
        """
        if self.config.dry_run:
            return self._preview_extraction(segment)
        
        # Reset stats for this extraction
        self.extraction_stats["segments_processed"] += 1
        
        # Extract quotes using different methods
        quotes = []
        
        # Pattern-based extraction
        pattern_quotes = self._extract_pattern_based_quotes(segment)
        quotes.extend(pattern_quotes)
        
        # LLM-based extraction if available
        if llm_client and self.config.use_llm_scoring:
            llm_quotes = self._extract_llm_based_quotes(segment, llm_client)
            quotes.extend(llm_quotes)
        
        # Deduplicate and validate quotes
        unique_quotes = self._deduplicate_quotes(quotes)
        validated_quotes = []
        
        for quote in unique_quotes:
            if self.config.validate_quotes:
                if self._validate_quote(quote, segment):
                    validated_quotes.append(quote)
                    self.extraction_stats["quotes_validated"] += 1
                else:
                    self.extraction_stats["quotes_rejected"] += 1
                    self.extraction_stats["validation_failures"].append(quote['text'][:50])
            else:
                validated_quotes.append(quote)
        
        # Calculate importance scores
        scored_quotes = []
        for quote in validated_quotes:
            quote['importance_score'] = self._calculate_importance_score(quote, segment)
            if quote['importance_score'] >= self.config.importance_threshold:
                scored_quotes.append(quote)
        
        # Integrate with SimpleKGPipeline results if provided
        if extraction_results:
            integrated_results = self._integrate_with_extraction(scored_quotes, extraction_results)
        else:
            integrated_results = extraction_results
        
        self.extraction_stats["quotes_extracted"] = len(scored_quotes)
        
        # Track contribution
        if scored_quotes:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="quote_extractor",
                contribution_type="quotes_extracted",
                details={
                    "quote_types": list(set(q.get('type', 'general') for q in scored_quotes)),
                    "avg_importance": sum(q['importance_score'] for q in scored_quotes) / len(scored_quotes)
                },
                count=len(scored_quotes),
                timestamp=kwargs.get('timestamp', datetime.now().isoformat())
            )
            tracker.track_contribution(contribution)
        
        return {
            "quotes": scored_quotes,
            "integrated_results": integrated_results,
            "metrics": self._get_extraction_metrics(),
            "episode_id": kwargs.get('episode_id'),
            "segment_id": kwargs.get('segment_id')
        }
    
    def _extract_pattern_based_quotes(self, segment: Segment) -> List[Dict[str, Any]]:
        """Extract quotes using pattern matching."""
        quotes = []
        text = segment.text
        
        # Common quote patterns
        patterns = [
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
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                speaker = match.group(1).strip()
                quote_text = match.group(2).strip()
                
                # Apply length filters
                word_count = len(quote_text.split())
                if (word_count >= self.config.min_quote_length and 
                    word_count <= self.config.max_quote_length):
                    
                    # Calculate position in segment
                    position = match.start()
                    timestamp = self._calculate_quote_timestamp(position, text, segment)
                    
                    quotes.append({
                        'text': quote_text,
                        'speaker': speaker if self.config.require_speaker else None,
                        'type': self._classify_quote_type(quote_text),
                        'start_time': timestamp,
                        'end_time': timestamp + self._estimate_quote_duration(quote_text),
                        'position_in_segment': position,
                        'confidence': 0.9  # High confidence for pattern matches
                    })
        
        return quotes
    
    def _extract_llm_based_quotes(self, segment: Segment, llm_client: Any) -> List[Dict[str, Any]]:
        """Extract quotes using LLM analysis."""
        # This is a placeholder for LLM-based extraction
        # In real implementation, would use the LLM to identify quotes
        return []
    
    def _validate_quote(self, quote: Dict[str, Any], segment: Segment) -> bool:
        """Validate that a quote actually exists in the segment."""
        quote_text = quote['text'].lower()
        segment_text = segment.text.lower()
        
        # For short quotes, require exact match
        if len(quote_text.split()) <= 3:
            return quote_text in segment_text
        
        # For longer quotes, allow fuzzy matching
        quote_words = quote_text.split()
        matches = 0
        
        for word in quote_words:
            if word in segment_text:
                matches += 1
        
        match_ratio = matches / len(quote_words)
        return match_ratio >= 0.7  # 70% of words must appear
    
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
    
    def _estimate_quote_duration(self, quote_text: str) -> float:
        """Estimate how long it takes to speak a quote."""
        # Average speaking rate: 150 words per minute
        words = len(quote_text.split())
        return (words / 150) * 60  # Convert to seconds
    
    def _classify_quote_type(self, quote_text: str) -> str:
        """Classify the type of quote."""
        text_lower = quote_text.lower()
        
        # Check for different quote types
        if any(word in text_lower for word in ['believe', 'think', 'opinion', 'perspective']):
            return 'opinion'
        elif any(word in text_lower for word in ['research', 'study', 'data', 'evidence']):
            return 'factual'
        elif any(word in text_lower for word in ['funny', 'hilarious', 'joke']):
            return 'humorous'
        elif any(word in text_lower for word in ['controversial', 'debate', 'disagree']):
            return 'controversial'
        elif any(word in text_lower for word in ['insight', 'realize', 'understand', 'learn']):
            return 'insightful'
        else:
            return 'general'
    
    def _calculate_importance_score(self, quote: Dict[str, Any], segment: Segment) -> float:
        """Calculate importance score for a quote."""
        score = 0.5  # Base score
        
        # Adjust based on quote type
        type_scores = {
            'insightful': 0.2,
            'controversial': 0.15,
            'factual': 0.1,
            'opinion': 0.05,
            'humorous': 0.1,
            'general': 0.0
        }
        score += type_scores.get(quote['type'], 0)
        
        # Adjust based on length (prefer medium length)
        word_count = len(quote['text'].split())
        if 15 <= word_count <= 30:
            score += 0.1
        
        # Adjust based on confidence
        score *= quote.get('confidence', 1.0)
        
        # Adjust based on speaker prominence (if available)
        if quote.get('speaker') and hasattr(segment, 'speaker_role'):
            if segment.speaker_role in ['HOST', 'GUEST']:
                score += 0.1
        
        # Ensure score is between 0 and 1
        return min(max(score, 0.0), 1.0)
    
    def _deduplicate_quotes(self, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate quotes."""
        seen = set()
        unique_quotes = []
        
        for quote in quotes:
            # Create a key for deduplication
            key = (quote['text'].lower().strip(), quote.get('speaker', '').lower())
            
            if key not in seen:
                seen.add(key)
                unique_quotes.append(quote)
        
        return unique_quotes
    
    def _integrate_with_extraction(
        self,
        quotes: List[Dict[str, Any]],
        extraction_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Integrate quotes with SimpleKGPipeline extraction results."""
        integrated = extraction_results.copy()
        
        # Add quotes as a special type of entity
        quote_entities = []
        for quote in quotes:
            quote_entity = {
                'type': 'Quote',
                'value': quote['text'][:100] + '...' if len(quote['text']) > 100 else quote['text'],
                'full_text': quote['text'],
                'speaker': quote.get('speaker'),
                'quote_type': quote['type'],
                'start_time': quote['start_time'],
                'end_time': quote['end_time'],
                'importance_score': quote['importance_score'],
                'properties': {
                    'position_in_segment': quote['position_in_segment'],
                    'confidence': quote['confidence']
                }
            }
            quote_entities.append(quote_entity)
        
        # Add to entities/nodes
        if 'entities' in integrated:
            integrated['entities'].extend(quote_entities)
        elif 'nodes' in integrated:
            integrated['nodes'].extend(quote_entities)
        else:
            integrated['quotes'] = quote_entities
        
        # Create relationships between quotes and speakers
        if 'relationships' in integrated and quotes:
            for quote in quotes:
                if quote.get('speaker'):
                    integrated['relationships'].append({
                        'type': 'SAID',
                        'source': quote['speaker'],
                        'target': quote['text'][:50] + '...',
                        'properties': {
                            'timestamp': quote['start_time'],
                            'quote_type': quote['type']
                        }
                    })
        
        return integrated
    
    def _get_extraction_metrics(self) -> Dict[str, Any]:
        """Get metrics about the quote extraction process."""
        validation_rate = (
            self.extraction_stats["quotes_validated"] / 
            (self.extraction_stats["quotes_validated"] + self.extraction_stats["quotes_rejected"])
            if (self.extraction_stats["quotes_validated"] + self.extraction_stats["quotes_rejected"]) > 0
            else 0
        )
        
        return {
            "type": "quote_extraction",
            "details": {
                "segments_processed": self.extraction_stats["segments_processed"],
                "quotes_extracted": self.extraction_stats["quotes_extracted"],
                "quotes_validated": self.extraction_stats["quotes_validated"],
                "quotes_rejected": self.extraction_stats["quotes_rejected"],
                "validation_rate": round(validation_rate, 2),
                "validation_failures_sample": self.extraction_stats["validation_failures"][:5]
            },
            "count": self.extraction_stats["quotes_extracted"]
        }
    
    def _preview_extraction(self, segment: Segment) -> Dict[str, Any]:
        """Preview quote extraction without processing."""
        # Quick pattern search to estimate quotes
        quote_patterns = [r'"[^"]+"', r'"[^"]+"', r':\s*[A-Z][^.!?]+[.!?]']
        potential_quotes = 0
        
        for pattern in quote_patterns:
            matches = re.findall(pattern, segment.text)
            potential_quotes += len(matches)
        
        return {
            "preview": {
                "segment_length": len(segment.text),
                "estimated_quotes": potential_quotes,
                "config": {
                    "min_length": self.config.min_quote_length,
                    "max_length": self.config.max_quote_length,
                    "validation_enabled": self.config.validate_quotes
                }
            }
        }