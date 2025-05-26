"""
Graph analysis and enhancement functionality
"""
import logging
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
from itertools import combinations

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
    
    def __init__(self):
        """Initialize graph analyzer"""
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Graph analysis features will be limited.")
        if not SCIPY_AVAILABLE:
            logger.warning("SciPy not available. Some analysis features will be limited.")
    
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