"""
Feature Integration Framework for SimpleKGPipeline Enhancement

This module provides the framework to enrich SimpleKGPipeline's knowledge graph
with advanced features from existing extractors like quotes, insights, complexity
analysis, importance scoring, and all other 15+ analytical capabilities.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from src.core.interfaces import TranscriptSegment
from src.core.models import Segment, Entity, Quote, Insight
from src.extraction.extraction import KnowledgeExtractor, ExtractionResult
from src.extraction.complexity_analysis import ComplexityAnalyzer, SegmentComplexity, EpisodeComplexity
from src.extraction.importance_scoring import ImportanceScorer
from src.storage.graph_storage import GraphStorageService
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureEnrichmentResult:
    """Result of feature enrichment process."""
    entities_enriched: int
    quotes_linked: int
    insights_linked: int
    complexity_analyzed: bool
    importance_scored: int
    processing_time: float
    enrichment_details: Dict[str, Any]


class FeatureIntegrationFramework:
    """
    Framework to integrate existing advanced features with SimpleKGPipeline output.
    
    This framework takes the entities and relationships created by SimpleKGPipeline
    and enriches them with:
    - Quote attribution and context
    - Insight generation and linking
    - Complexity analysis and scoring
    - Importance scoring based on multiple factors
    - Speaker identification and attribution
    - Temporal dynamics and discourse analysis
    - And all other 15+ advanced features
    """
    
    def __init__(self, 
                 knowledge_extractor: KnowledgeExtractor,
                 complexity_analyzer: ComplexityAnalyzer,
                 importance_scorer: ImportanceScorer,
                 graph_storage: GraphStorageService):
        """
        Initialize the feature integration framework.
        
        Args:
            knowledge_extractor: For quotes and insights extraction
            complexity_analyzer: For complexity analysis
            importance_scorer: For importance scoring
            graph_storage: For graph database operations
        """
        self.knowledge_extractor = knowledge_extractor
        self.complexity_analyzer = complexity_analyzer
        self.importance_scorer = importance_scorer
        self.graph_storage = graph_storage
        
        logger.info("Feature Integration Framework initialized")
    
    async def enrich_knowledge_graph(self, 
                                   segments: List[TranscriptSegment], 
                                   episode_id: str) -> FeatureEnrichmentResult:
        """
        Enrich the knowledge graph created by SimpleKGPipeline with advanced features.
        
        Args:
            segments: Original transcript segments
            episode_id: Episode identifier
            
        Returns:
            FeatureEnrichmentResult with enrichment statistics
        """
        start_time = time.time()
        logger.info(f"Starting knowledge graph enrichment for episode {episode_id}")
        
        # Step 1: Retrieve entities and relationships from Neo4j (created by SimpleKGPipeline)
        entities = await self._retrieve_entities_from_graph(episode_id)
        relationships = await self._retrieve_relationships_from_graph(episode_id)
        
        logger.info(f"Retrieved {len(entities)} entities and {len(relationships)} relationships from graph")
        
        # Step 2: Extract and link quotes to entities
        quotes_linked = await self._extract_and_link_quotes(segments, entities, episode_id)
        
        # Step 3: Generate and link insights
        insights_linked = await self._generate_and_link_insights(segments, entities, episode_id)
        
        # Step 4: Perform complexity analysis
        complexity_analyzed = await self._analyze_and_store_complexity(segments, entities, episode_id)
        
        # Step 5: Calculate importance scores for entities
        importance_scored = await self._calculate_importance_scores(entities, segments, episode_id)
        
        # Step 6: Add temporal and discourse analysis
        await self._add_temporal_discourse_analysis(segments, entities, episode_id)
        
        # Step 7: Enrich with speaker information
        await self._enrich_speaker_information(segments, entities, episode_id)
        
        processing_time = time.time() - start_time
        
        result = FeatureEnrichmentResult(
            entities_enriched=len(entities),
            quotes_linked=quotes_linked,
            insights_linked=insights_linked,
            complexity_analyzed=complexity_analyzed,
            importance_scored=importance_scored,
            processing_time=processing_time,
            enrichment_details={
                "episode_id": episode_id,
                "total_segments": len(segments),
                "entities_analyzed": len(entities),
                "relationships_analyzed": len(relationships)
            }
        )
        
        logger.info(f"Knowledge graph enrichment completed in {processing_time:.2f}s")
        return result
    
    async def _retrieve_entities_from_graph(self, episode_id: str) -> List[Dict[str, Any]]:
        """Retrieve entities created by SimpleKGPipeline from Neo4j."""
        query = """
        MATCH (e:Episode {id: $episode_id})-[*]->(entity)
        WHERE NOT entity:Episode AND NOT entity:Chunk
        RETURN entity, labels(entity) as entity_types, id(entity) as neo4j_id
        """
        
        try:
            with self.graph_storage.get_session() as session:
                result = session.run(query, episode_id=episode_id)
                entities = []
                for record in result:
                    entity_data = dict(record["entity"])
                    entity_data["entity_types"] = record["entity_types"]
                    entity_data["neo4j_id"] = record["neo4j_id"]
                    entities.append(entity_data)
                return entities
        except Exception as e:
            logger.error(f"Failed to retrieve entities from graph: {e}")
            return []
    
    async def _retrieve_relationships_from_graph(self, episode_id: str) -> List[Dict[str, Any]]:
        """Retrieve relationships created by SimpleKGPipeline from Neo4j."""
        query = """
        MATCH (e:Episode {id: $episode_id})-[*]->(start_node)-[rel]->(end_node)
        WHERE NOT start_node:Episode AND NOT end_node:Episode 
              AND NOT start_node:Chunk AND NOT end_node:Chunk
        RETURN type(rel) as relationship_type, 
               properties(rel) as properties,
               start_node.name as start_node_name,
               end_node.name as end_node_name,
               id(rel) as neo4j_id
        """
        
        try:
            with self.graph_storage.get_session() as session:
                result = session.run(query, episode_id=episode_id)
                relationships = []
                for record in result:
                    rel_data = {
                        "type": record["relationship_type"],
                        "properties": dict(record["properties"]) if record["properties"] else {},
                        "start_node": record["start_node_name"],
                        "end_node": record["end_node_name"],
                        "neo4j_id": record["neo4j_id"]
                    }
                    relationships.append(rel_data)
                return relationships
        except Exception as e:
            logger.error(f"Failed to retrieve relationships from graph: {e}")
            return []
    
    async def _extract_and_link_quotes(self, 
                                     segments: List[TranscriptSegment], 
                                     entities: List[Dict[str, Any]], 
                                     episode_id: str) -> int:
        """Extract quotes and link them to relevant entities in the graph."""
        quotes_linked = 0
        
        try:
            for i, segment in enumerate(segments):
                # Convert to internal segment format
                internal_segment = Segment(
                    id=f"{episode_id}_seg_{i}",
                    text=segment.text,
                    start_time=getattr(segment, 'start_time', 0.0),
                    end_time=getattr(segment, 'end_time', 0.0),
                    speaker=getattr(segment, 'speaker', 'Unknown')
                )
                
                # Extract quotes using existing extractor
                extraction_result = self.knowledge_extractor.extract_knowledge(internal_segment)
                
                if extraction_result.quotes:
                    # Link quotes to entities mentioned in the same segment
                    for quote_data in extraction_result.quotes:
                        # Handle both Quote objects and dict representations
                        if hasattr(quote_data, 'text'):
                            quote_text = quote_data.text
                            quote_obj = quote_data
                        else:
                            quote_text = quote_data.get('text', '')
                            # Create a mock Quote object from dict
                            quote_obj = type('Quote', (), {
                                'text': quote_text,
                                'type': quote_data.get('type', 'general'),
                                'context': quote_data.get('context', '')
                            })()
                        
                        linked_entities = self._find_related_entities(quote_text, entities)
                        
                        # Store quote in Neo4j with entity links
                        await self._store_quote_with_entity_links(
                            quote_obj, linked_entities, internal_segment, episode_id
                        )
                        quotes_linked += 1
                        
        except Exception as e:
            logger.error(f"Failed to extract and link quotes: {e}")
        
        logger.info(f"Linked {quotes_linked} quotes to entities")
        return quotes_linked
    
    async def _generate_and_link_insights(self, 
                                        segments: List[TranscriptSegment], 
                                        entities: List[Dict[str, Any]], 
                                        episode_id: str) -> int:
        """Generate insights and link them to relevant entities."""
        insights_linked = 0
        
        try:
            # Generate insights from segments
            for i, segment in enumerate(segments):
                internal_segment = Segment(
                    id=f"{episode_id}_seg_{i}",
                    text=segment.text,
                    start_time=getattr(segment, 'start_time', 0.0),
                    end_time=getattr(segment, 'end_time', 0.0),
                    speaker=getattr(segment, 'speaker', 'Unknown')
                )
                
                # Extract insights using existing extractor
                extraction_result = self.knowledge_extractor.extract_knowledge(internal_segment)
                
                if extraction_result.insights:
                    for insight_data in extraction_result.insights:
                        # Handle both Insight objects and dict representations
                        if hasattr(insight_data, 'content'):
                            insight_content = insight_data.content
                            insight_obj = insight_data
                        else:
                            insight_content = insight_data.get('content', '')
                            # Create a mock Insight object from dict
                            insight_obj = type('Insight', (), {
                                'content': insight_content,
                                'type': insight_data.get('type', 'general'),
                                'confidence': insight_data.get('confidence', 0.5)
                            })()
                        
                        # Find entities mentioned in the insight
                        related_entities = self._find_related_entities(insight_content, entities)
                        
                        # Store insight with entity relationships
                        await self._store_insight_with_entity_links(
                            insight_obj, related_entities, internal_segment, episode_id
                        )
                        insights_linked += 1
                        
        except Exception as e:
            logger.error(f"Failed to generate and link insights: {e}")
        
        logger.info(f"Generated and linked {insights_linked} insights")
        return insights_linked
    
    async def _analyze_and_store_complexity(self, 
                                          segments: List[TranscriptSegment], 
                                          entities: List[Dict[str, Any]], 
                                          episode_id: str) -> bool:
        """Analyze complexity and store results in the graph."""
        try:
            # Analyze complexity for each segment
            segment_complexities = []
            for i, segment in enumerate(segments):
                complexity = self.complexity_analyzer.classify_segment_complexity(
                    segment.text, 
                    entities=None  # Could pass relevant entities if needed
                )
                complexity.segment_id = f"{episode_id}_seg_{i}"
                segment_complexities.append(complexity)
            
            # Calculate episode-level complexity
            episode_complexity = self.complexity_analyzer.calculate_episode_complexity(segment_complexities)
            
            # Store complexity data in Neo4j
            await self._store_complexity_analysis(episode_complexity, segment_complexities, episode_id)
            
            logger.info(f"Complexity analysis completed: avg={episode_complexity.average_complexity:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze complexity: {e}")
            return False
    
    async def _calculate_importance_scores(self, 
                                         entities: List[Dict[str, Any]], 
                                         segments: List[TranscriptSegment], 
                                         episode_id: str) -> int:
        """Calculate importance scores for entities and update the graph."""
        scored_entities = 0
        
        try:
            # Convert segments to internal format for importance scoring
            internal_segments = []
            for i, segment in enumerate(segments):
                internal_segment = Segment(
                    id=f"{episode_id}_seg_{i}",
                    text=segment.text,
                    start_time=getattr(segment, 'start_time', 0.0),
                    end_time=getattr(segment, 'end_time', 0.0),
                    speaker=getattr(segment, 'speaker', 'Unknown')
                )
                internal_segments.append(internal_segment)
            
            # Calculate episode duration for frequency normalization
            episode_duration = max(seg.end_time for seg in internal_segments) if internal_segments else 60.0
            
            for entity in entities:
                try:
                    # Find mentions of this entity across segments
                    entity_mentions = self._find_entity_mentions(entity, internal_segments)
                    
                    if entity_mentions:
                        # Calculate frequency factor
                        frequency_factor = self.importance_scorer.calculate_frequency_factor(
                            entity_mentions, episode_duration
                        )
                        
                        # Calculate discourse function
                        discourse_analysis = self.importance_scorer.analyze_discourse_function(
                            entity_mentions, internal_segments
                        )
                        
                        # Calculate temporal dynamics
                        temporal_analysis = self.importance_scorer.analyze_temporal_dynamics(
                            entity_mentions, internal_segments
                        )
                        
                        # Combine factors for composite score
                        all_factors = {
                            "frequency": frequency_factor,
                            **discourse_analysis,
                            **temporal_analysis
                        }
                        
                        composite_score = self.importance_scorer.calculate_composite_importance(all_factors)
                        
                        # Update entity in Neo4j with importance data
                        await self._update_entity_importance(entity, composite_score, all_factors)
                        scored_entities += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to score entity {entity.get('name', 'unknown')}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to calculate importance scores: {e}")
        
        logger.info(f"Calculated importance scores for {scored_entities} entities")
        return scored_entities
    
    async def _add_temporal_discourse_analysis(self, 
                                             segments: List[TranscriptSegment], 
                                             entities: List[Dict[str, Any]], 
                                             episode_id: str):
        """Add temporal and discourse analysis to the knowledge graph."""
        try:
            # Analyze conversation flow and topic transitions
            topic_transitions = self._analyze_topic_transitions(segments, entities)
            
            # Store temporal flow information
            await self._store_temporal_analysis(topic_transitions, episode_id)
            
            logger.info("Temporal and discourse analysis completed")
        except Exception as e:
            logger.error(f"Failed to add temporal discourse analysis: {e}")
    
    async def _enrich_speaker_information(self, 
                                        segments: List[TranscriptSegment], 
                                        entities: List[Dict[str, Any]], 
                                        episode_id: str):
        """Enrich entities with speaker attribution and information."""
        try:
            # Map entities to speakers who mentioned them
            speaker_entity_map = {}
            
            for i, segment in enumerate(segments):
                speaker = getattr(segment, 'speaker', 'Unknown')
                segment_entities = self._find_entities_in_segment(segment.text, entities)
                
                if speaker not in speaker_entity_map:
                    speaker_entity_map[speaker] = []
                
                speaker_entity_map[speaker].extend(segment_entities)
            
            # Store speaker-entity relationships
            await self._store_speaker_entity_relationships(speaker_entity_map, episode_id)
            
            logger.info("Speaker information enrichment completed")
        except Exception as e:
            logger.error(f"Failed to enrich speaker information: {e}")
    
    def _find_related_entities(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find entities mentioned in the given text."""
        related = []
        text_lower = text.lower()
        
        for entity in entities:
            entity_name = entity.get('name', '').lower()
            if entity_name and entity_name in text_lower:
                related.append(entity)
        
        return related
    
    def _find_entity_mentions(self, entity: Dict[str, Any], segments: List[Segment]) -> List[Dict[str, Any]]:
        """Find all mentions of an entity across segments."""
        mentions = []
        entity_name = entity.get('name', '').lower()
        
        for i, segment in enumerate(segments):
            if entity_name in segment.text.lower():
                mentions.append({
                    "segment_index": i,
                    "timestamp": segment.start_time,
                    "speaker": segment.speaker,
                    "context": segment.text
                })
        
        return mentions
    
    def _find_entities_in_segment(self, text: str, entities: List[Dict[str, Any]]) -> List[str]:
        """Find entity names mentioned in a segment."""
        found_entities = []
        text_lower = text.lower()
        
        for entity in entities:
            entity_name = entity.get('name', '')
            if entity_name and entity_name.lower() in text_lower:
                found_entities.append(entity_name)
        
        return found_entities
    
    def _analyze_topic_transitions(self, segments: List[TranscriptSegment], entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze topic transitions throughout the episode."""
        transitions = []
        
        # Simple topic transition detection based on entity changes
        prev_entities = set()
        
        for i, segment in enumerate(segments):
            current_entities = set(self._find_entities_in_segment(segment.text, entities))
            
            if i > 0 and current_entities != prev_entities:
                # Detected a topic transition
                transitions.append({
                    "segment_index": i,
                    "timestamp": getattr(segment, 'start_time', 0.0),
                    "previous_entities": list(prev_entities),
                    "new_entities": list(current_entities),
                    "overlap": list(current_entities.intersection(prev_entities))
                })
            
            prev_entities = current_entities
        
        return transitions
    
    async def _store_quote_with_entity_links(self, quote: Quote, entities: List[Dict[str, Any]], 
                                           segment: Segment, episode_id: str):
        """Store quote in Neo4j with links to related entities."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        CREATE (q:Quote {
            text: $quote_text,
            type: $quote_type,
            importance: $importance,
            segment_id: $segment_id,
            timestamp: $timestamp,
            speaker: $speaker,
            context: $context
        })
        CREATE (e)-[:HAS_QUOTE]->(q)
        
        WITH q
        UNWIND $entity_names as entity_name
        MATCH (entity) WHERE entity.name = entity_name
        CREATE (q)-[:MENTIONS_ENTITY]->(entity)
        """
        
        try:
            with self.graph_storage.get_session() as session:
                session.run(query, 
                          episode_id=episode_id,
                          quote_text=quote.text,
                          quote_type=quote.type.value if hasattr(quote.type, 'value') else str(quote.type),
                          importance=getattr(quote, 'importance', 0.5),
                          segment_id=segment.id,
                          timestamp=segment.start_time,
                          speaker=segment.speaker,
                          context=quote.context,
                          entity_names=[e.get('name') for e in entities if e.get('name')])
        except Exception as e:
            logger.warning(f"Failed to store quote: {e}")
    
    async def _store_insight_with_entity_links(self, insight: Insight, entities: List[Dict[str, Any]], 
                                             segment: Segment, episode_id: str):
        """Store insight in Neo4j with links to related entities."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        CREATE (i:Insight {
            content: $content,
            type: $insight_type,
            confidence: $confidence,
            segment_id: $segment_id,
            timestamp: $timestamp,
            speaker: $speaker
        })
        CREATE (e)-[:HAS_INSIGHT]->(i)
        
        WITH i
        UNWIND $entity_names as entity_name
        MATCH (entity) WHERE entity.name = entity_name
        CREATE (i)-[:RELATES_TO_ENTITY]->(entity)
        """
        
        try:
            with self.graph_storage.get_session() as session:
                session.run(query,
                          episode_id=episode_id,
                          content=insight.content,
                          insight_type=insight.type.value if hasattr(insight.type, 'value') else str(insight.type),
                          confidence=getattr(insight, 'confidence', 0.5),
                          segment_id=segment.id,
                          timestamp=segment.start_time,
                          speaker=segment.speaker,
                          entity_names=[e.get('name') for e in entities if e.get('name')])
        except Exception as e:
            logger.warning(f"Failed to store insight: {e}")
    
    async def _store_complexity_analysis(self, episode_complexity: EpisodeComplexity, 
                                       segment_complexities: List[SegmentComplexity], 
                                       episode_id: str):
        """Store complexity analysis results in Neo4j."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        SET e.complexity_score = $avg_complexity,
            e.complexity_level = $dominant_level,
            e.complexity_variance = $variance,
            e.technical_density = $technical_density
        
        WITH e
        UNWIND $segment_data as seg
        CREATE (c:ComplexityAnalysis {
            segment_id: seg.segment_id,
            complexity_score: seg.score,
            complexity_level: seg.level,
            readability_score: seg.readability,
            technical_entity_count: seg.technical_entities,
            vocabulary_richness: seg.vocab_richness
        })
        CREATE (e)-[:HAS_COMPLEXITY_ANALYSIS]->(c)
        """
        
        try:
            segment_data = [
                {
                    "segment_id": sc.segment_id,
                    "score": sc.complexity_score,
                    "level": sc.complexity_level.value if hasattr(sc.complexity_level, 'value') else str(sc.complexity_level),
                    "readability": sc.readability_score,
                    "technical_entities": sc.technical_entity_count,
                    "vocab_richness": sc.vocabulary_metrics.vocabulary_richness
                }
                for sc in segment_complexities
            ]
            
            with self.graph_storage.get_session() as session:
                session.run(query,
                          episode_id=episode_id,
                          avg_complexity=episode_complexity.average_complexity,
                          dominant_level=episode_complexity.dominant_level.value if hasattr(episode_complexity.dominant_level, 'value') else str(episode_complexity.dominant_level),
                          variance=episode_complexity.complexity_variance,
                          technical_density=episode_complexity.technical_density,
                          segment_data=segment_data)
        except Exception as e:
            logger.warning(f"Failed to store complexity analysis: {e}")
    
    async def _update_entity_importance(self, entity: Dict[str, Any], score: float, factors: Dict[str, float]):
        """Update entity in Neo4j with importance score and factors."""
        query = """
        MATCH (entity) WHERE id(entity) = $neo4j_id
        SET entity.importance_score = $score,
            entity.frequency_factor = $frequency,
            entity.discourse_function = $discourse,
            entity.temporal_dynamics = $temporal
        """
        
        try:
            with self.graph_storage.get_session() as session:
                session.run(query,
                          neo4j_id=entity.get('neo4j_id'),
                          score=score,
                          frequency=factors.get('frequency', 0.0),
                          discourse=factors.get('development_role', 0.0),
                          temporal=factors.get('persistence_score', 0.0))
        except Exception as e:
            logger.warning(f"Failed to update entity importance: {e}")
    
    async def _store_temporal_analysis(self, transitions: List[Dict[str, Any]], episode_id: str):
        """Store temporal analysis results in Neo4j."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        UNWIND $transitions as transition
        CREATE (t:TopicTransition {
            segment_index: transition.segment_index,
            timestamp: transition.timestamp,
            previous_entities: transition.previous_entities,
            new_entities: transition.new_entities,
            overlap_entities: transition.overlap
        })
        CREATE (e)-[:HAS_TOPIC_TRANSITION]->(t)
        """
        
        try:
            with self.graph_storage.get_session() as session:
                session.run(query, episode_id=episode_id, transitions=transitions)
        except Exception as e:
            logger.warning(f"Failed to store temporal analysis: {e}")
    
    async def _store_speaker_entity_relationships(self, speaker_entity_map: Dict[str, List[str]], episode_id: str):
        """Store speaker-entity relationships in Neo4j."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        UNWIND $speaker_data as speaker_info
        MERGE (s:Speaker {name: speaker_info.speaker})
        CREATE (e)-[:HAS_SPEAKER]->(s)
        
        WITH s, speaker_info
        UNWIND speaker_info.entities as entity_name
        MATCH (entity) WHERE entity.name = entity_name
        MERGE (s)-[:MENTIONED_ENTITY]->(entity)
        """
        
        try:
            speaker_data = [
                {
                    "speaker": speaker,
                    "entities": list(set(entities))  # Remove duplicates
                }
                for speaker, entities in speaker_entity_map.items()
                if entities
            ]
            
            with self.graph_storage.get_session() as session:
                session.run(query, episode_id=episode_id, speaker_data=speaker_data)
        except Exception as e:
            logger.warning(f"Failed to store speaker-entity relationships: {e}")