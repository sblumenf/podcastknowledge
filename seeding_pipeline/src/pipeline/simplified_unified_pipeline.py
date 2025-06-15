"""
Simplified Unified Pipeline for Knowledge Extraction

This module provides a single, simplified pipeline that:
1. Uses SimpleKGPipeline for core entity/relationship extraction
2. Stores MeaningfulUnits as primary segments
3. Maintains ALL existing knowledge extraction features
4. Follows KISS principle with minimal complexity
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from src.core.interfaces import TranscriptSegment
from src.core.models import Episode, Podcast
from src.storage.graph_storage import GraphStorageService
from src.vtt.vtt_parser import VTTParser
from src.services.llm import LLMService
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.segment_regrouper import SegmentRegrouper, MeaningfulUnit
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.extraction.entity_resolution import EntityResolver
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SimplifiedUnifiedPipeline:
    """
    Simplified pipeline that chains existing components for knowledge extraction.
    
    This pipeline:
    1. Parses VTT files into segments
    2. Creates MeaningfulUnits via ConversationAnalyzer + SegmentRegrouper
    3. Stores MeaningfulUnits in Neo4j (not individual segments)
    4. Runs ALL knowledge extraction on MeaningfulUnits
    5. Links all extracted knowledge to MeaningfulUnits
    """
    
    def __init__(
        self,
        graph_storage: GraphStorageService,
        llm_service: LLMService,
        extraction_config: Optional[ExtractionConfig] = None
    ):
        """
        Initialize the simplified unified pipeline.
        
        Args:
            graph_storage: Neo4j storage service
            llm_service: LLM service for analysis
            extraction_config: Configuration for knowledge extraction
        """
        self.graph_storage = graph_storage
        self.llm_service = llm_service
        self.extraction_config = extraction_config or ExtractionConfig()
        
        # Initialize components
        self.vtt_parser = VTTParser()
        self.conversation_analyzer = ConversationAnalyzer(llm_service)
        self.segment_regrouper = SegmentRegrouper()
        self.knowledge_extractor = KnowledgeExtractor(
            llm_service=llm_service,
            config=extraction_config
        )
        self.entity_resolver = EntityResolver()
        
        logger.info("Initialized SimplifiedUnifiedPipeline")
    
    def process_episode(
        self,
        vtt_file_path: str,
        episode: Episode,
        podcast: Podcast
    ) -> Dict[str, Any]:
        """
        Process a single episode through the unified pipeline.
        
        Args:
            vtt_file_path: Path to VTT transcript file
            episode: Episode metadata
            podcast: Podcast metadata
            
        Returns:
            Processing results with extraction statistics
        """
        start_time = time.time()
        logger.info(f"Processing episode: {episode.id}")
        
        try:
            # Step 1: Parse VTT file into segments
            logger.info("Step 1: Parsing VTT file...")
            segments = self._parse_vtt_file(vtt_file_path)
            logger.info(f"Parsed {len(segments)} segments")
            
            # Step 2: Create MeaningfulUnits
            logger.info("Step 2: Creating MeaningfulUnits...")
            meaningful_units = self._create_meaningful_units(segments, episode.id)
            logger.info(f"Created {len(meaningful_units)} MeaningfulUnits")
            
            # Step 3: Store episode structure in Neo4j
            logger.info("Step 3: Storing episode structure...")
            self._store_episode_structure(podcast, episode, meaningful_units)
            
            # Step 4: Extract knowledge from MeaningfulUnits
            logger.info("Step 4: Extracting knowledge...")
            extraction_results = self._extract_knowledge(meaningful_units, episode)
            
            # Step 5: Store extracted knowledge
            logger.info("Step 5: Storing extracted knowledge...")
            storage_results = self._store_knowledge(
                extraction_results,
                meaningful_units,
                episode.id
            )
            
            # Calculate metrics
            processing_time = time.time() - start_time
            
            results = {
                'episode_id': episode.id,
                'segments_parsed': len(segments),
                'meaningful_units_created': len(meaningful_units),
                'entities_extracted': storage_results['entities_stored'],
                'insights_extracted': storage_results['insights_stored'],
                'quotes_extracted': storage_results['quotes_stored'],
                'relationships_created': storage_results['relationships_stored'],
                'processing_time': processing_time,
                'status': 'success'
            }
            
            logger.info(f"Episode processing complete in {processing_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            return {
                'episode_id': episode.id,
                'status': 'failed',
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def _parse_vtt_file(self, vtt_file_path: str) -> List[TranscriptSegment]:
        """Parse VTT file into transcript segments."""
        vtt_path = Path(vtt_file_path)
        if not vtt_path.exists():
            raise FileNotFoundError(f"VTT file not found: {vtt_file_path}")
        
        segments = self.vtt_parser.parse_file_with_metadata(vtt_path)['segments']
        return segments
    
    def _create_meaningful_units(
        self,
        segments: List[TranscriptSegment],
        episode_id: str
    ) -> List[MeaningfulUnit]:
        """Create MeaningfulUnits from segments using conversation analysis."""
        # Analyze conversation structure
        structure = self.conversation_analyzer.analyze_structure(segments)
        
        # Regroup segments into meaningful units
        meaningful_units = self.segment_regrouper.regroup_segments(segments, structure)
        
        # Adjust start times for YouTube URLs (subtract 2 seconds)
        for unit in meaningful_units:
            unit.start_time = max(0, unit.start_time - 2.0)
        
        return meaningful_units
    
    def _store_episode_structure(
        self,
        podcast: Podcast,
        episode: Episode,
        meaningful_units: List[MeaningfulUnit]
    ) -> None:
        """Store podcast, episode, and MeaningfulUnits in Neo4j."""
        # Store podcast (merge to avoid duplicates)
        with self.graph_storage.session() as session:
            session.run("""
                MERGE (p:Podcast {id: $id})
                SET p.title = $title, p.description = $description
            """, id=podcast.id, title=podcast.name, description=podcast.description)
        
        # Store episode
        with self.graph_storage.session() as session:
            session.run("""
                MERGE (e:Episode {id: $id})
                SET e.title = $title, 
                    e.description = $description,
                    e.published_date = $published_date,
                    e.youtube_url = $youtube_url
                WITH e
                MATCH (p:Podcast {id: $podcast_id})
                MERGE (p)-[:HAS_EPISODE]->(e)
            """, 
                id=episode.id,
                title=episode.title,
                description=episode.description,
                published_date=episode.published_date,
                youtube_url=episode.youtube_url,
                podcast_id=podcast.id
            )
        
        # Store MeaningfulUnits (NOT individual segments)
        for unit in meaningful_units:
            unit_data = {
                'id': unit.id,
                'text': unit.text,
                'start_time': unit.start_time,  # Already adjusted for YouTube
                'end_time': unit.end_time,
                'summary': unit.summary,
                'speaker_distribution': unit.speaker_distribution,
                'unit_type': unit.unit_type,
                'themes': unit.themes,
                'segment_indices': [seg.id for seg in unit.segments]
            }
            
            self.graph_storage.create_meaningful_unit(unit_data, episode.id)
    
    def _extract_knowledge(
        self,
        meaningful_units: List[MeaningfulUnit],
        episode: Episode
    ) -> Dict[str, Any]:
        """Extract all knowledge from MeaningfulUnits."""
        all_extraction_results = {
            'entities': [],
            'insights': [],
            'quotes': [],
            'gaps': [],
            'themes': [],
            'relationships': []
        }
        
        # Process each meaningful unit
        for unit in meaningful_units:
            # Extract knowledge from this unit's text
            extraction_result = self.knowledge_extractor.extract(
                text=unit.text,
                metadata={
                    'unit_id': unit.id,
                    'episode_id': episode.id,
                    'unit_type': unit.unit_type,
                    'themes': unit.themes
                }
            )
            
            # Aggregate results
            if extraction_result.entities:
                all_extraction_results['entities'].extend(extraction_result.entities)
            if extraction_result.insights:
                all_extraction_results['insights'].extend(extraction_result.insights)
            if extraction_result.quotes:
                all_extraction_results['quotes'].extend(extraction_result.quotes)
            if hasattr(extraction_result, 'gaps') and extraction_result.gaps:
                all_extraction_results['gaps'].extend(extraction_result.gaps)
            if hasattr(extraction_result, 'themes') and extraction_result.themes:
                all_extraction_results['themes'].extend(extraction_result.themes)
            if hasattr(extraction_result, 'relationships') and extraction_result.relationships:
                all_extraction_results['relationships'].extend(extraction_result.relationships)
        
        # Resolve entities across all units
        if all_extraction_results['entities']:
            resolved_entities = self.entity_resolver.resolve(all_extraction_results['entities'])
            all_extraction_results['entities'] = resolved_entities
        
        return all_extraction_results
    
    def _store_knowledge(
        self,
        extraction_results: Dict[str, Any],
        meaningful_units: List[MeaningfulUnit],
        episode_id: str
    ) -> Dict[str, int]:
        """Store extracted knowledge and link to MeaningfulUnits."""
        storage_stats = {
            'entities_stored': 0,
            'insights_stored': 0,
            'quotes_stored': 0,
            'relationships_stored': 0
        }
        
        # Create a mapping of which unit contains what content for linking
        unit_text_map = {unit.id: unit.text for unit in meaningful_units}
        
        # Store entities and link to MeaningfulUnits
        for entity in extraction_results.get('entities', []):
            # Store entity
            entity_id = entity.properties.get('id', entity.name)
            with self.graph_storage.session() as session:
                session.run("""
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name,
                        e.type = $type,
                        e.confidence = $confidence
                """, 
                    id=entity_id,
                    name=entity.name,
                    type=entity.entity_type.value if hasattr(entity, 'entity_type') else 'unknown',
                    confidence=entity.confidence
                )
            
            # Find which meaningful unit(s) mention this entity
            for unit_id, unit_text in unit_text_map.items():
                if entity.name.lower() in unit_text.lower():
                    self.graph_storage.create_meaningful_unit_relationship(
                        source_id=entity_id,
                        unit_id=unit_id,
                        rel_type='MENTIONED_IN',
                        properties={'confidence': entity.confidence}
                    )
            
            storage_stats['entities_stored'] += 1
        
        # Store insights and link to MeaningfulUnits
        for insight in extraction_results.get('insights', []):
            insight_id = insight.get('id', f"insight_{episode_id}_{storage_stats['insights_stored']}")
            
            with self.graph_storage.session() as session:
                session.run("""
                    CREATE (i:Insight {
                        id: $id,
                        content: $content,
                        type: $type,
                        confidence: $confidence
                    })
                """,
                    id=insight_id,
                    content=insight.get('content', ''),
                    type=insight.get('type', 'general'),
                    confidence=insight.get('confidence', 0.8)
                )
            
            # Link to the MeaningfulUnit it was extracted from
            unit_id = insight.get('metadata', {}).get('unit_id')
            if unit_id:
                self.graph_storage.create_meaningful_unit_relationship(
                    source_id=insight_id,
                    unit_id=unit_id,
                    rel_type='EXTRACTED_FROM'
                )
            
            storage_stats['insights_stored'] += 1
        
        # Store quotes and link to MeaningfulUnits
        for quote in extraction_results.get('quotes', []):
            quote_id = quote.get('id', f"quote_{episode_id}_{storage_stats['quotes_stored']}")
            
            with self.graph_storage.session() as session:
                session.run("""
                    CREATE (q:Quote {
                        id: $id,
                        text: $text,
                        speaker: $speaker,
                        significance: $significance
                    })
                """,
                    id=quote_id,
                    text=quote.get('text', ''),
                    speaker=quote.get('speaker', 'Unknown'),
                    significance=quote.get('significance', '')
                )
            
            # Find which meaningful unit contains this quote
            quote_text = quote.get('text', '').lower()
            for unit_id, unit_text in unit_text_map.items():
                if quote_text in unit_text.lower():
                    self.graph_storage.create_meaningful_unit_relationship(
                        source_id=quote_id,
                        unit_id=unit_id,
                        rel_type='EXTRACTED_FROM'
                    )
                    break
            
            storage_stats['quotes_stored'] += 1
        
        # Store entity relationships
        for relationship in extraction_results.get('relationships', []):
            with self.graph_storage.session() as session:
                session.run("""
                    MATCH (a:Entity {id: $source_id})
                    MATCH (b:Entity {id: $target_id})
                    CREATE (a)-[r:RELATED_TO {
                        type: $rel_type,
                        strength: $strength
                    }]->(b)
                """,
                    source_id=relationship.get('source_id'),
                    target_id=relationship.get('target_id'),
                    rel_type=relationship.get('type', 'RELATED_TO'),
                    strength=relationship.get('strength', 0.5)
                )
            
            storage_stats['relationships_stored'] += 1
        
        return storage_stats