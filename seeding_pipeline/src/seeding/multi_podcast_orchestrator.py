"""Multi-podcast aware orchestrator for the knowledge extraction pipeline."""

import os
from typing import Dict, Any, Optional, List, Union
import logging

from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage
from src.storage.multi_database_storage_coordinator import MultiDatabaseStorageCoordinator
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


class MultiPodcastVTTKnowledgeExtractor(EnhancedKnowledgePipeline):
    """Multi-podcast aware orchestrator for VTT transcript knowledge extraction."""
    
    def initialize_components(self, use_large_context: bool = True) -> bool:
        """Initialize all pipeline components with multi-podcast support.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            # Delegate base initialization to provider coordinator
            success = self.provider_coordinator.initialize_providers(use_large_context)
            if not success:
                return False
            
            # Set up backward compatibility references
            self.llm_service = self.provider_coordinator.llm_service
            self.embedding_service = self.provider_coordinator.embedding_service
            
            self.segmenter = self.provider_coordinator.segmenter
            self.knowledge_extractor = self.provider_coordinator.knowledge_extractor
            self.entity_resolver = self.provider_coordinator.entity_resolver
            self.graph_enhancer = self.provider_coordinator.graph_enhancer
            self.episode_flow_analyzer = self.provider_coordinator.episode_flow_analyzer
            
            # Set up checkpoint reference for backward compatibility
            self.checkpoint = self.checkpoint_manager.checkpoint
            
            # Check if we're in multi-podcast mode
            multi_podcast_mode = os.getenv('PODCAST_MODE', 'single') == 'multi'
            
            if multi_podcast_mode:
                logger.info("Initializing multi-database graph storage")
                # Create multi-database graph storage
                graph_config = self.provider_coordinator.graph_service.__dict__
                self.graph_service = MultiDatabaseGraphStorage(
                    uri=graph_config.get('uri'),
                    username=graph_config.get('username'),
                    password=graph_config.get('password'),
                    pool_size=graph_config.get('pool_size', 50),
                    max_retries=graph_config.get('max_retries', 5),
                    connection_timeout=graph_config.get('connection_timeout', 30.0)
                )
                
                # Update provider coordinator reference
                self.provider_coordinator.graph_service = self.graph_service
                
                # Create multi-database storage coordinator
                self.storage_coordinator = MultiDatabaseStorageCoordinator(
                    self.graph_service,
                    self.graph_enhancer,
                    self.config
                )
            else:
                # Use regular graph service from provider coordinator
                self.graph_service = self.provider_coordinator.graph_service
                
                # Initialize regular storage coordinator
                from src.seeding.components import StorageCoordinator
                self.storage_coordinator = StorageCoordinator(
                    self.graph_service,
                    self.graph_enhancer,
                    self.config
                )
            
            # Initialize pipeline executor with storage coordinator
            from src.seeding.multi_podcast_pipeline_executor import MultiPodcastPipelineExecutor
            self.pipeline_executor = MultiPodcastPipelineExecutor(
                self.config, 
                self.provider_coordinator,
                self.checkpoint_manager,
                self.storage_coordinator
            )
            
            logger.info("✓ All pipeline components initialized successfully")
            if multi_podcast_mode:
                logger.info("✓ Multi-podcast mode enabled")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize pipeline components: {e}")
            return False
    
    def process_vtt_files(self,
                         vtt_files: List[Any],
                         use_large_context: bool = True) -> Dict[str, Any]:
        """Process multiple VTT files with podcast context awareness.
        
        Args:
            vtt_files: List of VTTFile objects to process
            use_large_context: Whether to use large context models
            
        Returns:
            Summary dict with processing statistics
        """
        # Get base implementation
        summary = super().process_vtt_files(vtt_files, use_large_context)
        
        # Add multi-podcast specific information
        if os.getenv('PODCAST_MODE', 'single') == 'multi':
            summary['mode'] = 'multi_podcast'
            
            # Add podcast breakdown if available
            if hasattr(self, '_podcast_stats'):
                summary['podcasts_processed'] = self._podcast_stats
        
        return summary
    
    def cleanup(self):
        """Clean up resources including multi-database connections."""
        logger.info("Cleaning up pipeline resources...")
        
        # Close multi-database connections if applicable
        if hasattr(self.graph_service, 'close') and callable(self.graph_service.close):
            try:
                self.graph_service.close()
                logger.info("Closed multi-database connections")
            except Exception as e:
                logger.error(f"Error closing multi-database connections: {e}")
        
        # Call parent cleanup
        super().cleanup()