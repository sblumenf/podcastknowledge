"""Knowledge extraction core functionality.

DEPRECATED: This module implements fixed schema extraction and is being replaced
by schemaless extraction using Neo4j GraphRAG SimpleKGPipeline.

For new code, use:
- Enable ENABLE_SCHEMALESS_EXTRACTION feature flag
- Use SimpleKGPipeline for extraction
- See MIGRATION_PATH.md for migration guide

This module will be removed in version 2.0.0.
"""

import json
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from src.core.interfaces import LLMProvider
from src.core.models import Entity, Insight, Quote, InsightType, QuoteType, EntityType
from src.core.exceptions import ExtractionError
from src.utils.deprecation import deprecated, deprecated_class


logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of knowledge extraction process."""
    entities: List[Entity]
    insights: List[Insight]
    quotes: List[Quote]
    topics: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    

@deprecated_class(
    reason="Fixed schema extraction is being replaced by schemaless extraction",
    version="1.1.0",
    removal_version="2.0.0",
    alternative="SimpleKGPipeline with ENABLE_SCHEMALESS_EXTRACTION=true"
)
class KnowledgeExtractor:
    """Main class for extracting knowledge from transcript segments."""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        use_large_context: bool = True,
        max_retries: int = 3,
        enable_cache: bool = True,
        cache_size: int = 128
    ):
        """
        Initialize knowledge extractor.
        
        Args:
            llm_provider: LLM provider for extraction
            use_large_context: Whether to use large context prompts
            max_retries: Maximum retries for failed extractions
            enable_cache: Whether to enable result caching
            cache_size: Maximum number of cached results
        """
        self.llm_provider = llm_provider
        self.use_large_context = use_large_context
        self.max_retries = max_retries
        self.enable_cache = enable_cache
        self._cache: Dict[str, Any] = {}
        self._cache_size = cache_size
        
    def _get_cache_key(self, method: str, text: str, extra: str = "") -> str:
        """Generate cache key for a given extraction method and text."""
        content = f"{method}:{text[:200]}:{extra}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get result from cache if available."""
        if not self.enable_cache:
            return None
        return self._cache.get(cache_key)
    
    def _add_to_cache(self, cache_key: str, value: Any) -> None:
        """Add result to cache with size limit management."""
        if not self.enable_cache:
            return
            
        # Simple cache eviction: remove oldest if size exceeded
        if len(self._cache) >= self._cache_size:
            # Remove first (oldest) item
            first_key = next(iter(self._cache))
            del self._cache[first_key]
            
        self._cache[cache_key] = value
    
    def clear_cache(self) -> None:
        """Clear the extraction cache."""
        self._cache.clear()
        logger.info("Extraction cache cleared")
        
    def extract_all(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract all knowledge from text.
        
        Args:
            text: Text to extract from
            context: Optional context information
            
        Returns:
            ExtractionResult with all extracted knowledge
        """
        # Extract different types of knowledge
        entities = self.extract_entities(text)
        insights = self.extract_insights(text, entities)
        quotes = self.extract_quotes(text)
        topics = self.extract_topics(text, entities, insights)
        
        # Build metadata
        metadata = {
            'extraction_timestamp': datetime.now().isoformat(),
            'use_large_context': self.use_large_context,
            'text_length': len(text),
            'entity_count': len(entities),
            'insight_count': len(insights),
            'quote_count': len(quotes),
            'topic_count': len(topics)
        }
        
        if context:
            metadata['context'] = context
            
        return ExtractionResult(
            entities=entities,
            insights=insights,
            quotes=quotes,
            topics=topics,
            metadata=metadata
        )
        
    @deprecated(
        reason="Fixed entity extraction is replaced by schemaless extraction",
        version="1.1.0", 
        removal_version="2.0.0",
        alternative="SimpleKGPipeline.extract() for flexible entity discovery"
    )
    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract entities from text.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            List of extracted entities
        """
        if not text.strip():
            return []
            
        # Check cache first
        cache_key = self._get_cache_key("entities", text)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            logger.debug(f"Returning cached entities for key {cache_key}")
            return cached_result
            
        # Build entity extraction prompt
        prompt = self._build_entity_prompt(text)
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Get LLM response
                response = self.llm_provider.complete(prompt)
                
                # Parse entities from response
                entities = self._parse_entity_response(response)
                
                # Validate and normalize entities
                entities = self._validate_entities(entities, text)
                
                # Cache the result
                self._add_to_cache(cache_key, entities)
                
                return entities
                
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for entity extraction: {e}")
                if attempt < self.max_retries - 1:
                    continue
                    
        logger.error(f"Failed to extract entities after {self.max_retries} attempts: {last_error}")
        return []  # Return empty list on failure instead of raising
    
    def extract_combined(
        self,
        text: str,
        podcast_name: Optional[str] = None,
        episode_title: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract all knowledge in a single LLM call for efficiency.
        
        Args:
            text: Text to extract from
            podcast_name: Optional podcast name for context
            episode_title: Optional episode title for context
            
        Returns:
            ExtractionResult with all extracted knowledge
        """
        if not text.strip():
            return ExtractionResult(
                entities=[],
                insights=[],
                quotes=[],
                topics=[],
                metadata={'method': 'combined', 'empty_input': True}
            )
        
        # Check cache
        cache_key = self._get_cache_key(
            "combined", 
            text, 
            f"{podcast_name or ''}:{episode_title or ''}"
        )
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            logger.debug(f"Returning cached combined extraction for key {cache_key}")
            return cached_result
        
        # Build combined prompt
        from src.processing.prompts import PromptBuilder
        prompt_builder = PromptBuilder(self.use_large_context)
        prompt = prompt_builder.build_combined_extraction_prompt(
            podcast_name or "Unknown Podcast",
            episode_title or "Unknown Episode",
            text
        )
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Get LLM response
                response = self.llm_provider.complete(prompt)
                
                # Parse combined response
                from src.processing.parsers import ResponseParser
                parser = ResponseParser()
                json_result = parser.parse_json_response(response, expected_type=dict)
                
                if not json_result.success or not json_result.data:
                    raise ValueError("Failed to parse combined extraction response")
                
                data = json_result.data
                
                # Extract components
                entities = self._parse_entities_from_combined(data.get('entities', []))
                insights = self._parse_insights_from_combined(data.get('insights', []))
                quotes = self._parse_quotes_from_combined(data.get('quotes', []))
                
                # Topics can be derived from insights
                topics = self._derive_topics_from_insights(insights)
                
                # Create result
                result = ExtractionResult(
                    entities=entities,
                    insights=insights,
                    quotes=quotes,
                    topics=topics,
                    metadata={
                        'method': 'combined',
                        'extraction_timestamp': datetime.now().isoformat(),
                        'podcast_name': podcast_name,
                        'episode_title': episode_title
                    }
                )
                
                # Cache the result
                self._add_to_cache(cache_key, result)
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for combined extraction: {e}")
                if attempt < self.max_retries - 1:
                    continue
        
        logger.error(f"Failed combined extraction after {self.max_retries} attempts: {last_error}")
        # Fall back to individual extraction
        return self.extract_all(text)
    
    def _parse_entities_from_combined(self, entity_data: List[Dict[str, Any]]) -> List[Entity]:
        """Parse entities from combined extraction response."""
        entities = []
        for item in entity_data:
            try:
                entity = Entity(
                    name=item.get('name', ''),
                    type=self._map_entity_type(item.get('type', 'CONCEPT')),
                    confidence=min(1.0, item.get('importance', 5) / 10),
                    description=item.get('description', ''),
                    metadata={
                        'frequency': item.get('frequency', 1),
                        'has_citation': item.get('has_citation', False)
                    }
                )
                entities.append(entity)
            except Exception as e:
                logger.warning(f"Failed to parse entity: {e}")
        return entities
    
    def _parse_insights_from_combined(self, insight_data: List[Dict[str, Any]]) -> List[Insight]:
        """Parse insights from combined extraction response."""
        insights = []
        for item in insight_data:
            try:
                # Map insight type
                type_str = item.get('insight_type', 'conceptual').lower()
                if 'actionable' in type_str:
                    insight_type = InsightType.ACTIONABLE
                elif 'experiential' in type_str or 'example' in type_str:
                    insight_type = InsightType.EXAMPLE
                else:
                    insight_type = InsightType.OBSERVATION
                
                insight = Insight(
                    content=f"{item.get('title', '')}: {item.get('description', '')}".strip(),
                    type=insight_type,
                    confidence=min(1.0, item.get('confidence', 5) / 10),
                    context=item.get('context', '')
                )
                insights.append(insight)
            except Exception as e:
                logger.warning(f"Failed to parse insight: {e}")
        return insights
    
    def _parse_quotes_from_combined(self, quote_data: List[Dict[str, Any]]) -> List[Quote]:
        """Parse quotes from combined extraction response."""
        quotes = []
        for item in quote_data:
            try:
                quote = Quote(
                    text=item.get('text', ''),
                    speaker=item.get('speaker', 'Unknown'),
                    timestamp="",  # Not available in combined extraction
                    context=item.get('context', ''),
                    type=QuoteType.STATEMENT
                )
                quotes.append(quote)
            except Exception as e:
                logger.warning(f"Failed to parse quote: {e}")
        return quotes
    
    def _derive_topics_from_insights(self, insights: List[Insight]) -> List[Dict[str, Any]]:
        """Derive topics from extracted insights."""
        topics = []
        
        # Group insights by type
        by_type = {}
        for insight in insights:
            type_name = insight.type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(insight)
        
        # Create topics from groups
        for type_name, group_insights in by_type.items():
            if group_insights:
                topics.append({
                    'name': f"{type_name.replace('_', ' ').title()} Insights",
                    'description': f"Collection of {len(group_insights)} {type_name} insights",
                    'insight_count': len(group_insights)
                })
        
        return topics
    
    def _map_entity_type(self, type_str: str) -> EntityType:
        """Map string entity type to EntityType enum."""
        type_str = type_str.upper()
        
        # Direct mappings
        direct_mappings = {
            'PERSON': EntityType.PERSON,
            'COMPANY': EntityType.ORGANIZATION,
            'ORGANIZATION': EntityType.ORGANIZATION,
            'PRODUCT': EntityType.PRODUCT,
            'TECHNOLOGY': EntityType.TECHNOLOGY,
            'CONCEPT': EntityType.CONCEPT,
            'LOCATION': EntityType.LOCATION,
            'EVENT': EntityType.EVENT
        }
        
        if type_str in direct_mappings:
            return direct_mappings[type_str]
        
        # Scientific/medical types
        if type_str in ['STUDY', 'RESEARCH_METHOD', 'SCIENTIFIC_THEORY', 'EXPERIMENT']:
            return EntityType.RESEARCH_METHOD
        elif type_str in ['MEDICATION', 'TREATMENT', 'MEDICAL_DEVICE']:
            return EntityType.MEDICAL_TERM
        elif type_str in ['CONDITION', 'SYMPTOM', 'BIOLOGICAL_PROCESS']:
            return EntityType.MEDICAL_TERM
        
        # Default
        return EntityType.CONCEPT
            
    @deprecated(
        reason="Fixed insight extraction is replaced by schemaless extraction",
        version="1.1.0",
        removal_version="2.0.0", 
        alternative="SimpleKGPipeline.extract() for flexible knowledge discovery"
    )
    def extract_insights(
        self,
        text: str,
        entities: Optional[List[Entity]] = None
    ) -> List[Insight]:
        """
        Extract insights from text.
        
        Args:
            text: Text to extract insights from
            entities: Optional list of entities for context
            
        Returns:
            List of extracted insights
        """
        if not text.strip():
            return []
            
        # Build insight extraction prompt
        prompt = self._build_insight_prompt(text, entities)
        
        try:
            # Get LLM response
            response = self.llm_provider.complete(prompt)
            
            # Parse insights from response
            insights = self._parse_insight_response(response)
            
            # Validate insights
            insights = self._validate_insights(insights)
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to extract insights: {e}")
            raise ExtractionError("insights", f"Insight extraction failed: {e}")
            
    @deprecated(
        reason="Fixed quote extraction is replaced by schemaless extraction",
        version="1.1.0",
        removal_version="2.0.0",
        alternative="SimpleKGPipeline.extract() with quote post-processing"
    )
    def extract_quotes(self, text: str) -> List[Quote]:
        """
        Extract memorable quotes from text.
        
        Args:
            text: Text to extract quotes from
            
        Returns:
            List of extracted quotes
        """
        if not text.strip():
            return []
            
        # Build quote extraction prompt
        prompt = self._build_quote_prompt(text)
        
        try:
            # Get LLM response
            response = self.llm_provider.complete(prompt)
            
            # Parse quotes from response
            quotes = self._parse_quote_response(response)
            
            # Validate quotes
            quotes = self._validate_quotes(quotes, text)
            
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to extract quotes: {e}")
            raise ExtractionError("quotes", f"Quote extraction failed: {e}")
            
    @deprecated(
        reason="Fixed topic extraction is replaced by schemaless extraction",
        version="1.1.0",
        removal_version="2.0.0",
        alternative="SimpleKGPipeline.extract() discovers topics automatically"
    )
    def extract_topics(
        self,
        text: str,
        entities: Optional[List[Entity]] = None,
        insights: Optional[List[Insight]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract topics from text and related knowledge.
        
        Args:
            text: Text to extract topics from
            entities: Optional entities for context
            insights: Optional insights for context
            
        Returns:
            List of topic dictionaries
        """
        # Build topic extraction prompt
        prompt = self._build_topic_prompt(text, entities, insights)
        
        try:
            # Get LLM response
            response = self.llm_provider.complete(prompt)
            
            # Parse topics from response
            topics = self._parse_topic_response(response)
            
            return topics
            
        except Exception as e:
            logger.error(f"Failed to extract topics: {e}")
            # Return empty list on failure (topics are optional)
            return []
            
    # Prompt building methods
    
    def _build_entity_prompt(self, text: str) -> str:
        """Build entity extraction prompt."""
        if self.use_large_context:
            return f"""
Extract named entities from the following podcast transcript. With your 1M token context window,
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

JSON RESPONSE:
"""
        else:
            return f"""
Extract named entities from the following text.

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

JSON RESPONSE:
"""
            
    def _build_insight_prompt(
        self,
        text: str,
        entities: Optional[List[Entity]] = None
    ) -> str:
        """Build insight extraction prompt."""
        entity_context = ""
        if entities:
            entity_names = [e.name for e in entities[:10]]  # Limit to top 10
            entity_context = f"\nKey entities mentioned: {', '.join(entity_names)}\n"
            
        if self.use_large_context:
            return f"""
Extract key insights from this podcast transcript. Focus on:
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

JSON RESPONSE:
"""
        else:
            return f"""
Extract key insights from this text segment.
{entity_context}
TEXT:
{text}

For each insight:
- content: The insight (1-2 sentences)
- type: factual, conceptual, prediction, recommendation, key_point, technical, or methodological
- confidence: 0.0-1.0

Format as JSON list. Extract up to 5 insights.

JSON RESPONSE:
"""
            
    def _build_quote_prompt(self, text: str) -> str:
        """Build quote extraction prompt."""
        if self.use_large_context:
            return f"""
Extract memorable, insightful, or important quotes from this podcast transcript.

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

JSON RESPONSE:
"""
        else:
            return f"""
Extract notable quotes from this text.

TEXT:
{text}

For each quote:
- text: The exact quote
- speaker: Who said it (if known)
- type: memorable, controversial, humorous, insightful, technical, or general

Format as JSON list. Extract up to 3 quotes.

JSON RESPONSE:
"""
            
    def _build_topic_prompt(
        self,
        text: str,
        entities: Optional[List[Entity]] = None,
        insights: Optional[List[Insight]] = None
    ) -> str:
        """Build topic extraction prompt."""
        context_parts = []
        
        if entities:
            entity_types = {}
            for e in entities:
                entity_types[e.type] = entity_types.get(e.type, 0) + 1
            context_parts.append(f"Entity distribution: {dict(entity_types)}")
            
        if insights:
            insight_types = {}
            for i in insights:
                insight_types[i.insight_type] = insight_types.get(i.insight_type, 0) + 1
            context_parts.append(f"Insight types: {dict(insight_types)}")
            
        context = "\n".join(context_parts) if context_parts else ""
        
        return f"""
Identify the main topics discussed in this content.

{context}

TEXT:
{text}

For each topic:
- name: Topic name (2-4 words)
- description: Brief description (1 sentence)
- relevance: Score 0.0-1.0 based on discussion depth
- subtopics: List of related subtopics if any

Format as JSON list. Identify 3-7 main topics.

JSON RESPONSE:
"""
            
    # Parsing methods
    
    def _parse_entity_response(self, response: str) -> List[Entity]:
        """Parse entity extraction response."""
        try:
            # Clean and parse JSON
            json_data = self._extract_json_from_response(response)
            
            entities = []
            for item in json_data:
                # Map entity type string to enum
                entity_type = self._map_entity_type(item.get('type', 'OTHER'))
                
                entity = Entity(
                    id=f"entity_{len(entities)}_{item['name'].lower().replace(' ', '_')}",
                    name=item['name'],
                    type=entity_type.value,
                    description=item.get('description', ''),
                    first_mentioned=datetime.now().isoformat(),
                    mention_count=item.get('frequency', 1),
                    bridge_score=item.get('importance', 5) / 10.0,
                    is_peripheral=item.get('importance', 5) < 3,
                    embedding=None  # Will be added later
                )
                entities.append(entity)
                
            return entities
            
        except Exception as e:
            logger.warning(f"Failed to parse entity response: {e}")
            return []
            
    def _parse_insight_response(self, response: str) -> List[Insight]:
        """Parse insight extraction response."""
        try:
            # Clean and parse JSON
            json_data = self._extract_json_from_response(response)
            
            insights = []
            for item in json_data:
                # Map insight type
                insight_type = self._map_insight_type(item.get('type', 'general'))
                
                insight = Insight(
                    id=f"insight_{len(insights)}_{datetime.now().timestamp()}",
                    insight_type=insight_type.value,
                    content=item['content'],
                    confidence_score=item.get('confidence', 0.7),
                    extracted_from_segment="",  # Will be set by caller
                    is_bridge_insight=False,  # Will be determined later
                    timestamp=datetime.now().isoformat()
                )
                insights.append(insight)
                
            return insights
            
        except Exception as e:
            logger.warning(f"Failed to parse insight response: {e}")
            return []
            
    def _parse_quote_response(self, response: str) -> List[Quote]:
        """Parse quote extraction response."""
        try:
            # Clean and parse JSON
            json_data = self._extract_json_from_response(response)
            
            quotes = []
            for item in json_data:
                # Map quote type
                quote_type = self._map_quote_type(item.get('type', 'general'))
                
                quote = Quote(
                    id=f"quote_{len(quotes)}_{datetime.now().timestamp()}",
                    text=item['text'],
                    speaker=item.get('speaker', 'Unknown'),
                    quote_type=quote_type.value,
                    context=item.get('context', ''),
                    timestamp=datetime.now().isoformat(),
                    segment_id=""  # Will be set by caller
                )
                quotes.append(quote)
                
            return quotes
            
        except Exception as e:
            logger.warning(f"Failed to parse quote response: {e}")
            return []
            
    def _parse_topic_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse topic extraction response."""
        try:
            # Clean and parse JSON
            json_data = self._extract_json_from_response(response)
            
            topics = []
            for item in json_data:
                topic = {
                    'name': item.get('name', ''),
                    'description': item.get('description', ''),
                    'relevance': item.get('relevance', 0.5),
                    'subtopics': item.get('subtopics', [])
                }
                topics.append(topic)
                
            return topics
            
        except Exception as e:
            logger.warning(f"Failed to parse topic response: {e}")
            return []
            
    # Helper methods
    
    def _extract_json_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract JSON from LLM response."""
        # Clean up response to extract JSON
        lines = response.strip().split('\n')
        json_lines = []
        in_json = False
        
        for line in lines:
            if line.strip() in ["```json", "```"]:
                in_json = not in_json
                continue
            if in_json or "[" in line or "{" in line:
                json_lines.append(line)
                
        clean_json = '\n'.join(json_lines)
        
        # Try to parse JSON
        try:
            data = json.loads(clean_json)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                return []
        except json.JSONDecodeError:
            # Try to find JSON array or object
            import re
            json_match = re.search(r'[\[\{].*[\]\}]', clean_json, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return data if isinstance(data, list) else [data]
                except:
                    pass
            return []
            
    def _map_entity_type(self, type_str: str) -> EntityType:
        """Map entity type string to enum."""
        type_mapping = {
            'person': EntityType.PERSON,
            'company': EntityType.ORGANIZATION,
            'organization': EntityType.ORGANIZATION,
            'institution': EntityType.ORGANIZATION,
            'product': EntityType.PRODUCT,
            'technology': EntityType.TECHNOLOGY,
            'concept': EntityType.CONCEPT,
            'location': EntityType.LOCATION,
            'event': EntityType.EVENT,
            'study': EntityType.OTHER,
            'researcher': EntityType.PERSON,
            'journal': EntityType.ORGANIZATION,
            'medication': EntityType.PRODUCT,
            'condition': EntityType.CONCEPT,
            'treatment': EntityType.CONCEPT,
            'biological_process': EntityType.CONCEPT,
            'chemical': EntityType.OTHER,
            'scientific_theory': EntityType.CONCEPT,
            'medical_device': EntityType.PRODUCT
        }
        
        return type_mapping.get(type_str.lower(), EntityType.OTHER)
        
    def _map_insight_type(self, type_str: str) -> InsightType:
        """Map insight type string to enum."""
        type_mapping = {
            'factual': InsightType.FACTUAL,
            'conceptual': InsightType.CONCEPTUAL,
            'prediction': InsightType.PREDICTION,
            'recommendation': InsightType.RECOMMENDATION,
            'key_point': InsightType.KEY_POINT,
            'technical': InsightType.TECHNICAL,
            'methodological': InsightType.METHODOLOGICAL
        }
        
        return type_mapping.get(type_str.lower(), InsightType.FACTUAL)
        
    def _map_quote_type(self, type_str: str) -> QuoteType:
        """Map quote type string to enum."""
        type_mapping = {
            'memorable': QuoteType.MEMORABLE,
            'controversial': QuoteType.CONTROVERSIAL,
            'humorous': QuoteType.HUMOROUS,
            'insightful': QuoteType.INSIGHTFUL,
            'technical': QuoteType.TECHNICAL,
            'general': QuoteType.GENERAL
        }
        
        return type_mapping.get(type_str.lower(), QuoteType.GENERAL)
        
    def _validate_entities(
        self,
        entities: List[Entity],
        source_text: str
    ) -> List[Entity]:
        """Validate and filter entities."""
        validated = []
        seen_names = set()
        
        for entity in entities:
            # Skip duplicates
            name_lower = entity.name.lower()
            if name_lower in seen_names:
                continue
                
            # Skip entities that are too short
            if len(entity.name) < 2:
                continue
                
            # Verify entity appears in text (case-insensitive)
            if name_lower not in source_text.lower():
                # Try partial match for multi-word entities
                words = entity.name.split()
                if len(words) > 1:
                    # Check if any significant word appears
                    found = any(
                        word.lower() in source_text.lower()
                        for word in words
                        if len(word) > 3
                    )
                    if not found:
                        continue
                else:
                    continue
                    
            seen_names.add(name_lower)
            validated.append(entity)
            
        return validated
        
    def _validate_insights(self, insights: List[Insight]) -> List[Insight]:
        """Validate insights."""
        validated = []
        
        for insight in insights:
            # Skip empty or too short insights
            if not insight.content or len(insight.content) < 10:
                continue
                
            # Ensure confidence score is in valid range
            insight.confidence_score = max(0.0, min(1.0, insight.confidence_score))
            
            validated.append(insight)
            
        return validated
        
    def _validate_quotes(
        self,
        quotes: List[Quote],
        source_text: str
    ) -> List[Quote]:
        """Validate quotes appear in source text."""
        validated = []
        
        for quote in quotes:
            # Skip empty quotes
            if not quote.text or len(quote.text) < 10:
                continue
                
            # Check if quote appears in text (allowing for minor variations)
            quote_words = quote.text.lower().split()
            if len(quote_words) > 3:
                # For longer quotes, check if most words appear in order
                found_count = 0
                text_lower = source_text.lower()
                for word in quote_words:
                    if word in text_lower:
                        found_count += 1
                        
                if found_count / len(quote_words) < 0.7:
                    continue
            else:
                # For short quotes, require exact match
                if quote.text.lower() not in source_text.lower():
                    continue
                    
            validated.append(quote)
            
        return validated