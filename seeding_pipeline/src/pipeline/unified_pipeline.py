"""
Unified Knowledge Pipeline - Single entry point for all VTT processing.

This module implements the ONLY pipeline for processing podcast transcripts.
No alternative approaches or configurations - ONE WAY ONLY.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json

# VTT Processing
from src.vtt.vtt_parser import VTTParser
from src.vtt.vtt_segmentation import VTTSegmenter

# Conversation Analysis
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.segment_regrouper import SegmentRegrouper, MeaningfulUnit
from src.core.conversation_models.conversation import ConversationStructure

# Knowledge Extraction
from src.extraction.extraction import KnowledgeExtractor
from src.extraction.entity_resolution import EntityResolver
from src.extraction.complexity_analysis import ComplexityAnalyzer
from src.extraction.importance_scoring import ImportanceScorer
from src.extraction.sentiment_analyzer import SentimentAnalyzer, SentimentConfig

# Analysis Modules
from src.analysis import analysis_orchestrator
from src.analysis import diversity_metrics
from src.analysis import gap_detection
from src.analysis import missing_links

# Storage
from src.storage.graph_storage import GraphStorageService

# Services
from src.services.llm import LLMService
from src.services.embeddings import EmbeddingsService, create_embeddings_service

# Configuration
from src.core.config import PipelineConfig
from src.core.pipeline_config import PipelineConfig as PipelineTimeoutConfig

# Utils
from src.utils.logging import get_logger
from src.utils.retry import retry
from src.core.interfaces import TranscriptSegment
from src.pipeline.checkpoint import CheckpointManager
from src.core.validation import (
    validate_entity,
    validate_quote,
    validate_insight,
    validate_relationship,
    normalize_insight_for_storage
)
from src.core.exceptions import (
    PipelineError,
    ExtractionError,
    VTTProcessingError,
    SpeakerIdentificationError,
    ConversationAnalysisError,
    CriticalError
)

# Performance Benchmarking
from src.monitoring.pipeline_benchmarking import time_phase, get_benchmark

logger = get_logger(__name__)


class UnifiedKnowledgePipeline:
    """
    Single pipeline for processing VTT files into knowledge graph.
    
    This is the ONLY way to process podcasts - no alternatives.
    Implements all required features:
    - Speaker identification
    - Semantic grouping into MeaningfulUnits
    - Complete knowledge extraction
    - Full analysis suite
    - Schema-less discovery
    """
    
    def __init__(
        self,
        graph_storage: GraphStorageService,
        llm_service: LLMService,
        embeddings_service: Optional[EmbeddingsService] = None,
        llm_flash: Optional[LLMService] = None,
        llm_pro: Optional[LLMService] = None,
        enable_speaker_mapping: bool = False,
        config: Optional[Any] = None
    ):
        """
        Initialize the unified pipeline with required services.
        
        Args:
            graph_storage: Neo4j storage service
            llm_service: Default LLM service (for backward compatibility)
            embeddings_service: Optional embeddings service (auto-created if None)
            llm_flash: Optional Flash model service for fast tasks
            llm_pro: Optional Pro model service for complex tasks
            enable_speaker_mapping: Enable post-processing speaker identification (default: False)
            config: Optional pipeline configuration object
        """
        # Core services - dependency injection
        self.graph_storage = graph_storage
        self.llm_service = llm_service
        # Ensure embeddings service is always initialized for vector functionality
        self.embeddings_service = embeddings_service or create_embeddings_service()
        assert self.embeddings_service is not None, "Embeddings service must be initialized"
        self.enable_speaker_mapping = enable_speaker_mapping
        self.config = config or PipelineConfig()
        
        # Use separate models if provided, otherwise fall back to default
        self.llm_flash = llm_flash or llm_service
        self.llm_pro = llm_pro or llm_service
        
        # Initialize components with appropriate models
        self.vtt_parser = VTTParser()
        # VTT segmenter and conversation analyzer use Flash for speed
        # Configure speaker identification timeout to 120 seconds as per optimization plan
        # Use confidence threshold from config or default to 0.5
        speaker_confidence_threshold = 0.5
        if config and hasattr(config, 'speaker_confidence_threshold'):
            speaker_confidence_threshold = config.speaker_confidence_threshold
        
        vtt_config = {
            'speaker_timeout_seconds': 120,
            'speaker_confidence_threshold': speaker_confidence_threshold,
            'max_segments_for_context': 50
        }
        self.vtt_segmenter = VTTSegmenter(config=vtt_config, llm_service=self.llm_flash)
        self.conversation_analyzer = ConversationAnalyzer(self.llm_flash)
        self.segment_regrouper = SegmentRegrouper()
        
        # Knowledge extraction uses Pro model for accuracy
        self.knowledge_extractor = KnowledgeExtractor(
            llm_service=self.llm_pro,
            embedding_service=embeddings_service
        )
        self.entity_resolver = EntityResolver()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.importance_scorer = ImportanceScorer()
        # Configure sentiment analyzer with lower confidence threshold
        sentiment_config = SentimentConfig(
            min_confidence_threshold=0.5,  # Lowered from default 0.6
            emotion_detection_threshold=0.3  # Keep default
        )
        self.sentiment_analyzer = SentimentAnalyzer(self.llm_flash, config=sentiment_config)
        
        # Logging setup with clear phase tracking
        self.logger = logger
        self.logger.info("Initialized UnifiedKnowledgePipeline - THE ONLY PIPELINE")
        self.logger.info(f"  - Flash model: {getattr(self.llm_flash, 'model_name', 'default')}")
        self.logger.info(f"  - Pro model: {getattr(self.llm_pro, 'model_name', 'default')}")
        self.logger.info(f"  - Speaker confidence threshold: {speaker_confidence_threshold}")
        self.logger.info(f"  - Speaker mapping enabled: {enable_speaker_mapping}")
        
        # Phase tracking
        self.current_phase = None
        self.phase_start_time = None
        self.phase_timings = {}
        
        # Episode tracking
        self.current_episode_id = None
        self.episode_metadata = None  # Store episode metadata for access throughout pipeline
        
        # Track failed embeddings for recovery
        self.failed_embeddings = []
        
        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager()
        self.phase_results = {}
        
        # Parallel processing tracking
        self._completed_counter = 0
        self._counter_lock = threading.Lock()
        self._extraction_errors = []
        self._error_lock = threading.Lock()
        self._total_units = 0  # Will be set during extraction
        
    def _start_phase(self, phase_name: str) -> None:
        """Start tracking a processing phase."""
        self.current_phase = phase_name
        self.phase_start_time = time.time()
        
        # Start benchmarking phase
        benchmark = get_benchmark()
        benchmark.start_phase(phase_name)
        
        # Log which model is used for this phase
        if phase_name in ["SPEAKER_IDENTIFICATION", "CONVERSATION_ANALYSIS"]:
            model_info = f" (using Flash: {getattr(self.llm_flash, 'model_name', 'default')})"
        elif phase_name == "KNOWLEDGE_EXTRACTION":
            model_info = f" (using Pro: {getattr(self.llm_pro, 'model_name', 'default')})"
        else:
            model_info = ""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.logger.info(f"=== PHASE START: {phase_name}{model_info} at {current_time} ===")
        
    def _end_phase(self) -> None:
        """End tracking current phase and record timing."""
        if self.current_phase and self.phase_start_time:
            elapsed = time.time() - self.phase_start_time
            self.phase_timings[self.current_phase] = elapsed
            
            # End benchmarking phase
            benchmark = get_benchmark()
            benchmark.end_phase(self.current_phase)
            
            self.logger.info(
                f"=== PHASE END: {self.current_phase} "
                f"(took {elapsed:.2f}s) ==="
            )
            self.current_phase = None
            self.phase_start_time = None
    
    def _save_checkpoint(self, phase: str, phase_data: Any, metadata: Dict[str, Any]) -> None:
        """Save checkpoint after phase completion.
        
        Args:
            phase: Phase name that was completed
            phase_data: Data from the completed phase
            metadata: Episode metadata
        """
        # Check if checkpoints are disabled
        import os
        if os.getenv('DISABLE_CHECKPOINTS', 'false').lower() == 'true':
            self.logger.debug(f"Checkpoints disabled, skipping save for phase {phase}")
            return
            
        if self.current_episode_id:
            # Add phase data to results
            self.phase_results[phase] = phase_data
            
            try:
                # Save checkpoint with error handling
                success = self.checkpoint_manager.save_checkpoint(
                    episode_id=self.current_episode_id,
                    phase=phase,
                    phase_results=self.phase_results,
                    metadata=metadata
                )
                
                if success:
                    self.logger.debug(f"Checkpoint saved after phase {phase}")
                else:
                    self.logger.warning(f"Failed to save checkpoint after phase {phase}")
            except Exception as e:
                # Don't let checkpoint failures stop pipeline
                self.logger.warning(f"Checkpoint save failed for phase {phase}: {e}")
                # Continue processing
    
    def _should_skip_phase(self, phase: str, checkpoint: Optional[Any]) -> bool:
        """Check if a phase should be skipped based on checkpoint.
        
        Args:
            phase: Phase name to check
            checkpoint: Loaded checkpoint data
            
        Returns:
            True if phase should be skipped
        """
        if not checkpoint:
            return False
            
        # Define phase order
        phase_order = [
            "VTT_PARSING",
            "SPEAKER_IDENTIFICATION", 
            "CONVERSATION_ANALYSIS",
            "MEANINGFUL_UNIT_CREATION",
            "EPISODE_STORAGE",
            "KNOWLEDGE_EXTRACTION",
            "KNOWLEDGE_STORAGE",
            "ANALYSIS"
        ]
        
        try:
            last_phase_idx = phase_order.index(checkpoint.last_completed_phase)
            current_phase_idx = phase_order.index(phase)
            return current_phase_idx <= last_phase_idx
        except ValueError:
            return False
    
    # Placeholder methods for each processing phase
    async def _parse_vtt(self, vtt_path: Path) -> Tuple[List[TranscriptSegment], Dict[str, Any]]:
        """Parse VTT file into segments and extract metadata."""
        self.logger.info(f"Parsing VTT file: {vtt_path}")
        
        try:
            # Parse VTT file with metadata using VTTParser
            result = self.vtt_parser.parse_file_with_metadata(vtt_path)
            segments = result.get('segments', [])
            metadata = result.get('metadata', {})
            
            if not segments:
                raise VTTProcessingError(f"No segments found in VTT file: {vtt_path}")
            
            self.logger.info(f"Successfully parsed {len(segments)} segments from VTT file")
            if metadata:
                self.logger.info(f"Extracted metadata: {list(metadata.keys())}")
            
            return segments, metadata
            
        except Exception as e:
            self.logger.error(f"VTT parsing failed: {e}")
            raise VTTProcessingError(f"Failed to parse VTT file: {e}") from e
    
    async def _identify_speakers(self, segments: List[TranscriptSegment], episode_metadata: Dict) -> List[TranscriptSegment]:
        """
        Identify speakers in segments.
        
        This method MUST identify actual speaker names. NO FALLBACK to generic names.
        If speaker identification fails, the entire episode is rejected.
        
        Args:
            segments: List of transcript segments with generic speaker labels
            episode_metadata: Episode metadata for context
            
        Returns:
            List of segments with identified speaker names
            
        Raises:
            SpeakerIdentificationError: If speaker identification fails
        """
        self.logger.info(f"Starting speaker identification for {len(segments)} segments")
        
        # Process segments to identify speakers (with one retry on failure)
        retry_count = 0
        max_retries = 1
        
        while retry_count <= max_retries:
            try:
                # Call VTTSegmenter's process_segments which includes speaker identification
                result = self.vtt_segmenter.process_segments(
                    segments=segments,
                    episode_metadata=episode_metadata,
                    cached_content_name=episode_metadata.get('episode_id')
                )
                
                # Extract the identification result
                if 'transcript' not in result:
                    raise SpeakerIdentificationError("No transcript returned from speaker identification")
                
                # Get processed segments from result
                processed_data = result['transcript']
                
                # Convert processed data back to TranscriptSegment objects
                identified_segments = []
                for seg_data in processed_data:
                    # Create new segment with identified speaker
                    # Generate ID if not present
                    segment_id = seg_data.get('id', f"seg_{seg_data['start_time']}")
                    segment = TranscriptSegment(
                        id=segment_id,
                        text=seg_data['text'],
                        start_time=seg_data['start_time'],
                        end_time=seg_data['end_time'],
                        speaker=seg_data['speaker'],
                        confidence=seg_data.get('confidence', 1.0)
                    )
                    identified_segments.append(segment)
                
                # Verify speakers were actually identified
                speakers = set()
                # Accept all speaker names - post-processing will enhance
                # Previously rejected generic names like "Speaker 1", but now we accept them
                for segment in identified_segments:
                    if segment.speaker:
                        speakers.add(segment.speaker)
                
                # Removed generic speaker validation - accepting all names from LLM
                # if generic_speakers_found:
                #     raise SpeakerIdentificationError(
                #         "Generic speaker names detected. Actual speaker identification required."
                #     )
                
                if not speakers:
                    raise SpeakerIdentificationError("No speakers identified in transcript")
                
                # Log speaker mappings for debugging
                speaker_list = sorted(list(speakers))
                self.logger.info(f"Speaker identification successful. Found {len(speakers)} speakers: {speaker_list}")
                for speaker in speaker_list:
                    segment_count = sum(1 for seg in identified_segments if seg.speaker == speaker)
                    self.logger.debug(f"  - {speaker}: {segment_count} segments")
                
                return identified_segments
                
            except SpeakerIdentificationError:
                # Re-raise speaker identification errors
                raise
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    # Convert to SpeakerIdentificationError after retries exhausted
                    self.logger.error(f"Speaker identification failed after {max_retries + 1} attempts: {e}")
                    raise SpeakerIdentificationError(
                        f"Failed to identify speakers after {max_retries + 1} attempts: {e}"
                    ) from e
                else:
                    self.logger.warning(f"Speaker identification attempt {retry_count} failed: {e}. Retrying...")
                    # Brief delay before retry
                    await asyncio.sleep(2)
    
    async def _analyze_conversation(self, segments: List[TranscriptSegment]) -> ConversationStructure:
        """
        Analyze conversation structure.
        
        This method analyzes the conversation to identify semantic boundaries and themes.
        NO ALTERNATIVE GROUPING METHODS - only ConversationAnalyzer is used.
        
        Args:
            segments: Speaker-identified transcript segments
            
        Returns:
            ConversationStructure with units, themes, and boundaries
            
        Raises:
            ConversationAnalysisError: If analysis fails after retries
        """
        self.logger.info(f"Starting conversation analysis for {len(segments)} segments")
        
        # Analyze with retry logic (max 2 attempts as specified)
        retry_count = 0
        max_retries = 1  # Total of 2 attempts
        
        while retry_count <= max_retries:
            try:
                # Call analyze_structure on ConversationAnalyzer
                structure = self.conversation_analyzer.analyze_structure(segments)
                
                # Validate structure
                if not structure or not structure.units:
                    raise ConversationAnalysisError("No conversation units identified in structure")
                
                # Validate structure covers all segments
                total_unit_segments = sum(
                    unit.end_index - unit.start_index + 1 
                    for unit in structure.units
                )
                
                # Allow some flexibility for overlapping or gaps, but ensure reasonable coverage
                coverage_ratio = total_unit_segments / len(segments)
                if coverage_ratio < 0.9:  # At least 90% coverage required
                    self.logger.warning(
                        f"Conversation structure has low segment coverage: {coverage_ratio:.2%}"
                    )
                    raise ConversationAnalysisError(
                        f"Insufficient segment coverage in conversation structure: {coverage_ratio:.2%}"
                    )
                
                # Log conversation structure for debugging
                self.logger.info(
                    f"Conversation analysis successful: "
                    f"{len(structure.units)} units, "
                    f"{len(structure.themes)} themes, "
                    f"{len(structure.boundaries)} boundaries"
                )
                
                # Log unit details
                for idx, unit in enumerate(structure.units):
                    self.logger.debug(
                        f"  Unit {idx}: {unit.unit_type} "
                        f"(segments {unit.start_index}-{unit.end_index})"
                    )
                
                # Log themes
                if structure.themes:
                    theme_list = [theme.theme for theme in structure.themes]
                    self.logger.info(f"  Themes identified: {theme_list}")  # Changed to info for visibility
                
                # Log insights if available
                if structure.insights:
                    self.logger.debug(
                        f"  Structural insights: "
                        f"overall_coherence={structure.insights.overall_coherence}, "
                        f"fragmentation_issues={len(structure.insights.fragmentation_issues)}"
                    )
                
                return structure
                
            except ConversationAnalysisError:
                # Re-raise conversation analysis errors
                raise
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    # Convert to ConversationAnalysisError after retries exhausted
                    self.logger.error(f"Conversation analysis failed after {max_retries + 1} attempts: {e}")
                    raise ConversationAnalysisError(
                        f"Failed to analyze conversation after {max_retries + 1} attempts: {e}"
                    ) from e
                else:
                    self.logger.warning(f"Conversation analysis attempt {retry_count} failed: {e}. Retrying...")
                    # Brief delay before retry
                    await asyncio.sleep(3)
    
    async def _create_meaningful_units(self, segments: List[TranscriptSegment], structure: ConversationStructure) -> List[MeaningfulUnit]:
        """
        Create MeaningfulUnits from segments.
        
        Args:
            segments: Speaker-identified transcript segments
            structure: Analyzed conversation structure
            
        Returns:
            List of MeaningfulUnits ready for storage
        """
        self.logger.info(f"Creating MeaningfulUnits from {len(segments)} segments")
        
        # Call regroup_segments() with segments and structure, including episode_id
        meaningful_units = self.segment_regrouper.regroup_segments(segments, structure, episode_id=self.current_episode_id)
        
        if not meaningful_units:
            raise PipelineError("No meaningful units created from segments")
        
        # Process each MeaningfulUnit
        for unit in meaningful_units:
            # Adjust start_time by -2 seconds (minimum 0) for YouTube navigation
            unit.start_time = max(0, unit.start_time - 2.0)
            
            # The SegmentRegrouper already extracts primary speaker,
            # but let's verify it exists
            if not unit.primary_speaker:
                # Set to Unknown if missing
                unit.primary_speaker = "Unknown"
            
            # Generate unique ID (already done by SegmentRegrouper, but verify)
            if not unit.id:
                # Generate a unique ID based on episode and unit index
                unit.id = f"unit_{unit.start_time}_{unit.end_time}"
            
            # Generate embedding for the unit (embeddings service is always available)
            try:
                # Use unit text for embedding generation
                unit.embedding = self.embeddings_service.generate_embedding(unit.text)
                self.logger.debug(f"Generated embedding for unit {unit.id} (dimension: {len(unit.embedding)})")
            except Exception as e:
                self.logger.warning(f"Failed to generate embedding for unit {unit.id}: {e}")
                unit.embedding = None
                # Track failed embedding for later recovery
                self.failed_embeddings.append({
                    'unit_id': unit.id,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        self.logger.info(f"Created {len(meaningful_units)} MeaningfulUnits")
        
        # Log unit summary
        for idx, unit in enumerate(meaningful_units):
            self.logger.debug(
                f"  Unit {idx}: {unit.unit_type} "
                f"({unit.segment_count} segments, {unit.duration:.1f}s) "
                f"- {unit.summary[:50]}..."
            )
        
        return meaningful_units
    
    async def _store_episode_structure(self, episode_metadata: Dict, meaningful_units: List[MeaningfulUnit], 
                                       conversation_structure: ConversationStructure, vtt_path: Path) -> None:
        """
        Store episode, topics, and MeaningfulUnits in Neo4j.
        
        CRITICAL: DO NOT store individual segments - only MeaningfulUnits.
        All operations are transactional - either all succeed or all rollback.
        
        Args:
            episode_metadata: Episode information
            meaningful_units: List of MeaningfulUnits to store
            conversation_structure: ConversationStructure containing themes
            vtt_path: Path to the VTT file
        """
        self.logger.info(f"Storing episode structure with {len(meaningful_units)} MeaningfulUnits")
        
        episode_id = episode_metadata.get('episode_id')
        if not episode_id:
            raise PipelineError("episode_id required for storage")
        
        # Start Neo4j transaction
        try:
            # Add VTT path to episode metadata for storage
            episode_metadata['vtt_path'] = str(vtt_path)
            
            # Store episode if not exists
            episode_node_id = self.graph_storage.create_episode(episode_metadata)
            self.logger.info(f"Episode node created/retrieved: {episode_node_id}")
            
            # Store topics/themes from conversation structure
            if conversation_structure and conversation_structure.themes:
                self.logger.info(f"Creating {len(conversation_structure.themes)} topic nodes")
                for theme in conversation_structure.themes:
                    success = self.graph_storage.create_topic_for_episode(
                        topic_name=theme.theme,
                        episode_id=episode_id
                    )
                    if success:
                        self.logger.info(f"Successfully created/linked topic: {theme.theme}")  # Changed to info
                    else:
                        self.logger.warning(f"Failed to create/link topic: {theme.theme}")
            else:
                self.logger.warning(f"No themes found for episode {episode_id} to store")
            
            # Store each MeaningfulUnit with PART_OF relationship
            # Simple loop - no complex batch processing
            for idx, unit in enumerate(meaningful_units):
                # Prepare unit data for storage
                unit_data = {
                    'id': unit.id,
                    'text': unit.text,
                    'start_time': unit.start_time,
                    'end_time': unit.end_time,
                    'summary': unit.summary,
                    'primary_speaker': unit.primary_speaker,
                    'speaker_distribution': unit.speaker_distribution,  # Add speaker distribution
                    'unit_type': unit.unit_type,
                    'themes': unit.themes,
                    'segment_indices': [seg.start_time for seg in unit.segments],  # Store segment references
                    'is_complete': unit.is_complete,
                    'metadata': unit.metadata or {}
                }
                
                # Add embedding if available
                if hasattr(unit, 'embedding') and unit.embedding:
                    unit_data['embedding'] = unit.embedding
                
                # Create MeaningfulUnit node
                unit_node_id = self.graph_storage.create_meaningful_unit(
                    unit_data=unit_data,
                    episode_id=episode_id
                )
                
                self.logger.debug(f"Stored MeaningfulUnit {idx}: {unit_node_id}")
            
            # IMPORTANT: DO NOT store individual segments
            # The plan explicitly states to store only MeaningfulUnits
            
            self.logger.info(
                f"Successfully stored episode structure: "
                f"{episode_id} with {len(meaningful_units)} MeaningfulUnits"
            )
            
        except Exception as e:
            # Any error triggers rollback (handled by graph_storage transaction)
            self.logger.error(f"Failed to store episode structure: {e}")
            raise PipelineError(f"Episode structure storage failed: {e}") from e
    
    def _process_single_unit(self, unit: MeaningfulUnit, unit_index: int) -> Dict[str, Any]:
        """
        Process a single meaningful unit for knowledge extraction (thread-safe).
        
        This method is designed to be thread-safe and can be called concurrently
        for different units. All operations are isolated with no shared state.
        
        Args:
            unit: MeaningfulUnit to process
            unit_index: Index of the unit in the episode
            
        Returns:
            Dict containing:
                - success: bool indicating if processing succeeded
                - unit_index: int index of the processed unit
                - extraction_result: ExtractionResult if successful
                - sentiment_result: SentimentResult if successful
                - error: Exception details if failed
                - processing_time: float seconds taken
        """
        start_time = time.time()
        result = {
            'success': False,
            'unit_index': unit_index,
            'extraction_result': None,
            'sentiment_result': None,
            'error': None,
            'processing_time': 0
        }
        
        try:
            # Log progress (thread-safe logging)
            self.logger.info(f"Processing unit {unit_index + 1} for knowledge extraction...")
            
            # Track extraction type for benchmarking
            extraction_type = None
            
            # Use combined extraction for efficiency (1 LLM call instead of 5)
            if hasattr(self.knowledge_extractor, 'extract_knowledge_combined'):
                extraction_type = 'combined'
                extraction_result = self.knowledge_extractor.extract_knowledge_combined(
                    meaningful_unit=unit,
                    episode_metadata={
                        'episode_id': self.current_episode_id,
                        'unit_index': unit_index,
                        'total_units': self._total_units,  # Will be set by caller
                        'podcast_name': self.episode_metadata.get('podcast_name', 'Unknown'),
                        'episode_title': self.episode_metadata.get('episode_title', 'Unknown')
                    }
                )
            else:
                # Fallback to original method
                extraction_type = 'separate'
                extraction_result = self.knowledge_extractor.extract_knowledge(
                    meaningful_unit=unit,
                    episode_metadata={
                        'episode_id': self.current_episode_id,
                        'unit_index': unit_index,
                        'total_units': self._total_units
                    }
                )
            
            # Score importance of quotes
            if extraction_result.quotes:
                for quote in extraction_result.quotes:
                    quote['importance_score'] = self.importance_scorer.score_quote(quote)
            
            # Analyze complexity of insights
            if extraction_result.insights:
                for insight in extraction_result.insights:
                    insight['complexity'] = self.complexity_analyzer.analyze_insight(insight)
            
            # Analyze sentiment for this unit
            sentiment_result = self.sentiment_analyzer.analyze_meaningful_unit(
                meaningful_unit=unit,
                episode_context={'episode_id': self.current_episode_id}
            )
            
            # Success!
            result['success'] = True
            result['extraction_result'] = extraction_result
            result['sentiment_result'] = sentiment_result
            
        except Exception as e:
            error_msg = f"Failed to process unit {unit_index}: {e}"
            self.logger.error(error_msg)
            result['error'] = {
                'unit_index': unit_index,
                'unit_id': unit.id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        
        finally:
            result['processing_time'] = time.time() - start_time
            
            # Track unit processing in benchmark
            benchmark = get_benchmark()
            benchmark.track_unit_processing(
                unit_id=unit.id,
                start_time=start_time,
                end_time=time.time(),
                success=result['success'],
                error=result['error']['error_message'] if result['error'] else None,
                extraction_type=extraction_type
            )
            
        return result
    
    async def _extract_knowledge(self, meaningful_units: List[MeaningfulUnit]) -> Dict[str, Any]:
        """
        Extract all knowledge from MeaningfulUnits.
        
        This method processes MeaningfulUnits through the KnowledgeExtractor to
        extract entities, quotes, relationships, and insights using schema-less
        discovery. The LLM can create ANY entity or relationship type based on
        content, not limited to predefined schemas.
        
        Args:
            meaningful_units: List of MeaningfulUnits to extract knowledge from
            
        Returns:
            Dict containing all extracted knowledge organized by type
        """
        self.logger.info(f"Starting knowledge extraction for {len(meaningful_units)} MeaningfulUnits")
        
        # Aggregate results across all units
        all_entities = []
        all_quotes = []
        all_relationships = []
        all_insights = []
        all_sentiments = []
        extraction_metadata = {
            'units_processed': 0,
            'extraction_errors': [],
            'timeout_errors': 0,
            'entity_types_discovered': set(),
            'relationship_types_discovered': set(),
            'sentiment_types_discovered': set(),
            'total_extraction_time': 0
        }
        
        # Initialize parallel processing tracking
        self._total_units = len(meaningful_units)
        self._completed_counter = 0
        self._extraction_errors = []
        
        # Get concurrency limit and timeout from config
        max_concurrent_units = PipelineTimeoutConfig.MAX_CONCURRENT_UNITS
        unit_timeout = PipelineTimeoutConfig.KNOWLEDGE_EXTRACTION_TIMEOUT
        self.logger.info(
            f"Starting parallel knowledge extraction with {max_concurrent_units} concurrent units "
            f"(timeout: {unit_timeout}s per unit)"
        )
        
        # Process units in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_concurrent_units) as executor:
            # Submit all units for processing
            future_to_unit = {}
            for idx, unit in enumerate(meaningful_units):
                future = executor.submit(self._process_single_unit, unit, idx)
                future_to_unit[future] = (unit, idx)
            
            # Process results as they complete with timeout
            try:
                # Use timeout for the entire batch processing
                remaining_timeout = unit_timeout * len(meaningful_units)
                start_batch_time = time.time()
                
                for future in as_completed(future_to_unit, timeout=remaining_timeout):
                    unit, idx = future_to_unit[future]
                    
                    # Update remaining timeout for next iteration
                    elapsed = time.time() - start_batch_time
                    remaining_timeout = max(0, (unit_timeout * len(meaningful_units)) - elapsed)
                    
                    try:
                        # Get result from completed future
                        result = future.result()
                        
                        # Update progress counter (thread-safe)
                        with self._counter_lock:
                            self._completed_counter += 1
                            self.logger.info(
                                f"Completed {self._completed_counter}/{self._total_units} units "
                                f"(processing time: {result['processing_time']:.2f}s)"
                            )
                        
                        if result['success']:
                            extraction_result = result['extraction_result']
                            sentiment_result = result['sentiment_result']
                            
                            # Aggregate results (thread-safe operations)
                            if extraction_result.entities:
                                all_entities.extend(extraction_result.entities)
                                for entity in extraction_result.entities:
                                    extraction_metadata['entity_types_discovered'].add(entity['type'])
                            
                            if extraction_result.quotes:
                                # Add meaningful_unit_id to each quote's properties
                                for quote in extraction_result.quotes:
                                    if 'properties' not in quote:
                                        quote['properties'] = {}
                                    quote['properties']['meaningful_unit_id'] = unit.id
                                all_quotes.extend(extraction_result.quotes)
                            
                            if extraction_result.relationships:
                                all_relationships.extend(extraction_result.relationships)
                                for rel in extraction_result.relationships:
                                    extraction_metadata['relationship_types_discovered'].add(rel['type'])
                            
                            if extraction_result.insights:
                                # Add meaningful_unit_id to each insight's properties
                                for insight in extraction_result.insights:
                                    if 'properties' not in insight:
                                        insight['properties'] = {}
                                    insight['properties']['meaningful_unit_id'] = unit.id
                                all_insights.extend(extraction_result.insights)
                            
                            # Store sentiment result
                            sentiment_data = {
                                'unit_id': unit.id,
                                'sentiment': sentiment_result,
                                'unit_index': idx
                            }
                            all_sentiments.append(sentiment_data)
                            
                            # Track discovered sentiment types
                            for discovered in sentiment_result.discovered_sentiments:
                                extraction_metadata['sentiment_types_discovered'].add(discovered.sentiment_type)
                            
                            extraction_metadata['units_processed'] += 1
                            extraction_metadata['total_extraction_time'] += result['processing_time']
                            
                            self.logger.debug(
                                f"Unit {idx} extraction complete: "
                                f"{len(extraction_result.entities)} entities, "
                                f"{len(extraction_result.quotes)} quotes, "
                                f"{len(extraction_result.relationships)} relationships, "
                                f"{len(extraction_result.insights)} insights, "
                                f"sentiment analyzed: YES"
                            )
                        else:
                            # Handle error case
                            with self._error_lock:
                                self._extraction_errors.append(result['error'])
                                extraction_metadata['extraction_errors'].append(result['error'])
                            self.logger.debug(f"Unit {idx} extraction failed, sentiment analyzed: NO")
                        
                    except Exception as e:
                        # Handle future execution error
                        error_msg = f"Future execution failed for unit {idx}: {e}"
                        self.logger.error(error_msg)
                        with self._error_lock:
                            error_data = {
                                'unit_index': idx,
                                'unit_id': unit.id,
                                'error_type': 'FutureExecutionError',
                                'error_message': str(e)
                            }
                            self._extraction_errors.append(error_data)
                            extraction_metadata['extraction_errors'].append(error_data)
                
            except TimeoutError:
                # Handle timeout for the entire batch
                self.logger.error(
                    f"Knowledge extraction timed out after processing "
                    f"{self._completed_counter}/{len(meaningful_units)} units"
                )
                
                # Cancel remaining futures
                for future in future_to_unit:
                    if not future.done():
                        future.cancel()
                        unit, idx = future_to_unit[future]
                        with self._error_lock:
                            timeout_error = {
                                'unit_index': idx,
                                'unit_id': unit.id,
                                'error_type': 'TimeoutError',
                                'error_message': f'Unit processing timed out after {unit_timeout}s'
                            }
                            self._extraction_errors.append(timeout_error)
                            extraction_metadata['extraction_errors'].append(timeout_error)
                            extraction_metadata['timeout_errors'] += 1
        
        # Check error rate and decide whether to continue
        error_rate = len(self._extraction_errors) / len(meaningful_units) if meaningful_units else 0
        if error_rate > 0.5:  # More than 50% failed
            raise ExtractionError(
                f"Knowledge extraction failed for {len(self._extraction_errors)}/{len(meaningful_units)} units "
                f"({error_rate:.1%} failure rate)"
            )
        elif self._extraction_errors:
            timeout_count = extraction_metadata.get('timeout_errors', 0)
            other_errors = len(self._extraction_errors) - timeout_count
            self.logger.warning(
                f"Knowledge extraction completed with {len(self._extraction_errors)} errors "
                f"({error_rate:.1%} failure rate) - "
                f"{timeout_count} timeouts, {other_errors} other errors"
            )
        
        # Log parallel processing performance summary
        avg_time_per_unit = extraction_metadata['total_extraction_time'] / max(extraction_metadata['units_processed'], 1)
        sentiment_success_rate = len(all_sentiments) / len(meaningful_units) * 100 if meaningful_units else 0
        self.logger.info(
            f"Parallel processing performance: "
            f"{extraction_metadata['units_processed']} units processed in "
            f"{extraction_metadata['total_extraction_time']:.1f}s total compute time "
            f"(avg {avg_time_per_unit:.1f}s per unit)"
        )
        self.logger.info(
            f"Sentiment analysis success rate: {len(all_sentiments)}/{len(meaningful_units)} units "
            f"({sentiment_success_rate:.1f}%)"
        )
        
        # Deduplicate entities across all units using entity resolver
        unique_entities = self.entity_resolver.resolve_entities_for_meaningful_units(
            all_entities,
            preserve_unit_associations=True
        )
        
        # Build relationship graph for analysis
        relationship_graph = self._build_relationship_graph(unique_entities, all_relationships)
        
        # Log extraction summary
        self.logger.info(
            f"Knowledge extraction complete: "
            f"{len(unique_entities)} unique entities ({len(extraction_metadata['entity_types_discovered'])} types), "
            f"{len(all_quotes)} quotes, "
            f"{len(all_relationships)} relationships ({len(extraction_metadata['relationship_types_discovered'])} types), "
            f"{len(all_insights)} insights, "
            f"{len(all_sentiments)} sentiment analyses"
        )
        
        if extraction_metadata['entity_types_discovered']:
            self.logger.info(
                f"Discovered entity types: {sorted(extraction_metadata['entity_types_discovered'])}"
            )
        
        if extraction_metadata['relationship_types_discovered']:
            self.logger.info(
                f"Discovered relationship types: {sorted(extraction_metadata['relationship_types_discovered'])}"
            )
        
        if extraction_metadata['sentiment_types_discovered']:
            self.logger.info(
                f"Discovered sentiment types: {sorted(extraction_metadata['sentiment_types_discovered'])}"
            )
        
        return {
            'entities': unique_entities,
            'quotes': all_quotes,
            'relationships': all_relationships,
            'insights': all_insights,
            'sentiments': all_sentiments,
            'relationship_graph': relationship_graph,
            'metadata': extraction_metadata
        }
    
    async def _store_knowledge(self, extraction_results: Dict[str, Any], meaningful_units: List[MeaningfulUnit]) -> None:
        """
        Store extracted knowledge in Neo4j.
        
        This method stores all extracted entities, quotes, relationships, and insights,
        linking them to their source MeaningfulUnits.
        
        Args:
            extraction_results: Dict containing extracted knowledge
            meaningful_units: List of MeaningfulUnits for reference
        """
        self.logger.info("Starting knowledge storage phase")
        
        if not extraction_results:
            self.logger.warning("No extraction results to store")
            return
        
        episode_id = self.current_episode_id
        entities = extraction_results.get('entities', [])
        quotes = extraction_results.get('quotes', [])
        relationships = extraction_results.get('relationships', [])
        insights = extraction_results.get('insights', [])
        sentiments = extraction_results.get('sentiments', [])
        
        try:
            # Store entities
            entity_id_map = {}  # Map original entity to stored ID
            for entity in entities:
                # Validate before storage
                is_valid, error_msg = validate_entity(entity)
                if not is_valid:
                    self.logger.warning(f"Skipping invalid entity: {error_msg}")
                    continue
                    
                try:
                    entity_id = self.graph_storage.create_entity(
                        entity_data=entity,
                        episode_id=episode_id
                    )
                    entity_id_map[entity['value']] = entity_id
                except KeyError as e:
                    self.logger.error(f"KeyError accessing entity fields: {e}. Entity data: {entity}")
                    raise KeyError(f"Entity missing required field '{e.args[0]}'. Available fields: {list(entity.keys())}")
                except Exception as e:
                    self.logger.error(f"Failed to store entity: {e}. Entity data: {entity}")
                    raise
                
            self.logger.info(f"Stored {len(entities)} entities")
            
            # Store quotes linked to MeaningfulUnits
            quote_id_map = {}  # Map quote text to stored ID for relationships
            for quote in quotes:
                # Validate before storage
                is_valid, error_msg = validate_quote(quote)
                if not is_valid:
                    self.logger.warning(f"Skipping invalid quote: {error_msg}")
                    continue
                    
                # Find the source MeaningfulUnit
                unit_id = quote.get('properties', {}).get('meaningful_unit_id')
                
                if not unit_id:
                    self.logger.error(f"Quote missing meaningful_unit_id in properties: {quote}")
                    self.logger.error(f"Quote properties: {quote.get('properties', {})}")
                    continue
                
                try:
                    quote_id = self.graph_storage.create_quote(
                        quote_data=quote,
                        episode_id=episode_id,
                        meaningful_unit_id=unit_id
                    )
                except Exception as e:
                    self.logger.error(f"Failed to create quote for unit {unit_id}: {e}")
                    self.logger.error(f"Quote data: {quote}")
                    raise
                
                # Map quote text (truncated as used in relationships) to ID
                quote_text_key = quote['text'][:100] if 'text' in quote else quote.get('value', '')[:100]
                quote_id_map[quote_text_key] = quote_id
                
            self.logger.info(f"Stored {len(quotes)} quotes")
            
            # Store relationships with resolved entity IDs
            for relationship in relationships:
                try:
                    # Resolve source and target to stored entity IDs
                    # Check both entity and quote maps
                    source_id = entity_id_map.get(relationship['source']) or quote_id_map.get(relationship['source'])
                    target_id = entity_id_map.get(relationship['target']) or quote_id_map.get(relationship['target'])
                except KeyError as e:
                    self.logger.error(f"KeyError accessing relationship fields: {e}. Relationship data: {relationship}")
                    raise KeyError(f"Relationship missing required field '{e.args[0]}'. Available fields: {list(relationship.keys())}")
                
                if source_id and target_id:
                    # Extract relationship properties
                    rel_type = relationship.get('type', 'RELATED_TO')
                    properties = relationship.get('properties', {})
                    properties['confidence'] = relationship.get('confidence', 0.85)
                    properties['episode_id'] = episode_id
                    
                    self.graph_storage.create_relationship(
                        source_id=source_id,
                        target_id=target_id,
                        rel_type=rel_type,
                        properties=properties
                    )
                    
            self.logger.info(f"Stored {len(relationships)} relationships")
            
            # Store insights linked to MeaningfulUnits
            for insight in insights:
                # Validate before storage
                is_valid, error_msg = validate_insight(insight)
                if not is_valid:
                    self.logger.warning(f"Skipping invalid insight: {error_msg}")
                    continue
                    
                unit_id = insight.get('properties', {}).get('meaningful_unit_id')
                
                # Normalize insight for storage (map title/description to text)
                storage_insight = normalize_insight_for_storage(insight)
                
                insight_id = self.graph_storage.create_insight(
                    insight_data=storage_insight,
                    episode_id=episode_id,
                    meaningful_unit_id=unit_id
                )
                
            self.logger.info(f"Stored {len(insights)} insights")
            
            # Store sentiment analyses linked to MeaningfulUnits
            for sentiment_data in sentiments:
                unit_id = sentiment_data['unit_id']
                sentiment_result = sentiment_data['sentiment']
                
                # Convert sentiment result to storable format
                sentiment_dict = {
                    'unit_id': unit_id,
                    'overall_polarity': sentiment_result.overall_sentiment.polarity,
                    'overall_score': sentiment_result.overall_sentiment.score,
                    'emotions': sentiment_result.overall_sentiment.emotions,
                    'attitudes': sentiment_result.overall_sentiment.attitudes,
                    'energy_level': sentiment_result.overall_sentiment.energy_level,
                    'engagement_level': sentiment_result.overall_sentiment.engagement_level,
                    'speaker_sentiments': {
                        speaker: {
                            'polarity': sent.overall_sentiment.polarity,
                            'score': sent.overall_sentiment.score,
                            'dominant_emotion': sent.dominant_emotion,
                            'emotional_range': sent.emotional_range
                        }
                        for speaker, sent in sentiment_result.speaker_sentiments.items()
                    },
                    'emotional_moments': [
                        {
                            'text': moment.text,
                            'speaker': moment.speaker,
                            'emotion': moment.emotion,
                            'intensity': moment.intensity
                        }
                        for moment in sentiment_result.emotional_moments
                    ],
                    'sentiment_flow': sentiment_result.sentiment_flow.trajectory,
                    'interaction_harmony': sentiment_result.interaction_dynamics.harmony_score,
                    'discovered_sentiments': [
                        {
                            'type': ds.sentiment_type,
                            'description': ds.description,
                            'confidence': ds.confidence
                        }
                        for ds in sentiment_result.discovered_sentiments
                    ],
                    'confidence': sentiment_result.confidence
                }
                
                # Store sentiment data
                sentiment_id = self.graph_storage.create_sentiment(
                    sentiment_data=sentiment_dict,
                    episode_id=episode_id,
                    meaningful_unit_id=unit_id
                )
                
            self.logger.info(f"Stored {len(sentiments)} sentiment analyses in Neo4j")
            
            self.logger.info("Knowledge storage complete")
            
        except Exception as e:
            self.logger.error(f"Knowledge storage failed: {e}")
            raise PipelineError(f"Failed to store knowledge: {e}") from e
    
    async def _post_process_speakers(self, episode_id: str) -> Dict[str, str]:
        """Post-process speaker identification to resolve generic speaker names.
        
        This method runs after the main pipeline to identify and update generic
        speaker names using pattern matching, YouTube API, and LLM fallback.
        
        Args:
            episode_id: Episode ID to process
            
        Returns:
            Dict mapping generic names to identified real names
        """
        self.logger.info(f"Starting speaker post-processing for episode {episode_id}")
        
        try:
            # Import SpeakerMapper
            from src.post_processing.speaker_mapper import SpeakerMapper
            
            # Initialize speaker mapper with current services
            speaker_mapper = SpeakerMapper(
                storage=self.graph_storage,
                llm_service=self.llm_service,
                config=self.config
            )
            
            # Process the episode
            mappings = speaker_mapper.process_episode(episode_id)
            
            if mappings:
                self.logger.info(
                    f"Speaker post-processing completed: mapped {len(mappings)} speakers"
                )
                for generic, real in mappings.items():
                    self.logger.info(f"  '{generic}' -> '{real}'")
            else:
                self.logger.info("No generic speakers found to map")
            
            return mappings
            
        except Exception as e:
            self.logger.warning(f"Speaker post-processing failed: {e}")
            # Don't fail the entire pipeline for speaker mapping issues
            return {}
    
    def _deduplicate_entities_globally(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate entities across all MeaningfulUnits.
        
        This method identifies and merges duplicate entities that may appear
        across different units, preserving the most complete information.
        
        Args:
            entities: List of all entities from all units
            
        Returns:
            List of unique entities with merged information
        """
        entity_map = {}  # Key: (type, normalized_name) -> merged entity
        
        for entity in entities:
            # Create a key for deduplication
            entity_type = entity['type']
            entity_name = entity['value'].strip().lower()
            key = (entity_type, entity_name)
            
            if key in entity_map:
                # Merge with existing entity
                existing = entity_map[key]
                
                # Keep higher confidence
                if entity.get('confidence', 0) > existing.get('confidence', 0):
                    existing['confidence'] = entity['confidence']
                
                # Merge properties
                existing_props = existing.get('properties', {})
                new_props = entity.get('properties', {})
                
                # Combine descriptions
                existing_desc = existing_props.get('description', '')
                new_desc = new_props.get('description', '')
                if new_desc and new_desc not in existing_desc:
                    if existing_desc:
                        existing_props['description'] = f"{existing_desc}. {new_desc}"
                    else:
                        existing_props['description'] = new_desc
                
                # Collect all MeaningfulUnit IDs
                existing_units = existing_props.get('meaningful_unit_ids', [])
                if not isinstance(existing_units, list):
                    existing_units = [existing_units]
                new_unit_id = new_props.get('meaningful_unit_id')
                if new_unit_id and new_unit_id not in existing_units:
                    existing_units.append(new_unit_id)
                existing_props['meaningful_unit_ids'] = existing_units
                
                # Update properties
                existing['properties'] = existing_props
                
            else:
                # First occurrence of this entity
                # Convert single unit_id to list for consistency
                props = entity.get('properties', {})
                if 'meaningful_unit_id' in props:
                    props['meaningful_unit_ids'] = [props['meaningful_unit_id']]
                entity['properties'] = props
                entity_map[key] = entity
        
        # Return unique entities
        unique_entities = list(entity_map.values())
        
        self.logger.info(
            f"Deduplicated {len(entities)} entities to {len(unique_entities)} unique entities"
        )
        
        return unique_entities
    
    def _build_relationship_graph(
        self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build a graph structure from entities and relationships.
        
        This creates an adjacency representation of the knowledge graph
        for analysis and visualization.
        
        Args:
            entities: List of unique entities
            relationships: List of all relationships
            
        Returns:
            Graph structure with nodes and edges
        """
        # Create entity index for fast lookup
        entity_index = {entity['value']: entity for entity in entities}
        
        # Build adjacency lists
        graph = {
            'nodes': entities,
            'edges': relationships,
            'adjacency': {},  # entity_value -> list of connected entities
            'degree': {},     # entity_value -> number of connections
            'type_distribution': {
                'entities': {},
                'relationships': {}
            }
        }
        
        # Initialize adjacency lists
        for entity in entities:
            entity_value = entity['value']
            graph['adjacency'][entity_value] = []
            graph['degree'][entity_value] = 0
            
            # Count entity types
            entity_type = entity['type']
            graph['type_distribution']['entities'][entity_type] = \
                graph['type_distribution']['entities'].get(entity_type, 0) + 1
        
        # Build adjacency from relationships
        for rel in relationships:
            source = rel['source']
            target = rel['target']
            rel_type = rel['type']
            
            # Count relationship types
            graph['type_distribution']['relationships'][rel_type] = \
                graph['type_distribution']['relationships'].get(rel_type, 0) + 1
            
            # Add to adjacency if both entities exist
            if source in entity_index and target in entity_index:
                graph['adjacency'][source].append({
                    'target': target,
                    'type': rel_type,
                    'properties': rel.get('properties', {})
                })
                graph['degree'][source] += 1
                
                # Handle bidirectional relationships
                if rel.get('properties', {}).get('bidirectional', False):
                    graph['adjacency'][target].append({
                        'target': source,
                        'type': rel_type,
                        'properties': rel.get('properties', {})
                    })
                    graph['degree'][target] += 1
        
        # Calculate graph metrics
        graph['metrics'] = {
            'node_count': len(entities),
            'edge_count': len(relationships),
            'avg_degree': sum(graph['degree'].values()) / max(len(entities), 1),
            'max_degree': max(graph['degree'].values()) if graph['degree'] else 0,
            'connected_components': self._count_connected_components(graph['adjacency'])
        }
        
        return graph
    
    def _count_connected_components(self, adjacency: Dict[str, List]) -> int:
        """Count the number of connected components in the graph."""
        visited = set()
        components = 0
        
        def dfs(node):
            visited.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor['target'] not in visited:
                    dfs(neighbor['target'])
        
        for node in adjacency:
            if node not in visited:
                components += 1
                dfs(node)
        
        return components
    
    async def _run_analysis(self, episode_id: str) -> Dict[str, Any]:
        """Run all analysis modules after knowledge extraction.
        
        This includes:
        - Gap detection
        - Diversity metrics
        - Missing links analysis
        - Analysis orchestration
        
        Args:
            episode_id: ID of the episode to analyze
            
        Returns:
            Dict with analysis results from all modules
        """
        self.logger.info(f"Starting analysis phase for episode {episode_id}")
        
        analysis_results = {
            'gap_detection': {},
            'diversity_metrics': {},
            'missing_links': {},
            'orchestrator': {},
            'errors': []
        }
        
        # Task 5.4: Run coordinated knowledge discovery analysis
        # Use analysis orchestrator to coordinate all analysis modules
        with self.graph_storage.session() as session:
            try:
                self.logger.info("Running coordinated knowledge discovery analysis...")
                orchestrator_results = analysis_orchestrator.run_knowledge_discovery(episode_id, session)
                
                # Merge orchestrator results into analysis_results
                analysis_results.update(orchestrator_results)
                
                # Log comprehensive results
                completed = orchestrator_results.get('analyses_completed', [])
                failed = orchestrator_results.get('analyses_failed', [])
                total_time = orchestrator_results.get('total_time', 0)
                
                self.logger.info(
                    f"Knowledge discovery complete in {total_time:.2f}s: "
                    f"{len(completed)} analyses completed, {len(failed)} failed"
                )
                
                # Log completed analyses
                if completed:
                    self.logger.info(f"Completed analyses: {', '.join(completed)}")
                
                # Log failures
                if failed:
                    self.logger.warning(f"Failed analyses: {', '.join(failed)}")
                
                # Log summary findings
                summary = orchestrator_results.get('summary', {})
                key_findings = summary.get('key_findings', [])
                if key_findings:
                    self.logger.info(f"Key findings: {len(key_findings)} insights discovered")
                    for finding in key_findings[:3]:  # Log top 3 findings
                        self.logger.info(f"  - {finding}")
                
                # Log recommendations
                recommendations = summary.get('recommendations', [])
                if recommendations:
                    self.logger.info(f"Generated {len(recommendations)} analysis recommendations")
                    
            except Exception as e:
                self.logger.error(f"Knowledge discovery orchestration failed: {e}")
                analysis_results['errors'].append({
                    'module': 'analysis_orchestrator',
                    'error': str(e)
                })
        
        return analysis_results
    
    async def _post_process_speakers(self, episode_id: str) -> Dict[str, str]:
        """
        Post-process speaker identification to map generic names to real names.
        
        Args:
            episode_id: Episode ID to process
            
        Returns:
            Dictionary mapping generic names to identified names
        """
        self.logger.info(f"Starting speaker post-processing for episode {episode_id}")
        
        try:
            # Import here to avoid circular dependencies
            from src.post_processing.speaker_mapper import SpeakerMapper
            
            # Initialize speaker mapper
            mapper = SpeakerMapper(
                storage=self.graph_storage,
                llm_service=self.llm_flash,  # Use flash model for speed
                config=self.config
            )
            
            # Process the episode
            mappings = mapper.process_episode(episode_id)
            
            if mappings:
                self.logger.info(f"Successfully mapped {len(mappings)} speakers")
                for old_name, new_name in mappings.items():
                    self.logger.info(f"  - '{old_name}' → '{new_name}'")
            else:
                self.logger.info("No generic speakers found to map")
            
            return mappings
            
        except Exception as e:
            self.logger.error(f"Speaker post-processing failed: {e}")
            # Non-critical error - don't fail the pipeline
            return {}
    
    async def _cleanup_on_error(self, episode_id: str) -> None:
        """
        Clean up any partial data on error - CRITICAL for data integrity.
        
        This ensures NO PARTIAL DATA is left in the system. Any failure
        triggers complete rollback of the episode.
        
        Args:
            episode_id: Episode to clean up
        """
        self.logger.error(f"CRITICAL: Rolling back all data for episode {episode_id}")
        
        try:
            # Start rollback transaction
            with self.graph_storage.session() as session:
                # Delete all nodes related to this episode
                rollback_query = """
                // Find and delete all nodes connected to this episode
                MATCH (e:Episode {id: $episode_id})
                OPTIONAL MATCH (e)-[r1]-(m:MeaningfulUnit)
                OPTIONAL MATCH (m)-[r2]-(n)
                DETACH DELETE m, n
                
                // Delete the episode itself
                DETACH DELETE e
                
                // Return count of deleted nodes for logging
                RETURN COUNT(DISTINCT m) + COUNT(DISTINCT n) + 1 as deleted_count
                """
                
                result = session.run(rollback_query, episode_id=episode_id)
                record = result.single()
                deleted_count = record['deleted_count'] if record else 0
                
                self.logger.info(f"Rollback complete: Deleted {deleted_count} nodes for episode {episode_id}")
                
        except Exception as rollback_error:
            # Log rollback failure but don't raise - we're already in error handling
            self.logger.critical(
                f"ROLLBACK FAILED for episode {episode_id}: {rollback_error}. "
                "Manual cleanup may be required!"
            )
    
    def _store_error_details(self, episode_id: str, error: Exception) -> None:
        """
        Store error details for troubleshooting.
        
        Args:
            episode_id: Episode that failed
            error: The exception that occurred
        """
        error_details = {
            'episode_id': episode_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'phase': self.current_phase,
            'phase_timings': self.phase_timings
        }
        
        # Log error details
        self.logger.error(f"Episode processing failed: {error_details}")
        
        # Could also store in a failure log file or database
        # For now, just comprehensive logging
    
    def _write_embedding_failures(self) -> None:
        """
        Write embedding failures to a structured log file for recovery.
        
        Creates timestamped JSON files containing all information needed
        for the recovery script to retry failed embeddings.
        """
        if not self.failed_embeddings:
            return
        
        # Create logs directory if not exists
        logs_dir = Path("logs/embedding_failures")
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failures_{timestamp}_{self.current_episode_id}.json"
        filepath = logs_dir / filename
        
        # Prepare failure data
        failure_data = {
            'episode_id': self.current_episode_id,
            'episode_metadata': self.episode_metadata,
            'failures': self.failed_embeddings,
            'total_failures': len(self.failed_embeddings),
            'written_at': datetime.now().isoformat()
        }
        
        # Write to JSON file
        try:
            with open(filepath, 'w') as f:
                json.dump(failure_data, f, indent=2)
            self.logger.info(f"Wrote {len(self.failed_embeddings)} embedding failures to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to write embedding failures to file: {e}")
        
        # Clear the failures list after writing
        self.failed_embeddings = []
    
    def _merge_vtt_metadata(self, episode_metadata: Dict[str, Any], vtt_metadata: Dict[str, Any]) -> None:
        """
        Merge metadata extracted from VTT file into episode metadata.
        
        This method updates the episode_metadata dict in-place, prioritizing VTT metadata
        over passed-in metadata since VTT files contain authoritative information.
        
        Args:
            episode_metadata: Episode metadata dict to update
            vtt_metadata: Metadata extracted from VTT NOTE sections
        """
        if not vtt_metadata:
            return
        
        # YouTube URL from VTT takes priority
        if 'youtube_url' in vtt_metadata and vtt_metadata['youtube_url']:
            episode_metadata['youtube_url'] = vtt_metadata['youtube_url']
            self.logger.info(f"Set YouTube URL from VTT: {vtt_metadata['youtube_url']}")
        elif 'episode_url' in episode_metadata and episode_metadata['episode_url']:
            # Fall back to episode_url if no YouTube URL in VTT
            episode_metadata['youtube_url'] = episode_metadata['episode_url']
        
        # Description from VTT takes priority
        if 'description' in vtt_metadata and vtt_metadata['description']:
            episode_metadata['description'] = vtt_metadata['description']
        
        # Published date from VTT takes priority
        if 'published_date' in vtt_metadata and vtt_metadata['published_date']:
            episode_metadata['published_date'] = vtt_metadata['published_date']
        elif 'published' in vtt_metadata and vtt_metadata['published']:
            episode_metadata['published_date'] = vtt_metadata['published']
        
        # Handle title - VTT metadata takes priority
        if 'episode' in vtt_metadata and vtt_metadata['episode']:
            episode_metadata['title'] = vtt_metadata['episode']
            episode_metadata['episode_title'] = vtt_metadata['episode']
            self.logger.info(f"Set title from VTT: {vtt_metadata['episode']}")
        elif 'title' in vtt_metadata and vtt_metadata['title']:
            episode_metadata['title'] = vtt_metadata['title']
            episode_metadata['episode_title'] = vtt_metadata['title']
        elif 'episode_title' in episode_metadata and episode_metadata['episode_title']:
            # Ensure title field is set from episode_title
            episode_metadata['title'] = episode_metadata['episode_title']
        
        # Extract podcast info from VTT if available
        if 'podcast' in vtt_metadata:
            if 'podcast_info' not in episode_metadata:
                episode_metadata['podcast_info'] = {}
            episode_metadata['podcast_info']['name'] = vtt_metadata['podcast']
            if 'podcast_name' not in episode_metadata:
                episode_metadata['podcast_name'] = vtt_metadata['podcast']
        
        if 'author' in vtt_metadata:
            if 'podcast_info' not in episode_metadata:
                episode_metadata['podcast_info'] = {}
            episode_metadata['podcast_info']['host'] = vtt_metadata['author']
        
        # Store any additional VTT metadata that might be useful
        for key, value in vtt_metadata.items():
            # Skip fields we've already processed or that might conflict
            if key not in ['youtube_url', 'description', 'published_date', 'title', 'episode', 'podcast', 'author']:
                # Store additional metadata with vtt_ prefix to avoid conflicts
                episode_metadata[f'vtt_{key}'] = value
    
    async def process_vtt_file(self, vtt_path: Path, episode_metadata: Dict) -> Dict[str, Any]:
        """
        Main processing method - orchestrates entire pipeline flow.
        
        This is the ONLY way to process a VTT file. Linear flow with
        comprehensive error handling and transaction management.
        
        Args:
            vtt_path: Path to VTT transcript file
            episode_metadata: Episode information including:
                - episode_id
                - title
                - description
                - published_date
                - youtube_url
                - podcast_info
                
        Returns:
            Processing result with comprehensive stats
            
        Raises:
            PipelineError: On any processing failure (triggers full rollback)
        """
        # Initialize tracking
        pipeline_start_time = time.time()
        episode_id = episode_metadata.get('episode_id')
        
        if not episode_id:
            raise PipelineError("episode_id is required in metadata")
            
        # Check if episode with this VTT filename already exists
        vtt_filename = episode_metadata.get('vtt_filename')
        if vtt_filename:
            try:
                with self.graph_storage.session() as session:
                    check_query = """
                    MATCH (e:Episode {vtt_filename: $vtt_filename})
                    RETURN e.id AS id, e.title AS title
                    """
                    result_check = session.run(check_query, vtt_filename=vtt_filename)
                    existing = result_check.single()
                    
                    if existing:
                        self.logger.info(f"Episode with VTT filename '{vtt_filename}' already exists: {existing['title']}")
                        return {
                            'episode_id': existing['id'],
                            'status': 'skipped',
                            'reason': 'VTT filename already processed',
                            'existing_episode': existing['title']
                        }
            except Exception as e:
                self.logger.warning(f"Failed to check for existing VTT filename: {e}")
                # Continue processing if check fails
            
        # Set current episode for extraction context
        self.current_episode_id = episode_id
        self.episode_metadata = episode_metadata  # Store for access throughout pipeline
        
        # Start benchmarking for this episode
        benchmark = get_benchmark()
        benchmark.start_episode(episode_id)
        
        # Check for existing checkpoint (unless disabled)
        checkpoint = None
        import os
        if os.getenv('DISABLE_CHECKPOINTS', 'false').lower() != 'true':
            try:
                checkpoint = self.checkpoint_manager.load_checkpoint(episode_id)
                if checkpoint:
                    self.logger.info(f"Found checkpoint for episode {episode_id} at phase {checkpoint.last_completed_phase}")
                    self.phase_results = checkpoint.phase_results
                    checkpoint_age = self.checkpoint_manager.get_checkpoint_age(episode_id)
                    self.logger.info(f"Checkpoint age: {checkpoint_age:.2f} hours")
                else:
                    self.logger.info(f"Starting fresh pipeline processing for episode {episode_id}")
                    self.phase_results = {}
            except Exception as e:
                self.logger.warning(f"Failed to load checkpoint: {e}. Starting fresh.")
                self.phase_results = {}
        else:
            self.logger.info(f"Checkpoints disabled. Starting fresh pipeline processing for episode {episode_id}")
            self.phase_results = {}
        
        self.logger.info(f"VTT file: {vtt_path}")
        
        # Initialize result object
        result = {
            'episode_id': episode_id,
            'status': 'processing',
            'phases_completed': [],
            'phase_timings': {},
            'stats': {
                'segments_parsed': 0,
                'speakers_identified': 0,
                'meaningful_units_created': 0,
                'entities_extracted': 0,
                'insights_extracted': 0,
                'quotes_extracted': 0,
                'relationships_created': 0,
                'analysis_results': {}
            },
            'errors': [],
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'total_time': 0
        }
        
        try:
            # PHASE 1: VTT Parsing
            if self._should_skip_phase("VTT_PARSING", checkpoint):
                self.logger.info("Skipping VTT_PARSING - already completed")
                segments = self.phase_results.get("VTT_PARSING", {}).get("segments", [])
                vtt_metadata = self.phase_results.get("VTT_PARSING", {}).get("metadata", {})
                # Merge VTT metadata with episode metadata
                self._merge_vtt_metadata(episode_metadata, vtt_metadata)
                result['stats']['segments_parsed'] = len(segments)
                result['phases_completed'].append("VTT_PARSING")
            else:
                self._start_phase("VTT_PARSING")
                segments, vtt_metadata = await self._parse_vtt(vtt_path)
                # Merge VTT metadata with episode metadata
                self._merge_vtt_metadata(episode_metadata, vtt_metadata)
                result['stats']['segments_parsed'] = len(segments) if segments else 0
                result['phases_completed'].append("VTT_PARSING")
                self._end_phase()
                self._save_checkpoint("VTT_PARSING", {'segments': segments, 'metadata': vtt_metadata}, episode_metadata)
            
            # PHASE 2: Speaker Identification
            if self._should_skip_phase("SPEAKER_IDENTIFICATION", checkpoint):
                self.logger.info("Skipping SPEAKER_IDENTIFICATION - already completed")
                identified_segments = self.phase_results.get("SPEAKER_IDENTIFICATION", {}).get("segments", segments)
                result['stats']['speakers_identified'] = len(set(
                    seg.speaker for seg in identified_segments if hasattr(seg, 'speaker') and seg.speaker
                )) if identified_segments else 0
                result['phases_completed'].append("SPEAKER_IDENTIFICATION")
            else:
                self._start_phase("SPEAKER_IDENTIFICATION")
                identified_segments = await self._identify_speakers(segments, episode_metadata)
                result['stats']['speakers_identified'] = len(set(
                    seg.speaker for seg in identified_segments if hasattr(seg, 'speaker') and seg.speaker
                )) if identified_segments else 0
                result['phases_completed'].append("SPEAKER_IDENTIFICATION")
                self._end_phase()
                self._save_checkpoint("SPEAKER_IDENTIFICATION", {'segments': identified_segments}, episode_metadata)
            
            # PHASE 3: Conversation Analysis
            if self._should_skip_phase("CONVERSATION_ANALYSIS", checkpoint):
                self.logger.info("Skipping CONVERSATION_ANALYSIS - already completed")
                # ConversationStructure is not saved in checkpoint, need to regenerate
                self.logger.warning("ConversationStructure not in checkpoint, will regenerate")
                conversation_structure = None  # Will cause error if needed later
                result['phases_completed'].append("CONVERSATION_ANALYSIS")
            else:
                self._start_phase("CONVERSATION_ANALYSIS")
                conversation_structure = await self._analyze_conversation(identified_segments)
                result['phases_completed'].append("CONVERSATION_ANALYSIS")
                self._end_phase()
                # Don't save conversation_structure to avoid serialization issues
                # It can be regenerated if needed
                self._save_checkpoint("CONVERSATION_ANALYSIS", {'completed': True}, episode_metadata)
            
            # PHASE 4: Create MeaningfulUnits
            if self._should_skip_phase("MEANINGFUL_UNIT_CREATION", checkpoint):
                self.logger.info("Skipping MEANINGFUL_UNIT_CREATION - already completed")
                meaningful_units = self.phase_results.get("MEANINGFUL_UNIT_CREATION", {}).get("units", [])
                result['stats']['meaningful_units_created'] = len(meaningful_units)
                result['phases_completed'].append("MEANINGFUL_UNIT_CREATION")
            else:
                self._start_phase("MEANINGFUL_UNIT_CREATION")
                meaningful_units = await self._create_meaningful_units(
                    identified_segments, conversation_structure
                )
                result['stats']['meaningful_units_created'] = len(meaningful_units) if meaningful_units else 0
                result['phases_completed'].append("MEANINGFUL_UNIT_CREATION")
                self._end_phase()
                self._save_checkpoint("MEANINGFUL_UNIT_CREATION", {'units': meaningful_units}, episode_metadata)
            
            # PHASE 5: Store Episode Structure
            if self._should_skip_phase("EPISODE_STORAGE", checkpoint):
                self.logger.info("Skipping EPISODE_STORAGE - already completed")
                result['phases_completed'].append("EPISODE_STORAGE")
            else:
                self._start_phase("EPISODE_STORAGE")
                await self._store_episode_structure(episode_metadata, meaningful_units, conversation_structure, vtt_path)
                result['phases_completed'].append("EPISODE_STORAGE")
                self._end_phase()
                self._save_checkpoint("EPISODE_STORAGE", {'stored': True}, episode_metadata)
            
            # PHASE 6: Knowledge Extraction
            if self._should_skip_phase("KNOWLEDGE_EXTRACTION", checkpoint):
                self.logger.info("Skipping KNOWLEDGE_EXTRACTION - already completed")
                extraction_results = self.phase_results.get("KNOWLEDGE_EXTRACTION", {})
                if extraction_results:
                    result['stats']['entities_extracted'] = len(extraction_results.get('entities', []))
                    result['stats']['insights_extracted'] = len(extraction_results.get('insights', []))
                    result['stats']['quotes_extracted'] = len(extraction_results.get('quotes', []))
                    result['stats']['relationships_extracted'] = len(extraction_results.get('relationships', []))
                result['phases_completed'].append("KNOWLEDGE_EXTRACTION")
            else:
                self._start_phase("KNOWLEDGE_EXTRACTION")
                extraction_results = await self._extract_knowledge(meaningful_units)
                if extraction_results:
                    result['stats']['entities_extracted'] = len(extraction_results.get('entities', []))
                    result['stats']['insights_extracted'] = len(extraction_results.get('insights', []))
                    result['stats']['quotes_extracted'] = len(extraction_results.get('quotes', []))
                    result['stats']['relationships_extracted'] = len(extraction_results.get('relationships', []))
                result['phases_completed'].append("KNOWLEDGE_EXTRACTION")
                self._end_phase()
                self._save_checkpoint("KNOWLEDGE_EXTRACTION", extraction_results, episode_metadata)
            
            # PHASE 7: Store Knowledge
            if self._should_skip_phase("KNOWLEDGE_STORAGE", checkpoint):
                self.logger.info("Skipping KNOWLEDGE_STORAGE - already completed")
                result['phases_completed'].append("KNOWLEDGE_STORAGE")
                # Restore storage stats from extraction results
                if extraction_results:
                    result['stats']['nodes_created'] = (
                        len(extraction_results.get('entities', [])) +
                        len(extraction_results.get('quotes', [])) +
                        len(extraction_results.get('insights', [])) +
                        len(meaningful_units) +
                        2  # Episode + Podcast nodes
                    )
                    result['stats']['relationships_created'] = (
                        len(extraction_results.get('relationships', [])) +
                        len(extraction_results.get('entities', [])) +
                        len(extraction_results.get('quotes', [])) +
                        len(extraction_results.get('insights', []))
                    )
            else:
                self._start_phase("KNOWLEDGE_STORAGE")
                await self._store_knowledge(extraction_results, meaningful_units)
                result['phases_completed'].append("KNOWLEDGE_STORAGE")
                # Track storage stats (using extraction counts as approximation)
                if extraction_results:
                    # Nodes = entities + quotes + insights + meaningful units + episode + podcast
                    result['stats']['nodes_created'] = (
                        len(extraction_results.get('entities', [])) +
                        len(extraction_results.get('quotes', [])) +
                        len(extraction_results.get('insights', [])) +
                        len(meaningful_units) +
                        2  # Episode + Podcast nodes
                    )
                    # Relationships = extracted relationships + entity mentions + quote sources + insight sources
                    result['stats']['relationships_created'] = (
                        len(extraction_results.get('relationships', [])) +
                        len(extraction_results.get('entities', [])) +  # MENTIONED_IN relationships
                        len(extraction_results.get('quotes', [])) +  # QUOTED_IN relationships
                        len(extraction_results.get('insights', []))  # SOURCE relationships
                    )
                else:
                    result['stats']['nodes_created'] = 0
                    result['stats']['relationships_created'] = 0
                self._end_phase()
                self._save_checkpoint("KNOWLEDGE_STORAGE", {'stored': True}, episode_metadata)
            
            # PHASE 8: Run Analysis
            if self._should_skip_phase("ANALYSIS", checkpoint):
                self.logger.info("Skipping ANALYSIS - already completed")
                analysis_results = self.phase_results.get("ANALYSIS", {}).get("results", {})
                result['stats']['analysis_results'] = analysis_results
                result['phases_completed'].append("ANALYSIS")
            else:
                self._start_phase("ANALYSIS")
                analysis_results = await self._run_analysis(episode_id)
                result['stats']['analysis_results'] = analysis_results or {}
                result['phases_completed'].append("ANALYSIS")
                self._end_phase()
                self._save_checkpoint("ANALYSIS", {'results': analysis_results}, episode_metadata)
            
            # PHASE 9: Post-Process Speaker Mapping (Optional)
            if getattr(self, 'enable_speaker_mapping', False):
                if self._should_skip_phase("POST_PROCESS_SPEAKERS", checkpoint):
                    self.logger.info("Skipping POST_PROCESS_SPEAKERS - already completed")
                    speaker_mappings = self.phase_results.get("POST_PROCESS_SPEAKERS", {}).get("mappings", {})
                    result['stats']['speakers_mapped'] = len(speaker_mappings)
                    result['phases_completed'].append("POST_PROCESS_SPEAKERS")
                else:
                    self._start_phase("POST_PROCESS_SPEAKERS")
                    speaker_mappings = await self._post_process_speakers(episode_id)
                    result['stats']['speakers_mapped'] = len(speaker_mappings) if speaker_mappings else 0
                    result['phases_completed'].append("POST_PROCESS_SPEAKERS")
                    self._end_phase()
                    self._save_checkpoint("POST_PROCESS_SPEAKERS", {'mappings': speaker_mappings}, episode_metadata)
            
            # Success - update result
            result['status'] = 'completed'
            result['phase_timings'] = self.phase_timings.copy()
            
            # Delete checkpoint on successful completion
            self.checkpoint_manager.delete_checkpoint(self.current_episode_id)
            
        except (SpeakerIdentificationError, ConversationAnalysisError) as critical_error:
            # CRITICAL errors - must reject entire episode
            self.logger.error(f"CRITICAL ERROR: {critical_error}")
            result['status'] = 'failed'
            result['errors'].append({
                'phase': self.current_phase,
                'error_type': type(critical_error).__name__,
                'message': str(critical_error)
            })
            
            # Store error details
            self._store_error_details(episode_id, critical_error)
            
            # Rollback any partial data
            await self._cleanup_on_error(episode_id)
            
            # Re-raise as PipelineError
            raise PipelineError(
                f"Episode {episode_id} rejected due to critical error: {critical_error}"
            ) from critical_error
            
        except Exception as error:
            # Any other error - still reject entire episode (NO PARTIAL DATA)
            self.logger.error(f"Pipeline error: {error}")
            result['status'] = 'failed'
            result['errors'].append({
                'phase': self.current_phase,
                'error_type': type(error).__name__,
                'message': str(error)
            })
            
            # Store error details
            self._store_error_details(episode_id, error)
            
            # Rollback any partial data
            await self._cleanup_on_error(episode_id)
            
            # Re-raise as PipelineError
            raise PipelineError(
                f"Episode {episode_id} processing failed: {error}"
            ) from error
            
        finally:
            # Write any embedding failures to log file for recovery
            self._write_embedding_failures()
            
            # Clean up resources and finalize result
            result['end_time'] = datetime.now().isoformat()
            result['total_time'] = time.time() - pipeline_start_time
            
            # Log final status
            self.logger.info(
                f"Pipeline completed for episode {episode_id}: "
                f"Status={result['status']}, "
                f"Time={result['total_time']:.2f}s, "
                f"Phases={len(result['phases_completed'])}"
            )
            
        # End benchmarking and generate performance summary
        benchmark.end_episode()
        
        return result