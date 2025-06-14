"""
Semantic pipeline executor for meaningful unit processing.

This executor replaces segment-by-segment processing with semantic unit processing,
providing better context understanding and knowledge extraction.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import time

from src.core.exceptions import PipelineError
from src.core.interfaces import TranscriptSegment
from src.core.models import Podcast, Episode, Segment
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.segment_regrouper import SegmentRegrouper
from src.services.performance_optimizer import PerformanceOptimizer
from src.extraction.meaningful_unit_extractor import MeaningfulUnitExtractor
from src.extraction.meaningful_unit_entity_resolver import MeaningfulUnitEntityResolver
from src.extraction.meaningful_unit_prompts import MeaningfulUnitPromptBuilder
from src.core.monitoring import trace_operation
from src.utils.log_utils import get_logger
from src.utils.memory import cleanup_memory

logger = get_logger(__name__)


class SemanticPipelineExecutor:
    """
    Pipeline executor that processes transcripts using semantic segmentation.
    
    This executor:
    1. Analyzes conversation structure
    2. Regroups segments into meaningful units
    3. Extracts knowledge with better context
    4. Stores enhanced results including conversation structure
    """
    
    def __init__(
        self,
        config,
        provider_coordinator,
        checkpoint_manager,
        storage_coordinator=None
    ):
        """
        Initialize semantic pipeline executor.
        
        Args:
            config: Pipeline configuration
            provider_coordinator: Provider coordinator instance
            checkpoint_manager: Checkpoint manager instance
            storage_coordinator: Storage coordinator instance (optional)
        """
        self.config = config
        self.provider_coordinator = provider_coordinator
        self.checkpoint_manager = checkpoint_manager
        self.storage_coordinator = storage_coordinator
        
        # Get base services
        self.llm_service = provider_coordinator.llm_service
        self.graph_service = provider_coordinator.graph_service
        self.embedding_service = provider_coordinator.embedding_service
        
        # Initialize performance optimizer
        self.optimizer = PerformanceOptimizer(cache_ttl_minutes=60)
        
        # Initialize semantic processing components with optimizer
        self.conversation_analyzer = ConversationAnalyzer(self.llm_service, self.optimizer)
        self.segment_regrouper = SegmentRegrouper()
        
        # Initialize enhanced extraction components with optimizer
        base_extractor = provider_coordinator.knowledge_extractor
        self.unit_extractor = MeaningfulUnitExtractor(base_extractor, performance_optimizer=self.optimizer)
        
        base_resolver = provider_coordinator.entity_resolver
        self.unit_entity_resolver = MeaningfulUnitEntityResolver(base_resolver)
        
        self.prompt_builder = MeaningfulUnitPromptBuilder()
        
        self.logger = logger
        
    @trace_operation("process_vtt_semantic")
    def process_vtt_segments(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        segments: List[TranscriptSegment],
        use_large_context: bool = True
    ) -> Dict[str, Any]:
        """
        Process VTT segments using semantic segmentation.
        
        Args:
            podcast_config: Podcast configuration
            episode: Episode information
            segments: Pre-parsed VTT segments
            use_large_context: Whether to use large context models
            
        Returns:
            Processing results with extracted knowledge and structure
        """
        episode_id = episode['id']
        start_time = time.time()
        
        self.logger.info(
            f"Processing {len(segments)} VTT segments semantically for episode: "
            f"{episode['title']} (ID: {episode_id})"
        )
        
        # Check if already completed
        if self._is_episode_completed(episode_id):
            self.logger.info(f"Episode {episode_id} already completed, skipping")
            return {'status': 'already_completed'}
        
        # Create processing benchmark
        benchmark = self.optimizer.create_processing_benchmark()
        benchmark.set_operation_name(f"semantic_processing_{episode_id}")
        
        try:
            with benchmark:
                # Phase 1: Analyze conversation structure
                self.logger.info("Phase 1: Analyzing conversation structure...")
                conversation_structure = self.conversation_analyzer.analyze_structure(segments)
                benchmark.checkpoint("conversation_analysis")
                
                # Save structure checkpoint
                self.checkpoint_manager.save_progress(
                    episode_id, 
                    "conversation_structure", 
                    conversation_structure
                )
                
                # Phase 2: Regroup segments into meaningful units
                self.logger.info("Phase 2: Regrouping segments into meaningful units...")
                meaningful_units = self.segment_regrouper.regroup_segments(
                    segments, 
                    conversation_structure
                )
                benchmark.checkpoint("segment_regrouping")
                
                self.logger.info(
                    f"Created {len(meaningful_units)} meaningful units from "
                    f"{len(segments)} segments"
                )
                
                # Save units checkpoint
                self.checkpoint_manager.save_progress(
                    episode_id,
                    "meaningful_units",
                    meaningful_units
                )
                
                # Optimize memory before extraction
                self.optimizer.optimize_memory_usage()
                
                # Phase 3: Extract knowledge from meaningful units
                self.logger.info("Phase 3: Extracting knowledge from meaningful units...")
                extraction_results = self._extract_from_units(
                    meaningful_units,
                    episode,
                    podcast_config
                )
                benchmark.checkpoint("knowledge_extraction")
                
                # Phase 4: Resolve entities across units
                self.logger.info("Phase 4: Resolving entities across units...")
                resolution_results = self.unit_entity_resolver.resolve_entities_across_units(
                    extraction_results
                )
                benchmark.checkpoint("entity_resolution")
                
                # Phase 5: Store to graph database
                self.logger.info("Phase 5: Storing enhanced knowledge to graph...")
                storage_result = self._store_semantic_knowledge(
                    podcast_config,
                    episode,
                    conversation_structure,
                    meaningful_units,
                    extraction_results,
                    resolution_results
                )
                benchmark.checkpoint("graph_storage")
                
                # Build final result
                processing_time = time.time() - start_time
                result = self._build_processing_result(
                    segments,
                    meaningful_units,
                    extraction_results,
                    resolution_results,
                    processing_time
                )
                
                # Add performance metrics to result
                result['performance_metrics'] = self.optimizer.get_performance_summary()
                
                # Finalize processing
                self._finalize_episode_processing(episode_id, result)
                
                return result
            
        except Exception as e:
            self.logger.error(
                f"Error in semantic processing for episode {episode_id}: {e}",
                exc_info=True
            )
            raise PipelineError(f"Semantic processing failed: {e}")
    
    def _extract_from_units(
        self,
        meaningful_units,
        episode: Dict[str, Any],
        podcast_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract knowledge from meaningful units with batch optimization."""
        episode_metadata = {
            'id': episode['id'],
            'title': episode['title'],
            'description': episode.get('description', ''),
            'podcast_name': podcast_config.get('name', podcast_config['id']),
            'podcast_id': podcast_config['id']
        }
        
        # Optimize unit processing into groups
        unit_groups = self.optimizer.optimize_unit_processing(meaningful_units)
        self.logger.info(f"Processing {len(meaningful_units)} units in {len(unit_groups)} groups")
        
        extraction_results = []
        
        # Process each group
        for group_idx, unit_group in enumerate(unit_groups):
            self.logger.debug(f"Processing group {group_idx + 1}/{len(unit_groups)} with {len(unit_group)} units")
            
            # Define processing function for batch
            def process_unit(unit):
                try:
                    # Extract knowledge from unit
                    unit_result = self.unit_extractor.extract_from_unit(
                        unit,
                        episode_metadata
                    )
                    
                    # Resolve entities within unit
                    resolved_entities = self.unit_entity_resolver.resolve_entities_in_unit(
                        unit,
                        unit_result.entities
                    )
                    
                    # Update result with resolved entities
                    unit_result.entities = resolved_entities
                    
                    return {
                        'unit_id': unit.id,
                        'entities': unit_result.entities,
                        'insights': unit_result.insights,
                        'quotes': unit_result.quotes,
                        'relationships': unit_result.relationships,
                        'themes': unit_result.themes,
                        'metadata': unit_result.metadata
                    }
                except Exception as e:
                    self.logger.warning(f"Failed to extract from unit {unit.id}: {e}")
                    return None
            
            # Process units in the group
            group_results = self.optimizer.batch_llm_calls(
                unit_group,
                process_unit,
                batch_size=3,
                llm_service=self.llm_service
            )
            
            # Add successful results
            extraction_results.extend([r for r in group_results if r is not None])
            
            # Check memory usage between groups
            memory_stats = self.optimizer.optimize_memory_usage()
            if memory_stats['warning']:
                self.logger.warning("High memory usage detected during extraction, optimizing...")
        
        self.logger.info(f"Successfully extracted knowledge from {len(extraction_results)} units")
        return extraction_results
    
    def _store_semantic_knowledge(
        self,
        podcast_config: Dict[str, Any],
        episode: Dict[str, Any],
        conversation_structure,
        meaningful_units,
        extraction_results,
        resolution_results
    ) -> Dict[str, Any]:
        """Store semantic knowledge and structure to graph database."""
        try:
            # Create podcast node
            podcast_data = {
                'id': podcast_config['id'],
                'name': podcast_config.get('name', podcast_config['id']),
                'description': podcast_config.get('description', ''),
                'type': 'Podcast'
            }
            self.graph_service.create_node('Podcast', podcast_data)
            
            # Create enhanced episode node with structure info
            episode_data = {
                'id': episode['id'],
                'title': episode['title'],
                'description': episode.get('description', ''),
                'published_date': episode.get('published_date', ''),
                'duration_minutes': episode.get('duration', 0),
                
                # Semantic processing metadata
                'processing_type': 'semantic',
                'total_segments': conversation_structure.total_segments,
                'meaningful_units': len(meaningful_units),
                'conversation_themes': [t.name for t in conversation_structure.themes],
                'narrative_arc': conversation_structure.flow.narrative_arc,
                'coherence_score': conversation_structure.flow.coherence_score,
                
                # Extraction counts
                'entity_count': resolution_results['total_canonical'],
                'insight_count': sum(len(r['insights']) for r in extraction_results),
                'quote_count': sum(len(r['quotes']) for r in extraction_results),
                
                'type': 'Episode'
            }
            self.graph_service.create_node('Episode', episode_data)
            
            # Link podcast to episode
            self.graph_service.create_relationship(
                podcast_config['id'],
                episode['id'],
                'HAS_EPISODE',
                {'processed_semantically': True}
            )
            
            # Store conversation structure
            self._store_conversation_structure(
                episode['id'],
                conversation_structure,
                meaningful_units
            )
            
            # Store canonical entities
            self._store_canonical_entities(
                episode['id'],
                resolution_results['canonical_entities']
            )
            
            # Store insights and quotes by unit
            self._store_unit_knowledge(
                episode['id'],
                extraction_results,
                meaningful_units
            )
            
            # Store cross-unit relationships
            self._store_cross_unit_relationships(
                episode['id'],
                resolution_results
            )
            
            return {
                'stored_entities': len(resolution_results['canonical_entities']),
                'stored_units': len(meaningful_units),
                'stored_themes': len(conversation_structure.themes)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to store semantic knowledge: {e}")
            return {'error': str(e)}
    
    def _store_conversation_structure(
        self,
        episode_id: str,
        structure,
        units
    ):
        """Store conversation structure nodes and relationships."""
        # Create ConversationStructure node
        structure_data = {
            'id': f"{episode_id}_structure",
            'episode_id': episode_id,
            'total_segments': structure.total_segments,
            'unit_count': len(units),
            'narrative_arc': structure.flow.narrative_arc,
            'pacing': structure.flow.pacing,
            'coherence_score': structure.flow.coherence_score,
            'type': 'ConversationStructure'
        }
        self.graph_service.create_node('ConversationStructure', structure_data)
        
        # Link to episode
        self.graph_service.create_relationship(
            episode_id,
            structure_data['id'],
            'HAS_STRUCTURE',
            {}
        )
        
        # Store themes
        for theme in structure.themes:
            theme_data = {
                'id': f"{episode_id}_theme_{theme.name.replace(' ', '_')}",
                'name': theme.name,
                'description': theme.description,
                'episode_id': episode_id,
                'type': 'Theme'
            }
            self.graph_service.create_node('Theme', theme_data)
            
            # Link to structure
            self.graph_service.create_relationship(
                structure_data['id'],
                theme_data['id'],
                'CONTAINS_THEME',
                {'related_units': len(theme.related_units)}
            )
        
        # Store meaningful units
        for unit in units:
            unit_data = {
                'id': f"{episode_id}_{unit.id}",
                'unit_id': unit.id,
                'unit_type': unit.unit_type,
                'summary': unit.summary,
                'start_time': unit.start_time,
                'end_time': unit.end_time,
                'duration': unit.duration,
                'segment_count': unit.segment_count,
                'is_complete': unit.is_complete,
                'episode_id': episode_id,
                'type': 'MeaningfulUnit'
            }
            self.graph_service.create_node('MeaningfulUnit', unit_data)
            
            # Link to structure
            self.graph_service.create_relationship(
                structure_data['id'],
                unit_data['id'],
                'CONTAINS_UNIT',
                {'position': unit.metadata.get('original_indices', {}).get('start', 0)}
            )
            
            # Link unit to themes
            for theme_name in unit.themes:
                theme_id = f"{episode_id}_theme_{theme_name.replace(' ', '_')}"
                self.graph_service.create_relationship(
                    unit_data['id'],
                    theme_id,
                    'EXPLORES_THEME',
                    {}
                )
    
    def _store_canonical_entities(
        self,
        episode_id: str,
        canonical_entities: List[Dict[str, Any]]
    ):
        """Store canonical entities with cross-unit information."""
        for entity in canonical_entities:
            entity_data = {
                'id': f"{episode_id}_entity_{hash(entity['value'])}",
                'name': entity['value'],
                'type': entity['type'],
                'canonical_name': entity.get('canonical_name', entity['value']),
                'appears_in_units': len(entity.get('appears_in_units', [])),
                'total_mentions': entity.get('total_mentions_global', 1),
                'confidence': entity.get('confidence', 0.8),
                'episode_id': episode_id
            }
            
            # Add aliases if present
            if 'aliases' in entity:
                entity_data['aliases'] = entity['aliases']
            
            self.graph_service.create_node(entity['type'], entity_data)
            
            # Link to episode
            self.graph_service.create_relationship(
                episode_id,
                entity_data['id'],
                'MENTIONS',
                {
                    'frequency': entity.get('total_mentions_global', 1),
                    'unit_count': len(entity.get('appears_in_units', []))
                }
            )
    
    def _store_unit_knowledge(
        self,
        episode_id: str,
        extraction_results: List[Dict[str, Any]],
        units
    ):
        """Store insights and quotes organized by meaningful units."""
        unit_map = {unit.id: unit for unit in units}
        
        for result in extraction_results:
            unit_id = result['unit_id']
            unit = unit_map.get(unit_id)
            
            if not unit:
                continue
            
            unit_node_id = f"{episode_id}_{unit_id}"
            
            # Store insights
            for insight in result['insights']:
                insight_data = {
                    'id': f"{episode_id}_insight_{hash(insight['content'])}",
                    'content': insight['content'],
                    'type': insight['type'],
                    'confidence': insight.get('confidence', 0.7),
                    'unit_id': unit_id,
                    'episode_id': episode_id
                }
                self.graph_service.create_node('Insight', insight_data)
                
                # Link to unit
                self.graph_service.create_relationship(
                    unit_node_id,
                    insight_data['id'],
                    'CONTAINS_INSIGHT',
                    {'position_in_unit': insight['order'] if 'order' in insight else 0}
                )
            
            # Store quotes
            for quote in result['quotes']:
                quote_data = {
                    'id': f"{episode_id}_quote_{hash(quote['value'])}",
                    'text': quote['value'],
                    'speaker': quote.get('speaker', 'Unknown'),
                    'quote_type': quote.get('quote_type', 'general'),
                    'importance_score': quote.get('importance_score', 0.5),
                    'unit_id': unit_id,
                    'unit_context': unit.summary,
                    'episode_id': episode_id
                }
                self.graph_service.create_node('Quote', quote_data)
                
                # Link to unit
                self.graph_service.create_relationship(
                    unit_node_id,
                    quote_data['id'],
                    'CONTAINS_QUOTE',
                    {'importance': quote.get('importance_score', 0.5)}
                )
    
    def _store_cross_unit_relationships(
        self,
        episode_id: str,
        resolution_results: Dict[str, Any]
    ):
        """Store relationships that span across units."""
        # Store entity mapping for reference
        mapping_data = {
            'id': f"{episode_id}_entity_mapping",
            'episode_id': episode_id,
            'mapping': resolution_results['entity_mapping'],
            'reduction_ratio': resolution_results['reduction_ratio'],
            'type': 'EntityMapping'
        }
        self.graph_service.create_node('EntityMapping', mapping_data)
        
        # Link to episode
        self.graph_service.create_relationship(
            episode_id,
            mapping_data['id'],
            'HAS_ENTITY_MAPPING',
            {}
        )
        
        # Store cross-unit entity connections
        summary = resolution_results.get('cross_unit_summary', {})
        for theme, entities in summary.get('theme_entity_connections', {}).items():
            theme_id = f"{episode_id}_theme_{theme.replace(' ', '_')}"
            
            for entity_name in entities:
                # Find entity node
                entity_results = self.graph_service.query(
                    "MATCH (e) WHERE e.name = $name AND e.episode_id = $episode_id RETURN e",
                    {'name': entity_name, 'episode_id': episode_id}
                )
                
                if entity_results:
                    entity_node = entity_results[0]['e']
                    self.graph_service.create_relationship(
                        theme_id,
                        entity_node['id'],
                        'CONNECTED_TO',
                        {}
                    )
    
    def _build_processing_result(
        self,
        segments,
        meaningful_units,
        extraction_results,
        resolution_results,
        processing_time
    ) -> Dict[str, Any]:
        """Build comprehensive processing result."""
        # Calculate totals
        total_entities = resolution_results['total_canonical']
        total_insights = sum(len(r['insights']) for r in extraction_results)
        total_quotes = sum(len(r['quotes']) for r in extraction_results)
        total_relationships = sum(len(r['relationships']) for r in extraction_results)
        
        # Get unit statistics
        unit_stats = self.segment_regrouper.get_unit_statistics(meaningful_units)
        
        return {
            'status': 'success',
            'processing_type': 'semantic',
            'processing_time': processing_time,
            
            # Segment info
            'total_segments': len(segments),
            'meaningful_units': len(meaningful_units),
            'unit_statistics': unit_stats,
            
            # Extraction results
            'entities': total_entities,
            'insights': total_insights,
            'quotes': total_quotes,
            'relationships': total_relationships,
            
            # Entity resolution
            'entity_reduction_ratio': resolution_results['reduction_ratio'],
            'cross_unit_patterns': resolution_results.get('cross_unit_summary', {}),
            
            # Metadata
            'extraction_metadata': {
                'total_text_length': sum(len(s.text) for s in segments),
                'average_unit_duration': unit_stats.get('average_duration', 0),
                'completeness_rate': unit_stats.get('completeness_rate', 0),
                'processing_timestamp': datetime.now().isoformat()
            }
        }
    
    def _is_episode_completed(self, episode_id: str) -> bool:
        """Check if episode is already completed."""
        return self.checkpoint_manager.is_completed(episode_id)
    
    def _finalize_episode_processing(self, episode_id: str, result: Dict[str, Any]):
        """Finalize episode processing."""
        # Mark as complete
        self.checkpoint_manager.mark_completed(episode_id, result)
        
        # Clean up memory
        cleanup_memory()
        
        self.logger.info(
            f"Episode {episode_id} semantic processing completed: "
            f"{result.get('meaningful_units', 0)} units, "
            f"{result.get('entities', 0)} entities, "
            f"{result.get('insights', 0)} insights"
        )