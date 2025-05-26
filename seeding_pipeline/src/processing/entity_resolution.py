"""
Entity resolution and matching functionality
"""
import re
import difflib
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from src.core.models import Entity, EntityType
from src.core.interfaces import EmbeddingProvider


@dataclass
class EntityMatch:
    """Represents a potential entity match"""
    id: str
    name: str
    similarity: float
    match_type: str  # 'exact_normalized', 'alias_match', 'fuzzy_match'
    
    
@dataclass
class EntityRelationship:
    """Represents a relationship between entities"""
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    context: Optional[str] = None


class EntityResolver:
    """Handles entity resolution and deduplication"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize entity resolver
        
        Args:
            similarity_threshold: Minimum similarity score to consider a match
        """
        self.similarity_threshold = similarity_threshold
        
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
            r'also known as ([^,\.]+)',
            r'formerly ([^,\.]+)',
            r'aka ([^,\.]+)',
            r'\(([^)]+)\)',  # Names in parentheses
            r'or "([^"]+)"',  # Names in quotes
            r"or '([^']+)'",  # Names in single quotes
        ]
    
    def normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name for comparison and deduplication
        
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
        Calculate similarity between two entity names
        
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
        Extract potential aliases from entity description
        
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
        for alias in aliases:
            alias = alias.strip()
            # Don't include the main name as an alias
            if alias.lower() != entity_name.lower() and alias:
                cleaned_aliases.append(alias)
        
        return cleaned_aliases
    
    def find_potential_matches(
        self, 
        new_entity: Entity, 
        existing_entities: List[Entity]
    ) -> List[EntityMatch]:
        """
        Find existing entities that might be duplicates of the new entity
        
        Args:
            new_entity: New entity to check
            existing_entities: List of existing entities to compare against
            
        Returns:
            List of potential matches with similarity scores
        """
        # Normalize the new entity name
        normalized_new_name = self.normalize_entity_name(new_entity.name)
        
        potential_matches = []
        
        for existing in existing_entities:
            # Skip if different entity types
            if existing.type != new_entity.type:
                continue
                
            existing_normalized = self.normalize_entity_name(existing.name)
            
            # Check exact match on normalized names
            if normalized_new_name == existing_normalized:
                potential_matches.append(EntityMatch(
                    id=existing.id,
                    name=existing.name,
                    similarity=1.0,
                    match_type="exact_normalized"
                ))
                continue
            
            # Check if new name matches any aliases
            existing_aliases = getattr(existing, 'aliases', [])
            if existing_aliases and normalized_new_name in [
                self.normalize_entity_name(alias) for alias in existing_aliases
            ]:
                potential_matches.append(EntityMatch(
                    id=existing.id,
                    name=existing.name,
                    similarity=0.95,
                    match_type="alias_match"
                ))
                continue
            
            # Calculate fuzzy similarity
            similarity = self.calculate_name_similarity(new_entity.name, existing.name)
            if similarity >= self.similarity_threshold:
                potential_matches.append(EntityMatch(
                    id=existing.id,
                    name=existing.name,
                    similarity=similarity,
                    match_type="fuzzy_match"
                ))
        
        # Sort by similarity score
        potential_matches.sort(key=lambda x: x.similarity, reverse=True)
        
        return potential_matches
    
    def merge_entities(self, primary: Entity, duplicate: Entity) -> Entity:
        """
        Merge duplicate entity into primary entity
        
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
        primary_aliases = getattr(primary, 'aliases', [])
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
    
    def resolve_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        Resolve and deduplicate a list of entities
        
        Args:
            entities: List of entities to resolve
            
        Returns:
            List of deduplicated entities
        """
        if not entities:
            return []
        
        resolved = []
        processed_ids = set()
        
        for entity in entities:
            # Skip if already processed as a duplicate
            if entity.id in processed_ids:
                continue
            
            # Find potential matches in already resolved entities
            matches = self.find_potential_matches(entity, resolved)
            
            if matches and matches[0].similarity >= self.similarity_threshold:
                # Merge with the best match
                best_match = matches[0]
                for i, resolved_entity in enumerate(resolved):
                    if resolved_entity.id == best_match.id:
                        resolved[i] = self.merge_entities(resolved_entity, entity)
                        processed_ids.add(entity.id)
                        break
            else:
                # No match found, add as new entity
                resolved.append(entity)
                processed_ids.add(entity.id)
        
        return resolved
    
    def extract_entity_relationships(
        self, 
        text: str, 
        entities: List[Entity]
    ) -> List[EntityRelationship]:
        """
        Extract relationships between entities based on co-occurrence in text
        
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
                        relationships.append(EntityRelationship(
                            source_id=entity1.id,
                            target_id=entity2.id,
                            relationship_type=rel_type,
                            confidence=confidence,
                            context=self._extract_relationship_context(
                                text, entity1.name, entity2.name
                            )
                        ))
        
        return relationships
    
    def _determine_relationship_type(self, entity1: Entity, entity2: Entity) -> str:
        """Determine relationship type based on entity types"""
        type_pairs = {
            (EntityType.PERSON, EntityType.ORGANIZATION): "AFFILIATED_WITH",
            (EntityType.PERSON, EntityType.TECHNOLOGY): "WORKS_WITH",
            (EntityType.ORGANIZATION, EntityType.TECHNOLOGY): "USES",
            (EntityType.CONCEPT, EntityType.TECHNOLOGY): "IMPLEMENTED_BY",
            (EntityType.PERSON, EntityType.CONCEPT): "DISCUSSES",
            (EntityType.ORGANIZATION, EntityType.CONCEPT): "IMPLEMENTS"
        }
        
        # Check both directions
        pair = (entity1.type, entity2.type)
        reverse_pair = (entity2.type, entity1.type)
        
        if pair in type_pairs:
            return type_pairs[pair]
        elif reverse_pair in type_pairs:
            return type_pairs[reverse_pair]
        else:
            return "RELATED_TO"
    
    def _calculate_relationship_confidence(
        self, 
        text: str, 
        entity1_name: str, 
        entity2_name: str
    ) -> float:
        """Calculate confidence based on entity proximity in text"""
        # Find positions of entities
        pos1 = text.find(entity1_name.lower())
        pos2 = text.find(entity2_name.lower())
        
        if pos1 == -1 or pos2 == -1:
            return 0.0
        
        # Calculate distance between entities
        distance = abs(pos2 - pos1)
        text_length = len(text)
        
        # Normalize distance
        normalized_distance = distance / text_length if text_length > 0 else 1.0
        
        # Convert to confidence (closer = higher confidence)
        confidence = 1.0 - normalized_distance
        
        # Boost confidence if entities appear in same sentence
        sentences = text.split('.')
        for sentence in sentences:
            if (entity1_name.lower() in sentence.lower() and 
                entity2_name.lower() in sentence.lower()):
                confidence = min(confidence + 0.2, 1.0)
                break
        
        return confidence
    
    def _extract_relationship_context(
        self, 
        text: str, 
        entity1_name: str, 
        entity2_name: str,
        context_window: int = 100
    ) -> str:
        """Extract text context around entity mentions"""
        text_lower = text.lower()
        entity1_lower = entity1_name.lower()
        entity2_lower = entity2_name.lower()
        
        # Find positions
        pos1 = text_lower.find(entity1_lower)
        pos2 = text_lower.find(entity2_lower)
        
        if pos1 == -1 or pos2 == -1:
            return ""
        
        # Get context around both entities
        start = max(0, min(pos1, pos2) - context_window)
        end = min(len(text), max(pos1 + len(entity1_name), pos2 + len(entity2_name)) + context_window)
        
        context = text[start:end].strip()
        
        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context


class VectorEntityMatcher:
    """Entity matcher using vector embeddings for semantic similarity"""
    
    def __init__(
        self, 
        embedding_provider: EmbeddingProvider,
        similarity_threshold: float = 0.8
    ):
        """
        Initialize vector entity matcher
        
        Args:
            embedding_provider: Provider for generating embeddings
            similarity_threshold: Minimum cosine similarity for matches
        """
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold
        self._embedding_cache: Dict[str, List[float]] = {}
    
    def get_entity_embedding(self, entity: Entity) -> List[float]:
        """
        Get embedding for an entity
        
        Args:
            entity: Entity to embed
            
        Returns:
            Embedding vector
        """
        # Create cache key
        cache_key = f"{entity.name}_{entity.type.value}_{entity.description or ''}"
        
        # Check cache
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        # Create entity text representation
        entity_text = self._create_entity_text(entity)
        
        # Generate embedding
        embedding = self.embedding_provider.embed(entity_text)
        
        # Cache result
        self._embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _create_entity_text(self, entity: Entity) -> str:
        """Create text representation of entity for embedding"""
        parts = [
            f"{entity.type.value}: {entity.name}"
        ]
        
        if entity.description:
            parts.append(f"Description: {entity.description}")
        
        if hasattr(entity, 'aliases') and entity.aliases:
            parts.append(f"Also known as: {', '.join(entity.aliases)}")
        
        if entity.wikipedia_url:
            parts.append(f"Wikipedia: {entity.wikipedia_url}")
        
        return " | ".join(parts)
    
    def calculate_cosine_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score
        """
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have same dimension")
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Calculate magnitudes
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        return dot_product / (magnitude1 * magnitude2)
    
    def find_similar_entities(
        self, 
        query_entity: Entity, 
        candidate_entities: List[Entity],
        top_k: int = 5
    ) -> List[Tuple[Entity, float]]:
        """
        Find entities similar to query entity using embeddings
        
        Args:
            query_entity: Entity to find matches for
            candidate_entities: List of entities to search
            top_k: Number of top matches to return
            
        Returns:
            List of (entity, similarity_score) tuples
        """
        # Get query embedding
        query_embedding = self.get_entity_embedding(query_entity)
        
        # Calculate similarities
        similarities = []
        for candidate in candidate_entities:
            # Skip same entity
            if candidate.id == query_entity.id:
                continue
            
            # Get candidate embedding
            candidate_embedding = self.get_entity_embedding(candidate)
            
            # Calculate similarity
            similarity = self.calculate_cosine_similarity(
                query_embedding, 
                candidate_embedding
            )
            
            if similarity >= self.similarity_threshold:
                similarities.append((candidate, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k
        return similarities[:top_k]
    
    def cluster_entities(
        self, 
        entities: List[Entity],
        min_cluster_size: int = 2
    ) -> List[List[Entity]]:
        """
        Cluster entities based on semantic similarity
        
        Args:
            entities: List of entities to cluster
            min_cluster_size: Minimum size for a cluster
            
        Returns:
            List of entity clusters
        """
        if len(entities) < min_cluster_size:
            return [entities] if entities else []
        
        # Get embeddings for all entities
        entity_embeddings = [
            (entity, self.get_entity_embedding(entity)) 
            for entity in entities
        ]
        
        # Simple clustering algorithm (can be replaced with more sophisticated methods)
        clusters = []
        assigned = set()
        
        for i, (entity1, embedding1) in enumerate(entity_embeddings):
            if entity1.id in assigned:
                continue
            
            # Start new cluster
            cluster = [entity1]
            assigned.add(entity1.id)
            
            # Find similar entities
            for j, (entity2, embedding2) in enumerate(entity_embeddings[i+1:], i+1):
                if entity2.id in assigned:
                    continue
                
                similarity = self.calculate_cosine_similarity(embedding1, embedding2)
                if similarity >= self.similarity_threshold:
                    cluster.append(entity2)
                    assigned.add(entity2.id)
            
            if len(cluster) >= min_cluster_size:
                clusters.append(cluster)
        
        # Add unclustered entities as single-item clusters if needed
        for entity in entities:
            if entity.id not in assigned:
                clusters.append([entity])
        
        return clusters
    
    def find_cross_type_relationships(
        self, 
        entities: List[Entity]
    ) -> List[EntityRelationship]:
        """
        Find relationships between entities of different types using embeddings
        
        Args:
            entities: List of entities
            
        Returns:
            List of cross-type relationships
        """
        relationships = []
        
        # Group entities by type
        entities_by_type: Dict[EntityType, List[Entity]] = {}
        for entity in entities:
            if entity.type not in entities_by_type:
                entities_by_type[entity.type] = []
            entities_by_type[entity.type].append(entity)
        
        # Find relationships between different types
        entity_types = list(entities_by_type.keys())
        for i, type1 in enumerate(entity_types):
            for type2 in entity_types[i+1:]:
                # Compare entities of different types
                for entity1 in entities_by_type[type1]:
                    embedding1 = self.get_entity_embedding(entity1)
                    
                    for entity2 in entities_by_type[type2]:
                        embedding2 = self.get_entity_embedding(entity2)
                        
                        similarity = self.calculate_cosine_similarity(
                            embedding1, 
                            embedding2
                        )
                        
                        if similarity >= self.similarity_threshold:
                            rel_type = self._determine_semantic_relationship(
                                entity1, entity2, similarity
                            )
                            
                            relationships.append(EntityRelationship(
                                source_id=entity1.id,
                                target_id=entity2.id,
                                relationship_type=rel_type,
                                confidence=similarity
                            ))
        
        return relationships
    
    def _determine_semantic_relationship(
        self, 
        entity1: Entity, 
        entity2: Entity, 
        similarity: float
    ) -> str:
        """Determine relationship type based on semantic similarity and entity types"""
        # High similarity suggests strong semantic connection
        if similarity > 0.9:
            return "STRONGLY_RELATED_TO"
        elif similarity > 0.85:
            return "RELATED_TO"
        else:
            return "ASSOCIATED_WITH"
    
    def merge_entity_clusters(
        self, 
        clusters: List[List[Entity]],
        resolver: EntityResolver
    ) -> List[Entity]:
        """
        Merge entity clusters into single entities
        
        Args:
            clusters: List of entity clusters
            resolver: Entity resolver for merging logic
            
        Returns:
            List of merged entities
        """
        merged_entities = []
        
        for cluster in clusters:
            if len(cluster) == 1:
                merged_entities.append(cluster[0])
            else:
                # Sort by confidence to pick primary entity
                cluster.sort(key=lambda e: e.confidence, reverse=True)
                
                # Merge all entities into the primary one
                primary = cluster[0]
                for duplicate in cluster[1:]:
                    primary = resolver.merge_entities(primary, duplicate)
                
                merged_entities.append(primary)
        
        return merged_entities