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
        self.logger.info("This may take several minutes for long transcripts...")
        
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
            # Use JSON mode for reliable parsing
            system_prompt = "You are an expert conversation analyst specializing in podcast and interview structure. Generate valid JSON output."
            full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response_data = self.llm_service.complete_with_options(
                prompt=full_prompt,
                temperature=0.2,
                json_mode=True
            )
            response = response_data['content']
            
            # Parse and validate response
            if isinstance(response, dict):
                # Fix any invalid unit indices before creating ConversationStructure
                response = self._fix_invalid_indices(response, len(segments))
                structure = ConversationStructure(**response)
            elif isinstance(response, ConversationStructure):
                structure = response
            else:
                # Fallback parsing for string responses
                import json
                try:
                    # Parse JSON (no cleaning needed with native JSON mode)
                    structure_dict = json.loads(response)
                    # Fix any invalid unit indices before creating ConversationStructure
                    structure_dict = self._fix_invalid_indices(structure_dict, len(segments))
                    structure = ConversationStructure(**structure_dict)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON parsing failed: {e}")
                    # Try to fix common JSON issues
                    try:
                        # Try to load with ast.literal_eval as fallback
                        import ast
                        structure_dict = ast.literal_eval(response)
                        # Fix any invalid unit indices before creating ConversationStructure
                        structure_dict = self._fix_invalid_indices(structure_dict, len(segments))
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
            # Handle both TranscriptSegment objects and dictionaries
            if isinstance(segment, dict):
                speaker = segment.get('speaker') or "Unknown"
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
            else:
                speaker = segment.speaker or "Unknown"
                text = segment.text
                start_time = segment.start_time
                end_time = segment.end_time
            
            # Track speaker statistics
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {"count": 0, "total_duration": 0.0}
            speaker_stats[speaker]["count"] += 1
            speaker_stats[speaker]["total_duration"] += (end_time - start_time)
            
            # Format segment with index and timing
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            line = f"[{i}] [{speaker} {time_str}] {text}"
            transcript_lines.append(line)
        
        return {
            "transcript": "\n".join(transcript_lines),
            "speaker_stats": speaker_stats,
            "total_segments": len(segments),
            "total_duration": (segments[-1]['end_time'] if isinstance(segments[-1], dict) else segments[-1].end_time) if segments else 0
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
- units: List of semantic conversation units (keep descriptions under 400 characters)
- themes: Major themes throughout the conversation (keep descriptions under 400 characters)
- flow: Overall narrative arc (keep opening/development/conclusion under 800 characters each)
- insights: Structural observations including fragmentation issues
- boundaries: Key boundary points between units
- total_segments: {transcript_data['total_segments']}

IMPORTANT: Keep all text descriptions concise and focused. Avoid lengthy explanations.
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
    
    def _fix_invalid_indices(self, structure_dict: Dict[str, Any], total_segments: int) -> Dict[str, Any]:
        """Fix any invalid indices in the structure before validation."""
        # Fix field name mismatches in units
        if 'units' in structure_dict:
            for unit in structure_dict['units']:
                if isinstance(unit, dict):
                    # Handle segments array format
                    if 'segments' in unit and isinstance(unit['segments'], list):
                        if unit['segments']:
                            unit['start_index'] = unit['segments'][0]
                            unit['end_index'] = unit['segments'][-1]
                        else:
                            unit['start_index'] = 0
                            unit['end_index'] = 0
                    # Map field names
                    if 'start_segment_index' in unit and 'start_index' not in unit:
                        unit['start_index'] = unit.pop('start_segment_index')
                    if 'end_segment_index' in unit and 'end_index' not in unit:
                        unit['end_index'] = unit.pop('end_segment_index')
                    # Also handle start_segment/end_segment format
                    if 'start_segment' in unit and 'start_index' not in unit:
                        unit['start_index'] = unit.pop('start_segment')
                    if 'end_segment' in unit and 'end_index' not in unit:
                        unit['end_index'] = unit.pop('end_segment')
                    
                    # Ensure start_index and end_index exist (required fields)
                    if 'start_index' not in unit:
                        self.logger.warning(f"Unit missing start_index, defaulting to 0")
                        unit['start_index'] = 0
                    if 'end_index' not in unit:
                        self.logger.warning(f"Unit missing end_index, defaulting to start_index")
                        unit['end_index'] = unit.get('start_index', 0)
                    
                    # Ensure required fields have defaults
                    if 'unit_type' not in unit:
                        unit['unit_type'] = 'topic_discussion'
                    if 'completeness' not in unit:
                        unit['completeness'] = 'complete'
                    else:
                        # Normalize completeness to lowercase
                        unit['completeness'] = str(unit['completeness']).lower()
                    if 'confidence' not in unit:
                        unit['confidence'] = 0.8
                    
                    # Ensure description field exists (required field)
                    if 'description' not in unit:
                        if 'summary' in unit:
                            unit['description'] = unit['summary'][:400] if len(unit['summary']) > 400 else unit['summary']
                        elif 'content' in unit:
                            unit['description'] = unit['content'][:400] if len(unit['content']) > 400 else unit['content']
                        else:
                            unit['description'] = f"Unit {unit.get('unit_id', 'unknown')}"
        
        # Fix themes format
        if 'themes' in structure_dict:
            fixed_themes = []
            for theme in structure_dict['themes']:
                if isinstance(theme, str):
                    # Convert string to theme dict
                    fixed_themes.append({
                        'theme': theme.split(':')[0].strip() if ':' in theme else theme,
                        'description': theme.split(':', 1)[1].strip() if ':' in theme else theme,
                        'evolution': 'Theme remains consistent throughout the conversation',
                        'related_units': []
                    })
                elif isinstance(theme, dict):
                    # Create a copy to avoid modifying the original in place
                    theme_copy = dict(theme)
                    # Map 'id' or 'name' to 'theme' if needed
                    if 'theme' not in theme_copy:
                        if 'id' in theme_copy:
                            theme_copy['theme'] = f"Theme {theme_copy.pop('id')}"
                        elif 'name' in theme_copy:
                            theme_copy['theme'] = theme_copy.pop('name')
                        else:
                            theme_copy['theme'] = 'Unknown Theme'
                    # Ensure evolution field exists
                    if 'evolution' not in theme_copy:
                        theme_copy['evolution'] = theme_copy.get('description', 'Theme remains consistent throughout the conversation')[:400]
                    # Ensure related_units exists
                    if 'related_units' not in theme_copy:
                        theme_copy['related_units'] = []
                    fixed_themes.append(theme_copy)
            structure_dict['themes'] = fixed_themes
            
            # Now fix invalid unit indices
            max_unit_index = len(structure_dict.get('units', [])) - 1
            for theme in structure_dict['themes']:
                if 'related_units' in theme:
                    # Filter out invalid unit indices
                    valid_units = []
                    for unit_idx in theme['related_units']:
                        if 0 <= unit_idx <= max_unit_index:
                            valid_units.append(unit_idx)
                        else:
                            self.logger.warning(
                                f"Removing invalid unit index {unit_idx} from theme '{theme.get('theme', 'Unknown')}' "
                                f"(max valid index: {max_unit_index})"
                            )
                    theme['related_units'] = valid_units
        
        # Fix boundary indices that are out of range
        if 'boundaries' in structure_dict:
            valid_boundaries = []
            for boundary in structure_dict['boundaries']:
                if isinstance(boundary, dict) and 'segment_index' in boundary:
                    if 0 <= boundary['segment_index'] < total_segments:
                        # Ensure all required fields exist
                        if 'boundary_type' not in boundary:
                            # Try to infer from description or default
                            if 'description' in boundary:
                                desc_lower = boundary['description'].lower()
                                if 'topic' in desc_lower or 'shift' in desc_lower:
                                    boundary['boundary_type'] = 'topic_shift'
                                elif 'speaker' in desc_lower:
                                    boundary['boundary_type'] = 'speaker_change'
                                elif 'end' in desc_lower or 'conclusion' in desc_lower:
                                    boundary['boundary_type'] = 'story_end'
                                else:
                                    boundary['boundary_type'] = 'topic_shift'
                            else:
                                boundary['boundary_type'] = 'topic_shift'
                        
                        if 'confidence' not in boundary:
                            boundary['confidence'] = 0.7  # Default confidence
                        
                        if 'reason' not in boundary:
                            # Use description if available, otherwise create default
                            if 'description' in boundary:
                                boundary['reason'] = boundary['description']
                            else:
                                boundary['reason'] = f"Boundary at segment {boundary['segment_index']}"
                        
                        valid_boundaries.append(boundary)
                    else:
                        self.logger.warning(
                            f"Removing invalid boundary at segment index {boundary['segment_index']} "
                            f"(max valid index: {total_segments - 1})"
                        )
            structure_dict['boundaries'] = valid_boundaries
        
        # Fix unit indices that are out of range
        if 'units' in structure_dict:
            for unit in structure_dict['units']:
                if isinstance(unit, dict):
                    # Clamp start and end indices to valid range
                    if 'start_index' in unit:
                        unit['start_index'] = max(0, min(unit['start_index'], total_segments - 1))
                    if 'end_index' in unit:
                        unit['end_index'] = max(0, min(unit['end_index'], total_segments - 1))
                    # Ensure start <= end
                    if 'start_index' in unit and 'end_index' in unit:
                        if unit['start_index'] > unit['end_index']:
                            unit['start_index'], unit['end_index'] = unit['end_index'], unit['start_index']
        
        # Fix insights structure
        if 'insights' in structure_dict:
            if isinstance(structure_dict['insights'], str):
                # Convert string to insights dict
                structure_dict['insights'] = {
                    'fragmentation_issues': [structure_dict['insights']],
                    'missing_context': [],
                    'natural_boundaries': [],
                    'overall_coherence': 0.7
                }
            elif isinstance(structure_dict['insights'], list):
                # Convert list to insights dict - assume they're fragmentation issues
                structure_dict['insights'] = {
                    'fragmentation_issues': structure_dict['insights'],
                    'missing_context': [],
                    'natural_boundaries': [],
                    'overall_coherence': 0.7
                }
            elif isinstance(structure_dict['insights'], dict):
                # Fix field name mappings
                if 'structural_observations' in structure_dict['insights'] and 'fragmentation_issues' not in structure_dict['insights']:
                    structure_dict['insights']['fragmentation_issues'] = structure_dict['insights'].pop('structural_observations', [])
                if 'fragmentation_points' in structure_dict['insights'] and 'fragmentation_issues' not in structure_dict['insights']:
                    structure_dict['insights']['fragmentation_issues'] = structure_dict['insights'].pop('fragmentation_points', [])
                
                # Fix overall_coherence if it's a string
                if 'overall_coherence' in structure_dict['insights']:
                    coherence = structure_dict['insights']['overall_coherence']
                    if isinstance(coherence, str):
                        # Map common string values to floats
                        coherence_map = {
                            'excellent': 0.95, 'very good': 0.9, 'good': 0.8,
                            'moderate': 0.7, 'fair': 0.6, 'poor': 0.4,
                            'very poor': 0.2, 'terrible': 0.1,
                            'high': 0.85, 'medium': 0.65, 'low': 0.35
                        }
                        # Try to extract number from string like "0.8" or "8/10"
                        import re
                        number_match = re.search(r'(\d+\.?\d*)', coherence)
                        if number_match:
                            value = float(number_match.group(1))
                            # If it's greater than 1, assume it's out of 10
                            if value > 1:
                                value = value / 10
                            structure_dict['insights']['overall_coherence'] = min(1.0, max(0.0, value))
                        else:
                            structure_dict['insights']['overall_coherence'] = coherence_map.get(
                                coherence.lower().strip(), 0.7  # Default to 0.7 if not recognized
                            )
                else:
                    structure_dict['insights']['overall_coherence'] = 0.7
                
                # Ensure all required fields exist and are lists
                if 'fragmentation_issues' not in structure_dict['insights']:
                    structure_dict['insights']['fragmentation_issues'] = []
                elif isinstance(structure_dict['insights']['fragmentation_issues'], str):
                    # Convert string to list
                    structure_dict['insights']['fragmentation_issues'] = [structure_dict['insights']['fragmentation_issues']]
                elif isinstance(structure_dict['insights']['fragmentation_issues'], list):
                    # Convert any dict items to strings
                    fixed_issues = []
                    for issue in structure_dict['insights']['fragmentation_issues']:
                        if isinstance(issue, dict):
                            # Convert dict to string format
                            if 'type' in issue and 'description' in issue:
                                fixed_issues.append(f"{issue['type']}: {issue['description']}")
                            elif 'type' in issue:
                                fixed_issues.append(issue['type'])
                            elif 'description' in issue:
                                fixed_issues.append(issue['description'])
                            else:
                                # Fallback: convert dict to string representation
                                fixed_issues.append(str(issue))
                        elif isinstance(issue, str):
                            fixed_issues.append(issue)
                        else:
                            # Convert any other type to string
                            fixed_issues.append(str(issue))
                    structure_dict['insights']['fragmentation_issues'] = fixed_issues
                
                if 'missing_context' not in structure_dict['insights']:
                    structure_dict['insights']['missing_context'] = []
                elif isinstance(structure_dict['insights']['missing_context'], str):
                    # Convert string to list
                    structure_dict['insights']['missing_context'] = [structure_dict['insights']['missing_context']]
                elif isinstance(structure_dict['insights']['missing_context'], list):
                    # Convert any dict items to strings
                    fixed_context = []
                    for context in structure_dict['insights']['missing_context']:
                        if isinstance(context, dict):
                            # Convert dict to string format
                            if 'type' in context and 'description' in context:
                                fixed_context.append(f"{context['type']}: {context['description']}")
                            elif 'description' in context:
                                fixed_context.append(context['description'])
                            elif 'context' in context:
                                fixed_context.append(context['context'])
                            else:
                                # Fallback: convert dict to string representation
                                fixed_context.append(str(context))
                        elif isinstance(context, str):
                            fixed_context.append(context)
                        else:
                            # Convert any other type to string
                            fixed_context.append(str(context))
                    structure_dict['insights']['missing_context'] = fixed_context
                
                if 'natural_boundaries' not in structure_dict['insights']:
                    structure_dict['insights']['natural_boundaries'] = []
                elif isinstance(structure_dict['insights']['natural_boundaries'], (str, int, float)):
                    # Convert non-list to list
                    structure_dict['insights']['natural_boundaries'] = [structure_dict['insights']['natural_boundaries']]
        
        # Ensure required top-level fields exist
        if 'flow' not in structure_dict:
            structure_dict['flow'] = {
                'opening': 'The conversation begins',
                'development': 'The main discussion unfolds',
                'conclusion': 'The conversation concludes'
            }
        
        if 'boundaries' not in structure_dict:
            structure_dict['boundaries'] = []
        
        if 'total_segments' not in structure_dict:
            structure_dict['total_segments'] = total_segments
        
        return structure_dict
    
    def _create_fallback_structure(self, segments: List[TranscriptSegment]) -> ConversationStructure:
        """Create a minimal fallback conversation structure."""
        # Create a single conversation unit covering all segments
        unit = ConversationUnit(
            start_index=0,
            end_index=len(segments) - 1,
            unit_type="topic_discussion",
            description="Full conversation - fallback structure",
            completeness="complete",
            key_entities=[],
            confidence=0.5
        )
        
        # Create minimal structure
        structure = ConversationStructure(
            units=[unit],
            themes=[],
            boundaries=[],
            flow=ConversationFlow(
                opening="Conversation begins",
                development="Content proceeds linearly",
                conclusion="Conversation ends"
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[],
                overall_coherence=0.5
            ),
            total_segments=len(segments)
        )
        
        return structure
