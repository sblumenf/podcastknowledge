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
from src.vtt.vtt_segmenter import VTTSegmenter

# Conversation Analysis
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.segment_regrouper import SegmentRegrouper

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
    async def _parse_vtt(self, vtt_path: Path) -> List[Any]:
        """Parse VTT file into segments."""
        # TODO: Implement in Phase 3
        pass
    
    async def _identify_speakers(self, segments: List[Any], episode_metadata: Dict) -> List[Any]:
        """Identify speakers in segments."""
        # TODO: Implement in Phase 3
        pass
    
    async def _analyze_conversation(self, segments: List[Any]) -> Any:
        """Analyze conversation structure."""
        # TODO: Implement in Phase 3
        pass
    
    async def _create_meaningful_units(self, segments: List[Any], structure: Any) -> List[Any]:
        """Create MeaningfulUnits from segments."""
        # TODO: Implement in Phase 3
        pass
    
    async def _store_episode_structure(self, episode_metadata: Dict, meaningful_units: List[Any]) -> None:
        """Store episode and MeaningfulUnits in Neo4j."""
        # TODO: Implement in Phase 3
        pass
    
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
        # TODO: Implement in Task 2.3
        pass