"""Base pipeline executor with common functionality for all pipeline implementations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import logging
import gc
import time
from contextlib import contextmanager

from ...core.models import Entity
from ...utils.logging import get_logger
from ...monitoring import get_metrics_collector

logger = get_logger(__name__)


class BasePipelineExecutor(ABC):
    """Abstract base class for pipeline executors.
    
    Provides common functionality for processing VTT segments through
    the knowledge extraction pipeline with different strategies.
    """
    
    def __init__(self, config: Any, provider_coordinator: Any, checkpoint_manager: Any):
        """Initialize base pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator for services
            checkpoint_manager: Checkpoint manager for progress tracking
        """
        self.config = config
        self.provider_coordinator = provider_coordinator
        self.checkpoint_manager = checkpoint_manager
        self.metrics = get_metrics_collector()
        
        # Initialize from provider coordinator
        self.llm_provider = provider_coordinator.llm_provider
        self.graph_storage = provider_coordinator.graph_storage
        self.storage_coordinator = provider_coordinator.storage_coordinator
        self.knowledge_extractor = provider_coordinator.knowledge_extractor
        self.entity_resolver = provider_coordinator.entity_resolver
        
        logger.info(f"Initialized {self.__class__.__name__}")
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    def process_vtt_segments(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        segments: List[Dict[str, Any]],
        use_large_context: bool = True
    ) -> Dict[str, Any]:
        """Process VTT segments through the knowledge extraction pipeline.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: VTT segments to process
            use_large_context: Whether to use large context model
            
        Returns:
            Processing result
        """
        try:
            episode_id = episode['id']
            
            # Check if episode is already completed
            if self._is_episode_completed(episode_id):
                logger.info(f"Episode {episode_id} already completed, skipping")
                return {'status': 'skipped', 'reason': 'already_completed'}
            
            # Log processing start
            logger.info(f"Processing episode {episode_id} with {len(segments)} segments")
            self.metrics.episodes_started.inc()
            
            # Create tracing span
            with self._create_span('process_episode', episode_id) as span:
                # Process segments (implementation-specific)
                extraction_result = self._process_segments_impl(
                    podcast_config,
                    episode,
                    segments,
                    use_large_context
                )
                
                # Prepare data for storage
                storage_data = self._prepare_storage_data(
                    podcast_config,
                    episode,
                    segments,
                    extraction_result
                )
                
                # Store to graph
                self._store_to_graph(*storage_data)
                
                # Mark episode as completed
                self._finalize_episode_processing(episode_id, extraction_result)
                
                # Clean up memory
                self._cleanup_memory()
                
                # Record success metrics
                self.metrics.episodes_completed.inc()
                
                return {
                    'status': 'success',
                    'episode_id': episode_id,
                    'stats': self._get_processing_stats(extraction_result)
                }
                
        except Exception as e:
            logger.error(f"Failed to process episode {episode.get('id', 'unknown')}: {e}")
            self.metrics.episodes_failed.inc()
            raise
    
    def _is_episode_completed(self, episode_id: str) -> bool:
        """Check if an episode has already been completed.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if episode is already completed
        """
        return self.checkpoint_manager.is_episode_completed(episode_id)
    
    def _store_to_graph(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        segments: List[Dict[str, Any]],
        extraction_result: Dict[str, Any],
        resolved_entities: List[Entity]
    ) -> None:
        """Store extracted knowledge to the graph database.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            extraction_result: Extraction results
            resolved_entities: Resolved entities
        """
        logger.info(f"Storing knowledge for episode {episode['id']}")
        
        # Delegate to storage coordinator
        self.storage_coordinator.store_all(
            podcast_config,
            episode,
            segments,
            extraction_result,
            resolved_entities
        )
    
    def _finalize_episode_processing(self, episode_id: str, result: Dict[str, Any]) -> None:
        """Finalize episode processing and mark as completed.
        
        Args:
            episode_id: Episode identifier
            result: Processing result
        """
        # Save checkpoint
        self.checkpoint_manager.save_checkpoint(episode_id, 'completed', result)
        
        # Log completion
        logger.info(f"Episode {episode_id} processing completed")
    
    def _cleanup_memory(self) -> None:
        """Clean up memory after processing."""
        gc.collect()
        logger.debug("Memory cleanup performed")
    
    def _get_processing_stats(self, extraction_result: Dict[str, Any]) -> Dict[str, int]:
        """Get processing statistics from extraction result.
        
        Args:
            extraction_result: Extraction results
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'entities': len(extraction_result.get('entities', [])),
            'insights': len(extraction_result.get('insights', [])),
            'quotes': len(extraction_result.get('quotes', [])),
            'themes': len(extraction_result.get('emergent_themes', {}).get('themes', [])),
        }
        
        # Add implementation-specific stats
        stats.update(self._get_additional_stats(extraction_result))
        
        return stats
    
    def _get_additional_stats(self, extraction_result: Dict[str, Any]) -> Dict[str, int]:
        """Get implementation-specific statistics.
        
        Args:
            extraction_result: Extraction results
            
        Returns:
            Additional statistics
        """
        # Default implementation returns empty dict
        # Subclasses can override to add specific stats
        return {}
    
    @contextmanager
    def _create_span(self, operation: str, episode_id: str):
        """Create a tracing span for monitoring.
        
        Args:
            operation: Operation name
            episode_id: Episode identifier
            
        Yields:
            Span object (currently a mock implementation)
        """
        # Mock implementation for now
        # TODO: Replace with real tracing when available
        class MockSpan:
            def set_attribute(self, key: str, value: Any) -> None:
                pass
            
            def set_status(self, status: str) -> None:
                pass
        
        span = MockSpan()
        span.set_attribute('episode_id', episode_id)
        span.set_attribute('operation', operation)
        
        start_time = time.time()
        
        try:
            yield span
            span.set_status('success')
        except Exception as e:
            span.set_status('error')
            span.set_attribute('error', str(e))
            raise
        finally:
            duration = time.time() - start_time
            span.set_attribute('duration', duration)
            logger.debug(f"Operation {operation} took {duration:.2f}s")
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get executor metadata.
        
        Returns:
            Metadata dictionary
        """
        return {
            'executor_type': self.__class__.__name__,
            'config': {
                'use_enhanced_logging': getattr(self.config, 'use_enhanced_logging', False),
                'enable_graph_enhancements': getattr(self.config, 'enable_graph_enhancements', True),
                'use_large_context': getattr(self.config, 'use_large_context', True),
            }
        }
    
    def resolve_entities(self, entities: List[Dict[str, Any]]) -> List[Entity]:
        """Resolve and deduplicate entities.
        
        Args:
            entities: List of entity dictionaries
            
        Returns:
            List of resolved Entity objects
        """
        if not entities:
            return []
        
        # Convert to Entity objects
        entity_objects = []
        for entity_data in entities:
            entity = Entity(
                name=entity_data.get('name', ''),
                entity_type=entity_data.get('type', 'unknown'),
                description=entity_data.get('description', ''),
                confidence=entity_data.get('confidence', 0.5),
                properties=entity_data
            )
            entity_objects.append(entity)
        
        # Resolve using entity resolver
        resolved = self.entity_resolver.resolve_entities(entity_objects)
        
        logger.info(f"Resolved {len(entities)} entities to {len(resolved)} unique entities")
        
        return resolved