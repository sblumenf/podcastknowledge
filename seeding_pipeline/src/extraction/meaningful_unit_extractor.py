"""
Knowledge extraction optimized for meaningful conversation units.

This module extends the base extraction to work with semantically coherent units
rather than individual segments, enabling better context understanding.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import logging
import time

from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig, ExtractionResult
from src.services.segment_regrouper import MeaningfulUnit
from src.services.performance_optimizer import PerformanceOptimizer
from src.core.interfaces import TranscriptSegment
from src.core.monitoring import trace_operation
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MeaningfulUnitExtractionResult:
    """Result of extracting knowledge from a meaningful unit."""
    
    unit_id: str
    entities: List[Dict[str, Any]]
    insights: List[Dict[str, Any]]
    quotes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    themes: List[str]
    metadata: Dict[str, Any]
    
    @property
    def total_extractions(self) -> int:
        """Total number of extracted items."""
        return len(self.entities) + len(self.insights) + len(self.quotes)


class MeaningfulUnitExtractor:
    """
    Extracts knowledge from meaningful conversation units.
    
    This extractor processes entire conversation units as cohesive blocks,
    providing better context for entity resolution, insight extraction, and
    relationship discovery.
    """
    
    def __init__(
        self,
        base_extractor: KnowledgeExtractor,
        config: Optional[ExtractionConfig] = None,
        performance_optimizer: Optional[PerformanceOptimizer] = None
    ):
        """
        Initialize the meaningful unit extractor.
        
        Args:
            base_extractor: Base knowledge extractor for segment processing
            config: Extraction configuration
            performance_optimizer: Optional performance optimizer for monitoring
        """
        self.base_extractor = base_extractor
        self.config = config or base_extractor.config
        self.logger = logger
        self.optimizer = performance_optimizer
        
    @trace_operation("extract_from_meaningful_unit")
    def extract_from_unit(
        self, 
        unit: MeaningfulUnit,
        episode_metadata: Optional[Dict[str, Any]] = None
    ) -> MeaningfulUnitExtractionResult:
        """
        Extract knowledge from a meaningful conversation unit.
        
        Args:
            unit: Meaningful unit containing related segments
            episode_metadata: Episode context information
            
        Returns:
            MeaningfulUnitExtractionResult with aggregated extractions
        """
        start_time = time.time()
        
        # Wrap with performance monitoring if optimizer available
        if self.optimizer:
            decorated_func = self.optimizer.measure_performance(f"unit_extraction_{unit.unit_type}")
            return decorated_func(self._do_extract_from_unit)(unit, episode_metadata)
        else:
            return self._do_extract_from_unit(unit, episode_metadata)
    
    def _do_extract_from_unit(
        self,
        unit: MeaningfulUnit,
        episode_metadata: Optional[Dict[str, Any]] = None
    ) -> MeaningfulUnitExtractionResult:
        """Internal method for unit extraction."""
        start_time = time.time()
        
        self.logger.info(
            f"Extracting from unit {unit.id} with {unit.segment_count} segments "
            f"({unit.duration:.1f}s duration)"
        )
        
        # Extract from all segments within the unit
        all_entities = []
        all_quotes = []
        all_relationships = []
        segment_metadata = []
        
        # Process segments in the unit
        for i, segment in enumerate(unit.segments):
            try:
                # Extract knowledge from segment with unit context
                result = self.base_extractor.extract_knowledge(
                    segment,
                    episode_metadata=episode_metadata,
                    unit_context={
                        'unit_id': unit.id,
                        'unit_type': unit.unit_type,
                        'unit_themes': unit.themes,
                        'segment_position': i,
                        'total_segments': unit.segment_count
                    }
                )
                
                # Collect results
                all_entities.extend(result.entities)
                all_quotes.extend(result.quotes)
                all_relationships.extend(result.relationships)
                segment_metadata.append(result.metadata)
                
            except Exception as e:
                self.logger.warning(
                    f"Failed to extract from segment {i} in unit {unit.id}: {e}"
                )
                continue
        
        # Post-process extractions at unit level
        processed_entities = self._process_unit_entities(all_entities, unit)
        processed_insights = self._extract_unit_insights(unit, all_entities, all_quotes)
        processed_quotes = self._process_unit_quotes(all_quotes, unit)
        processed_relationships = self._process_unit_relationships(
            all_relationships, processed_entities, unit
        )
        
        # Build unit-level metadata
        extraction_time = time.time() - start_time
        metadata = {
            'extraction_timestamp': datetime.now().isoformat(),
            'unit_id': unit.id,
            'unit_type': unit.unit_type,
            'extraction_mode': 'meaningful_unit',
            'segment_count': unit.segment_count,
            'unit_duration': unit.duration,
            'extraction_time': extraction_time,
            'entity_count': len(processed_entities),
            'insight_count': len(processed_insights),
            'quote_count': len(processed_quotes),
            'relationship_count': len(processed_relationships),
            'speaker_distribution': unit.speaker_distribution,
            'is_complete_unit': unit.is_complete,
            'segment_metadata': segment_metadata,
            'episode_metadata': episode_metadata
        }
        
        return MeaningfulUnitExtractionResult(
            unit_id=unit.id,
            entities=processed_entities,
            insights=processed_insights,
            quotes=processed_quotes,
            relationships=processed_relationships,
            themes=unit.themes,
            metadata=metadata
        )
    
    def _process_unit_entities(
        self, 
        entities: List[Dict[str, Any]], 
        unit: MeaningfulUnit
    ) -> List[Dict[str, Any]]:
        """
        Process and deduplicate entities at the unit level.
        
        Args:
            entities: Raw entities from all segments
            unit: The meaningful unit
            
        Returns:
            Processed and deduplicated entities
        """
        # Group entities by normalized name
        entity_groups = {}
        
        for entity in entities:
            # Create normalized key
            key = (
                entity.get('value', '').lower().strip(),
                entity.get('type', 'UNKNOWN')
            )
            
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)
        
        # Merge entity groups
        processed = []
        for (name, entity_type), group in entity_groups.items():
            # Merge confidence scores
            avg_confidence = sum(e.get('confidence', 0.5) for e in group) / len(group)
            
            # Find first and last occurrence
            start_times = [e.get('start_time', 0) for e in group if e.get('start_time')]
            
            merged_entity = {
                'type': entity_type,
                'value': group[0].get('value', name),  # Use original casing
                'entity_type': entity_type.lower(),
                'confidence': avg_confidence,
                'occurrences': len(group),
                'unit_id': unit.id,
                'first_occurrence': min(start_times) if start_times else unit.start_time,
                'properties': {
                    'extraction_method': 'meaningful_unit',
                    'unit_type': unit.unit_type,
                    'themes': unit.themes,
                    'merged_from': len(group)
                }
            }
            
            # Merge properties from all occurrences
            for entity in group:
                if 'description' in entity.get('properties', {}):
                    merged_entity['properties']['description'] = entity['properties']['description']
                    break
            
            processed.append(merged_entity)
        
        return processed
    
    def _extract_unit_insights(
        self,
        unit: MeaningfulUnit,
        entities: List[Dict[str, Any]],
        quotes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract high-level insights from the meaningful unit.
        
        Args:
            unit: The meaningful unit
            entities: Entities found in the unit
            quotes: Quotes found in the unit
            
        Returns:
            List of unit-level insights
        """
        insights = []
        
        # Generate insight based on unit type
        if unit.unit_type == "topic_discussion":
            # Create topic summary insight
            if entities:
                entity_names = [e['value'] for e in entities[:5]]  # Top 5 entities
                insights.append({
                    'type': 'SUMMARY',
                    'content': f"{unit.summary} Key concepts discussed: {', '.join(entity_names)}",
                    'confidence': 0.8,
                    'unit_id': unit.id,
                    'properties': {
                        'insight_type': 'topic_summary',
                        'themes': unit.themes,
                        'entity_count': len(entities)
                    }
                })
        
        elif unit.unit_type == "q&a_pair":
            # Extract Q&A insight
            if quotes:
                insights.append({
                    'type': 'KEY_POINT',
                    'content': f"Q&A Exchange: {unit.summary}",
                    'confidence': 0.85,
                    'unit_id': unit.id,
                    'properties': {
                        'insight_type': 'qa_exchange',
                        'speaker_distribution': unit.speaker_distribution
                    }
                })
        
        elif unit.unit_type == "story":
            # Extract narrative insight
            insights.append({
                'type': 'NARRATIVE',
                'content': f"Story/Example: {unit.summary}",
                'confidence': 0.75,
                'unit_id': unit.id,
                'properties': {
                    'insight_type': 'narrative',
                    'duration': unit.duration
                }
            })
        
        # Add insights about incomplete units
        if not unit.is_complete:
            insights.append({
                'type': 'META',
                'content': f"Note: This {unit.unit_type} may be incomplete - {unit.metadata.get('completeness_note', '')}",
                'confidence': 1.0,
                'unit_id': unit.id,
                'properties': {
                    'insight_type': 'data_quality',
                    'issue': 'incomplete_unit'
                }
            })
        
        # Add theme-based insights
        for theme in unit.themes[:2]:  # Top 2 themes
            insights.append({
                'type': 'THEME',
                'content': f"Theme explored: {theme}",
                'confidence': 0.7,
                'unit_id': unit.id,
                'properties': {
                    'insight_type': 'thematic',
                    'theme': theme
                }
            })
        
        return insights
    
    def _process_unit_quotes(
        self,
        quotes: List[Dict[str, Any]],
        unit: MeaningfulUnit
    ) -> List[Dict[str, Any]]:
        """
        Process and enhance quotes with unit context.
        
        Args:
            quotes: Raw quotes from segments
            unit: The meaningful unit
            
        Returns:
            Processed quotes with unit context
        """
        processed = []
        
        for quote in quotes:
            # Enhance quote with unit context
            enhanced_quote = quote.copy()
            enhanced_quote['unit_id'] = unit.id
            enhanced_quote['unit_type'] = unit.unit_type
            
            # Add context from unit summary
            if 'properties' not in enhanced_quote:
                enhanced_quote['properties'] = {}
            
            enhanced_quote['properties'].update({
                'unit_context': unit.summary,
                'unit_themes': unit.themes,
                'position_in_unit': self._calculate_quote_position(quote, unit)
            })
            
            # Boost importance for quotes in key unit types
            if unit.unit_type in ['conclusion', 'key_point']:
                current_importance = enhanced_quote.get('importance_score', 0.5)
                enhanced_quote['importance_score'] = min(current_importance + 0.2, 1.0)
            
            processed.append(enhanced_quote)
        
        return processed
    
    def _process_unit_relationships(
        self,
        relationships: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        unit: MeaningfulUnit
    ) -> List[Dict[str, Any]]:
        """
        Process relationships and add unit-level relationships.
        
        Args:
            relationships: Raw relationships from segments
            entities: Processed entities
            unit: The meaningful unit
            
        Returns:
            Enhanced relationships including unit-level connections
        """
        processed = relationships.copy()
        
        # Add unit context to existing relationships
        for rel in processed:
            rel['unit_id'] = unit.id
            if 'properties' not in rel:
                rel['properties'] = {}
            rel['properties']['unit_type'] = unit.unit_type
        
        # Create theme-entity relationships
        for theme in unit.themes:
            for entity in entities:
                if entity['occurrences'] >= 2:  # Only frequently mentioned entities
                    processed.append({
                        'type': 'RELATED_TO_THEME',
                        'source': entity['value'],
                        'target': theme,
                        'confidence': 0.7,
                        'unit_id': unit.id,
                        'properties': {
                            'relationship_level': 'unit',
                            'occurrences': entity['occurrences']
                        }
                    })
        
        # Create speaker-topic relationships for topic discussions
        if unit.unit_type == 'topic_discussion':
            for speaker, percentage in unit.speaker_distribution.items():
                if percentage > 30:  # Significant contribution
                    processed.append({
                        'type': 'DISCUSSES',
                        'source': speaker,
                        'target': unit.summary[:100],  # Truncated summary
                        'confidence': percentage / 100,
                        'unit_id': unit.id,
                        'properties': {
                            'contribution_percentage': percentage,
                            'unit_type': unit.unit_type
                        }
                    })
        
        return processed
    
    def _calculate_quote_position(
        self, 
        quote: Dict[str, Any], 
        unit: MeaningfulUnit
    ) -> str:
        """Calculate relative position of quote within unit."""
        quote_time = quote.get('start_time', 0)
        
        if not quote_time:
            return 'unknown'
        
        relative_position = (quote_time - unit.start_time) / unit.duration
        
        if relative_position < 0.25:
            return 'beginning'
        elif relative_position < 0.75:
            return 'middle'
        else:
            return 'end'
    
    @trace_operation("extract_from_units_batch")
    def extract_from_units_batch(
        self,
        units: List[MeaningfulUnit],
        episode_metadata: Optional[Dict[str, Any]] = None
    ) -> List[MeaningfulUnitExtractionResult]:
        """
        Extract knowledge from multiple meaningful units.
        
        Args:
            units: List of meaningful units to process
            episode_metadata: Episode context information
            
        Returns:
            List of extraction results
        """
        results = []
        
        self.logger.info(f"Extracting from {len(units)} meaningful units")
        
        for i, unit in enumerate(units):
            self.logger.debug(f"Processing unit {i+1}/{len(units)}: {unit.id}")
            
            try:
                result = self.extract_from_unit(unit, episode_metadata)
                results.append(result)
                
                # Log progress
                if (i + 1) % 10 == 0:
                    self.logger.info(
                        f"Processed {i+1}/{len(units)} units. "
                        f"Total extractions so far: "
                        f"{sum(r.total_extractions for r in results)}"
                    )
                    
            except Exception as e:
                self.logger.error(f"Failed to extract from unit {unit.id}: {e}")
                # Create minimal result for failed extraction
                results.append(MeaningfulUnitExtractionResult(
                    unit_id=unit.id,
                    entities=[],
                    insights=[],
                    quotes=[],
                    relationships=[],
                    themes=unit.themes,
                    metadata={
                        'error': str(e),
                        'extraction_failed': True,
                        'unit_type': unit.unit_type
                    }
                ))
        
        self.logger.info(
            f"Extraction complete. Processed {len(results)} units with "
            f"{sum(r.total_extractions for r in results)} total extractions"
        )
        
        return results