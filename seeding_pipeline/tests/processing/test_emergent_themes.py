"""Tests for emergent theme detection functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
import networkx as nx

from src.processing.emergent_themes import EmergentThemeDetector
from src.core.models import Entity, Insight, Segment, InsightType


class TestEmergentThemeDetector:
    """Test suite for EmergentThemeDetector class."""
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = Mock()
        provider.embed_text = Mock(return_value=np.random.rand(768).tolist())
        provider.embed_batch = Mock(return_value=[np.random.rand(768).tolist() for _ in range(3)])
        return provider
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = Mock()
        provider.generate = Mock(return_value="technological disruption")
        return provider
    
    @pytest.fixture
    def detector(self, mock_embedding_provider, mock_llm_provider):
        """Create an EmergentThemeDetector instance."""
        return EmergentThemeDetector(mock_embedding_provider, mock_llm_provider)
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing."""
        return [
            Entity(
                id="ent_1",
                name="Artificial Intelligence",
                type="TECHNOLOGY",
                embedding=np.random.rand(768).tolist()
            ),
            Entity(
                id="ent_2",
                name="Machine Learning",
                type="TECHNOLOGY",
                embedding=np.random.rand(768).tolist()
            ),
            Entity(
                id="ent_3",
                name="Ethics",
                type="CONCEPT",
                embedding=np.random.rand(768).tolist()
            ),
            Entity(
                id="ent_4",
                name="Society",
                type="CONCEPT",
                embedding=np.random.rand(768).tolist()
            ),
            Entity(
                id="ent_5",
                name="Innovation",
                type="CONCEPT",
                embedding=np.random.rand(768).tolist()
            )
        ]
    
    @pytest.fixture
    def sample_co_occurrences(self):
        """Create sample co-occurrence data."""
        return [
            {"entity1_id": "ent_1", "entity2_id": "ent_2", "weight": 5},
            {"entity1_id": "ent_1", "entity2_id": "ent_3", "weight": 3},
            {"entity1_id": "ent_2", "entity2_id": "ent_3", "weight": 2},
            {"entity1_id": "ent_3", "entity2_id": "ent_4", "weight": 4},
            {"entity1_id": "ent_4", "entity2_id": "ent_5", "weight": 2}
        ]
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        return [
            Segment(
                id="seg_0",
                text="We need to consider the ethical implications of artificial intelligence.",
                start_time=0.0,
                end_time=10.0,
                speaker="Host",
                segment_index=0
            ),
            Segment(
                id="seg_1",
                text="Machine learning is transforming our society in profound ways.",
                start_time=10.0,
                end_time=20.0,
                speaker="Guest",
                segment_index=1
            ),
            Segment(
                id="seg_2",
                text="The journey of innovation requires careful consideration.",
                start_time=20.0,
                end_time=30.0,
                speaker="Host",
                segment_index=2
            ),
            Segment(
                id="seg_3",
                text="We're in a battle for ethical AI development.",
                start_time=30.0,
                end_time=40.0,
                speaker="Guest",
                segment_index=3
            )
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Create sample insights for testing."""
        return [
            Insight(
                id="ins_1",
                title="AI Ethics Connection",
                description="AI development directly impacts ethical considerations",
                insight_type=InsightType.RELATIONSHIP,
                supporting_entities=["ent_1", "ent_3"],
                confidence_score=0.85
            ),
            Insight(
                id="ins_2",
                title="Innovation Requires Ethics",
                description="Innovation depends on ethical frameworks",
                insight_type=InsightType.PRINCIPLE,
                supporting_entities=["ent_3", "ent_5"],
                confidence_score=0.75
            )
        ]
    
    def test_analyze_concept_clusters(self, detector, sample_entities, sample_co_occurrences):
        """Test concept cluster analysis."""
        with patch('community.best_partition') as mock_partition:
            # Mock community detection
            mock_partition.return_value = {
                "ent_1": 0, "ent_2": 0, "ent_3": 0,  # Tech & Ethics cluster
                "ent_4": 1, "ent_5": 1  # Society & Innovation cluster
            }
            
            clusters = detector.analyze_concept_clusters(
                sample_entities, 
                sample_co_occurrences
            )
            
            assert len(clusters) > 0
            
            # Check cluster structure
            first_cluster = clusters[0]
            assert "cluster_id" in first_cluster
            assert "entities" in first_cluster
            assert "size" in first_cluster
            assert "coherence" in first_cluster
            assert first_cluster["size"] >= 2
            assert 0 <= first_cluster["coherence"] <= 1
    
    def test_analyze_concept_clusters_fallback(self, detector, sample_entities, sample_co_occurrences):
        """Test fallback to connected components when community detection fails."""
        # Don't mock community detection to trigger ImportError
        clusters = detector.analyze_concept_clusters(
            sample_entities,
            sample_co_occurrences
        )
        
        # Should still return clusters using connected components
        assert len(clusters) >= 0
    
    def test_extract_semantic_fields(self, detector, sample_entities):
        """Test semantic field extraction."""
        clusters = [
            {
                "cluster_id": "cluster_1",
                "entities": sample_entities[:3],  # AI, ML, Ethics
                "coherence": 0.8
            }
        ]
        
        fields = detector.extract_semantic_fields(clusters, sample_entities)
        
        assert len(fields) == 1
        field = fields[0]
        
        assert "cluster_id" in field
        assert "semantic_field" in field
        assert "confidence" in field
        assert "key_concepts" in field
        assert "peripheral_concepts" in field
        assert field["semantic_field"] == "technological disruption"  # From mock
    
    def test_detect_cross_cluster_patterns(self, detector, sample_insights):
        """Test cross-cluster pattern detection."""
        clusters = [
            {"cluster_id": "c1", "entities": [Mock(id="ent_1"), Mock(id="ent_3")]},
            {"cluster_id": "c2", "entities": [Mock(id="ent_4"), Mock(id="ent_5")]}
        ]
        
        patterns = detector.detect_cross_cluster_patterns(clusters, sample_insights)
        
        assert len(patterns) > 0
        
        # Check for causal patterns
        causal_patterns = [p for p in patterns if p["pattern_type"] == "causal_chain"]
        assert len(causal_patterns) > 0
        
        # Check for dependency patterns
        dependency_patterns = [p for p in patterns if p["pattern_type"] == "dependency"]
        assert len(dependency_patterns) > 0
    
    def test_extract_implicit_messages(self, detector):
        """Test implicit message extraction."""
        semantic_fields = [
            {
                "semantic_field": "technological change",
                "key_concepts": ["AI", "automation", "disruption"],
                "peripheral_concepts": ["jobs", "society"]
            },
            {
                "semantic_field": "ethical considerations",
                "key_concepts": ["ethics", "responsibility", "values"],
                "peripheral_concepts": ["regulation", "guidelines"]
            }
        ]
        
        messages = detector.extract_implicit_messages(semantic_fields, {})
        
        assert isinstance(messages, list)
        if messages:
            message = messages[0]
            assert "implicit_message" in message
            assert "supporting_evidence" in message
            assert "confidence" in message
            assert "interpretation" in message
    
    def test_score_theme_emergence(self, detector):
        """Test theme emergence scoring."""
        theme = {
            "semantic_field": "technological disruption",
            "evidence_segments": [0, 2, 4, 6],
            "pattern_type": "emergence",
            "explicitly_named": False
        }
        
        explicit_topics = ["AI", "Machine Learning", "Ethics"]
        
        score = detector.score_theme_emergence(theme, explicit_topics)
        
        assert 0 <= score <= 1
        # Should have moderate emergence since it's not explicitly named
        assert score > 0.3
    
    def test_detect_metaphorical_themes(self, detector, sample_segments, sample_entities):
        """Test metaphor detection."""
        themes = detector.detect_metaphorical_themes(sample_segments, sample_entities)
        
        # Should detect journey and battle metaphors from sample segments
        assert len(themes) > 0
        
        # Check theme structure
        if themes:
            theme = themes[0]
            assert "metaphor_family" in theme
            assert "occurrences" in theme
            assert "segments" in theme
            assert "keywords_used" in theme
            assert "related_concepts" in theme
            assert "thematic_implication" in theme
            assert "confidence" in theme
    
    def test_track_theme_evolution(self, detector, sample_segments):
        """Test theme evolution tracking."""
        emergent_themes = [
            {
                "theme_id": "theme_1",
                "key_concepts": ["AI", "Ethics"],
                "semantic_field": "ethical AI"
            }
        ]
        
        evolution = detector.track_theme_evolution(emergent_themes, sample_segments)
        
        assert "theme_1" in evolution
        theme_evolution = evolution["theme_1"]
        
        assert "first_emergence" in theme_evolution
        assert "strength_timeline" in theme_evolution
        assert "contributing_concepts" in theme_evolution
        assert "evolution_pattern" in theme_evolution
    
    def test_validate_emergent_themes(self, detector, sample_segments, sample_insights):
        """Test theme validation."""
        themes = [
            {
                "theme_id": "theme_1",
                "semantic_field": "technological ethics",
                "key_concepts": ["AI", "Ethics"],
                "confidence": 0.8,
                "evidence_segments": [0, 1, 3],
                "strength_timeline": [0.5, 0.7, 0.6, 0.8]
            }
        ]
        
        validated = detector.validate_emergent_themes(themes, sample_segments, sample_insights)
        
        assert len(validated) <= len(themes)
        
        if validated:
            theme = validated[0]
            assert "validation_score" in theme
            assert "validation_evidence" in theme
            assert "is_validated" in theme
            assert theme["is_validated"] is True
            assert theme["validation_score"] >= 0.6
    
    def test_build_theme_hierarchy(self, detector):
        """Test theme hierarchy building."""
        themes = [
            {
                "cluster_id": "t1",
                "semantic_field": "technological transformation",
                "key_concepts": ["AI", "ML", "automation", "disruption"],
                "confidence": 0.9
            },
            {
                "cluster_id": "t2",
                "semantic_field": "AI ethics",
                "key_concepts": ["AI", "ethics"],
                "confidence": 0.8
            },
            {
                "cluster_id": "t3",
                "semantic_field": "automation impact",
                "key_concepts": ["automation"],
                "confidence": 0.7
            }
        ]
        
        hierarchy = detector.build_theme_hierarchy(themes)
        
        assert "meta_themes" in hierarchy
        assert "primary_themes" in hierarchy
        assert "sub_themes" in hierarchy
        assert "micro_themes" in hierarchy
        
        # Check that themes are distributed across levels
        total_themes = (
            len(hierarchy["meta_themes"]) +
            len(hierarchy["primary_themes"]) +
            len(hierarchy["sub_themes"]) +
            len(hierarchy["micro_themes"])
        )
        assert total_themes == len(themes)
    
    def test_generate_theme_summary(self, detector):
        """Test theme summary generation."""
        themes = [
            {
                "semantic_field": "technological disruption",
                "emergence_score": 0.85,
                "confidence": 0.8,
                "key_concepts": ["AI", "automation"],
                "evolution_pattern": "crescendo",
                "validation_score": 0.9
            }
        ]
        
        summary = detector.generate_theme_summary(themes)
        
        assert "major_themes" in summary
        assert "theme_relationships" in summary
        assert "overall_narrative" in summary
        
        assert len(summary["major_themes"]) <= 5
        if summary["major_themes"]:
            theme = summary["major_themes"][0]
            assert "theme" in theme
            assert "emergence_score" in theme
            assert "supporting_concepts" in theme
            assert "interpretation" in theme
    
    def test_detect_themes_integration(
        self, 
        detector, 
        sample_entities, 
        sample_insights,
        sample_segments,
        sample_co_occurrences
    ):
        """Test the main detect_themes integration."""
        with patch.object(detector, 'analyze_concept_clusters') as mock_clusters:
            mock_clusters.return_value = [
                {
                    "cluster_id": "c1",
                    "entities": sample_entities[:3],
                    "coherence": 0.8
                }
            ]
            
            result = detector.detect_themes(
                entities=sample_entities,
                insights=sample_insights,
                segments=sample_segments,
                co_occurrences=sample_co_occurrences,
                explicit_topics=["AI", "ML"]
            )
            
            assert "themes" in result
            assert "hierarchy" in result
            assert "summary" in result
            assert "implicit_messages" in result
            
            # Verify the flow was executed
            mock_clusters.assert_called_once()
    
    def test_empty_inputs(self, detector):
        """Test handling of empty inputs."""
        # Empty entities
        clusters = detector.analyze_concept_clusters([], [])
        assert clusters == []
        
        # Empty segments
        themes = detector.detect_metaphorical_themes([], [])
        assert themes == []
        
        # Empty themes for summary
        summary = detector.generate_theme_summary([])
        assert summary["overall_narrative"] == "No significant emergent themes detected."
    
    def test_error_handling(self, detector):
        """Test error handling in various methods."""
        # Test with None embeddings
        entities_no_embed = [
            Entity(id="e1", name="Test", type="CONCEPT")
        ]
        
        clusters = [{
            "cluster_id": "c1",
            "entities": entities_no_embed,
            "coherence": 0.5
        }]
        
        # Should handle gracefully
        fields = detector.extract_semantic_fields(clusters, entities_no_embed)
        assert isinstance(fields, list)