"""
Consolidated entity resolution and matching functionality.

This module handles entity resolution and deduplication for both structured Entity objects
and dictionary-based entities from schemaless extraction.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any, Set, Union
import logging
import re

import difflib

from src.core.extraction_interface import Entity, EntityType
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
    id: str
    name: str
    similarity: float
    match_type: str  # 'exact_normalized', 'alias_match', 'fuzzy_match', 'case', 'abbreviation', 'singular_plural'
    confidence: float = 1.0
    entity1: Optional[Dict[str, Any]] = None
    entity2: Optional[Dict[str, Any]] = None
    

@dataclass
class EntityRelationship:
    """Represents a relationship between entities."""
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    context: Optional[str] = None


class EntityResolver:
    """Handles entity resolution and deduplication for all entity types."""
    
    def __init__(self, config: Optional[EntityResolutionConfig] = None):
        """
        Initialize entity resolver with configuration.
        
        Args:
            config: Configuration for entity resolution
        """
        self.config = config or EntityResolutionConfig()
        
        # Legacy similarity threshold for backward compatibility
        self.similarity_threshold = self.config.similarity_threshold
        
        # Common suffixes to remove during normalization
        self.suffixes_to_remove = [
            ", inc.", ", inc", " inc.", " inc",
            ", llc", " llc",
            ", ltd", " ltd",
            ", corp", " corp",
            " corporation",
            " company",
            " & co",
            " co."
        ]
        
        # Common abbreviations to expand
        self.abbreviations = {
            "&": "and",
            "u.s.": "us",
            "u.k.": "uk",
            "dr.": "doctor",
            "mr.": "mister",
            "ms.": "miss",
            "prof.": "professor"
        }
        
        # Alias extraction patterns
        self.alias_patterns = [
            r'also known as ([^,]+)',
            r'formerly ([^,.]+(?:,\s*[^.]+)?\.?)',
            r'aka ([^,]+)',
            r'\(([^)]+)\)',  # Names in parentheses
            r'or "([^"]+)"',  # Names in quotes
            r"or '([^']+)'",  # Names in single quotes
        ]
        
        # Load advanced alias and abbreviation rules
        self.alias_rules = self._load_alias_rules()
        self.abbreviation_map = self._load_abbreviations()
        
        # Resolution metrics
        self.resolution_metrics = {
            "entities_before": 0,
            "entities_after": 0,
            "merges_performed": 0,
            "merge_types": defaultdict(int)
        }
    
    def normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name for comparison and deduplication.
        
        Args:
            name: Entity name to normalize
            
        Returns:
            Normalized name (lowercase, stripped, common variations handled)
        """
        if not name:
            return ""
        
        # Convert to lowercase and strip
        normalized = name.lower().strip()
        
        # Remove common suffixes
        for suffix in self.suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # Handle common abbreviations
        for abbr, full in self.abbreviations.items():
            normalized = normalized.replace(abbr, full)
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        return normalized
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two entity names.
        
        Args:
            name1: First entity name
            name2: Second entity name
            
        Returns:
            Similarity score between 0 and 1
        """
        # Normalize both names
        norm1 = self.normalize_entity_name(name1)
        norm2 = self.normalize_entity_name(name2)
        
        # Use sequence matcher for fuzzy matching
        return difflib.SequenceMatcher(None, norm1, norm2).ratio()
    
    def extract_entity_aliases(self, entity_name: str, entity_description: Optional[str]) -> List[str]:
        """
        Extract potential aliases from entity description.
        
        Args:
            entity_name: Main entity name
            entity_description: Entity description that might contain aliases
            
        Returns:
            List of potential aliases
        """
        aliases = []
        
        if not entity_description:
            return aliases
        
        # Extract aliases using patterns
        for pattern in self.alias_patterns:
            matches = re.findall(pattern, entity_description, re.IGNORECASE)
            aliases.extend(matches)
        
        # Clean up aliases
        cleaned_aliases = []
        seen = set()
        for alias in aliases:
            alias = alias.strip()
            # Don't include the main name as an alias
            if alias.lower() != entity_name.lower() and alias and alias.lower() not in seen:
                cleaned_aliases.append(alias)
                seen.add(alias.lower())
        
        return cleaned_aliases
    
    def _compare_entities(self, entity1: Union[Entity, Dict[str, Any]], entity2: Union[Entity, Dict[str, Any]]) -> Optional[EntityMatch]:
        """Compare two entities and return match information if similar."""
        # Extract names from different entity formats
        if isinstance(entity1, Entity):
            name1 = entity1.name
            id1 = entity1.properties.get('id', '') if entity1.properties else ''
        elif isinstance(entity1, dict):
            name1 = entity1.get('value', entity1.get('name', ''))
            id1 = entity1.get('id', '')
        else:
            # Handle case where entity1 is actually an Entity but being checked incorrectly
            name1 = getattr(entity1, 'name', '')
            props = getattr(entity1, 'properties', {})
            id1 = props.get('id', '') if props else ''
        
        if isinstance(entity2, Entity):
            name2 = entity2.name
            id2 = entity2.properties.get('id', '') if entity2.properties else ''
        elif isinstance(entity2, dict):
            name2 = entity2.get('value', entity2.get('name', ''))
            id2 = entity2.get('id', '')
        else:
            # Handle case where entity2 is actually an Entity but being checked incorrectly
            name2 = getattr(entity2, 'name', '')
            props = getattr(entity2, 'properties', {})
            id2 = props.get('id', '') if props else ''
        
        if not name1 or not name2:
            return None
        
        # Check exact match
        if name1 == name2:
            return EntityMatch(
                id=id2,
                name=name2,
                similarity=1.0,
                match_type='exact',
                confidence=1.0,
                entity1=entity1 if isinstance(entity1, dict) else None,
                entity2=entity2 if isinstance(entity2, dict) else None
            )
        
        # Check case-insensitive match
        if not self.config.case_sensitive and name1.lower() == name2.lower():
            self.resolution_metrics["merge_types"]["case"] += 1
            return EntityMatch(
                id=id2,
                name=name2,
                similarity=0.95,
                match_type='case',
                confidence=0.95,
                entity1=entity1 if isinstance(entity1, dict) else None,
                entity2=entity2 if isinstance(entity2, dict) else None
            )
        
        # Check exact match on normalized names
        normalized_name1 = self.normalize_entity_name(name1)
        normalized_name2 = self.normalize_entity_name(name2)
        
        if normalized_name1 == normalized_name2:
            return EntityMatch(
                id=id2,
                name=name2,
                similarity=1.0,
                match_type="exact_normalized",
                confidence=1.0,
                entity1=entity1 if isinstance(entity1, dict) else None,
                entity2=entity2 if isinstance(entity2, dict) else None
            )
        
        # Check alias match
        if self.config.use_aliases:
            if self._are_aliases(name1, name2):
                self.resolution_metrics["merge_types"]["alias"] += 1
                return EntityMatch(
                    id=id2,
                    name=name2,
                    similarity=0.9,
                    match_type='alias_match',
                    confidence=0.9,
                    entity1=entity1 if isinstance(entity1, dict) else None,
                    entity2=entity2 if isinstance(entity2, dict) else None
                )
        
        # Check abbreviation match
        if self.config.use_abbreviations:
            if self._is_abbreviation(name1, name2):
                self.resolution_metrics["merge_types"]["abbreviation"] += 1
                return EntityMatch(
                    id=id2,
                    name=name2,
                    similarity=0.9,
                    match_type='abbreviation',
                    confidence=0.9,
                    entity1=entity1 if isinstance(entity1, dict) else None,
                    entity2=entity2 if isinstance(entity2, dict) else None
                )
        
        # Check singular/plural match
        if self.config.merge_singular_plural:
            if self._are_singular_plural(name1, name2):
                self.resolution_metrics["merge_types"]["singular_plural"] += 1
                return EntityMatch(
                    id=id2,
                    name=name2,
                    similarity=0.9,
                    match_type='singular_plural',
                    confidence=0.9,
                    entity1=entity1 if isinstance(entity1, dict) else None,
                    entity2=entity2 if isinstance(entity2, dict) else None
                )
        
        # Fuzzy match
        similarity = self.calculate_name_similarity(name1, name2)
        if similarity >= self.config.similarity_threshold:
            self.resolution_metrics["merge_types"]["fuzzy"] += 1
            return EntityMatch(
                id=id2,
                name=name2,
                similarity=similarity,
                match_type='fuzzy_match',
                confidence=similarity * 0.8,  # Lower confidence for fuzzy matches
                entity1=entity1 if isinstance(entity1, dict) else None,
                entity2=entity2 if isinstance(entity2, dict) else None
            )
        
        return None
    
    def find_potential_matches(
        self, 
        new_entity: Union[Entity, Dict[str, Any]], 
        existing_entities: List[Union[Entity, Dict[str, Any]]]
    ) -> List[EntityMatch]:
        """
        Find existing entities that might be duplicates of the new entity.
        
        Args:
            new_entity: New entity to check
            existing_entities: List of existing entities to compare against
            
        Returns:
            List of potential matches with similarity scores
        """
        potential_matches = []
        
        for existing in existing_entities:
            # Skip if different entity types (for Entity objects)
            if isinstance(new_entity, Entity) and isinstance(existing, Entity):
                # Compare types - handle both string and enum types
                new_type = new_entity.type.value if hasattr(new_entity.type, 'value') else new_entity.type
                existing_type = existing.type.value if hasattr(existing.type, 'value') else existing.type
                if new_type != existing_type:
                    continue
            elif isinstance(new_entity, dict) and isinstance(existing, dict):
                # Also skip for dict entities with different types
                if new_entity.get('type') != existing.get('type'):
                    continue
            
            match = self._compare_entities(new_entity, existing)
            if match and match.similarity >= self.config.similarity_threshold:
                potential_matches.append(match)
        
        # Sort by similarity score
        potential_matches.sort(key=lambda x: x.similarity, reverse=True)
        
        return potential_matches
    
    def merge_entities(self, primary: Entity, duplicate: Entity) -> Entity:
        """
        Merge duplicate entity into primary entity.
        
        Args:
            primary: Primary entity to keep
            duplicate: Duplicate entity to merge
            
        Returns:
            Merged entity
        """
        # Merge descriptions
        if duplicate.description and duplicate.description not in (primary.description or ""):
            if primary.description:
                primary.description = f"{primary.description}. {duplicate.description}"
            else:
                primary.description = duplicate.description
        
        # Merge aliases
        primary_aliases = getattr(primary, 'aliases', [])[:]  # Make a copy
        duplicate_aliases = getattr(duplicate, 'aliases', [])
        
        # Add duplicate's name as an alias if different
        if duplicate.name.lower() != primary.name.lower():
            primary_aliases.append(duplicate.name)
        
        # Add duplicate's aliases
        primary_aliases.extend(duplicate_aliases)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_aliases = []
        for alias in primary_aliases:
            normalized = self.normalize_entity_name(alias)
            if normalized not in seen and normalized != self.normalize_entity_name(primary.name):
                seen.add(normalized)
                unique_aliases.append(alias)
        
        setattr(primary, 'aliases', unique_aliases)
        
        # Update confidence (take max)
        primary.confidence = max(primary.confidence, duplicate.confidence)
        
        # Merge metadata if available
        if hasattr(primary, 'metadata') and hasattr(duplicate, 'metadata'):
            primary.metadata = {**duplicate.metadata, **primary.metadata}
        
        return primary
    
    def _merge_entity_cluster(self, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a cluster of dictionary-based entities into one canonical entity."""
        if not cluster:
            return {}
        
        # Sort by confidence if available, otherwise use the first one
        sorted_cluster = sorted(cluster, key=lambda x: x.get('confidence', 0.5), reverse=True)
        canonical = sorted_cluster[0].copy()
        
        # Merge properties from all entities
        all_values = set()
        all_descriptions = []
        all_types = set()
        
        for entity in cluster:
            # Collect all name variations
            value = entity.get('value', entity.get('name', ''))
            if value:
                all_values.add(value)
            
            # Collect descriptions
            desc = entity.get('description', '')
            if desc and desc not in all_descriptions:
                all_descriptions.append(desc)
            
            # Collect types
            entity_type = entity.get('type', '')
            if entity_type:
                all_types.add(entity_type)
        
        # Update canonical entity
        if len(all_values) > 1:
            canonical['aliases'] = list(all_values - {canonical.get('value', canonical.get('name', ''))})
        
        if all_descriptions:
            canonical['description'] = '. '.join(all_descriptions)
        
        # Use the most common type or the first one
        if all_types:
            canonical['type'] = list(all_types)[0]
        
        return canonical
    
    @track_component_impact("entity_resolution", "1.0.0")
    def resolve_entities(self, entities: Union[List[Entity], List[Dict[str, Any]]], **kwargs) -> Union[List[Entity], Dict[str, Any]]:
        """
        Resolve and deduplicate a list of entities.
        
        Args:
            entities: List of entities to resolve (Entity objects or dictionaries)
            **kwargs: Additional context for tracking
            
        Returns:
            List of deduplicated entities or dict with resolution results
        """
        if not entities:
            return []
        
        # Reset metrics
        self.resolution_metrics = {
            "entities_before": len(entities),
            "entities_after": 0,
            "merges_performed": 0,
            "merge_types": defaultdict(int)
        }
        
        # Handle preview mode for dict entities
        if self.config.preview_mode and isinstance(entities[0], dict):
            return self._preview_resolution(entities)
        
        # Handle Entity objects with legacy method
        if isinstance(entities[0], Entity):
            return self._resolve_entity_objects(entities)
        
        # Handle dictionary entities with clustering approach
        return self._resolve_dict_entities(entities, **kwargs)
    
    def _resolve_entity_objects(self, entities: List[Entity]) -> List[Entity]:
        """Resolve Entity objects using legacy approach."""
        resolved = []
        processed_ids = set()
        
        for entity in entities:
            # Get id from properties
            entity_id = entity.properties.get('id', '') if entity.properties else ''
            
            # Skip if already processed as a duplicate
            if entity_id in processed_ids:
                continue
            
            # Find potential matches in already resolved entities
            matches = self.find_potential_matches(entity, resolved)
            
            if matches and matches[0].similarity >= self.config.similarity_threshold:
                # Merge with the best match
                best_match = matches[0]
                for i, resolved_entity in enumerate(resolved):
                    resolved_id = resolved_entity.properties.get('id', '') if resolved_entity.properties else ''
                    if resolved_id == best_match.id:
                        resolved[i] = self.merge_entities(resolved_entity, entity)
                        processed_ids.add(entity_id)
                        self.resolution_metrics["merges_performed"] += 1
                        break
            else:
                # No match found, add as new entity
                resolved.append(entity)
                processed_ids.add(entity_id)
        
        self.resolution_metrics["entities_after"] = len(resolved)
        return resolved
    
    def _resolve_dict_entities(self, entities: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Resolve dictionary entities using clustering approach."""
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
                metadata={
                    "merge_types": dict(self.resolution_metrics["merge_types"]),
                    "reduction_ratio": 1 - (len(resolved_entities) / len(entities))
                },
                count=self.resolution_metrics["merges_performed"]
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
                if match and match.similarity >= self.config.similarity_threshold:
                    matches.append(match)
        
        return matches
    
    def _cluster_entities(self, entities: List[Dict[str, Any]], matches: List[EntityMatch]) -> List[List[Dict[str, Any]]]:
        """Group entities into clusters based on matches."""
        # Create adjacency list
        entity_to_index = {id(entity): i for i, entity in enumerate(entities)}
        adjacency = defaultdict(set)
        
        for match in matches:
            idx1 = entity_to_index[id(match.entity1)]
            idx2 = entity_to_index[id(match.entity2)]
            adjacency[idx1].add(idx2)
            adjacency[idx2].add(idx1)
        
        # Find connected components
        visited = set()
        clusters = []
        
        def dfs(idx, cluster):
            if idx in visited:
                return
            visited.add(idx)
            cluster.append(entities[idx])
            for neighbor in adjacency[idx]:
                dfs(neighbor, cluster)
        
        for i in range(len(entities)):
            if i not in visited:
                cluster = []
                dfs(i, cluster)
                clusters.append(cluster)
        
        return clusters
    
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
    
    def _get_resolution_metrics(self) -> Dict[str, Any]:
        """Get resolution metrics summary."""
        return {
            "entities_before": self.resolution_metrics["entities_before"],
            "entities_after": self.resolution_metrics["entities_after"],
            "merges_performed": self.resolution_metrics["merges_performed"],
            "reduction_ratio": 1 - (self.resolution_metrics["entities_after"] / max(1, self.resolution_metrics["entities_before"])),
            "merge_types": dict(self.resolution_metrics["merge_types"])
        }
    
    def _preview_resolution(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Preview what would be merged without actually merging."""
        matches = self._find_entity_matches(entities)
        clusters = self._cluster_entities(entities, matches)
        
        merge_preview = []
        for cluster in clusters:
            if len(cluster) > 1:
                names = [e.get('value', e.get('name', '')) for e in cluster]
                merge_preview.append({
                    "canonical": names[0],
                    "merged": names[1:],
                    "count": len(cluster)
                })
        
        return {
            "original_count": len(entities),
            "resolved_count": len(clusters),
            "merges_to_perform": len(merge_preview),
            "merge_preview": merge_preview,
            "metrics": self._get_resolution_metrics()
        }
    
    def _load_alias_rules(self) -> List[Set[str]]:
        """Load known alias rules."""
        # Common aliases for demonstration
        return [
            {"ai", "artificial intelligence", "machine intelligence"},
            {"ml", "machine learning"},
            {"nlp", "natural language processing"},
            {"usa", "united states", "america", "us"},
            {"uk", "united kingdom", "britain"},
            {"google", "alphabet inc"},
            {"facebook", "meta"},
        ]
    
    def _load_abbreviations(self) -> Dict[str, str]:
        """Load abbreviation mappings."""
        return {
            "ai": "artificial intelligence",
            "ml": "machine learning", 
            "nlp": "natural language processing",
            "usa": "united states",
            "uk": "united kingdom",
            "ceo": "chief executive officer",
            "cto": "chief technology officer",
            "cfo": "chief financial officer"
        }
    
    # Legacy methods for backward compatibility
    def extract_entity_relationships(
        self, 
        text: str, 
        entities: List[Entity]
    ) -> List[EntityRelationship]:
        """
        Extract relationships between entities based on co-occurrence in text.
        
        Args:
            text: Text to analyze
            entities: List of entities to find relationships between
            
        Returns:
            List of entity relationships
        """
        relationships = []
        text_lower = text.lower()
        
        # Check co-occurrence for each pair of entities
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Skip same type entities for certain relationships
                if entity1.type == entity2.type and entity1.type in [
                    EntityType.PERSON, EntityType.ORGANIZATION
                ]:
                    continue
                
                # Check if both entities appear in the text
                if (self.normalize_entity_name(entity1.name) in text_lower and 
                    self.normalize_entity_name(entity2.name) in text_lower):
                    
                    # Determine relationship type based on entity types
                    rel_type = self._determine_relationship_type(entity1, entity2)
                    
                    # Calculate confidence based on proximity
                    confidence = self._calculate_relationship_confidence(
                        text_lower, entity1.name, entity2.name
                    )
                    
                    if confidence > 0.5:  # Minimum confidence threshold
                        source_id = entity1.properties.get('id', '') if entity1.properties else ''
                        target_id = entity2.properties.get('id', '') if entity2.properties else ''
                        relationships.append(EntityRelationship(
                            source_id=source_id,
                            target_id=target_id,
                            relationship_type=rel_type,
                            confidence=confidence,
                            context=self._extract_relationship_context(text, entity1.name, entity2.name)
                        ))
        
        return relationships
    
    def _determine_relationship_type(self, entity1: Entity, entity2: Entity) -> str:
        """Determine the type of relationship between two entities."""
        # Simple heuristic based on entity types
        type_pair = (entity1.type, entity2.type)
        
        relationship_map = {
            (EntityType.PERSON, EntityType.ORGANIZATION): "WORKS_FOR",
            (EntityType.ORGANIZATION, EntityType.PERSON): "EMPLOYS",
            (EntityType.PERSON, EntityType.TOPIC): "DISCUSSES",
            (EntityType.ORGANIZATION, EntityType.TOPIC): "FOCUSES_ON",
            (EntityType.PERSON, EntityType.PERSON): "MENTIONED_WITH",
            (EntityType.ORGANIZATION, EntityType.ORGANIZATION): "RELATED_TO",
        }
        
        return relationship_map.get(type_pair, "RELATED_TO")
    
    def _calculate_relationship_confidence(
        self, text: str, name1: str, name2: str
    ) -> float:
        """Calculate confidence of relationship based on proximity in text."""
        # Find positions of both names
        pos1 = text.find(name1.lower())
        pos2 = text.find(name2.lower())
        
        if pos1 == -1 or pos2 == -1:
            return 0.0
        
        # Calculate distance
        distance = abs(pos1 - pos2)
        
        # Confidence decreases with distance
        if distance < 50:
            return 0.9
        elif distance < 100:
            return 0.7
        elif distance < 200:
            return 0.6
        else:
            return 0.5
    
    def _extract_relationship_context(
        self, text: str, name1: str, name2: str, window: int = 100
    ) -> str:
        """Extract context around entity mentions."""
        # Find positions
        pos1 = text.lower().find(name1.lower())
        pos2 = text.lower().find(name2.lower())
        
        if pos1 == -1 or pos2 == -1:
            return ""
        
        # Get context window around both entities
        start = max(0, min(pos1, pos2) - window)
        end = min(len(text), max(pos1 + len(name1), pos2 + len(name2)) + window)
        
        return text[start:end].strip()