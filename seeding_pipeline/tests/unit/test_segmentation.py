"""Comprehensive tests for podcast segmentation module.

Tests for src/processing/segmentation.py covering all segmentation functionality.
"""

from typing import List, Dict, Any
from unittest import mock
import json

import pytest

from src.processing.segmentation import (
    EnhancedPodcastSegmenter, SegmentationResult, SegmentBoundary
)
from src.core.models import Segment, ComplexityLevel
from src.providers.llm.base import LLMProvider


class TestEnhancedPodcastSegmenter:
    """Test EnhancedPodcastSegmenter class."""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = mock.Mock(spec=LLMProvider)
        provider.complete = mock.Mock()
        return provider
    
    @pytest.fixture
    def segmenter(self, mock_llm_provider):
        """Create segmenter instance."""
        return EnhancedPodcastSegmenter(
            llm_provider=mock_llm_provider,
            min_segment_duration=30,
            max_segment_duration=300,
            overlap_duration=5
        )
    
    def test_segmenter_initialization(self, mock_llm_provider):
        """Test segmenter initialization."""
        segmenter = EnhancedPodcastSegmenter(
            llm_provider=mock_llm_provider,
            min_segment_duration=60,
            max_segment_duration=600,
            overlap_duration=10
        )
        
        assert segmenter.llm_provider == mock_llm_provider
        assert segmenter.min_segment_duration == 60
        assert segmenter.max_segment_duration == 600
        assert segmenter.overlap_duration == 10
    
    def test_segment_transcript_basic(self, segmenter, mock_llm_provider):
        """Test basic transcript segmentation."""
        transcript = {
            "segments": [
                {"text": "Welcome to our show.", "start": 0.0, "end": 3.0},
                {"text": "Today we discuss AI.", "start": 3.0, "end": 6.0},
                {"text": "AI is transformative.", "start": 6.0, "end": 9.0}
            ]
        }
        
        # Mock LLM responses
        mock_llm_provider.complete.side_effect = [
            json.dumps({
                "segments": [
                    {"start_index": 0, "end_index": 1, "topic": "Introduction"},
                    {"start_index": 1, "end_index": 2, "topic": "AI Discussion"}
                ]
            }),
            json.dumps({"classification": "intermediate", "technical_density": 0.3}),
            json.dumps({"classification": "technical", "technical_density": 0.7})
        ]
        
        result = segmenter.segment_transcript(transcript)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(s, Segment) for s in result)
        assert result[0].text == "Welcome to our show. Today we discuss AI."
        assert result[1].text == "AI is transformative."
    
    def test_segment_transcript_empty(self, segmenter):
        """Test segmentation with empty transcript."""
        result = segmenter.segment_transcript({"segments": []})
        assert result == []
    
    def test_segment_transcript_single_segment(self, segmenter, mock_llm_provider):
        """Test segmentation with single segment."""
        transcript = {
            "segments": [
                {"text": "Short segment.", "start": 0.0, "end": 2.0}
            ]
        }
        
        mock_llm_provider.complete.return_value = json.dumps({
            "segments": [{"start_index": 0, "end_index": 0, "topic": "Brief"}]
        })
        
        result = segmenter.segment_transcript(transcript)
        
        assert len(result) == 1
        assert result[0].text == "Short segment."
    
    def test_identify_segment_boundaries(self, segmenter, mock_llm_provider):
        """Test segment boundary identification."""
        raw_segments = [
            {"text": "Intro text", "start": 0.0, "end": 5.0},
            {"text": "Main content", "start": 5.0, "end": 10.0},
            {"text": "Conclusion", "start": 10.0, "end": 15.0}
        ]
        
        mock_llm_provider.complete.return_value = json.dumps({
            "segments": [
                {"start_index": 0, "end_index": 0, "topic": "Introduction", "coherence_score": 0.9},
                {"start_index": 1, "end_index": 2, "topic": "Main Discussion", "coherence_score": 0.85}
            ]
        })
        
        boundaries = segmenter._identify_segment_boundaries(raw_segments)
        
        assert len(boundaries) == 2
        assert boundaries[0].start_index == 0
        assert boundaries[0].end_index == 0
        assert boundaries[0].topic == "Introduction"
        assert boundaries[1].start_index == 1
        assert boundaries[1].end_index == 2
    
    def test_create_segments_from_boundaries(self, segmenter, mock_llm_provider):
        """Test segment creation from boundaries."""
        raw_segments = [
            {"text": "First part.", "start": 0.0, "end": 5.0},
            {"text": "Second part.", "start": 5.0, "end": 10.0},
            {"text": "Third part.", "start": 10.0, "end": 15.0}
        ]
        
        boundaries = [
            SegmentBoundary(0, 1, "Topic A", 0.9),
            SegmentBoundary(2, 2, "Topic B", 0.8)
        ]
        
        # Mock complexity analysis
        mock_llm_provider.complete.side_effect = [
            json.dumps({"classification": "layperson", "technical_density": 0.1}),
            json.dumps({"classification": "intermediate", "technical_density": 0.5})
        ]
        
        segments = segmenter._create_segments_from_boundaries(raw_segments, boundaries, "ep1")
        
        assert len(segments) == 2
        assert segments[0].text == "First part. Second part."
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 10.0
        assert segments[1].text == "Third part."
        assert segments[1].complexity_level == ComplexityLevel.INTERMEDIATE
    
    def test_merge_short_segments(self, segmenter):
        """Test merging of short segments."""
        boundaries = [
            SegmentBoundary(0, 0, "Very Short", 0.9),  # 5 seconds
            SegmentBoundary(1, 1, "Also Short", 0.8),  # 5 seconds
            SegmentBoundary(2, 4, "Normal", 0.85)      # 15 seconds
        ]
        
        raw_segments = [
            {"text": "A", "start": 0.0, "end": 5.0},
            {"text": "B", "start": 5.0, "end": 10.0},
            {"text": "C", "start": 10.0, "end": 15.0},
            {"text": "D", "start": 15.0, "end": 20.0},
            {"text": "E", "start": 20.0, "end": 25.0}
        ]
        
        merged = segmenter._merge_short_segments(boundaries, raw_segments)
        
        # Should merge first two short segments
        assert len(merged) == 2
        assert merged[0].start_index == 0
        assert merged[0].end_index == 1
        assert merged[1].start_index == 2
        assert merged[1].end_index == 4
    
    def test_split_long_segments(self, segmenter):
        """Test splitting of long segments."""
        # Create a very long boundary (400 seconds)
        boundaries = [
            SegmentBoundary(0, 79, "Very Long Topic", 0.9)
        ]
        
        raw_segments = [{"text": f"Part {i}.", "start": i*5.0, "end": (i+1)*5.0} 
                       for i in range(80)]
        
        split = segmenter._split_long_segments(boundaries, raw_segments)
        
        # Should split into multiple segments
        assert len(split) > 1
        # Each segment should be under max duration (300s)
        for boundary in split:
            duration = raw_segments[boundary.end_index]["end"] - raw_segments[boundary.start_index]["start"]
            assert duration <= segmenter.max_segment_duration
    
    def test_analyze_complexity(self, segmenter, mock_llm_provider):
        """Test complexity analysis."""
        mock_llm_provider.complete.return_value = json.dumps({
            "classification": "expert",
            "technical_density": 0.9,
            "requires_domain_knowledge": True,
            "accessibility_score": 0.3
        })
        
        level, density = segmenter._analyze_complexity("Highly technical content")
        
        assert level == ComplexityLevel.EXPERT
        assert density == 0.9
    
    def test_analyze_complexity_error_handling(self, segmenter, mock_llm_provider):
        """Test complexity analysis error handling."""
        mock_llm_provider.complete.side_effect = Exception("LLM error")
        
        level, density = segmenter._analyze_complexity("Some content")
        
        assert level == ComplexityLevel.UNKNOWN
        assert density == 0.5
    
    def test_calculate_information_density(self, segmenter):
        """Test information density calculation."""
        segment_text = """
        This segment discusses multiple important concepts including artificial intelligence,
        machine learning algorithms, neural networks, deep learning frameworks,
        and their applications in healthcare, finance, and autonomous vehicles.
        We also explore ethical considerations and future implications.
        """
        
        density = segmenter._calculate_information_density(segment_text)
        
        # Should have moderate to high density due to many concepts
        assert 0.5 <= density <= 1.0
    
    def test_segment_with_speaker_info(self, segmenter, mock_llm_provider):
        """Test segmentation preserving speaker information."""
        transcript = {
            "segments": [
                {"text": "Hello everyone.", "start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
                {"text": "Welcome to the show.", "start": 2.0, "end": 4.0, "speaker": "SPEAKER_00"},
                {"text": "Thanks for having me.", "start": 4.0, "end": 6.0, "speaker": "SPEAKER_01"}
            ]
        }
        
        mock_llm_provider.complete.return_value = json.dumps({
            "segments": [
                {"start_index": 0, "end_index": 2, "topic": "Introduction"}
            ]
        })
        
        result = segmenter.segment_transcript(transcript)
        
        assert len(result) == 1
        # Should use most common speaker in segment
        assert result[0].speaker in ["SPEAKER_00", "SPEAKER_01"]
    
    def test_segmentation_result_creation(self):
        """Test SegmentationResult dataclass."""
        segments = [
            Segment(
                id="seg1",
                text="Test segment",
                start_time=0.0,
                end_time=10.0,
                speaker="Host"
            )
        ]
        
        result = SegmentationResult(
            segments=segments,
            total_duration=10.0,
            segment_count=1,
            average_segment_duration=10.0
        )
        
        assert result.segments == segments
        assert result.total_duration == 10.0
        assert result.segment_count == 1
        assert result.average_segment_duration == 10.0


class TestSegmentBoundary:
    """Test SegmentBoundary dataclass."""
    
    def test_segment_boundary_creation(self):
        """Test creating segment boundary."""
        boundary = SegmentBoundary(
            start_index=0,
            end_index=5,
            topic="AI Discussion",
            coherence_score=0.85
        )
        
        assert boundary.start_index == 0
        assert boundary.end_index == 5
        assert boundary.topic == "AI Discussion"
        assert boundary.coherence_score == 0.85
    
    def test_segment_boundary_defaults(self):
        """Test segment boundary with defaults."""
        boundary = SegmentBoundary(
            start_index=0,
            end_index=1
        )
        
        assert boundary.topic == ""
        assert boundary.coherence_score == 0.0


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def segmenter(self):
        """Create segmenter for edge case testing."""
        mock_llm = mock.Mock()
        return EnhancedPodcastSegmenter(llm_provider=mock_llm)
    
    def test_very_long_transcript(self, segmenter):
        """Test handling very long transcripts."""
        # Create transcript with 1000 segments
        transcript = {
            "segments": [
                {"text": f"Segment {i}.", "start": i*2.0, "end": (i+1)*2.0}
                for i in range(1000)
            ]
        }
        
        segmenter.llm_provider.complete.return_value = json.dumps({
            "segments": [
                {"start_index": i*100, "end_index": (i+1)*100-1, "topic": f"Part {i}"}
                for i in range(10)
            ]
        })
        
        result = segmenter.segment_transcript(transcript)
        
        # Should handle large transcript
        assert len(result) > 0
        assert all(isinstance(s, Segment) for s in result)
    
    def test_malformed_llm_response(self, segmenter):
        """Test handling malformed LLM responses."""
        transcript = {
            "segments": [{"text": "Test", "start": 0.0, "end": 1.0}]
        }
        
        # Return invalid JSON
        segmenter.llm_provider.complete.return_value = "Not valid JSON"
        
        result = segmenter.segment_transcript(transcript)
        
        # Should handle gracefully
        assert isinstance(result, list)
    
    def test_overlapping_segments(self, segmenter):
        """Test handling overlapping segment times."""
        transcript = {
            "segments": [
                {"text": "First", "start": 0.0, "end": 5.0},
                {"text": "Overlap", "start": 4.0, "end": 8.0},  # Overlaps
                {"text": "Third", "start": 8.0, "end": 12.0}
            ]
        }
        
        segmenter.llm_provider.complete.return_value = json.dumps({
            "segments": [{"start_index": 0, "end_index": 2, "topic": "All"}]
        })
        
        result = segmenter.segment_transcript(transcript)
        
        # Should handle overlaps
        assert len(result) > 0
    
    def test_missing_fields_in_transcript(self, segmenter):
        """Test handling missing fields in transcript segments."""
        transcript = {
            "segments": [
                {"text": "No timestamps"},  # Missing start/end
                {"start": 0.0, "end": 5.0},  # Missing text
                {"text": "Valid", "start": 5.0, "end": 10.0}
            ]
        }
        
        segmenter.llm_provider.complete.return_value = json.dumps({
            "segments": [{"start_index": 2, "end_index": 2, "topic": "Valid only"}]
        })
        
        result = segmenter.segment_transcript(transcript)
        
        # Should skip invalid segments
        assert len(result) <= 1