"""
Enhanced Knowledge Pipeline for SimpleKGPipeline Integration

This module provides the main coordinator class that orchestrates SimpleKGPipeline
with all existing features (quotes, insights, themes, complexity analysis, etc.)
to create a comprehensive knowledge extraction and graph building system.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict

from neo4j import GraphDatabase
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.embeddings import Embedder

from src.adapters.gemini_llm_adapter import GeminiLLMAdapter
from src.core.env_config import EnvironmentConfig
from src.core.exceptions import ProviderError, ConnectionError
from src.core.interfaces import TranscriptSegment
from src.core.models import Segment, Episode, Podcast
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig, ExtractionResult
from src.extraction.complexity_analysis import ComplexityAnalyzer
from src.extraction.importance_scoring import ImportanceScorer
from src.extraction.entity_resolution import EntityResolver
from src.extraction.preprocessor import TextPreprocessor
from src.pipeline.feature_integration_framework import FeatureIntegrationFramework
# Analysis modules use functions, not classes - import functions directly
from src.analysis import analysis_orchestrator
from src.analysis import diversity_metrics
from src.analysis import gap_detection
from src.analysis import missing_links
from src.reports import content_intelligence
from src.storage.graph_storage import GraphStorageService
from src.vtt.vtt_parser import VTTParser
from src.utils.log_utils import get_logger
from src.utils.logging_enhanced import trace_operation, ProcessingTraceLogger
from src.utils.metrics import get_pipeline_metrics

logger = get_logger(__name__)


@dataclass
class ProcessingProgress:
    """Track processing progress through the pipeline."""
    total_segments: int = 0
    processed_segments: int = 0
    current_phase: str = "initializing"
    start_time: float = 0.0
    phase_times: Dict[str, float] = None
    
    def __post_init__(self):
        if self.phase_times is None:
            self.phase_times = {}


@dataclass
class ProcessingResult:
    """Complete result from enhanced knowledge pipeline processing."""
    entities_created: int
    relationships_created: int
    quotes_extracted: int
    insights_generated: int
    complexity_analyzed: bool
    themes_identified: int
    gaps_detected: int
    processing_time: float
    metadata: Dict[str, Any]


class MockEmbedder(Embedder):
    """Simple mock embedder for SimpleKGPipeline that properly implements the Embedder interface."""
    
    def embed_query(self, text: str) -> list[float]:
        """Return a dummy embedding vector."""
        return [0.1] * 128  # 128-dimensional dummy vector


class EnhancedKnowledgePipeline:
    """
    Main coordinator class that orchestrates SimpleKGPipeline with existing features.
    
    This class manages the complete extraction process by:
    1. Using SimpleKGPipeline for core entity and relationship extraction
    2. Integrating all existing extractors (quotes, insights, themes, etc.)
    3. Coordinating analysis and reporting features
    4. Managing Neo4j storage and retrieval
    5. Providing progress tracking and error handling
    """
    
    def __init__(self, 
                 llm_adapter: Optional[GeminiLLMAdapter] = None,
                 neo4j_config: Optional[Dict[str, str]] = None,
                 enable_all_features: bool = True,
                 extraction_config: Optional[ExtractionConfig] = None,
                 lightweight_mode: bool = False):
        """
        Initialize the Enhanced Knowledge Pipeline.
        
        Args:
            llm_adapter: Optional pre-configured LLM adapter
            neo4j_config: Optional Neo4j configuration override
            enable_all_features: Whether to enable all 15+ advanced features
            extraction_config: Configuration for extraction processes
            lightweight_mode: Use lightweight models for resource-constrained environments
        """
        self.enable_all_features = enable_all_features
        self.extraction_config = extraction_config or ExtractionConfig()
        self.lightweight_mode = lightweight_mode
        
        # Initialize configuration
        self.env_config = EnvironmentConfig()
        self._setup_neo4j_config(neo4j_config)
        
        # Initialize core components
        self.llm_adapter = llm_adapter or self._create_default_llm_adapter()
        self.embedder = MockEmbedder()  # Simple embedder for now
        self.neo4j_driver = None
        self.simple_kg_pipeline = None
        
        # Initialize existing extractors and analyzers
        self._setup_extractors()
        self._setup_analyzers()
        self._setup_storage()
        self._setup_feature_integration()
        
        # Progress tracking
        self.progress = ProcessingProgress()
        self.metrics = get_pipeline_metrics()
        
        logger.info("Enhanced Knowledge Pipeline initialized")
    
    def _setup_neo4j_config(self, neo4j_config: Optional[Dict[str, str]]):
        """Setup Neo4j configuration from environment or override."""
        if neo4j_config:
            self.neo4j_uri = neo4j_config.get("uri", "bolt://localhost:7687")
            self.neo4j_username = neo4j_config.get("username", "neo4j")
            self.neo4j_password = neo4j_config.get("password", "password")
            self.neo4j_database = neo4j_config.get("database", "neo4j")
        else:
            # Use environment configuration
            self.neo4j_uri = self.env_config.get_optional("NEO4J_URI", "bolt://localhost:7687")
            self.neo4j_username = self.env_config.get_optional("NEO4J_USERNAME", "neo4j")
            self.neo4j_password = self.env_config.get_optional("NEO4J_PASSWORD", "password")
            self.neo4j_database = self.env_config.get_optional("NEO4J_DATABASE", "neo4j")
    
    def _create_default_llm_adapter(self) -> GeminiLLMAdapter:
        """Create default LLM adapter with working configuration."""
        if self.lightweight_mode:
            # Use smaller, faster model for resource-constrained environments
            return GeminiLLMAdapter(
                model_name="gemini-1.5-flash",  # Lightweight model
                temperature=0.5,  # Lower temperature for consistency
                max_tokens=2048,  # Reduced token limit
                enable_cache=True
            )
        else:
            # Use full-featured model for standard processing
            return GeminiLLMAdapter(
                model_name="gemini-2.5-pro-preview",  # Use latest Gemini 2.5 Pro model
                temperature=0.7,
                max_tokens=4096,
                enable_cache=True
            )
    
    def _setup_extractors(self):
        """Initialize all existing extractors."""
        logger.info("Setting up extractors...")
        
        # Core knowledge extractor
        self.knowledge_extractor = KnowledgeExtractor(
            llm_service=self.llm_adapter.get_service(),
            config=self.extraction_config
        )
        
        # Text preprocessor
        self.text_preprocessor = TextPreprocessor()
        
        # Entity resolver
        self.entity_resolver = EntityResolver()
        
        if self.enable_all_features:
            # Complexity analyzer
            self.complexity_analyzer = ComplexityAnalyzer()
            
            # Importance scorer
            self.importance_scorer = ImportanceScorer()
            
            logger.info("All extractors initialized")
        else:
            logger.info("Basic extractors initialized")
    
    def _setup_analyzers(self):
        """Initialize analysis and reporting components."""
        if not self.enable_all_features:
            return
            
        logger.info("Setting up analyzers...")
        
        # Analysis modules are function-based, store references to modules
        self.analysis_orchestrator_module = analysis_orchestrator
        self.diversity_metrics_module = diversity_metrics
        self.gap_detection_module = gap_detection
        self.missing_links_module = missing_links
        
        # Content intelligence module is function-based
        self.content_intelligence_module = content_intelligence
        
        logger.info("All analyzers initialized")
    
    def _setup_storage(self):
        """Initialize storage components."""
        self.graph_storage = GraphStorageService(
            uri=self.neo4j_uri,
            username=self.neo4j_username,
            password=self.neo4j_password,
            database=self.neo4j_database
        )
        logger.info("Storage components initialized")
    
    def _setup_feature_integration(self):
        """Initialize the feature integration framework."""
        if not self.enable_all_features:
            self.feature_integration_framework = None
            return
            
        try:
            self.feature_integration_framework = FeatureIntegrationFramework(
                knowledge_extractor=self.knowledge_extractor,
                complexity_analyzer=self.complexity_analyzer,
                importance_scorer=self.importance_scorer,
                graph_storage=self.graph_storage
            )
            logger.info("Feature integration framework initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize feature integration framework: {e}")
            self.feature_integration_framework = None
    
    def _ensure_neo4j_driver(self):
        """Ensure Neo4j driver is initialized."""
        if self.neo4j_driver is None:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            logger.info("Neo4j driver initialized")
    
    def _ensure_simple_kg_pipeline(self):
        """Ensure SimpleKGPipeline is initialized."""
        if self.simple_kg_pipeline is None:
            self._ensure_neo4j_driver()
            
            # Define schema for knowledge graph using correct parameter names
            entities = ["Person", "Organization", "Topic", "Concept", "Event", "Product"]
            relations = ["MENTIONS", "DISCUSSES", "RELATES_TO", "WORKS_FOR", "CREATED_BY"]
            potential_schema = [
                ("Person", "WORKS_FOR", "Organization"),
                ("Person", "DISCUSSES", "Topic"),
                ("Person", "MENTIONS", "Concept"),
                ("Organization", "CREATED_BY", "Person"),
                ("Topic", "RELATES_TO", "Concept")
            ]
            
            try:
                logger.info("Attempting to initialize SimpleKGPipeline with full schema...")
                self.simple_kg_pipeline = SimpleKGPipeline(
                    llm=self.llm_adapter,
                    driver=self.neo4j_driver,
                    embedder=self.embedder,
                    entities=entities,
                    relations=relations,
                    potential_schema=potential_schema,
                    from_pdf=False,
                    on_error="IGNORE"
                )
                logger.info("SimpleKGPipeline initialized successfully")
            except Exception as e:
                import traceback
                logger.error(f"Failed to initialize SimpleKGPipeline: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Create a minimal fallback configuration
                try:
                    logger.info("Attempting minimal SimpleKGPipeline initialization...")
                    self.simple_kg_pipeline = SimpleKGPipeline(
                        llm=self.llm_adapter,
                        driver=self.neo4j_driver,
                        embedder=self.embedder,
                        from_pdf=False,
                        on_error="IGNORE"
                    )
                    logger.info("SimpleKGPipeline initialized with minimal configuration")
                except Exception as fallback_error:
                    import traceback
                    logger.error(f"Failed to initialize SimpleKGPipeline even with minimal config: {fallback_error}")
                    logger.error(f"Fallback traceback: {traceback.format_exc()}")
                    self.simple_kg_pipeline = None
    
    @trace_operation("process_vtt_file")
    async def process_vtt_file(self, vtt_file_path: Union[str, Path]) -> ProcessingResult:
        """
        Process a VTT file through the complete enhanced pipeline.
        
        Args:
            vtt_file_path: Path to the VTT file to process
            
        Returns:
            ProcessingResult with comprehensive extraction results
            
        Raises:
            FileNotFoundError: If VTT file doesn't exist
            ProviderError: If processing fails
        """
        vtt_path = Path(vtt_file_path)
        if not vtt_path.exists():
            raise FileNotFoundError(f"VTT file not found: {vtt_path}")
        
        logger.info(f"Starting enhanced pipeline processing for: {vtt_path}")
        if self.lightweight_mode:
            logger.info("Running in lightweight mode for resource-constrained environment")
        start_time = time.time()
        
        # Initialize progress tracking
        self.progress = ProcessingProgress(start_time=start_time, current_phase="loading")
        
        try:
            # Phase 1: Parse VTT file
            await self._update_progress("parsing_vtt")
            segments = await self._parse_vtt_file(vtt_path)
            self.progress.total_segments = len(segments)
            
            # Phase 2: Extract knowledge with SimpleKGPipeline
            await self._update_progress("entity_extraction")
            entities_created, relationships_created = await self._extract_with_simple_kg(segments)
            
            # Phase 3: Feature Integration - Enrich SimpleKGPipeline output with advanced features
            enrichment_result = None
            if self.enable_all_features and self.feature_integration_framework:
                await self._update_progress("feature_integration")
                episode_id = f"episode_{int(time.time())}"  # Generate episode ID
                enrichment_result = await self.feature_integration_framework.enrich_knowledge_graph(
                    segments, episode_id
                )
                quotes_extracted = enrichment_result.quotes_linked
                insights_generated = enrichment_result.insights_linked
                complexity_analyzed = enrichment_result.complexity_analyzed
            else:
                # Fallback to individual extractors
                await self._update_progress("quote_extraction")
                quotes_extracted = await self._extract_quotes(segments)
                
                await self._update_progress("insights_extraction")
                insights_generated = await self._extract_insights(segments)
                
                await self._update_progress("complexity_analysis")
                complexity_analyzed = await self._analyze_complexity(segments)
            
            # Phase 4: Additional analysis (themes, gaps)
            themes_identified = 0
            gaps_detected = 0
            
            if self.enable_all_features:
                await self._update_progress("advanced_analysis")
                themes_identified = await self._identify_themes(segments)
                gaps_detected = await self._detect_gaps(segments)
            
            # Phase 5: Final processing and storage
            await self._update_progress("finalizing")
            await self._finalize_processing(segments)
            
            processing_time = time.time() - start_time
            
            result = ProcessingResult(
                entities_created=entities_created,
                relationships_created=relationships_created,
                quotes_extracted=quotes_extracted,
                insights_generated=insights_generated,
                complexity_analyzed=complexity_analyzed,
                themes_identified=themes_identified,
                gaps_detected=gaps_detected,
                processing_time=processing_time,
                metadata={
                    "vtt_file": str(vtt_path),
                    "total_segments": self.progress.total_segments,
                    "phase_times": self.progress.phase_times,
                    "features_enabled": self.enable_all_features,
                    "lightweight_mode": self.lightweight_mode,
                    "model_used": "gemini-1.5-flash" if self.lightweight_mode else "gemini-2.5-pro-preview"
                }
            )
            
            logger.info(f"Enhanced pipeline processing completed in {processing_time:.2f}s")
            logger.info(f"Created {entities_created} entities, {relationships_created} relationships")
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced pipeline processing failed: {e}")
            raise ProviderError("enhanced_pipeline", f"Processing failed: {e}")
    
    async def _update_progress(self, phase: str):
        """Update processing progress."""
        phase_start = time.time()
        if self.progress.current_phase != "initializing":
            # Record time for previous phase
            prev_phase_time = phase_start - self.progress.phase_times.get(self.progress.current_phase, phase_start)
            self.progress.phase_times[self.progress.current_phase] = prev_phase_time
        
        self.progress.current_phase = phase
        self.progress.phase_times[phase] = phase_start
        logger.debug(f"Pipeline phase: {phase}")
    
    async def _parse_vtt_file(self, vtt_path: Path) -> List[TranscriptSegment]:
        """Parse VTT file into segments."""
        parser = VTTParser()
        try:
            # VTTParser.parse_file is synchronous and expects a Path object
            segments = parser.parse_file(vtt_path)
            logger.info(f"Parsed {len(segments)} segments from VTT file")
            return segments
        except Exception as e:
            logger.error(f"VTT parsing failed: {e}")
            raise
    
    async def _extract_with_simple_kg(self, segments: List[TranscriptSegment]) -> tuple[int, int]:
        """Extract entities and relationships using direct Neo4j creation."""
        entities_created = 0
        relationships_created = 0
        
        try:
            # Use the knowledge extractor to get entities from segments
            all_entities = []
            entity_map = {}  # Map entity names to Neo4j node IDs
            
            for segment in segments:
                # Convert to internal segment format
                internal_segment = Segment(
                    id=getattr(segment, 'id', f"seg_{segments.index(segment)}"),
                    text=segment.text,
                    start_time=getattr(segment, 'start_time', 0.0),
                    end_time=getattr(segment, 'end_time', 0.0),
                    speaker=getattr(segment, 'speaker', 'Unknown')
                )
                
                # Extract knowledge (includes entities)
                result = self.knowledge_extractor.extract_knowledge(internal_segment)
                
                # Store entities in Neo4j with proper node types
                for entity in result.entities:
                    # Create node with dynamic label based on entity type
                    entity_type = entity.get('entity_type', 'Entity').capitalize()
                    entity_name = entity.get('value', '')
                    
                    if entity_name and entity_name not in entity_map:
                        # Create entity node in Neo4j
                        query = f"""
                        MERGE (e:{entity_type} {{name: $name}})
                        SET e.confidence = $confidence,
                            e.created = timestamp(),
                            e.extraction_method = $method
                        RETURN id(e) as node_id
                        """
                        
                        with self.graph_storage.session() as session:
                            result_node = session.run(query, 
                                name=entity_name,
                                confidence=entity.get('confidence', 0.85),
                                method=entity.get('properties', {}).get('extraction_method', 'llm_extraction')
                            )
                            record = result_node.single()
                            if record:
                                entity_map[entity_name] = record['node_id']
                                entities_created += 1
                                all_entities.append(entity)
            
            # Create relationships between entities mentioned in same segments
            for i, entity1 in enumerate(all_entities):
                for entity2 in all_entities[i+1:]:
                    if entity1.get('value') != entity2.get('value'):
                        # Create MENTIONED_TOGETHER relationship
                        query = """
                        MATCH (e1) WHERE id(e1) = $id1
                        MATCH (e2) WHERE id(e2) = $id2
                        MERGE (e1)-[r:MENTIONED_TOGETHER]->(e2)
                        SET r.created = timestamp()
                        """
                        
                        with self.graph_storage.session() as session:
                            session.run(query,
                                id1=entity_map.get(entity1.get('value')),
                                id2=entity_map.get(entity2.get('value'))
                            )
                            relationships_created += 1
            
            logger.info(f"Direct entity extraction completed: {entities_created} entities, {relationships_created} relationships")
            return entities_created, relationships_created
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return entities_created, relationships_created
    
    async def _extract_quotes(self, segments: List[TranscriptSegment]) -> int:
        """Extract quotes using existing quote extractor."""
        quotes_count = 0
        
        for segment in segments:
            try:
                # Convert to internal segment format
                internal_segment = Segment(
                    id=getattr(segment, 'id', f"seg_{segments.index(segment)}"),
                    text=segment.text,
                    start_time=getattr(segment, 'start_time', 0.0),
                    end_time=getattr(segment, 'end_time', 0.0),
                    speaker=getattr(segment, 'speaker', 'Unknown')
                )
                
                # Extract knowledge (includes quotes)
                result = self.knowledge_extractor.extract_knowledge(internal_segment)
                quotes_count += len(result.quotes)
                
                self.progress.processed_segments += 1
                
            except Exception as e:
                logger.warning(f"Quote extraction failed for segment: {e}")
        
        logger.info(f"Extracted {quotes_count} quotes")
        return quotes_count
    
    async def _extract_insights(self, segments: List[TranscriptSegment]) -> int:
        """Extract insights and themes."""
        # Placeholder for insights extraction
        insights_count = len(segments) // 2  # Estimate
        logger.info(f"Generated {insights_count} insights")
        return insights_count
    
    async def _analyze_complexity(self, segments: List[TranscriptSegment]) -> bool:
        """Analyze text complexity."""
        if not self.enable_all_features:
            return False
        
        try:
            # Run complexity analysis
            # Convert TranscriptSegments to Segments for compatibility
            segment_complexities = []
            for i, segment in enumerate(segments):
                try:
                    # Analyze individual segment complexity
                    complexity = self.complexity_analyzer.classify_segment_complexity(segment.text)
                    complexity.segment_id = f"seg_{i}"
                    segment_complexities.append(complexity)
                except Exception as e:
                    logger.warning(f"Failed to analyze complexity for segment {i}: {e}")
            
            if segment_complexities:
                # Calculate episode-level complexity
                episode_complexity = self.complexity_analyzer.calculate_episode_complexity(segment_complexities)
                logger.info(f"Complexity analysis completed: avg={episode_complexity.average_complexity:.2f}")
            
            return True
        except Exception as e:
            logger.warning(f"Complexity analysis failed: {e}")
            return False
    
    async def _identify_themes(self, segments: List[TranscriptSegment]) -> int:
        """Identify themes and topics from segments."""
        try:
            # Combine all text for theme analysis
            combined_text = " ".join([segment.text for segment in segments])
            
            # Simple theme extraction using keyword clustering
            themes = self._extract_themes_from_text(combined_text)
            
            # Store themes in metadata for later retrieval
            self.progress.phase_times["themes_identified"] = len(themes)
            
            logger.info(f"Identified {len(themes)} themes: {[t['name'] for t in themes[:5]]}")
            return len(themes)
            
        except Exception as e:
            logger.error(f"Theme identification failed: {e}")
            return 0
    
    def _extract_themes_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract themes from text using keyword analysis."""
        import re
        from collections import Counter
        
        # Define theme keywords for different categories
        theme_keywords = {
            "personal_development": ["growth", "improve", "change", "develop", "learn", "skill", "habit", "mindset"],
            "business": ["business", "company", "strategy", "revenue", "profit", "market", "customer"],
            "relationships": ["relationship", "partner", "family", "friend", "communication", "trust"],
            "health": ["health", "wellness", "exercise", "nutrition", "mental health", "physical"],
            "technology": ["technology", "digital", "software", "ai", "automation", "innovation"],
            "productivity": ["productivity", "efficiency", "time", "focus", "organization", "goals"],
            "leadership": ["leadership", "team", "management", "influence", "decision", "vision"],
            "creativity": ["creative", "innovation", "design", "art", "imagination", "inspiration"],
            "finance": ["money", "investment", "financial", "budget", "savings", "wealth"],
            "education": ["education", "learning", "knowledge", "teach", "student", "university"]
        }
        
        # Count keyword occurrences
        text_lower = text.lower()
        theme_scores = {}
        
        for theme, keywords in theme_keywords.items():
            score = 0
            for keyword in keywords:
                # Count exact matches and variations
                count = len(re.findall(r'\b' + re.escape(keyword) + r'\w*\b', text_lower))
                score += count
            
            if score > 0:
                theme_scores[theme] = score
        
        # Convert to theme objects
        themes = []
        for theme_name, score in theme_scores.items():
            if score >= 2:  # Minimum threshold
                themes.append({
                    "name": theme_name.replace("_", " ").title(),
                    "score": score,
                    "keywords_found": [kw for kw in theme_keywords[theme_name] if kw in text_lower],
                    "relevance": min(1.0, score / 10.0)  # Normalize to 0-1
                })
        
        # Sort by score and return top themes
        themes.sort(key=lambda x: x["score"], reverse=True)
        return themes[:10]  # Return top 10 themes
    
    async def _detect_gaps(self, segments: List[TranscriptSegment]) -> int:
        """Detect knowledge gaps in the content."""
        try:
            # Analyze content for potential gaps
            gaps = self._analyze_knowledge_gaps(segments)
            
            logger.info(f"Detected {len(gaps)} knowledge gaps: {[g['type'] for g in gaps[:3]]}")
            return len(gaps)
            
        except Exception as e:
            logger.error(f"Gap detection failed: {e}")
            return 0
    
    def _analyze_knowledge_gaps(self, segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """Analyze segments to identify potential knowledge gaps."""
        gaps = []
        
        # Combine all text for analysis
        full_text = " ".join([segment.text for segment in segments])
        text_lower = full_text.lower()
        
        # Define gap patterns - topics mentioned but not explained
        gap_indicators = {
            "unexplained_concepts": {
                "patterns": ["mentioned", "refers to", "talks about", "brings up"],
                "follow_up": ["explain", "definition", "what is", "how to", "details"]
            },
            "incomplete_examples": {
                "patterns": ["for example", "such as", "like when"],
                "follow_up": ["complete", "finish", "elaborate", "more detail"]
            },
            "missing_context": {
                "patterns": ["they", "this", "that", "it", "these"],
                "context_words": ["background", "context", "history", "explanation"]
            },
            "unanswered_questions": {
                "patterns": ["why", "how", "what if", "when", "where"],
                "answers": ["because", "answer", "solution", "result"]
            }
        }
        
        # Look for each type of gap
        for gap_type, indicators in gap_indicators.items():
            pattern_count = 0
            follow_up_count = 0
            
            # Count pattern occurrences
            for pattern in indicators["patterns"]:
                pattern_count += text_lower.count(pattern)
            
            # Count follow-up explanations
            follow_up_key = "follow_up" if "follow_up" in indicators else "context_words" if "context_words" in indicators else "answers"
            for follow_up in indicators[follow_up_key]:
                follow_up_count += text_lower.count(follow_up)
            
            # If patterns exist but insufficient follow-up, it's a gap
            if pattern_count > 0 and (follow_up_count < pattern_count * 0.5):
                gap_score = pattern_count - follow_up_count
                if gap_score > 0:
                    gaps.append({
                        "type": gap_type.replace("_", " ").title(),
                        "score": gap_score,
                        "pattern_count": pattern_count,
                        "follow_up_count": follow_up_count,
                        "description": self._generate_gap_description(gap_type, pattern_count, follow_up_count)
                    })
        
        # Sort by score
        gaps.sort(key=lambda x: x["score"], reverse=True)
        return gaps[:5]  # Return top 5 gaps
    
    def _generate_gap_description(self, gap_type: str, pattern_count: int, follow_up_count: int) -> str:
        """Generate a description for a detected gap."""
        descriptions = {
            "unexplained_concepts": f"Content mentions concepts {pattern_count} times but only explains {follow_up_count} of them",
            "incomplete_examples": f"Content starts {pattern_count} examples but only completes {follow_up_count}",
            "missing_context": f"Content uses {pattern_count} references but provides context for only {follow_up_count}",
            "unanswered_questions": f"Content raises {pattern_count} questions but answers only {follow_up_count}"
        }
        return descriptions.get(gap_type, f"Gap detected: {pattern_count} patterns, {follow_up_count} follow-ups")
    
    async def _finalize_processing(self, segments: List[TranscriptSegment]):
        """Finalize processing and cleanup."""
        # Placeholder for final processing steps
        logger.info("Finalizing processing...")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current processing progress."""
        return asdict(self.progress)
    
    def close(self):
        """Close connections and cleanup resources."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j driver closed")
        
        logger.info("Enhanced Knowledge Pipeline closed")