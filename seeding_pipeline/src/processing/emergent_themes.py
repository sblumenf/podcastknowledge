"""Emergent theme detection from concept interactions."""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
import numpy as np
import networkx as nx
from scipy.spatial.distance import cosine

from src.core.models import Entity, Insight, Segment
# Provider imports removed - using services directly
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmergentThemeDetector:
    """
    Identifies implicit themes by analyzing concept clusters,
    co-occurrence patterns, and semantic fields.
    Discovers what the conversation is "really about" beyond surface topics.
    """
    
    def __init__(self, embedding_provider: Optional[Any] = None, 
                 llm_provider: Optional[Any] = None):
        """
        Initialize the emergent theme detector.
        
        Args:
            embedding_provider: Provider for generating embeddings
            llm_provider: Provider for generating field descriptions
        """
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
    
    def analyze_concept_clusters(
        self, 
        entities: List[Entity], 
        co_occurrences: List[Dict]
    ) -> List[Dict]:
        """
        Group entities into semantic clusters.
        
        Args:
            entities: List of entities to cluster
            co_occurrences: List of co-occurrence data
            
        Returns:
            List of coherent concept clusters with member entities
        """
        if not entities:
            return []
        
        # Build co-occurrence graph
        G = nx.Graph()
        
        # Add nodes
        for entity in entities:
            G.add_node(entity.id, entity=entity)
        
        # Add edges from co-occurrences
        for co_occ in co_occurrences:
            entity1_id = co_occ.get("entity1_id")
            entity2_id = co_occ.get("entity2_id")
            weight = co_occ.get("weight", 1.0)
            
            if entity1_id and entity2_id and entity1_id in G and entity2_id in G:
                G.add_edge(entity1_id, entity2_id, weight=weight)
        
        # Apply community detection at multiple resolutions
        clusters = []
        resolutions = [0.5, 1.0, 1.5]  # Different granularity levels
        
        for resolution in resolutions:
            try:
                # Use Louvain community detection
                import community as community_louvain
                partition = community_louvain.best_partition(G, resolution=resolution)
                
                # Group entities by community
                communities = defaultdict(list)
                for node_id, comm_id in partition.items():
                    entity = G.nodes[node_id]["entity"]
                    communities[f"res_{resolution}_comm_{comm_id}"].append(entity)
                
                # Calculate cluster coherence and filter
                for cluster_id, cluster_entities in communities.items():
                    if len(cluster_entities) < 2:  # Skip single-entity clusters
                        continue
                    
                    coherence = self._calculate_cluster_coherence(cluster_entities)
                    if coherence > 0.6:  # Threshold for significant clusters
                        clusters.append({
                            "cluster_id": cluster_id,
                            "entities": cluster_entities,
                            "size": len(cluster_entities),
                            "coherence": coherence,
                            "resolution": resolution
                        })
            except:
                # Fallback to connected components if community detection fails
                components = nx.connected_components(G)
                for i, component in enumerate(components):
                    cluster_entities = [G.nodes[node_id]["entity"] for node_id in component]
                    if len(cluster_entities) >= 2:
                        clusters.append({
                            "cluster_id": f"component_{i}",
                            "entities": cluster_entities,
                            "size": len(cluster_entities),
                            "coherence": self._calculate_cluster_coherence(cluster_entities),
                            "resolution": "connected_components"
                        })
        
        # Remove duplicate clusters
        unique_clusters = self._deduplicate_clusters(clusters)
        
        return unique_clusters
    
    def _calculate_cluster_coherence(self, entities: List[Entity]) -> float:
        """Calculate semantic coherence of a cluster using embeddings."""
        if not entities or not self.embedding_provider:
            return 0.5
        
        # Get embeddings
        embeddings = []
        for entity in entities:
            if hasattr(entity, 'embedding') and entity.embedding:
                embeddings.append(np.array(entity.embedding))
        
        if len(embeddings) < 2:
            return 0.5
        
        # Calculate average pairwise similarity
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = 1 - cosine(embeddings[i], embeddings[j])
                similarities.append(sim)
        
        return np.mean(similarities) if similarities else 0.5
    
    def _deduplicate_clusters(self, clusters: List[Dict]) -> List[Dict]:
        """Remove duplicate clusters based on entity overlap."""
        unique_clusters = []
        seen_entity_sets = []
        
        for cluster in sorted(clusters, key=lambda x: x["coherence"], reverse=True):
            entity_ids = {e.id for e in cluster["entities"]}
            
            # Check if this cluster significantly overlaps with existing ones
            is_duplicate = False
            for seen_set in seen_entity_sets:
                overlap = len(entity_ids & seen_set) / len(entity_ids)
                if overlap > 0.8:  # 80% overlap threshold
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_clusters.append(cluster)
                seen_entity_sets.append(entity_ids)
        
        return unique_clusters
    
    def extract_semantic_fields(
        self, 
        clusters: List[Dict], 
        entities: List[Entity]
    ) -> List[Dict]:
        """
        Identify the semantic field each cluster represents.
        
        Args:
            clusters: List of concept clusters
            entities: All entities for reference
            
        Returns:
            List of semantic fields with metadata
        """
        semantic_fields = []
        
        for cluster in clusters:
            cluster_entities = cluster["entities"]
            
            # Get embeddings for cluster
            embeddings = []
            entity_names = []
            for entity in cluster_entities:
                if hasattr(entity, 'embedding') and entity.embedding:
                    embeddings.append(np.array(entity.embedding))
                    entity_names.append(entity.name)
            
            if not embeddings:
                continue
            
            # Find semantic centroid
            centroid = np.mean(embeddings, axis=0)
            
            # Generate field description
            field_description = self._generate_field_description(
                entity_names, 
                cluster_entities
            )
            
            # Identify key vs peripheral concepts
            key_concepts = []
            peripheral_concepts = []
            
            for entity, embedding in zip(cluster_entities, embeddings):
                distance_to_centroid = cosine(embedding, centroid)
                if distance_to_centroid < 0.3:  # Close to center
                    key_concepts.append(entity.name)
                else:
                    peripheral_concepts.append(entity.name)
            
            semantic_fields.append({
                "cluster_id": cluster["cluster_id"],
                "semantic_field": field_description,
                "confidence": cluster["coherence"],
                "key_concepts": key_concepts[:5],  # Top 5
                "peripheral_concepts": peripheral_concepts[:5],  # Top 5
                "centroid_embedding": centroid.tolist()
            })
        
        return semantic_fields
    
    def _generate_field_description(
        self, 
        entity_names: List[str], 
        entities: List[Entity]
    ) -> str:
        """Generate semantic field description."""
        if self.llm_provider:
            # Use LLM to generate description
            prompt = f"""Given these related concepts: {', '.join(entity_names[:10])}
            
What semantic field or abstract theme do they represent? Provide a 2-3 word description.
Examples: "technological disruption", "social dynamics", "economic uncertainty"

Semantic field:"""
            
            try:
                response = self.llm_provider.generate(prompt, max_tokens=20)
                return response.strip()
            except:
                pass
        
        # Fallback: Use most common entity types
        types = [e.type for e in entities if e.type]
        if types:
            type_counts = Counter(types)
            dominant_type = type_counts.most_common(1)[0][0]
            return f"{dominant_type.lower()} concepts"
        
        return "related concepts"
    
    def detect_cross_cluster_patterns(
        self, 
        clusters: List[Dict], 
        insights: List[Insight]
    ) -> List[Dict]:
        """
        Find patterns that span multiple concept clusters.
        
        Args:
            clusters: List of concept clusters
            insights: List of insights for pattern detection
            
        Returns:
            List of cross-cluster patterns
        """
        patterns = []
        
        # Build entity to cluster mapping
        entity_to_cluster = {}
        for cluster in clusters:
            for entity in cluster["entities"]:
                entity_to_cluster[entity.id] = cluster["cluster_id"]
        
        # Detect causal chains
        causal_patterns = self._detect_causal_chains(clusters, insights, entity_to_cluster)
        patterns.extend(causal_patterns)
        
        # Detect tensions/oppositions
        tension_patterns = self._detect_tensions(clusters, insights)
        patterns.extend(tension_patterns)
        
        # Detect dependencies
        dependency_patterns = self._detect_dependencies(clusters, insights, entity_to_cluster)
        patterns.extend(dependency_patterns)
        
        # Detect emergence patterns
        emergence_patterns = self._detect_emergence(clusters, insights)
        patterns.extend(emergence_patterns)
        
        return patterns
    
    def _detect_causal_chains(
        self, 
        clusters: List[Dict], 
        insights: List[Insight],
        entity_to_cluster: Dict
    ) -> List[Dict]:
        """Detect causal relationships between clusters."""
        causal_patterns = []
        
        # Look for causal language in insights
        causal_keywords = ["causes", "leads to", "results in", "drives", "impacts", "affects"]
        
        for insight in insights:
            description = insight.description.lower()
            
            # Check if insight contains causal language
            if any(keyword in description for keyword in causal_keywords):
                # Get entities mentioned in insight
                mentioned_entities = insight.supporting_entities or []
                mentioned_clusters = set()
                
                for entity_id in mentioned_entities:
                    if entity_id in entity_to_cluster:
                        mentioned_clusters.add(entity_to_cluster[entity_id])
                
                if len(mentioned_clusters) >= 2:
                    causal_patterns.append({
                        "pattern_type": "causal_chain",
                        "involved_clusters": list(mentioned_clusters),
                        "evidence": insight.description,
                        "strength": insight.confidence_score,
                        "insight_id": insight.id
                    })
        
        return causal_patterns
    
    def _detect_tensions(self, clusters: List[Dict], insights: List[Insight]) -> List[Dict]:
        """Detect opposing or conflicting clusters."""
        tension_patterns = []
        
        # Look for opposition language
        opposition_keywords = ["versus", "vs", "conflict", "tension", "opposing", "contrary", "debate"]
        
        for insight in insights:
            description = insight.description.lower()
            
            if any(keyword in description for keyword in opposition_keywords):
                tension_patterns.append({
                    "pattern_type": "tension",
                    "evidence": insight.description,
                    "strength": insight.confidence_score,
                    "insight_id": insight.id
                })
        
        return tension_patterns
    
    def _detect_dependencies(
        self, 
        clusters: List[Dict], 
        insights: List[Insight],
        entity_to_cluster: Dict
    ) -> List[Dict]:
        """Detect dependency relationships between clusters."""
        dependency_patterns = []
        
        # Look for dependency language
        dependency_keywords = ["requires", "depends on", "needs", "prerequisite", "based on"]
        
        for insight in insights:
            description = insight.description.lower()
            
            if any(keyword in description for keyword in dependency_keywords):
                mentioned_entities = insight.supporting_entities or []
                mentioned_clusters = set()
                
                for entity_id in mentioned_entities:
                    if entity_id in entity_to_cluster:
                        mentioned_clusters.add(entity_to_cluster[entity_id])
                
                if len(mentioned_clusters) >= 2:
                    dependency_patterns.append({
                        "pattern_type": "dependency",
                        "involved_clusters": list(mentioned_clusters),
                        "evidence": insight.description,
                        "strength": insight.confidence_score,
                        "insight_id": insight.id
                    })
        
        return dependency_patterns
    
    def _detect_emergence(self, clusters: List[Dict], insights: List[Insight]) -> List[Dict]:
        """Detect emergence of new concepts from cluster combinations."""
        emergence_patterns = []
        
        # Look for emergence language
        emergence_keywords = ["emerges", "creates", "forms", "generates", "produces", "synthesis"]
        
        for insight in insights:
            description = insight.description.lower()
            
            if any(keyword in description for keyword in emergence_keywords):
                emergence_patterns.append({
                    "pattern_type": "emergence",
                    "evidence": insight.description,
                    "strength": insight.confidence_score,
                    "insight_id": insight.id
                })
        
        return emergence_patterns
    
    def extract_implicit_messages(
        self, 
        semantic_fields: List[Dict], 
        discourse_flow: Dict
    ) -> List[Dict]:
        """
        Identify messages not explicitly stated.
        
        Args:
            semantic_fields: List of semantic fields
            discourse_flow: Discourse flow analysis results
            
        Returns:
            List of implicit messages with evidence
        """
        implicit_messages = []
        
        # Look for recurring semantic patterns
        field_patterns = self._find_recurring_patterns(semantic_fields)
        
        # Analyze emotional undertones
        emotional_messages = self._analyze_emotional_undertones(semantic_fields)
        implicit_messages.extend(emotional_messages)
        
        # Identify value judgments
        value_messages = self._identify_value_judgments(semantic_fields, discourse_flow)
        implicit_messages.extend(value_messages)
        
        # Detect unstated assumptions
        assumption_messages = self._detect_unstated_assumptions(semantic_fields, field_patterns)
        implicit_messages.extend(assumption_messages)
        
        # Deduplicate and rank by confidence
        unique_messages = self._deduplicate_messages(implicit_messages)
        
        return sorted(unique_messages, key=lambda x: x["confidence"], reverse=True)
    
    def _find_recurring_patterns(self, semantic_fields: List[Dict]) -> List[Dict]:
        """Find patterns that recur across semantic fields."""
        patterns = []
        
        # Group fields by similarity
        if len(semantic_fields) < 2:
            return patterns
        
        # Look for fields that appear together frequently
        field_pairs = []
        for i in range(len(semantic_fields)):
            for j in range(i + 1, len(semantic_fields)):
                field1 = semantic_fields[i]
                field2 = semantic_fields[j]
                
                # Check concept overlap
                key_overlap = set(field1["key_concepts"]) & set(field2["key_concepts"])
                if len(key_overlap) > 0:
                    field_pairs.append({
                        "field1": field1["semantic_field"],
                        "field2": field2["semantic_field"],
                        "overlap": list(key_overlap),
                        "strength": len(key_overlap) / min(len(field1["key_concepts"]), 
                                                         len(field2["key_concepts"]))
                    })
        
        return field_pairs
    
    def _analyze_emotional_undertones(self, semantic_fields: List[Dict]) -> List[Dict]:
        """Analyze emotional content of semantic fields."""
        messages = []
        
        # Emotional indicator words
        positive_indicators = ["success", "innovation", "growth", "opportunity", "benefit"]
        negative_indicators = ["challenge", "risk", "concern", "problem", "threat"]
        neutral_indicators = ["change", "transition", "development", "evolution"]
        
        for field in semantic_fields:
            all_concepts = field["key_concepts"] + field["peripheral_concepts"]
            concepts_lower = [c.lower() for c in all_concepts]
            
            positive_count = sum(1 for indicator in positive_indicators 
                               if any(indicator in concept for concept in concepts_lower))
            negative_count = sum(1 for indicator in negative_indicators 
                               if any(indicator in concept for concept in concepts_lower))
            
            if positive_count > negative_count * 2:
                messages.append({
                    "implicit_message": f"Optimistic view of {field['semantic_field']}",
                    "supporting_evidence": all_concepts,
                    "confidence": 0.7,
                    "interpretation": f"The discussion frames {field['semantic_field']} in predominantly positive terms"
                })
            elif negative_count > positive_count * 2:
                messages.append({
                    "implicit_message": f"Cautionary stance on {field['semantic_field']}",
                    "supporting_evidence": all_concepts,
                    "confidence": 0.7,
                    "interpretation": f"The discussion emphasizes risks and challenges in {field['semantic_field']}"
                })
        
        return messages
    
    def _identify_value_judgments(
        self, 
        semantic_fields: List[Dict], 
        discourse_flow: Dict
    ) -> List[Dict]:
        """Identify implicit value judgments in concept relationships."""
        messages = []
        
        # Look for evaluative language patterns
        for field in semantic_fields:
            if field["confidence"] > 0.7:
                # Check if field name contains evaluative terms
                field_name = field["semantic_field"].lower()
                if any(term in field_name for term in ["good", "bad", "right", "wrong", "should"]):
                    messages.append({
                        "implicit_message": f"Normative stance on {field['semantic_field']}",
                        "supporting_evidence": field["key_concepts"],
                        "confidence": field["confidence"],
                        "interpretation": "The discussion implies value judgments about this topic"
                    })
        
        return messages
    
    def _detect_unstated_assumptions(
        self, 
        semantic_fields: List[Dict], 
        field_patterns: List[Dict]
    ) -> List[Dict]:
        """Detect assumptions that underlie the discussion."""
        messages = []
        
        # Look for fields that are always discussed together
        for pattern in field_patterns:
            if pattern["strength"] > 0.5:
                messages.append({
                    "implicit_message": f"{pattern['field1']} inherently connected to {pattern['field2']}",
                    "supporting_evidence": pattern["overlap"],
                    "confidence": pattern["strength"],
                    "interpretation": "The discussion assumes these concepts are naturally linked"
                })
        
        return messages
    
    def _deduplicate_messages(self, messages: List[Dict]) -> List[Dict]:
        """Remove duplicate implicit messages."""
        unique_messages = []
        seen_messages = set()
        
        for message in messages:
            msg_key = message["implicit_message"].lower()
            if msg_key not in seen_messages:
                unique_messages.append(message)
                seen_messages.add(msg_key)
        
        return unique_messages
    
    def score_theme_emergence(
        self, 
        theme: Dict, 
        explicit_topics: List[str]
    ) -> float:
        """
        Measure how "emergent" vs explicit a theme is.
        
        Args:
            theme: Theme dictionary
            explicit_topics: List of explicitly stated topics
            
        Returns:
            Score between 0 (explicit) and 1 (fully emergent)
        """
        score_factors = []
        
        # Check absence from explicit topics
        theme_terms = theme.get("semantic_field", "").lower().split()
        explicit_terms = [topic.lower() for topic in explicit_topics]
        
        overlap_score = 0
        for term in theme_terms:
            if any(term in explicit for explicit in explicit_terms):
                overlap_score += 1
        
        absence_score = 1 - (overlap_score / len(theme_terms)) if theme_terms else 0.5
        score_factors.append(absence_score)
        
        # Check distribution across segments
        if "evidence_segments" in theme:
            segment_count = len(theme["evidence_segments"])
            distribution_score = min(segment_count / 10, 1.0)  # Normalize to max 10 segments
            score_factors.append(distribution_score)
        
        # Check if arises from interactions
        if theme.get("pattern_type") in ["emergence", "synthesis"]:
            score_factors.append(0.9)
        else:
            score_factors.append(0.5)
        
        # Check if explicitly named
        if theme.get("explicitly_named", False):
            score_factors.append(0.0)
        else:
            score_factors.append(1.0)
        
        # Calculate weighted average
        return np.mean(score_factors) if score_factors else 0.5
    
    def detect_metaphorical_themes(
        self, 
        segments: List[Segment], 
        entities: List[Entity]
    ) -> List[Dict]:
        """
        Identify recurring metaphors that reveal themes.
        
        Args:
            segments: List of segments
            entities: List of entities
            
        Returns:
            List of metaphorical themes
        """
        metaphorical_themes = []
        
        # Common metaphor families
        metaphor_families = {
            "journey": ["path", "road", "journey", "destination", "milestone", "crossroads"],
            "war": ["battle", "fight", "combat", "victory", "defeat", "strategy", "weapon"],
            "growth": ["grow", "seed", "bloom", "flourish", "root", "branch", "fertile"],
            "building": ["foundation", "build", "construct", "architect", "structure", "pillar"],
            "game": ["play", "rules", "win", "lose", "score", "team", "compete"],
            "machine": ["engine", "gear", "mechanism", "fuel", "drive", "operate"],
            "ecosystem": ["ecosystem", "environment", "evolve", "adapt", "balance", "symbiosis"]
        }
        
        # Count metaphor occurrences
        metaphor_counts = defaultdict(list)
        
        for segment in segments:
            text_lower = segment.text.lower()
            
            for family, keywords in metaphor_families.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        metaphor_counts[family].append({
                            "segment_index": segment.segment_index,
                            "keyword": keyword,
                            "context": segment.text[:100]  # First 100 chars for context
                        })
        
        # Analyze significant metaphor families
        for family, occurrences in metaphor_counts.items():
            if len(occurrences) >= 3:  # Threshold for significance
                # Link to concept clusters
                related_entities = self._find_metaphor_related_entities(
                    occurrences, entities, segments
                )
                
                metaphorical_themes.append({
                    "metaphor_family": family,
                    "occurrences": len(occurrences),
                    "segments": [occ["segment_index"] for occ in occurrences],
                    "keywords_used": list(set(occ["keyword"] for occ in occurrences)),
                    "related_concepts": [e.name for e in related_entities[:5]],
                    "thematic_implication": self._interpret_metaphor(family, len(occurrences)),
                    "confidence": min(len(occurrences) / 10, 1.0)  # Normalize confidence
                })
        
        return metaphorical_themes
    
    def _find_metaphor_related_entities(
        self, 
        occurrences: List[Dict], 
        entities: List[Entity],
        segments: List[Segment]
    ) -> List[Entity]:
        """Find entities related to metaphor occurrences."""
        related_entities = []
        occurrence_segments = {occ["segment_index"] for occ in occurrences}
        
        # Find entities mentioned in same segments as metaphors
        for entity in entities:
            entity_segments = set()
            
            # Check which segments mention this entity
            for i, segment in enumerate(segments):
                if entity.name.lower() in segment.text.lower():
                    entity_segments.add(i)
            
            # Calculate overlap with metaphor segments
            overlap = len(entity_segments & occurrence_segments)
            if overlap > 0:
                related_entities.append((entity, overlap))
        
        # Sort by overlap count
        related_entities.sort(key=lambda x: x[1], reverse=True)
        
        return [entity for entity, _ in related_entities]
    
    def _interpret_metaphor(self, family: str, count: int) -> str:
        """Generate thematic interpretation of metaphor usage."""
        interpretations = {
            "journey": "underlying theme of progression and transformation",
            "war": "underlying theme of conflict and competition",
            "growth": "underlying theme of development and potential",
            "building": "underlying theme of construction and stability",
            "game": "underlying theme of strategy and competition",
            "machine": "underlying theme of efficiency and systems",
            "ecosystem": "underlying theme of interconnection and balance"
        }
        
        base = interpretations.get(family, "recurring metaphorical pattern")
        intensity = "strong" if count >= 5 else "moderate"
        
        return f"{intensity} {base}"
    
    def track_theme_evolution(
        self, 
        emergent_themes: List[Dict], 
        segments: List[Segment]
    ) -> Dict:
        """
        Track how emergent themes develop through conversation.
        
        Args:
            emergent_themes: List of detected emergent themes
            segments: List of segments
            
        Returns:
            Theme evolution tracking data
        """
        evolution_data = {}
        
        for theme in emergent_themes:
            theme_id = theme.get("cluster_id", theme.get("theme_id", "unknown"))
            
            # Track when theme first emerges
            first_emergence = self._find_first_emergence(theme, segments)
            
            # Track strength over time
            strength_timeline = self._track_theme_strength(theme, segments)
            
            # Track contributing concepts
            contributing_concepts = self._track_contributing_concepts(theme, segments)
            
            # Check if explicitly acknowledged
            explicit_acknowledgment = self._check_explicit_acknowledgment(theme, segments)
            
            evolution_data[theme_id] = {
                "first_emergence": first_emergence,
                "strength_timeline": strength_timeline,
                "contributing_concepts": contributing_concepts,
                "explicit_acknowledgment": explicit_acknowledgment,
                "evolution_pattern": self._classify_evolution_pattern(strength_timeline)
            }
        
        return evolution_data
    
    def _find_first_emergence(self, theme: Dict, segments: List[Segment]) -> Dict:
        """Find when theme first emerges."""
        # Get theme-related concepts
        key_concepts = theme.get("key_concepts", [])
        
        for i, segment in enumerate(segments):
            segment_lower = segment.text.lower()
            
            # Check if any key concepts appear
            for concept in key_concepts:
                if concept.lower() in segment_lower:
                    return {
                        "segment_index": i,
                        "timestamp": segment.start_time,
                        "emergence_type": "implicit",
                        "triggering_concept": concept
                    }
        
        return {"segment_index": -1, "emergence_type": "not_found"}
    
    def _track_theme_strength(self, theme: Dict, segments: List[Segment]) -> List[float]:
        """Track theme strength over conversation."""
        strength_timeline = []
        key_concepts = theme.get("key_concepts", [])
        
        for segment in segments:
            segment_lower = segment.text.lower()
            
            # Count concept mentions
            mention_count = sum(1 for concept in key_concepts 
                              if concept.lower() in segment_lower)
            
            # Normalize by segment length and concept count
            if key_concepts:
                strength = mention_count / (len(key_concepts) * max(len(segment_lower.split()) / 100, 1))
            else:
                strength = 0.0
            
            strength_timeline.append(min(strength, 1.0))
        
        return strength_timeline
    
    def _track_contributing_concepts(
        self, 
        theme: Dict, 
        segments: List[Segment]
    ) -> List[Dict]:
        """Track which concepts contribute to theme over time."""
        contributions = []
        key_concepts = theme.get("key_concepts", [])
        
        for i, segment in enumerate(segments):
            segment_lower = segment.text.lower()
            
            contributing = []
            for concept in key_concepts:
                if concept.lower() in segment_lower:
                    contributing.append(concept)
            
            if contributing:
                contributions.append({
                    "segment_index": i,
                    "concepts": contributing,
                    "contribution_strength": len(contributing) / len(key_concepts)
                })
        
        return contributions
    
    def _check_explicit_acknowledgment(self, theme: Dict, segments: List[Segment]) -> Optional[Dict]:
        """Check if theme gets explicitly acknowledged."""
        theme_field = theme.get("semantic_field", "")
        
        # Look for explicit mentions of the theme
        acknowledgment_phrases = [
            "this is really about",
            "what we're talking about is",
            "the underlying theme",
            "this comes down to",
            "at its core"
        ]
        
        for i, segment in enumerate(segments):
            segment_lower = segment.text.lower()
            
            for phrase in acknowledgment_phrases:
                if phrase in segment_lower:
                    # Check if theme-related terms appear nearby
                    if any(term.lower() in segment_lower for term in theme_field.split()):
                        return {
                            "segment_index": i,
                            "acknowledgment_type": "explicit",
                            "phrase": phrase
                        }
        
        return None
    
    def _classify_evolution_pattern(self, strength_timeline: List[float]) -> str:
        """Classify how theme evolves over time."""
        if not strength_timeline:
            return "unknown"
        
        # Calculate trend
        if len(strength_timeline) >= 3:
            first_third = np.mean(strength_timeline[:len(strength_timeline)//3])
            last_third = np.mean(strength_timeline[-len(strength_timeline)//3:])
            peak = max(strength_timeline)
            peak_position = strength_timeline.index(peak) / len(strength_timeline)
            
            if last_third > first_third * 1.5:
                return "crescendo"  # Builds over time
            elif first_third > last_third * 1.5:
                return "diminuendo"  # Fades over time
            elif peak_position < 0.3:
                return "front-loaded"  # Strong start then maintained
            elif peak_position > 0.7:
                return "climactic"  # Builds to climax
            elif max(strength_timeline) > np.mean(strength_timeline) * 2:
                return "punctuated"  # Sporadic peaks
            else:
                return "steady"  # Consistent throughout
        
        return "brief"  # Too short to classify
    
    def validate_emergent_themes(
        self, 
        themes: List[Dict], 
        segments: List[Segment], 
        insights: List[Insight]
    ) -> List[Dict]:
        """
        Ensure detected themes are genuine, not artifacts.
        
        Args:
            themes: List of emergent themes to validate
            segments: List of segments
            insights: List of insights
            
        Returns:
            Validated themes with validation scores
        """
        validated_themes = []
        
        for theme in themes:
            validation_score = 0.0
            validation_evidence = []
            
            # Check multiple evidence sources
            evidence_score = self._check_evidence_sources(theme, segments, insights)
            validation_score += evidence_score * 0.3
            validation_evidence.append(f"Evidence sources: {evidence_score:.2f}")
            
            # Check coherence across conversation
            coherence_score = self._check_theme_coherence(theme, segments)
            validation_score += coherence_score * 0.3
            validation_evidence.append(f"Coherence: {coherence_score:.2f}")
            
            # Check for contradictions
            contradiction_score = self._check_contradictions(theme, segments, insights)
            validation_score += contradiction_score * 0.2
            validation_evidence.append(f"No contradictions: {contradiction_score:.2f}")
            
            # Check statistical significance
            significance_score = self._check_statistical_significance(theme, segments)
            validation_score += significance_score * 0.2
            validation_evidence.append(f"Statistical significance: {significance_score:.2f}")
            
            # Only include themes with sufficient validation
            if validation_score >= 0.6:
                theme["validation_score"] = validation_score
                theme["validation_evidence"] = validation_evidence
                theme["is_validated"] = True
                validated_themes.append(theme)
        
        return validated_themes
    
    def _check_evidence_sources(
        self, 
        theme: Dict, 
        segments: List[Segment], 
        insights: List[Insight]
    ) -> float:
        """Check if theme has multiple independent evidence sources."""
        evidence_types = set()
        
        # Check segment evidence
        if theme.get("evidence_segments"):
            evidence_types.add("segments")
        
        # Check insight evidence
        theme_concepts = set(theme.get("key_concepts", []))
        for insight in insights:
            insight_entities = set(insight.supporting_entities or [])
            if len(theme_concepts & insight_entities) > 0:
                evidence_types.add("insights")
                break
        
        # Check pattern evidence
        if theme.get("pattern_type"):
            evidence_types.add("patterns")
        
        # Check metaphor evidence
        if theme.get("metaphor_family"):
            evidence_types.add("metaphors")
        
        # Score based on number of evidence types
        return min(len(evidence_types) / 3, 1.0)
    
    def _check_theme_coherence(self, theme: Dict, segments: List[Segment]) -> float:
        """Check if theme is coherent across conversation."""
        if not theme.get("strength_timeline"):
            return 0.5
        
        timeline = theme["strength_timeline"]
        
        # Check for consistent presence
        presence_count = sum(1 for strength in timeline if strength > 0)
        presence_ratio = presence_count / len(timeline) if timeline else 0
        
        # Check for smooth evolution (not too jumpy)
        if len(timeline) > 1:
            differences = [abs(timeline[i+1] - timeline[i]) for i in range(len(timeline)-1)]
            smoothness = 1 - (np.mean(differences) / 0.5)  # Normalize by max expected jump
            smoothness = max(0, min(1, smoothness))
        else:
            smoothness = 0.5
        
        return (presence_ratio + smoothness) / 2
    
    def _check_contradictions(
        self, 
        theme: Dict, 
        segments: List[Segment], 
        insights: List[Insight]
    ) -> float:
        """Check if theme is contradicted by explicit statements."""
        contradiction_keywords = ["not", "isn't", "wrong", "opposite", "contrary", "however"]
        theme_field = theme.get("semantic_field", "").lower()
        
        contradiction_count = 0
        
        for segment in segments:
            segment_lower = segment.text.lower()
            
            # Check if contradiction keywords appear near theme concepts
            for keyword in contradiction_keywords:
                if keyword in segment_lower and any(
                    concept.lower() in segment_lower 
                    for concept in theme.get("key_concepts", [])
                ):
                    contradiction_count += 1
        
        # Return inverse score (fewer contradictions = higher score)
        max_contradictions = 5
        return max(0, 1 - (contradiction_count / max_contradictions))
    
    def _check_statistical_significance(self, theme: Dict, segments: List[Segment]) -> float:
        """Check statistical significance of theme patterns."""
        # Check cluster size
        cluster_size = len(theme.get("entities", theme.get("key_concepts", [])))
        size_score = min(cluster_size / 10, 1.0)  # Normalize to 10 concepts
        
        # Check pattern strength
        pattern_strength = theme.get("confidence", theme.get("coherence", 0.5))
        
        # Check frequency of appearance
        if theme.get("strength_timeline"):
            timeline = theme["strength_timeline"]
            frequency_score = sum(1 for s in timeline if s > 0.1) / len(timeline)
        else:
            frequency_score = 0.5
        
        return (size_score + pattern_strength + frequency_score) / 3
    
    def build_theme_hierarchy(self, emergent_themes: List[Dict]) -> Dict:
        """
        Organize themes into hierarchical structure.
        
        Args:
            emergent_themes: List of emergent themes
            
        Returns:
            Hierarchical theme structure
        """
        hierarchy = {
            "meta_themes": [],
            "primary_themes": [],
            "sub_themes": [],
            "micro_themes": []
        }
        
        if not emergent_themes:
            return hierarchy
        
        # Sort themes by scope and importance
        for theme in emergent_themes:
            scope_score = self._calculate_theme_scope(theme)
            theme["scope_score"] = scope_score
        
        # Classify into hierarchy levels
        sorted_themes = sorted(emergent_themes, key=lambda x: x["scope_score"], reverse=True)
        
        # Find relationships between themes
        theme_relationships = self._find_theme_relationships(sorted_themes)
        
        # Build hierarchy
        for i, theme in enumerate(sorted_themes):
            theme_with_relations = theme.copy()
            theme_with_relations["children"] = []
            theme_with_relations["parent"] = None
            
            # Assign to level based on scope
            if theme["scope_score"] > 0.8:
                hierarchy["meta_themes"].append(theme_with_relations)
                level = "meta"
            elif theme["scope_score"] > 0.6:
                hierarchy["primary_themes"].append(theme_with_relations)
                level = "primary"
            elif theme["scope_score"] > 0.4:
                hierarchy["sub_themes"].append(theme_with_relations)
                level = "sub"
            else:
                hierarchy["micro_themes"].append(theme_with_relations)
                level = "micro"
            
            # Add relationships
            for rel in theme_relationships:
                if rel["parent_id"] == theme.get("cluster_id"):
                    theme_with_relations["children"].append(rel["child_id"])
                elif rel["child_id"] == theme.get("cluster_id"):
                    theme_with_relations["parent"] = rel["parent_id"]
        
        return hierarchy
    
    def _calculate_theme_scope(self, theme: Dict) -> float:
        """Calculate how broad vs specific a theme is."""
        scope_factors = []
        
        # Number of concepts covered
        concept_count = len(theme.get("key_concepts", []))
        scope_factors.append(min(concept_count / 20, 1.0))
        
        # Number of segments where theme appears
        if theme.get("evidence_segments"):
            segment_count = len(theme["evidence_segments"])
            scope_factors.append(min(segment_count / 10, 1.0))
        
        # Abstractness of semantic field
        field = theme.get("semantic_field", "").lower()
        abstract_terms = ["concept", "system", "framework", "paradigm", "principle"]
        if any(term in field for term in abstract_terms):
            scope_factors.append(0.8)
        else:
            scope_factors.append(0.4)
        
        # Cross-cluster involvement
        if theme.get("pattern_type") in ["emergence", "synthesis"]:
            scope_factors.append(0.9)
        else:
            scope_factors.append(0.5)
        
        return np.mean(scope_factors) if scope_factors else 0.5
    
    def _find_theme_relationships(self, themes: List[Dict]) -> List[Dict]:
        """Find parent-child relationships between themes."""
        relationships = []
        
        for i, theme1 in enumerate(themes):
            theme1_concepts = set(theme1.get("key_concepts", []))
            
            for j, theme2 in enumerate(themes):
                if i == j:
                    continue
                
                theme2_concepts = set(theme2.get("key_concepts", []))
                
                # Check if theme2 is subset of theme1 (parent-child)
                if theme2_concepts and theme1_concepts:
                    overlap = len(theme2_concepts & theme1_concepts)
                    
                    if overlap > len(theme2_concepts) * 0.7:  # 70% overlap
                        # theme1 is parent of theme2
                        relationships.append({
                            "parent_id": theme1.get("cluster_id"),
                            "child_id": theme2.get("cluster_id"),
                            "relationship_type": "subsumes",
                            "strength": overlap / len(theme2_concepts)
                        })
        
        return relationships
    
    def generate_theme_summary(self, emergent_themes: List[Dict]) -> Dict:
        """
        Create interpretable summary of emergent themes.
        
        Args:
            emergent_themes: List of emergent themes
            
        Returns:
            Theme summary with interpretations
        """
        summary = {
            "major_themes": [],
            "theme_relationships": [],
            "overall_narrative": ""
        }
        
        if not emergent_themes:
            summary["overall_narrative"] = "No significant emergent themes detected."
            return summary
        
        # Sort by importance/emergence score
        sorted_themes = sorted(
            emergent_themes, 
            key=lambda x: x.get("emergence_score", 0.5) * x.get("confidence", 0.5), 
            reverse=True
        )
        
        # Extract major themes (top 5)
        for theme in sorted_themes[:5]:
            major_theme = {
                "theme": theme.get("semantic_field", "Unknown theme"),
                "emergence_score": theme.get("emergence_score", 0.5),
                "supporting_concepts": theme.get("key_concepts", [])[:5],
                "interpretation": self._generate_theme_interpretation(theme)
            }
            summary["major_themes"].append(major_theme)
        
        # Find theme relationships
        relationships = self._summarize_theme_relationships(sorted_themes)
        summary["theme_relationships"] = relationships
        
        # Generate overall narrative
        summary["overall_narrative"] = self._generate_overall_narrative(sorted_themes)
        
        return summary
    
    def _generate_theme_interpretation(self, theme: Dict) -> str:
        """Generate human-readable interpretation of a theme."""
        interpretations = []
        
        # Base interpretation on theme type
        if theme.get("pattern_type") == "emergence":
            interpretations.append("This theme emerges from the synthesis of multiple concepts")
        elif theme.get("pattern_type") == "tension":
            interpretations.append("This theme reflects underlying tensions in the discussion")
        
        # Add metaphor interpretation
        if theme.get("metaphor_family"):
            family = theme["metaphor_family"]
            interpretations.append(f"Recurring {family} metaphors reinforce this theme")
        
        # Add evolution interpretation
        if theme.get("evolution_pattern") == "crescendo":
            interpretations.append("The theme builds in importance throughout the discussion")
        elif theme.get("evolution_pattern") == "steady":
            interpretations.append("This theme maintains consistent presence")
        
        # Add validation interpretation
        if theme.get("validation_score", 0) > 0.8:
            interpretations.append("Strong evidence supports this as a genuine emergent theme")
        
        return ". ".join(interpretations) if interpretations else "Implicit theme detected through concept clustering"
    
    def _summarize_theme_relationships(self, themes: List[Dict]) -> List[Dict]:
        """Summarize relationships between themes."""
        relationships = []
        
        # Look for themes that appear together
        for i, theme1 in enumerate(themes[:5]):  # Top 5 themes
            for j, theme2 in enumerate(themes[:5]):
                if i >= j:
                    continue
                
                # Check concept overlap
                concepts1 = set(theme1.get("key_concepts", []))
                concepts2 = set(theme2.get("key_concepts", []))
                overlap = concepts1 & concepts2
                
                if len(overlap) > 0:
                    relationships.append({
                        "theme1": theme1.get("semantic_field"),
                        "theme2": theme2.get("semantic_field"),
                        "relationship": "share concepts",
                        "shared_concepts": list(overlap)[:3]
                    })
        
        return relationships
    
    def _generate_overall_narrative(self, themes: List[Dict]) -> str:
        """Generate overall narrative description of emergent themes."""
        if not themes:
            return "No clear emergent narrative detected."
        
        narrative_parts = []
        
        # Describe dominant theme
        dominant = themes[0]
        narrative_parts.append(
            f"The conversation implicitly explores {dominant.get('semantic_field', 'complex themes')}"
        )
        
        # Describe theme evolution
        evolution_patterns = [t.get("evolution_pattern") for t in themes[:3] 
                            if t.get("evolution_pattern")]
        if "crescendo" in evolution_patterns:
            narrative_parts.append("with themes building in intensity")
        elif "steady" in evolution_patterns:
            narrative_parts.append("with consistent thematic presence")
        
        # Describe theme relationships
        if len(themes) > 1:
            narrative_parts.append(f"while connecting {len(themes)} interrelated concepts")
        
        # Add emergence characteristic
        avg_emergence = np.mean([t.get("emergence_score", 0.5) for t in themes[:3]])
        if avg_emergence > 0.7:
            narrative_parts.append("through largely implicit means")
        
        return " ".join(narrative_parts) + "."
    
    def detect_themes(
        self,
        entities: List[Entity],
        insights: List[Insight],
        segments: List[Segment],
        co_occurrences: List[Dict],
        explicit_topics: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Main method to detect emergent themes.
        
        Args:
            entities: List of entities
            insights: List of insights
            segments: List of segments
            co_occurrences: Co-occurrence data
            explicit_topics: List of explicitly stated topics
            
        Returns:
            List of detected emergent themes
        """
        logger.info("Starting emergent theme detection")
        
        # Analyze concept clusters
        clusters = self.analyze_concept_clusters(entities, co_occurrences)
        logger.info(f"Found {len(clusters)} concept clusters")
        
        # Extract semantic fields
        semantic_fields = self.extract_semantic_fields(clusters, entities)
        logger.info(f"Extracted {len(semantic_fields)} semantic fields")
        
        # Detect cross-cluster patterns
        patterns = self.detect_cross_cluster_patterns(clusters, insights)
        logger.info(f"Detected {len(patterns)} cross-cluster patterns")
        
        # Extract implicit messages
        implicit_messages = self.extract_implicit_messages(
            semantic_fields, 
            {}  # Empty discourse flow for now
        )
        logger.info(f"Found {len(implicit_messages)} implicit messages")
        
        # Detect metaphorical themes
        metaphor_themes = self.detect_metaphorical_themes(segments, entities)
        logger.info(f"Found {len(metaphor_themes)} metaphorical themes")
        
        # Combine all theme sources
        all_themes = []
        
        # Add semantic field themes
        for field in semantic_fields:
            theme = field.copy()
            theme["theme_source"] = "semantic_field"
            theme["theme_id"] = field["cluster_id"]
            all_themes.append(theme)
        
        # Add pattern-based themes
        for pattern in patterns:
            theme = {
                "theme_id": f"pattern_{pattern['pattern_type']}_{len(all_themes)}",
                "semantic_field": f"{pattern['pattern_type']} relationship",
                "theme_source": "cross_cluster_pattern",
                "pattern_type": pattern["pattern_type"],
                "confidence": pattern["strength"],
                "evidence": pattern.get("evidence", "")
            }
            all_themes.append(theme)
        
        # Add metaphorical themes
        for metaphor in metaphor_themes:
            theme = {
                "theme_id": f"metaphor_{metaphor['metaphor_family']}",
                "semantic_field": f"{metaphor['metaphor_family']} metaphor",
                "theme_source": "metaphor",
                "metaphor_family": metaphor["metaphor_family"],
                "confidence": metaphor["confidence"],
                "key_concepts": metaphor["related_concepts"]
            }
            all_themes.append(theme)
        
        # Calculate emergence scores
        if explicit_topics is None:
            explicit_topics = []
        
        for theme in all_themes:
            theme["emergence_score"] = self.score_theme_emergence(theme, explicit_topics)
        
        # Track theme evolution
        evolution_data = self.track_theme_evolution(all_themes, segments)
        for theme in all_themes:
            theme_id = theme.get("theme_id", "")
            if theme_id in evolution_data:
                theme.update(evolution_data[theme_id])
        
        # Validate themes
        validated_themes = self.validate_emergent_themes(all_themes, segments, insights)
        logger.info(f"Validated {len(validated_themes)} themes")
        
        # Build hierarchy
        hierarchy = self.build_theme_hierarchy(validated_themes)
        
        # Generate summary
        summary = self.generate_theme_summary(validated_themes)
        
        # Return themes with metadata
        result = {
            "themes": validated_themes,
            "hierarchy": hierarchy,
            "summary": summary,
            "implicit_messages": implicit_messages
        }
        
        return result