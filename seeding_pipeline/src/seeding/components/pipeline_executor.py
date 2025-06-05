"""Simplified pipeline execution component for VTT processing."""

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import os

from src.core.exceptions import PipelineError
from src.core.interfaces import TranscriptSegment
from src.core.models import Podcast, Episode, Segment
from src.utils.logging import get_logger
from src.utils.memory import cleanup_memory


def add_span_attributes(attributes: Dict[str, Any]) -> None:
    """Mock implementation for tracing/observability attributes."""
    # This is a placeholder for actual tracing implementation
    pass


def create_span(name: str, **kwargs) -> 'MockSpan':
    """Mock implementation for tracing/observability spans."""
    return MockSpan(name)


class MockSpan:
    """Mock implementation for tracing spans."""
    
    def __init__(self, name: str):
        self.name = name
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

logger = get_logger(__name__)


class PipelineExecutor:
    """Simplified pipeline executor for VTT knowledge extraction."""
    
    def __init__(self, config, provider_coordinator, checkpoint_manager, storage_coordinator=None):
        """Initialize pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator instance  
            checkpoint_manager: Checkpoint manager instance
            storage_coordinator: Storage coordinator instance (optional)
        """
        self.config = config
        self.provider_coordinator = provider_coordinator
        self.checkpoint_manager = checkpoint_manager
        self.storage_coordinator = storage_coordinator
        
        # Get services directly from provider coordinator
        self.llm_service = provider_coordinator.llm_service
        self.graph_service = provider_coordinator.graph_service
        self.embedding_service = provider_coordinator.embedding_service
        
        # Get processing components
        self.knowledge_extractor = provider_coordinator.knowledge_extractor
        self.entity_resolver = provider_coordinator.entity_resolver
        self.segmenter = provider_coordinator.segmenter
    
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
            
            # Store to graph database
            self._store_to_graph(podcast_config, episode, segments, resolved_entities, all_quotes, all_relationships)
            
            # Build result summary
            result = {
                'segments': len(segments),
                'entities': len(resolved_entities),
                'quotes': len(all_quotes),
                'relationships': len(all_relationships),
                'mode': 'direct_schemaless',
                'extraction_metadata': {
                    'total_text_length': sum(len(s.text) for s in segments),
                    'average_segment_length': sum(len(s.text) for s in segments) / len(segments) if segments else 0,
                    'processing_timestamp': datetime.now().isoformat()
                }
            }
            
            # Add metrics to tracing
            add_span_attributes({
                "result.entities": len(resolved_entities),
                "result.quotes": len(all_quotes),
                "result.relationships": len(all_relationships)
            })
            
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
                    ('Podcast', {'id': podcast_config['id']}),
                    'HAS_EPISODE',
                    ('Episode', {'id': episode['id']}),
                    {}
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
                        ('Episode', {'id': episode['id']}),
                        'MENTIONS',
                        (entity['type'], {'id': entity_data['id']}),
                        {'confidence': entity.get('confidence', 1.0)}
                    )
                
                # Store quotes
                for quote in quotes:
                    quote_data = {
                        'id': f"quote_{hash(quote['value'])}",
                        'text': quote['value'],
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
                        ('Episode', {'id': episode['id']}),
                        'CONTAINS_QUOTE',
                        ('Quote', {'id': quote_data['id']}),
                        {'importance': quote.get('importance_score', 0.5)}
                    )
                
                # Store relationships
                for relationship in relationships:
                    self.graph_service.create_relationship(
                        ('Entity', {'name': relationship['source']}),
                        relationship['type'],
                        ('Entity', {'name': relationship['target']}),
                        {
                            'confidence': relationship.get('confidence', 0.5),
                            'episode_id': episode['id']
                        }
                    )
                
                logger.info(f"Stored {len(entities)} entities, {len(quotes)} quotes, {len(relationships)} relationships")
                
            except Exception as e:
                logger.error(f"Failed to store knowledge to graph: {e}")
                # Don't fail the entire pipeline if storage fails
    
    def _is_episode_completed(self, episode_id: str) -> bool:
        """Check if episode is already completed.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if episode is already completed
        """
        return self.checkpoint_manager.is_completed(episode_id)
    
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
        """Finalize episode processing.
        
        Args:
            episode_id: Episode identifier
            result: Processing results
        """
        # Mark episode as complete
        self.checkpoint_manager.mark_completed(episode_id, result)
        
        # Clean up memory
        cleanup_memory()
        
        # Add result metrics to span
        add_span_attributes({
            "result.segments": result["segments"],
            "result.entities": result.get("entities", 0),
            "result.quotes": result.get("quotes", 0),
            "result.relationships": result.get("relationships", 0),
            "result.mode": result.get("mode", "direct_schemaless")
        })
        
        logger.info(f"Episode {episode_id} processing completed: {result}")
    
    # Legacy method for backward compatibility
    def process_episode(self, podcast_config: Dict[str, Any], 
                       episode: Dict[str, Any],
                       use_large_context: bool) -> Dict[str, Any]:
        """Legacy episode processing method (deprecated for VTT workflow).
        
        This method is kept for backward compatibility but should not be used
        for VTT-based processing. Use process_vtt_segments instead.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            use_large_context: Whether to use large context
            
        Returns:
            Episode processing results
        """
        logger.warning("process_episode is deprecated for VTT workflow. Use process_vtt_segments instead.")
        
        # Return minimal result to maintain compatibility
        return {
            'segments': 0,
            'entities': 0,
            'quotes': 0,
            'relationships': 0,
            'mode': 'deprecated',
            'message': 'Use process_vtt_segments for VTT-based processing'
        }