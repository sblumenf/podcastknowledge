"""
Graph analysis and enhancement functionality
"""
import logging
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
from itertools import combinations
import numpy as np

from src.core.models import Entity, Insight
from src.core.interfaces import LLMProvider

try:
    import networkx as nx
    from networkx.algorithms import community
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None
    community = None

try:
    from scipy.stats import entropy
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    entropy = None


logger = logging.getLogger(__name__)


class DiscourseType(Enum):
    """Types of discourse structures"""
    HIERARCHICAL = "hierarchical"
    MODULAR = "modular"
    SEQUENTIAL = "sequential"
    EMERGENT = "emergent"


@dataclass
class CentralityResult:
    """Result of centrality analysis"""
    node_id: str
    node_name: str
    centrality_score: float
    node_type: str


@dataclass
class CommunityResult:
    """Result of community detection"""
    resolution: float
    communities: Dict[str, int]  # node_id -> community_id
    num_communities: int
    modularity: Optional[float] = None


@dataclass
class PeripheralConcept:
    """Peripheral concept with exploration potential"""
    id: str
    name: str
    type: str
    degree: int
    segment_mentions: int
    exploration_potential: float


@dataclass
class DiscourseStructure:
    """Discourse structure analysis result"""
    type: DiscourseType
    influence_entropy: float
    modularity_score: float
    top_influencers: List[str]
    confidence: float


@dataclass
class DiversityMetrics:
    """Diversity metrics for episode analysis"""
    topic_diversity: float
    connection_richness: float
    concept_density: float
    entity_count: int
    insight_count: int
    community_count: int


@dataclass
class StructuralGap:
    """Represents a gap between topic communities"""
    community_1: int
    community_2: int
    connection_count: int
    representative_concepts_1: List[str]
    representative_concepts_2: List[str]
    gap_score: float


@dataclass
class HierarchicalTopic:
    """Hierarchical topic structure"""
    id: str
    name: str
    level: str
    member_count: int
    top_concepts: List[str]


@dataclass
class BridgeInsight:
    """Insight that bridges multiple communities"""
    id: str
    content: str
    key_insight: bool
    communities_bridged: int
    bridge_score: float


class GraphAnalyzer:
    """Handles graph analysis and enhancement operations"""
    
    def __init__(self, graph_provider=None):
        """Initialize graph analyzer
        
        Args:
            graph_provider: Optional graph provider instance (for compatibility)
        """
        self.graph_provider = graph_provider
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Graph analysis features will be limited.")
        if not SCIPY_AVAILABLE:
            logger.warning("SciPy not available. Some analysis features will be limited.")
    
    class EnhancedGapAnalyzer:
        """Inner class for enhanced structural gap analysis.
        
        Extends basic gap detection with semantic analysis, bridge identification,
        and actionable suggestions for knowledge exploration.
        """
        
        def __init__(self, graph_analyzer: 'GraphAnalyzer'):
            """Initialize enhanced gap analyzer.
            
            Args:
                graph_analyzer: Parent GraphAnalyzer instance
            """
            self.graph_analyzer = graph_analyzer
            
        def calculate_semantic_distance(
            self,
            community1_entities: List[Entity],
            community2_entities: List[Entity]
        ) -> Dict[str, float]:
            """Measure semantic distance between two disconnected communities.
            
            Args:
                community1_entities: Entities in first community
                community2_entities: Entities in second community
                
            Returns:
                Dictionary with distance metrics
            """
            if not community1_entities or not community2_entities:
                return {
                    "centroid_distance": 1.0,
                    "min_pairwise_distance": 1.0,
                    "max_pairwise_distance": 1.0,
                    "avg_pairwise_distance": 1.0
                }
            
            # Get embeddings for each community
            embeddings1 = []
            embeddings2 = []
            
            for entity in community1_entities:
                if hasattr(entity, 'embedding') and entity.embedding:
                    embeddings1.append(np.array(entity.embedding))
                    
            for entity in community2_entities:
                if hasattr(entity, 'embedding') and entity.embedding:
                    embeddings2.append(np.array(entity.embedding))
            
            # If no embeddings available, return default distances
            if not embeddings1 or not embeddings2:
                return {
                    "centroid_distance": 0.5,  # Unknown distance
                    "min_pairwise_distance": 0.5,
                    "max_pairwise_distance": 0.5,
                    "avg_pairwise_distance": 0.5
                }
            
            # Calculate centroid for each community
            centroid1 = np.mean(embeddings1, axis=0)
            centroid2 = np.mean(embeddings2, axis=0)
            
            # Normalize centroids
            centroid1 = centroid1 / (np.linalg.norm(centroid1) + 1e-8)
            centroid2 = centroid2 / (np.linalg.norm(centroid2) + 1e-8)
            
            # Calculate centroid distance (1 - cosine similarity)
            centroid_distance = 1 - np.dot(centroid1, centroid2)
            
            # Calculate pairwise distances
            pairwise_distances = []
            for emb1 in embeddings1:
                emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
                for emb2 in embeddings2:
                    emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)
                    distance = 1 - np.dot(emb1_norm, emb2_norm)
                    pairwise_distances.append(distance)
            
            return {
                "centroid_distance": float(centroid_distance),
                "min_pairwise_distance": float(min(pairwise_distances)),
                "max_pairwise_distance": float(max(pairwise_distances)),
                "avg_pairwise_distance": float(np.mean(pairwise_distances))
            }
        
        def find_potential_bridges(
            self,
            gap: Dict[str, Any],
            all_entities: List[Entity],
            top_n: int = 5
        ) -> List[Dict[str, Any]]:
            """Identify concepts that could connect disconnected communities.
            
            Args:
                gap: Gap information dictionary
                all_entities: All entities in the graph
                top_n: Number of top bridge candidates to return
                
            Returns:
                List of potential bridge concepts with scores
            """
            # Get entities in each community
            comm1_entity_ids = set(gap.get('community1_entities', []))
            comm2_entity_ids = set(gap.get('community2_entities', []))
            
            # Find entities not in either community
            bridge_candidates = []
            
            for entity in all_entities:
                if entity.id not in comm1_entity_ids and entity.id not in comm2_entity_ids:
                    if hasattr(entity, 'embedding') and entity.embedding:
                        # Calculate similarity to both communities
                        comm1_entities = [e for e in all_entities if e.id in comm1_entity_ids]
                        comm2_entities = [e for e in all_entities if e.id in comm2_entity_ids]
                        
                        # Get embeddings
                        comm1_embeddings = []
                        comm2_embeddings = []
                        
                        for e in comm1_entities:
                            if hasattr(e, 'embedding') and e.embedding:
                                comm1_embeddings.append(np.array(e.embedding))
                        
                        for e in comm2_entities:
                            if hasattr(e, 'embedding') and e.embedding:
                                comm2_embeddings.append(np.array(e.embedding))
                        
                        if comm1_embeddings and comm2_embeddings:
                            # Calculate centroids
                            centroid1 = np.mean(comm1_embeddings, axis=0)
                            centroid2 = np.mean(comm2_embeddings, axis=0)
                            
                            # Normalize
                            entity_emb = np.array(entity.embedding)
                            entity_emb_norm = entity_emb / (np.linalg.norm(entity_emb) + 1e-8)
                            centroid1_norm = centroid1 / (np.linalg.norm(centroid1) + 1e-8)
                            centroid2_norm = centroid2 / (np.linalg.norm(centroid2) + 1e-8)
                            
                            # Calculate similarities
                            sim_to_comm1 = np.dot(entity_emb_norm, centroid1_norm)
                            sim_to_comm2 = np.dot(entity_emb_norm, centroid2_norm)
                            
                            # Bridge score: minimum similarity to both communities
                            bridge_score = min(sim_to_comm1, sim_to_comm2) * 2
                            
                            bridge_candidates.append({
                                "entity": entity,
                                "bridge_score": float(bridge_score),
                                "similarity_to_community1": float(sim_to_comm1),
                                "similarity_to_community2": float(sim_to_comm2),
                                "explanation": f"This concept relates to both communities with balanced similarity"
                            })
            
            # Sort by bridge score
            bridge_candidates.sort(key=lambda x: x['bridge_score'], reverse=True)
            
            return bridge_candidates[:top_n]
        
        def calculate_gap_bridgeability(
            self,
            gap: Dict[str, Any],
            semantic_distance: Dict[str, float],
            potential_bridges: List[Dict[str, Any]]
        ) -> float:
            """Score how easily a gap could be bridged.
            
            Args:
                gap: Gap information
                semantic_distance: Semantic distance metrics
                potential_bridges: List of potential bridge concepts
                
            Returns:
                Bridgeability score between 0 and 1
            """
            # Factor 1: Semantic distance (closer = more bridgeable)
            distance_factor = 1 - semantic_distance.get('centroid_distance', 0.5)
            
            # Factor 2: Number and quality of bridge candidates
            if potential_bridges:
                # Average score of top 3 bridges
                top_bridge_scores = [b['bridge_score'] for b in potential_bridges[:3]]
                bridge_quality = np.mean(top_bridge_scores) if top_bridge_scores else 0
            else:
                bridge_quality = 0
            
            # Factor 3: Size balance between communities
            comm1_size = len(gap.get('community1_entities', []))
            comm2_size = len(gap.get('community2_entities', []))
            total_size = comm1_size + comm2_size
            if total_size > 0:
                size_balance = 1 - abs(comm1_size - comm2_size) / total_size
            else:
                size_balance = 0
            
            # Factor 4: Conceptual coherence (simplified - based on existing connections)
            connection_count = gap.get('connection_count', 0)
            coherence_factor = min(1.0, connection_count / 3.0)
            
            # Combine factors
            bridgeability = (
                0.3 * distance_factor +
                0.4 * bridge_quality +
                0.2 * size_balance +
                0.1 * coherence_factor
            )
            
            return float(bridgeability)
        
        def find_conceptual_paths(
            self,
            entity1: Entity,
            entity2: Entity,
            all_entities: List[Entity],
            max_hops: int = 3
        ) -> List[List[Entity]]:
            """Find potential conceptual paths between disconnected entities.
            
            Args:
                entity1: Starting entity
                entity2: Target entity
                all_entities: All available entities
                max_hops: Maximum path length
                
            Returns:
                List of paths (each path is a list of entities)
            """
            if not (hasattr(entity1, 'embedding') and entity1.embedding and
                    hasattr(entity2, 'embedding') and entity2.embedding):
                return []
            
            # Use embedding space to find intermediate concepts
            start_emb = np.array(entity1.embedding)
            end_emb = np.array(entity2.embedding)
            
            # Normalize
            start_emb = start_emb / (np.linalg.norm(start_emb) + 1e-8)
            end_emb = end_emb / (np.linalg.norm(end_emb) + 1e-8)
            
            paths = []
            
            # Simple approach: find entities that are similar to both
            for intermediate in all_entities:
                if (intermediate.id != entity1.id and 
                    intermediate.id != entity2.id and
                    hasattr(intermediate, 'embedding') and 
                    intermediate.embedding):
                    
                    inter_emb = np.array(intermediate.embedding)
                    inter_emb = inter_emb / (np.linalg.norm(inter_emb) + 1e-8)
                    
                    # Check similarity to both start and end
                    sim_to_start = np.dot(start_emb, inter_emb)
                    sim_to_end = np.dot(end_emb, inter_emb)
                    
                    # If reasonably similar to both, it's a good bridge
                    if sim_to_start > 0.5 and sim_to_end > 0.5:
                        path = [entity1, intermediate, entity2]
                        paths.append(path)
            
            # Sort paths by average similarity
            def path_score(path):
                if len(path) < 2:
                    return 0
                scores = []
                for i in range(len(path) - 1):
                    if (hasattr(path[i], 'embedding') and path[i].embedding and
                        hasattr(path[i+1], 'embedding') and path[i+1].embedding):
                        emb1 = np.array(path[i].embedding)
                        emb2 = np.array(path[i+1].embedding)
                        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-8)
                        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-8)
                        scores.append(np.dot(emb1, emb2))
                return np.mean(scores) if scores else 0
            
            paths.sort(key=path_score, reverse=True)
            
            # Return top 3 paths
            return paths[:3]
        
        def generate_enhanced_gap_report(self, gap: Dict[str, Any]) -> Dict[str, Any]:
            """Create comprehensive gap analysis report.
            
            Args:
                gap: Basic gap information
                
            Returns:
                Enhanced gap report with analysis and suggestions
            """
            # Get entities for semantic analysis
            all_entities = gap.get('all_entities', [])
            comm1_entity_ids = gap.get('community1_entities', [])
            comm2_entity_ids = gap.get('community2_entities', [])
            
            comm1_entities = [e for e in all_entities if e.id in comm1_entity_ids]
            comm2_entities = [e for e in all_entities if e.id in comm2_entity_ids]
            
            # Calculate semantic distance
            semantic_distance = self.calculate_semantic_distance(comm1_entities, comm2_entities)
            
            # Find potential bridges
            potential_bridges = self.find_potential_bridges(gap, all_entities, top_n=5)
            
            # Calculate bridgeability
            bridgeability_score = self.calculate_gap_bridgeability(
                gap, semantic_distance, potential_bridges
            )
            
            # Generate exploration suggestions
            exploration_suggestions = []
            
            if potential_bridges:
                top_bridge = potential_bridges[0]['entity']
                exploration_suggestions.append(
                    f"Consider exploring how {top_bridge.name} relates to both topic areas"
                )
            
            if semantic_distance['centroid_distance'] < 0.5:
                exploration_suggestions.append(
                    "These topics are semantically close - look for implicit connections"
                )
            else:
                exploration_suggestions.append(
                    "These topics are semantically distant - bridging may reveal novel insights"
                )
            
            # Create report
            report = {
                "gap_id": f"community_{gap.get('community_1', 0)}_to_{gap.get('community_2', 0)}",
                "semantic_analysis": {
                    "distance_metrics": semantic_distance,
                    "interpretation": self._interpret_semantic_distance(semantic_distance)
                },
                "bridge_analysis": {
                    "potential_bridges": potential_bridges,
                    "bridgeability_score": bridgeability_score,
                    "recommended_connections": [b['entity'].name for b in potential_bridges[:3]]
                },
                "exploration_suggestions": exploration_suggestions
            }
            
            return report
        
        def _interpret_semantic_distance(self, distance_metrics: Dict[str, float]) -> str:
            """Interpret semantic distance metrics.
            
            Args:
                distance_metrics: Distance metrics dictionary
                
            Returns:
                Human-readable interpretation
            """
            centroid_dist = distance_metrics.get('centroid_distance', 0.5)
            
            if centroid_dist < 0.3:
                return "These communities are semantically very close"
            elif centroid_dist < 0.5:
                return "These communities are moderately distant"
            elif centroid_dist < 0.7:
                return "These communities are quite distant"
            else:
                return "These communities are very distant semantically"
        
        def track_gap_evolution(
            self,
            current_gaps: List[Dict[str, Any]],
            previous_gaps: List[Dict[str, Any]]
        ) -> Dict[str, Any]:
            """Track how gaps change as more content is processed.
            
            Args:
                current_gaps: Current gap analysis
                previous_gaps: Previous gap analysis
                
            Returns:
                Gap evolution analysis
            """
            evolution = {
                "new_gaps": [],
                "bridged_gaps": [],
                "widened_gaps": [],
                "stable_gaps": []
            }
            
            # Create gap identifiers for comparison
            def gap_id(gap):
                return f"{gap.get('community_1', 0)}_{gap.get('community_2', 0)}"
            
            current_gap_ids = {gap_id(g): g for g in current_gaps}
            previous_gap_ids = {gap_id(g): g for g in previous_gaps}
            
            # Find new gaps
            for gid, gap in current_gap_ids.items():
                if gid not in previous_gap_ids:
                    evolution["new_gaps"].append(gap)
            
            # Find bridged gaps
            for gid, gap in previous_gap_ids.items():
                if gid not in current_gap_ids:
                    evolution["bridged_gaps"].append(gap)
            
            # Compare stable gaps
            for gid in set(current_gap_ids.keys()) & set(previous_gap_ids.keys()):
                current = current_gap_ids[gid]
                previous = previous_gap_ids[gid]
                
                # Compare gap scores or connection counts
                current_score = current.get('gap_score', 0)
                previous_score = previous.get('gap_score', 0)
                
                if current_score > previous_score + 0.1:
                    evolution["widened_gaps"].append(current)
                else:
                    evolution["stable_gaps"].append(current)
            
            return evolution
        
        def prioritize_gaps(self, gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Rank gaps by importance and exploration value.
            
            Args:
                gaps: List of gap dictionaries
                
            Returns:
                Prioritized list of gaps
            """
            prioritized_gaps = []
            
            for gap in gaps:
                # Calculate priority factors
                
                # Size of disconnected communities
                comm1_size = len(gap.get('community1_entities', []))
                comm2_size = len(gap.get('community2_entities', []))
                size_factor = (comm1_size + comm2_size) / 20.0  # Normalize
                
                # Importance of entities (if available)
                importance_factor = 0.5  # Default
                all_entities = gap.get('all_entities', [])
                if all_entities:
                    comm1_entities = [e for e in all_entities 
                                     if e.id in gap.get('community1_entities', [])]
                    comm2_entities = [e for e in all_entities 
                                     if e.id in gap.get('community2_entities', [])]
                    
                    importances = []
                    for e in comm1_entities + comm2_entities:
                        if hasattr(e, 'importance_score'):
                            importances.append(e.importance_score)
                    
                    if importances:
                        importance_factor = np.mean(importances)
                
                # Bridgeability (if calculated)
                bridgeability = gap.get('bridgeability_score', 0.5)
                
                # Novelty factor (gaps with fewer connections are more novel)
                connection_count = gap.get('connection_count', 0)
                novelty_factor = 1 - min(1.0, connection_count / 5.0)
                
                # Calculate priority score
                priority_score = (
                    0.25 * size_factor +
                    0.35 * importance_factor +
                    0.25 * bridgeability +
                    0.15 * novelty_factor
                )
                
                gap['priority_score'] = float(priority_score)
                prioritized_gaps.append(gap)
            
            # Sort by priority
            prioritized_gaps.sort(key=lambda x: x['priority_score'], reverse=True)
            
            return prioritized_gaps
        
        def prepare_gap_visualization_data(
            self,
            enhanced_gaps: List[Dict[str, Any]]
        ) -> Dict[str, Any]:
            """Structure data for gap visualization.
            
            Args:
                enhanced_gaps: List of enhanced gap analyses
                
            Returns:
                Visualization-ready data structure
            """
            viz_data = {
                "communities": {},
                "gaps": [],
                "bridges": [],
                "semantic_map": {}
            }
            
            for gap in enhanced_gaps:
                gap_id = gap.get('gap_id', '')
                
                # Add community info
                comm1_id = gap.get('community_1', 0)
                comm2_id = gap.get('community_2', 0)
                
                if comm1_id not in viz_data["communities"]:
                    viz_data["communities"][comm1_id] = {
                        "id": comm1_id,
                        "entities": gap.get('representative_concepts_1', []),
                        "size": len(gap.get('community1_entities', []))
                    }
                
                if comm2_id not in viz_data["communities"]:
                    viz_data["communities"][comm2_id] = {
                        "id": comm2_id,
                        "entities": gap.get('representative_concepts_2', []),
                        "size": len(gap.get('community2_entities', []))
                    }
                
                # Add gap info
                gap_viz = {
                    "id": gap_id,
                    "source": comm1_id,
                    "target": comm2_id,
                    "distance": gap.get('semantic_analysis', {}).get('distance_metrics', {}).get('centroid_distance', 0.5),
                    "bridgeability": gap.get('bridge_analysis', {}).get('bridgeability_score', 0.5),
                    "priority": gap.get('priority_score', 0.5)
                }
                viz_data["gaps"].append(gap_viz)
                
                # Add bridge candidates
                for bridge in gap.get('bridge_analysis', {}).get('potential_bridges', [])[:3]:
                    bridge_viz = {
                        "entity": bridge['entity'].name,
                        "score": bridge['bridge_score'],
                        "connects": [comm1_id, comm2_id]
                    }
                    viz_data["bridges"].append(bridge_viz)
            
            return viz_data
    
    def extract_weighted_co_occurrences(
        self, 
        entities: List[Entity], 
        segments: List[Any]
    ) -> List[Tuple[str, str, float]]:
        """
        Extract weighted co-occurrence relationships between entities
        
        Args:
            entities: List of entities
            segments: List of segments containing text
            
        Returns:
            List of (entity1_id, entity2_id, weight) tuples
        """
        co_occurrences = {}
        
        # Process each segment
        for segment in segments:
            segment_text = segment.text.lower() if hasattr(segment, 'text') else str(segment).lower()
            
            # Find entities that appear in this segment
            entities_in_segment = []
            for entity in entities:
                if entity.name.lower() in segment_text:
                    entities_in_segment.append(entity)
            
            # Create co-occurrence pairs
            for i, entity1 in enumerate(entities_in_segment):
                for entity2 in entities_in_segment[i+1:]:
                    # Create ordered pair to avoid duplicates
                    pair = tuple(sorted([entity1.id, entity2.id]))
                    
                    # Increment co-occurrence count
                    co_occurrences[pair] = co_occurrences.get(pair, 0) + 1
        
        # Convert to list format with weights
        result = []
        for (id1, id2), count in co_occurrences.items():
            # Weight can be normalized or use raw count
            weight = count
            result.append((id1, id2, weight))
        
        return result
    
    def calculate_betweenness_centrality(
        self, 
        nodes: List[Dict[str, Any]], 
        edges: List[Tuple[str, str, float]]
    ) -> List[CentralityResult]:
        """
        Calculate betweenness centrality for nodes to find bridge concepts
        
        Args:
            nodes: List of node dictionaries with 'id' and 'name' keys
            edges: List of (source_id, target_id, weight) tuples
            
        Returns:
            List of centrality results sorted by score
        """
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Cannot calculate centrality.")
            return []
        
        try:
            # Build graph
            G = nx.Graph()
            
            # Add nodes
            for node in nodes:
                G.add_node(node['id'], name=node.get('name', ''), type=node.get('type', 'unknown'))
            
            # Add edges
            for source, target, weight in edges:
                G.add_edge(source, target, weight=weight)
            
            # Check if graph has nodes
            if len(G.nodes()) == 0:
                return []
            
            # Calculate betweenness centrality
            centrality = nx.betweenness_centrality(G, weight='weight')
            
            # Create results
            results = []
            for node_id, score in centrality.items():
                node_data = G.nodes[node_id]
                results.append(CentralityResult(
                    node_id=node_id,
                    node_name=node_data.get('name', ''),
                    centrality_score=score,
                    node_type=node_data.get('type', 'unknown')
                ))
            
            # Sort by centrality score
            results.sort(key=lambda x: x.centrality_score, reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to calculate centrality: {e}")
            return []
    
    def detect_communities_multi_level(
        self, 
        nodes: List[Dict[str, Any]], 
        edges: List[Tuple[str, str, float]],
        resolution_levels: List[float] = None
    ) -> Tuple[List[CommunityResult], Dict[str, str]]:
        """
        Detect communities at multiple resolution levels using Louvain algorithm
        
        Args:
            nodes: List of node dictionaries
            edges: List of (source_id, target_id, weight) tuples
            resolution_levels: List of resolution parameters (default: [0.5, 1.0, 2.0])
            
        Returns:
            Tuple of (community results, node name mapping)
        """
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Cannot detect communities.")
            return [], {}
        
        if resolution_levels is None:
            resolution_levels = [0.5, 1.0, 2.0]
        
        try:
            # Build graph
            G = nx.Graph()
            node_names = {}
            
            # Add nodes
            for node in nodes:
                node_id = node['id']
                node_name = node.get('name', node_id)
                G.add_node(node_id)
                node_names[node_id] = node_name
            
            # Add edges
            for source, target, weight in edges:
                if source in G and target in G:
                    G.add_edge(source, target, weight=weight)
            
            # Check if graph has nodes
            if len(G.nodes()) == 0:
                return [], {}
            
            # Detect communities at each resolution level
            community_results = []
            for resolution in resolution_levels:
                communities = community.louvain_communities(
                    G, resolution=resolution, weight='weight'
                )
                
                # Convert to node->community mapping
                node_communities = {}
                for comm_id, nodes_in_comm in enumerate(communities):
                    for node in nodes_in_comm:
                        node_communities[node] = comm_id
                
                # Calculate modularity if possible
                try:
                    modularity = community.modularity(G, communities, weight='weight')
                except:
                    modularity = None
                
                community_results.append(CommunityResult(
                    resolution=resolution,
                    communities=node_communities,
                    num_communities=len(communities),
                    modularity=modularity
                ))
            
            return community_results, node_names
            
        except Exception as e:
            logger.error(f"Failed to detect communities: {e}")
            return [], {}
    
    def identify_peripheral_concepts(
        self, 
        entities: List[Entity],
        edges: List[Tuple[str, str, float]],
        segment_mentions: Dict[str, int]
    ) -> List[PeripheralConcept]:
        """
        Identify peripheral concepts that are mentioned but not deeply explored
        
        Args:
            entities: List of entities
            edges: List of relationship edges
            segment_mentions: Dict mapping entity_id to mention count
            
        Returns:
            List of peripheral concepts with exploration potential
        """
        # Calculate degree for each entity
        entity_degrees = {}
        for entity in entities:
            entity_degrees[entity.id] = 0
        
        for source, target, _ in edges:
            if source in entity_degrees:
                entity_degrees[source] += 1
            if target in entity_degrees:
                entity_degrees[target] += 1
        
        # Find peripheral concepts
        peripheral_concepts = []
        
        for entity in entities:
            degree = entity_degrees.get(entity.id, 0)
            mentions = segment_mentions.get(entity.id, 0)
            
            # Peripheral if low degree but mentioned multiple times
            if 0 < degree < 3 and mentions >= 2:
                # Calculate exploration potential
                exploration_potential = degree * 0.3 + mentions * 0.7
                
                peripheral_concepts.append(PeripheralConcept(
                    id=entity.id,
                    name=entity.name,
                    type=entity.type.value,
                    degree=degree,
                    segment_mentions=mentions,
                    exploration_potential=exploration_potential
                ))
        
        # Sort by exploration potential
        peripheral_concepts.sort(key=lambda x: x.exploration_potential, reverse=True)
        
        # Return top 20
        return peripheral_concepts[:20]
    
    def calculate_discourse_structure(
        self, 
        centrality_results: List[CentralityResult],
        community_data: List[CommunityResult]
    ) -> DiscourseStructure:
        """
        Calculate discourse structure classification based on modularity and influence distribution
        
        Args:
            centrality_results: Results from centrality analysis
            community_data: Results from community detection
            
        Returns:
            Discourse structure classification and metrics
        """
        # Get influence distribution
        if centrality_results:
            scores = [r.centrality_score for r in centrality_results[:20]]  # Top 20
            
            # Calculate influence distribution entropy
            if scores and SCIPY_AVAILABLE and entropy:
                total = sum(scores)
                if total > 0:
                    probabilities = [s/total for s in scores]
                    influence_entropy = entropy(probabilities)
                else:
                    influence_entropy = 0.0
            else:
                influence_entropy = 0.0
        else:
            influence_entropy = 0.0
            scores = []
        
        # Get modularity from community data
        modularity_score = 0.0
        num_communities = 1
        
        if community_data:
            # Use middle resolution level
            mid_level = community_data[len(community_data)//2]
            num_communities = mid_level.num_communities
            modularity_score = mid_level.modularity or 0.0
            
            # If modularity not available, estimate from community count
            if modularity_score == 0.0 and num_communities > 1:
                modularity_score = min(num_communities / 10, 0.8)
        
        # Determine discourse type
        if influence_entropy < 1.5 and len(scores) > 0 and scores[0] > 0.3:
            discourse_type = DiscourseType.HIERARCHICAL
        elif modularity_score > 0.4 and num_communities > 3:
            discourse_type = DiscourseType.MODULAR
        elif influence_entropy > 2.5:
            discourse_type = DiscourseType.EMERGENT
        else:
            discourse_type = DiscourseType.SEQUENTIAL
        
        # Get top influencers
        top_influencers = [r.node_name for r in centrality_results[:5]]
        
        # Calculate confidence
        confidence = min(len(centrality_results) / 20, 1.0) * 0.5 + \
                    min(len(community_data) / 3, 1.0) * 0.5
        
        return DiscourseStructure(
            type=discourse_type,
            influence_entropy=influence_entropy,
            modularity_score=modularity_score,
            top_influencers=top_influencers,
            confidence=confidence
        )
    
    def build_graph_from_entities_and_insights(
        self,
        entities: List[Entity],
        insights: List[Insight],
        co_occurrences: List[Tuple[str, str, float]]
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str, float]]]:
        """
        Build graph nodes and edges from entities and insights
        
        Args:
            entities: List of entities
            insights: List of insights
            co_occurrences: Co-occurrence relationships
            
        Returns:
            Tuple of (nodes, edges)
        """
        nodes = []
        edges = list(co_occurrences)  # Start with co-occurrences
        
        # Add entity nodes
        for entity in entities:
            nodes.append({
                'id': entity.id,
                'name': entity.name,
                'type': 'entity',
                'subtype': entity.type.value
            })
        
        # Add insight nodes
        for insight in insights:
            nodes.append({
                'id': insight.id,
                'name': insight.content[:50] + '...' if len(insight.content) > 50 else insight.content,
                'type': 'insight',
                'subtype': insight.type.value
            })
        
        # Add entity-insight relationships
        for insight in insights:
            # Find entities mentioned in insight
            insight_text = insight.content.lower()
            for entity in entities:
                if entity.name.lower() in insight_text:
                    edges.append((entity.id, insight.id, 0.5))  # Lower weight for entity-insight
        
        return nodes, edges
    
    def analyze_graph_structure(
        self,
        entities: List[Entity],
        insights: List[Insight],
        segments: List[Any],
        segment_mentions: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive graph structure analysis
        
        Args:
            entities: List of entities
            insights: List of insights
            segments: List of segments
            segment_mentions: Optional pre-calculated segment mentions
            
        Returns:
            Dictionary with analysis results
        """
        # Extract co-occurrences
        co_occurrences = self.extract_weighted_co_occurrences(entities, segments)
        
        # Build graph
        nodes, edges = self.build_graph_from_entities_and_insights(
            entities, insights, co_occurrences
        )
        
        # Calculate centrality
        centrality_results = self.calculate_betweenness_centrality(nodes, edges)
        
        # Detect communities
        community_results, node_names = self.detect_communities_multi_level(nodes, edges)
        
        # Calculate segment mentions if not provided
        if segment_mentions is None:
            segment_mentions = {}
            for entity in entities:
                count = 0
                for segment in segments:
                    segment_text = segment.text.lower() if hasattr(segment, 'text') else str(segment).lower()
                    if entity.name.lower() in segment_text:
                        count += 1
                segment_mentions[entity.id] = count
        
        # Identify peripheral concepts
        peripheral_concepts = self.identify_peripheral_concepts(
            entities, edges, segment_mentions
        )
        
        # Calculate discourse structure
        discourse_structure = self.calculate_discourse_structure(
            centrality_results, community_results
        )
        
        return {
            'centrality': centrality_results,
            'communities': community_results,
            'peripheral_concepts': peripheral_concepts,
            'discourse_structure': discourse_structure,
            'node_names': node_names,
            'graph_stats': {
                'num_nodes': len(nodes),
                'num_edges': len(edges),
                'num_entities': len(entities),
                'num_insights': len(insights)
            }
        }
    
    def calculate_diversity_metrics(
        self,
        entities: List[Entity],
        insights: List[Insight],
        edges: List[Tuple[str, str, float]],
        community_data: List[CommunityResult],
        total_words: int
    ) -> DiversityMetrics:
        """
        Calculate comprehensive diversity metrics
        
        Args:
            entities: List of entities
            insights: List of insights
            edges: List of edges
            community_data: Community detection results
            total_words: Total word count
            
        Returns:
            Diversity metrics
        """
        # Calculate basic counts
        entity_count = len(entities)
        insight_count = len(insights)
        total_nodes = entity_count + insight_count
        relationship_count = len(edges)
        
        # Calculate topic diversity
        num_communities = 1
        if community_data:
            # Use middle resolution level
            mid_level = community_data[len(community_data)//2]
            num_communities = mid_level.num_communities
        
        topic_diversity = min(num_communities / max(total_nodes, 1), 1.0)
        
        # Calculate connection richness
        connection_richness = relationship_count / max(total_nodes, 1)
        
        # Calculate concept density (per 1000 words)
        words_in_thousands = max(total_words / 1000, 0.001)
        concept_density = (entity_count + insight_count) / words_in_thousands
        
        return DiversityMetrics(
            topic_diversity=topic_diversity,
            connection_richness=connection_richness,
            concept_density=concept_density,
            entity_count=entity_count,
            insight_count=insight_count,
            community_count=num_communities
        )
    
    def identify_structural_gaps(
        self,
        community_data: List[CommunityResult],
        edges: List[Tuple[str, str, float]],
        node_names: Dict[str, str]
    ) -> List[StructuralGap]:
        """
        Identify structural gaps between topic clusters
        
        Args:
            community_data: Community detection results
            edges: List of edges
            node_names: Mapping of node IDs to names
            
        Returns:
            List of structural gaps
        """
        if not community_data:
            return []
        
        # Use middle resolution level
        mid_level = community_data[len(community_data)//2]
        level_communities = mid_level.communities
        
        # Count connections between communities
        community_connections = defaultdict(int)
        for source, target, _ in edges:
            source_comm = level_communities.get(source)
            target_comm = level_communities.get(target)
            
            if source_comm is not None and target_comm is not None and source_comm != target_comm:
                key = tuple(sorted([source_comm, target_comm]))
                community_connections[key] += 1
        
        # Find community pairs with few connections
        gaps = []
        all_communities = set(level_communities.values())
        
        for comm1, comm2 in combinations(all_communities, 2):
            key = tuple(sorted([comm1, comm2]))
            connection_count = community_connections.get(key, 0)
            
            if connection_count < 3:  # Few connections indicate a gap
                # Find nodes in each community
                nodes_comm1 = [n for n, c in level_communities.items() if c == comm1]
                nodes_comm2 = [n for n, c in level_communities.items() if c == comm2]
                
                # Get representative nodes
                repr_nodes_1 = nodes_comm1[:3]
                repr_nodes_2 = nodes_comm2[:3]
                
                gap = StructuralGap(
                    community_1=comm1,
                    community_2=comm2,
                    connection_count=connection_count,
                    representative_concepts_1=[node_names.get(n, n) for n in repr_nodes_1],
                    representative_concepts_2=[node_names.get(n, n) for n in repr_nodes_2],
                    gap_score=1 - (connection_count / 3)
                )
                
                gaps.append(gap)
        
        # Sort by gap score
        gaps.sort(key=lambda x: x.gap_score, reverse=True)
        
        return gaps[:10]  # Return top 10 gaps
    
    def enhance_gap_analysis(self, gap: StructuralGap, all_entities: List[Entity]) -> Dict[str, Any]:
        """Enhance a structural gap with semantic analysis and bridge identification.
        
        Args:
            gap: Basic structural gap
            all_entities: All entities in the graph
            
        Returns:
            Enhanced gap analysis dictionary
        """
        # Create enhanced analyzer instance
        enhanced_analyzer = self.EnhancedGapAnalyzer(self)
        
        # Build gap dictionary with all needed information
        gap_dict = {
            'community_1': gap.community_1,
            'community_2': gap.community_2,
            'connection_count': gap.connection_count,
            'representative_concepts_1': gap.representative_concepts_1,
            'representative_concepts_2': gap.representative_concepts_2,
            'gap_score': gap.gap_score,
            'community1_entities': [],  # Will be populated below
            'community2_entities': [],  # Will be populated below
            'all_entities': all_entities
        }
        
        # Get entity IDs for each community from node names
        # Note: This is a simplified approach - in production, you'd have proper entity ID mapping
        comm1_entity_ids = []
        comm2_entity_ids = []
        
        for entity in all_entities:
            if entity.name in gap.representative_concepts_1:
                comm1_entity_ids.append(entity.id)
            elif entity.name in gap.representative_concepts_2:
                comm2_entity_ids.append(entity.id)
        
        gap_dict['community1_entities'] = comm1_entity_ids
        gap_dict['community2_entities'] = comm2_entity_ids
        
        # Generate enhanced report
        enhanced_report = enhanced_analyzer.generate_enhanced_gap_report(gap_dict)
        
        # Add original gap information
        enhanced_report.update({
            'community_1': gap.community_1,
            'community_2': gap.community_2,
            'connection_count': gap.connection_count,
            'representative_concepts_1': gap.representative_concepts_1,
            'representative_concepts_2': gap.representative_concepts_2,
            'gap_score': gap.gap_score
        })
        
        return enhanced_report
    
    def create_hierarchical_topics(
        self,
        community_data: List[CommunityResult],
        node_names: Dict[str, str],
        llm_provider: Optional[LLMProvider] = None
    ) -> List[HierarchicalTopic]:
        """
        Create hierarchical topic structure from community data
        
        Args:
            community_data: Multi-level community detection results
            node_names: Mapping of node IDs to names
            llm_provider: Optional LLM provider for generating topic names
            
        Returns:
            List of hierarchical topics
        """
        topics = []
        
        if not community_data:
            return topics
        
        # Process each resolution level
        for level_idx, level_result in enumerate(community_data):
            level_name = f"level_{level_idx + 1}"
            level_communities = level_result.communities
            
            # Group nodes by community
            community_nodes = defaultdict(list)
            for node_id, comm_id in level_communities.items():
                if node_id in node_names:
                    community_nodes[comm_id].append({
                        'id': node_id,
                        'name': node_names[node_id]
                    })
            
            # Create topic for each community
            for comm_id, nodes in community_nodes.items():
                # Get top concepts for naming
                top_concepts = [n['name'] for n in nodes[:5]]
                
                # Generate topic name
                if llm_provider and len(top_concepts) >= 2:
                    try:
                        prompt = f"""Create a concise topic name (2-3 words) for these related concepts:
{', '.join(top_concepts)}

Return only the topic name, nothing else."""
                        
                        response = llm_provider.complete(prompt, max_tokens=20)
                        topic_name = response.strip()
                    except:
                        topic_name = f"{top_concepts[0]} & Related"
                else:
                    topic_name = top_concepts[0] if top_concepts else f"Topic {comm_id}"
                
                topic = HierarchicalTopic(
                    id=f"{level_name}-{comm_id}",
                    name=topic_name,
                    level=level_name,
                    member_count=len(nodes),
                    top_concepts=top_concepts
                )
                
                topics.append(topic)
        
        return topics
    
    def identify_bridge_insights(
        self,
        insights: List[Insight],
        entities: List[Entity],
        community_data: List[CommunityResult]
    ) -> List[BridgeInsight]:
        """
        Identify insights that bridge multiple topic communities
        
        Args:
            insights: List of insights
            entities: List of entities
            community_data: Community detection results
            
        Returns:
            List of bridge insights
        """
        if not community_data:
            return []
        
        # Use middle resolution level
        mid_level = community_data[len(community_data)//2]
        level_communities = mid_level.communities
        
        # Create entity name to ID mapping
        entity_name_to_id = {e.name.lower(): e.id for e in entities}
        
        bridge_insights = []
        
        for insight in insights:
            # Find entities mentioned in insight
            insight_text = insight.content.lower()
            mentioned_entities = []
            
            for entity in entities:
                if entity.name.lower() in insight_text:
                    mentioned_entities.append(entity.id)
            
            if len(mentioned_entities) >= 2:
                # Check which communities these entities belong to
                communities_touched = set()
                for entity_id in mentioned_entities:
                    comm = level_communities.get(entity_id)
                    if comm is not None:
                        communities_touched.add(comm)
                
                if len(communities_touched) >= 2:
                    bridge_insight = BridgeInsight(
                        id=insight.id,
                        content=insight.content,
                        key_insight=getattr(insight, 'key_insight', False),
                        communities_bridged=len(communities_touched),
                        bridge_score=len(communities_touched) / max(len(mentioned_entities), 1)
                    )
                    bridge_insights.append(bridge_insight)
        
        # Sort by bridge score
        bridge_insights.sort(key=lambda x: x.bridge_score, reverse=True)
        
        return bridge_insights[:20]  # Return top 20
    
    def analyze_episode_discourse(
        self,
        episode_id: str,
        entities: List[Entity],
        insights: List[Insight],
        segments: List[Any],
        llm_provider: Optional[LLMProvider] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive discourse analysis on an episode
        
        Args:
            episode_id: Episode identifier
            entities: List of entities
            insights: List of insights
            segments: List of segments
            llm_provider: Optional LLM provider for topic naming
            
        Returns:
            Dictionary of discourse analysis results
        """
        try:
            logger.info(f"Starting discourse analysis for episode {episode_id}")
            
            # Step 1: Extract co-occurrences and build graph
            logger.info("Extracting weighted co-occurrences...")
            co_occurrences = self.extract_weighted_co_occurrences(entities, segments)
            nodes, edges = self.build_graph_from_entities_and_insights(
                entities, insights, co_occurrences
            )
            
            # Step 2: Calculate betweenness centrality
            logger.info("Calculating betweenness centrality...")
            centrality_results = self.calculate_betweenness_centrality(nodes, edges)
            
            # Step 3: Multi-level community detection
            logger.info("Detecting communities at multiple levels...")
            community_results, node_names = self.detect_communities_multi_level(nodes, edges)
            
            # Step 4: Create hierarchical topics
            logger.info("Creating hierarchical topic structure...")
            topics_created = self.create_hierarchical_topics(
                community_results, node_names, llm_provider
            )
            
            # Step 5: Calculate segment mentions
            segment_mentions = {}
            for entity in entities:
                count = 0
                for segment in segments:
                    segment_text = segment.text.lower() if hasattr(segment, 'text') else str(segment).lower()
                    if entity.name.lower() in segment_text:
                        count += 1
                segment_mentions[entity.id] = count
            
            # Step 6: Identify peripheral concepts
            logger.info("Identifying peripheral concepts...")
            peripheral_concepts = self.identify_peripheral_concepts(
                entities, edges, segment_mentions
            )
            
            # Step 7: Calculate discourse structure
            logger.info("Analyzing discourse structure...")
            discourse_structure = self.calculate_discourse_structure(
                centrality_results, community_results
            )
            
            # Step 8: Calculate diversity metrics
            logger.info("Calculating diversity metrics...")
            total_words = sum(
                len(segment.text.split()) if hasattr(segment, 'text') else 0 
                for segment in segments
            )
            diversity_metrics = self.calculate_diversity_metrics(
                entities, insights, edges, community_results, total_words
            )
            
            # Step 9: Identify structural gaps
            logger.info("Identifying structural gaps...")
            structural_gaps = self.identify_structural_gaps(
                community_results, edges, node_names
            )
            
            # Step 9a: Enhance gap analysis
            logger.info("Enhancing structural gap analysis...")
            enhanced_gaps = []
            enhanced_analyzer = self.EnhancedGapAnalyzer(self)
            for gap in structural_gaps:
                try:
                    enhanced_gap = self.enhance_gap_analysis(gap, entities)
                    enhanced_gaps.append(enhanced_gap)
                except Exception as e:
                    logger.warning(f"Failed to enhance gap analysis: {e}")
                    # Fall back to basic gap info
                    enhanced_gaps.append({
                        'gap_id': f"community_{gap.community_1}_to_{gap.community_2}",
                        'community_1': gap.community_1,
                        'community_2': gap.community_2,
                        'connection_count': gap.connection_count,
                        'representative_concepts_1': gap.representative_concepts_1,
                        'representative_concepts_2': gap.representative_concepts_2,
                        'gap_score': gap.gap_score
                    })
            
            # Prioritize enhanced gaps
            prioritized_gaps = enhanced_analyzer.prioritize_gaps(enhanced_gaps)
            
            # Step 10: Identify bridge insights
            logger.info("Identifying bridge insights...")
            bridge_insights = self.identify_bridge_insights(
                insights, entities, community_results
            )
            
            # Compile results
            results = {
                'episode_id': episode_id,
                'discourse_structure': {
                    'type': discourse_structure.type.value,
                    'description': self._get_discourse_description(discourse_structure.type),
                    'influence_entropy': discourse_structure.influence_entropy,
                    'modularity_score': discourse_structure.modularity_score,
                    'top_influencers': discourse_structure.top_influencers,
                    'confidence': discourse_structure.confidence
                },
                'diversity_metrics': {
                    'topic_diversity': diversity_metrics.topic_diversity,
                    'connection_richness': diversity_metrics.connection_richness,
                    'concept_density': diversity_metrics.concept_density,
                    'entity_count': diversity_metrics.entity_count,
                    'insight_count': diversity_metrics.insight_count,
                    'community_count': diversity_metrics.community_count
                },
                'topics_created': len(topics_created),
                'topics': [
                    {
                        'id': t.id,
                        'name': t.name,
                        'level': t.level,
                        'member_count': t.member_count,
                        'top_concepts': t.top_concepts
                    }
                    for t in topics_created[:10]  # Top 10 topics
                ],
                'peripheral_concepts': len(peripheral_concepts),
                'peripheral_samples': [
                    {
                        'name': pc.name,
                        'type': pc.type,
                        'exploration_potential': pc.exploration_potential
                    }
                    for pc in peripheral_concepts[:5]  # Top 5
                ],
                'structural_gaps': len(structural_gaps),
                'enhanced_structural_gaps': prioritized_gaps[:3],  # Top 3 prioritized enhanced gaps
                'gap_samples': [
                    {
                        'concepts_1': sg.representative_concepts_1,
                        'concepts_2': sg.representative_concepts_2,
                        'gap_score': sg.gap_score
                    }
                    for sg in structural_gaps[:3]  # Top 3
                ],
                'bridge_insights': len(bridge_insights),
                'bridge_samples': [
                    {
                        'content': bi.content[:100] + '...' if len(bi.content) > 100 else bi.content,
                        'communities_bridged': bi.communities_bridged,
                        'bridge_score': bi.bridge_score
                    }
                    for bi in bridge_insights[:3]  # Top 3
                ],
                'nodes_with_centrality': len(centrality_results),
                'graph_stats': {
                    'num_nodes': len(nodes),
                    'num_edges': len(edges),
                    'num_entities': len(entities),
                    'num_insights': len(insights),
                    'num_communities': len(community_results) if community_results else 0
                }
            }
            
            logger.info(f"Discourse analysis completed for episode {episode_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to analyze episode discourse: {e}")
            return {
                'episode_id': episode_id,
                'discourse_structure': {
                    'type': 'unknown',
                    'description': 'Analysis failed'
                },
                'diversity_metrics': {},
                'topics_created': 0,
                'peripheral_concepts': 0,
                'structural_gaps': 0,
                'enhanced_structural_gaps': [],
                'bridge_insights': 0,
                'nodes_with_centrality': 0,
                'error': str(e)
            }
    
    def _get_discourse_description(self, discourse_type: DiscourseType) -> str:
        """Get human-readable description of discourse type"""
        descriptions = {
            DiscourseType.HIERARCHICAL: "Centralized discussion with dominant themes",
            DiscourseType.MODULAR: "Multiple distinct topic clusters",
            DiscourseType.SEQUENTIAL: "Linear progression of ideas",
            DiscourseType.EMERGENT: "Organic, exploratory conversation"
        }
        return descriptions.get(discourse_type, "Unknown discourse structure")