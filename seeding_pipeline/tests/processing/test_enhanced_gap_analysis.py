"""Tests for enhanced structural gap analysis functionality."""

from datetime import datetime

import networkx as nx
import numpy as np
import pytest

from src.core.models import Entity, Insight, EntityType, InsightType
from src.processing.graph_analysis import GraphAnalyzer, StructuralGap
class TestEnhancedGapAnalysis:
    """Test suite for enhanced gap analysis features."""
    
    @pytest.fixture
    def graph_analyzer(self):
        """Create a GraphAnalyzer instance."""
        return GraphAnalyzer()
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities with embeddings for testing."""
        # Create entities in two distinct semantic clusters
        entities = []
        
        # Cluster 1: AI/Technology entities
        ai_embedding = np.array([0.9, 0.1, 0.0, 0.0])
        ml_embedding = np.array([0.8, 0.2, 0.0, 0.0])
        tech_embedding = np.array([0.85, 0.15, 0.0, 0.0])
        
        entities.extend([
            Entity(
                id="entity_ai",
                name="Artificial Intelligence",
                entity_type=EntityType.CONCEPT,
                embedding=ai_embedding.tolist(),
                importance_score=0.9
            ),
            Entity(
                id="entity_ml",
                name="Machine Learning",
                entity_type=EntityType.CONCEPT,
                embedding=ml_embedding.tolist(),
                importance_score=0.8
            ),
            Entity(
                id="entity_tech",
                name="Technology",
                entity_type=EntityType.CONCEPT,
                embedding=tech_embedding.tolist(),
                importance_score=0.7
            )
        ])
        
        # Cluster 2: Healthcare entities
        health_embedding = np.array([0.0, 0.0, 0.9, 0.1])
        medicine_embedding = np.array([0.0, 0.0, 0.8, 0.2])
        patient_embedding = np.array([0.0, 0.0, 0.85, 0.15])
        
        entities.extend([
            Entity(
                id="entity_health",
                name="Healthcare",
                entity_type=EntityType.CONCEPT,
                embedding=health_embedding.tolist(),
                importance_score=0.85
            ),
            Entity(
                id="entity_medicine",
                name="Medicine",
                entity_type=EntityType.CONCEPT,
                embedding=medicine_embedding.tolist(),
                importance_score=0.75
            ),
            Entity(
                id="entity_patient",
                name="Patient Care",
                entity_type=EntityType.CONCEPT,
                embedding=patient_embedding.tolist(),
                importance_score=0.7
            )
        ])
        
        # Bridge entity: Digital Health
        bridge_embedding = np.array([0.4, 0.1, 0.4, 0.1])  # Between both clusters
        entities.append(
            Entity(
                id="entity_digital_health",
                name="Digital Health",
                entity_type=EntityType.CONCEPT,
                embedding=bridge_embedding.tolist(),
                importance_score=0.6
            )
        )
        
        return entities
    
    @pytest.fixture
    def sample_gap(self):
        """Create a sample structural gap."""
        return StructuralGap(
            community_1=1,
            community_2=2,
            connection_count=1,
            representative_concepts_1=["Artificial Intelligence", "Machine Learning", "Technology"],
            representative_concepts_2=["Healthcare", "Medicine", "Patient Care"],
            gap_score=0.8
        )
    
    def test_calculate_semantic_distance(self, graph_analyzer, sample_entities):
        """Test semantic distance calculation between communities."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Split entities into two communities
        comm1_entities = sample_entities[:3]  # AI cluster
        comm2_entities = sample_entities[3:6]  # Healthcare cluster
        
        distance_metrics = enhancer.calculate_semantic_distance(comm1_entities, comm2_entities)
        
        # Verify distance metrics structure
        assert "centroid_distance" in distance_metrics
        assert "min_pairwise_distance" in distance_metrics
        assert "max_pairwise_distance" in distance_metrics
        assert "avg_pairwise_distance" in distance_metrics
        
        # Communities should be semantically distant
        assert distance_metrics["centroid_distance"] > 0.7
        assert distance_metrics["min_pairwise_distance"] > 0.6
        
        # Test with empty communities
        empty_distance = enhancer.calculate_semantic_distance([], comm2_entities)
        assert empty_distance["centroid_distance"] == 1.0
        
        # Test with no embeddings
        no_emb_entities = [Entity(id="e1", name="Test", entity_type=EntityType.CONCEPT)]
        no_emb_distance = enhancer.calculate_semantic_distance(no_emb_entities, no_emb_entities)
        assert no_emb_distance["centroid_distance"] == 0.5  # Unknown distance
    
    def test_find_potential_bridges(self, graph_analyzer, sample_entities, sample_gap):
        """Test finding potential bridge concepts."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Set up gap with entity IDs
        gap_dict = {
            'community1_entities': ["entity_ai", "entity_ml", "entity_tech"],
            'community2_entities': ["entity_health", "entity_medicine", "entity_patient"],
            'connection_count': 1
        }
        
        bridges = enhancer.find_potential_bridges(gap_dict, sample_entities, top_n=3)
        
        # Should find Digital Health as the top bridge
        assert len(bridges) > 0
        assert bridges[0]['entity'].name == "Digital Health"
        assert bridges[0]['bridge_score'] > 0.3
        assert "similarity_to_community1" in bridges[0]
        assert "similarity_to_community2" in bridges[0]
        
        # Test with no bridge candidates
        gap_all_entities = {
            'community1_entities': [e.id for e in sample_entities],
            'community2_entities': []
        }
        no_bridges = enhancer.find_potential_bridges(gap_all_entities, sample_entities)
        assert len(no_bridges) == 0
    
    def test_calculate_gap_bridgeability(self, graph_analyzer):
        """Test gap bridgeability scoring."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # High bridgeability: close distance, good bridges
        gap_close = {
            'community1_entities': ["e1", "e2"],
            'community2_entities': ["e3", "e4"],
            'connection_count': 2
        }
        
        semantic_distance_close = {"centroid_distance": 0.3}
        bridges_good = [
            {"bridge_score": 0.8},
            {"bridge_score": 0.7},
            {"bridge_score": 0.6}
        ]
        
        high_bridgeability = enhancer.calculate_gap_bridgeability(
            gap_close, semantic_distance_close, bridges_good
        )
        assert high_bridgeability > 0.6
        
        # Low bridgeability: far distance, no bridges
        gap_far = {
            'community1_entities': ["e1"],
            'community2_entities': ["e3", "e4", "e5"],
            'connection_count': 0
        }
        
        semantic_distance_far = {"centroid_distance": 0.9}
        bridges_none = []
        
        low_bridgeability = enhancer.calculate_gap_bridgeability(
            gap_far, semantic_distance_far, bridges_none
        )
        assert low_bridgeability < 0.3
    
    def test_find_conceptual_paths(self, graph_analyzer, sample_entities):
        """Test finding conceptual paths between entities."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Find path from AI to Healthcare through Digital Health
        ai_entity = sample_entities[0]  # AI
        health_entity = sample_entities[3]  # Healthcare
        
        paths = enhancer.find_conceptual_paths(
            ai_entity, health_entity, sample_entities, max_hops=3
        )
        
        # Should find at least one path through Digital Health
        assert len(paths) > 0
        assert any("Digital Health" in [e.name for e in path] for path in paths)
        
        # Test with no embeddings
        no_emb1 = Entity(id="e1", name="Test1", entity_type=EntityType.CONCEPT)
        no_emb2 = Entity(id="e2", name="Test2", entity_type=EntityType.CONCEPT)
        no_paths = enhancer.find_conceptual_paths(no_emb1, no_emb2, sample_entities)
        assert len(no_paths) == 0
    
    def test_generate_enhanced_gap_report(self, graph_analyzer, sample_entities, sample_gap):
        """Test enhanced gap report generation."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Prepare gap dictionary
        gap_dict = {
            'community_1': sample_gap.community_1,
            'community_2': sample_gap.community_2,
            'connection_count': sample_gap.connection_count,
            'community1_entities': ["entity_ai", "entity_ml", "entity_tech"],
            'community2_entities': ["entity_health", "entity_medicine", "entity_patient"],
            'all_entities': sample_entities
        }
        
        report = enhancer.generate_enhanced_gap_report(gap_dict)
        
        # Verify report structure
        assert "gap_id" in report
        assert "semantic_analysis" in report
        assert "bridge_analysis" in report
        assert "exploration_suggestions" in report
        
        # Check semantic analysis
        assert "distance_metrics" in report["semantic_analysis"]
        assert "interpretation" in report["semantic_analysis"]
        
        # Check bridge analysis
        assert "potential_bridges" in report["bridge_analysis"]
        assert "bridgeability_score" in report["bridge_analysis"]
        assert "recommended_connections" in report["bridge_analysis"]
        
        # Should have suggestions
        assert len(report["exploration_suggestions"]) > 0
    
    def test_track_gap_evolution(self, graph_analyzer):
        """Test gap evolution tracking."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Previous gaps
        previous_gaps = [
            {"community_1": 1, "community_2": 2, "gap_score": 0.8},
            {"community_1": 3, "community_2": 4, "gap_score": 0.6},
            {"community_1": 5, "community_2": 6, "gap_score": 0.7}
        ]
        
        # Current gaps (1-2 bridged, 3-4 widened, 7-8 new)
        current_gaps = [
            {"community_1": 3, "community_2": 4, "gap_score": 0.9},  # Widened
            {"community_1": 5, "community_2": 6, "gap_score": 0.7},  # Stable
            {"community_1": 7, "community_2": 8, "gap_score": 0.5}   # New
        ]
        
        evolution = enhancer.track_gap_evolution(current_gaps, previous_gaps)
        
        assert len(evolution["new_gaps"]) == 1
        assert len(evolution["bridged_gaps"]) == 1
        assert len(evolution["widened_gaps"]) == 1
        assert len(evolution["stable_gaps"]) == 1
    
    def test_prioritize_gaps(self, graph_analyzer, sample_entities):
        """Test gap prioritization."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Create gaps with different characteristics
        gaps = [
            {
                "community_1": 1,
                "community_2": 2,
                "community1_entities": ["entity_ai", "entity_ml"],
                "community2_entities": ["entity_health"],
                "connection_count": 0,
                "bridgeability_score": 0.8,
                "all_entities": sample_entities
            },
            {
                "community_1": 3,
                "community_2": 4,
                "community1_entities": ["entity_tech"],
                "community2_entities": ["entity_medicine", "entity_patient"],
                "connection_count": 3,
                "bridgeability_score": 0.3,
                "all_entities": sample_entities
            }
        ]
        
        prioritized = enhancer.prioritize_gaps(gaps)
        
        # All gaps should have priority scores
        assert all("priority_score" in gap for gap in prioritized)
        
        # Should be sorted by priority
        scores = [gap["priority_score"] for gap in prioritized]
        assert scores == sorted(scores, reverse=True)
    
    def test_prepare_gap_visualization_data(self, graph_analyzer):
        """Test visualization data preparation."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Create enhanced gaps
        enhanced_gaps = [
            {
                "gap_id": "community_1_to_2",
                "community_1": 1,
                "community_2": 2,
                "representative_concepts_1": ["AI", "ML"],
                "representative_concepts_2": ["Health", "Medicine"],
                "community1_entities": ["e1", "e2"],
                "community2_entities": ["e3", "e4"],
                "semantic_analysis": {
                    "distance_metrics": {"centroid_distance": 0.7}
                },
                "bridge_analysis": {
                    "bridgeability_score": 0.6,
                    "potential_bridges": [
                        {"entity": Entity(id="b1", name="Bridge1", entity_type=EntityType.CONCEPT), 
                         "bridge_score": 0.8}
                    ]
                },
                "priority_score": 0.75
            }
        ]
        
        viz_data = enhancer.prepare_gap_visualization_data(enhanced_gaps)
        
        # Verify structure
        assert "communities" in viz_data
        assert "gaps" in viz_data
        assert "bridges" in viz_data
        assert "semantic_map" in viz_data
        
        # Check communities
        assert 1 in viz_data["communities"]
        assert 2 in viz_data["communities"]
        
        # Check gaps
        assert len(viz_data["gaps"]) == 1
        assert viz_data["gaps"][0]["distance"] == 0.7
        
        # Check bridges
        assert len(viz_data["bridges"]) == 1
        assert viz_data["bridges"][0]["entity"] == "Bridge1"
    
    def test_enhance_gap_analysis_integration(self, graph_analyzer, sample_entities, sample_gap):
        """Test the main enhance_gap_analysis method."""
        enhanced_report = graph_analyzer.enhance_gap_analysis(sample_gap, sample_entities)
        
        # Should include all original gap data
        assert enhanced_report["community_1"] == sample_gap.community_1
        assert enhanced_report["community_2"] == sample_gap.community_2
        assert enhanced_report["gap_score"] == sample_gap.gap_score
        
        # Should include enhanced analysis
        assert "gap_id" in enhanced_report
        assert "semantic_analysis" in enhanced_report
        assert "bridge_analysis" in enhanced_report
        assert "exploration_suggestions" in enhanced_report
    
    def test_error_handling(self, graph_analyzer):
        """Test error handling in enhanced gap analysis."""
        enhancer = graph_analyzer.EnhancedGapAnalyzer(graph_analyzer)
        
        # Test with invalid data
        invalid_gap = {"invalid": "data"}
        
        # Should handle gracefully
        try:
            report = enhancer.generate_enhanced_gap_report(invalid_gap)
            # Should still return a report structure
            assert isinstance(report, dict)
        except Exception as e:
            # Should not raise unhandled exceptions
            pytest.fail(f"Unhandled exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])