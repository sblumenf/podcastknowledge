"""
Enhanced entity resolution for meaningful conversation units.

This module extends entity resolution to leverage the larger context and
semantic coherence of meaningful units for better entity disambiguation.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any, Set
import logging
from collections import defaultdict

from src.extraction.entity_resolution import EntityResolver, EntityResolutionConfig, EntityMatch
from src.services.segment_regrouper import MeaningfulUnit
from src.core.monitoring import trace_operation
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UnitEntityContext:
    """Context information for entity resolution within a unit."""
    
    unit_id: str
    unit_type: str
    unit_summary: str
    themes: List[str]
    speaker_context: Dict[str, float]  # Speaker -> percentage
    entity_mentions: Dict[str, List[int]]  # Entity -> segment indices
    co_occurrences: Dict[Tuple[str, str], int]  # Entity pair -> count
    

@dataclass
class CrossUnitEntityInfo:
    """Information about entities across multiple units."""
    
    entity_name: str
    canonical_form: str
    unit_appearances: List[str]  # Unit IDs where entity appears
    total_mentions: int
    context_variations: Dict[str, str]  # Unit ID -> context description
    confidence_scores: Dict[str, float]  # Unit ID -> confidence
    

class MeaningfulUnitEntityResolver:
    """
    Enhanced entity resolver that uses meaningful unit context.
    
    This resolver improves entity resolution by:
    1. Using unit summaries and themes for disambiguation
    2. Tracking entity co-occurrences within semantic units
    3. Resolving pronouns and references within unit boundaries
    4. Building entity profiles across units for better matching
    """
    
    def __init__(self, base_resolver: Optional[EntityResolver] = None):
        """
        Initialize the meaningful unit entity resolver.
        
        Args:
            base_resolver: Base entity resolver to extend
        """
        self.base_resolver = base_resolver or EntityResolver(
            EntityResolutionConfig(
                similarity_threshold=0.8,  # Slightly lower threshold due to better context
                use_aliases=True,
                use_abbreviations=True,
                merge_singular_plural=True
            )
        )
        self.logger = logger
        
        # Unit-level caches
        self.unit_contexts: Dict[str, UnitEntityContext] = {}
        self.cross_unit_entities: Dict[str, CrossUnitEntityInfo] = {}
        
        # Pronoun resolution patterns
        self.pronoun_patterns = {
            'he': 'male_person',
            'she': 'female_person',
            'they': 'person_or_group',
            'it': 'thing_or_concept',
            'this': 'recent_reference',
            'that': 'previous_reference',
            'these': 'multiple_recent',
            'those': 'multiple_previous'
        }
        
    @trace_operation("resolve_unit_entities")
    def resolve_entities_in_unit(
        self,
        unit: MeaningfulUnit,
        raw_entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Resolve entities within a meaningful unit using unit context.
        
        Args:
            unit: The meaningful unit providing context
            raw_entities: Raw extracted entities from the unit
            
        Returns:
            Resolved and deduplicated entities with enhanced metadata
        """
        if not raw_entities:
            return []
            
        self.logger.info(
            f"Resolving {len(raw_entities)} entities in unit {unit.id} "
            f"({unit.unit_type})"
        )
        
        # Build unit context
        context = self._build_unit_context(unit, raw_entities)
        self.unit_contexts[unit.id] = context
        
        # First pass: resolve within unit
        unit_resolved = self._resolve_within_unit(raw_entities, context)
        
        # Second pass: resolve pronouns and references
        reference_resolved = self._resolve_references(unit_resolved, unit, context)
        
        # Third pass: apply cross-unit knowledge if available
        final_resolved = self._apply_cross_unit_resolution(reference_resolved, unit)
        
        # Update cross-unit entity tracking
        self._update_cross_unit_tracking(final_resolved, unit)
        
        self.logger.info(
            f"Resolved {len(raw_entities)} entities to {len(final_resolved)} "
            f"in unit {unit.id}"
        )
        
        return final_resolved
    
    def _build_unit_context(
        self,
        unit: MeaningfulUnit,
        entities: List[Dict[str, Any]]
    ) -> UnitEntityContext:
        """Build context information for the unit."""
        # Track entity mentions by segment
        entity_mentions = defaultdict(list)
        for i, segment in enumerate(unit.segments):
            segment_text = segment.text.lower()
            for entity in entities:
                entity_name = entity.get('value', '').lower()
                if entity_name in segment_text:
                    entity_mentions[entity_name].append(i)
        
        # Calculate co-occurrences
        co_occurrences = defaultdict(int)
        entity_names = [e.get('value', '').lower() for e in entities]
        
        for i in range(len(entity_names)):
            for j in range(i + 1, len(entity_names)):
                name1, name2 = entity_names[i], entity_names[j]
                # Count segments where both appear
                segments1 = set(entity_mentions.get(name1, []))
                segments2 = set(entity_mentions.get(name2, []))
                common_segments = segments1 & segments2
                if common_segments:
                    co_occurrences[(name1, name2)] = len(common_segments)
        
        return UnitEntityContext(
            unit_id=unit.id,
            unit_type=unit.unit_type,
            unit_summary=unit.summary,
            themes=unit.themes,
            speaker_context=unit.speaker_distribution,
            entity_mentions=dict(entity_mentions),
            co_occurrences=dict(co_occurrences)
        )
    
    def _resolve_within_unit(
        self,
        entities: List[Dict[str, Any]],
        context: UnitEntityContext
    ) -> List[Dict[str, Any]]:
        """Resolve entities within the unit using context."""
        # Group entities by type for better resolution
        entities_by_type = defaultdict(list)
        for entity in entities:
            entity_type = entity.get('type', 'UNKNOWN')
            entities_by_type[entity_type].append(entity)
        
        resolved = []
        
        # Resolve each type group
        for entity_type, typed_entities in entities_by_type.items():
            # Use base resolver with context hints
            resolution_result = self.base_resolver.resolve_entities(typed_entities)
            
            if isinstance(resolution_result, dict):
                resolved_entities = resolution_result.get('resolved_entities', [])
            else:
                resolved_entities = resolution_result
            
            # Enhance with unit context
            for entity in resolved_entities:
                self._enhance_entity_with_context(entity, context)
            
            resolved.extend(resolved_entities)
        
        return resolved
    
    def _enhance_entity_with_context(
        self,
        entity: Dict[str, Any],
        context: UnitEntityContext
    ) -> None:
        """Enhance entity metadata with unit context."""
        entity_name = entity.get('value', '').lower()
        
        # Add unit context
        if 'unit_context' not in entity:
            entity['unit_context'] = {}
        
        entity['unit_context'].update({
            'unit_id': context.unit_id,
            'unit_type': context.unit_type,
            'relevance_to_unit': self._calculate_entity_relevance(entity_name, context),
            'mention_segments': context.entity_mentions.get(entity_name, []),
            'themes_related': [t for t in context.themes if entity_name in t.lower()]
        })
        
        # Add importance score based on context
        if 'importance' not in entity:
            entity['importance'] = self._calculate_entity_importance(entity, context)
    
    def _calculate_entity_relevance(
        self,
        entity_name: str,
        context: UnitEntityContext
    ) -> float:
        """Calculate how relevant an entity is to the unit."""
        relevance = 0.5  # Base relevance
        
        # Check if mentioned in unit summary
        if entity_name in context.unit_summary.lower():
            relevance += 0.3
        
        # Check theme relevance
        for theme in context.themes:
            if entity_name in theme.lower():
                relevance += 0.2
                break
        
        # Check mention frequency
        mentions = len(context.entity_mentions.get(entity_name, []))
        if mentions > 3:
            relevance += 0.2
        elif mentions > 1:
            relevance += 0.1
        
        return min(relevance, 1.0)
    
    def _calculate_entity_importance(
        self,
        entity: Dict[str, Any],
        context: UnitEntityContext
    ) -> float:
        """Calculate entity importance within the unit."""
        entity_name = entity.get('value', '').lower()
        importance = 0.5
        
        # Frequency factor
        mentions = len(context.entity_mentions.get(entity_name, []))
        importance += min(mentions * 0.1, 0.3)
        
        # Co-occurrence factor
        co_occurrence_count = sum(
            count for (e1, e2), count in context.co_occurrences.items()
            if e1 == entity_name or e2 == entity_name
        )
        importance += min(co_occurrence_count * 0.05, 0.2)
        
        # Unit type factor
        if context.unit_type in ['topic_discussion', 'key_point']:
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _resolve_references(
        self,
        entities: List[Dict[str, Any]],
        unit: MeaningfulUnit,
        context: UnitEntityContext
    ) -> List[Dict[str, Any]]:
        """Resolve pronouns and references within the unit."""
        resolved = entities.copy()
        
        # Build entity position map
        entity_positions = self._build_entity_position_map(entities, unit)
        
        # Look for references in segments
        for i, segment in enumerate(unit.segments):
            text = segment.text.lower()
            
            # Check for pronouns
            for pronoun, pronoun_type in self.pronoun_patterns.items():
                if f" {pronoun} " in f" {text} ":
                    # Find the most likely antecedent
                    antecedent = self._find_antecedent(
                        pronoun, pronoun_type, i, entity_positions, context
                    )
                    
                    if antecedent:
                        # Create reference annotation
                        self._add_reference_annotation(
                            resolved, antecedent, segment, pronoun
                        )
        
        return resolved
    
    def _build_entity_position_map(
        self,
        entities: List[Dict[str, Any]],
        unit: MeaningfulUnit
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Map segment indices to entities mentioned."""
        position_map = defaultdict(list)
        
        for entity in entities:
            entity_name = entity.get('value', '').lower()
            for i, segment in enumerate(unit.segments):
                if entity_name in segment.text.lower():
                    position_map[i].append(entity)
        
        return dict(position_map)
    
    def _find_antecedent(
        self,
        pronoun: str,
        pronoun_type: str,
        segment_idx: int,
        entity_positions: Dict[int, List[Dict[str, Any]]],
        context: UnitEntityContext
    ) -> Optional[Dict[str, Any]]:
        """Find the most likely antecedent for a pronoun."""
        # Look backwards from current segment
        for i in range(segment_idx - 1, max(segment_idx - 5, -1), -1):
            if i in entity_positions:
                candidates = entity_positions[i]
                
                # Filter by pronoun type
                if pronoun_type in ['male_person', 'female_person']:
                    candidates = [
                        e for e in candidates 
                        if e.get('type', '').upper() == 'PERSON'
                    ]
                elif pronoun_type == 'thing_or_concept':
                    candidates = [
                        e for e in candidates 
                        if e.get('type', '').upper() not in ['PERSON', 'ORGANIZATION']
                    ]
                
                if candidates:
                    # Return most recent matching entity
                    return candidates[0]
        
        return None
    
    def _add_reference_annotation(
        self,
        entities: List[Dict[str, Any]],
        antecedent: Dict[str, Any],
        segment: Any,
        pronoun: str
    ) -> None:
        """Add reference annotation to entity."""
        # Find the antecedent in entities list
        for entity in entities:
            if entity.get('value') == antecedent.get('value'):
                if 'references' not in entity:
                    entity['references'] = []
                
                entity['references'].append({
                    'segment_id': segment.id,
                    'pronoun': pronoun,
                    'confidence': 0.8
                })
                break
    
    def _apply_cross_unit_resolution(
        self,
        entities: List[Dict[str, Any]],
        unit: MeaningfulUnit
    ) -> List[Dict[str, Any]]:
        """Apply knowledge from other units to improve resolution."""
        resolved = []
        
        for entity in entities:
            entity_name = entity.get('value', '')
            
            # Check if we've seen this entity in other units
            canonical_form = self._find_canonical_form(entity_name)
            
            if canonical_form and canonical_form != entity_name:
                # Update to canonical form
                entity['canonical_name'] = canonical_form
                entity['aliases'] = entity.get('aliases', [])
                if entity_name not in entity['aliases']:
                    entity['aliases'].append(entity_name)
                entity['value'] = canonical_form
            
            resolved.append(entity)
        
        return resolved
    
    def _find_canonical_form(self, entity_name: str) -> Optional[str]:
        """Find the canonical form of an entity from cross-unit tracking."""
        for canonical_name, info in self.cross_unit_entities.items():
            # Check exact match
            if entity_name.lower() == canonical_name.lower():
                return info.canonical_form
            
            # Check aliases
            normalized_name = self.base_resolver.normalize_entity_name(entity_name)
            normalized_canonical = self.base_resolver.normalize_entity_name(canonical_name)
            
            if normalized_name == normalized_canonical:
                return info.canonical_form
        
        return None
    
    def _update_cross_unit_tracking(
        self,
        entities: List[Dict[str, Any]],
        unit: MeaningfulUnit
    ) -> None:
        """Update cross-unit entity tracking with new information."""
        for entity in entities:
            entity_name = entity.get('value', '')
            canonical = entity.get('canonical_name', entity_name)
            
            if canonical not in self.cross_unit_entities:
                self.cross_unit_entities[canonical] = CrossUnitEntityInfo(
                    entity_name=entity_name,
                    canonical_form=canonical,
                    unit_appearances=[],
                    total_mentions=0,
                    context_variations={},
                    confidence_scores={}
                )
            
            info = self.cross_unit_entities[canonical]
            
            # Update appearances
            if unit.id not in info.unit_appearances:
                info.unit_appearances.append(unit.id)
            
            # Update mentions
            mentions = len(entity.get('unit_context', {}).get('mention_segments', []))
            info.total_mentions += mentions
            
            # Update context
            info.context_variations[unit.id] = unit.summary[:100]
            info.confidence_scores[unit.id] = entity.get('confidence', 0.8)
    
    @trace_operation("resolve_across_units")
    def resolve_entities_across_units(
        self,
        unit_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Resolve entities across multiple units for global consistency.
        
        Args:
            unit_results: List of entity extraction results from units
            
        Returns:
            Global resolution results with cross-unit entity mapping
        """
        self.logger.info(f"Resolving entities across {len(unit_results)} units")
        
        # Collect all entities with unit context
        all_entities = []
        for result in unit_results:
            unit_id = result.get('unit_id', '')
            entities = result.get('entities', [])
            
            for entity in entities:
                entity['source_unit'] = unit_id
                all_entities.append(entity)
        
        # Group by potential matches
        entity_clusters = self._cluster_cross_unit_entities(all_entities)
        
        # Resolve each cluster to canonical form
        canonical_entities = []
        entity_mapping = {}
        
        for cluster in entity_clusters:
            canonical = self._resolve_entity_cluster(cluster)
            canonical_entities.append(canonical)
            
            # Create mapping
            for entity in cluster:
                source_key = f"{entity['source_unit']}:{entity.get('value', '')}"
                entity_mapping[source_key] = canonical['value']
        
        # Build final cross-unit summary
        cross_unit_summary = self._build_cross_unit_summary(canonical_entities)
        
        return {
            'canonical_entities': canonical_entities,
            'entity_mapping': entity_mapping,
            'cross_unit_summary': cross_unit_summary,
            'total_original': len(all_entities),
            'total_canonical': len(canonical_entities),
            'reduction_ratio': 1 - (len(canonical_entities) / max(1, len(all_entities)))
        }
    
    def _cluster_cross_unit_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Cluster entities that likely refer to the same real-world entity."""
        clusters = []
        clustered = set()
        
        for i, entity1 in enumerate(entities):
            if i in clustered:
                continue
                
            cluster = [entity1]
            clustered.add(i)
            
            for j, entity2 in enumerate(entities[i + 1:], i + 1):
                if j in clustered:
                    continue
                
                # Check if same type
                if entity1.get('type') != entity2.get('type'):
                    continue
                
                # Check similarity
                similarity = self.base_resolver.calculate_name_similarity(
                    entity1.get('value', ''),
                    entity2.get('value', '')
                )
                
                if similarity >= 0.8:
                    cluster.append(entity2)
                    clustered.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def _resolve_entity_cluster(
        self,
        cluster: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Resolve a cluster of entities to a canonical form."""
        if len(cluster) == 1:
            return cluster[0].copy()
        
        # Sort by total mentions and confidence
        sorted_cluster = sorted(
            cluster,
            key=lambda e: (
                self.cross_unit_entities.get(e.get('value', ''), 
                    CrossUnitEntityInfo('', '', [], 0, {}, {})).total_mentions,
                e.get('confidence', 0)
            ),
            reverse=True
        )
        
        # Use the most mentioned/confident as canonical
        canonical = sorted_cluster[0].copy()
        
        # Merge information from all instances
        all_units = []
        all_themes = set()
        total_mentions = 0
        
        for entity in cluster:
            source_unit = entity.get('source_unit', '')
            if source_unit:
                all_units.append(source_unit)
            
            # Collect themes
            unit_context = entity.get('unit_context', {})
            themes = unit_context.get('themes_related', [])
            all_themes.update(themes)
            
            # Sum mentions
            mention_segments = unit_context.get('mention_segments', [])
            total_mentions += len(mention_segments)
        
        # Update canonical entity
        canonical['appears_in_units'] = all_units
        canonical['cross_unit_themes'] = list(all_themes)
        canonical['total_mentions_global'] = total_mentions
        canonical['variant_count'] = len(cluster)
        
        return canonical
    
    def _build_cross_unit_summary(
        self,
        canonical_entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a summary of cross-unit entity patterns."""
        # Analyze entity distribution
        entity_distribution = defaultdict(int)
        theme_connections = defaultdict(set)
        
        for entity in canonical_entities:
            # Count by type
            entity_type = entity.get('type', 'UNKNOWN')
            entity_distribution[entity_type] += 1
            
            # Track theme connections
            for theme in entity.get('cross_unit_themes', []):
                theme_connections[theme].add(entity.get('value', ''))
        
        # Find most connected entities
        most_connected = sorted(
            canonical_entities,
            key=lambda e: len(e.get('appears_in_units', [])),
            reverse=True
        )[:10]
        
        return {
            'entity_type_distribution': dict(entity_distribution),
            'theme_entity_connections': {
                theme: list(entities) 
                for theme, entities in theme_connections.items()
            },
            'most_connected_entities': [
                {
                    'name': e.get('value', ''),
                    'type': e.get('type', ''),
                    'unit_count': len(e.get('appears_in_units', [])),
                    'themes': e.get('cross_unit_themes', [])
                }
                for e in most_connected
            ],
            'total_themes_covered': len(theme_connections)
        }