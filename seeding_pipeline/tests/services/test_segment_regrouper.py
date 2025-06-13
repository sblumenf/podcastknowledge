"""Tests for segment regrouper service."""

import pytest
from src.services.segment_regrouper import SegmentRegrouper, MeaningfulUnit
from src.core.interfaces import TranscriptSegment
from src.core.conversation_models.conversation import (
    ConversationStructure,
    ConversationUnit,
    ConversationTheme,
    ConversationBoundary,
    ConversationFlow,
    StructuralInsights
)


class TestSegmentRegrouper:
    """Test segment regrouper functionality."""
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample transcript segments."""
        return [
            TranscriptSegment(
                id=f"seg_{i}",
                text=f"Segment {i} text",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                speaker="Host" if i % 2 == 0 else "Guest"
            )
            for i in range(10)
        ]
    
    @pytest.fixture
    def sample_structure(self):
        """Create sample conversation structure."""
        return ConversationStructure(
            units=[
                ConversationUnit(
                    start_index=0,
                    end_index=2,
                    unit_type="introduction",
                    summary="Host introduces the topic and guest",
                    is_complete=True,
                    completeness_note="Full introduction captured"
                ),
                ConversationUnit(
                    start_index=3,
                    end_index=6,
                    unit_type="topic_discussion",
                    summary="Main discussion about the topic",
                    is_complete=True,
                    completeness_note="Complete topic coverage"
                ),
                ConversationUnit(
                    start_index=7,
                    end_index=9,
                    unit_type="conclusion",
                    summary="Closing thoughts and summary",
                    is_complete=False,
                    completeness_note="Cut off mid-sentence"
                )
            ],
            themes=[
                ConversationTheme(
                    name="Main Topic",
                    description="The central theme of discussion",
                    related_units=[1]
                )
            ],
            boundaries=[
                ConversationBoundary(
                    segment_index=3,
                    boundary_type="topic_shift",
                    description="Shift from introduction to main topic"
                ),
                ConversationBoundary(
                    segment_index=7,
                    boundary_type="closing",
                    description="Beginning of conclusion"
                )
            ],
            flow=ConversationFlow(
                narrative_arc="introduction -> exploration -> conclusion",
                pacing="steady",
                coherence_score=0.85
            ),
            insights=StructuralInsights(
                fragmentation_issues=["Conclusion cut off abruptly"],
                coherence_observations=["Good flow between segments"],
                suggested_improvements=["May need the final segment"]
            ),
            total_segments=10
        )
    
    def test_regroup_segments_basic(self, sample_segments, sample_structure):
        """Test basic segment regrouping."""
        regrouper = SegmentRegrouper()
        
        units = regrouper.regroup_segments(sample_segments, sample_structure)
        
        assert len(units) == 3
        assert units[0].unit_type == "introduction"
        assert len(units[0].segments) == 3
        assert units[0].is_complete is True
        
        assert units[1].unit_type == "topic_discussion"
        assert len(units[1].segments) == 4
        assert "Main Topic" in units[1].themes
        
        assert units[2].unit_type == "conclusion"
        assert units[2].is_complete is False
    
    def test_meaningful_unit_properties(self, sample_segments, sample_structure):
        """Test MeaningfulUnit properties."""
        regrouper = SegmentRegrouper()
        units = regrouper.regroup_segments(sample_segments, sample_structure)
        
        first_unit = units[0]
        assert first_unit.duration == 30.0  # 3 segments * 10s each
        assert first_unit.segment_count == 3
        assert "Host" in first_unit.speaker_distribution
        assert "Guest" in first_unit.speaker_distribution
        
        # Test text concatenation
        expected_text = "Segment 0 text Segment 1 text Segment 2 text"
        assert first_unit.text == expected_text
    
    def test_speaker_distribution(self, sample_segments, sample_structure):
        """Test speaker distribution calculation."""
        regrouper = SegmentRegrouper()
        units = regrouper.regroup_segments(sample_segments, sample_structure)
        
        # First unit has segments 0, 1, 2 (Host, Guest, Host)
        first_unit = units[0]
        # Two Host segments (20s) and one Guest segment (10s)
        assert first_unit.speaker_distribution["Host"] > 60  # ~66.7%
        assert first_unit.speaker_distribution["Guest"] < 40  # ~33.3%
    
    def test_unit_statistics(self, sample_segments, sample_structure):
        """Test unit statistics generation."""
        regrouper = SegmentRegrouper()
        units = regrouper.regroup_segments(sample_segments, sample_structure)
        
        stats = regrouper.get_unit_statistics(units)
        
        assert stats["total_units"] == 3
        assert stats["unit_types"]["introduction"] == 1
        assert stats["unit_types"]["topic_discussion"] == 1
        assert stats["unit_types"]["conclusion"] == 1
        assert stats["incomplete_units"] == 1
        assert stats["completeness_rate"] > 60  # 2/3 complete
        assert stats["average_duration"] > 0
        assert stats["average_segments_per_unit"] > 3
    
    def test_empty_segments_error(self, sample_structure):
        """Test error handling for empty segments."""
        regrouper = SegmentRegrouper()
        
        with pytest.raises(Exception) as exc:
            regrouper.regroup_segments([], sample_structure)
        assert "No segments provided" in str(exc.value)
    
    def test_empty_structure_error(self, sample_segments):
        """Test error handling for empty structure."""
        regrouper = SegmentRegrouper()
        empty_structure = ConversationStructure(
            units=[],
            themes=[],
            boundaries=[],
            flow=ConversationFlow(
                narrative_arc="",
                pacing="",
                coherence_score=0.0
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                coherence_observations=[],
                suggested_improvements=[]
            ),
            total_segments=0
        )
        
        with pytest.raises(Exception) as exc:
            regrouper.regroup_segments(sample_segments, empty_structure)
        assert "No conversation units" in str(exc.value)