"""Comprehensive unit tests for VTT segmentation module."""

from typing import List, Dict, Any
from unittest.mock import Mock, patch

import pytest

from src.core import constants
from src.core.interfaces import TranscriptSegment
from src.vtt.vtt_segmentation import VTTSegmenter, SegmentMetadata
class TestSegmentMetadata:
    """Test SegmentMetadata dataclass."""
    
    def test_segment_metadata_creation(self):
        """Test creating segment metadata."""
        metadata = SegmentMetadata(
            is_advertisement=True,
            sentiment={"score": 0.5, "polarity": "positive"},
            segment_index=1,
            word_count=10,
            duration_seconds=2.5
        )
        
        assert metadata.is_advertisement is True
        assert metadata.sentiment == {"score": 0.5, "polarity": "positive"}
        assert metadata.segment_index == 1
        assert metadata.word_count == 10
        assert metadata.duration_seconds == 2.5
    
    def test_segment_metadata_defaults(self):
        """Test segment metadata with default values."""
        metadata = SegmentMetadata()
        
        assert metadata.is_advertisement is False
        assert metadata.sentiment is None
        assert metadata.segment_index == 0
        assert metadata.word_count == 0
        assert metadata.duration_seconds == 0.0


class TestVTTSegmenter:
    """Test VTT segmenter functionality."""
    
    @pytest.fixture
    def segmenter(self):
        """Create a VTT segmenter instance."""
        return VTTSegmenter()
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample transcript segments."""
        return [
            TranscriptSegment("seg_0", "Welcome to our podcast.", 0.0, 2.0, "Host", 1.0),
            TranscriptSegment("seg_1", "Today we're discussing AI.", 2.0, 4.0, "Host", 1.0),
            TranscriptSegment("seg_2", "Thanks to our sponsor, TechCorp.", 4.0, 6.0, "Host", 1.0),
            TranscriptSegment("seg_3", "AI is amazing and revolutionary!", 6.0, 8.0, "Guest", 1.0),
            TranscriptSegment("seg_4", "", 8.0, 8.5, "Guest", 1.0),  # Empty segment
        ]
    
    def test_segmenter_initialization_default(self, segmenter):
        """Test segmenter initialization with default config."""
        assert segmenter.config['min_segment_tokens'] == constants.MIN_SEGMENT_TOKENS
        assert segmenter.config['max_segment_tokens'] == constants.MAX_SEGMENT_TOKENS
        assert segmenter.config['ad_detection_enabled'] is True
        assert segmenter.config['use_semantic_boundaries'] is True
    
    def test_segmenter_initialization_custom(self):
        """Test segmenter initialization with custom config."""
        config = {
            'min_segment_tokens': 10,
            'max_segment_tokens': 100,
            'ad_detection_enabled': False,
            'use_semantic_boundaries': False
        }
        segmenter = VTTSegmenter(config)
        
        assert segmenter.config['min_segment_tokens'] == 10
        assert segmenter.config['max_segment_tokens'] == 100
        assert segmenter.config['ad_detection_enabled'] is False
        assert segmenter.config['use_semantic_boundaries'] is False
    
    def test_process_segments_empty(self, segmenter):
        """Test processing empty segment list."""
        result = segmenter.process_segments([])
        
        assert result["transcript"] == []
        assert result["metadata"]["warning"] == "No segments provided"
    
    def test_process_segments_basic(self, segmenter, sample_segments):
        """Test basic segment processing."""
        result = segmenter.process_segments(sample_segments)
        
        assert "transcript" in result
        assert "metadata" in result
        assert len(result["transcript"]) == 4  # Empty segment should be skipped
        
        # Check first segment
        first_seg = result["transcript"][0]
        assert first_seg["text"] == "Welcome to our podcast."
        assert first_seg["start_time"] == 0.0
        assert first_seg["end_time"] == 2.0
        assert first_seg["speaker"] == "Host"
        assert first_seg["segment_index"] == 0
        assert first_seg["word_count"] == 4
        assert first_seg["duration_seconds"] == 2.0
    
    def test_process_segments_with_advertisement(self, segmenter, sample_segments):
        """Test segment processing with advertisement detection."""
        result = segmenter.process_segments(sample_segments)
        
        # Check advertisement detection
        segments = result["transcript"]
        assert segments[2]["is_advertisement"] is True  # "Thanks to our sponsor"
        assert segments[0]["is_advertisement"] is False
        assert segments[1]["is_advertisement"] is False
    
    def test_process_segments_with_sentiment(self, segmenter, sample_segments):
        """Test segment processing with sentiment analysis."""
        result = segmenter.process_segments(sample_segments)
        
        segments = result["transcript"]
        
        # Check sentiment analysis
        assert all("sentiment" in seg for seg in segments)
        
        # "AI is amazing and revolutionary!" should be positive
        positive_segment = segments[3]
        assert positive_segment["sentiment"]["polarity"] == "positive"
        assert positive_segment["sentiment"]["score"] > 0
        assert positive_segment["sentiment"]["positive_count"] > 0
    
    def test_process_segments_metadata(self, segmenter, sample_segments):
        """Test metadata calculation."""
        result = segmenter.process_segments(sample_segments)
        
        metadata = result["metadata"]
        assert metadata["total_segments"] == 4
        assert metadata["total_duration"] == 8.0
        assert metadata["total_words"] == 18
        assert metadata["average_segment_duration"] == 2.0
        assert metadata["advertisement_count"] == 1
        assert metadata["advertisement_percentage"] == 0.25
        assert metadata["unique_speakers"] == 2
        assert set(metadata["speakers"]) == {"Guest", "Host"}
        assert "sentiment_distribution" in metadata
    
    def test_detect_advertisement_positive(self, segmenter):
        """Test positive advertisement detection."""
        ad_texts = [
            "Thanks to our sponsor TechCorp",
            "This episode is brought to you by Example Inc",
            "Visit our sponsor at example.com",
            "Use promo code PODCAST for 20% off",
            "Special offer for our listeners",
            "Sign up today for a free trial"
        ]
        
        for text in ad_texts:
            assert segmenter._detect_advertisement(text) is True
    
    def test_detect_advertisement_negative(self, segmenter):
        """Test negative advertisement detection."""
        non_ad_texts = [
            "Let's discuss today's topic",
            "The weather is nice today",
            "Artificial intelligence is fascinating",
            "Welcome to our show"
        ]
        
        for text in non_ad_texts:
            assert segmenter._detect_advertisement(text) is False
    
    def test_detect_advertisement_case_insensitive(self, segmenter):
        """Test case-insensitive advertisement detection."""
        assert segmenter._detect_advertisement("BROUGHT TO YOU BY") is True
        assert segmenter._detect_advertisement("Promo Code: SAVE20") is True
    
    def test_analyze_segment_sentiment_positive(self, segmenter):
        """Test positive sentiment analysis."""
        text = "This is absolutely amazing! I love this wonderful product. It's fantastic!"
        sentiment = segmenter._analyze_segment_sentiment(text)
        
        assert sentiment["polarity"] == "positive"
        assert sentiment["score"] > 0
        assert sentiment["positive_count"] > sentiment["negative_count"]
    
    def test_analyze_segment_sentiment_negative(self, segmenter):
        """Test negative sentiment analysis."""
        text = "This is terrible and awful. I hate this horrible experience. It's a disaster!"
        sentiment = segmenter._analyze_segment_sentiment(text)
        
        assert sentiment["polarity"] == "negative"
        assert sentiment["score"] < 0
        assert sentiment["negative_count"] > sentiment["positive_count"]
    
    def test_analyze_segment_sentiment_neutral(self, segmenter):
        """Test neutral sentiment analysis."""
        text = "The meeting is scheduled for Tuesday at 3 PM."
        sentiment = segmenter._analyze_segment_sentiment(text)
        
        assert sentiment["polarity"] == "neutral"
        assert sentiment["score"] == 0.0
        assert sentiment["positive_count"] == 0
        assert sentiment["negative_count"] == 0
    
    def test_analyze_segment_sentiment_mixed(self, segmenter):
        """Test mixed sentiment analysis."""
        text = "The product has some good features but also has terrible problems."
        sentiment = segmenter._analyze_segment_sentiment(text)
        
        # Should have both positive and negative counts
        assert sentiment["positive_count"] > 0
        assert sentiment["negative_count"] > 0
    
    def test_calculate_metadata_empty(self, segmenter):
        """Test metadata calculation with empty segments."""
        metadata = segmenter._calculate_metadata([])
        
        assert metadata["total_segments"] == 0
        assert metadata["total_duration"] == 0.0
        assert metadata["total_words"] == 0
        assert metadata["advertisement_count"] == 0
        assert metadata["sentiment_distribution"] == {}
    
    def test_calculate_metadata_comprehensive(self, segmenter):
        """Test comprehensive metadata calculation."""
        segments = [
            {
                "text": "Welcome",
                "start_time": 0.0,
                "end_time": 1.0,
                "speaker": "Host",
                "word_count": 1,
                "is_advertisement": False,
                "sentiment": {"polarity": "neutral"}
            },
            {
                "text": "Great product",
                "start_time": 1.0,
                "end_time": 3.0,
                "speaker": "Guest",
                "word_count": 2,
                "is_advertisement": True,
                "sentiment": {"polarity": "positive"}
            },
            {
                "text": "Terrible issue",
                "start_time": 3.0,
                "end_time": 5.0,
                "speaker": "Host",
                "word_count": 2,
                "is_advertisement": False,
                "sentiment": {"polarity": "negative"}
            }
        ]
        
        metadata = segmenter._calculate_metadata(segments)
        
        assert metadata["total_segments"] == 3
        assert metadata["total_duration"] == 5.0
        assert metadata["total_words"] == 5
        assert metadata["average_segment_duration"] == pytest.approx(1.67, rel=0.01)
        assert metadata["advertisement_count"] == 1
        assert metadata["advertisement_percentage"] == pytest.approx(0.333, rel=0.01)
        assert metadata["unique_speakers"] == 2
        assert set(metadata["speakers"]) == {"Guest", "Host"}
        
        # Check sentiment distribution
        dist = metadata["sentiment_distribution"]
        assert dist["positive"] == pytest.approx(0.333, rel=0.01)
        assert dist["negative"] == pytest.approx(0.333, rel=0.01)
        assert dist["neutral"] == pytest.approx(0.333, rel=0.01)
    
    def test_post_process_segments_attribute_access(self, segmenter):
        """Test post-processing with proper attribute access."""
        # Create mock segments with proper attributes
        mock_segment = Mock()
        mock_segment.text = "Test text"
        mock_segment.start_time = 0.0
        mock_segment.end_time = 2.0
        mock_segment.speaker = "Speaker1"
        
        segments = [mock_segment]
        
        result = segmenter._post_process_segments(segments)
        
        assert len(result) == 1
        assert result[0]["text"] == "Test text"
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 2.0
        assert result[0]["speaker"] == "Speaker1"
    
    def test_process_segments_with_disabled_features(self):
        """Test processing with features disabled."""
        config = {
            'ad_detection_enabled': False
        }
        segmenter = VTTSegmenter(config)
        
        segment = TranscriptSegment(
            "seg_0", 
            "Thanks to our sponsor", 
            0.0, 
            2.0, 
            "Host", 
            1.0
        )
        
        result = segmenter.process_segments([segment])
        
        # Advertisement detection should be skipped
        assert "is_advertisement" not in result["transcript"][0]
    
    @patch('src.vtt.vtt_segmentation.logger')
    def test_logging(self, mock_logger, segmenter):
        """Test logging functionality."""
        segmenter.process_segments([])
        
        # Check logging calls
        mock_logger.info.assert_called()
        mock_logger.warning.assert_called_with("No segments to process")
    
    def test_word_count_calculation(self, segmenter):
        """Test accurate word counting."""
        segments = [
            TranscriptSegment("seg_0", "One two three", 0.0, 1.0, "Speaker", 1.0),
            TranscriptSegment("seg_1", "  Four   five  ", 1.0, 2.0, "Speaker", 1.0),
            TranscriptSegment("seg_2", "Six-seven eight's", 2.0, 3.0, "Speaker", 1.0),
        ]
        
        result = segmenter.process_segments(segments)
        
        assert result["transcript"][0]["word_count"] == 3
        assert result["transcript"][1]["word_count"] == 2
        assert result["transcript"][2]["word_count"] == 2
    
    def test_duration_calculation(self, segmenter):
        """Test accurate duration calculation."""
        segments = [
            TranscriptSegment("seg_0", "Text", 0.0, 1.5, "Speaker", 1.0),
            TranscriptSegment("seg_1", "More text", 1.5, 4.25, "Speaker", 1.0),
        ]
        
        result = segmenter.process_segments(segments)
        
        assert result["transcript"][0]["duration_seconds"] == 1.5
        assert result["transcript"][1]["duration_seconds"] == 2.75
        assert result["metadata"]["total_duration"] == 4.25