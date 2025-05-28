"""Unit tests for segmentation module."""

import pytest
from unittest.mock import Mock, MagicMock

from src.processing import EnhancedPodcastSegmenter
from src.providers.audio import MockAudioProvider
from src.core import TranscriptSegment, DiarizationSegment


class TestEnhancedPodcastSegmenter:
    """Test the EnhancedPodcastSegmenter class."""
    
    def test_segmenter_initialization(self):
        """Test segmenter initialization with config."""
        mock_provider = Mock()
        config = {
            "min_segment_tokens": 100,
            "max_segment_tokens": 500,
            "ad_detection_enabled": False
        }
        
        segmenter = EnhancedPodcastSegmenter(mock_provider, config)
        
        assert segmenter.audio_provider == mock_provider
        assert segmenter.config["min_segment_tokens"] == 100
        assert segmenter.config["max_segment_tokens"] == 500
        assert segmenter.config["ad_detection_enabled"] is False
        
    def test_process_audio_with_mock_provider(self):
        """Test audio processing with mock provider."""
        # Create mock segments
        mock_segments = [
            TranscriptSegment(
                id=f"seg_{i}",
                text=f"This is segment {i}",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                confidence=0.95
            ) for i in range(3)
        ]
        mock_provider = MockAudioProvider(config={"mock_segments": mock_segments})
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        
        result = segmenter.process_audio("fake_audio.mp3")
        
        assert "transcript" in result
        assert "diarization" in result
        assert "metadata" in result
        assert len(result["transcript"]) == 3
        assert result["metadata"]["total_segments"] == 3
        
    def test_advertisement_detection(self):
        """Test advertisement detection in segments."""
        mock_provider = Mock()
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        
        # Test with ad content
        ad_text = "This episode is brought to you by our sponsor. Use promo code SAVE20."
        assert segmenter._detect_advertisement(ad_text) is True
        
        # Test with normal content
        normal_text = "Today we're discussing artificial intelligence and its impact."
        assert segmenter._detect_advertisement(normal_text) is False
        
        # Test with config disabled
        segmenter.config["ad_detection_enabled"] = False
        assert segmenter._detect_advertisement(ad_text) is False
        
    def test_sentiment_analysis(self):
        """Test sentiment analysis functionality."""
        mock_provider = Mock()
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        
        # Test positive sentiment
        positive_text = "This is absolutely amazing and wonderful! I love it!"
        sentiment = segmenter._analyze_segment_sentiment(positive_text)
        assert sentiment["polarity"] == "positive"
        assert sentiment["score"] > 0
        assert sentiment["positive_count"] > sentiment["negative_count"]
        
        # Test negative sentiment
        negative_text = "This is terrible and awful. I hate this horrible experience."
        sentiment = segmenter._analyze_segment_sentiment(negative_text)
        assert sentiment["polarity"] == "negative"
        assert sentiment["score"] < 0
        assert sentiment["negative_count"] > sentiment["positive_count"]
        
        # Test neutral sentiment
        neutral_text = "The weather today is cloudy with a chance of rain."
        sentiment = segmenter._analyze_segment_sentiment(neutral_text)
        assert sentiment["polarity"] == "neutral"
        assert -0.2 <= sentiment["score"] <= 0.2
        
    def test_post_processing(self):
        """Test segment post-processing."""
        mock_provider = Mock()
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        
        # Create test segments
        segments = [
            TranscriptSegment(
                id="seg_1",
                text="Welcome to our podcast sponsored by TechCorp.",
                start_time=0.0,
                end_time=5.0,
                speaker="Speaker_0"
            ),
            TranscriptSegment(
                id="seg_2",
                text="",  # Empty segment should be skipped
                start_time=5.0,
                end_time=5.5,
                speaker="Speaker_0"
            ),
            TranscriptSegment(
                id="seg_3",
                text="Today we have great news to share!",
                start_time=5.5,
                end_time=10.0,
                speaker="Speaker_1"
            )
        ]
        
        processed = segmenter._post_process_segments(segments)
        
        # Check that empty segment was skipped
        assert len(processed) == 2
        
        # Check first segment (should be ad)
        assert processed[0]["is_advertisement"] is True
        assert processed[0]["speaker"] == "Speaker_0"
        assert processed[0]["word_count"] == 7
        assert processed[0]["duration_seconds"] == 5.0
        
        # Check second segment
        assert processed[1]["is_advertisement"] is False
        assert processed[1]["sentiment"]["polarity"] == "positive"
        
    def test_metadata_calculation(self):
        """Test metadata calculation from segments."""
        mock_provider = Mock()
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        
        # Create test segments
        segments = [
            {
                "text": "Segment 1",
                "start_time": 0.0,
                "end_time": 10.0,
                "word_count": 10,
                "is_advertisement": True,
                "sentiment": {"polarity": "positive"},
                "speaker": "Speaker_0"
            },
            {
                "text": "Segment 2",
                "start_time": 10.0,
                "end_time": 20.0,
                "word_count": 15,
                "is_advertisement": False,
                "sentiment": {"polarity": "negative"},
                "speaker": "Speaker_1"
            },
            {
                "text": "Segment 3",
                "start_time": 20.0,
                "end_time": 30.0,
                "word_count": 20,
                "is_advertisement": False,
                "sentiment": {"polarity": "neutral"},
                "speaker": "Speaker_0"
            }
        ]
        
        metadata = segmenter._calculate_metadata(segments)
        
        assert metadata["total_segments"] == 3
        assert metadata["total_duration"] == 30.0
        assert metadata["total_words"] == 45
        assert metadata["advertisement_count"] == 1
        assert metadata["unique_speakers"] == 2
        assert "Speaker_0" in metadata["speakers"]
        assert "Speaker_1" in metadata["speakers"]
        assert metadata["sentiment_distribution"]["positive"] == pytest.approx(1/3, 0.01)
        assert metadata["sentiment_distribution"]["negative"] == pytest.approx(1/3, 0.01)
        assert metadata["sentiment_distribution"]["neutral"] == pytest.approx(1/3, 0.01)
        
    def test_empty_audio_handling(self):
        """Test handling of empty audio results."""
        mock_provider = Mock()
        mock_provider.transcribe.return_value = []
        
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        result = segmenter.process_audio("empty_audio.mp3")
        
        assert result["transcript"] == []
        assert result["metadata"]["warning"] == "No transcript segments"
        
    def test_transcription_error_handling(self):
        """Test handling of transcription errors."""
        mock_provider = Mock()
        mock_provider.transcribe.side_effect = Exception("Transcription failed")
        
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        result = segmenter.process_audio("bad_audio.mp3")
        
        assert result["transcript"] == []
        assert "error" in result["metadata"]
        assert "Transcription failed" in result["metadata"]["error"]
        
    def test_diarization_failure_handling(self):
        """Test handling when diarization fails but transcription succeeds."""
        mock_provider = Mock()
        mock_provider.transcribe.return_value = [
            TranscriptSegment(id="seg_1", text="Test", start_time=0, end_time=5)
        ]
        mock_provider.diarize.side_effect = Exception("Diarization failed")
        mock_provider.align_transcript_with_diarization.return_value = [
            TranscriptSegment(id="seg_1", text="Test", start_time=0, end_time=5)
        ]
        
        segmenter = EnhancedPodcastSegmenter(mock_provider)
        result = segmenter.process_audio("audio.mp3")
        
        # Should continue without diarization
        assert len(result["transcript"]) == 1
        assert result["diarization"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])