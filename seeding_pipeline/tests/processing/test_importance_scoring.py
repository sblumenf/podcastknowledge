"""Tests for multi-factor importance scoring module."""

from datetime import datetime
import math

import networkx as nx
import numpy as np
import pytest

from src.core.extraction_interface import Entity, Insight, Segment, EntityType, InsightType
from src.extraction.importance_scoring import ImportanceScorer
class TestImportanceScorer:
    """Test suite for ImportanceScorer class."""
    
    @pytest.fixture
    def scorer(self):
        """Create an ImportanceScorer instance."""
        return ImportanceScorer(
            max_expected_mentions_per_minute=2.0,
            embedding_dimension=384,
            temporal_decay_alpha=0.1
        )
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing."""
        entities = [
            Entity(
                id="entity_1",
                name="Machine Learning",
                entity_type=EntityType.CONCEPT,
                description="A type of artificial intelligence",
                mention_count=5,
                embedding=np.random.rand(384).tolist()
            ),
            Entity(
                id="entity_2",
                name="Python",
                entity_type=EntityType.TECHNOLOGY,
                description="Programming language",
                mention_count=3,
                embedding=np.random.rand(384).tolist()
            ),
            Entity(
                id="entity_3",
                name="Data Science",
                entity_type=EntityType.CONCEPT,
                description="Field combining statistics and computing",
                mention_count=7,
                embedding=np.random.rand(384).tolist()
            )
        ]
        return entities
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        segments = []
        for i in range(10):
            segments.append(Segment(
                id=f"segment_{i}",
                text=f"Sample text for segment {i}",
                start_time=i * 60.0,
                end_time=(i + 1) * 60.0,
                speaker="Host" if i % 2 == 0 else "Guest",
                segment_index=i
            ))
        return segments
    
    @pytest.fixture
    def sample_insights(self):
        """Create sample insights for testing."""
        return [
            Insight(
                id="insight_1",
                title="ML Impact",
                description="Machine Learning is transforming industries",
                insight_type=InsightType.KEY_POINT,
                supporting_entities=["entity_1", "entity_3"]
            ),
            Insight(
                id="insight_2",
                title="Python Dominance",
                description="Python is the leading language for Data Science",
                insight_type=InsightType.FACTUAL,
                supporting_entities=["entity_2", "entity_3"]
            )
        ]
    
    def test_calculate_frequency_factor(self, scorer):
        """Test frequency factor calculation."""
        # Test with normal mentions
        entity_mentions = [
            {"segment_index": 0, "timestamp": 30},
            {"segment_index": 2, "timestamp": 150},
            {"segment_index": 5, "timestamp": 330}
        ]
        episode_duration = 600.0  # 10 minutes
        
        score = scorer.calculate_frequency_factor(entity_mentions, episode_duration)
        
        # 3 mentions in 10 minutes = 0.3 mentions/minute
        # log(1 + 0.3) / log(1 + 2.0) ≈ 0.262 / 1.099 ≈ 0.239
        assert 0.2 < score < 0.3
        
        # Test with high frequency
        high_freq_mentions = [{"segment_index": i, "timestamp": i * 30} for i in range(20)]
        high_score = scorer.calculate_frequency_factor(high_freq_mentions, episode_duration)
        
        # Should be capped at 1.0
        assert 0.8 < high_score <= 1.0
        
        # Test edge cases
        assert scorer.calculate_frequency_factor([], 600.0) == 0.0
        assert scorer.calculate_frequency_factor(entity_mentions, 0.0) == 0.0
    
    def test_calculate_structural_centrality(self, scorer):
        """Test structural centrality calculation."""
        # Create a test graph
        G = nx.Graph()
        G.add_edges_from([
            ("entity_1", "entity_2"),
            ("entity_1", "entity_3"),
            ("entity_1", "entity_4"),
            ("entity_2", "entity_3"),
            ("entity_3", "entity_4"),
            ("entity_4", "entity_5")
        ])
        
        # Test entity with high centrality (entity_1 is well connected)
        centrality_1 = scorer.calculate_structural_centrality("entity_1", G)
        assert 0.5 < centrality_1 < 0.8
        
        # Test entity with low centrality (entity_5 is peripheral)
        centrality_5 = scorer.calculate_structural_centrality("entity_5", G)
        assert 0.1 < centrality_5 < 0.4
        
        # Test non-existent entity
        assert scorer.calculate_structural_centrality("entity_999", G) == 0.0
        
        # Test with empty graph
        empty_graph = nx.Graph()
        assert scorer.calculate_structural_centrality("entity_1", empty_graph) == 0.0
    
    def test_calculate_semantic_centrality(self, scorer):
        """Test semantic centrality calculation."""
        # Create embeddings with known similarities
        center_embedding = np.array([1.0, 0.0, 0.0])
        similar_embedding1 = np.array([0.9, 0.1, 0.0])
        similar_embedding2 = np.array([0.8, 0.2, 0.0])
        different_embedding = np.array([0.0, 1.0, 0.0])
        
        all_embeddings = [similar_embedding1, similar_embedding2, different_embedding]
        
        # Test central entity (similar to others)
        centrality = scorer.calculate_semantic_centrality(center_embedding, all_embeddings)
        assert 0.6 < centrality < 0.9
        
        # Test peripheral entity (different from others)
        periphery_centrality = scorer.calculate_semantic_centrality(
            different_embedding, 
            [center_embedding, similar_embedding1, similar_embedding2]
        )
        assert 0.3 < periphery_centrality < 0.6
        
        # Test edge cases
        assert scorer.calculate_semantic_centrality(None, all_embeddings) == 0.5
        assert scorer.calculate_semantic_centrality(center_embedding, []) == 0.5
    
    def test_analyze_discourse_function(self, scorer, sample_segments):
        """Test discourse function analysis."""
        # Entity mentioned early and late
        early_late_mentions = [
            {"segment_index": 0, "timestamp": 30},
            {"segment_index": 1, "timestamp": 90},
            {"segment_index": 8, "timestamp": 510},
            {"segment_index": 9, "timestamp": 570}
        ]
        
        discourse_funcs = scorer.analyze_discourse_function(early_late_mentions, sample_segments)
        
        assert discourse_funcs["introduction_role"] > 0.4  # Strong introduction
        assert discourse_funcs["conclusion_role"] > 0.4    # Strong conclusion
        assert discourse_funcs["development_role"] > 0.0
        assert discourse_funcs["bridge_role"] > 0.0
        
        # Entity mentioned only in middle
        middle_mentions = [
            {"segment_index": 4, "timestamp": 270},
            {"segment_index": 5, "timestamp": 330}
        ]
        
        middle_funcs = scorer.analyze_discourse_function(middle_mentions, sample_segments)
        assert middle_funcs["introduction_role"] < 0.2
        assert middle_funcs["conclusion_role"] < 0.2
        
        # Test empty mentions
        empty_funcs = scorer.analyze_discourse_function([], sample_segments)
        assert all(v == 0.0 for v in empty_funcs.values())
    
    def test_analyze_temporal_dynamics(self, scorer, sample_segments):
        """Test temporal dynamics analysis."""
        # Entity with increasing mentions (momentum)
        increasing_mentions = [
            {"segment_index": 0, "timestamp": 30},
            {"segment_index": 6, "timestamp": 390},
            {"segment_index": 7, "timestamp": 450},
            {"segment_index": 8, "timestamp": 510},
            {"segment_index": 9, "timestamp": 570}
        ]
        
        dynamics = scorer.analyze_temporal_dynamics(increasing_mentions, sample_segments)
        
        assert dynamics["recency_weight"] > 0.8  # Recent mentions
        assert dynamics["persistence_score"] > 0.8  # Long discussion
        assert dynamics["momentum"] > 0.0  # Positive momentum (increasing)
        
        # Entity mentioned only early
        early_only = [
            {"segment_index": 0, "timestamp": 30},
            {"segment_index": 1, "timestamp": 90}
        ]
        
        early_dynamics = scorer.analyze_temporal_dynamics(early_only, sample_segments)
        assert early_dynamics["recency_weight"] < 0.5  # Not recent
        assert early_dynamics["momentum"] < 0.0  # Negative momentum (decreasing)
        
        # Test empty mentions
        empty_dynamics = scorer.analyze_temporal_dynamics([], sample_segments)
        assert all(v == 0.0 for v in empty_dynamics.values())
    
    def test_calculate_cross_reference_score(self, scorer, sample_entities, sample_insights):
        """Test cross-reference score calculation."""
        # Entity 1 is referenced by insight 1
        # Entity 3 is referenced by both insights
        
        score_1 = scorer.calculate_cross_reference_score("entity_1", sample_entities, sample_insights)
        score_3 = scorer.calculate_cross_reference_score("entity_3", sample_entities, sample_insights)
        
        # Entity 3 should have higher score (referenced more)
        assert score_3 > score_1
        assert score_1 > 0.0
        
        # Test entity with no references
        score_2 = scorer.calculate_cross_reference_score("entity_2", sample_entities, sample_insights)
        assert score_2 > 0.0  # Still referenced in one insight
        
        # Test non-existent entity
        score_999 = scorer.calculate_cross_reference_score("entity_999", sample_entities, sample_insights)
        assert score_999 == 0.0
    
    def test_calculate_composite_importance(self, scorer):
        """Test composite importance calculation."""
        # Test with all factors
        all_factors = {
            "frequency": 0.8,
            "structural_centrality": 0.6,
            "semantic_centrality": 0.7,
            "introduction_role": 0.9,
            "development_role": 0.5,
            "conclusion_role": 0.3,
            "bridge_role": 0.4,
            "recency_weight": 0.8,
            "persistence_score": 0.6,
            "peak_influence": 0.7,
            "cross_reference": 0.5
        }
        
        composite = scorer.calculate_composite_importance(all_factors)
        
        # Should be weighted average
        assert 0.5 < composite < 0.8
        
        # Test with custom weights
        custom_weights = {
            "frequency": 1.0,  # Only frequency matters
            "structural_centrality": 0.0,
            "semantic_centrality": 0.0,
            "discourse_function": 0.0,
            "temporal_dynamics": 0.0,
            "cross_reference": 0.0
        }
        
        freq_only = scorer.calculate_composite_importance(all_factors, custom_weights)
        assert abs(freq_only - 0.8) < 0.01  # Should equal frequency factor
        
        # Test with missing factors
        partial_factors = {
            "frequency": 0.8,
            "structural_centrality": 0.6
        }
        
        partial_composite = scorer.calculate_composite_importance(partial_factors)
        assert 0.0 < partial_composite < 1.0
    
    def test_generate_importance_visualization_data(self, scorer, sample_entities):
        """Test visualization data generation."""
        # Add importance data to entities
        for i, entity in enumerate(sample_entities):
            entity.importance_score = 0.3 + (i * 0.2)  # 0.3, 0.5, 0.7
            entity.importance_factors = {
                "frequency": 0.5 + (i * 0.1),
                "structural_centrality": 0.4 + (i * 0.15),
                "semantic_centrality": 0.6,
                "introduction_role": 0.8 - (i * 0.2),
                "development_role": 0.5,
                "conclusion_role": 0.3 + (i * 0.1),
                "bridge_role": 0.4
            }
        
        viz_data = scorer.generate_importance_visualization_data(sample_entities)
        
        # Check structure
        assert "entities" in viz_data
        assert "importance_distribution" in viz_data
        assert "factor_correlations" in viz_data
        assert "top_by_factor" in viz_data
        
        # Check entity count
        assert len(viz_data["entities"]) == 3
        
        # Check distribution
        dist = viz_data["importance_distribution"]
        assert dist["counts"][1] == 1  # One entity in 0.2-0.4 range
        assert dist["counts"][2] == 1  # One entity in 0.4-0.6 range
        assert dist["counts"][3] == 1  # One entity in 0.6-0.8 range
        
        # Check top by factor
        assert len(viz_data["top_by_factor"]["frequency"]) <= 5
        assert len(viz_data["top_by_factor"]["structural_centrality"]) <= 5
    
    def test_filtering_utilities(self, scorer, sample_entities):
        """Test entity filtering utility methods."""
        # Add importance scores
        sample_entities[0].importance_score = 0.8
        sample_entities[1].importance_score = 0.5
        sample_entities[2].importance_score = 0.3
        
        # Test top N filtering
        top_2 = scorer.get_top_entities_by_importance(sample_entities, top_n=2)
        assert len(top_2) == 2
        assert top_2[0].importance_score == 0.8
        assert top_2[1].importance_score == 0.5
        
        # Test threshold filtering
        above_threshold = scorer.filter_entities_by_importance_threshold(sample_entities, threshold=0.4)
        assert len(above_threshold) == 2
        assert all(e.importance_score >= 0.4 for e in above_threshold)
        
        # Test factor-based filtering
        for entity in sample_entities:
            entity.importance_factors = {"frequency": entity.importance_score}
        
        top_by_freq = scorer.get_entities_by_factor(sample_entities, "frequency", top_n=2)
        assert len(top_by_freq) == 2
        assert top_by_freq[0].importance_factors["frequency"] == 0.8
    
    def test_edge_cases_and_error_handling(self, scorer):
        """Test edge cases and error handling."""
        # Test with extreme values
        huge_mentions = [{"segment_index": i, "timestamp": i} for i in range(1000)]
        freq_score = scorer.calculate_frequency_factor(huge_mentions, 60.0)
        assert freq_score == 1.0  # Should be capped
        
        # Test with invalid graph
        invalid_graph = "not a graph"
        with pytest.raises(AttributeError):
            scorer.calculate_structural_centrality("entity_1", invalid_graph)
        
        # Test with malformed embeddings
        malformed_embedding = [1, 2, 3]  # Wrong size
        result = scorer.calculate_semantic_centrality(malformed_embedding, [[4, 5, 6]])
        assert 0.0 <= result <= 1.0  # Should still return valid score
        
        # Test composite with invalid weights
        factors = {"frequency": 0.5}
        invalid_weights = {"frequency": -1.0}  # Negative weight
        result = scorer.calculate_composite_importance(factors, invalid_weights)
        assert 0.0 <= result <= 1.0  # Should normalize and return valid score


class TestIntegrationWithExtraction:
    """Test integration of ImportanceScorer with extraction pipeline."""
    
    def test_importance_scoring_in_extraction(self):
        """Test that importance scoring is properly integrated in extraction."""
        from src.extraction.extraction import KnowledgeExtractor
        from src.providers.llm.mock import MockLLMProvider
        
        # Create mock LLM provider
        llm = MockLLMProvider()
        extractor = KnowledgeExtractor(llm)
        
        # Create test segments
        segments = [
            {
                "text": "Machine learning and artificial intelligence are transforming industries.",
                "start_time": 0.0,
                "end_time": 60.0,
                "speaker": "Host"
            },
            {
                "text": "Python is the most popular language for machine learning.",
                "start_time": 60.0,
                "end_time": 120.0,
                "speaker": "Guest"
            },
            {
                "text": "Data science combines statistics, machine learning, and domain knowledge.",
                "start_time": 120.0,
                "end_time": 180.0,
                "speaker": "Host"
            }
        ]
        
        # Extract with importance scoring
        result = extractor.extract_from_segments(
            segments,
            podcast_name="Tech Talk",
            episode_title="ML Basics"
        )
        
        # Verify results
        assert "entities" in result
        assert "metadata" in result
        assert result["metadata"]["importance_scoring_applied"] is True
        
        # Check that entities have importance scores
        for entity in result["entities"]:
            assert hasattr(entity, "importance_score")
            assert hasattr(entity, "importance_factors")
            assert hasattr(entity, "discourse_roles")
            assert 0.0 <= entity.importance_score <= 1.0
            
            # Check factor structure
            if entity.importance_factors:
                assert "frequency" in entity.importance_factors
                assert "semantic_centrality" in entity.importance_factors
                assert "cross_reference" in entity.importance_factors
        
        # Verify entities are sorted by importance
        if len(result["entities"]) > 1:
            importance_scores = [e.importance_score for e in result["entities"]]
            assert importance_scores == sorted(importance_scores, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])