"""Integration tests for validation and enhancement features.

Tests the features implemented in Phases 1-4:
- RSS description preservation in VTT files
- YouTube URL extraction and storage
- Transcript length validation system
- LLM continuation and stitching system
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

from src.feed_parser import Episode, PodcastMetadata
from src.gemini_client import RateLimitedGeminiClient
from src.vtt_generator import VTTGenerator, VTTMetadata
from src.youtube_searcher import YouTubeSearcher
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.config import Config


class TestRSSDescriptionPreservation:
    """Test RSS description preservation in VTT files."""
    
    def test_vtt_metadata_includes_description(self):
        """Test VTTMetadata properly handles descriptions."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Test Episode", 
            publication_date="2024-01-01",
            description="This is a test episode description."
        )
        
        note_block = metadata.to_note_block()
        
        # Check description in human-readable format
        assert "Description: This is a test episode description." in note_block
        
        # Check description in JSON metadata
        json_start = note_block.find('{"podcast":')
        json_end = note_block.rfind('}') + 1
        json_data = json.loads(note_block[json_start:json_end])
        assert json_data["description"] == "This is a test episode description."
    
    def test_vtt_metadata_long_description_wrapping(self):
        """Test long descriptions are properly wrapped."""
        long_description = "This is a very long description that should be wrapped " * 5
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            publication_date="2024-01-01", 
            description=long_description
        )
        
        note_block = metadata.to_note_block()
        lines = note_block.split('\n')
        
        # Check that description lines don't exceed 80 characters
        for line in lines:
            if line.startswith("Description:"):
                assert len(line) <= 80
    
    def test_episode_data_to_vtt_metadata(self):
        """Test episode data conversion to VTT metadata includes description."""
        vtt_gen = VTTGenerator()
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Test Episode',
            'publication_date': '2024-01-01',
            'description': 'Episode description from RSS'
        }
        
        metadata = vtt_gen.create_metadata_from_episode(episode_data)
        assert metadata.description == 'Episode description from RSS'


class TestYouTubeURLExtraction:
    """Test YouTube URL extraction and storage."""
    
    def test_episode_model_youtube_field(self):
        """Test Episode model includes youtube_url field."""
        episode = Episode(
            title="Test Episode",
            audio_url="http://example.com/audio.mp3",
            guid="test-guid",
            youtube_url="https://youtube.com/watch?v=test123"
        )
        
        assert episode.youtube_url == "https://youtube.com/watch?v=test123"
        
        # Test to_dict includes youtube_url
        episode_dict = episode.to_dict()
        assert episode_dict['youtube_url'] == "https://youtube.com/watch?v=test123"
    
    def test_youtube_searcher_rss_extraction(self):
        """Test YouTube URL extraction from RSS content."""
        config = Config(test_mode=True)
        searcher = YouTubeSearcher(config)
        
        # Test RSS content with YouTube URL
        rss_content = "Check out the video version at https://youtube.com/watch?v=abc123"
        url = searcher._extract_from_rss(rss_content)
        
        assert url == "https://www.youtube.com/watch?v=abc123"
    
    def test_youtube_searcher_no_url_found(self):
        """Test YouTube searcher when no URL is found."""
        config = Config(test_mode=True)
        searcher = YouTubeSearcher(config)
        
        # Test RSS content without YouTube URL
        rss_content = "This episode has no video version available."
        url = searcher._extract_from_rss(rss_content)
        
        assert url is None
    
    def test_vtt_metadata_includes_youtube_url(self):
        """Test VTT metadata includes YouTube URL."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            publication_date="2024-01-01",
            youtube_url="https://youtube.com/watch?v=test123"
        )
        
        note_block = metadata.to_note_block()
        
        # Check YouTube URL in human-readable format
        assert "YouTube: https://youtube.com/watch?v=test123" in note_block
        
        # Check YouTube URL in JSON metadata
        json_start = note_block.find('{"podcast":')
        json_end = note_block.rfind('}') + 1
        json_data = json.loads(note_block[json_start:json_end])
        assert json_data["youtube_url"] == "https://youtube.com/watch?v=test123"


class TestTranscriptValidation:
    """Test transcript length validation system."""
    
    def test_gemini_client_validation_complete(self):
        """Test transcript validation for complete transcript."""
        client = RateLimitedGeminiClient(["test-key"])
        
        # Mock transcript with full coverage
        transcript = """00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>This is the beginning of the episode.

00:28:55.000 --> 00:29:00.000
<v SPEAKER_1>And this is the end of the episode."""
        
        duration_seconds = 30 * 60  # 30 minutes
        is_complete, coverage = client.validate_transcript_completeness(transcript, duration_seconds)
        
        assert is_complete is True
        assert coverage > 0.95  # Should be ~97% coverage
    
    def test_gemini_client_validation_incomplete(self):
        """Test transcript validation for incomplete transcript."""
        client = RateLimitedGeminiClient(["test-key"])
        
        # Mock transcript with partial coverage
        transcript = """00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>This is the beginning of the episode.

00:10:55.000 --> 00:11:00.000
<v SPEAKER_1>This episode cuts off early."""
        
        duration_seconds = 30 * 60  # 30 minutes
        is_complete, coverage = client.validate_transcript_completeness(transcript, duration_seconds)
        
        assert is_complete is False
        assert coverage < 0.5  # Should be ~37% coverage
    
    def test_timestamp_parsing(self):
        """Test VTT timestamp parsing to seconds."""
        client = RateLimitedGeminiClient(["test-key"])
        
        # Test different timestamp formats
        assert client._parse_timestamp_to_seconds("00:05:30.250") == 330.25
        assert client._parse_timestamp_to_seconds("01:23:45.500") == 5025.5
        assert client._parse_timestamp_to_seconds("05:30.750") == 330.75


class TestContinuationAndStitching:
    """Test LLM continuation and stitching system."""
    
    def test_transcript_stitching_single_segment(self):
        """Test stitching with single segment returns original."""
        client = RateLimitedGeminiClient(["test-key"])
        
        segments = ["WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest content"]
        result = client.stitch_transcripts(segments)
        
        assert result == segments[0]
    
    def test_transcript_stitching_multiple_segments(self):
        """Test stitching multiple segments."""
        client = RateLimitedGeminiClient(["test-key"])
        
        segments = [
            "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v SPEAKER_1>First segment",
            "00:00:05.000 --> 00:00:10.000\n<v SPEAKER_1>Second segment"
        ]
        
        result = client.stitch_transcripts(segments)
        
        # Should contain both segments
        assert "First segment" in result
        assert "Second segment" in result
        assert result.startswith("WEBVTT")
    
    def test_vtt_cue_parsing(self):
        """Test parsing VTT cues for stitching."""
        client = RateLimitedGeminiClient(["test-key"])
        
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>First cue

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Second cue"""
        
        cues = client._parse_vtt_cues(vtt_content)
        
        assert len(cues) == 2
        assert cues[0]['start_time'] == "00:00:00.000"
        assert cues[0]['end_time'] == "00:00:05.000"
        assert cues[1]['start_seconds'] == 5.0
        assert cues[1]['end_seconds'] == 10.0


class TestContinuationTracking:
    """Test continuation tracking in progress tracker."""
    
    def test_progress_tracker_continuation_fields(self):
        """Test progress tracker includes continuation fields."""
        tracker = ProgressTracker(Path("/tmp/test_progress.json"))
        
        episode_data = {
            'guid': 'test-guid',
            'title': 'Test Episode',
            'podcast_name': 'Test Podcast',
            'audio_url': 'http://example.com/audio.mp3'
        }
        
        continuation_info = {
            'continuation_attempts': 3,
            'final_coverage_ratio': 0.92,
            'segment_count': 4
        }
        
        tracker.update_episode_state(
            'test-guid', 
            EpisodeStatus.COMPLETED, 
            episode_data,
            output_file='/tmp/test.vtt',
            continuation_info=continuation_info
        )
        
        episode = tracker.state.episodes['test-guid']
        assert episode.continuation_attempts == 3
        assert episode.final_coverage_ratio == 0.92
        assert episode.segment_count == 4
    
    def test_episode_progress_serialization(self):
        """Test episode progress with continuation fields serializes correctly."""
        from src.progress_tracker import EpisodeProgress
        
        episode = EpisodeProgress(
            guid="test-guid",
            status=EpisodeStatus.COMPLETED,
            continuation_attempts=2,
            final_coverage_ratio=0.88,
            segment_count=3
        )
        
        # Test to_dict includes continuation fields
        data = episode.to_dict()
        assert data['continuation_attempts'] == 2
        assert data['final_coverage_ratio'] == 0.88
        assert data['segment_count'] == 3
        
        # Test from_dict restores continuation fields
        restored = EpisodeProgress.from_dict(data)
        assert restored.continuation_attempts == 2
        assert restored.final_coverage_ratio == 0.88
        assert restored.segment_count == 3


class TestIntegrationFlow:
    """Test integration of all features together."""
    
    @pytest.mark.asyncio
    async def test_episode_processing_with_all_features(self):
        """Test episode processing includes all new features."""
        # This is a simplified integration test
        # In a full test, we'd mock the actual API calls
        
        # Test data
        episode = Episode(
            title="Integration Test Episode",
            audio_url="http://example.com/audio.mp3",
            guid="integration-test-guid",
            description="Test episode for integration testing",
            duration="00:30:00"
        )
        
        # Test that all features work together
        assert episode.description == "Test episode for integration testing"
        assert episode.youtube_url is None  # Will be populated during processing
        assert episode.duration == "00:30:00"
        
        # Test VTT generation includes all metadata
        vtt_gen = VTTGenerator()
        episode_data = episode.to_dict()
        episode_data['podcast_name'] = 'Integration Test Podcast'
        episode_data['youtube_url'] = 'https://youtube.com/watch?v=integration123'
        
        metadata = vtt_gen.create_metadata_from_episode(episode_data)
        
        assert metadata.description == "Test episode for integration testing"
        assert metadata.youtube_url == 'https://youtube.com/watch?v=integration123'
        assert metadata.podcast_name == 'Integration Test Podcast'
        
        # Test VTT output includes all features
        note_block = metadata.to_note_block()
        assert "Description:" in note_block
        assert "YouTube:" in note_block
        assert "Integration Test Podcast" in note_block


if __name__ == "__main__":
    pytest.main([__file__])