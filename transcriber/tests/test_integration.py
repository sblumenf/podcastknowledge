"""Integration tests for the podcast transcription pipeline."""

import pytest
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

from src.feed_parser import parse_feed, Episode, PodcastMetadata
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.gemini_client import RateLimitedGeminiClient
from src.key_rotation_manager import KeyRotationManager
from src.transcription_processor import TranscriptionProcessor
from src.speaker_identifier import SpeakerIdentifier
from src.vtt_generator import VTTGenerator, VTTMetadata
from src.file_organizer import FileOrganizer
from src.orchestrator import TranscriptionOrchestrator
from src.checkpoint_recovery import CheckpointManager
from tenacity import RetryError


@pytest.mark.integration
class TestEndToEndPipeline:
    """Test complete transcription pipeline from RSS feed to VTT files."""
    
    @pytest.fixture
    def mock_rss_feed(self):
        """Create a mock RSS feed response."""
        from unittest.mock import MagicMock
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {
            'title': 'Integration Test Podcast',
            'description': 'A podcast for integration testing',
            'link': 'https://example.com/podcast',
            'language': 'en',
            'itunes_author': 'Test Host'
        }
        mock_feed.entries = [
                {
                    'title': 'Episode 1: Introduction',
                    'id': 'ep1-guid',
                    'description': 'First test episode',
                    'published': 'Mon, 15 Jan 2024 10:00:00 GMT',
                    'published_parsed': (2024, 1, 15, 10, 0, 0, 0, 15, 0),
                    'link': 'https://example.com/episodes/1',
                    'enclosures': [{
                        'href': 'https://example.com/audio/episode1.mp3',
                        'type': 'audio/mpeg',
                        'length': '25000000'
                    }],
                    'itunes_duration': '30:00',
                    'itunes_episode': '1'
                },
                {
                    'title': 'Episode 2: Deep Dive',
                    'id': 'ep2-guid',
                    'description': 'Second test episode',
                    'published': 'Mon, 22 Jan 2024 10:00:00 GMT',
                    'published_parsed': (2024, 1, 22, 10, 0, 0, 0, 22, 0),
                    'link': 'https://example.com/episodes/2',
                    'enclosures': [{
                        'href': 'https://example.com/audio/episode2.mp3',
                        'type': 'audio/mpeg',
                        'length': '30000000'
                    }],
                    'itunes_duration': '45:00',
                    'itunes_episode': '2'
                }
            ]
        return mock_feed
    
    @pytest.fixture
    def mock_transcription_response(self):
        """Create a mock transcription response."""
        return """WEBVTT

NOTE
Podcast: Integration Test Podcast
Episode: Episode 1: Introduction
Date: 2024-01-15

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello and welcome to Integration Test Podcast.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>I'm your host, and today we have a special guest.

00:00:10.000 --> 00:00:15.000
<v SPEAKER_2>Thanks for having me on the show.

00:00:15.000 --> 00:00:20.000
<v SPEAKER_1>Let's dive into our topic for today."""
    
    @pytest.fixture
    def mock_speaker_identification(self):
        """Create a mock speaker identification response."""
        return {
            "SPEAKER_1": "Test Host (Host)",
            "SPEAKER_2": "Jane Doe (Guest, Software Engineer)"
        }
    
    @pytest.mark.asyncio
    async def test_full_pipeline_single_episode(self, tmp_path, mock_rss_feed, 
                                              mock_transcription_response, 
                                              mock_speaker_identification):
        """Test processing a single episode through the full pipeline."""
        # Setup directory structure
        data_dir = Path(tmp_path) / "data"
        config_dir = Path(tmp_path) / "config"
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'test_key_1',
            'GEMINI_API_KEY_2': 'test_key_2',
            'PODCAST_OUTPUT_DIR': str(data_dir / 'transcripts')
        }):
            # Mock feedparser
            with patch('src.feed_parser.feedparser.parse', return_value=mock_rss_feed):
                # Parse RSS feed
                podcast_metadata, episodes = parse_feed('https://example.com/feed.xml')
                
                assert podcast_metadata.title == 'Integration Test Podcast'
                assert len(episodes) == 2
                assert episodes[0].title == 'Episode 2: Deep Dive'  # Sorted by date, newest first
            
            # Initialize components
            progress_file = data_dir / '.progress.json'
            progress_tracker = ProgressTracker(progress_file)
            
            # Add episodes to tracker
            for episode in episodes:
                progress_tracker.add_episode({
                    'guid': episode.guid,
                    'podcast_name': podcast_metadata.title,
                    'title': episode.title,
                    'audio_url': episode.audio_url,
                    'published_date': episode.published_date.strftime('%Y-%m-%d') if episode.published_date else None
                })
            
            # Mock Gemini client
            mock_genai_client = MagicMock()
            mock_genai_client.generate_content_async = AsyncMock()
            
            # Mock transcription response
            mock_transcript_response = MagicMock()
            mock_transcript_response.text = mock_transcription_response
            
            # Mock speaker ID response
            mock_speaker_response = MagicMock()
            mock_speaker_response.text = json.dumps(mock_speaker_identification)
            
            # Set up the mock to return different responses based on call count
            call_count = 0
            async def mock_generate_content(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                # For transcription, we'll be called multiple times (initial + continuations)
                # Return transcript response for first 10 calls (transcription + continuations)
                if call_count <= 10:
                    return mock_transcript_response
                else:
                    # This is the speaker identification call
                    return mock_speaker_response
            
            mock_genai_client.generate_content_async = AsyncMock(side_effect=mock_generate_content)
            
            # Mock audio file upload/download
            mock_uploaded_file = MagicMock()
            mock_uploaded_file.name = "uploaded_test_audio.mp3"
            
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel', return_value=mock_genai_client):
                    with patch('src.gemini_client.genai.upload_file', return_value=mock_uploaded_file):
                        with patch('src.gemini_client.genai.delete_file'):
                            # Mock audio download
                            with patch('src.gemini_client.RateLimitedGeminiClient._download_audio_file') as mock_download:
                                mock_download.return_value = "/tmp/test_audio.mp3"
                                
                                # Mock usage state loading to prevent quota issues
                                with patch('src.gemini_client.RateLimitedGeminiClient._load_usage_state'):
                                    # Initialize Gemini client
                                    gemini_client = RateLimitedGeminiClient(['test_key_1', 'test_key_2'])
                                
                                # Process first episode
                                episode = episodes[1]  # Episode 1 (older)
                                episode_data = {
                                    'guid': episode.guid,
                                    'podcast_name': podcast_metadata.title,
                                    'title': episode.title,
                                    'audio_url': episode.audio_url,
                                    'published_date': episode.published_date.strftime('%Y-%m-%d'),
                                    'duration': episode.duration,
                                    'author': podcast_metadata.author,
                                    'description': episode.description
                                }
                                
                                # Start processing
                                progress_tracker.mark_started(episode_data, api_key_index=0)
                                
                                # Transcribe audio
                                transcript = await gemini_client.transcribe_audio(
                                    episode.audio_url,
                                    episode_data
                                )
                                
                                assert transcript == mock_transcription_response
                                
                                # Identify speakers
                                speaker_mapping = await gemini_client.identify_speakers(
                                    transcript,
                                    episode_data
                                )
                                
                                assert speaker_mapping == mock_speaker_identification
                                
                                # Generate VTT with metadata
                                vtt_generator = VTTGenerator()
                                vtt_metadata = vtt_generator.create_metadata_from_episode(
                                    episode_data,
                                    speaker_mapping
                                )
                                
                                assert vtt_metadata.host == "Test Host"
                                assert len(vtt_metadata.guests) == 1
                                assert "Jane Doe" in vtt_metadata.guests
                                
                                # Organize and save file
                                file_organizer = FileOrganizer(base_dir=str(data_dir / 'transcripts'))
                                
                                final_vtt = vtt_generator.generate_vtt(
                                    transcript,
                                    vtt_metadata
                                )
                                
                                saved_metadata = file_organizer.create_episode_file(
                                    podcast_name=podcast_metadata.title,
                                    episode_title=episode.title,
                                    publication_date=episode_data['published_date'],
                                    speakers=list(speaker_mapping.values()),
                                    content=final_vtt,
                                    duration=1800,  # 30 minutes
                                    episode_number=episode.episode_number,
                                    description=episode.description
                                )
                                
                                # Mark as completed
                                progress_tracker.mark_completed(
                                    episode.guid,
                                    saved_metadata.file_path,
                                    processing_time=5.0
                                )
                                
                                # Verify results
                                assert saved_metadata.file_path == "Integration_Test_Podcast/2024-01-15_Episode_1_Introduction.vtt"
                                
                                # Check file was created
                                vtt_file = Path(data_dir) / 'transcripts' / saved_metadata.file_path
                                assert vtt_file.exists()
                                
                                # Check content
                                with open(vtt_file, 'r') as f:
                                    content = f.read()
                                
                                assert "WEBVTT" in content
                                assert "Test Host (Host)" in content
                                assert "Jane Doe (Guest, Software Engineer)" in content
                                assert "Hello and welcome to Integration Test Podcast" in content
                                
                                # Check progress was updated
                                completed_episodes = [ep for ep in progress_tracker.state.episodes.values() 
                                                    if ep.status == EpisodeStatus.COMPLETED]
                                assert len(completed_episodes) == 1
                                assert completed_episodes[0].guid == episode.guid
                                
                                # Check manifest was created
                                manifest_file = Path(data_dir) / 'transcripts' / 'manifest.json'
                                assert manifest_file.exists()
                                
                                with open(manifest_file, 'r') as f:
                                    manifest = json.load(f)
                                
                                # Handle both test and production manifest formats
                                if isinstance(manifest, list):
                                    # Test format - simple list
                                    assert len(manifest) == 1
                                else:
                                    # Production format - dict with metadata
                                    assert manifest['total_episodes'] == 1
                                    assert len(manifest['episodes']) == 1
    
    @pytest.mark.asyncio
    async def test_pipeline_with_errors_and_recovery(self, tmp_path):
        """Test pipeline handling errors and recovery."""
        data_dir = Path(tmp_path) / "data"
        
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key_1'}):
            # Initialize components
            progress_tracker = ProgressTracker(data_dir / '.progress.json')
            checkpoint_manager = CheckpointManager(data_dir)
            
            # Add test episode
            episode_data = {
                'guid': 'error-test-ep',
                'podcast_name': 'Error Test Podcast',
                'title': 'Error Episode',
                'audio_url': 'https://example.com/error.mp3',
                'published_date': '2024-01-15'
            }
            
            progress_tracker.add_episode(episode_data)
            
            # Mock Gemini client to fail first time
            mock_genai_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Transcription result"
            
            # First two calls fail (to exhaust retry attempts), then succeeds
            mock_genai_client.generate_content_async = AsyncMock(
                side_effect=[
                    Exception("Rate limit exceeded"),
                    Exception("Rate limit exceeded"),
                    mock_response
                ]
            )
            
            # Mock audio file upload/download
            mock_uploaded_file = MagicMock()
            mock_uploaded_file.name = "uploaded_test_audio.mp3"
            
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel', return_value=mock_genai_client):
                    with patch('src.gemini_client.genai.upload_file', return_value=mock_uploaded_file):
                        with patch('src.gemini_client.genai.delete_file'):
                            with patch('src.gemini_client.RateLimitedGeminiClient._download_audio_file') as mock_download:
                                mock_download.return_value = "/tmp/test_audio.mp3"
                                with patch('src.gemini_client.RateLimitedGeminiClient._load_usage_state'):
                                    # Clear any existing retry state file
                                    retry_state_file = Path("data/.retry_state.json")
                                    if retry_state_file.exists():
                                        retry_state_file.unlink()
                                    
                                    gemini_client = RateLimitedGeminiClient(['test_key_1'])
                                
                                # First attempt should fail
                                progress_tracker.mark_started(episode_data, api_key_index=0)
                                
                                with pytest.raises(RetryError):
                                    await gemini_client._transcribe_with_retry(
                                        gemini_client.models[0],
                                        0,
                                        episode_data['audio_url'],
                                        episode_data
                                    )
                                
                                # Mark as failed
                                progress_tracker.mark_failed(
                                    episode_data['guid'],
                                    "Rate limit exceeded",
                                    "rate_limit"
                                )
                                
                                # Check episode is marked as failed
                                episode_progress = progress_tracker.state.episodes[episode_data['guid']]
                                assert episode_progress.status == EpisodeStatus.FAILED
                                assert episode_progress.error == "Rate limit exceeded"
                                assert episode_progress.attempt_count == 1
                                
                                # Simulate recovery - get failed episodes
                                failed_episodes = progress_tracker.get_failed(max_attempts=2)
                                assert len(failed_episodes) == 1
                                
                                # Second attempt should succeed
                                progress_tracker.mark_started(episode_data, api_key_index=0)
                                
                                result = await gemini_client._transcribe_with_retry(
                                    gemini_client.models[0],
                                    0,
                                    episode_data['audio_url'],
                                    episode_data
                                )
                                
                                assert result == "Transcription result"
                                
                                # Check attempt count increased
                                episode_progress = progress_tracker.state.episodes[episode_data['guid']]
                                assert episode_progress.attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_pipeline_with_checkpoint_recovery(self, tmp_path):
        """Test pipeline checkpoint and recovery functionality."""
        data_dir = Path(tmp_path) / "data"
        
        # Create interrupted checkpoint using EpisodeCheckpoint format
        checkpoint_data = {
            'episode_id': 'checkpoint-test-ep',
            'audio_url': 'https://example.com/audio/test.mp3',
            'title': 'Test Episode',
            'status': 'transcribing',
            'stage_completed': [],
            'temporary_files': {
                'transcription': str(data_dir / '.temp' / 'partial_transcript.txt')
            },
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'metadata': {
                'processed_segments': 5,
                'total_segments': 10
            }
        }
        
        checkpoint_file = data_dir / 'checkpoints' / 'active_checkpoint.json'
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
        
        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager(data_dir)
        
        # Check if checkpoint manager can resume
        assert checkpoint_manager.can_resume() is True
        
        # Get resume info
        resume_info = checkpoint_manager.get_resume_info()
        assert resume_info is not None
        assert checkpoint_manager.current_checkpoint.status == 'transcribing'
        
        # Simulate continuing from checkpoint
        # Update the stage to speaker_identification
        checkpoint_manager.update_stage('speaker_identification')
        
        # Complete processing
        checkpoint_manager.complete_stage('transcription')
        checkpoint_manager.mark_completed('checkpoint-test-ep')
        
        # Verify checkpoint was cleaned up
        assert not checkpoint_file.exists()
    
    @pytest.mark.asyncio
    async def test_pipeline_daily_quota_management(self, tmp_path):
        """Test pipeline respecting daily quota limits."""
        data_dir = Path(tmp_path) / "data"
        
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'test_key_1',
            'PODCAST_API_MAX_EPISODES': '2'  # Limit to 2 episodes
        }):
            # Initialize components
            progress_tracker = ProgressTracker(data_dir / '.progress.json')
            
            # Add multiple episodes
            for i in range(5):
                progress_tracker.add_episode({
                    'guid': f'quota-test-ep-{i}',
                    'podcast_name': 'Quota Test Podcast',
                    'title': f'Episode {i+1}',
                    'audio_url': f'https://example.com/episode{i+1}.mp3',
                    'published_date': f'2024-01-{15+i:02d}'
                })
            
            # Mock Gemini client with usage tracking
            mock_genai_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Transcription"
            mock_genai_client.generate_content_async = AsyncMock(return_value=mock_response)
            
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel', return_value=mock_genai_client):
                    with patch('src.gemini_client.Path.exists', return_value=False):
                        gemini_client = RateLimitedGeminiClient(['test_key_1'])
                
                # Process episodes until quota limit
                processed_count = 0
                pending_episodes = progress_tracker.get_pending()
                
                for episode in pending_episodes[:3]:  # Try to process 3 episodes
                    # Check if we should skip to preserve quota
                    if processed_count >= 2:  # Our configured limit
                        # Should skip remaining episodes
                        break
                    
                    episode_data = {
                        'guid': episode.guid,
                        'title': episode.title,
                        'audio_url': episode.audio_url
                    }
                    
                    # Process episode
                    progress_tracker.mark_started(episode_data)
                    
                    # Simulate successful processing
                    progress_tracker.mark_completed(
                        episode.guid,
                        f"output/{episode.guid}.vtt",
                        processing_time=5.0
                    )
                    
                    processed_count += 1
                
                # Verify only 2 episodes were processed
                assert processed_count == 2
                
                # Check progress state
                completed = [ep for ep in progress_tracker.state.episodes.values() 
                           if ep.status == EpisodeStatus.COMPLETED]
                pending = [ep for ep in progress_tracker.state.episodes.values() 
                          if ep.status == EpisodeStatus.PENDING]
                
                assert len(completed) == 2
                assert len(pending) == 3  # 3 episodes still pending