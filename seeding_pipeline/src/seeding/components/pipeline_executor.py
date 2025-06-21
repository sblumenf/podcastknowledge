"""Simplified pipeline execution component for VTT processing."""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging
import os

from .base_pipeline_executor import BasePipelineExecutor
from ...core.exceptions import PipelineError
from ...core.interfaces import TranscriptSegment
from ...core.models import Podcast, Episode, Segment, Entity
from ...utils.logging import get_logger
from ...utils.memory import cleanup_memory
logger = get_logger(__name__)


class PipelineExecutor(BasePipelineExecutor):
    """Simplified pipeline executor for VTT knowledge extraction."""
    
    def __init__(self, config, provider_coordinator, checkpoint_manager, storage_coordinator=None):
        """Initialize pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator instance  
            checkpoint_manager: Checkpoint manager instance
            storage_coordinator: Storage coordinator instance (optional)
        """
        # Initialize base class
        super().__init__(config, provider_coordinator, checkpoint_manager)
        
        # Set storage coordinator if provided (overrides base class default)
        if storage_coordinator:
            self.storage_coordinator = storage_coordinator
        
        # Additional services from provider coordinator
        self.llm_service = provider_coordinator.llm_service
        self.graph_service = provider_coordinator.graph_service
        self.embedding_service = provider_coordinator.embedding_service
        self.segmenter = provider_coordinator.segmenter
    
    def _process_segments_impl(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        segments: List[Dict[str, Any]],
        use_large_context: bool
    ) -> Dict[str, Any]:
        """Implementation-specific segment processing logic.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: VTT segments to process
            use_large_context: Whether to use large context model
            
        Returns:
            Processing result with extracted knowledge
        """
        episode_id = episode['id']
        
        # Convert to Segment objects if needed
        if segments and isinstance(segments[0], (dict, TranscriptSegment)):
            segment_objects = self._convert_segments(segments, episode_id)
        else:
            segment_objects = segments
        
        # Save segments checkpoint
        self.checkpoint_manager.save_progress(episode_id, "segments", segment_objects)
        
        # Perform knowledge extraction
        extraction_result = self._extract_knowledge_direct(
            podcast_config, episode, segment_objects, episode_id
        )
        
        return extraction_result
    
    def _prepare_storage_data(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        segments: List[Dict[str, Any]],
        extraction_result: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], List[Entity]]:
        """Prepare data for storage based on implementation specifics.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Raw extraction results
            
        Returns:
            Tuple of (podcast_config, episode, segments, extraction_result, resolved_entities)
        """
        # Extract entities from result - they're already Entity objects from resolver
        entities = extraction_result.get('entities', [])
        quotes = extraction_result.get('quotes', [])
        relationships = extraction_result.get('relationships', [])
        
        # Convert segments to dict format for storage
        segment_dicts = []
        for seg in segments:
            if isinstance(seg, Segment):
                segment_dicts.append({
                    'id': seg.id,
                    'text': seg.text,
                    'start': seg.start_time,
                    'end': seg.end_time,
                    'speaker': seg.speaker,
                    'segment_number': seg.segment_number
                })
            elif hasattr(seg, 'text'):  # TranscriptSegment
                segment_dicts.append({
                    'id': f"{episode['id']}_segment_{len(segment_dicts)}",
                    'text': seg.text,
                    'start': seg.start_time,
                    'end': seg.end_time,
                    'speaker': getattr(seg, 'speaker', 'Unknown'),
                    'segment_number': len(segment_dicts) + 1
                })
            else:
                segment_dicts.append(seg)
        
        # Prepare extraction result for storage coordinator
        storage_extraction_result = {
            'entities': [],  # Entities are passed separately as Entity objects
            'quotes': quotes,
            'relationships': relationships,
            'insights': [],  # No insights in direct extraction
            'emergent_themes': {},  # No themes in direct extraction
            'metadata': extraction_result.get('extraction_metadata', {})
        }
        
        return podcast_config, episode, segment_dicts, storage_extraction_result, entities
    
    def process_vtt_segments(self,
                           podcast_config: Dict[str, Any],
                           episode: Dict[str, Any],
                           segments: List[TranscriptSegment],
                           use_large_context: bool = True) -> Dict[str, Any]:
        """Process VTT segments through the simplified knowledge extraction pipeline.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Pre-parsed VTT segments
            use_large_context: Whether to use large context models
            
        Returns:
            Processing results with extracted knowledge
        """
        episode_id = episode['id']
        logger.info(f"Processing VTT segments for episode: {episode['title']} (ID: {episode_id})")
        
        # Check if already completed
        if self._is_episode_completed(episode_id):
            logger.info(f"Episode {episode_id} already completed, skipping")
            return {'segments': 0, 'insights': 0, 'entities': 0}
        
        try:
            # Add episode context for tracing
            self._add_episode_context(episode, podcast_config)
            
            # Convert to processing format
            segment_objects = self._convert_segments(segments, episode_id)
            
            # Save segments checkpoint
            self.checkpoint_manager.save_progress(episode_id, "segments", segment_objects)
            
            # Direct schemaless extraction (no mode selection)
            result = self._extract_knowledge_direct(
                podcast_config, episode, segment_objects, episode_id
            )
            
            # Finalize processing
            self._finalize_episode_processing(episode_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing VTT segments for episode {episode_id}: {e}")
            raise PipelineError(f"VTT segment processing failed: {e}")
    
    def _convert_segments(self, segments: List[TranscriptSegment], episode_id: str) -> List[Segment]:
        """Convert TranscriptSegment objects to Segment model objects.
        
        Args:
            segments: List of TranscriptSegment objects
            episode_id: Episode identifier
            
        Returns:
            List of Segment model objects
        """
        segment_objects = []
        for i, segment in enumerate(segments):
            segment_obj = Segment(
                id=f"{episode_id}_segment_{i}",
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                speaker=segment.speaker,
                episode_id=episode_id,
                segment_index=i,
                segment_number=i + 1
            )
            segment_objects.append(segment_obj)
        return segment_objects
    
    def _extract_knowledge_direct(self,
                                podcast_config: Dict[str, Any],
                                episode: Dict[str, Any],
                                segments: List[Segment],
                                episode_id: str) -> Dict[str, Any]:
        """Direct knowledge extraction without strategy pattern.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Segment model objects
            episode_id: Episode identifier
            
        Returns:
            Extraction results
        """
        logger.info("Processing segments with direct knowledge extraction")
        
        with create_span("knowledge_extraction", attributes={
            "segments.count": len(segments),
            "extraction.mode": "direct_schemaless"
        }):
            # Create episode metadata for context
            episode_metadata = {
                'id': episode['id'],
                'title': episode['title'],
                'description': episode.get('description', ''),
                'podcast_name': podcast_config.get('name', podcast_config['id'])
            }
            
            # Process each segment for knowledge extraction
            all_entities = []
            all_quotes = []
            all_relationships = []
            
            for segment in segments:
                try:
                    # Extract knowledge from segment
                    extraction_result = self.knowledge_extractor.extract_knowledge(
                        segment, episode_metadata
                    )
                    
                    # Collect results
                    all_entities.extend(extraction_result.entities)
                    all_quotes.extend(extraction_result.quotes)
                    all_relationships.extend(extraction_result.relationships)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract knowledge from segment {segment.id}: {e}")
                    continue
            
            # Resolve and deduplicate entities
            if all_entities:
                entity_resolution_result = self.entity_resolver.resolve_entities(all_entities)
                resolved_entities = entity_resolution_result.get('resolved_entities', all_entities)
            else:
                resolved_entities = []
            
            # Note: Storage is handled by base class via _prepare_storage_data
            
            # Build result summary with actual data for base class
            result = {
                'segments': len(segments),
                'entities': resolved_entities,  # Return actual entities
                'quotes': all_quotes,
                'relationships': all_relationships,
                'mode': 'direct_schemaless',
                'extraction_metadata': {
                    'total_text_length': sum(len(s.text) for s in segments),
                    'average_segment_length': sum(len(s.text) for s in segments) / len(segments) if segments else 0,
                    'processing_timestamp': datetime.now().isoformat()
                }
            }
            
            return result
    
    def _store_to_graph(self,
                       podcast_config: Dict[str, Any],
                       episode: Dict[str, Any],
                       segments: List[Segment],
                       entities: List[Dict[str, Any]],
                       quotes: List[Dict[str, Any]],
                       relationships: List[Dict[str, Any]]) -> None:
        """Store extracted knowledge to graph database.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Segment objects
            entities: Extracted entities
            quotes: Extracted quotes
            relationships: Extracted relationships
        """
        with create_span("graph_storage"):
            logger.info("Storing knowledge to graph database...")
            
            try:
                # Create podcast node
                podcast_data = {
                    'id': podcast_config['id'],
                    'name': podcast_config.get('name', podcast_config['id']),
                    'description': podcast_config.get('description', ''),
                    'type': 'Podcast'
                }
                self.graph_service.create_node('Podcast', podcast_data)
                
                # Create episode node
                episode_data = {
                    'id': episode['id'],
                    'title': episode['title'],
                    'description': episode.get('description', ''),
                    'published_date': episode.get('published_date', ''),
                    'duration_minutes': episode.get('duration', 0),
                    'segment_count': len(segments),
                    'entity_count': len(entities),
                    'quote_count': len(quotes),
                    'type': 'Episode'
                }
                self.graph_service.create_node('Episode', episode_data)
                
                # Create relationship between podcast and episode
                self.graph_service.create_relationship(
                    podcast_config['id'],  # source_id: str
                    episode['id'],         # target_id: str
                    'HAS_EPISODE',         # rel_type: str
                    {}                     # properties: dict
                )
                
                # Store entities
                for entity in entities:
                    entity_data = {
                        'id': entity.get('id', f"entity_{hash(entity['value'])}"),
                        'name': entity['value'],
                        'type': entity['type'],
                        'confidence': entity.get('confidence', 1.0),
                        'episode_id': episode['id']
                    }
                    if 'start_time' in entity:
                        entity_data['start_time'] = entity['start_time']
                    
                    self.graph_service.create_node(entity['type'], entity_data)
                    
                    # Create relationship to episode
                    self.graph_service.create_relationship(
                        episode['id'],                           # source_id: str
                        entity_data['id'],                       # target_id: str
                        'MENTIONS',                              # rel_type: str
                        {'confidence': entity.get('confidence', 1.0)}  # properties: dict
                    )
                
                # Store quotes
                for quote in quotes:
                    quote_text = quote.get('text', quote.get('value', ''))  # Support both field names
                    quote_data = {
                        'id': f"quote_{hash(quote_text)}",
                        'text': quote_text,
                        'speaker': quote.get('speaker', 'Unknown'),
                        'quote_type': quote.get('quote_type', 'general'),
                        'importance_score': quote.get('importance_score', 0.5),
                        'start_time': quote.get('start_time', 0),
                        'end_time': quote.get('end_time', 0),
                        'episode_id': episode['id']
                    }
                    self.graph_service.create_node('Quote', quote_data)
                    
                    # Create relationship to episode
                    self.graph_service.create_relationship(
                        episode['id'],                               # source_id: str
                        quote_data['id'],                            # target_id: str
                        'CONTAINS_QUOTE',                            # rel_type: str
                        {'importance': quote.get('importance_score', 0.5)}  # properties: dict
                    )
                
                # Store relationships
                for relationship in relationships:
                    # Note: This needs to be updated to use entity IDs instead of names
                    # For now, we'll use the source/target names as IDs (requires entity lookup)
                    source_id = f"entity_{hash(relationship['source'])}"
                    target_id = f"entity_{hash(relationship['target'])}"
                    
                    self.graph_service.create_relationship(
                        source_id,             # source_id: str
                        target_id,             # target_id: str
                        relationship['type'],  # rel_type: str
                        {                      # properties: dict
                            'confidence': relationship.get('confidence', 0.5),
                            'episode_id': episode['id']
                        }
                    )
                
                logger.info(f"Stored {len(entities)} entities, {len(quotes)} quotes, {len(relationships)} relationships")
                
            except Exception as e:
                logger.error(f"Failed to store knowledge to graph: {e}")
                # Don't fail the entire pipeline if storage fails
    
    
    def _add_episode_context(self, episode: Dict[str, Any], 
                            podcast_config: Dict[str, Any]) -> None:
        """Add episode context to tracing span.
        
        Args:
            episode: Episode information
            podcast_config: Podcast configuration
        """
        add_span_attributes({
            "episode.id": episode["id"],
            "episode.title": episode["title"],
            "podcast.id": podcast_config["id"],
            "podcast.name": podcast_config.get("name", ""),
        })
    
    def _finalize_episode_processing(self, episode_id: str, result: Dict[str, Any]) -> None:
        """Override to add custom finalization."""
        # Mark episode as complete with checkpoint manager's specific method
        self.checkpoint_manager.mark_completed(episode_id, result)
        
        # Call parent implementation
        super()._finalize_episode_processing(episode_id, result)
