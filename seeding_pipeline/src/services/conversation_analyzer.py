"""Conversation structure analysis service for semantic segmentation."""

import logging
from typing import List, Dict, Any, Optional
from src.core.interfaces import TranscriptSegment
from src.services.llm_service import LLMService
from src.core.monitoring import trace_operation
from src.core.exceptions import ProcessingError
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
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize conversation analyzer.
        
        Args:
            llm_service: LLM service for structure analysis
        """
        self.llm_service = llm_service
        self.logger = logger
        
    @trace_operation("analyze_conversation_structure")
    def analyze_structure(self, segments: List[TranscriptSegment]) -> ConversationStructure:
        """
        Analyze full transcript to identify semantic boundaries and structure.
        
        Args:
            segments: List of VTT segments to analyze
            
        Returns:
            ConversationStructure with identified units, themes, and insights
            
        Raises:
            ProcessingError: If analysis fails
        """
        if not segments:
            raise ProcessingError("No segments provided for analysis")
            
        self.logger.info(f"Analyzing conversation structure for {len(segments)} segments")
        
        try:
            # Prepare transcript for analysis
            transcript_data = self._prepare_transcript_data(segments)
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(transcript_data)
            
            # Get structured response from LLM
            response = self.llm_service.generate_completion(
                prompt=prompt,
                system_prompt="You are an expert conversation analyst specializing in podcast and interview structure.",
                response_format=ConversationStructure,
                temperature=0.1  # Low temperature for consistent analysis
            )
            
            # Parse and validate response
            if isinstance(response, dict):
                structure = ConversationStructure(**response)
            elif isinstance(response, ConversationStructure):
                structure = response
            else:
                # Fallback parsing for string responses
                import json
                structure_dict = json.loads(response)
                structure = ConversationStructure(**structure_dict)
            
            # Validate structure
            self._validate_structure(structure, len(segments))
            
            self.logger.info(f"Identified {len(structure.units)} conversation units from {len(segments)} segments")
            return structure
            
        except Exception as e:
            self.logger.error(f"Failed to analyze conversation structure: {str(e)}")
            raise ProcessingError(f"Conversation structure analysis failed: {str(e)}")
    
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