"""
Multi-factor importance scoring for entities.

This module implements sophisticated importance calculation that considers:
- Frequency (normalized by episode length)
- Structural centrality (position in knowledge graph)
- Semantic centrality (embedding-based relationships)
- Discourse function (role in conversation)
- Temporal dynamics (when and how concepts are introduced)
- Cross-reference score (how often referenced by other entities/insights)
"""

import logging
import math
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import networkx as nx

from ..core.models import Entity, Insight, Segment

logger = logging.getLogger(__name__)


class ImportanceScorer:
    """
    Calculates multi-factor importance scores for entities based on:
    1. Frequency: How often mentioned (normalized by episode length)
    2. Structural Centrality: Position in knowledge graph
    3. Semantic Centrality: Embedding-based importance
    4. Discourse Function: Role in conversation (introduction, elaboration, conclusion)
    5. Temporal Dynamics: When and how concepts are introduced
    6. Cross-Reference Score: How often other concepts reference this one
    """
    
    def __init__(
        self,
        max_expected_mentions_per_minute: float = 2.0,
        embedding_dimension: int = 384,
        temporal_decay_alpha: float = 0.1
    ):
        """
        Initialize the ImportanceScorer.
        
        Args:
            max_expected_mentions_per_minute: Maximum expected mention frequency for normalization
            embedding_dimension: Dimension of entity embeddings
            temporal_decay_alpha: Decay factor for temporal recency calculations
        """
        self.max_expected_mentions_per_minute = max_expected_mentions_per_minute
        self.embedding_dimension = embedding_dimension
        self.temporal_decay_alpha = temporal_decay_alpha
        
    def calculate_frequency_factor(
        self, 
        entity_mentions: List[Dict[str, Any]], 
        episode_duration: float
    ) -> float:
        """
        Calculate normalized frequency score that accounts for episode length.
        
        Args:
            entity_mentions: List of mention dictionaries with segment info
            episode_duration: Total episode duration in seconds
            
        Returns:
            Frequency factor between 0 and 1
        """
        if episode_duration <= 0:
            logger.warning(f"Invalid episode duration: {episode_duration}")
            return 0.0
            
        total_mentions = len(entity_mentions)
        duration_minutes = episode_duration / 60.0
        
        # Calculate mentions per minute
        mentions_per_minute = total_mentions / duration_minutes
        
        # Apply logarithmic scaling to prevent frequency dominance
        # log(1 + mentions_per_minute) / log(1 + max_expected_frequency)
        normalized_score = (
            math.log(1 + mentions_per_minute) / 
            math.log(1 + self.max_expected_mentions_per_minute)
        )
        
        # Clamp between 0 and 1
        return min(1.0, max(0.0, normalized_score))
    
    def calculate_structural_centrality(
        self, 
        entity_id: str, 
        graph: nx.Graph
    ) -> float:
        """
        Measure how central the entity is in the knowledge structure.
        
        Args:
            entity_id: ID of the entity to analyze
            graph: NetworkX graph containing entities and relationships
            
        Returns:
            Centrality factor between 0 and 1
        """
        if not graph.has_node(entity_id):
            logger.warning(f"Entity {entity_id} not found in graph")
            return 0.0
            
        try:
            # Calculate different centrality measures
            degree_cent = nx.degree_centrality(graph).get(entity_id, 0.0)
            
            # Betweenness centrality: how often this entity bridges other concepts
            between_cent = nx.betweenness_centrality(graph).get(entity_id, 0.0)
            
            # Eigenvector centrality: connection to other important entities
            # Handle case where graph might be disconnected
            try:
                eigen_cent = nx.eigenvector_centrality(graph, max_iter=1000).get(entity_id, 0.0)
            except nx.PowerIterationFailedConvergence:
                logger.warning("Eigenvector centrality failed to converge, using degree centrality")
                eigen_cent = degree_cent
            except:
                eigen_cent = 0.0
                
            # Combine with weights
            # Betweenness is most important for knowledge bridging
            weighted_score = (
                0.3 * degree_cent +
                0.5 * between_cent +
                0.2 * eigen_cent
            )
            
            return min(1.0, weighted_score)
            
        except Exception as e:
            logger.error(f"Error calculating structural centrality: {e}")
            return 0.0
    
    def calculate_semantic_centrality(
        self, 
        entity_embedding: Optional[np.ndarray], 
        all_embeddings: List[np.ndarray]
    ) -> float:
        """
        Determine semantic importance based on embedding relationships.
        
        Args:
            entity_embedding: Embedding vector for the entity
            all_embeddings: List of all entity embeddings in the episode
            
        Returns:
            Semantic centrality factor between 0 and 1
        """
        if entity_embedding is None or len(all_embeddings) == 0:
            return 0.5  # Default to neutral if no embeddings available
            
        # Convert to numpy array if needed
        if not isinstance(entity_embedding, np.ndarray):
            entity_embedding = np.array(entity_embedding)
            
        # Calculate cosine similarity to all other entities
        similarities = []
        for other_embedding in all_embeddings:
            if other_embedding is not None:
                if not isinstance(other_embedding, np.ndarray):
                    other_embedding = np.array(other_embedding)
                    
                # Cosine similarity
                similarity = np.dot(entity_embedding, other_embedding) / (
                    np.linalg.norm(entity_embedding) * np.linalg.norm(other_embedding)
                )
                similarities.append(similarity)
                
        if not similarities:
            return 0.5
            
        # Calculate average similarity (semantic centrality)
        avg_similarity = np.mean(similarities)
        
        # Transform to 0-1 range (similarity is already -1 to 1, we want 0 to 1)
        centrality_score = (avg_similarity + 1) / 2
        
        return float(centrality_score)
    
    def analyze_discourse_function(
        self, 
        entity_mentions: List[Dict[str, Any]], 
        segments: List[Segment]
    ) -> Dict[str, float]:
        """
        Understand the role of entity in conversation structure.
        
        Args:
            entity_mentions: List of mentions with segment indices
            segments: All segments in the episode
            
        Returns:
            Dictionary with discourse function scores
        """
        if not segments or not entity_mentions:
            return {
                "introduction_role": 0.0,
                "development_role": 0.0,
                "conclusion_role": 0.0,
                "bridge_role": 0.0
            }
            
        total_segments = len(segments)
        introduction_boundary = int(total_segments * 0.2)  # First 20%
        conclusion_boundary = int(total_segments * 0.8)   # Last 20%
        
        # Track which segments contain mentions
        mention_segments = set()
        for mention in entity_mentions:
            if "segment_index" in mention:
                mention_segments.add(mention["segment_index"])
                
        # Introduction score: appears early in episode
        introduction_mentions = sum(
            1 for idx in mention_segments if idx <= introduction_boundary
        )
        introduction_role = introduction_mentions / max(1, len(mention_segments))
        
        # Development score: mentioned across multiple segments
        segment_spread = len(mention_segments) / total_segments
        development_role = min(1.0, segment_spread * 2)  # Scale up for visibility
        
        # Conclusion score: appears in final portion
        conclusion_mentions = sum(
            1 for idx in mention_segments if idx >= conclusion_boundary
        )
        conclusion_role = conclusion_mentions / max(1, len(mention_segments))
        
        # Bridge score: connects different topics/segments
        # Calculate based on gaps between mentions
        if len(mention_segments) > 1:
            sorted_segments = sorted(mention_segments)
            gaps = [sorted_segments[i+1] - sorted_segments[i] 
                   for i in range(len(sorted_segments)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            # Higher gap means better bridging
            bridge_role = min(1.0, avg_gap / max(1, total_segments * 0.1))
        else:
            bridge_role = 0.0
            
        return {
            "introduction_role": introduction_role,
            "development_role": development_role,
            "conclusion_role": conclusion_role,
            "bridge_role": bridge_role
        }
    
    def analyze_temporal_dynamics(
        self, 
        entity_mentions: List[Dict[str, Any]], 
        segments: List[Segment]
    ) -> Dict[str, float]:
        """
        Analyze how entity importance changes over time.
        
        Args:
            entity_mentions: List of mentions with timing info
            segments: All segments for context
            
        Returns:
            Dictionary with temporal dynamics metrics
        """
        if not entity_mentions or not segments:
            return {
                "recency_weight": 0.0,
                "persistence_score": 0.0,
                "peak_influence": 0.0,
                "momentum": 0.0
            }
            
        # Get total duration from segments
        total_duration = segments[-1].end_time if segments else 0
        
        # Extract mention times
        mention_times = []
        for mention in entity_mentions:
            if "timestamp" in mention:
                mention_times.append(mention["timestamp"])
            elif "segment_index" in mention and mention["segment_index"] < len(segments):
                # Use segment start time as approximation
                segment = segments[mention["segment_index"]]
                mention_times.append(segment.start_time)
                
        if not mention_times:
            return {
                "recency_weight": 0.0,
                "persistence_score": 0.0,
                "peak_influence": 0.0,
                "momentum": 0.0
            }
            
        mention_times.sort()
        
        # Recency weight: exponential decay from last mention
        last_mention_time = mention_times[-1]
        time_since_last = total_duration - last_mention_time
        recency_weight = math.exp(-self.temporal_decay_alpha * (time_since_last / total_duration))
        
        # Persistence score: how long the concept is discussed
        first_mention = mention_times[0]
        discussion_duration = last_mention_time - first_mention
        persistence_score = discussion_duration / total_duration if total_duration > 0 else 0
        
        # Peak influence: maximum concentration of mentions
        # Use sliding window to find peak density
        window_size = total_duration * 0.1  # 10% of episode
        max_density = 0.0
        
        for i in range(len(mention_times)):
            window_start = mention_times[i]
            window_end = window_start + window_size
            mentions_in_window = sum(1 for t in mention_times if window_start <= t <= window_end)
            density = mentions_in_window / window_size if window_size > 0 else 0
            max_density = max(max_density, density)
            
        # Normalize peak influence
        peak_influence = min(1.0, max_density * 60)  # Normalize to mentions per minute
        
        # Momentum: increasing or decreasing importance
        # Compare first half vs second half
        midpoint = total_duration / 2
        first_half_mentions = sum(1 for t in mention_times if t < midpoint)
        second_half_mentions = len(mention_times) - first_half_mentions
        
        if first_half_mentions > 0:
            momentum_ratio = second_half_mentions / first_half_mentions
            # Convert to -1 to 1 scale
            momentum = (momentum_ratio - 1) / (momentum_ratio + 1)
        else:
            momentum = 1.0 if second_half_mentions > 0 else 0.0
            
        return {
            "recency_weight": recency_weight,
            "persistence_score": persistence_score,
            "peak_influence": peak_influence,
            "momentum": momentum
        }
    
    def calculate_cross_reference_score(
        self, 
        entity_id: str, 
        all_entities: List[Entity], 
        insights: List[Insight]
    ) -> float:
        """
        Measure how often other entities/insights reference this concept.
        
        Args:
            entity_id: ID of entity to analyze
            all_entities: All entities in the episode
            insights: All insights in the episode
            
        Returns:
            Cross-reference score between 0 and 1
        """
        reference_count = 0
        weighted_references = 0.0
        
        # Find entity name for text matching
        target_entity = next((e for e in all_entities if e.id == entity_id), None)
        if not target_entity:
            return 0.0
            
        target_name = target_entity.name.lower()
        target_aliases = [alias.lower() for alias in target_entity.aliases] if target_entity.aliases else []
        
        # Check references in other entities
        for entity in all_entities:
            if entity.id == entity_id:
                continue
                
            # Check description for references
            if entity.description:
                description_lower = entity.description.lower()
                if target_name in description_lower or any(alias in description_lower for alias in target_aliases):
                    reference_count += 1
                    # Weight by referencing entity's importance (use mention count as proxy)
                    weight = min(1.0, entity.mention_count / 10) if hasattr(entity, 'mention_count') else 0.5
                    weighted_references += weight
                    
        # Check references in insights
        for insight in insights:
            # Check both title and description
            text_to_check = f"{insight.title} {insight.description}".lower()
            if target_name in text_to_check or any(alias in text_to_check for alias in target_aliases):
                reference_count += 1
                # Insights have higher weight
                weighted_references += 1.5
                
            # Check if entity is in supporting entities
            if hasattr(insight, 'supporting_entities') and entity_id in insight.supporting_entities:
                reference_count += 1
                weighted_references += 2.0  # Direct support is highly weighted
                
        # Normalize score
        # Use log scale to prevent extremely referenced entities from dominating
        if weighted_references > 0:
            score = math.log(1 + weighted_references) / math.log(1 + 10)  # Normalize assuming 10 is high
        else:
            score = 0.0
            
        return min(1.0, score)
    
    def calculate_composite_importance(
        self, 
        all_factors: Dict[str, float], 
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Combine all factors into final importance score.
        
        Args:
            all_factors: Dictionary of all calculated factors
            weights: Optional custom weights for factors
            
        Returns:
            Composite importance score between 0 and 1
        """
        # Default weights if not provided
        if weights is None:
            weights = {
                "frequency": 0.15,
                "structural_centrality": 0.25,
                "semantic_centrality": 0.20,
                "discourse_function": 0.20,
                "temporal_dynamics": 0.10,
                "cross_reference": 0.10
            }
            
        # Validate weights sum to 1.0
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            logger.warning(f"Weights sum to {weight_sum}, normalizing...")
            weights = {k: v/weight_sum for k, v in weights.items()}
            
        # Calculate composite score
        composite_score = 0.0
        
        # Handle individual factors
        if "frequency" in all_factors and "frequency" in weights:
            composite_score += weights["frequency"] * all_factors["frequency"]
            
        if "structural_centrality" in all_factors and "structural_centrality" in weights:
            composite_score += weights["structural_centrality"] * all_factors["structural_centrality"]
            
        if "semantic_centrality" in all_factors and "semantic_centrality" in weights:
            composite_score += weights["semantic_centrality"] * all_factors["semantic_centrality"]
            
        if "cross_reference" in all_factors and "cross_reference" in weights:
            composite_score += weights["cross_reference"] * all_factors["cross_reference"]
            
        # Handle discourse function (multiple sub-factors)
        if "discourse_function" in weights:
            discourse_factors = ["introduction_role", "development_role", "conclusion_role", "bridge_role"]
            discourse_score = 0.0
            discourse_count = 0
            
            for factor in discourse_factors:
                if factor in all_factors:
                    discourse_score += all_factors[factor]
                    discourse_count += 1
                    
            if discourse_count > 0:
                avg_discourse = discourse_score / discourse_count
                composite_score += weights["discourse_function"] * avg_discourse
                
        # Handle temporal dynamics (multiple sub-factors)
        if "temporal_dynamics" in weights:
            temporal_factors = ["recency_weight", "persistence_score", "peak_influence"]
            temporal_score = 0.0
            temporal_count = 0
            
            for factor in temporal_factors:
                if factor in all_factors:
                    temporal_score += all_factors[factor]
                    temporal_count += 1
                    
            if temporal_count > 0:
                avg_temporal = temporal_score / temporal_count
                composite_score += weights["temporal_dynamics"] * avg_temporal
                
        return min(1.0, max(0.0, composite_score))
    
    def generate_importance_visualization_data(
        self, 
        entities: List[Entity]
    ) -> Dict[str, Any]:
        """
        Prepare data for future visualization of importance factors.
        
        Args:
            entities: List of entities with importance data
            
        Returns:
            Structured data for visualization
        """
        viz_data = {
            "entities": [],
            "importance_distribution": {
                "bins": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "counts": [0, 0, 0, 0, 0]
            },
            "factor_correlations": {},
            "top_by_factor": {
                "frequency": [],
                "structural_centrality": [],
                "semantic_centrality": [],
                "discourse_function": [],
                "temporal_dynamics": [],
                "cross_reference": []
            }
        }
        
        # Collect entity data
        for entity in entities:
            entity_data = {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type.value if hasattr(entity, 'entity_type') else "unknown"
            }
            
            # Add importance data if available
            if hasattr(entity, 'importance_score'):
                entity_data["importance_score"] = entity.importance_score
                
                # Update distribution
                score = entity.importance_score
                if score < 0.2:
                    viz_data["importance_distribution"]["counts"][0] += 1
                elif score < 0.4:
                    viz_data["importance_distribution"]["counts"][1] += 1
                elif score < 0.6:
                    viz_data["importance_distribution"]["counts"][2] += 1
                elif score < 0.8:
                    viz_data["importance_distribution"]["counts"][3] += 1
                else:
                    viz_data["importance_distribution"]["counts"][4] += 1
                    
            if hasattr(entity, 'importance_factors'):
                entity_data["importance_factors"] = entity.importance_factors
                
            viz_data["entities"].append(entity_data)
            
        # Sort entities by different factors
        if viz_data["entities"]:
            # Overall importance
            sorted_by_importance = sorted(
                [e for e in viz_data["entities"] if "importance_score" in e],
                key=lambda x: x["importance_score"],
                reverse=True
            )
            
            # By individual factors
            for factor in ["frequency", "structural_centrality", "semantic_centrality"]:
                sorted_by_factor = sorted(
                    [e for e in viz_data["entities"] 
                     if "importance_factors" in e and factor in e["importance_factors"]],
                    key=lambda x: x["importance_factors"][factor],
                    reverse=True
                )
                viz_data["top_by_factor"][factor] = sorted_by_factor[:5]
                
            # For compound factors
            # Discourse function - average of sub-factors
            entities_with_discourse = []
            for e in viz_data["entities"]:
                if "importance_factors" in e:
                    discourse_factors = ["introduction_role", "development_role", 
                                       "conclusion_role", "bridge_role"]
                    discourse_scores = [e["importance_factors"].get(f, 0) 
                                       for f in discourse_factors 
                                       if f in e["importance_factors"]]
                    if discourse_scores:
                        avg_discourse = sum(discourse_scores) / len(discourse_scores)
                        entities_with_discourse.append({**e, "_discourse_avg": avg_discourse})
                        
            sorted_by_discourse = sorted(
                entities_with_discourse,
                key=lambda x: x["_discourse_avg"],
                reverse=True
            )
            viz_data["top_by_factor"]["discourse_function"] = sorted_by_discourse[:5]
            
            # Similar for temporal dynamics
            entities_with_temporal = []
            for e in viz_data["entities"]:
                if "importance_factors" in e:
                    temporal_factors = ["recency_weight", "persistence_score", "peak_influence"]
                    temporal_scores = [e["importance_factors"].get(f, 0) 
                                      for f in temporal_factors 
                                      if f in e["importance_factors"]]
                    if temporal_scores:
                        avg_temporal = sum(temporal_scores) / len(temporal_scores)
                        entities_with_temporal.append({**e, "_temporal_avg": avg_temporal})
                        
            sorted_by_temporal = sorted(
                entities_with_temporal,
                key=lambda x: x["_temporal_avg"],
                reverse=True
            )
            viz_data["top_by_factor"]["temporal_dynamics"] = sorted_by_temporal[:5]
            
            # Cross reference
            sorted_by_cross_ref = sorted(
                [e for e in viz_data["entities"] 
                 if "importance_factors" in e and "cross_reference" in e["importance_factors"]],
                key=lambda x: x["importance_factors"]["cross_reference"],
                reverse=True
            )
            viz_data["top_by_factor"]["cross_reference"] = sorted_by_cross_ref[:5]
            
        return viz_data
    
    # Utility methods for filtering
    
    def get_top_entities_by_importance(
        self, 
        entities: List[Entity], 
        top_n: int = 10
    ) -> List[Entity]:
        """Get top N entities by composite importance score."""
        entities_with_importance = [
            e for e in entities 
            if hasattr(e, 'importance_score') and e.importance_score is not None
        ]
        
        return sorted(
            entities_with_importance,
            key=lambda x: x.importance_score,
            reverse=True
        )[:top_n]
    
    def filter_entities_by_importance_threshold(
        self, 
        entities: List[Entity], 
        threshold: float = 0.5
    ) -> List[Entity]:
        """Filter entities above importance threshold."""
        return [
            e for e in entities
            if hasattr(e, 'importance_score') and e.importance_score >= threshold
        ]
    
    def get_entities_by_factor(
        self, 
        entities: List[Entity], 
        factor_name: str, 
        top_n: int = 5
    ) -> List[Entity]:
        """Get top entities for a specific importance factor."""
        # Handle compound factors
        if factor_name == "discourse_function":
            # Calculate average of discourse sub-factors
            entities_with_score = []
            for e in entities:
                if hasattr(e, 'importance_factors') and e.importance_factors:
                    discourse_factors = ["introduction_role", "development_role", 
                                       "conclusion_role", "bridge_role"]
                    scores = [e.importance_factors.get(f, 0) for f in discourse_factors]
                    if scores:
                        avg_score = sum(scores) / len(scores)
                        entities_with_score.append((e, avg_score))
                        
            entities_with_score.sort(key=lambda x: x[1], reverse=True)
            return [e for e, _ in entities_with_score[:top_n]]
            
        elif factor_name == "temporal_dynamics":
            # Calculate average of temporal sub-factors
            entities_with_score = []
            for e in entities:
                if hasattr(e, 'importance_factors') and e.importance_factors:
                    temporal_factors = ["recency_weight", "persistence_score", "peak_influence"]
                    scores = [e.importance_factors.get(f, 0) for f in temporal_factors]
                    if scores:
                        avg_score = sum(scores) / len(scores)
                        entities_with_score.append((e, avg_score))
                        
            entities_with_score.sort(key=lambda x: x[1], reverse=True)
            return [e for e, _ in entities_with_score[:top_n]]
            
        else:
            # Direct factor
            entities_with_factor = [
                e for e in entities
                if hasattr(e, 'importance_factors') 
                and e.importance_factors 
                and factor_name in e.importance_factors
            ]
            
            return sorted(
                entities_with_factor,
                key=lambda x: x.importance_factors[factor_name],
                reverse=True
            )[:top_n]