"""Tests for episode flow analysis functionality."""

from unittest.mock import Mock, MagicMock

import numpy as np
import pytest

from src.core.models import Entity, Segment
from src.processing.episode_flow import EpisodeFlowAnalyzer
class TestEpisodeFlowAnalyzer:
    """Test suite for EpisodeFlowAnalyzer class."""
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = Mock()
        provider.embed_text = Mock(return_value=np.random.rand(768).tolist())
        provider.embed_batch = Mock(return_value=[np.random.rand(768).tolist() for _ in range(3)])
        return provider
    
    @pytest.fixture
    def analyzer(self, mock_embedding_provider):
        """Create an EpisodeFlowAnalyzer instance."""
        return EpisodeFlowAnalyzer(mock_embedding_provider)
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        return [
            Segment(
                id="seg_0",
                text="Today we'll discuss artificial intelligence and its impact.",
                start_time=0.0,
                end_time=10.0,
                speaker="Host",
                segment_index=0
            ),
            Segment(
                id="seg_1",
                text="AI has many applications in healthcare. For example, diagnosis.",
                start_time=10.0,
                end_time=20.0,
                speaker="Guest",
                segment_index=1
            ),
            Segment(
                id="seg_2",
                text="However, there are ethical concerns about AI decisions.",
                start_time=20.0,
                end_time=30.0,
                speaker="Host",
                segment_index=2
            ),
            Segment(
                id="seg_3",
                text="Let's shift to talking about machine learning specifically.",
                start_time=30.0,
                end_time=40.0,
                speaker="Guest",
                segment_index=3
            ),
            Segment(
                id="seg_4",
                text="In conclusion, AI and ethics must be considered together.",
                start_time=40.0,
                end_time=50.0,
                speaker="Host",
                segment_index=4
            )
        ]
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing."""
        return [
            Entity(
                id="ent_1",
                name="artificial intelligence",
                type="TECHNOLOGY"
            ),
            Entity(
                id="ent_2",
                name="healthcare",
                type="DOMAIN"
            ),
            Entity(
                id="ent_3",
                name="ethics",
                type="CONCEPT"
            ),
            Entity(
                id="ent_4",
                name="machine learning",
                type="TECHNOLOGY"
            )
        ]
    
    def test_classify_segment_transitions(self, analyzer, sample_segments):
        """Test segment transition classification."""
        transitions = analyzer.classify_segment_transitions(sample_segments)
        
        assert len(transitions) == len(sample_segments) - 1
        
        # Check first transition
        assert transitions[0]["from_segment"] == 0
        assert transitions[0]["to_segment"] == 1
        assert "transition_type" in transitions[0]
        assert "semantic_similarity" in transitions[0]
        assert "smoothness_score" in transitions[0]
        
        # Check for explicit markers
        # Segment 2 starts with "However" - should be detected
        however_transition = transitions[1]  # From segment 1 to 2
        assert however_transition.get("explicit_marker") == "however"
        
        # Segment 3 has "Let's shift to" - should be detected as jump
        shift_transition = transitions[2]  # From segment 2 to 3
        assert shift_transition.get("explicit_marker") is not None
    
    def test_track_concept_introductions(self, analyzer, sample_segments, sample_entities):
        """Test concept introduction tracking."""
        introductions = analyzer.track_concept_introductions(sample_segments, sample_entities)
        
        # AI should be introduced in segment 0 as planned
        if "ent_1" in introductions:
            ai_intro = introductions["ent_1"]
            assert ai_intro["introduction_segment"] == 0
            assert ai_intro["introduction_type"] == "planned"
            assert ai_intro["introducer"] == "Host"
        
        # Healthcare appears in segment 1
        if "ent_2" in introductions:
            healthcare_intro = introductions["ent_2"]
            assert healthcare_intro["introduction_segment"] == 1
            assert healthcare_intro["introducer"] == "Guest"
    
    def test_map_concept_development(self, analyzer, sample_segments, sample_entities):
        """Test concept development mapping."""
        # Test AI development (appears in segments 0, 1, 2, 4)
        ai_entity = sample_entities[0]
        development = analyzer.map_concept_development(ai_entity, sample_segments)
        
        assert "phases" in development
        assert "timeline" in development
        assert "total_mentions" in development
        assert "development_pattern" in development
        
        # Should have multiple phases
        if development["phases"]:
            assert development["phases"][0]["phase"] == "introduction"
    
    def test_analyze_conversation_momentum(self, analyzer, sample_segments):
        """Test conversation momentum analysis."""
        momentum_data = analyzer.analyze_conversation_momentum(sample_segments, window_size=3)
        
        assert len(momentum_data) == len(sample_segments)
        
        for momentum_point in momentum_data:
            assert "segment_index" in momentum_point
            assert "momentum" in momentum_point
            assert "factors" in momentum_point
            assert "timestamp" in momentum_point
            assert "annotation" in momentum_point
            
            # Check momentum is in valid range
            assert 0 <= momentum_point["momentum"] <= 1
            
            # Check all factors are present
            factors = momentum_point["factors"]
            assert "new_concepts" in factors
            assert "speaker_turns" in factors
            assert "questions" in factors
            assert "insights" in factors
            assert "intensity" in factors
    
    def test_track_topic_depth(self, analyzer, sample_segments, sample_entities):
        """Test topic depth tracking."""
        depths = analyzer.track_topic_depth(sample_segments, sample_entities)
        
        assert isinstance(depths, dict)
        
        # AI should have some depth since it's mentioned multiple times
        if "artificial intelligence" in depths:
            ai_depth = depths["artificial intelligence"]
            assert 0 <= ai_depth <= 1
            assert ai_depth > 0  # Should have some depth
        
        # Check all tracked topics have valid depth scores
        for topic, depth in depths.items():
            assert 0 <= depth <= 1
    
    def test_detect_circular_references(self, analyzer):
        """Test circular reference detection."""
        concept_timeline = {
            "ent_1": [
                {"segment_index": 0, "timestamp": 0},
                {"segment_index": 1, "timestamp": 10},
                {"segment_index": 8, "timestamp": 80},  # Gap then return
                {"segment_index": 9, "timestamp": 90}
            ],
            "ent_2": [
                {"segment_index": 2, "timestamp": 20}
            ]
        }
        
        circular_refs = analyzer.detect_circular_references(concept_timeline)
        
        # Should detect circular reference for ent_1
        assert len(circular_refs) > 0
        
        ref = circular_refs[0]
        assert ref["concept"] == "ent_1"
        assert ref["first_mention"]["segment"] == 0
        assert ref["return_mention"]["segment"] == 8
        assert "evolution" in ref
        assert "closure_achieved" in ref
    
    def test_analyze_concept_resolution(self, analyzer, sample_segments):
        """Test concept resolution analysis."""
        concepts = {
            "ent_1": {"mentions": [0, 1, 4]},  # Appears in conclusion
            "ent_2": {"mentions": [1]},  # Only middle
            "ent_3": {"mentions": [2, 4]}  # Also in conclusion
        }
        
        final_segments = sample_segments[-2:]  # Last 2 segments
        
        resolutions = analyzer.analyze_concept_resolution(concepts, final_segments)
        
        assert isinstance(resolutions, dict)
        
        for concept_id, resolution in resolutions.items():
            assert "resolution_type" in resolution
            assert "quality_score" in resolution
            assert "final_state" in resolution
            
            # Check valid resolution types
            assert resolution["resolution_type"] in [
                "answered", "partial", "deferred", "abandoned", "transformed"
            ]
            assert 0 <= resolution["quality_score"] <= 1
    
    def test_generate_episode_flow_summary(self, analyzer):
        """Test episode flow summary generation."""
        flow_analysis = {
            "concept_introductions": {
                "ent_1": {"introduction_segment": 0},
                "ent_2": {"introduction_segment": 1}
            },
            "transitions": [
                {"transition_type": "continuation", "smoothness_score": 0.8},
                {"transition_type": "pivot", "smoothness_score": 0.6},
                {"transition_type": "jump", "smoothness_score": 0.3}
            ],
            "resolutions": {
                "ent_1": {"resolution_type": "answered"},
                "ent_2": {"resolution_type": "abandoned"}
            },
            "circular_references": [
                {"concept": "ent_1", "closure_achieved": True}
            ]
        }
        
        summary = analyzer.generate_episode_flow_summary(flow_analysis)
        
        assert "opening_concepts" in summary
        assert "core_developments" in summary
        assert "key_transitions" in summary
        assert "unresolved_threads" in summary
        assert "circular_themes" in summary
        assert "flow_pattern" in summary
        assert "narrative_coherence" in summary
        
        # Check narrative coherence is valid
        assert 0 <= summary["narrative_coherence"] <= 1
    
    def test_analyze_speaker_contribution_flow(self, analyzer, sample_segments):
        """Test speaker contribution analysis."""
        contributions = analyzer.analyze_speaker_contribution_flow(sample_segments)
        
        assert "Host" in contributions
        assert "Guest" in contributions
        
        for speaker, data in contributions.items():
            assert "segments" in data
            assert "concept_introductions" in data
            assert "questions" in data
            assert "statements" in data
            assert "transitions_initiated" in data
            assert "flow_role" in data
            assert "question_ratio" in data
            assert "introduction_rate" in data
            
            # Check ratios are valid
            assert 0 <= data["question_ratio"] <= 1
            assert 0 <= data["introduction_rate"] <= 1
    
    def test_calculate_segment_flow_importance(self, analyzer, sample_segments):
        """Test segment flow importance calculation."""
        flow_analysis = {
            "concept_introductions": {
                "ent_1": {"introduction_segment": 0}
            },
            "transitions": [
                {"from_segment": 2, "to_segment": 3, "transition_type": "jump"}
            ],
            "resolutions": {
                "ent_1": {"resolution_segment": 4}
            },
            "momentum": [
                {"momentum": 0.5},
                {"momentum": 0.7},
                {"momentum": 0.4},
                {"momentum": 0.8},
                {"momentum": 0.6}
            ]
        }
        
        # Test importance of first segment (introduces major concept)
        importance_0 = analyzer.calculate_segment_flow_importance(
            sample_segments[0], 
            flow_analysis
        )
        assert importance_0 > 0.5  # Should be high
        
        # Test importance of last segment (has resolution)
        importance_4 = analyzer.calculate_segment_flow_importance(
            sample_segments[4],
            flow_analysis
        )
        assert importance_4 > 0.5  # Should be high
        
        # Test all segments have valid importance
        for segment in sample_segments:
            importance = analyzer.calculate_segment_flow_importance(
                segment,
                flow_analysis
            )
            assert 0 <= importance <= 1
    
    def test_empty_inputs(self, analyzer):
        """Test handling of empty inputs."""
        # Empty segments
        empty_transitions = analyzer.classify_segment_transitions([])
        assert empty_transitions == []
        
        # Empty entities
        empty_introductions = analyzer.track_concept_introductions([], [])
        assert empty_introductions == {}
        
        # Empty momentum
        empty_momentum = analyzer.analyze_conversation_momentum([])
        assert empty_momentum == []
    
    def test_single_segment(self, analyzer, sample_segments):
        """Test handling of single segment."""
        single_segment = [sample_segments[0]]
        
        # Should handle gracefully
        transitions = analyzer.classify_segment_transitions(single_segment)
        assert transitions == []
        
        momentum = analyzer.analyze_conversation_momentum(single_segment)
        assert len(momentum) == 1
    
    def test_no_embedding_provider(self):
        """Test analyzer without embedding provider."""
        analyzer = EpisodeFlowAnalyzer(embedding_provider=None)
        
        segments = [
            Segment(id="s1", text="Text 1", start_time=0, end_time=10, speaker="A", segment_index=0),
            Segment(id="s2", text="Text 2", start_time=10, end_time=20, speaker="B", segment_index=1)
        ]
        
        # Should still work with default similarity
        transitions = analyzer.classify_segment_transitions(segments)
        assert len(transitions) == 1
        assert transitions[0]["semantic_similarity"] == 0.5  # Default value