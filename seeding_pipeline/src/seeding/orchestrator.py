"""Main orchestrator for the podcast knowledge extraction pipeline."""

import os
import signal
import sys
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
import logging

from src.core.config import PipelineConfig, SeedingConfig
from src.core.exceptions import PipelineError, ConfigurationError
from src.factories.provider_factory import ProviderFactory
from src.providers.llm.base import LLMProvider
from src.providers.graph.base import GraphProvider
from src.providers.embeddings.base import EmbeddingProvider
from src.processing.segmentation import EnhancedPodcastSegmenter
from src.processing.extraction import KnowledgeExtractor
from src.processing.entity_resolution import EntityResolver
from src.processing.graph_analysis import GraphAnalyzer
from src.processing.discourse_flow import DiscourseFlowTracker
from src.processing.emergent_themes import EmergentThemeDetector
from src.processing.episode_flow import EpisodeFlowAnalyzer
from src.utils.memory import cleanup_memory, monitor_memory
from src.utils.resources import ProgressCheckpoint
from src.providers.graph.enhancements import GraphEnhancements
from src.utils.logging import get_logger, log_execution_time, log_error_with_context, log_metric

# Import new components
from src.seeding.components import (
    SignalManager,
    ProviderCoordinator,
    CheckpointManager,
    PipelineExecutor,
    StorageCoordinator
)

logger = get_logger(__name__)


class PodcastKnowledgePipeline:
    """Master orchestrator for the podcast knowledge extraction pipeline.
    
    This class coordinates all components of the pipeline using dependency injection
    and provides the main API for seeding the knowledge graph.
    """
    
    def __init__(self, config: Optional[Union[PipelineConfig, SeedingConfig]] = None):
        """Initialize the pipeline with configuration.
        
        Args:
            config: Pipeline or seeding configuration
        """
        self.config = config or SeedingConfig()
        self.factory = ProviderFactory()
        
        # Initialize components
        self.signal_manager = SignalManager()
        self.provider_coordinator = ProviderCoordinator(self.factory, self.config)
        self.checkpoint_manager = CheckpointManager(self.config)
        
        # The pipeline executor and storage coordinator will be initialized after providers
        self.pipeline_executor = None
        self.storage_coordinator = None
        
        # Provider instances - maintain references for backward compatibility
        self.llm_provider: Optional[LLMProvider] = None
        self.graph_provider: Optional[GraphProvider] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None
        
        # Processing components - maintain references for backward compatibility
        self.segmenter: Optional[EnhancedPodcastSegmenter] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.entity_resolver: Optional[EntityResolver] = None
        self.graph_analyzer: Optional[GraphAnalyzer] = None
        self.graph_enhancer: Optional[GraphEnhancements] = None
        self.discourse_flow_tracker: Optional[DiscourseFlowTracker] = None
        self.emergent_theme_detector: Optional[EmergentThemeDetector] = None
        self.episode_flow_analyzer: Optional[EpisodeFlowAnalyzer] = None
        
        # Checkpoint manager - maintain reference for backward compatibility
        self.checkpoint: Optional[ProgressCheckpoint] = None
        
        # Shutdown handling - now managed by signal_manager
        self._shutdown_requested = False
        self.signal_manager.setup(cleanup_callback=self.cleanup)
        
        # Initialize logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up comprehensive logging."""
        log_level = getattr(self.config, 'log_level', 'INFO')
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format
        )
        
        # Add file handler if log file specified
        if hasattr(self.config, 'log_file') and self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            logging.getLogger().addHandler(file_handler)
    
    def initialize_components(self, use_large_context: bool = True) -> bool:
        """Initialize all pipeline components.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        try:
            # Delegate to provider coordinator
            success = self.provider_coordinator.initialize_providers(use_large_context)
            if not success:
                return False
            
            # Set up backward compatibility references
            self.llm_provider = self.provider_coordinator.llm_provider
            self.graph_provider = self.provider_coordinator.graph_provider
            self.embedding_provider = self.provider_coordinator.embedding_provider
            
            self.segmenter = self.provider_coordinator.segmenter
            self.knowledge_extractor = self.provider_coordinator.knowledge_extractor
            self.entity_resolver = self.provider_coordinator.entity_resolver
            self.graph_analyzer = self.provider_coordinator.graph_analyzer
            self.graph_enhancer = self.provider_coordinator.graph_enhancer
            self.discourse_flow_tracker = self.provider_coordinator.discourse_flow_tracker
            self.emergent_theme_detector = self.provider_coordinator.emergent_theme_detector
            self.episode_flow_analyzer = self.provider_coordinator.episode_flow_analyzer
            
            # Set up checkpoint reference for backward compatibility
            self.checkpoint = self.checkpoint_manager.checkpoint
            
            # Initialize storage coordinator first
            self.storage_coordinator = StorageCoordinator(
                self.graph_provider,
                self.graph_enhancer,
                self.config
            )
            
            # Initialize pipeline executor with storage coordinator
            self.pipeline_executor = PipelineExecutor(
                self.config, 
                self.provider_coordinator,
                self.checkpoint_manager,
                self.storage_coordinator
            )
            
            # Verify all components are healthy
            if not self._verify_components_health():
                raise PipelineError("Component health check failed")
            
            logger.info("✓ All pipeline components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize pipeline components: {e}")
            return False
    
    @trace_method(name="pipeline.verify_components_health")
    def _verify_components_health(self) -> bool:
        """Verify all components are healthy."""
        # Delegate to provider coordinator
        return self.provider_coordinator.check_health()
    
    def cleanup(self):
        """Clean up resources and close connections."""
        logger.info("Cleaning up pipeline resources...")
        
        # Delegate to provider coordinator
        self.provider_coordinator.cleanup()
        
        # Clean up memory
        cleanup_memory()
        logger.info("Pipeline cleanup completed")
    
    @trace_method(name="pipeline.process_vtt_directory")
    def process_vtt_directory(self, 
                            directory_path: str,
                            pattern: str = "*.vtt",
                            recursive: bool = False,
                            use_large_context: bool = True) -> Dict[str, Any]:
        """Process VTT files from a directory.
        
        Args:
            directory_path: Path to directory containing VTT files
            pattern: File pattern to match (default: *.vtt)
            recursive: Whether to search subdirectories
            use_large_context: Whether to use large context models
            
        Returns:
            Processing summary
        """
        from src.seeding.transcript_ingestion import TranscriptIngestion
        
        ingestion = TranscriptIngestion(self.config)
        vtt_files = ingestion.scan_directory(
            Path(directory_path),
            pattern=pattern,
            recursive=recursive
        )
        
        return self.process_vtt_files(
            vtt_files,
            use_large_context=use_large_context
        )
    
    @trace_method(name="pipeline.process_vtt_files")
    def process_vtt_files(self,
                         vtt_files: List[Any],
                         use_large_context: bool = True) -> Dict[str, Any]:
        """Process multiple VTT files into knowledge graph.
        
        Args:
            vtt_files: List of VTTFile objects to process
            use_large_context: Whether to use large context models
            
        Returns:
            Summary dict with processing statistics
        """
        from src.seeding.transcript_ingestion import TranscriptIngestion
        
        # Ensure vtt_files is a list
        if not isinstance(vtt_files, list):
            vtt_files = [vtt_files]
        
        # Initialize components if not already done
        if not self.llm_provider:
            if not self.initialize_components(use_large_context):
                raise PipelineError("Failed to initialize pipeline components")
        
        summary = {
            'start_time': datetime.now().isoformat(),
            'files_processed': 0,
            'files_failed': 0,
            'total_segments': 0,
            'total_insights': 0,
            'total_entities': 0,
            'total_relationships': 0,
            'discovered_types': set(),
            'extraction_mode': 'schemaless' if getattr(self.config, 'use_schemaless_extraction', False) else 'fixed',
            'errors': []
        }
        
        ingestion = TranscriptIngestion(self.config)
        
        try:
            for vtt_file in vtt_files:
                if self._shutdown_requested:
                    logger.info("Shutdown requested, stopping processing")
                    break
                
                try:
                    result = ingestion.process_vtt_file(vtt_file)
                    
                    if result['status'] == 'success':
                        # Process the segments through knowledge extraction
                        if self.pipeline_executor:
                            # Create podcast and episode data structures
                            podcast_config = {
                                'id': f"podcast_{vtt_file.podcast_name.lower().replace(' ', '_')}",
                                'name': vtt_file.podcast_name,
                                'description': ''
                            }
                            
                            episode_data = result['episode']
                            
                            # Process segments through pipeline executor
                            extraction_result = self.pipeline_executor.process_vtt_segments(
                                podcast_config,
                                episode_data,
                                result['segments'],
                                use_large_context=use_large_context
                            )
                            
                            # Update summary with extraction results
                            if extraction_result:
                                summary['total_insights'] += len(extraction_result.get('insights', []))
                                summary['total_entities'] += len(extraction_result.get('entities', []))
                                summary['total_relationships'] += len(extraction_result.get('relationships', []))
                        
                        summary['files_processed'] += 1
                        summary['total_segments'] += result.get('segment_count', 0)
                    else:
                        summary['files_failed'] += 1
                        summary['errors'].append({
                            'file': str(vtt_file.path),
                            'error': result.get('error', 'Unknown error')
                        })
                    
                    # Add schemaless-specific metrics
                    if result.get('extraction_mode') == 'schemaless':
                        summary['total_relationships'] += result.get('total_relationships', 0)
                        if 'discovered_types' in result and isinstance(result['discovered_types'], list):
                            summary['discovered_types'].update(result['discovered_types'])
                    
                except Exception as e:
                    logger.error(f"Failed to process VTT file: {e}")
                    summary['files_failed'] += 1
                    summary['errors'].append({
                        'file': str(vtt_file.path) if hasattr(vtt_file, 'path') else 'unknown',
                        'error': str(e)
                    })
            
            summary['end_time'] = datetime.now().isoformat()
            summary['success'] = len(summary['errors']) == 0
            
            # Convert discovered types set to sorted list for JSON serialization
            if isinstance(summary['discovered_types'], set):
                summary['discovered_types'] = sorted(list(summary['discovered_types']))
            
            # Log final schema discovery summary if in schemaless mode
            if summary['extraction_mode'] == 'schemaless' and summary['discovered_types']:
                logger.info(f"Overall Schema Discovery - Found {len(summary['discovered_types'])} unique entity types across all VTT files")
            
            return summary
            
        finally:
            # Always cleanup
            self.cleanup()
    
    def resume_from_checkpoints(self) -> Dict[str, Any]:
        """Resume processing from checkpoints after interruption.
        
        Returns:
            Summary of resumed processing
        """
        logger.info("Resuming from checkpoints...")
        
        # Find incomplete episodes
        incomplete_episodes = []
        
        # This would need to be implemented based on checkpoint analysis
        # For now, return empty summary
        return {
            'resumed_episodes': 0,
            'message': 'Checkpoint recovery not fully implemented'
        }