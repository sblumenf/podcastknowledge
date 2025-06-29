"""Knowledge extraction with integrated Gemini caching support."""

import logging
from typing import Dict, Any, List, Optional, Union
import json
from dataclasses import dataclass, field

from src.core.interfaces import TranscriptSegment
from src.services.llm_gemini_direct import GeminiDirectService
from src.services.cache_manager import CacheManager
from src.services.cached_prompt_service import CachedPromptService
from src.extraction.prompts import PromptBuilder
from src.monitoring import get_pipeline_metrics
from src.core.env_config import EnvironmentConfig

logger = logging.getLogger(__name__)


@dataclass
class CachedExtractionConfig:
    """Configuration for cached extraction."""
    entity_extraction_model: str = field(default_factory=EnvironmentConfig.get_flash_model)
    insight_extraction_model: str = field(default_factory=EnvironmentConfig.get_flash_model)
    use_large_context: bool = True
    cache_ttl: int = 3600
    batch_size: int = 10
    min_transcript_size_for_cache: int = 5000  # characters


class CachedExtractionService:
    """Extraction service with integrated caching support."""
    
    def __init__(self,
                 llm_service: Union[GeminiDirectService, Any],
                 cache_manager: CacheManager,
                 config: Optional[CachedExtractionConfig] = None):
        """Initialize cached extraction service.
        
        Args:
            llm_service: LLM service (preferably GeminiDirectService)
            cache_manager: Cache manager instance
            config: Extraction configuration
        """
        self.llm_service = llm_service
        self.cache_manager = cache_manager
        self.config = config or CachedExtractionConfig()
        
        # Use GeminiDirectService features if available
        self.is_gemini_direct = isinstance(llm_service, GeminiDirectService)
        
        # Create cached prompt service if using Gemini Direct
        if self.is_gemini_direct:
            self.cached_prompt_service = CachedPromptService(
                llm_service=llm_service,
                cache_manager=cache_manager,
                use_large_context=self.config.use_large_context
            )
            # Warm prompt caches
            try:
                self.cached_prompt_service.warm_caches()
            except Exception as e:
                logger.warning(f"Failed to warm prompt caches: {e}")
        else:
            self.cached_prompt_service = None
            
        self.prompt_builder = PromptBuilder(use_large_context=self.config.use_large_context)
        self.metrics = get_pipeline_metrics()
        
    def extract_from_episode(self, 
                           episode_id: str,
                           transcript: str,
                           segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """Extract knowledge from an entire episode with caching.
        
        Args:
            episode_id: Unique episode identifier
            transcript: Full transcript text
            segments: List of transcript segments
            
        Returns:
            Extraction results with entities, insights, quotes
        """
        start_time = logger.time() if hasattr(logger, 'time') else 0
        
        # Check if transcript should be cached
        episode_cache_name = None
        if (self.is_gemini_direct and 
            len(transcript) >= self.config.min_transcript_size_for_cache and
            self.cache_manager.should_cache_transcript(transcript, episode_id)):
            
            # Try to create episode cache
            try:
                logger.info(f"Creating cache for episode {episode_id}")
                episode_cache_name = self.llm_service.create_cached_content(
                    content=transcript,
                    episode_id=episode_id,
                    system_instruction="You are analyzing a podcast transcript for knowledge extraction."
                )
                
                if episode_cache_name:
                    # Register in cache manager
                    self.cache_manager.register_episode_cache(
                        episode_id=episode_id,
                        cache_name=episode_cache_name,
                        content=transcript,
                        ttl=self.config.cache_ttl
                    )
                    logger.info(f"Successfully cached episode {episode_id}")
                    
            except Exception as e:
                logger.warning(f"Failed to cache episode {episode_id}: {e}")
                
        # Process segments in batches
        all_results = {
            'entities': [],
            'insights': [],
            'quotes': [],
            'relationships': []
        }
        
        # Process in batches for efficiency
        for i in range(0, len(segments), self.config.batch_size):
            batch = segments[i:i + self.config.batch_size]
            batch_results = self._process_segment_batch(
                batch, 
                episode_cache_name,
                episode_id
            )
            
            # Aggregate results
            for key in all_results:
                all_results[key].extend(batch_results.get(key, []))
                
        # Add metadata
        all_results['metadata'] = {
            'episode_id': episode_id,
            'segment_count': len(segments),
            'cached': episode_cache_name is not None,
            'cache_stats': self.cache_manager.get_cache_stats()
        }
        
        # Record metrics
        if self.metrics:
            self.metrics.record_extraction(
                'episode',
                success=True,
                latency=logger.time() - start_time if hasattr(logger, 'time') else 0,
                cached=episode_cache_name is not None
            )
            
        return all_results
        
    def _process_segment_batch(self,
                             segments: List[TranscriptSegment],
                             episode_cache_name: Optional[str],
                             episode_id: str) -> Dict[str, Any]:
        """Process a batch of segments.
        
        Args:
            segments: Batch of segments to process
            episode_cache_name: Optional episode cache to use
            episode_id: Episode identifier for context
            
        Returns:
            Batch extraction results
        """
        results = {
            'entities': [],
            'insights': [],
            'quotes': [],
            'relationships': []
        }
        
        # Combine segment texts for batch processing
        combined_text = "\n\n---SEGMENT---\n\n".join([
            f"[Time: {seg.start_time}-{seg.end_time}]\n{seg.text}"
            for seg in segments
        ])
        
        # Extract entities
        try:
            if self.cached_prompt_service:
                # Use cached prompt service
                entity_response = self.cached_prompt_service.extract_entities(
                    text=combined_text,
                    episode_cache_name=episode_cache_name
                )
            else:
                # Fall back to regular LLM service
                template = self.prompt_builder.get_template('entity_extraction_large')
                prompt = template.format(text=combined_text)
                entity_response = self.llm_service.complete(prompt)
                
            # Parse entities
            entities = self._parse_entities(entity_response, segments)
            results['entities'] = entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            
        # Extract insights
        try:
            # Build entity context
            entity_context = self._build_entity_context(entities)
            
            if self.cached_prompt_service:
                insight_response = self.cached_prompt_service.extract_insights(
                    text=combined_text,
                    entity_context=entity_context,
                    episode_cache_name=episode_cache_name
                )
            else:
                template = self.prompt_builder.get_template('insight_extraction_large')
                prompt = template.format(text=combined_text, entity_context=entity_context)
                insight_response = self.llm_service.complete(prompt)
                
            # Parse insights
            insights = self._parse_insights(insight_response, segments)
            results['insights'] = insights
            
        except Exception as e:
            logger.error(f"Insight extraction failed: {e}")
            
        # Extract quotes (only for first segment in batch to avoid duplication)
        if segments and self.config.use_large_context:
            try:
                if self.cached_prompt_service:
                    quote_response = self.cached_prompt_service.extract_quotes(
                        text=combined_text,
                        episode_cache_name=episode_cache_name
                    )
                else:
                    template = self.prompt_builder.get_template('quote_extraction_large')
                    prompt = template.format(text=combined_text)
                    quote_response = self.llm_service.complete(prompt)
                    
                quotes = self._parse_quotes(quote_response, segments)
                results['quotes'] = quotes
                
            except Exception as e:
                logger.error(f"Quote extraction failed: {e}")
                
        # Extract relationships between entities
        if entities and len(entities) > 1:
            relationships = self._extract_relationships(entities, segments)
            results['relationships'] = relationships
            
        return results
        
    def _parse_entities(self, response: str, segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """Parse entity extraction response."""
        try:
            # Extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                entities = json.loads(json_str)
                
                # Add segment references
                for entity in entities:
                    # Simple assignment to first segment for now
                    if segments:
                        entity['segment_id'] = segments[0].id if hasattr(segments[0], 'id') else 0
                        entity['timestamp'] = segments[0].start_time
                        
                return entities
            else:
                logger.warning("No JSON found in entity response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse entity JSON: {e}")
            return []
            
    def _parse_insights(self, response: str, segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """Parse insight extraction response."""
        try:
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                insights = json.loads(json_str)
                
                # Add segment references
                for insight in insights:
                    if segments:
                        insight['segment_id'] = segments[0].id if hasattr(segments[0], 'id') else 0
                        insight['timestamp'] = segments[0].start_time
                        
                return insights
            else:
                logger.warning("No JSON found in insight response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse insight JSON: {e}")
            return []
            
    def _parse_quotes(self, response: str, segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """Parse quote extraction response."""
        try:
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                quotes = json.loads(json_str)
                
                # Add segment references
                for quote in quotes:
                    if segments:
                        quote['segment_id'] = segments[0].id if hasattr(segments[0], 'id') else 0
                        quote['timestamp'] = segments[0].start_time
                        
                return quotes
            else:
                logger.warning("No JSON found in quote response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quote JSON: {e}")
            return []
            
    def _build_entity_context(self, entities: List[Dict[str, Any]]) -> str:
        """Build context string from extracted entities."""
        if not entities:
            return ""
            
        context_parts = ["Known entities in this segment:"]
        for entity in entities[:10]:  # Limit to prevent prompt bloat
            context_parts.append(f"- {entity.get('name', 'Unknown')} ({entity.get('type', 'Unknown')})")
            
        return "\n".join(context_parts)
        
    def _extract_relationships(self, 
                             entities: List[Dict[str, Any]], 
                             segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """Extract simple relationships between entities."""
        relationships = []
        
        # Simple co-occurrence based relationships
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Check if entities appear in same segment
                if entity1.get('segment_id') == entity2.get('segment_id'):
                    relationships.append({
                        'source': entity1.get('name', 'Unknown'),
                        'target': entity2.get('name', 'Unknown'),
                        'type': 'co-occurrence',
                        'confidence': 0.6,
                        'segment_id': entity1.get('segment_id')
                    })
                    
        return relationships
        
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics including cache performance."""
        stats = {
            'cache_stats': self.cache_manager.get_cache_stats(),
            'cost_savings': self.cache_manager.estimate_cost_savings()
        }
        
        if self.cached_prompt_service:
            stats['prompt_cache_stats'] = self.cached_prompt_service.get_cache_stats()
            
        return stats