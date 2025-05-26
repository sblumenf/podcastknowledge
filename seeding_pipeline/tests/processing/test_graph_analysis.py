"""
Tests for graph analysis functionality
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List, Tuple

from src.core.models import Entity, Insight, EntityType, InsightType
from src.core.interfaces import LLMProvider
from src.processing.graph_analysis import (
    GraphAnalyzer, DiscourseType, CentralityResult, CommunityResult,
    PeripheralConcept, DiscourseStructure, DiversityMetrics,
    StructuralGap, HierarchicalTopic, BridgeInsight
)


class TestGraphAnalyzer:
    """Test suite for GraphAnalyzer class"""
    
    @pytest.fixture
    def analyzer(self):
        """Create a GraphAnalyzer instance"""
        return GraphAnalyzer()
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities"""
        return [
            Entity(
                id="e1",
                name="Machine Learning",
                type=EntityType.TECHNOLOGY,
                confidence=0.9
            ),
            Entity(
                id="e2",
                name="Neural Networks",
                type=EntityType.TECHNOLOGY,
                confidence=0.85
            ),
            Entity(
                id="e3",
                name="Google",
                type=EntityType.ORGANIZATION,
                confidence=0.95
            ),
            Entity(
                id="e4",
                name="Data Science",
                type=EntityType.CONCEPT,
                confidence=0.88
            )
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Create sample insights"""
        return [
            Insight(
                id="i1",
                content="Machine learning is revolutionizing data science",
                type=InsightType.TREND,
                confidence=0.8
            ),
            Insight(
                id="i2",
                content="Neural networks are a key component of ML systems",
                type=InsightType.TECHNICAL_DETAIL,
                confidence=0.9
            ),
            Insight(
                id="i3",
                content="Google is investing heavily in AI research",
                type=InsightType.BUSINESS_INSIGHT,
                confidence=0.85
            )
        ]
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments"""
        class Segment:
            def __init__(self, text):
                self.text = text
        
        return [
            Segment("Machine Learning and Neural Networks are transforming technology"),
            Segment("Google is leading the way in Data Science applications"),
            Segment("Neural Networks enable complex pattern recognition")
        ]
    
    def test_extract_weighted_co_occurrences(self, analyzer, sample_entities, sample_segments):
        """Test weighted co-occurrence extraction"""
        co_occurrences = analyzer.extract_weighted_co_occurrences(
            sample_entities, sample_segments
        )
        
        assert isinstance(co_occurrences, list)
        assert len(co_occurrences) > 0
        
        # Check format
        for source, target, weight in co_occurrences:
            assert isinstance(source, str)
            assert isinstance(target, str)
            assert isinstance(weight, (int, float))
            assert weight > 0
        
        # Should find ML and NN co-occurrence
        ml_nn_found = False
        for source, target, weight in co_occurrences:
            if (source == "e1" and target == "e2") or (source == "e2" and target == "e1"):
                ml_nn_found = True
                break
        assert ml_nn_found
    
    @patch('src.processing.graph_analysis.NETWORKX_AVAILABLE', True)
    @patch('src.processing.graph_analysis.nx')
    def test_calculate_betweenness_centrality(self, mock_nx, analyzer):
        """Test betweenness centrality calculation"""
        # Mock NetworkX
        mock_graph = MagicMock()
        mock_nx.Graph.return_value = mock_graph
        mock_nx.betweenness_centrality.return_value = {
            'e1': 0.5,
            'e2': 0.3,
            'e3': 0.1
        }
        
        nodes = [
            {'id': 'e1', 'name': 'ML', 'type': 'technology'},
            {'id': 'e2', 'name': 'NN', 'type': 'technology'},
            {'id': 'e3', 'name': 'Google', 'type': 'organization'}
        ]
        edges = [('e1', 'e2', 1.0), ('e2', 'e3', 0.5)]
        
        results = analyzer.calculate_betweenness_centrality(nodes, edges)
        
        assert len(results) == 3
        assert all(isinstance(r, CentralityResult) for r in results)
        assert results[0].centrality_score == 0.5  # Highest score first
        assert results[0].node_id == 'e1'
    
    @patch('src.processing.graph_analysis.NETWORKX_AVAILABLE', True)
    @patch('src.processing.graph_analysis.nx')
    @patch('src.processing.graph_analysis.community')
    def test_detect_communities_multi_level(self, mock_community, mock_nx, analyzer):
        """Test multi-level community detection"""
        # Mock NetworkX
        mock_graph = MagicMock()
        mock_nx.Graph.return_value = mock_graph
        
        # Mock community detection
        mock_community.louvain_communities.side_effect = [
            [{'e1', 'e2'}, {'e3', 'e4'}],  # Level 1: 2 communities
            [{'e1'}, {'e2'}, {'e3', 'e4'}],  # Level 2: 3 communities
            [{'e1'}, {'e2'}, {'e3'}, {'e4'}]  # Level 3: 4 communities
        ]
        mock_community.modularity.return_value = 0.4
        
        nodes = [
            {'id': 'e1', 'name': 'ML'},
            {'id': 'e2', 'name': 'NN'},
            {'id': 'e3', 'name': 'Google'},
            {'id': 'e4', 'name': 'DS'}
        ]
        edges = [('e1', 'e2', 1.0), ('e3', 'e4', 1.0)]
        
        community_results, node_names = analyzer.detect_communities_multi_level(
            nodes, edges
        )
        
        assert len(community_results) == 3  # 3 resolution levels
        assert community_results[0].num_communities == 2
        assert community_results[1].num_communities == 3
        assert community_results[2].num_communities == 4
        assert 'e1' in node_names
    
    def test_identify_peripheral_concepts(self, analyzer, sample_entities):
        """Test peripheral concept identification"""
        edges = [
            ('e1', 'e2', 1.0),  # ML connected to NN
            ('e1', 'e3', 1.0),  # ML connected to Google
            # e4 (Data Science) has only one connection
            ('e1', 'e4', 1.0)
        ]
        
        segment_mentions = {
            'e1': 5,  # ML mentioned 5 times
            'e2': 3,  # NN mentioned 3 times
            'e3': 2,  # Google mentioned 2 times
            'e4': 2   # DS mentioned 2 times
        }
        
        peripheral = analyzer.identify_peripheral_concepts(
            sample_entities, edges, segment_mentions
        )
        
        assert isinstance(peripheral, list)
        # e4 should be peripheral (low degree but mentioned multiple times)
        peripheral_ids = [p.id for p in peripheral]
        assert 'e4' in peripheral_ids or 'e3' in peripheral_ids
    
    @patch('src.processing.graph_analysis.SCIPY_AVAILABLE', True)
    @patch('src.processing.graph_analysis.entropy')
    def test_calculate_discourse_structure(self, mock_entropy, analyzer):
        """Test discourse structure calculation"""
        mock_entropy.return_value = 1.2
        
        centrality_results = [
            CentralityResult('e1', 'ML', 0.6, 'technology'),
            CentralityResult('e2', 'NN', 0.2, 'technology'),
            CentralityResult('e3', 'Google', 0.1, 'organization')
        ]
        
        community_data = [
            CommunityResult(
                resolution=1.0,
                communities={'e1': 0, 'e2': 0, 'e3': 1},
                num_communities=2,
                modularity=0.3
            )
        ]
        
        discourse = analyzer.calculate_discourse_structure(
            centrality_results, community_data
        )
        
        assert isinstance(discourse, DiscourseStructure)
        assert discourse.type == DiscourseType.HIERARCHICAL  # High centrality, low entropy
        assert discourse.influence_entropy == 1.2
        assert len(discourse.top_influencers) > 0
    
    def test_calculate_diversity_metrics(self, analyzer, sample_entities, sample_insights):
        """Test diversity metrics calculation"""
        edges = [('e1', 'e2', 1.0), ('e2', 'e3', 1.0)]
        community_data = [
            CommunityResult(1.0, {'e1': 0, 'e2': 0, 'e3': 1}, 2)
        ]
        
        metrics = analyzer.calculate_diversity_metrics(
            sample_entities, sample_insights, edges, community_data, 1000
        )
        
        assert isinstance(metrics, DiversityMetrics)
        assert metrics.entity_count == len(sample_entities)
        assert metrics.insight_count == len(sample_insights)
        assert metrics.concept_density > 0
        assert 0 <= metrics.topic_diversity <= 1
    
    def test_identify_structural_gaps(self, analyzer):
        """Test structural gap identification"""
        community_data = [
            CommunityResult(
                resolution=1.0,
                communities={
                    'e1': 0, 'e2': 0,  # Community 0
                    'e3': 1, 'e4': 1   # Community 1
                },
                num_communities=2
            )
        ]
        
        # Only one edge between communities
        edges = [
            ('e1', 'e2', 1.0),  # Within community 0
            ('e3', 'e4', 1.0),  # Within community 1
            ('e1', 'e3', 1.0)   # Between communities
        ]
        
        node_names = {
            'e1': 'ML',
            'e2': 'NN',
            'e3': 'Google',
            'e4': 'DS'
        }
        
        gaps = analyzer.identify_structural_gaps(
            community_data, edges, node_names
        )
        
        assert isinstance(gaps, list)
        if gaps:  # Should find gap between communities
            assert gaps[0].connection_count < 3
            assert gaps[0].gap_score > 0
    
    def test_create_hierarchical_topics(self, analyzer):
        """Test hierarchical topic creation"""
        community_data = [
            CommunityResult(
                resolution=1.0,
                communities={'e1': 0, 'e2': 0, 'e3': 1},
                num_communities=2
            )
        ]
        
        node_names = {
            'e1': 'Machine Learning',
            'e2': 'Neural Networks',
            'e3': 'Google'
        }
        
        topics = analyzer.create_hierarchical_topics(
            community_data, node_names
        )
        
        assert isinstance(topics, list)
        assert len(topics) == 2  # Two communities
        assert all(isinstance(t, HierarchicalTopic) for t in topics)
        assert topics[0].member_count > 0
        assert len(topics[0].top_concepts) > 0
    
    def test_identify_bridge_insights(
        self, analyzer, sample_insights, sample_entities
    ):
        """Test bridge insight identification"""
        community_data = [
            CommunityResult(
                resolution=1.0,
                communities={
                    'e1': 0, 'e2': 0,  # ML and NN in community 0
                    'e3': 1, 'e4': 1   # Google and DS in community 1
                },
                num_communities=2
            )
        ]
        
        # First insight mentions entities from both communities
        bridge_insights = analyzer.identify_bridge_insights(
            sample_insights, sample_entities, community_data
        )
        
        assert isinstance(bridge_insights, list)
        # Should find insights that mention entities from different communities
        if bridge_insights:
            assert bridge_insights[0].communities_bridged >= 2
            assert bridge_insights[0].bridge_score > 0
    
    def test_analyze_episode_discourse(
        self, analyzer, sample_entities, sample_insights, sample_segments
    ):
        """Test comprehensive discourse analysis"""
        with patch('src.processing.graph_analysis.NETWORKX_AVAILABLE', True):
            with patch('src.processing.graph_analysis.nx') as mock_nx:
                # Mock NetworkX components
                mock_graph = MagicMock()
                mock_nx.Graph.return_value = mock_graph
                mock_nx.betweenness_centrality.return_value = {
                    'e1': 0.5, 'e2': 0.3, 'e3': 0.2, 'e4': 0.1
                }
                
                with patch('src.processing.graph_analysis.community') as mock_comm:
                    mock_comm.louvain_communities.return_value = [
                        {'e1', 'e2'}, {'e3', 'e4'}
                    ]
                    
                    results = analyzer.analyze_episode_discourse(
                        'episode-1',
                        sample_entities,
                        sample_insights,
                        sample_segments
                    )
        
        assert isinstance(results, dict)
        assert results['episode_id'] == 'episode-1'
        assert 'discourse_structure' in results
        assert 'diversity_metrics' in results
        assert 'topics_created' in results
        assert 'graph_stats' in results
        
        # Check discourse structure
        ds = results['discourse_structure']
        assert 'type' in ds
        assert 'description' in ds
        assert 'influence_entropy' in ds
    
    def test_build_graph_from_entities_and_insights(
        self, analyzer, sample_entities, sample_insights
    ):
        """Test graph building from entities and insights"""
        co_occurrences = [('e1', 'e2', 1.0)]
        
        nodes, edges = analyzer.build_graph_from_entities_and_insights(
            sample_entities, sample_insights, co_occurrences
        )
        
        assert len(nodes) == len(sample_entities) + len(sample_insights)
        assert len(edges) >= len(co_occurrences)
        
        # Check node structure
        entity_nodes = [n for n in nodes if n['type'] == 'entity']
        insight_nodes = [n for n in nodes if n['type'] == 'insight']
        
        assert len(entity_nodes) == len(sample_entities)
        assert len(insight_nodes) == len(sample_insights)
    
    def test_empty_inputs(self, analyzer):
        """Test handling of empty inputs"""
        # Empty entities and insights
        co_occurrences = analyzer.extract_weighted_co_occurrences([], [])
        assert co_occurrences == []
        
        # Empty nodes and edges
        centrality = analyzer.calculate_betweenness_centrality([], [])
        assert centrality == []
        
        # Empty community data
        peripheral = analyzer.identify_peripheral_concepts([], [], {})
        assert peripheral == []
    
    def test_discourse_type_description(self, analyzer):
        """Test discourse type descriptions"""
        for discourse_type in DiscourseType:
            description = analyzer._get_discourse_description(discourse_type)
            assert isinstance(description, str)
            assert len(description) > 0
    
    @patch('src.processing.graph_analysis.NETWORKX_AVAILABLE', False)
    def test_networkx_not_available(self, analyzer):
        """Test behavior when NetworkX is not available"""
        nodes = [{'id': 'e1', 'name': 'Test'}]
        edges = [('e1', 'e1', 1.0)]
        
        # Should return empty results
        centrality = analyzer.calculate_betweenness_centrality(nodes, edges)
        assert centrality == []
        
        communities, names = analyzer.detect_communities_multi_level(nodes, edges)
        assert communities == []
        assert names == {}