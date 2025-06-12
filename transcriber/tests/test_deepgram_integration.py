"""Integration tests for Deepgram-based podcast transcription.

Tests the complete flow from RSS feed parsing through VTT generation
using mocked Deepgram responses.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from src.simple_orchestrator import SimpleOrchestrator
from src.feed_parser import Episode
from src.deepgram_client import DeepgramClient, DeepgramResponse
from src.vtt_formatter import VTTFormatter
from tests.fixtures.deepgram_responses import (
    get_successful_transcription,
    get_single_speaker_transcription,
    get_multi_speaker_panel,
    get_empty_transcription
)


class TestDeepgramIntegration:
    """Test complete Deepgram integration flow."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for test outputs."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_episode(self):
        """Create a mock Episode object."""
        episode = Episode(
            title="Test Episode: AI and Society",
            audio_url="https://example.com/episode1.mp3",
            guid="test-guid-123",
            description="A discussion about AI",
            published_date=datetime(2024, 6, 9),
            duration="45:00",
            author="Test Host"
        )
        episode.podcast_name = "Test Podcast"
        return episode
    
    def test_deepgram_client_mock_response(self):
        """Test Deepgram client returns proper mock response."""
        client = DeepgramClient(mock_enabled=True)
        response = client.transcribe_audio("https://example.com/test.mp3")
        
        assert isinstance(response, DeepgramResponse)
        assert response.transcript != ""
        assert len(response.words) > 0
        assert response.metadata['duration'] > 0
    
    
    def test_vtt_formatter_output(self):
        """Test VTT formatter generates valid WebVTT content."""
        formatter = VTTFormatter()
        mock_response = get_successful_transcription()
        
        vtt_content = formatter.format_deepgram_response(mock_response['results'])
        
        # Validate VTT structure
        assert vtt_content.startswith("WEBVTT")
        assert "NOTE Transcription powered by Deepgram" in vtt_content
        assert "-->" in vtt_content  # Has timestamp arrows
        assert "<v Speaker 0>" in vtt_content  # Has speaker tags
        assert "<v Speaker 1>" in vtt_content
        
        # Validate VTT format
        is_valid, error = formatter.validate_vtt(vtt_content)
        assert is_valid, f"VTT validation failed: {error}"
    
    def test_end_to_end_transcription(self, temp_output_dir, mock_episode):
        """Test complete transcription flow from episode to VTT file."""
        # Initialize orchestrator with mock mode
        orchestrator = SimpleOrchestrator(
            output_dir=temp_output_dir,
            mock_enabled=True
        )
        
        # Process episode
        result = orchestrator.process_episode(mock_episode)
        
        # Check result
        assert result['status'] == 'completed'
        assert result['output_path'] is not None
        assert result['error'] is None
        
        # Verify file was created
        output_path = Path(result['output_path'])
        assert output_path.exists()
        
        # Verify content
        with open(output_path, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
        
        assert vtt_content.startswith("WEBVTT")
        assert len(vtt_content) > 100  # Has substantial content
    
    def test_batch_processing(self, temp_output_dir):
        """Test processing multiple episodes."""
        # Create multiple mock episodes
        episodes = []
        for i in range(1, 4):
            ep = Episode(
                title=f"Episode {i}: Topic {i}",
                audio_url=f"https://example.com/episode{i}.mp3",
                guid=f"guid-{i}",
                description=f"Description {i}",
                published_date=datetime(2024, 6, i),
                duration="30:00",
                author="Host"
            )
            ep.podcast_name = "Test Podcast"
            episodes.append(ep)
        
        orchestrator = SimpleOrchestrator(
            output_dir=temp_output_dir,
            mock_enabled=True
        )
        
        results = orchestrator.process_episodes(episodes)
        
        assert results['total_episodes'] == 3
        assert results['completed'] == 3
        assert results['failed'] == 0
        
        # Verify all files created
        for episode_result in results['episodes']:
            assert episode_result['status'] == 'completed'
            assert Path(episode_result['output_path']).exists()
    
    def test_single_speaker_podcast(self):
        """Test handling of single-speaker (monologue) podcasts."""
        formatter = VTTFormatter()
        
        mock_response = get_single_speaker_transcription()
        words = mock_response['results']['channels'][0]['alternatives'][0]['words']
        
        # Verify only one speaker in mock data
        speakers = set(word.get('speaker', 0) for word in words)
        assert len(speakers) == 1  # Only one speaker
        assert 0 in speakers  # Speaker 0
        
        # Format to VTT
        vtt_content = formatter.format_deepgram_response(mock_response['results'])
        assert "<v Speaker 0>" in vtt_content
        assert "<v Speaker 1>" not in vtt_content
    
    def test_multi_speaker_panel(self):
        """Test handling of multi-speaker panel discussions."""
        formatter = VTTFormatter()
        
        mock_response = get_multi_speaker_panel()
        words = mock_response['results']['channels'][0]['alternatives'][0]['words']
        
        # Verify multiple speakers in mock data
        speakers = set(word.get('speaker', 0) for word in words)
        assert len(speakers) == 4  # 4 speakers (0, 1, 2, 3)
        assert speakers == {0, 1, 2, 3}
        
        # Format to VTT and verify all speakers appear
        vtt_content = formatter.format_deepgram_response(mock_response['results'])
        assert "<v Speaker 0>" in vtt_content
        assert "<v Speaker 1>" in vtt_content
        assert "<v Speaker 2>" in vtt_content
        assert "<v Speaker 3>" in vtt_content
    
    def test_empty_transcription_handling(self):
        """Test handling of empty transcription results."""
        formatter = VTTFormatter()
        mock_response = get_empty_transcription()
        
        vtt_content = formatter.format_deepgram_response(mock_response['results'])
        
        assert vtt_content.startswith("WEBVTT")
        assert "NOTE No transcript available" in vtt_content
    
    def test_output_directory_consistency(self, temp_output_dir, mock_episode):
        """Test that output files are saved to the correct location."""
        # Set explicit output directory in environment
        os.environ['TRANSCRIPT_OUTPUT_DIR'] = temp_output_dir
        
        orchestrator = SimpleOrchestrator(mock_enabled=True)
        result = orchestrator.process_episode(mock_episode)
        
        assert result['status'] == 'completed'
        
        # Verify file is in the correct directory
        output_path = Path(result['output_path'])
        assert str(output_path).startswith(temp_output_dir)
        assert output_path.parent.name == "Test_Podcast"  # Podcast name directory
        assert output_path.suffix == ".vtt"
    
    def test_filename_generation(self, temp_output_dir):
        """Test proper filename generation with sanitization."""
        from src.file_organizer import FileOrganizer
        
        organizer = FileOrganizer(base_output_dir=temp_output_dir)
        
        # Test with special characters
        episode = Episode(
            title="Episode: AI & Machine Learning (Part 1/2)",
            audio_url="https://example.com/episode.mp3",
            guid="guid-123",
            published_date=datetime(2024, 6, 9)
        )
        episode.podcast_name = "Tech Talk: The Podcast"
        
        output_path = organizer.get_output_path(episode)
        
        # Filename should be sanitized
        assert ":" not in output_path.name
        assert "/" not in output_path.name
        assert "&" not in output_path.name
        assert output_path.suffix == ".vtt"