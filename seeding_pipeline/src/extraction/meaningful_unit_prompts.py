"""Optimized prompts for meaningful unit extraction."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from src.extraction.prompts import PromptTemplate, PromptVersion
from src.services.segment_regrouper import MeaningfulUnit
import json


@dataclass
class MeaningfulUnitPromptBuilder:
    """Builder for creating prompts optimized for meaningful conversation units."""
    
    def __init__(self):
        """Initialize the prompt builder with unit-specific templates."""
        self.templates = self._initialize_templates()
        
    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize prompt templates for meaningful units."""
        templates = {}
        
        # Combined extraction for meaningful units
        templates['unit_extraction'] = PromptTemplate(
            name='unit_extraction',
            version=PromptVersion.V2_0,
            template="""Analyze this semantically coherent conversation unit and extract structured knowledge.

UNIT METADATA:
- Type: {unit_type}
- Summary: {unit_summary}
- Themes: {themes}
- Duration: {duration} seconds
- Speakers: {speakers}
- Completeness: {completeness_status}

CONVERSATION CONTENT:
{content}

EXTRACTION TASKS:

1. ENTITIES - Extract all important entities mentioned in this unit
   Consider the unit context when determining entity importance. Entities central to {unit_type} should be prioritized.
   
   For each entity provide:
   - name: As it appears in the conversation
   - type: Person/Organization/Concept/Product/Technology/Method/Study/Location/Event
   - description: One-sentence description based on this unit's discussion
   - role_in_unit: How this entity relates to the unit's main topic
   - mentions: Number of times referenced
   - importance: 1-10 based on relevance to {unit_summary}

2. INSIGHTS - Extract key insights specific to this {unit_type}
   {unit_specific_guidance}
   
   For each insight:
   - content: The insight (1-3 sentences)
   - type: {insight_types}
   - evidence_level: strong/moderate/anecdotal/theoretical
   - relevance_to_themes: Which of the unit themes this relates to
   - speaker_attribution: Who provided this insight (if clear)

3. QUOTES - Extract the most impactful quotes from this unit
   Focus on quotes that best represent the {unit_type}'s key messages.
   
   For each quote:
   - text: Exact quote (prefer 10-50 words)
   - speaker: Who said it
   - significance: Why this quote matters in the unit context
   - timestamp_context: beginning/middle/end of unit

4. RELATIONSHIPS - Identify relationships between entities within this unit
   - source: Source entity
   - target: Target entity  
   - relationship_type: Specific relationship
   - context: How this relationship is established in the unit

5. UNIT_SYNTHESIS - Provide a synthesis of this unit
   - key_takeaway: Main point in 1-2 sentences
   - unanswered_questions: Questions raised but not answered
   - connections_to_themes: How this unit develops the episode themes
   - quality_notes: Any issues with coherence or completeness

Format your response as valid JSON matching this structure:
{{
  "entities": [...],
  "insights": [...],
  "quotes": [...],
  "relationships": [...],
  "unit_synthesis": {{...}}
}}""",
            variables=['unit_type', 'unit_summary', 'themes', 'duration', 'speakers', 
                      'completeness_status', 'content', 'unit_specific_guidance', 'insight_types'],
            description='Extract knowledge from a meaningful conversation unit',
            use_large_context=True
        )
        
        # Unit type specific templates
        templates['topic_discussion_guidance'] = PromptTemplate(
            name='topic_discussion_guidance',
            version=PromptVersion.V2_0,
            template="""For this topic discussion unit, focus on:
- Core concepts being explained
- Arguments and evidence presented
- Different perspectives or viewpoints shared
- Conclusions or consensus reached
- Practical applications discussed""",
            variables=[],
            description='Guidance for topic discussion units',
            use_large_context=False
        )
        
        templates['qa_pair_guidance'] = PromptTemplate(
            name='qa_pair_guidance',
            version=PromptVersion.V2_0,
            template="""For this Q&A unit, focus on:
- The specific question asked
- Completeness of the answer
- Key points made in response
- Follow-up clarifications
- Whether the question was fully addressed""",
            variables=[],
            description='Guidance for Q&A pair units',
            use_large_context=False
        )
        
        templates['story_guidance'] = PromptTemplate(
            name='story_guidance',
            version=PromptVersion.V2_0,
            template="""For this story/narrative unit, focus on:
- The main narrative or example
- Key lessons or morals
- Characters or entities involved
- Timeline of events
- How the story supports broader points""",
            variables=[],
            description='Guidance for story units',
            use_large_context=False
        )
        
        # Cross-unit analysis template
        templates['cross_unit_analysis'] = PromptTemplate(
            name='cross_unit_analysis',
            version=PromptVersion.V2_0,
            template="""Analyze relationships and patterns across these conversation units.

UNITS SUMMARY:
{units_summary}

ANALYSIS TASKS:

1. THEME EVOLUTION
   - How do the main themes develop across units?
   - Which themes are introduced, developed, and concluded?
   - Are there any unresolved themes?

2. ENTITY TRACKING
   - Which entities appear across multiple units?
   - How do entity relationships evolve?
   - Are there any entity contradictions?

3. NARRATIVE FLOW
   - How do the units connect to form a coherent narrative?
   - Are there logical gaps between units?
   - What is the overall story arc?

4. KNOWLEDGE SYNTHESIS
   - What are the main conclusions across all units?
   - Which insights are reinforced across units?
   - What questions remain unanswered?

Provide your analysis as JSON:
{{
  "theme_evolution": [...],
  "cross_unit_entities": [...],
  "narrative_analysis": {{...}},
  "synthesized_insights": [...]
}}""",
            variables=['units_summary'],
            description='Analyze patterns across multiple conversation units',
            use_large_context=True
        )
        
        # Entity resolution template for unit context
        templates['unit_entity_resolution'] = PromptTemplate(
            name='unit_entity_resolution',
            version=PromptVersion.V2_0,
            template="""Resolve and consolidate entity references within this conversation unit.

UNIT CONTEXT:
- Type: {unit_type}
- Summary: {unit_summary}

RAW ENTITIES FOUND:
{raw_entities}

RESOLUTION TASKS:
1. Identify which references refer to the same entity (e.g., "Dr. Smith", "John Smith", "the doctor")
2. Determine the most complete/formal name for each entity
3. Classify any ambiguous references based on unit context
4. Note any entities that need more context for proper identification

For each resolved entity provide:
- canonical_name: The primary name to use
- aliases: List of alternative references
- type: Most specific type based on unit context
- confidence: How certain the resolution is (0.0-1.0)
- resolution_notes: Any ambiguities or assumptions

Return as JSON list of resolved entities.""",
            variables=['unit_type', 'unit_summary', 'raw_entities'],
            description='Resolve entity references within unit context',
            use_large_context=False
        )
        
        # Insight quality scoring template
        templates['insight_scoring'] = PromptTemplate(
            name='insight_scoring',
            version=PromptVersion.V2_0,
            template="""Score the quality and importance of insights extracted from this unit.

UNIT CONTEXT:
{unit_context}

INSIGHTS TO SCORE:
{insights}

SCORING CRITERIA:
1. Novelty: Is this a new/unique insight or common knowledge?
2. Evidence: How well supported is this insight?
3. Actionability: Can someone act on this insight?
4. Relevance: How central is this to the unit's themes?
5. Clarity: How clearly is the insight expressed?

For each insight, provide:
- insight_id: Reference to the insight
- scores: Object with scores (1-10) for each criterion
- overall_score: Weighted average (1-10)
- recommendation: keep/enhance/remove
- enhancement_suggestion: How to improve if needed

Return as JSON list.""",
            variables=['unit_context', 'insights'],
            description='Score and rank insights for quality',
            use_large_context=False
        )
        
        return templates
    
    def build_unit_extraction_prompt(self, unit: MeaningfulUnit) -> str:
        """
        Build extraction prompt for a meaningful unit.
        
        Args:
            unit: The meaningful unit to process
            
        Returns:
            Formatted prompt for extraction
        """
        # Get unit-specific guidance based on type
        guidance = self._get_unit_specific_guidance(unit.unit_type)
        insight_types = self._get_insight_types_for_unit(unit.unit_type)
        
        # Format speakers
        speakers_str = ", ".join([
            f"{speaker} ({pct:.0f}%)" 
            for speaker, pct in unit.speaker_distribution.items()
        ])
        
        # Format themes
        themes_str = ", ".join(unit.themes) if unit.themes else "General discussion"
        
        # Format completeness
        completeness = "Complete" if unit.is_complete else f"Incomplete - {unit.metadata.get('completeness_note', 'truncated')}"
        
        # Combine segment texts
        content_lines = []
        for i, segment in enumerate(unit.segments):
            speaker = segment.speaker or "Unknown"
            text = segment.text
            content_lines.append(f"[{speaker}] {text}")
        content = "\n\n".join(content_lines)
        
        # Build prompt
        template = self.templates['unit_extraction']
        return template.format(
            unit_type=unit.unit_type,
            unit_summary=unit.summary,
            themes=themes_str,
            duration=f"{unit.duration:.1f}",
            speakers=speakers_str,
            completeness_status=completeness,
            content=content,
            unit_specific_guidance=guidance,
            insight_types=insight_types
        )
    
    def _get_unit_specific_guidance(self, unit_type: str) -> str:
        """Get extraction guidance specific to unit type."""
        guidance_map = {
            'topic_discussion': self.templates['topic_discussion_guidance'].template,
            'q&a_pair': self.templates['qa_pair_guidance'].template,
            'story': self.templates['story_guidance'].template,
            'introduction': "Focus on: Setting context, introducing speakers, episode overview, key topics to be covered",
            'conclusion': "Focus on: Summary points, key takeaways, calls to action, future directions",
        }
        return guidance_map.get(unit_type, "Focus on extracting the main points and supporting details.")
    
    def _get_insight_types_for_unit(self, unit_type: str) -> str:
        """Get relevant insight types for the unit type."""
        type_map = {
            'topic_discussion': "factual/conceptual/analytical/comparative",
            'q&a_pair': "answer/clarification/follow_up/example",
            'story': "lesson/moral/example/illustration",
            'introduction': "overview/context/preview/goal",
            'conclusion': "summary/takeaway/action_item/reflection"
        }
        return type_map.get(unit_type, "key_point/observation/conclusion")
    
    def build_cross_unit_analysis_prompt(self, units: List[MeaningfulUnit]) -> str:
        """
        Build prompt for analyzing patterns across multiple units.
        
        Args:
            units: List of meaningful units to analyze
            
        Returns:
            Formatted prompt for cross-unit analysis
        """
        # Create units summary
        units_summary_parts = []
        for i, unit in enumerate(units):
            summary = {
                'index': i,
                'type': unit.unit_type,
                'summary': unit.summary,
                'themes': unit.themes,
                'duration': f"{unit.duration:.1f}s",
                'complete': unit.is_complete
            }
            units_summary_parts.append(json.dumps(summary, indent=2))
        
        units_summary = "\n\n".join(units_summary_parts)
        
        template = self.templates['cross_unit_analysis']
        return template.format(units_summary=units_summary)
    
    def build_entity_resolution_prompt(
        self, 
        unit: MeaningfulUnit, 
        raw_entities: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for entity resolution within unit context.
        
        Args:
            unit: The meaningful unit providing context
            raw_entities: List of raw extracted entities
            
        Returns:
            Formatted prompt for entity resolution
        """
        # Format raw entities
        entities_str = json.dumps(raw_entities, indent=2)
        
        template = self.templates['unit_entity_resolution']
        return template.format(
            unit_type=unit.unit_type,
            unit_summary=unit.summary,
            raw_entities=entities_str
        )
    
    def build_insight_scoring_prompt(
        self,
        unit: MeaningfulUnit,
        insights: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for scoring insight quality.
        
        Args:
            unit: The meaningful unit providing context
            insights: List of extracted insights to score
            
        Returns:
            Formatted prompt for insight scoring
        """
        # Create unit context summary
        unit_context = {
            'type': unit.unit_type,
            'summary': unit.summary,
            'themes': unit.themes,
            'duration': unit.duration
        }
        
        template = self.templates['insight_scoring']
        return template.format(
            unit_context=json.dumps(unit_context, indent=2),
            insights=json.dumps(insights, indent=2)
        )
    
    def optimize_prompt_for_unit_batch(
        self,
        units: List[MeaningfulUnit],
        max_units_per_prompt: int = 5
    ) -> List[str]:
        """
        Create optimized prompts for processing multiple units efficiently.
        
        Args:
            units: List of meaningful units
            max_units_per_prompt: Maximum units to include in one prompt
            
        Returns:
            List of prompts for batch processing
        """
        prompts = []
        
        # Group units by type for more coherent prompts
        units_by_type = {}
        for unit in units:
            if unit.unit_type not in units_by_type:
                units_by_type[unit.unit_type] = []
            units_by_type[unit.unit_type].append(unit)
        
        # Create batched prompts
        for unit_type, typed_units in units_by_type.items():
            for i in range(0, len(typed_units), max_units_per_prompt):
                batch = typed_units[i:i + max_units_per_prompt]
                
                # Create a batch prompt
                batch_prompt = self._create_batch_prompt(batch, unit_type)
                prompts.append(batch_prompt)
        
        return prompts
    
    def _create_batch_prompt(self, units: List[MeaningfulUnit], unit_type: str) -> str:
        """Create a prompt for processing multiple units of the same type."""
        prompt_parts = [
            f"Analyze these {len(units)} {unit_type} units and extract knowledge from each.",
            f"Process each unit independently but note any connections between them.",
            ""
        ]
        
        for i, unit in enumerate(units):
            prompt_parts.append(f"UNIT {i+1}:")
            prompt_parts.append(self.build_unit_extraction_prompt(unit))
            prompt_parts.append("")
        
        prompt_parts.append("Return a JSON array with extraction results for each unit in order.")
        
        return "\n".join(prompt_parts)