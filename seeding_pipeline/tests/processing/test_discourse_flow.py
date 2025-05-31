"""Tests for discourse flow tracking functionality."""

from datetime import datetime
from unittest.mock import Mock, MagicMock

import numpy as np
import pytest

from src.core.models import Entity, Segment, Insight, InsightType
from src.processing.discourse_flow import DiscourseFlowTracker
class TestDiscourseFlowTracker:
    """Test suite for DiscourseFlowTracker class."""
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = Mock()
        provider.embed_text = Mock(return_value=np.random.rand(768).tolist())
        provider.embed_batch = Mock(return_value=[np.random.rand(768).tolist() for _ in range(3)])
        return provider
    
    @pytest.fixture
    def tracker(self, mock_embedding_provider):
        """Create a DiscourseFlowTracker instance."""
        return DiscourseFlowTracker(mock_embedding_provider)
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        return [
            Segment(
                id="seg_0",
                text="Let's discuss artificial intelligence and its impact on society.",
                start_time=0.0,
                end_time=10.0,
                speaker="Host",
                segment_index=0
            ),
            Segment(
                id="seg_1", 
                text="AI has transformed healthcare with diagnostic tools.",
                start_time=10.0,
                end_time=20.0,
                speaker="Guest",
                segment_index=1
            ),
            Segment(
                id="seg_2",
                text="The ethical implications of AI are significant.",
                start_time=20.0,
                end_time=30.0,
                speaker="Host",
                segment_index=2
            ),
            Segment(
                id="seg_3",
                text="Machine learning algorithms need better transparency.",
                start_time=30.0,
                end_time=40.0,
                speaker="Guest",
                segment_index=3
            ),
            Segment(
                id="seg_4",
                text="In conclusion, AI ethics must guide development.",
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
                name="Artificial Intelligence",
                type="TECHNOLOGY",
                embedding=np.random.rand(768).tolist()
            ),
            Entity(
                id="ent_2",
                name="Healthcare",
                type="DOMAIN",
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
                name="Machine Learning",
                type="TECHNOLOGY",
                embedding=np.random.rand(768).tolist()
            )
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Create sample insights for testing."""
        return [
            Insight(
                id="ins_1",
                title="AI Healthcare Revolution",
                description="AI is transforming healthcare",
                insight_type=InsightType.TREND,
                supporting_entities=["ent_1", "ent_2"]
            ),
            Insight(
                id="ins_2",
                title="Ethical AI Development",
                description="Ethics must guide AI development",
                insight_type=InsightType.PRINCIPLE,
                supporting_entities=["ent_1", "ent_3"]
            )
        ]
    
    def test_build_concept_timeline(self, tracker, sample_segments, sample_entities):
        """Test building concept timelines from segments and entities."""
        # Mock entity detection in segments
        tracker._find_entity_mentions = Mock(side_effect=[
            [sample_entities[0], sample_entities[2]],  # seg 0: AI, Ethics
            [sample_entities[0], sample_entities[1]],  # seg 1: AI, Healthcare
            [sample_entities[0], sample_entities[2]],  # seg 2: AI, Ethics
            [sample_entities[3]],                       # seg 3: ML
            [sample_entities[0], sample_entities[2]]   # seg 4: AI, Ethics
        ])
        
        timelines = tracker.build_concept_timeline(sample_segments, sample_entities)
        
        # Verify timeline structure
        assert "ent_1" in timelines  # AI should have timeline
        assert "ent_2" in timelines  # Healthcare should have timeline
        assert "ent_3" in timelines  # Ethics should have timeline
        assert "ent_4" in timelines  # ML should have timeline
        
        # Check AI timeline (appears in segments 0, 1, 2, 4)
        ai_timeline = timelines["ent_1"]["timeline"]
        assert len(ai_timeline) == 4
        assert ai_timeline[0]["segment_index"] == 0
        assert ai_timeline[0]["mention_type"] == "introduction"
        assert ai_timeline[-1]["segment_index"] == 4
        assert ai_timeline[-1]["mention_type"] == "conclusion"
        
        # Check entity info
        assert timelines["ent_1"]["entity_name"] == "Artificial Intelligence"
        assert timelines["ent_1"]["entity_type"] == "TECHNOLOGY"
    
    def test_analyze_concept_lifecycle(self, tracker):
        """Test concept lifecycle analysis."""
        timeline_data = {
            "timeline": [
                {"segment_index": 0, "timestamp": 5.0, "context_density": 0.8},
                {"segment_index": 1, "timestamp": 15.0, "context_density": 0.9},
                {"segment_index": 2, "timestamp": 25.0, "context_density": 0.95},
                {"segment_index": 4, "timestamp": 45.0, "context_density": 0.6}
            ]
        }
        
        lifecycle = tracker.analyze_concept_lifecycle(timeline_data)
        
        assert lifecycle["lifecycle_pattern"] in [
            "introduce-develop-conclude",
            "introduce-develop",
            "recurring-theme"
        ]
        assert lifecycle["introduction_segment"] == 0
        assert lifecycle["peak_segment"] == 2  # Highest context density
        assert lifecycle["total_duration"] == 40.0  # 45 - 5
        assert 0 <= lifecycle["development_intensity"] <= 1.0
    
    def test_detect_discourse_patterns(self, tracker):
        """Test discourse pattern detection."""
        concept_timelines = {
            "ent_1": {  # Central concept appearing throughout
                "timeline": [
                    {"segment_index": i} for i in range(5)
                ]
            },
            "ent_2": {  # Spoke concept
                "timeline": [{"segment_index": 1}]
            },
            "ent_3": {  # Another spoke concept
                "timeline": [{"segment_index": 2}, {"segment_index": 4}]
            }
        }
        
        patterns = tracker.detect_discourse_patterns(concept_timelines)
        
        assert len(patterns) > 0
        
        # Should detect hub and spoke pattern
        hub_patterns = [p for p in patterns if p["pattern_type"] == "hub_and_spoke"]
        assert len(hub_patterns) > 0
        assert "ent_1" in hub_patterns[0]["hub_entities"]
    
    def test_calculate_concept_momentum(self, tracker):
        """Test concept momentum calculation."""
        timeline = [
            {"segment_index": 0, "context_density": 0.5},
            {"segment_index": 1, "context_density": 0.7},
            {"segment_index": 2, "context_density": 0.9},
            {"segment_index": 3, "context_density": 0.8},
            {"segment_index": 4, "context_density": 0.4}
        ]
        
        momentum = tracker.calculate_concept_momentum(timeline, window_size=2)
        
        assert len(momentum) == len(timeline)
        # Momentum should increase then decrease
        assert momentum[2] > momentum[0]  # Peak momentum
        assert momentum[4] < momentum[2]  # Declining momentum
    
    def test_detect_narrative_arcs(self, tracker, sample_segments):
        """Test narrative arc detection."""
        concept_timelines = {
            "problem": {
                "timeline": [{"segment_index": 0}, {"segment_index": 2}]
            },
            "solution": {
                "timeline": [{"segment_index": 3}, {"segment_index": 4}]
            }
        }
        
        # Mock arc detection methods
        tracker._detect_problem_solution_arc = Mock(
            return_value=(0.8, {"turning_points": [2], "resolution_status": "resolved"})
        )
        tracker._detect_journey_arc = Mock(return_value=(0.3, {}))
        tracker._detect_debate_arc = Mock(return_value=(0.2, {}))
        tracker._detect_discovery_arc = Mock(return_value=(0.4, {}))
        
        arcs = tracker.detect_narrative_arcs(sample_segments, concept_timelines)
        
        assert arcs["primary_arc"] == "problem_solution"
        assert arcs["arc_confidence"] == 0.8
        assert len(arcs["turning_points"]) == 1
        assert arcs["resolution_status"] == "resolved"
    
    def test_track_concept_interactions(self, tracker, sample_segments):
        """Test concept interaction tracking."""
        concept_timelines = {
            "ent_1": {
                "timeline": [
                    {"segment_index": 0},
                    {"segment_index": 1},
                    {"segment_index": 2}
                ]
            },
            "ent_2": {
                "timeline": [
                    {"segment_index": 0},
                    {"segment_index": 1}
                ]
            },
            "ent_3": {
                "timeline": [
                    {"segment_index": 2},
                    {"segment_index": 3}
                ]
            }
        }
        
        interactions = tracker.track_concept_interactions(concept_timelines, sample_segments)
        
        # Should find co-introduction of ent_1 and ent_2
        co_intros = [i for i in interactions if i["interaction_type"] == "co-introduction"]
        assert len(co_intros) > 0
        
        # Should find causal links
        causal_links = [i for i in interactions if i["interaction_type"] == "causal_link"]
        assert len(causal_links) >= 0
    
    def test_analyze_transitions(self, tracker, sample_segments):
        """Test transition analysis between segments."""
        concept_timelines = {
            "ent_1": {"timeline": [{"segment_index": 0}, {"segment_index": 1}]},
            "ent_2": {"timeline": [{"segment_index": 1}, {"segment_index": 2}]},
            "ent_3": {"timeline": [{"segment_index": 3}]}
        }
        
        transitions = tracker.analyze_transitions(sample_segments, concept_timelines)
        
        assert len(transitions) == len(sample_segments) - 1
        
        # Check first transition (0->1)
        assert transitions[0]["from_segment"] == 0
        assert transitions[0]["to_segment"] == 1
        assert transitions[0]["transition_type"] in [
            "continuation", "expansion", "focus", "pivot", "bridge"
        ]
        assert 0 <= transitions[0]["smoothness_score"] <= 1.0
    
    def test_generate_flow_visualization_data(self, tracker):
        """Test flow visualization data generation."""
        flow_analysis = {
            "concept_timelines": {
                "ent_1": {"timeline": [{"segment_index": i} for i in range(5)]}
            },
            "transitions": [
                {
                    "from_segment": 1,
                    "to_segment": 2,
                    "transition_type": "pivot",
                    "explicit_marker": "however"
                }
            ],
            "concept_momentum": {
                "ent_1": [0.5, 0.7, 0.9, 0.6, 0.3]
            }
        }
        
        viz_data = tracker.generate_flow_visualization_data(flow_analysis)
        
        assert "concept_streams" in viz_data
        assert len(viz_data["concept_streams"]) > 0
        assert viz_data["concept_streams"][0]["entity_id"] == "ent_1"
        
        assert "key_transitions" in viz_data
        assert len(viz_data["key_transitions"]) > 0
        
        assert "momentum_data" in viz_data
        assert len(viz_data["momentum_data"]) > 0
    
    def test_enrich_entities_with_flow_data(self, tracker, sample_entities):
        """Test entity enrichment with flow data."""
        flow_analysis = {
            "concept_lifecycles": {
                "ent_1": {
                    "lifecycle_pattern": "introduce-develop-conclude",
                    "development_intensity": 0.8
                },
                "ent_3": {
                    "lifecycle_pattern": "recurring-theme",
                    "development_intensity": 0.6
                }
            },
            "concept_momentum": {
                "ent_1": [0.5, 0.7, 0.9, 0.6, 0.3],
                "ent_3": [0.4, 0.5, 0.7, 0.8, 0.6]
            },
            "discourse_patterns": [
                {
                    "pattern_type": "hub_and_spoke",
                    "hub_entities": ["ent_1"],
                    "confidence": 0.85
                }
            ]
        }
        
        enriched = tracker.enrich_entities_with_flow_data(sample_entities, flow_analysis)
        
        # Check AI entity enrichment
        ai_entity = next(e for e in enriched if e.id == "ent_1")
        assert hasattr(ai_entity, "discourse_lifecycle")
        assert ai_entity.discourse_lifecycle == "introduce-develop-conclude"
        assert hasattr(ai_entity, "discourse_intensity")
        assert ai_entity.discourse_intensity == 0.8
        assert hasattr(ai_entity, "discourse_momentum")
        assert ai_entity.discourse_momentum == 0.6  # Average of momentum values
        assert hasattr(ai_entity, "discourse_role")
        assert ai_entity.discourse_role == "central_concept"
    
    def test_generate_flow_summary(self, tracker):
        """Test flow summary generation."""
        flow_analysis = {
            "discourse_patterns": [
                {
                    "pattern_type": "hub_and_spoke",
                    "confidence": 0.85
                }
            ],
            "narrative_arc": {
                "primary_arc": "problem_solution",
                "arc_confidence": 0.75,
                "resolution_status": "resolved"
            },
            "transitions": [
                {"transition_type": "pivot"},
                {"transition_type": "expansion"},
                {"transition_type": "pivot"}
            ],
            "concept_lifecycles": {
                "ent_1": {"lifecycle_pattern": "introduce-develop-conclude"},
                "ent_2": {"lifecycle_pattern": "introduce-develop-conclude"},
                "ent_3": {"lifecycle_pattern": "recurring-theme"}
            }
        }
        
        summary = tracker.generate_flow_summary(flow_analysis)
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "hub and spoke" in summary
        assert "problem solution" in summary
        assert "2 major topic shifts" in summary
        assert "2 concepts are fully developed" in summary
    
    def test_analyze_episode_flow(self, tracker, sample_segments, sample_entities, sample_insights):
        """Test complete episode flow analysis."""
        # Mock internal methods
        tracker.build_concept_timeline = Mock(return_value={
            "ent_1": {"timeline": [{"segment_index": i} for i in range(5)]}
        })
        tracker.analyze_concept_lifecycle = Mock(return_value={
            "lifecycle_pattern": "introduce-develop-conclude"
        })
        tracker.calculate_concept_momentum = Mock(return_value=[0.5, 0.7, 0.9])
        tracker.detect_discourse_patterns = Mock(return_value=[
            {"pattern_type": "linear_progression", "confidence": 0.8}
        ])
        tracker.detect_narrative_arcs = Mock(return_value={
            "primary_arc": "journey"
        })
        tracker.track_concept_interactions = Mock(return_value=[])
        tracker.analyze_transitions = Mock(return_value=[])
        tracker.generate_flow_visualization_data = Mock(return_value={})
        tracker.enrich_entities_with_flow_data = Mock(return_value=sample_entities)
        tracker.generate_flow_summary = Mock(return_value="Test summary")
        
        result = tracker.analyze_episode_flow(sample_segments, sample_entities, sample_insights)
        
        assert "concept_timelines" in result
        assert "concept_lifecycles" in result
        assert "concept_momentum" in result
        assert "discourse_patterns" in result
        assert "narrative_arc" in result
        assert "concept_interactions" in result
        assert "transitions" in result
        assert "visualization_data" in result
        assert "enriched_entities" in result
        assert "summary" in result
        
        # Verify all methods were called
        tracker.build_concept_timeline.assert_called_once()
        tracker.detect_discourse_patterns.assert_called_once()
        tracker.generate_flow_summary.assert_called_once()
    
    def test_error_handling(self, tracker):
        """Test error handling in various methods."""
        # Test with empty inputs
        empty_result = tracker.build_concept_timeline([], [])
        assert empty_result == {}
        
        # Test with invalid timeline data
        invalid_timeline = {"timeline": []}
        lifecycle = tracker.analyze_concept_lifecycle(invalid_timeline)
        assert lifecycle["lifecycle_pattern"] == "unknown"
        
        # Test with no patterns
        patterns = tracker.detect_discourse_patterns({})
        assert patterns == []