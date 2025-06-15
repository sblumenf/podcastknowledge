"""Multi-podcast aware pipeline executor with context propagation."""

import os
from typing import Dict, Any, List, Optional
import logging

from src.seeding.components.pipeline_executor import PipelineExecutor
from src.core.interfaces import TranscriptSegment
from src.core.models import Segment
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MultiPodcastPipelineExecutor(PipelineExecutor):
    """Pipeline executor with multi-podcast context propagation."""
    
    def __init__(self, config, provider_coordinator, checkpoint_manager, storage_coordinator=None):
        """Initialize multi-podcast pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator instance  
            checkpoint_manager: Checkpoint manager instance
            storage_coordinator: Storage coordinator instance (optional)
        """
        super().__init__(config, provider_coordinator, checkpoint_manager, storage_coordinator)
        self._current_podcast_id = None
        self._multi_podcast_mode = os.getenv('PODCAST_MODE', 'single') == 'multi'
        
        if self._multi_podcast_mode:
            logger.info("Multi-podcast mode enabled in pipeline executor")
    
    def process_vtt_segments(self,
                           podcast_config: Dict[str, Any],
                           episode: Dict[str, Any],
                           segments: List[TranscriptSegment],
                           use_large_context: bool = True) -> Dict[str, Any]:
        """Process VTT segments with podcast context awareness.
        
        Args:
            podcast_config: Podcast configuration with podcast_id
            episode: Episode information
            segments: Pre-parsed VTT segments
            use_large_context: Whether to use large context models
            
        Returns:
            Processing results with extracted knowledge
        """
        # Extract podcast ID from config
        podcast_id = self._extract_podcast_id(podcast_config, episode)
        
        if self._multi_podcast_mode and podcast_id:
            logger.info(f"Processing segments for podcast: {podcast_id}")
            self._set_podcast_context(podcast_id)
            
            # Add podcast context to episode data
            episode['podcast_id'] = podcast_id
        
        # Call parent implementation
        result = super().process_vtt_segments(
            podcast_config, episode, segments, use_large_context
        )
        
        # Add podcast info to result
        if self._multi_podcast_mode and podcast_id:
            result['podcast_id'] = podcast_id
        
        return result
    
    def _extract_podcast_id(self, podcast_config: Dict[str, Any], 
                           episode: Dict[str, Any]) -> Optional[str]:
        """Extract podcast ID from configuration or episode.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode data
            
        Returns:
            Podcast ID or None
        """
        # Priority order: podcast_config['podcast_id'] > podcast_config['id'] > episode['podcast_id']
        podcast_id = (
            podcast_config.get('podcast_id') or 
            podcast_config.get('id') or 
            episode.get('podcast_id')
        )
        
        if not podcast_id and self._multi_podcast_mode:
            logger.warning("No podcast ID found in multi-podcast mode")
        
        return podcast_id
    
    def _set_podcast_context(self, podcast_id: str) -> None:
        """Set podcast context for all pipeline components.
        
        Args:
            podcast_id: The podcast identifier
        """
        self._current_podcast_id = podcast_id
        
        # Set context in storage coordinator if it supports it
        if hasattr(self.storage_coordinator, 'switch_podcast_context'):
            self.storage_coordinator.switch_podcast_context(podcast_id)
            logger.debug(f"Set podcast context in storage coordinator: {podcast_id}")
        
        # Set context in graph service if it supports it
        if hasattr(self.graph_service, 'set_podcast_context'):
            self.graph_service.set_podcast_context(podcast_id)
            logger.debug(f"Set podcast context in graph service: {podcast_id}")
        
        # Update checkpoint manager context
        if self._multi_podcast_mode:
            self._update_checkpoint_context(podcast_id)
    
    def _update_checkpoint_context(self, podcast_id: str) -> None:
        """Update checkpoint manager for podcast-specific state.
        
        Args:
            podcast_id: The podcast identifier
        """
        # Create podcast-specific checkpoint directory
        checkpoint_dir = self.checkpoint_manager.checkpoint_dir
        podcast_checkpoint_dir = checkpoint_dir / f"podcasts/{podcast_id}"
        podcast_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporarily update checkpoint path for this podcast
        # This maintains separate checkpoint state per podcast
        original_checkpoint_path = self.checkpoint_manager.checkpoint.checkpoint_path
        podcast_checkpoint_path = podcast_checkpoint_dir / "checkpoint.json"
        
        # Store original path to restore later if needed
        self.checkpoint_manager._original_checkpoint_path = original_checkpoint_path
        self.checkpoint_manager.checkpoint.checkpoint_path = podcast_checkpoint_path
        
        logger.debug(f"Using podcast-specific checkpoint: {podcast_checkpoint_path}")
    
    def _is_episode_completed(self, episode_id: str) -> bool:
        """Check if episode is already completed in podcast context.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if episode is already completed
        """
        # In multi-podcast mode, episode IDs should include podcast context
        if self._multi_podcast_mode and self._current_podcast_id:
            # Ensure episode ID includes podcast context
            if not episode_id.startswith(self._current_podcast_id):
                episode_id = f"{self._current_podcast_id}_{episode_id}"
        
        return super()._is_episode_completed(episode_id)
    
    def _add_episode_context(self, episode: Dict[str, Any], 
                            podcast_config: Dict[str, Any]) -> None:
        """Add episode context to tracing span with podcast info.
        
        Args:
            episode: Episode information
            podcast_config: Podcast configuration
        """
        # Call parent implementation
        super()._add_episode_context(episode, podcast_config)
        
        # Add podcast-specific context
        if self._multi_podcast_mode and self._current_podcast_id:
            from src.seeding.components.pipeline_executor import add_span_attributes
            add_span_attributes({
                "podcast.current_id": self._current_podcast_id,
                "podcast.mode": "multi"
            })
    
    def _store_to_graph(self,
                       podcast_config: Dict[str, Any],
                       episode: Dict[str, Any],
                       segments: List[Segment],
                       entities: List[Dict[str, Any]],
                       quotes: List[Dict[str, Any]],
                       relationships: List[Dict[str, Any]]) -> None:
        """Store extracted knowledge to graph database with podcast context.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Segment objects
            entities: Extracted entities
            quotes: Extracted quotes
            relationships: Extracted relationships
        """
        # Ensure podcast ID is in the config
        if self._multi_podcast_mode and self._current_podcast_id:
            podcast_config['podcast_id'] = self._current_podcast_id
            episode['podcast_id'] = self._current_podcast_id
        
        # Use storage coordinator if available (which handles multi-db routing)
        if self.storage_coordinator and hasattr(self.storage_coordinator, 'store_all'):
            logger.debug("Using storage coordinator for graph storage")
            
            # Package extraction results
            extraction_result = {
                'entities': entities,
                'quotes': quotes,
                'relationships': relationships,
                'metadata': {
                    'segment_count': len(segments),
                    'podcast_id': self._current_podcast_id
                }
            }
            
            # Entities need to be in the expected format for entity resolver
            resolved_entities = [{'entity': entity} for entity in entities]
            
            self.storage_coordinator.store_all(
                podcast_config,
                episode,
                segments,
                extraction_result,
                resolved_entities
            )
        else:
            # Fall back to direct storage
            super()._store_to_graph(
                podcast_config, episode, segments, 
                entities, quotes, relationships
            )
    
    def cleanup(self):
        """Clean up resources and restore original checkpoint paths."""
        # Restore original checkpoint path if it was changed
        if hasattr(self.checkpoint_manager, '_original_checkpoint_path'):
            self.checkpoint_manager.checkpoint.checkpoint_path = self.checkpoint_manager._original_checkpoint_path
            delattr(self.checkpoint_manager, '_original_checkpoint_path')
        
        # Clear podcast context
        self._current_podcast_id = None
        
        # Call parent cleanup
        super().cleanup()