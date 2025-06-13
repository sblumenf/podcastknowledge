"""
Semantic orchestrator for conversation-aware knowledge extraction.

This orchestrator uses semantic segmentation to process transcripts,
replacing the segment-by-segment approach with meaningful unit processing.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging
import os

from src.core.config import PipelineConfig, SeedingConfig
from src.core.exceptions import PipelineError, ConfigurationError
from src.seeding.orchestrator import VTTKnowledgeExtractor
from src.seeding.components import (
    SignalManager,
    ProviderCoordinator,
    CheckpointManager,
    StorageCoordinator
)
from src.seeding.components.semantic_pipeline_executor import SemanticPipelineExecutor
from src.utils.log_utils import get_logger
from src.utils.metrics import get_pipeline_metrics
from src.tracking import EpisodeTracker, generate_episode_id, calculate_file_hash

logger = get_logger(__name__)


class SemanticVTTKnowledgeExtractor(VTTKnowledgeExtractor):
    """
    Semantic orchestrator that extends the base orchestrator with conversation-aware processing.
    
    This orchestrator:
    1. Analyzes conversation structure before extraction
    2. Groups segments into meaningful units
    3. Extracts knowledge with better context
    4. Stores enhanced conversation structure in the graph
    """
    
    def __init__(self, config: Optional[Union[PipelineConfig, SeedingConfig]] = None):
        """
        Initialize semantic orchestrator.
        
        Args:
            config: Pipeline or seeding configuration
        """
        super().__init__(config)
        
        # Override with semantic processing flag
        self.semantic_processing_enabled = True
        
        # Semantic-specific components will be initialized in initialize_components
        self.semantic_pipeline_executor = None
        
        logger.info("Initialized Semantic VTT Knowledge Extractor")
    
    def initialize_components(self, use_large_context: bool = True) -> bool:
        """
        Initialize all pipeline components including semantic processors.
        
        Args:
            use_large_context: Whether to use large context models
            
        Returns:
            True if initialization successful
        """
        # Initialize base components first
        if not super().initialize_components(use_large_context):
            return False
        
        try:
            # Initialize semantic pipeline executor
            self.semantic_pipeline_executor = SemanticPipelineExecutor(
                self.config,
                self.provider_coordinator,
                self.checkpoint_manager,
                self.storage_coordinator
            )
            
            # Override the base pipeline executor with semantic version
            self.pipeline_executor = self.semantic_pipeline_executor
            
            logger.info("✓ Semantic processing components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize semantic components: {e}")
            return False
    
    def process_vtt_files(
        self,
        vtt_files: List[Any],
        use_large_context: bool = True,
        force_reprocess: bool = False,
        use_semantic_processing: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Process multiple VTT files with semantic segmentation.
        
        Args:
            vtt_files: List of VTTFile objects to process
            use_large_context: Whether to use large context models
            force_reprocess: Force reprocessing of already completed episodes
            use_semantic_processing: Override for semantic processing (defaults to True)
            
        Returns:
            Summary dict with processing statistics including semantic metrics
        """
        from src.seeding.transcript_ingestion import TranscriptIngestion
        
        # Use semantic processing by default unless explicitly disabled
        if use_semantic_processing is None:
            use_semantic_processing = self.semantic_processing_enabled
        
        # Get metrics instance
        metrics = get_pipeline_metrics()
        
        # Ensure vtt_files is a list
        if not isinstance(vtt_files, list):
            vtt_files = [vtt_files]
        
        # Initialize components if not already done
        if not self.llm_service:
            if not self.initialize_components(use_large_context):
                raise PipelineError("Failed to initialize pipeline components")
        
        summary = {
            'start_time': datetime.now().isoformat(),
            'processing_type': 'semantic' if use_semantic_processing else 'segment',
            'files_processed': 0,
            'files_failed': 0,
            'total_segments': 0,
            'total_meaningful_units': 0,
            'total_insights': 0,
            'total_entities': 0,
            'total_relationships': 0,
            'total_themes': 0,
            'conversation_structures': [],
            'discovered_types': set(),
            'extraction_mode': 'semantic_schemaless',
            'errors': []
        }
        
        ingestion = TranscriptIngestion(self.config)
        
        try:
            for vtt_file_path in vtt_files:
                if self._shutdown_requested:
                    logger.info("Shutdown requested, stopping processing")
                    break
                
                try:
                    # Convert Path to VTTFile if needed
                    if isinstance(vtt_file_path, Path):
                        vtt_file = ingestion._create_vtt_file(vtt_file_path)
                        if not vtt_file:
                            logger.warning(f"Failed to create VTTFile from {vtt_file_path}")
                            summary['files_failed'] += 1
                            continue
                    else:
                        vtt_file = vtt_file_path
                    
                    # Start timing
                    file_start_time = datetime.now().timestamp()
                    file_path = str(vtt_file.path if hasattr(vtt_file, 'path') else vtt_file)
                    
                    # Check if already processed
                    if self.episode_tracker and not force_reprocess:
                        podcast_id = vtt_file.podcast_name.lower().replace(' ', '_')
                        episode_id = generate_episode_id(file_path, podcast_id)
                        
                        if self.episode_tracker.is_episode_processed(episode_id):
                            logger.info(f"Episode {episode_id} already processed, skipping")
                            continue
                    
                    # Process VTT file
                    result = ingestion.process_vtt_file(vtt_file)
                    
                    if result['status'] == 'success':
                        # Create podcast and episode data
                        podcast_config = {
                            'id': f"podcast_{vtt_file.podcast_name.lower().replace(' ', '_')}",
                            'name': vtt_file.podcast_name,
                            'description': ''
                        }
                        
                        episode_data = result['episode']
                        
                        # Process with semantic or regular pipeline
                        if use_semantic_processing and self.semantic_pipeline_executor:
                            logger.info(f"Processing episode {episode_data['id']} with semantic segmentation")
                            extraction_result = self.semantic_pipeline_executor.process_vtt_segments(
                                podcast_config,
                                episode_data,
                                result['segments'],
                                use_large_context=use_large_context
                            )
                        else:
                            logger.info(f"Processing episode {episode_data['id']} with segment-by-segment extraction")
                            extraction_result = self.pipeline_executor.process_vtt_segments(
                                podcast_config,
                                episode_data,
                                result['segments'],
                                use_large_context=use_large_context
                            )
                        
                        # Update summary with results
                        if extraction_result and extraction_result.get('status') == 'success':
                            summary['files_processed'] += 1
                            summary['total_segments'] += result.get('segment_count', 0)
                            
                            # Semantic-specific metrics
                            if extraction_result.get('processing_type') == 'semantic':
                                summary['total_meaningful_units'] += extraction_result.get('meaningful_units', 0)
                                summary['total_themes'] += len(
                                    extraction_result.get('cross_unit_patterns', {})
                                    .get('theme_entity_connections', {})
                                )
                                
                                # Add conversation structure summary
                                summary['conversation_structures'].append({
                                    'episode_id': episode_data['id'],
                                    'unit_count': extraction_result.get('meaningful_units', 0),
                                    'completeness_rate': extraction_result.get('unit_statistics', {})
                                        .get('completeness_rate', 0),
                                    'average_unit_duration': extraction_result.get('unit_statistics', {})
                                        .get('average_duration', 0)
                                })
                            
                            # Common metrics
                            summary['total_insights'] += extraction_result.get('insights', 0)
                            summary['total_entities'] += extraction_result.get('entities', 0)
                            summary['total_relationships'] += extraction_result.get('relationships', 0)
                        
                        # Record metrics
                        file_end_time = datetime.now().timestamp()
                        metrics.record_file_processing(
                            file_path,
                            file_start_time,
                            file_end_time,
                            result.get('segment_count', 0),
                            success=True
                        )
                        
                        # Track episode completion
                        if self.episode_tracker and 'episode_id' in locals():
                            file_hash = calculate_file_hash(file_path)
                            
                            # Archive if enabled
                            archive_path = None
                            if getattr(self.config, 'archive_processed_vtt', True):
                                archive_path = self._archive_vtt_file(file_path, podcast_id)
                            
                            metadata = {
                                'podcast_id': podcast_id,
                                'processing_type': 'semantic' if use_semantic_processing else 'segment',
                                'segment_count': result.get('segment_count', 0),
                                'meaningful_units': extraction_result.get('meaningful_units', 0),
                                'entity_count': extraction_result.get('entities', 0),
                                'vtt_path': file_path,
                                'archive_path': str(archive_path) if archive_path else None
                            }
                            self.episode_tracker.mark_episode_complete(episode_id, file_hash, metadata)
                            
                    else:
                        summary['files_failed'] += 1
                        summary['errors'].append({
                            'file': str(vtt_file.path if hasattr(vtt_file, 'path') else vtt_file),
                            'error': result.get('error', 'Unknown error')
                        })
                        
                        # Record failure
                        file_end_time = datetime.now().timestamp()
                        metrics.record_file_processing(
                            file_path,
                            file_start_time,
                            file_end_time,
                            0,
                            success=False
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing file {vtt_file_path}: {e}", exc_info=True)
                    summary['files_failed'] += 1
                    summary['errors'].append({
                        'file': str(vtt_file_path),
                        'error': str(e)
                    })
            
            # Add final summary
            summary['end_time'] = datetime.now().isoformat()
            summary['discovered_types'] = list(summary['discovered_types'])
            
            # Calculate semantic processing effectiveness
            if summary['total_meaningful_units'] > 0:
                summary['segment_to_unit_ratio'] = (
                    summary['total_segments'] / summary['total_meaningful_units']
                )
            
            logger.info(
                f"Processing complete. Files: {summary['files_processed']}/{len(vtt_files)}, "
                f"Segments: {summary['total_segments']}, "
                f"Units: {summary['total_meaningful_units']}, "
                f"Entities: {summary['total_entities']}"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Fatal error in semantic processing: {e}", exc_info=True)
            summary['fatal_error'] = str(e)
            return summary
    
    def process_single_vtt(
        self,
        vtt_path: str,
        use_large_context: bool = True,
        force_semantic: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single VTT file with semantic processing.
        
        Args:
            vtt_path: Path to VTT file
            use_large_context: Whether to use large context models
            force_semantic: Force semantic processing
            
        Returns:
            Processing result
        """
        return self.process_vtt_files(
            [Path(vtt_path)],
            use_large_context=use_large_context,
            use_semantic_processing=force_semantic
        )
    
    def compare_processing_methods(
        self,
        vtt_path: str,
        use_large_context: bool = True
    ) -> Dict[str, Any]:
        """
        Process the same VTT file with both methods for comparison.
        
        Args:
            vtt_path: Path to VTT file
            use_large_context: Whether to use large context models
            
        Returns:
            Comparison results
        """
        logger.info(f"Comparing processing methods for {vtt_path}")
        
        # Process with segment-by-segment
        segment_result = self.process_vtt_files(
            [Path(vtt_path)],
            use_large_context=use_large_context,
            use_semantic_processing=False,
            force_reprocess=True
        )
        
        # Process with semantic segmentation
        semantic_result = self.process_vtt_files(
            [Path(vtt_path)],
            use_large_context=use_large_context,
            use_semantic_processing=True,
            force_reprocess=True
        )
        
        # Build comparison
        comparison = {
            'vtt_file': vtt_path,
            'segment_processing': {
                'total_segments': segment_result.get('total_segments', 0),
                'entities': segment_result.get('total_entities', 0),
                'insights': segment_result.get('total_insights', 0),
                'relationships': segment_result.get('total_relationships', 0)
            },
            'semantic_processing': {
                'total_segments': semantic_result.get('total_segments', 0),
                'meaningful_units': semantic_result.get('total_meaningful_units', 0),
                'entities': semantic_result.get('total_entities', 0),
                'insights': semantic_result.get('total_insights', 0),
                'relationships': semantic_result.get('total_relationships', 0),
                'themes': semantic_result.get('total_themes', 0)
            },
            'improvements': {
                'entity_reduction': 1 - (
                    semantic_result.get('total_entities', 1) / 
                    max(segment_result.get('total_entities', 1), 1)
                ),
                'segment_to_unit_ratio': semantic_result.get('segment_to_unit_ratio', 0)
            }
        }
        
        return comparison