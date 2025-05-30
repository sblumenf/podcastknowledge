"""Pipeline execution component for processing episodes."""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.core.models import Podcast, Episode, Segment
from src.core.exceptions import PipelineError
from src.utils.memory import cleanup_memory
from src.tracing import create_span, add_span_attributes
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PipelineExecutor:
    """Executes the processing pipeline for podcast episodes."""
    
    def __init__(self, config, provider_coordinator, checkpoint_manager, storage_coordinator=None):
        """Initialize pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator instance
            checkpoint_manager: Checkpoint manager instance
            storage_coordinator: Storage coordinator instance (optional for backward compatibility)
        """
        self.config = config
        self.provider_coordinator = provider_coordinator
        self.checkpoint_manager = checkpoint_manager
        self.storage_coordinator = storage_coordinator
        
        # Get components from provider coordinator
        self.segmenter = provider_coordinator.segmenter
        self.knowledge_extractor = provider_coordinator.knowledge_extractor
        self.entity_resolver = provider_coordinator.entity_resolver
        self.discourse_flow_tracker = provider_coordinator.discourse_flow_tracker
        self.emergent_theme_detector = provider_coordinator.emergent_theme_detector
        self.episode_flow_analyzer = provider_coordinator.episode_flow_analyzer
        self.graph_provider = provider_coordinator.graph_provider
        self.llm_provider = provider_coordinator.llm_provider
        self.embedding_provider = provider_coordinator.embedding_provider
    
    def process_episode(self, podcast_config: Dict[str, Any], 
                       episode: Dict[str, Any],
                       use_large_context: bool) -> Dict[str, Any]:
        """Process a single episode through the pipeline.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            use_large_context: Whether to use large context
            
        Returns:
            Episode processing results
        """
        episode_id = episode['id']
        logger.info(f"Processing episode: {episode['title']} (ID: {episode_id})")
        
        # Check if already completed
        if self._is_episode_completed(episode_id):
            return {'segments': 0, 'insights': 0, 'entities': 0}
        
        # Download and process audio
        audio_path = self._download_episode_audio(episode, podcast_config['id'])
        
        try:
            # Add episode context
            self._add_episode_context(episode, podcast_config)
            
            # Process audio segments
            segments = self._process_audio_segments(audio_path, episode_id)
            
            # Extract knowledge based on mode
            result = self._extract_knowledge(
                podcast_config, episode, segments, episode_id, use_large_context
            )
            
            # Finalize processing
            self._finalize_episode_processing(episode_id, result)
            
            return result
            
        finally:
            # Cleanup
            self._cleanup_audio_file(audio_path)
    
    def _prepare_segments(self, audio_path: str) -> List[Dict[str, Any]]:
        """Prepare and process audio segments.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            List of processed segments
        """
        return self.segmenter.process_audio(audio_path)
    
    def _extract_fixed_schema(self, podcast_config: Dict[str, Any],
                            episode: Dict[str, Any],
                            segments: List[Dict[str, Any]],
                            episode_id: str,
                            use_large_context: bool) -> Dict[str, Any]:
        """Extract knowledge using fixed schema approach.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information  
            segments: Processed segments
            episode_id: Episode ID
            use_large_context: Whether to use large context
            
        Returns:
            Extraction results
        """
        logger.info("Using FIXED SCHEMA extraction pipeline")
        
        with create_span("fixed_schema_extraction", attributes={
            "segments.count": len(segments),
            "extraction.mode": "fixed"
        }):
            # Extract knowledge
            logger.info("Extracting knowledge...")
            extraction_result = self.knowledge_extractor.extract_knowledge(
                segments,
                episode_metadata={
                    'title': episode['title'],
                    'description': episode.get('description', ''),
                    'podcast_name': podcast_config.get('name', '')
                },
                use_large_context=use_large_context
            )
            
            add_span_attributes({
                "entities.extracted": len(extraction_result.get('entities', [])),
                "insights.extracted": len(extraction_result.get('insights', []))
            })
            
            # Save extraction checkpoint
            self.checkpoint_manager.save_progress(episode_id, 'extraction', extraction_result)
            
            # Resolve entities
            logger.info("Resolving entities...")
            resolved_entities = self._resolve_entities(
                extraction_result.get('entities', []),
                episode_id
            )
            
            # Analyze discourse flow
            segment_objects = self._create_segment_objects(segments, episode_id)
            flow_results = self.discourse_flow_tracker.analyze_episode_flow(
                segment_objects,
                resolved_entities,
                extraction_result.get('insights', [])
            )
            extraction_result['discourse_flow'] = flow_results
            
            # Detect emergent themes
            theme_results = self._detect_themes(
                resolved_entities,
                extraction_result,
                segment_objects
            )
            extraction_result['emergent_themes'] = theme_results
            
            # Analyze episode flow
            episode_flow = self._analyze_episode_flow(
                segment_objects,
                resolved_entities
            )
            extraction_result['episode_flow'] = episode_flow
            
            # Save to graph
            if self.storage_coordinator:
                self.storage_coordinator.store_all(
                    podcast_config,
                    episode,
                    segments,
                    extraction_result,
                    resolved_entities
                )
            else:
                # Fallback to direct method if storage coordinator not available
                self._save_to_graph(
                    podcast_config,
                    episode,
                    segments,
                    extraction_result,
                    resolved_entities
                )
            
            return {
                'segments': len(segments),
                'insights': len(extraction_result.get('insights', [])),
                'entities': len(resolved_entities),
                'mode': 'fixed'
            }
    
    def _extract_schemaless(self, podcast_config: Dict[str, Any],
                          episode: Dict[str, Any],
                          segments: List[Dict[str, Any]],
                          episode_id: str) -> Dict[str, Any]:
        """Extract knowledge using schemaless approach.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            episode_id: Episode ID
            
        Returns:
            Extraction results
        """
        logger.info("Using SCHEMALESS extraction pipeline")
        
        with create_span("schemaless_extraction", attributes={
            "segments.count": len(segments),
            "extraction.mode": "schemaless"
        }):
            # Check if graph provider supports schemaless
            if not hasattr(self.graph_provider, 'process_segment_schemaless'):
                raise PipelineError("Graph provider does not support schemaless extraction")
            
            # Convert to model objects
            podcast_obj = Podcast(
                id=podcast_config['id'],
                title=podcast_config.get('name', podcast_config['id']),
                description=podcast_config.get('description', ''),
                rss_url=podcast_config.get('rss_url', '')
            )
            episode_obj = Episode(
                id=episode['id'],
                title=episode['title'],
                description=episode.get('description', ''),
                published_date=episode.get('published_date', ''),
                audio_url=episode.get('audio_url', '')
            )
            
            extraction_results = []
            discovered_types = set()
            
            for i, segment_data in enumerate(segments):
                segment_obj = Segment(
                    id=f"{episode_id}_segment_{i}",
                    text=segment_data.get('text', ''),
                    start_time=segment_data.get('start_time', 0),
                    end_time=segment_data.get('end_time', 0),
                    speaker=segment_data.get('speaker', 'Unknown')
                )
                
                try:
                    result = self.graph_provider.process_segment_schemaless(
                        segment_obj, episode_obj, podcast_obj
                    )
                    
                    extraction_results.append(result)
                    if 'discovered_types' in result:
                        discovered_types.update(result['discovered_types'])
                        
                except Exception as e:
                    logger.error(f"Failed to process segment {i}: {e}")
                    continue
            
            # Save discovered types
            if discovered_types:
                self.checkpoint_manager.save_schema_evolution(
                    episode_id, 
                    list(discovered_types)
                )
            
            # Aggregate results
            total_entities = sum(r.get('entities', 0) for r in extraction_results)
            total_relationships = sum(r.get('relationships', 0) for r in extraction_results)
            
            return {
                'segments': len(segments),
                'insights': 0,  # Schemaless mode doesn't track insights separately
                'entities': total_entities,
                'relationships': total_relationships,
                'discovered_types': list(discovered_types),
                'mode': 'schemaless'
            }
    
    def _handle_migration_mode(self, podcast_config: Dict[str, Any],
                             episode: Dict[str, Any],
                             segments: List[Dict[str, Any]],
                             episode_id: str,
                             use_large_context: bool) -> Dict[str, Any]:
        """Handle migration mode by running both extraction methods.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            episode_id: Episode ID
            use_large_context: Whether to use large context
            
        Returns:
            Combined extraction results
        """
        logger.info("Running in MIGRATION MODE - executing both extraction pipelines")
        
        # Run fixed schema extraction
        fixed_result = self._extract_fixed_schema(
            podcast_config, episode, segments, episode_id, use_large_context
        )
        
        # Run schemaless extraction
        schemaless_result = self._extract_schemaless(
            podcast_config, episode, segments, episode_id
        )
        
        # Compare results
        logger.info(f"Migration mode comparison:")
        logger.info(f"  Fixed schema: {fixed_result['entities']} entities")
        logger.info(f"  Schemaless: {schemaless_result['entities']} entities, "
                   f"{len(schemaless_result.get('discovered_types', []))} types")
        
        # Return combined results
        return {
            'segments': len(segments),
            'insights': fixed_result['insights'],
            'entities': fixed_result['entities'],
            'relationships': schemaless_result.get('relationships', 0),
            'discovered_types': schemaless_result.get('discovered_types', []),
            'mode': 'migration',
            'fixed_result': fixed_result,
            'schemaless_result': schemaless_result
        }
    
    def _resolve_entities(self, entities: List[Dict[str, Any]], 
                         episode_id: str) -> List[Any]:
        """Resolve and deduplicate entities.
        
        Args:
            entities: List of extracted entities
            episode_id: Episode ID
            
        Returns:
            List of resolved entities
        """
        with create_span("entity_resolution", attributes={"entities.count": len(entities)}):
            resolved_entities = self.entity_resolver.resolve_entities(entities)
            add_span_attributes({"entities.resolved": len(resolved_entities)})
            
            # Save resolution checkpoint
            self.checkpoint_manager.save_progress(
                episode_id, 'entity_resolution', resolved_entities
            )
            
            return resolved_entities
    
    def _create_segment_objects(self, segments: List[Dict[str, Any]], 
                               episode_id: str) -> List[Segment]:
        """Create Segment model objects from segment data.
        
        Args:
            segments: Raw segment data
            episode_id: Episode ID
            
        Returns:
            List of Segment objects
        """
        segment_objects = []
        for i, segment_data in enumerate(segments):
            segment_obj = Segment(
                id=f"{episode_id}_segment_{i}",
                text=segment_data['text'],
                start_time=segment_data['start'],
                end_time=segment_data['end'],
                speaker=segment_data.get('speaker', 'Unknown'),
                segment_index=i
            )
            segment_objects.append(segment_obj)
        return segment_objects
    
    def _detect_themes(self, resolved_entities: List[Any],
                      extraction_result: Dict[str, Any],
                      segment_objects: List[Segment]) -> Dict[str, Any]:
        """Detect emergent themes from entities and segments.
        
        Args:
            resolved_entities: Resolved entities
            extraction_result: Extraction results
            segment_objects: Segment objects
            
        Returns:
            Theme detection results
        """
        with create_span("emergent_theme_detection", attributes={"entities.count": len(resolved_entities)}):
            logger.info("Detecting emergent themes...")
            
            # Build co-occurrence data
            co_occurrences = self._build_co_occurrence_data(segment_objects, resolved_entities)
            
            # Extract explicit topics
            explicit_topics = extraction_result.get('topics', [])
            explicit_topic_names = [topic.get('name', '') for topic in explicit_topics if isinstance(topic, dict)]
            
            # Detect themes
            theme_results = self.emergent_theme_detector.detect_themes(
                entities=resolved_entities,
                insights=extraction_result.get('insights', []),
                segments=segment_objects,
                co_occurrences=co_occurrences,
                explicit_topics=explicit_topic_names
            )
            
            add_span_attributes({
                "themes.detected": len(theme_results.get('themes', [])),
                "themes.meta": len(theme_results.get('hierarchy', {}).get('meta_themes', [])),
                "themes.primary": len(theme_results.get('hierarchy', {}).get('primary_themes', [])),
                "themes.implicit_messages": len(theme_results.get('implicit_messages', []))
            })
            
            return theme_results
    
    def _analyze_episode_flow(self, segment_objects: List[Segment],
                            resolved_entities: List[Any]) -> Dict[str, Any]:
        """Analyze the flow patterns of the episode.
        
        Args:
            segment_objects: Segment objects
            resolved_entities: Resolved entities
            
        Returns:
            Episode flow analysis results
        """
        with create_span("episode_flow_analysis", attributes={"segments.count": len(segment_objects)}):
            logger.info("Analyzing episode flow...")
            
            # Build concept timeline
            concept_timeline = {}
            entity_mentions = self.episode_flow_analyzer._find_entity_mentions(
                segment_objects, 
                resolved_entities
            )
            for entity_id, mentions in entity_mentions.items():
                concept_timeline[entity_id] = mentions
            
            # Run comprehensive flow analysis
            episode_flow = {
                "transitions": self.episode_flow_analyzer.classify_segment_transitions(segment_objects),
                "concept_introductions": self.episode_flow_analyzer.track_concept_introductions(
                    segment_objects, resolved_entities
                ),
                "momentum": self.episode_flow_analyzer.analyze_conversation_momentum(segment_objects),
                "topic_depths": self.episode_flow_analyzer.track_topic_depth(
                    segment_objects, resolved_entities
                ),
                "circular_references": self.episode_flow_analyzer.detect_circular_references(
                    concept_timeline
                ),
                "resolutions": self.episode_flow_analyzer.analyze_concept_resolution(
                    concept_timeline, segment_objects[-5:]  # Last 5 segments
                ),
                "speaker_contributions": self.episode_flow_analyzer.analyze_speaker_contribution_flow(
                    segment_objects
                )
            }
            
            # Generate flow summary
            flow_summary = self.episode_flow_analyzer.generate_episode_flow_summary(episode_flow)
            episode_flow["summary"] = flow_summary
            
            # Add flow data to entities
            self._add_flow_data_to_entities(
                resolved_entities, episode_flow, segment_objects
            )
            
            add_span_attributes({
                "flow.pattern": flow_summary.get("flow_pattern"),
                "flow.coherence": flow_summary.get("narrative_coherence"),
                "flow.transitions": len(episode_flow.get("transitions", [])),
                "flow.circular_refs": len(episode_flow.get("circular_references", []))
            })
            
            return {
                "pattern": flow_summary.get("flow_pattern", "unknown"),
                "key_transitions": flow_summary.get("key_transitions", []),
                "flow_quality": flow_summary.get("narrative_coherence", 0.5)
            }
    
    def _add_flow_data_to_entities(self, entities: List[Any],
                                 episode_flow: Dict[str, Any],
                                 segment_objects: List[Segment]):
        """Add flow data to entities based on episode flow analysis.
        
        Args:
            entities: List of entities to update
            episode_flow: Episode flow analysis results
            segment_objects: Segment objects
        """
        total_segments = len(segment_objects)
        
        for entity in entities:
            if entity.id in episode_flow["concept_introductions"]:
                intro_data = episode_flow["concept_introductions"][entity.id]
                development = self.episode_flow_analyzer.map_concept_development(
                    entity, segment_objects
                )
                
                # Calculate flow position metrics
                intro_position = intro_data["introduction_segment"] / total_segments if total_segments > 0 else 0
                
                # Find peak discussion segment
                peak_segment = 0
                if development.get("phases"):
                    elaboration_phases = [p for p in development["phases"] if p["phase"] == "elaboration"]
                    if elaboration_phases:
                        peak_segment = elaboration_phases[len(elaboration_phases)//2]["segment_index"]
                peak_position = peak_segment / total_segments if total_segments > 0 else intro_position
                
                # Determine resolution status
                resolution_status = "unknown"
                if entity.id in episode_flow["resolutions"]:
                    resolution_status = episode_flow["resolutions"][entity.id]["resolution_type"]
                
                # Add flow data to entity
                entity.flow_data = {
                    "introduction_point": intro_position,
                    "development_duration": len(development.get("phases", [])) * 10.0,
                    "peak_discussion": peak_position,
                    "resolution_status": resolution_status
                }
    
    def _build_co_occurrence_data(self, segments: List[Segment], 
                                entities: List[Any]) -> List[Dict]:
        """Build co-occurrence data for entities appearing in the same segments.
        
        Args:
            segments: List of segment objects
            entities: List of entity objects
            
        Returns:
            List of co-occurrence relationships
        """
        from collections import defaultdict
        
        # Map entities to segments they appear in
        entity_segments = defaultdict(set)
        
        for entity in entities:
            entity_name_lower = entity.name.lower()
            
            for i, segment in enumerate(segments):
                if entity_name_lower in segment.text.lower():
                    entity_segments[entity.id].add(i)
        
        # Build co-occurrence relationships
        co_occurrences = []
        entities_list = list(entities)
        
        for i, entity1 in enumerate(entities_list):
            for j, entity2 in enumerate(entities_list[i+1:], start=i+1):
                # Find shared segments
                shared_segments = entity_segments[entity1.id] & entity_segments[entity2.id]
                
                if shared_segments:
                    co_occurrences.append({
                        "entity1_id": entity1.id,
                        "entity2_id": entity2.id,
                        "weight": len(shared_segments),
                        "shared_segments": list(shared_segments)
                    })
        
        return co_occurrences
    
    def _save_to_graph(self, podcast_config: Dict[str, Any],
                      episode: Dict[str, Any],
                      segments: List[Dict[str, Any]],
                      extraction_result: Dict[str, Any],
                      resolved_entities: List[Any]):
        """Save all data to the knowledge graph.
        
        This method is delegated to the storage coordinator in the full refactor.
        For now, it maintains the existing logic.
        """
        with create_span("graph_storage"):
            logger.info("Saving to knowledge graph...")
            
            # Create podcast node
            self.graph_provider.create_node(
                'Podcast',
                {
                    'id': podcast_config['id'],
                    'name': podcast_config.get('name', podcast_config['id']),
                    'description': podcast_config.get('description', ''),
                    'rss_url': podcast_config.get('rss_url', '')
                }
            )
            
            # Create episode node with flow data
            episode_data = {
                'id': episode['id'],
                'title': episode['title'],
                'description': episode.get('description', ''),
                'published_date': episode.get('published_date', ''),
                'duration': episode.get('duration', ''),
                'audio_url': episode.get('audio_url', '')
            }
            
            # Add episode flow data if available
            if 'episode_flow' in extraction_result:
                episode_flow_data = extraction_result['episode_flow']
                episode_data['discourse_flow_pattern'] = episode_flow_data.get('pattern', 'unknown')
                episode_data['flow_quality'] = episode_flow_data.get('flow_quality', 0.5)
                episode_data['key_transitions_count'] = len(episode_flow_data.get('key_transitions', []))
            
            self.graph_provider.create_node('Episode', episode_data)
            
            # Create relationship
            self.graph_provider.create_relationship(
                ('Podcast', {'id': podcast_config['id']}),
                'HAS_EPISODE',
                ('Episode', {'id': episode['id']}),
                {}
            )
            
            # Continue with saving segments, entities, etc.
            # (Full implementation would be in storage_coordinator)
    
    def _is_episode_completed(self, episode_id: str) -> bool:
        """Check if episode is already completed.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            True if episode is already completed
        """
        if self.checkpoint_manager.is_completed(episode_id):
            logger.info(f"Episode {episode_id} already completed, skipping")
            return True
        return False
    
    def _download_episode_audio(self, episode: Dict[str, Any], podcast_id: str) -> str:
        """Download episode audio file.
        
        Args:
            episode: Episode information
            podcast_id: Podcast identifier
            
        Returns:
            Path to downloaded audio file
            
        Raises:
            PipelineError: If download fails
        """
        audio_path = download_episode_audio(
            episode,
            podcast_id,
            output_dir=getattr(self.config, "audio_dir", "audio_files")
        )
        
        if not audio_path:
            raise PipelineError(f"Failed to download audio for episode {episode['id']}")
            
        return audio_path
    
    def _add_episode_context(self, episode: Dict[str, Any], 
                            podcast_config: Dict[str, Any]) -> None:
        """Add episode context to tracing span.
        
        Args:
            episode: Episode information
            podcast_config: Podcast configuration
        """
        add_span_attributes({
            "episode.id": episode["id"],
            "episode.title": episode["title"],
            "podcast.id": podcast_config["id"],
            "podcast.name": podcast_config.get("name", ""),
        })
    
    def _process_audio_segments(self, audio_path: str, episode_id: str) -> List[Dict[str, Any]]:
        """Process audio into segments.
        
        Args:
            audio_path: Path to audio file
            episode_id: Episode identifier
            
        Returns:
            List of processed segments
        """
        with create_span("segmentation", attributes={"audio.path": audio_path}):
            logger.info("Segmenting audio...")
            segments = self._prepare_segments(audio_path)
            add_span_attributes({"segments.count": len(segments)})
        
        # Save segments checkpoint
        self.checkpoint_manager.save_progress(episode_id, "segments", segments)
        
        return segments
    
    def _extract_knowledge(self, podcast_config: Dict[str, Any],
                          episode: Dict[str, Any],
                          segments: List[Dict[str, Any]],
                          episode_id: str,
                          use_large_context: bool) -> Dict[str, Any]:
        """Extract knowledge from segments based on configured mode.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Processed segments
            episode_id: Episode identifier
            use_large_context: Whether to use large context
            
        Returns:
            Extraction results
        """
        # Determine extraction mode
        extraction_mode = self._determine_extraction_mode()
        
        if extraction_mode == "migration":
            # Handle migration mode - run both extractions
            return self._handle_migration_mode(
                podcast_config, episode, segments, episode_id, use_large_context
            )
        elif extraction_mode == "schemaless":
            # Schemaless extraction
            return self._extract_schemaless(
                podcast_config, episode, segments, episode_id
            )
        else:
            # Fixed schema extraction
            return self._extract_fixed_schema(
                podcast_config, episode, segments, episode_id, use_large_context
            )
    
    def _determine_extraction_mode(self) -> str:
        """Determine which extraction mode to use.
        
        Returns:
            Extraction mode: "fixed", "schemaless", or "migration"
        """
        use_schemaless = getattr(self.config, "use_schemaless_extraction", False)
        migration_mode = getattr(self.config, "migration_mode", False)
        
        if migration_mode:
            return "migration"
        elif use_schemaless:
            return "schemaless"
        else:
            return "fixed"
    
    def _finalize_episode_processing(self, episode_id: str, result: Dict[str, Any]) -> None:
        """Finalize episode processing.
        
        Args:
            episode_id: Episode identifier
            result: Processing results
        """
        # Mark episode as complete
        self.checkpoint_manager.mark_completed(episode_id, result)
        
        # Clean up memory
        cleanup_memory()
        
        # Add result metrics to span
        add_span_attributes({
            "result.segments": result["segments"],
            "result.insights": result.get("insights", 0),
            "result.entities": result.get("entities", 0),
            "result.mode": result.get("mode", "unknown")
        })
    
    def _cleanup_audio_file(self, audio_path: str) -> None:
        """Clean up audio file if configured.
        
        Args:
            audio_path: Path to audio file
        """
        if getattr(self.config, "delete_audio_after_processing", True):
            try:
                os.remove(audio_path)
            except Exception:
                # Silently ignore cleanup failures
                pass
