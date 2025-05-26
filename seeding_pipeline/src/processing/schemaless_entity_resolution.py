"""
Custom entity resolution component for schemaless extraction.

This module handles post-processing entity resolution to merge duplicates,
identify aliases, and generate canonical names for entities extracted by SimpleKGPipeline.

JUSTIFICATION: SimpleKGPipeline extracts entities as they appear in text without:
- Recognizing that "AI" and "Artificial Intelligence" refer to the same concept
- Merging entities with different capitalizations ("Google" vs "google")
- Tracking entity occurrences across segments
- Generating consistent canonical names

EVIDENCE: Phase 1 testing showed SimpleKGPipeline creates separate entities for
variations of the same concept, leading to fragmented knowledge graphs.

REMOVAL CRITERIA: This component can be removed if SimpleKGPipeline adds:
- Built-in entity resolution and deduplication
- Alias recognition and management
- Cross-segment entity tracking
- Canonical name generation

THRESHOLD: If entity resolution reduces unique entities by less than 5%, consider removal.
"""

import re
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging
from difflib import SequenceMatcher

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker

logger = logging.getLogger(__name__)


@dataclass
class EntityResolutionConfig:
    """Configuration for entity resolution."""
    similarity_threshold: float = 0.85  # Threshold for considering entities similar
    case_sensitive: bool = False  # Whether to consider case in matching
    use_aliases: bool = True  # Whether to use alias rules
    use_abbreviations: bool = True  # Whether to expand abbreviations
    merge_singular_plural: bool = True  # Whether to merge singular/plural forms
    preview_mode: bool = False  # Show merges without applying
    max_merge_distance: int = 3  # Max edit distance for fuzzy matching
    confidence_weight: bool = True  # Weight merges by entity confidence


@dataclass
class EntityMatch:
    """Represents a potential entity match."""
    entity1: Dict[str, Any]
    entity2: Dict[str, Any]
    similarity_score: float
    match_type: str  # 'exact', 'case', 'alias', 'fuzzy', 'abbreviation'
    confidence: float


class SchemalessEntityResolver:
    """
    Resolves and merges duplicate entities from schemaless extraction.
    
    This class identifies entities that refer to the same concept and merges them,
    preserving all properties while creating canonical representations.
    """
    
    def __init__(self, config: Optional[EntityResolutionConfig] = None):
        """Initialize the entity resolver with configuration."""
        self.config = config or EntityResolutionConfig()
        self.alias_rules = self._load_alias_rules()
        self.abbreviation_map = self._load_abbreviations()
        self.resolution_metrics = {
            "entities_before": 0,
            "entities_after": 0,
            "merges_performed": 0,
            "merge_types": defaultdict(int)
        }
    
    @track_component_impact("entity_resolution", "1.0.0")
    def resolve_entities(
        self,
        entities: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Resolve duplicate entities and generate canonical forms.
        
        Args:
            entities: List of entities extracted by SimpleKGPipeline
            **kwargs: Additional context (episode_id, segment_id)
            
        Returns:
            Dictionary with resolved entities and resolution metrics
        """
        if self.config.preview_mode:
            return self._preview_resolution(entities)
        
        # Reset metrics
        self.resolution_metrics = {
            "entities_before": len(entities),
            "entities_after": 0,
            "merges_performed": 0,
            "merge_types": defaultdict(int)
        }
        
        # Find all potential matches
        matches = self._find_entity_matches(entities)
        
        # Group entities by match clusters
        clusters = self._cluster_entities(entities, matches)
        
        # Merge entities within each cluster
        resolved_entities = []
        for cluster in clusters:
            if len(cluster) > 1:
                merged = self._merge_entity_cluster(cluster)
                resolved_entities.append(merged)
                self.resolution_metrics["merges_performed"] += len(cluster) - 1
            else:
                resolved_entities.append(cluster[0])
        
        self.resolution_metrics["entities_after"] = len(resolved_entities)
        
        # Track contribution
        if self.resolution_metrics["merges_performed"] > 0:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="entity_resolution",
                contribution_type="entities_merged",
                details={
                    "merge_types": dict(self.resolution_metrics["merge_types"]),
                    "reduction_ratio": 1 - (len(resolved_entities) / len(entities))
                },
                count=self.resolution_metrics["merges_performed"],
                timestamp=kwargs.get('timestamp', '')
            )
            tracker.track_contribution(contribution)
        
        return {
            "resolved_entities": resolved_entities,
            "original_count": len(entities),
            "resolved_count": len(resolved_entities),
            "metrics": self._get_resolution_metrics(),
            "episode_id": kwargs.get('episode_id'),
            "segment_id": kwargs.get('segment_id')
        }
    
    def _find_entity_matches(self, entities: List[Dict[str, Any]]) -> List[EntityMatch]:
        """Find all potential matches between entities."""
        matches = []
        
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                match = self._compare_entities(entities[i], entities[j])
                if match and match.similarity_score >= self.config.similarity_threshold:
                    matches.append(match)
        
        return matches
    
    def _compare_entities(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> Optional[EntityMatch]:
        """Compare two entities and return match information if similar."""
        name1 = entity1.get('value', entity1.get('name', ''))
        name2 = entity2.get('value', entity2.get('name', ''))
        
        if not name1 or not name2:
            return None
        
        # Check exact match
        if name1 == name2:
            return EntityMatch(
                entity1=entity1,
                entity2=entity2,
                similarity_score=1.0,
                match_type='exact',
                confidence=1.0
            )
        
        # Check case-insensitive match
        if not self.config.case_sensitive and name1.lower() == name2.lower():
            self.resolution_metrics["merge_types"]["case"] += 1
            return EntityMatch(
                entity1=entity1,
                entity2=entity2,
                similarity_score=0.95,
                match_type='case',
                confidence=0.95
            )
        
        # Check alias match
        if self.config.use_aliases:
            if self._are_aliases(name1, name2):
                self.resolution_metrics["merge_types"]["alias"] += 1
                return EntityMatch(
                    entity1=entity1,
                    entity2=entity2,
                    similarity_score=0.9,
                    match_type='alias',
                    confidence=0.9
                )
        
        # Check abbreviation match
        if self.config.use_abbreviations:
            if self._is_abbreviation(name1, name2):
                self.resolution_metrics["merge_types"]["abbreviation"] += 1
                return EntityMatch(
                    entity1=entity1,
                    entity2=entity2,
                    similarity_score=0.9,
                    match_type='abbreviation',
                    confidence=0.9
                )
        
        # Check singular/plural match
        if self.config.merge_singular_plural:
            if self._are_singular_plural(name1, name2):
                self.resolution_metrics["merge_types"]["singular_plural"] += 1
                return EntityMatch(
                    entity1=entity1,
                    entity2=entity2,
                    similarity_score=0.9,
                    match_type='singular_plural',
                    confidence=0.9
                )
        
        # Fuzzy match
        similarity = self._calculate_similarity(name1, name2)
        if similarity >= self.config.similarity_threshold:
            self.resolution_metrics["merge_types"]["fuzzy"] += 1
            return EntityMatch(
                entity1=entity1,
                entity2=entity2,
                similarity_score=similarity,
                match_type='fuzzy',
                confidence=similarity * 0.8  # Lower confidence for fuzzy matches
            )
        
        return None
    
    def _are_aliases(self, name1: str, name2: str) -> bool:
        """Check if two names are known aliases."""
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        for aliases in self.alias_rules:
            if name1_lower in aliases and name2_lower in aliases:
                return True
        
        return False
    
    def _is_abbreviation(self, name1: str, name2: str) -> bool:
        """Check if one name is an abbreviation of the other."""
        # Check direct abbreviation mapping
        if name1 in self.abbreviation_map and self.abbreviation_map[name1].lower() == name2.lower():
            return True
        if name2 in self.abbreviation_map and self.abbreviation_map[name2].lower() == name1.lower():
            return True
        
        # Check if one is an acronym of the other
        if self._is_acronym(name1, name2) or self._is_acronym(name2, name1):
            return True
        
        return False
    
    def _is_acronym(self, acronym: str, full_name: str) -> bool:
        """Check if acronym matches the initials of full_name."""
        if not acronym.isupper() or ' ' not in full_name:
            return False
        
        initials = ''.join(word[0].upper() for word in full_name.split() if word)
        return acronym == initials
    
    def _are_singular_plural(self, name1: str, name2: str) -> bool:
        """Check if names are singular/plural forms of each other."""
        # Simple rule-based check
        if name1.endswith('s') and name1[:-1] == name2:
            return True
        if name2.endswith('s') and name2[:-1] == name1:
            return True
        
        # Common irregular plurals
        irregular_plurals = {
            'person': 'people',
            'child': 'children',
            'man': 'men',
            'woman': 'women',
            'datum': 'data',
            'index': 'indices'
        }
        
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        for singular, plural in irregular_plurals.items():
            if (name1_lower == singular and name2_lower == plural) or \
               (name1_lower == plural and name2_lower == singular):
                return True
        
        return False
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two names."""
        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    
    def _cluster_entities(self, entities: List[Dict[str, Any]], matches: List[EntityMatch]) -> List[List[Dict[str, Any]]]:
        """Group entities into clusters based on matches."""
        # Create a mapping of entity to cluster ID
        entity_to_cluster = {}
        clusters = []
        
        # Initialize each entity in its own cluster
        for i, entity in enumerate(entities):
            entity_id = id(entity)
            entity_to_cluster[entity_id] = i
            clusters.append([entity])
        
        # Merge clusters based on matches
        for match in matches:
            id1 = id(match.entity1)
            id2 = id(match.entity2)
            
            cluster1 = entity_to_cluster[id1]
            cluster2 = entity_to_cluster[id2]
            
            if cluster1 != cluster2:
                # Merge smaller cluster into larger
                if len(clusters[cluster1]) < len(clusters[cluster2]):
                    cluster1, cluster2 = cluster2, cluster1
                
                # Move all entities from cluster2 to cluster1
                for entity in clusters[cluster2]:
                    entity_to_cluster[id(entity)] = cluster1
                    clusters[cluster1].append(entity)
                
                clusters[cluster2] = []  # Mark as empty
        
        # Return non-empty clusters
        return [cluster for cluster in clusters if cluster]
    
    def _merge_entity_cluster(self, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a cluster of entities into a single canonical entity."""
        # Select canonical name (most frequent or longest)
        name_counts = defaultdict(int)
        for entity in cluster:
            name = entity.get('value', entity.get('name', ''))
            name_counts[name] += 1
        
        # Choose most frequent name, break ties by length
        canonical_name = max(name_counts.keys(), key=lambda x: (name_counts[x], len(x)))
        
        # Merge properties
        merged_entity = {
            'value': canonical_name,
            'type': cluster[0].get('type', 'Entity'),
            'aliases': set(),
            'occurrences': 0,
            'confidence': 0.0,
            'properties': {}
        }
        
        # Collect all unique names as aliases
        for entity in cluster:
            name = entity.get('value', entity.get('name', ''))
            if name != canonical_name:
                merged_entity['aliases'].add(name)
            
            merged_entity['occurrences'] += entity.get('occurrences', 1)
            
            # Average confidence scores
            if 'confidence' in entity:
                merged_entity['confidence'] += entity['confidence']
            
            # Merge properties
            for key, value in entity.items():
                if key not in ['value', 'name', 'type', 'confidence', 'occurrences']:
                    if key not in merged_entity['properties']:
                        merged_entity['properties'][key] = []
                    if value not in merged_entity['properties'][key]:
                        merged_entity['properties'][key].append(value)
        
        # Convert aliases to list
        merged_entity['aliases'] = list(merged_entity['aliases'])
        
        # Average confidence
        if merged_entity['confidence'] > 0:
            merged_entity['confidence'] /= len(cluster)
        
        return merged_entity
    
    def _get_resolution_metrics(self) -> Dict[str, Any]:
        """Get metrics about the resolution process."""
        return {
            "type": "entity_resolution",
            "details": {
                "entities_before": self.resolution_metrics["entities_before"],
                "entities_after": self.resolution_metrics["entities_after"],
                "merges_performed": self.resolution_metrics["merges_performed"],
                "reduction_percentage": (
                    (1 - self.resolution_metrics["entities_after"] / 
                     self.resolution_metrics["entities_before"]) * 100
                    if self.resolution_metrics["entities_before"] > 0 else 0
                ),
                "merge_types": dict(self.resolution_metrics["merge_types"])
            },
            "count": self.resolution_metrics["merges_performed"]
        }
    
    def _preview_resolution(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Preview resolution without applying changes."""
        matches = self._find_entity_matches(entities)
        clusters = self._cluster_entities(entities, matches)
        
        preview = {
            "would_merge": [],
            "total_merges": 0
        }
        
        for cluster in clusters:
            if len(cluster) > 1:
                names = [e.get('value', e.get('name', '')) for e in cluster]
                preview["would_merge"].append({
                    "entities": names,
                    "count": len(names),
                    "canonical": max(names, key=len)  # Longest as canonical
                })
                preview["total_merges"] += len(cluster) - 1
        
        preview["entities_before"] = len(entities)
        preview["entities_after"] = len(entities) - preview["total_merges"]
        
        return preview
    
    def _load_alias_rules(self) -> List[Set[str]]:
        """Load predefined alias rules."""
        return [
            {"ai", "artificial intelligence", "a.i."},
            {"ml", "machine learning"},
            {"nlp", "natural language processing"},
            {"llm", "large language model", "large language models"},
            {"api", "application programming interface"},
            {"ui", "user interface"},
            {"ux", "user experience"},
            {"db", "database"},
            {"os", "operating system"},
            {"cpu", "central processing unit", "processor"},
            {"gpu", "graphics processing unit", "graphics card"},
            {"ram", "random access memory", "memory"},
            {"ssd", "solid state drive"},
            {"hdd", "hard disk drive", "hard drive"},
            {"iot", "internet of things"},
            {"vr", "virtual reality"},
            {"ar", "augmented reality"},
            {"mr", "mixed reality"},
            {"ci", "continuous integration"},
            {"cd", "continuous deployment", "continuous delivery"},
            {"devops", "development operations"},
            {"poc", "proof of concept"},
            {"mvp", "minimum viable product"},
            {"roi", "return on investment"},
            {"kpi", "key performance indicator"},
            {"b2b", "business to business"},
            {"b2c", "business to consumer"},
            {"saas", "software as a service"},
            {"paas", "platform as a service"},
            {"iaas", "infrastructure as a service"}
        ]
    
    def _load_abbreviations(self) -> Dict[str, str]:
        """Load abbreviation mappings."""
        return {
            "Dr.": "Doctor",
            "Mr.": "Mister",
            "Mrs.": "Missus",
            "Ms.": "Miss",
            "Prof.": "Professor",
            "CEO": "Chief Executive Officer",
            "CTO": "Chief Technology Officer",
            "CFO": "Chief Financial Officer",
            "COO": "Chief Operating Officer",
            "VP": "Vice President",
            "SVP": "Senior Vice President",
            "EVP": "Executive Vice President",
            "PhD": "Doctor of Philosophy",
            "MD": "Medical Doctor",
            "JD": "Juris Doctor",
            "MBA": "Master of Business Administration",
            "USA": "United States of America",
            "UK": "United Kingdom",
            "EU": "European Union",
            "UN": "United Nations",
            "WHO": "World Health Organization",
            "NASA": "National Aeronautics and Space Administration",
            "FBI": "Federal Bureau of Investigation",
            "CIA": "Central Intelligence Agency",
            "MIT": "Massachusetts Institute of Technology",
            "UCLA": "University of California Los Angeles",
            "NYU": "New York University"
        }