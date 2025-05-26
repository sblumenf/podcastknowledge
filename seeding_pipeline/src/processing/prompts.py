"""Prompt management and building for LLM interactions."""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.core.models import Entity, Insight


logger = logging.getLogger(__name__)


class PromptVersion(str, Enum):
    """Prompt versions for tracking changes."""
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"  # Large context version


@dataclass
class PromptTemplate:
    """Template for consistent prompt generation."""
    name: str
    version: str
    template: str
    variables: List[str]
    description: str
    use_large_context: bool = False
    
    def format(self, **kwargs) -> str:
        """Format the template with provided variables."""
        # Check all required variables are provided
        missing = set(self.variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")
            
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Template formatting error: {e}")
            

class PromptBuilder:
    """Builder for creating consistent prompts across the system."""
    
    def __init__(self, use_large_context: bool = True):
        """
        Initialize prompt builder.
        
        Args:
            use_large_context: Whether to use prompts optimized for large context
        """
        self.use_large_context = use_large_context
        self.version = PromptVersion.V2_0 if use_large_context else PromptVersion.V1_1
        self._templates = self._initialize_templates()
        
    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize all prompt templates."""
        templates = {}
        
        # Entity extraction prompts
        templates['entity_extraction_large'] = PromptTemplate(
            name='entity_extraction_large',
            version=PromptVersion.V2_0,
            template="""Extract named entities from the following podcast transcript. With your 1M token context window,
look for all key entities throughout the entire conversation.

Entity Types to Extract:
- General: Person, Company, Product, Technology, Concept, Book, Framework, Method, Location
- Research: Study, Institution, Researcher, Journal, Theory, Research_Method
- Medical: Medication, Condition, Treatment, Symptom, Biological_Process, Medical_Device
- Science: Chemical, Scientific_Theory, Laboratory, Experiment, Discovery

TRANSCRIPT:
{text}

For each entity, provide:
1. The entity name as it appears in the text
2. The entity type from the categories above
3. A brief one-sentence description synthesizing all mentions of this entity
4. A frequency count indicating how many times this entity is mentioned
5. Whether it's mentioned with scientific evidence or citations
6. Context type: research, clinical, anecdotal, or general

Pay special attention to:
- Scientific studies and their findings
- Medical conditions and treatments discussed
- Research institutions and researchers mentioned
- Biological processes and mechanisms explained
- Citations or references to scientific literature

Format your response as a valid JSON list of objects with these fields:
- name (string): The entity name
- type (string): The entity type from the list above
- description (string): Brief description synthesizing all mentions
- frequency (number): Approximate number of mentions
- importance (number): Importance score 1-10 based on discussion depth
- has_citation (boolean): Whether mentioned with studies/evidence
- context_type (string): research, clinical, anecdotal, or general

Only include entities that are clearly mentioned. Consolidate variants of the same entity.

JSON RESPONSE:""",
            variables=['text'],
            description='Extract entities from large transcript',
            use_large_context=True
        )
        
        templates['entity_extraction_small'] = PromptTemplate(
            name='entity_extraction_small',
            version=PromptVersion.V1_1,
            template="""Extract named entities from the following text.

Entity Types: Person, Company, Product, Technology, Concept, Book, Framework, Method,
Study, Institution, Researcher, Journal, Medication, Condition, Treatment, Symptom,
Biological_Process, Chemical, Scientific_Theory, Medical_Device

TEXT:
{text}

For each entity, provide:
1. The entity name as it appears in the text
2. The entity type from the list above
3. A brief one-sentence description if possible
4. Whether it includes a citation or evidence reference

Format your response as valid JSON list of objects with these fields:
- name (string): The entity name
- type (string): The entity type
- description (string): Brief description if known
- has_citation (boolean): Whether mentioned with evidence

Only include entities that are clearly mentioned in the text.

JSON RESPONSE:""",
            variables=['text'],
            description='Extract entities from text segment',
            use_large_context=False
        )
        
        # Insight extraction prompts
        templates['insight_extraction_large'] = PromptTemplate(
            name='insight_extraction_large',
            version=PromptVersion.V2_0,
            template="""Extract key insights from this podcast transcript. Focus on:
1. Main conclusions or findings discussed
2. Novel ideas or perspectives presented
3. Practical applications or recommendations
4. Counterintuitive or surprising points
5. Connections between different concepts
{entity_context}
TRANSCRIPT:
{text}

For each insight, provide:
- content: The insight itself (1-2 sentences)
- type: factual, conceptual, prediction, recommendation, key_point, technical, or methodological
- confidence: 0.0-1.0 based on evidence/support
- evidence: Brief note on supporting evidence if any
- related_entities: List of entity names this insight relates to

Format as JSON list. Extract 5-15 most important insights.

JSON RESPONSE:""",
            variables=['text', 'entity_context'],
            description='Extract insights from large transcript',
            use_large_context=True
        )
        
        templates['insight_extraction_small'] = PromptTemplate(
            name='insight_extraction_small',
            version=PromptVersion.V1_1,
            template="""Extract key insights from this text segment.
{entity_context}
TEXT:
{text}

For each insight:
- content: The insight (1-2 sentences)
- type: factual, conceptual, prediction, recommendation, key_point, technical, or methodological
- confidence: 0.0-1.0

Format as JSON list. Extract up to 5 insights.

JSON RESPONSE:""",
            variables=['text', 'entity_context'],
            description='Extract insights from text segment',
            use_large_context=False
        )
        
        # Quote extraction prompts
        templates['quote_extraction_large'] = PromptTemplate(
            name='quote_extraction_large',
            version=PromptVersion.V2_0,
            template="""Extract memorable, insightful, or important quotes from this podcast transcript.

TRANSCRIPT:
{text}

Look for:
1. Memorable statements that capture key ideas
2. Controversial or thought-provoking claims
3. Humorous or witty remarks
4. Clear explanations of complex concepts
5. Personal anecdotes or experiences
6. Strong opinions or predictions

For each quote:
- text: The exact quote
- speaker: Who said it (if identifiable)
- type: memorable, controversial, humorous, insightful, technical, or general
- context: Brief context (1 sentence)

Format as JSON list. Extract 5-10 best quotes.

JSON RESPONSE:""",
            variables=['text'],
            description='Extract quotes from large transcript',
            use_large_context=True
        )
        
        # Complexity analysis prompt
        templates['complexity_analysis'] = PromptTemplate(
            name='complexity_analysis',
            version=PromptVersion.V1_1,
            template="""Analyze the technical complexity of this text segment.

TEXT:
{text}

Identify:
1. Technical terms and jargon
2. Average sentence complexity
3. Required background knowledge
4. Target audience level

Classify as: layperson, intermediate, or expert

Return JSON: {{"classification": "...", "technical_density": 0.0-1.0, "explanation": "..."}}""",
            variables=['text'],
            description='Analyze text complexity',
            use_large_context=False
        )
        
        # Information density prompt
        templates['information_density'] = PromptTemplate(
            name='information_density',
            version=PromptVersion.V1_1,
            template="""Analyze the information density of this text segment.

TEXT:
{text}

Consider:
1. Number of distinct concepts introduced
2. Depth of explanation for each concept
3. Use of examples and analogies
4. Pacing of information delivery

{additional_context}

Rate information density from 0.0 (very sparse) to 1.0 (very dense).

Return JSON: {{"density": 0.0-1.0, "concept_count": N, "explanation": "..."}}""",
            variables=['text', 'additional_context'],
            description='Analyze information density',
            use_large_context=False
        )
        
        # Topic extraction prompt
        templates['topic_extraction'] = PromptTemplate(
            name='topic_extraction',
            version=PromptVersion.V1_1,
            template="""Identify the main topics discussed in this content.

{context}

TEXT:
{text}

For each topic:
- name: Topic name (2-4 words)
- description: Brief description (1 sentence)
- relevance: Score 0.0-1.0 based on discussion depth
- subtopics: List of related subtopics if any

Format as JSON list. Identify 3-7 main topics.

JSON RESPONSE:""",
            variables=['text', 'context'],
            description='Extract topics from content',
            use_large_context=False
        )
        
        # Sentiment analysis prompt
        templates['sentiment_analysis'] = PromptTemplate(
            name='sentiment_analysis',
            version=PromptVersion.V1_1,
            template="""Analyze the sentiment and emotional tone of this text.

TEXT:
{text}

Consider:
1. Overall emotional tone (positive, negative, neutral)
2. Specific emotions expressed (excitement, concern, skepticism, etc.)
3. Changes in sentiment throughout the text
4. Speaker attitudes toward topics discussed

Return JSON: {{"overall_sentiment": "...", "score": -1.0 to 1.0, "emotions": [...], "explanation": "..."}}""",
            variables=['text'],
            description='Analyze text sentiment',
            use_large_context=False
        )
        
        return templates
        
    def get_template(self, name: str) -> PromptTemplate:
        """Get a prompt template by name."""
        if name not in self._templates:
            raise ValueError(f"Unknown template: {name}")
        return self._templates[name]
        
    def build_entity_prompt(self, text: str) -> str:
        """Build entity extraction prompt."""
        template_name = 'entity_extraction_large' if self.use_large_context else 'entity_extraction_small'
        template = self.get_template(template_name)
        return template.format(text=text)
        
    def build_insight_prompt(
        self,
        text: str,
        entities: Optional[List[Entity]] = None
    ) -> str:
        """Build insight extraction prompt."""
        # Build entity context
        entity_context = ""
        if entities:
            entity_names = [e.name for e in entities[:10]]
            entity_context = f"\nKey entities mentioned: {', '.join(entity_names)}\n"
            
        template_name = 'insight_extraction_large' if self.use_large_context else 'insight_extraction_small'
        template = self.get_template(template_name)
        return template.format(text=text, entity_context=entity_context)
        
    def build_quote_prompt(self, text: str) -> str:
        """Build quote extraction prompt."""
        # Only use large context template for quotes
        template = self.get_template('quote_extraction_large')
        return template.format(text=text)
        
    def build_complexity_prompt(self, text: str) -> str:
        """Build complexity analysis prompt."""
        template = self.get_template('complexity_analysis')
        return template.format(text=text)
        
    def build_information_density_prompt(
        self,
        text: str,
        insights_count: int = 0,
        entities_count: int = 0
    ) -> str:
        """Build information density analysis prompt."""
        additional_context = ""
        if insights_count > 0 or entities_count > 0:
            additional_context = f"Note: {insights_count} insights and {entities_count} entities were extracted from this segment."
            
        template = self.get_template('information_density')
        return template.format(text=text, additional_context=additional_context)
        
    def build_topic_prompt(
        self,
        text: str,
        entity_distribution: Optional[Dict[str, int]] = None,
        insight_distribution: Optional[Dict[str, int]] = None
    ) -> str:
        """Build topic extraction prompt."""
        context_parts = []
        
        if entity_distribution:
            context_parts.append(f"Entity distribution: {entity_distribution}")
            
        if insight_distribution:
            context_parts.append(f"Insight types: {insight_distribution}")
            
        context = "\n".join(context_parts) if context_parts else ""
        
        template = self.get_template('topic_extraction')
        return template.format(text=text, context=context)
        
    def build_sentiment_prompt(self, text: str) -> str:
        """Build sentiment analysis prompt."""
        template = self.get_template('sentiment_analysis')
        return template.format(text=text)
        
    def convert_transcript_for_llm(
        self,
        segments: List[Dict[str, Any]],
        max_length: Optional[int] = None
    ) -> str:
        """
        Convert transcript segments to formatted text for LLM processing.
        
        Args:
            segments: List of segment dictionaries
            max_length: Optional maximum length limit
            
        Returns:
            Formatted transcript text
        """
        lines = []
        
        for segment in segments:
            # Format: [SPEAKER TIME] Text
            speaker = segment.get('speaker', 'Unknown')
            start_time = segment.get('start_time', 0)
            text = segment.get('text', '')
            
            # Convert time to MM:SS format
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            line = f"[{speaker} {time_str}] {text}"
            lines.append(line)
            
        transcript = "\n\n".join(lines)
        
        # Truncate if needed
        if max_length and len(transcript) > max_length:
            transcript = transcript[:max_length] + "\n\n[Transcript truncated...]"
            
        return transcript
        
    def get_all_templates(self) -> Dict[str, PromptTemplate]:
        """Get all available templates."""
        return self._templates.copy()
        
    def add_custom_template(self, template: PromptTemplate) -> None:
        """Add a custom prompt template."""
        if template.name in self._templates:
            logger.warning(f"Overwriting existing template: {template.name}")
        self._templates[template.name] = template
        
    def get_version_info(self) -> Dict[str, Any]:
        """Get prompt version information."""
        return {
            'current_version': self.version.value,
            'use_large_context': self.use_large_context,
            'template_count': len(self._templates),
            'templates': list(self._templates.keys())
        }
    
    # Additional methods for compatibility
    def build_entity_extraction_prompt(self, text: str, context_hints: Optional[List[str]] = None) -> str:
        """Build entity extraction prompt (alias for build_entity_prompt)."""
        prompt = self.build_entity_prompt(text)
        
        # Add context hints if provided
        if context_hints:
            context_str = f"\nContext hints: {', '.join(context_hints)}\n"
            prompt = prompt.replace("TRANSCRIPT:", f"{context_str}TRANSCRIPT:")
            
        return prompt
    
    def build_insight_extraction_prompt(self, text: str, entity_names: Optional[List[str]] = None) -> str:
        """Build insight extraction prompt."""
        # Convert entity names to Entity objects for compatibility
        entities = None
        if entity_names:
            from src.core.models import Entity, EntityType
            entities = [Entity(name=name, type=EntityType.CONCEPT, confidence=0.8) for name in entity_names]
        
        return self.build_insight_prompt(text, entities)
    
    def build_quote_extraction_prompt(self, text: str) -> str:
        """Build quote extraction prompt (alias for build_quote_prompt)."""
        return self.build_quote_prompt(text)
    
    def build_topic_identification_prompt(
        self, 
        text: str, 
        entities: Optional[List[str]] = None,
        insights: Optional[List[str]] = None
    ) -> str:
        """Build topic identification prompt."""
        # Convert to Entity objects if needed
        entity_objs = None
        if entities:
            from src.core.models import Entity, EntityType
            entity_objs = [Entity(name=name, type=EntityType.CONCEPT, confidence=0.8) for name in entities]
        
        # Convert to Insight objects if needed
        insight_objs = None
        if insights:
            from src.core.models import Insight, InsightType
            insight_objs = [Insight(content=content, type=InsightType.OBSERVATION, confidence=0.8) for content in insights]
        
        return self.build_topic_prompt(text, entity_objs, insight_objs)
    
    def build_summary_prompt(self, transcript: str, key_points: List[str]) -> str:
        """Build summary generation prompt."""
        key_points_str = "\n".join(f"- {point}" for point in key_points)
        
        prompt = f"""Generate a comprehensive summary of the following transcript.

Key points to emphasize:
{key_points_str}

TRANSCRIPT:
{transcript}

Provide a structured summary that:
1. Captures the main themes and discussions
2. Highlights key insights and conclusions
3. Maintains the narrative flow
4. Emphasizes the provided key points"""
        
        return prompt
    
    def build_relationship_extraction_prompt(self, text: str, entities: List[str]) -> str:
        """Build relationship extraction prompt."""
        entities_str = ", ".join(entities)
        
        prompt = f"""Identify relationships between entities in the following text.

Entities to consider: {entities_str}

TEXT:
{text}

For each relationship found:
1. Identify the source and target entities
2. Describe the type of relationship (e.g., "works for", "acquired", "developed", "uses")
3. Provide confidence level (high/medium/low)
4. Include relevant context

Return as JSON list of relationships."""
        
        return prompt
    
    def get_prompt_version(self, prompt_name: str) -> str:
        """Get version of a specific prompt."""
        if prompt_name in ["entity_extraction", "insight_extraction", "quote_extraction"]:
            return self.version.value
        return "1.0"
    
    def register_prompt_template(self, name: str, template: PromptTemplate) -> None:
        """Register a custom prompt template."""
        self._templates[name] = template
    
    def build_custom_prompt(self, template_name: str, **kwargs) -> str:
        """Build a prompt from a custom template."""
        if template_name not in self._templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        template = self._templates[template_name]
        return template.format(**kwargs)
    
    def get_prompt_metadata(self) -> Dict[str, Any]:
        """Get metadata about available prompts."""
        return {
            "version": self.version.value,
            "use_large_context": self.use_large_context,
            "supported_prompts": list(self._templates.keys()),
            "template_count": len(self._templates)
        }
    
    def build_combined_extraction_prompt(
        self, 
        podcast_name: str,
        episode_title: str,
        transcript: str
    ) -> str:
        """
        Build a combined prompt for extracting insights, entities, and quotes in a single call.
        Optimized for token efficiency.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            transcript: Full transcript text
            
        Returns:
            Combined extraction prompt
        """
        if self.use_large_context:
            prompt = f"""
Analyze this podcast transcript and extract structured knowledge in ONE pass.

PODCAST: {podcast_name}
EPISODE: {episode_title}

TRANSCRIPT:
{transcript}

Extract the following in JSON format:

1. INSIGHTS: Key takeaways and learnings
   - title: Brief 3-5 word title
   - description: One sentence description
   - insight_type: actionable (practical advice)/conceptual (theory, explanations)/experiential (stories, examples)
   - confidence: 1-10 score

2. ENTITIES: Important people, companies, concepts
   - name: Entity name
   - type: Person/Company/Product/Technology/Concept/Book/Framework/Method/Location/Study/Institution/Researcher/Journal/Theory/Research_Method/Medication/Condition/Treatment/Symptom/Biological_Process/Medical_Device/Chemical/Scientific_Theory/Laboratory/Experiment/Discovery
   - description: Brief description
   - importance: 1-10 score
   - frequency: Approximate mentions
   - has_citation: true/false

3. QUOTES: Highly quotable segments (10-30 words ideal)
   - text: The exact quote
   - speaker: Who said it
   - context: Brief context

Return ONLY valid JSON:
{{
  "insights": [...],
  "entities": [...],
  "quotes": [...]
}}"""
        else:
            # Shorter prompt for segment processing
            prompt = f"""
Extract insights, entities, and quotes from this segment.

SEGMENT:
{transcript}

Return JSON with:
- insights: Key points with title, description, type
- entities: Important names with type and description
- quotes: Notable statements with speaker

Keep it concise and accurate."""
        
        return prompt