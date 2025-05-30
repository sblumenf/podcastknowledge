"""Comprehensive tests for graph analysis module.

Tests for src/processing/graph_analysis.py covering all graph analysis functionality.
"""

import pytest
from unittest import mock
from typing import List, Dict, Any, Set

from src.processing.graph_analysis import (
    GraphAnalyzer, AnalysisResult, NodeMetrics, GraphMetrics,
    CommunityDetectionResult, PathAnalysis
)
from src.providers.graph.base import GraphProvider
from src.core.models import Entity, EntityType


class TestGraphAnalyzer:
    """Test GraphAnalyzer class."""
    
    @pytest.fixture
    def mock_graph_provider(self):
        """Create mock graph provider."""
        provider = mock.Mock(spec=GraphProvider)
        provider.execute_query = mock.Mock()
        provider.get_node_count = mock.Mock(return_value=100)
        provider.get_relationship_count = mock.Mock(return_value=250)
        return provider
    
    @pytest.fixture
    def analyzer(self, mock_graph_provider):
        """Create graph analyzer instance."""
        return GraphAnalyzer(
            graph_provider=mock_graph_provider,
            enable_community_detection=True,
            enable_centrality_analysis=True
        )
    
    def test_analyzer_initialization(self, mock_graph_provider):
        """Test analyzer initialization."""
        analyzer = GraphAnalyzer(
            graph_provider=mock_graph_provider,
            enable_community_detection=False,
            enable_centrality_analysis=False,
            min_community_size=10
        )
        
        assert analyzer.graph_provider == mock_graph_provider
        assert analyzer.enable_community_detection is False
        assert analyzer.enable_centrality_analysis is False
        assert analyzer.min_community_size == 10
    
    def test_analyze_graph_structure(self, analyzer, mock_graph_provider):
        """Test basic graph structure analysis."""
        # Mock query responses
        mock_graph_provider.execute_query.side_effect = [
            # Node count by type
            [
                {"type": "Person", "count": 50},
                {"type": "Organization", "count": 30},
                {"type": "Concept", "count": 20}
            ],
            # Relationship count by type
            [
                {"type": "MENTIONS", "count": 150},
                {"type": "RELATES_TO", "count": 100}
            ],
            # Density calculation nodes
            [{"node_count": 100}],
            # Density calculation relationships
            [{"rel_count": 250}]
        ]
        
        result = analyzer.analyze_graph_structure()
        
        assert isinstance(result, GraphMetrics)
        assert result.node_count == 100
        assert result.relationship_count == 250
        assert len(result.node_type_distribution) == 3
        assert result.node_type_distribution["Person"] == 50
        assert result.density > 0
    
    def test_calculate_node_centrality(self, analyzer, mock_graph_provider):
        """Test node centrality calculation."""
        node_id = "entity_123"
        
        # Mock centrality queries
        mock_graph_provider.execute_query.side_effect = [
            # Degree centrality
            [{"degree": 15}],
            # Betweenness centrality
            [{"betweenness": 0.045}],
            # Closeness centrality
            [{"closeness": 0.523}],
            # PageRank
            [{"pagerank": 0.0034}]
        ]
        
        metrics = analyzer.calculate_node_centrality(node_id)
        
        assert isinstance(metrics, NodeMetrics)
        assert metrics.node_id == node_id
        assert metrics.degree_centrality == 15
        assert metrics.betweenness_centrality == 0.045
        assert metrics.closeness_centrality == 0.523
        assert metrics.pagerank == 0.0034
    
    def test_detect_communities(self, analyzer, mock_graph_provider):
        """Test community detection."""
        # Mock community detection results
        mock_graph_provider.execute_query.return_value = [
            {"communityId": 0, "nodeId": "entity_1", "name": "AI Research"},
            {"communityId": 0, "nodeId": "entity_2", "name": "Machine Learning"},
            {"communityId": 1, "nodeId": "entity_3", "name": "Healthcare"},
            {"communityId": 1, "nodeId": "entity_4", "name": "Medicine"},
            {"communityId": 1, "nodeId": "entity_5", "name": "Biotechnology"}
        ]
        
        result = analyzer.detect_communities()
        
        assert isinstance(result, CommunityDetectionResult)
        assert len(result.communities) == 2
        assert len(result.communities[0]) == 2
        assert len(result.communities[1]) == 3
        assert result.modularity == 0.0  # Default when not calculated
    
    def test_find_shortest_paths(self, analyzer, mock_graph_provider):
        """Test shortest path finding."""
        source = "entity_1"
        target = "entity_5"
        
        # Mock path query result
        mock_graph_provider.execute_query.return_value = [
            {
                "path": {
                    "nodes": ["entity_1", "entity_3", "entity_5"],
                    "relationships": ["REL_1", "REL_2"],
                    "length": 2
                }
            }
        ]
        
        paths = analyzer.find_shortest_paths(source, target, max_paths=5)
        
        assert isinstance(paths, list)
        assert len(paths) == 1
        assert isinstance(paths[0], PathAnalysis)
        assert paths[0].source == source
        assert paths[0].target == target
        assert paths[0].length == 2
        assert len(paths[0].nodes) == 3
    
    def test_find_connected_components(self, analyzer, mock_graph_provider):
        """Test connected component detection."""
        # Mock component query
        mock_graph_provider.execute_query.return_value = [
            {"componentId": 0, "nodeId": "entity_1"},
            {"componentId": 0, "nodeId": "entity_2"},
            {"componentId": 0, "nodeId": "entity_3"},
            {"componentId": 1, "nodeId": "entity_4"},
            {"componentId": 1, "nodeId": "entity_5"}
        ]
        
        components = analyzer.find_connected_components()
        
        assert len(components) == 2
        assert len(components[0]) == 3
        assert len(components[1]) == 2
        assert "entity_1" in components[0]
        assert "entity_4" in components[1]
    
    def test_calculate_clustering_coefficient(self, analyzer, mock_graph_provider):
        """Test clustering coefficient calculation."""
        node_id = "entity_123"
        
        # Mock clustering queries
        mock_graph_provider.execute_query.side_effect = [
            # Node's neighbors
            [{"neighbor": "entity_1"}, {"neighbor": "entity_2"}, {"neighbor": "entity_3"}],
            # Connections between neighbors
            [{"connections": 2}]
        ]
        
        coefficient = analyzer.calculate_clustering_coefficient(node_id)
        
        # With 3 neighbors and 2 connections, coefficient = 2/(3*2/2) = 2/3
        assert 0.66 <= coefficient <= 0.67
    
    def test_find_influential_nodes(self, analyzer, mock_graph_provider):
        """Test finding influential nodes."""
        # Mock influential nodes query
        mock_graph_provider.execute_query.return_value = [
            {"nodeId": "entity_1", "name": "AI", "score": 0.95},
            {"nodeId": "entity_2", "name": "Machine Learning", "score": 0.87},
            {"nodeId": "entity_3", "name": "Deep Learning", "score": 0.82}
        ]
        
        influential = analyzer.find_influential_nodes(
            metric="pagerank",
            limit=3
        )
        
        assert len(influential) == 3
        assert influential[0]["nodeId"] == "entity_1"
        assert influential[0]["score"] == 0.95
        # Should be sorted by score descending
        assert influential[0]["score"] >= influential[1]["score"]
        assert influential[1]["score"] >= influential[2]["score"]
    
    def test_analyze_node_neighborhood(self, analyzer, mock_graph_provider):
        """Test node neighborhood analysis."""
        node_id = "entity_123"
        
        # Mock neighborhood queries
        mock_graph_provider.execute_query.side_effect = [
            # Direct neighbors
            [
                {"neighbor": "entity_1", "relationship": "RELATES_TO"},
                {"neighbor": "entity_2", "relationship": "MENTIONS"},
                {"neighbor": "entity_3", "relationship": "RELATES_TO"}
            ],
            # Second-degree neighbors
            [
                {"neighbor": "entity_4", "distance": 2},
                {"neighbor": "entity_5", "distance": 2}
            ]
        ]
        
        neighborhood = analyzer.analyze_node_neighborhood(node_id, depth=2)
        
        assert "direct_neighbors" in neighborhood
        assert len(neighborhood["direct_neighbors"]) == 3
        assert "second_degree_neighbors" in neighborhood
        assert len(neighborhood["second_degree_neighbors"]) == 2
    
    def test_calculate_graph_density(self, analyzer, mock_graph_provider):
        """Test graph density calculation."""
        mock_graph_provider.execute_query.side_effect = [
            [{"node_count": 50}],
            [{"rel_count": 200}]
        ]
        
        density = analyzer.calculate_graph_density()
        
        # Density = edges / (nodes * (nodes-1))
        # For directed graph: 200 / (50 * 49) = 0.0816...
        assert 0.08 <= density <= 0.09
    
    def test_find_bridges(self, analyzer, mock_graph_provider):
        """Test bridge edge detection."""
        # Mock bridge detection query
        mock_graph_provider.execute_query.return_value = [
            {
                "source": "entity_1",
                "target": "entity_5",
                "relationship": "CONNECTS",
                "importance": 0.9
            },
            {
                "source": "entity_10",
                "target": "entity_20",
                "relationship": "LINKS",
                "importance": 0.85
            }
        ]
        
        bridges = analyzer.find_bridges()
        
        assert len(bridges) == 2
        assert bridges[0]["source"] == "entity_1"
        assert bridges[0]["importance"] == 0.9
    
    def test_analysis_result_aggregation(self, analyzer, mock_graph_provider):
        """Test comprehensive analysis result."""
        # Mock various queries for full analysis
        mock_graph_provider.execute_query.side_effect = [
            # Structure analysis
            [{"type": "Entity", "count": 100}],
            [{"type": "RELATES_TO", "count": 250}],
            [{"node_count": 100}],
            [{"rel_count": 250}],
            # Community detection
            [
                {"communityId": 0, "nodeId": "e1"},
                {"communityId": 0, "nodeId": "e2"},
                {"communityId": 1, "nodeId": "e3"}
            ],
            # Influential nodes
            [{"nodeId": "e1", "score": 0.9}]
        ]
        
        result = analyzer.perform_full_analysis()
        
        assert isinstance(result, AnalysisResult)
        assert result.graph_metrics is not None
        assert result.communities is not None
        assert result.influential_nodes is not None
        assert result.timestamp is not None


class TestMetricsDataclasses:
    """Test metrics dataclasses."""
    
    def test_node_metrics_creation(self):
        """Test NodeMetrics dataclass."""
        metrics = NodeMetrics(
            node_id="test_123",
            degree_centrality=10,
            betweenness_centrality=0.05,
            closeness_centrality=0.4,
            pagerank=0.003,
            clustering_coefficient=0.67
        )
        
        assert metrics.node_id == "test_123"
        assert metrics.degree_centrality == 10
        assert metrics.clustering_coefficient == 0.67
    
    def test_graph_metrics_creation(self):
        """Test GraphMetrics dataclass."""
        metrics = GraphMetrics(
            node_count=1000,
            relationship_count=5000,
            density=0.005,
            average_degree=10.0,
            diameter=6,
            node_type_distribution={"Person": 600, "Organization": 400},
            relationship_type_distribution={"KNOWS": 3000, "WORKS_AT": 2000}
        )
        
        assert metrics.node_count == 1000
        assert metrics.density == 0.005
        assert metrics.node_type_distribution["Person"] == 600
    
    def test_path_analysis_creation(self):
        """Test PathAnalysis dataclass."""
        path = PathAnalysis(
            source="node_1",
            target="node_5",
            length=3,
            nodes=["node_1", "node_2", "node_4", "node_5"],
            relationships=["rel_1", "rel_2", "rel_3"],
            total_weight=2.5
        )
        
        assert path.source == "node_1"
        assert path.length == 3
        assert len(path.nodes) == 4
        assert path.total_weight == 2.5


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer for edge case testing."""
        mock_provider = mock.Mock()
        mock_provider.execute_query = mock.Mock(return_value=[])
        return GraphAnalyzer(graph_provider=mock_provider)
    
    def test_empty_graph_analysis(self, analyzer):
        """Test analysis on empty graph."""
        analyzer.graph_provider.get_node_count.return_value = 0
        analyzer.graph_provider.get_relationship_count.return_value = 0
        
        result = analyzer.analyze_graph_structure()
        
        assert result.node_count == 0
        assert result.relationship_count == 0
        assert result.density == 0.0
    
    def test_single_node_graph(self, analyzer):
        """Test analysis on graph with single node."""
        analyzer.graph_provider.get_node_count.return_value = 1
        analyzer.graph_provider.get_relationship_count.return_value = 0
        
        # Single node centrality
        metrics = analyzer.calculate_node_centrality("single_node")
        
        assert metrics.degree_centrality == 0
        assert metrics.betweenness_centrality == 0.0
    
    def test_disconnected_graph_communities(self, analyzer):
        """Test community detection on disconnected graph."""
        # Mock disconnected components
        analyzer.graph_provider.execute_query.return_value = [
            {"communityId": 0, "nodeId": "island_1"},
            {"communityId": 1, "nodeId": "island_2"},
            {"communityId": 2, "nodeId": "island_3"}
        ]
        
        result = analyzer.detect_communities()
        
        # Each node is its own community
        assert len(result.communities) == 3
        assert all(len(community) == 1 for community in result.communities)
    
    def test_query_failure_handling(self, analyzer):
        """Test handling of query failures."""
        analyzer.graph_provider.execute_query.side_effect = Exception("Database error")
        
        # Should handle error gracefully
        result = analyzer.analyze_graph_structure()
        assert result.node_count == 0  # Falls back to provider method
        
        # Should return empty results on error
        paths = analyzer.find_shortest_paths("a", "b")
        assert paths == []
    
    def test_large_graph_performance_limits(self, analyzer):
        """Test handling of large graph queries."""
        # Mock large result set
        large_result = [{"nodeId": f"node_{i}"} for i in range(10000)]
        analyzer.graph_provider.execute_query.return_value = large_result
        
        # Should handle large results
        influential = analyzer.find_influential_nodes(limit=100)
        assert len(influential) <= 100  # Respects limit
    
    def test_invalid_node_ids(self, analyzer):
        """Test handling of invalid node IDs."""
        # Empty result for non-existent node
        analyzer.graph_provider.execute_query.return_value = []
        
        metrics = analyzer.calculate_node_centrality("non_existent_node")
        
        assert metrics.degree_centrality == 0
        assert metrics.pagerank == 0.0
    
    def test_cyclic_paths(self, analyzer):
        """Test handling of cyclic paths."""
        # Mock cyclic path
        analyzer.graph_provider.execute_query.return_value = [
            {
                "path": {
                    "nodes": ["a", "b", "c", "a"],  # Cycle
                    "relationships": ["r1", "r2", "r3"],
                    "length": 3
                }
            }
        ]
        
        paths = analyzer.find_shortest_paths("a", "a")
        
        # Should handle cycles
        assert len(paths) == 1
        assert paths[0].source == "a"
        assert paths[0].target == "a"