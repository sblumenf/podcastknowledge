"""Conversation structure analysis service for semantic segmentation."""

import logging
from typing import List, Dict, Any, Optional
from src.core.interfaces import TranscriptSegment
from src.services.llm import LLMService
from src.services.performance_optimizer import PerformanceOptimizer
# from src.core.monitoring import trace_operation  # Module doesn't exist
from src.core.exceptions import PipelineError
from src.core.conversation_models.conversation import (
    ConversationBoundary,
    ConversationUnit,
    ConversationTheme,
    ConversationFlow,
    StructuralInsights,
    ConversationStructure
)

logger = logging.getLogger(__name__)
    

class ConversationAnalyzer:
    """Analyzes transcript segments to identify semantic boundaries and structure."""
    
    def __init__(self, llm_service: LLMService, performance_optimizer: Optional[PerformanceOptimizer] = None):
        """
        Initialize conversation analyzer.
        
        Args:
            llm_service: LLM service for structure analysis
            performance_optimizer: Optional performance optimizer for caching
        """
        self.llm_service = llm_service
        self.logger = logger
        self.optimizer = performance_optimizer
        
    # @trace_operation("analyze_conversation_structure")  # Decorator not available
    def analyze_structure(self, segments: List[TranscriptSegment]) -> ConversationStructure:
        """
        Analyze full transcript to identify semantic boundaries and structure.
        
        Args:
            segments: List of VTT segments to analyze
            
        Returns:
            ConversationStructure with identified units, themes, and insights
            
        Raises:
            PipelineError: If analysis fails
        """
        if not segments:
            raise PipelineError("No segments provided for analysis")
            
        self.logger.info(f"Analyzing conversation structure for {len(segments)} segments")
        
        # Check cache if optimizer is available
        transcript_hash = None
        if self.optimizer:
            transcript_hash = self.optimizer.compute_transcript_hash(segments)
            cached_structure = self.optimizer.get_cached_structure(transcript_hash)
            if cached_structure:
                self.logger.info("Using cached conversation structure")
                return cached_structure
        
        try:
            # Prepare transcript for analysis
            transcript_data = self._prepare_transcript_data(segments)
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(transcript_data)
            
            # Get structured response from LLM
            # Use a higher temperature to allow more flexibility
            response = self.llm_service.generate_completion(
                prompt=prompt,
                system_prompt="You are an expert conversation analyst specializing in podcast and interview structure. Generate valid JSON output.",
                response_format=ConversationStructure,
                temperature=0.2  # Slightly higher temperature
            )
            
            # Parse and validate response
            if isinstance(response, dict):
                structure = ConversationStructure(**response)
            elif isinstance(response, ConversationStructure):
                structure = response
            else:
                # Fallback parsing for string responses
                import json
                try:
                    # Clean up the response if needed
                    if isinstance(response, str):
                        # Try to extract JSON from the response
                        response = response.strip()
                        # If response starts with ```json, extract the JSON part
                        if response.startswith('```json'):
                            response = response[7:]  # Remove ```json
                            if response.endswith('```'):
                                response = response[:-3]  # Remove trailing ```
                        response = response.strip()
                    
                    structure_dict = json.loads(response)
                    structure = ConversationStructure(**structure_dict)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON parsing failed: {e}")
                    # Try to fix common JSON issues
                    try:
                        # Try to load with ast.literal_eval as fallback
                        import ast
                        structure_dict = ast.literal_eval(response)
                        structure = ConversationStructure(**structure_dict)
                    except:
                        # Create a minimal valid structure as fallback
                        self.logger.warning("Creating fallback conversation structure")
                        structure = self._create_fallback_structure(segments)
            
            # Validate structure
            self._validate_structure(structure, len(segments))
            
            # Cache the result if optimizer is available
            if self.optimizer and transcript_hash:
                self.optimizer.cache_conversation_structure(transcript_hash, structure)
            
            self.logger.info(f"Identified {len(structure.units)} conversation units from {len(segments)} segments")
            return structure
            
        except Exception as e:
            self.logger.error(f"Failed to analyze conversation structure: {str(e)}")
            raise PipelineError(f"Conversation structure analysis failed: {str(e)}")
    
    def _prepare_transcript_data(self, segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """Prepare transcript data for analysis."""
        # Create formatted transcript with segment markers
        transcript_lines = []
        speaker_stats = {}
        
        for i, segment in enumerate(segments):
            speaker = segment.speaker or "Unknown"
            
            # Track speaker statistics
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {"count": 0, "total_duration": 0.0}
            speaker_stats[speaker]["count"] += 1
            speaker_stats[speaker]["total_duration"] += (segment.end_time - segment.start_time)
            
            # Format segment with index and timing
            minutes = int(segment.start_time // 60)
            seconds = int(segment.start_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            line = f"[{i}] [{speaker} {time_str}] {segment.text}"
            transcript_lines.append(line)
        
        return {
            "transcript": "\n".join(transcript_lines),
            "speaker_stats": speaker_stats,
            "total_segments": len(segments),
            "total_duration": segments[-1].end_time if segments else 0
        }
    
    def _build_analysis_prompt(self, transcript_data: Dict[str, Any]) -> str:
        """Build prompt for conversation structure analysis."""
        speaker_summary = "\n".join([
            f"- {speaker}: {stats['count']} segments, {stats['total_duration']:.1f}s total"
            for speaker, stats in transcript_data["speaker_stats"].items()
        ])
        
        prompt = f"""Analyze this podcast/interview transcript to identify natural conversation structure.

TRANSCRIPT STATISTICS:
- Total segments: {transcript_data['total_segments']}
- Total duration: {transcript_data['total_duration']:.1f} seconds
- Speakers:
{speaker_summary}

TRANSCRIPT (format: [segment_index] [speaker timestamp] text):
{transcript_data['transcript']}

ANALYSIS REQUIREMENTS:
1. Identify natural conversation units where related content is discussed together
2. Detect boundaries where topics shift, stories end, or Q&A pairs complete
3. Note where arbitrary segmentation has split coherent thoughts
4. Identify major themes and how they evolve
5. Assess overall conversation flow and coherence

IMPORTANT GUIDELINES:
- Group segments that belong together semantically (complete thoughts, full stories, Q&A exchanges)
- A conversation unit should typically span multiple segments (average 5-10)
- Mark units as "incomplete" if they end mid-thought due to arbitrary segmentation
- Identify clear natural boundaries where new topics begin
- Consider speaker patterns (e.g., host questions followed by guest answers)

Return a JSON object matching the ConversationStructure schema with:
- units: List of semantic conversation units
- themes: Major themes throughout the conversation
- flow: Overall narrative arc
- insights: Structural observations including fragmentation issues
- boundaries: Key boundary points between units
- total_segments: {transcript_data['total_segments']}
"""
        return prompt
    
    def _validate_structure(self, structure: ConversationStructure, total_segments: int):
        """Validate the analyzed structure for consistency."""
        # Check that units cover all segments
        covered_segments = set()
        for unit in structure.units:
            if unit.start_index < 0 or unit.end_index >= total_segments:
                raise ValueError(f"Unit indices out of range: {unit.start_index}-{unit.end_index}")
            if unit.start_index > unit.end_index:
                raise ValueError(f"Invalid unit range: {unit.start_index}-{unit.end_index}")
            
            for i in range(unit.start_index, unit.end_index + 1):
                if i in covered_segments:
                    self.logger.warning(f"Segment {i} appears in multiple units")
                covered_segments.add(i)
        
        # Check coverage
        missing_segments = set(range(total_segments)) - covered_segments
        if missing_segments:
            self.logger.warning(f"Segments not covered by any unit: {sorted(missing_segments)}")
        
        # Validate boundaries
        for boundary in structure.boundaries:
            if boundary.segment_index < 0 or boundary.segment_index >= total_segments:
                raise ValueError(f"Boundary index out of range: {boundary.segment_index}")
        
        # Check themes reference valid units
        for theme in structure.themes:
            for unit_idx in theme.related_units:
                if unit_idx >= len(structure.units):
                    raise ValueError(f"Theme references invalid unit index: {unit_idx}")
    
    def _create_fallback_structure(self, segments: List[TranscriptSegment]) -> ConversationStructure:
        """Create a minimal fallback conversation structure."""
        # Create a single conversation unit covering all segments
        unit = ConversationUnit(
            start_index=0,
            end_index=len(segments) - 1,
            type="discussion",
            summary="Full conversation",
            key_points=["Complete transcript"],
            transitions=[]
        )
        
        # Create minimal structure
        structure = ConversationStructure(
            units=[unit],
            themes=[],
            boundaries=[],
            flow=ConversationFlow(
                overall_pattern="linear",
                key_transitions=[],
                narrative_arc="single-segment"
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[],
                overall_coherence=0.5
            )
        )
        
        return structure
