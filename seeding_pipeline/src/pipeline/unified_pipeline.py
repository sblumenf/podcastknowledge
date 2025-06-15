"""
Unified Knowledge Pipeline - Single entry point for all VTT processing.

This module implements the ONLY pipeline for processing podcast transcripts.
No alternative approaches or configurations - ONE WAY ONLY.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

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

# Analysis Modules
from src.analysis import analysis_orchestrator
from src.analysis import diversity_metrics
from src.analysis import gap_detection
from src.analysis import missing_links

# Storage
from src.storage.graph_storage import GraphStorageService

# Services
from src.services.llm import LLMService
from src.services.embeddings import EmbeddingsService

# Utils
from src.utils.logging import get_logger
from src.utils.retry import retry
from src.core.interfaces import TranscriptSegment
from src.core.exceptions import (
    PipelineError,
    ExtractionError,
    VTTProcessingError,
    SpeakerIdentificationError,
    ConversationAnalysisError,
    CriticalError
)

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
        embeddings_service: Optional[EmbeddingsService] = None
    ):
        """
        Initialize the unified pipeline with required services.
        
        Args:
            graph_storage: Neo4j storage service
            llm_service: LLM service for analysis and extraction
            embeddings_service: Optional embeddings service
        """
        # Core services - dependency injection
        self.graph_storage = graph_storage
        self.llm_service = llm_service
        self.embeddings_service = embeddings_service
        
        # Initialize components
        self.vtt_parser = VTTParser()
        self.vtt_segmenter = VTTSegmenter(llm_service)
        self.conversation_analyzer = ConversationAnalyzer(llm_service)
        self.segment_regrouper = SegmentRegrouper()
        
        # Extractors
        self.knowledge_extractor = KnowledgeExtractor(
            llm_service=llm_service,
            embedding_service=embeddings_service
        )
        self.entity_resolver = EntityResolver()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.importance_scorer = ImportanceScorer()
        
        # Logging setup with clear phase tracking
        self.logger = logger
        self.logger.info("Initialized UnifiedKnowledgePipeline - THE ONLY PIPELINE")
        
        # Phase tracking
        self.current_phase = None
        self.phase_start_time = None
        self.phase_timings = {}
        
    def _start_phase(self, phase_name: str) -> None:
        """Start tracking a processing phase."""
        self.current_phase = phase_name
        self.phase_start_time = time.time()
        self.logger.info(f"=== PHASE START: {phase_name} ===")
        
    def _end_phase(self) -> None:
        """End tracking current phase and record timing."""
        if self.current_phase and self.phase_start_time:
            elapsed = time.time() - self.phase_start_time
            self.phase_timings[self.current_phase] = elapsed
            self.logger.info(
                f"=== PHASE END: {self.current_phase} "
                f"(took {elapsed:.2f}s) ==="
            )
            self.current_phase = None
            self.phase_start_time = None
    
    # Placeholder methods for each processing phase
    async def _parse_vtt(self, vtt_path: Path) -> List[TranscriptSegment]:
        """Parse VTT file into segments."""
        self.logger.info(f"Parsing VTT file: {vtt_path}")
        
        try:
            # Parse VTT file using VTTParser
            segments = self.vtt_parser.parse_file(vtt_path)
            
            if not segments:
                raise VTTProcessingError(f"No segments found in VTT file: {vtt_path}")
            
            self.logger.info(f"Successfully parsed {len(segments)} segments from VTT file")
            return segments
            
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
                    segment = TranscriptSegment(
                        text=seg_data['text'],
                        start_time=seg_data['start_time'],
                        end_time=seg_data['end_time'],
                        speaker=seg_data['speaker']
                    )
                    identified_segments.append(segment)
                
                # Verify speakers were actually identified (NO generic names allowed)
                speakers = set()
                generic_speakers_found = False
                for segment in identified_segments:
                    if segment.speaker:
                        speakers.add(segment.speaker)
                        # Check for generic speaker names (Speaker 0, Speaker 1, etc.)
                        if segment.speaker.startswith('Speaker ') and segment.speaker.split()[-1].isdigit():
                            generic_speakers_found = True
                
                if generic_speakers_found:
                    raise SpeakerIdentificationError(
                        "Generic speaker names detected. Actual speaker identification required."
                    )
                
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
                    theme_list = [theme.name for theme in structure.themes]
                    self.logger.debug(f"  Themes identified: {theme_list}")
                
                # Log insights if available
                if structure.insights:
                    self.logger.debug(
                        f"  Structural insights: "
                        f"flow_type={structure.insights.flow_type}, "
                        f"coherence_score={structure.insights.coherence_score}"
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
        
        # Call regroup_segments() with segments and structure
        meaningful_units = self.segment_regrouper.regroup_segments(segments, structure)
        
        if not meaningful_units:
            raise PipelineError("No meaningful units created from segments")
        
        # Process each MeaningfulUnit
        for unit in meaningful_units:
            # Adjust start_time by -2 seconds (minimum 0) for YouTube navigation
            unit.start_time = max(0, unit.start_time - 2.0)
            
            # The SegmentRegrouper already calculates speaker distribution,
            # but let's verify it exists
            if not unit.speaker_distribution:
                # Calculate speaker distribution if missing
                speaker_counts = {}
                total_duration = 0
                
                for segment in unit.segments:
                    duration = segment.end_time - segment.start_time
                    total_duration += duration
                    
                    if segment.speaker:
                        speaker_counts[segment.speaker] = speaker_counts.get(segment.speaker, 0) + duration
                
                # Convert to percentages
                unit.speaker_distribution = {
                    speaker: round(duration / total_duration, 3)
                    for speaker, duration in speaker_counts.items()
                } if total_duration > 0 else {}
            
            # Generate unique ID (already done by SegmentRegrouper, but verify)
            if not unit.id:
                # Generate a unique ID based on episode and unit index
                unit.id = f"unit_{unit.start_time}_{unit.end_time}"
        
        self.logger.info(f"Created {len(meaningful_units)} MeaningfulUnits")
        
        # Log unit summary
        for idx, unit in enumerate(meaningful_units):
            self.logger.debug(
                f"  Unit {idx}: {unit.unit_type} "
                f"({unit.segment_count} segments, {unit.duration:.1f}s) "
                f"- {unit.summary[:50]}..."
            )
        
        return meaningful_units
    
    async def _store_episode_structure(self, episode_metadata: Dict, meaningful_units: List[MeaningfulUnit]) -> None:
        """
        Store episode and MeaningfulUnits in Neo4j.
        
        CRITICAL: DO NOT store individual segments - only MeaningfulUnits.
        All operations are transactional - either all succeed or all rollback.
        
        Args:
            episode_metadata: Episode information
            meaningful_units: List of MeaningfulUnits to store
        """
        self.logger.info(f"Storing episode structure with {len(meaningful_units)} MeaningfulUnits")
        
        episode_id = episode_metadata.get('episode_id')
        if not episode_id:
            raise PipelineError("episode_id required for storage")
        
        # Start Neo4j transaction
        try:
            # Store episode if not exists
            episode_node_id = self.graph_storage.create_episode(episode_metadata)
            self.logger.info(f"Episode node created/retrieved: {episode_node_id}")
            
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
                    'speaker_distribution': unit.speaker_distribution,
                    'unit_type': unit.unit_type,
                    'themes': unit.themes,
                    'segment_indices': [seg.start_time for seg in unit.segments],  # Store segment references
                    'is_complete': unit.is_complete,
                    'metadata': unit.metadata or {}
                }
                
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
    
    async def _extract_knowledge(self, meaningful_units: List[Any]) -> Dict[str, Any]:
        """Extract all knowledge from MeaningfulUnits."""
        # TODO: Implement in Phase 4
        pass
    
    async def _store_knowledge(self, extraction_results: Dict[str, Any], meaningful_units: List[Any]) -> None:
        """Store extracted knowledge in Neo4j."""
        # TODO: Implement in Phase 4
        pass
    
    async def _run_analysis(self, episode_id: str) -> Dict[str, Any]:
        """Run all analysis modules."""
        # TODO: Implement in Phase 5
        pass
    
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
        
        self.logger.info(f"Starting pipeline processing for episode {episode_id}")
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
            self._start_phase("VTT_PARSING")
            segments = await self._parse_vtt(vtt_path)
            result['stats']['segments_parsed'] = len(segments) if segments else 0
            result['phases_completed'].append("VTT_PARSING")
            self._end_phase()
            
            # PHASE 2: Speaker Identification
            self._start_phase("SPEAKER_IDENTIFICATION")
            identified_segments = await self._identify_speakers(segments, episode_metadata)
            result['stats']['speakers_identified'] = len(set(
                seg.speaker for seg in identified_segments if hasattr(seg, 'speaker') and seg.speaker
            )) if identified_segments else 0
            result['phases_completed'].append("SPEAKER_IDENTIFICATION")
            self._end_phase()
            
            # PHASE 3: Conversation Analysis
            self._start_phase("CONVERSATION_ANALYSIS")
            conversation_structure = await self._analyze_conversation(identified_segments)
            result['phases_completed'].append("CONVERSATION_ANALYSIS")
            self._end_phase()
            
            # PHASE 4: Create MeaningfulUnits
            self._start_phase("MEANINGFUL_UNIT_CREATION")
            meaningful_units = await self._create_meaningful_units(
                identified_segments, conversation_structure
            )
            result['stats']['meaningful_units_created'] = len(meaningful_units) if meaningful_units else 0
            result['phases_completed'].append("MEANINGFUL_UNIT_CREATION")
            self._end_phase()
            
            # PHASE 5: Store Episode Structure
            self._start_phase("EPISODE_STORAGE")
            await self._store_episode_structure(episode_metadata, meaningful_units)
            result['phases_completed'].append("EPISODE_STORAGE")
            self._end_phase()
            
            # PHASE 6: Knowledge Extraction
            self._start_phase("KNOWLEDGE_EXTRACTION")
            extraction_results = await self._extract_knowledge(meaningful_units)
            if extraction_results:
                result['stats']['entities_extracted'] = len(extraction_results.get('entities', []))
                result['stats']['insights_extracted'] = len(extraction_results.get('insights', []))
                result['stats']['quotes_extracted'] = len(extraction_results.get('quotes', []))
            result['phases_completed'].append("KNOWLEDGE_EXTRACTION")
            self._end_phase()
            
            # PHASE 7: Store Knowledge
            self._start_phase("KNOWLEDGE_STORAGE")
            await self._store_knowledge(extraction_results, meaningful_units)
            result['phases_completed'].append("KNOWLEDGE_STORAGE")
            self._end_phase()
            
            # PHASE 8: Run Analysis
            self._start_phase("ANALYSIS")
            analysis_results = await self._run_analysis(episode_id)
            result['stats']['analysis_results'] = analysis_results or {}
            result['phases_completed'].append("ANALYSIS")
            self._end_phase()
            
            # Success - update result
            result['status'] = 'completed'
            result['phase_timings'] = self.phase_timings.copy()
            
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
            
        return result