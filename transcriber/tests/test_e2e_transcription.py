"""End-to-end test for the podcast transcription pipeline with audio upload."""

import pytest
import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open, Mock

from src.feed_parser import parse_feed
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.gemini_client import RateLimitedGeminiClient
from src.vtt_generator import VTTGenerator
from src.file_organizer import FileOrganizer
from src.orchestrator import TranscriptionOrchestrator
from src.config import Config


@pytest.mark.integration
@pytest.mark.e2e
class TestE2ETranscriptionWithAudioUpload:
    """Test complete transcription pipeline including audio file upload."""
    
    @pytest.fixture
    def mock_audio_file(self, tmp_path):
        """Create a mock audio file."""
        audio_file = tmp_path / "test_audio.mp3"
        # Create a small fake MP3 file (just some bytes)
        audio_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 1024)
        return str(audio_file)
    
    @pytest.fixture
    def mock_rss_response(self):
        """Create a mock RSS feed response."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
            <channel>
                <title>E2E Test Podcast</title>
                <description>Testing end-to-end transcription</description>
                <link>https://example.com/podcast</link>
                <language>en</language>
                <itunes:author>E2E Test Host</itunes:author>
                <itunes:image href="https://example.com/logo.jpg"/>
                <item>
                    <title>Test Episode 1</title>
                    <guid>e2e-test-ep1</guid>
                    <description>This is a test episode for E2E testing</description>
                    <pubDate>Wed, 01 Jun 2025 12:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/audio/test-ep1.mp3" type="audio/mpeg" length="5242880"/>
                    <itunes:duration>30:00</itunes:duration>
                </item>
            </channel>
        </rss>
        """
    
    @pytest.fixture
    def mock_vtt_transcript(self):
        """Mock VTT transcript response from Gemini."""
        return """WEBVTT

NOTE
Podcast: E2E Test Podcast
Episode: Test Episode 1
Date: 2025-06-01

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Welcome to E2E Test Podcast.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>I'm your host, and today we're testing the transcription pipeline.

00:00:10.000 --> 00:00:15.000
<v SPEAKER_2>Thanks for having me. This is exciting!

00:00:15.000 --> 00:00:20.000
<v SPEAKER_1>Let's make sure everything works end-to-end."""
    
    @pytest.fixture
    def mock_speaker_mapping(self):
        """Mock speaker identification response."""
        return {
            "SPEAKER_1": "E2E Test Host",
            "SPEAKER_2": "Guest Speaker"
        }
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_audio_upload(self, tmp_path, mock_audio_file, 
                                                  mock_rss_response, mock_vtt_transcript,
                                                  mock_speaker_mapping):
        """Test the complete pipeline including audio download and upload to Gemini."""
        # Setup directories
        data_dir = tmp_path / "data"
        config_dir = tmp_path / "config"
        data_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        
        # Create config file
        config_file = config_dir / "test_config.yaml"
        config_content = {
            "output": {
                "default_dir": str(data_dir / "transcripts"),
                "sanitize_filenames": True
            },
            "processing": {
                "max_episodes": 10,
                "skip_existing": True
            },
            "logging": {
                "level": "INFO",
                "directory": str(data_dir / "logs")
            }
        }
        
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_content, f)
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'test_key_1',
            'PODCAST_CONFIG_PATH': str(config_file)
        }):
            # Mock feedparser
            import feedparser
            mock_feed = Mock()
            mock_feed.bozo = False
            mock_feed.feed = {
                'title': 'E2E Test Podcast',
                'description': 'Testing end-to-end transcription',
                'link': 'https://example.com/podcast',
                'language': 'en',
                'itunes_author': 'E2E Test Host',
                'image': {'href': 'https://example.com/logo.jpg'}
            }
            mock_feed.entries = [{
                'title': 'Test Episode 1',
                'id': 'e2e-test-ep1',
                'description': 'This is a test episode for E2E testing',
                'published': 'Wed, 01 Jun 2025 12:00:00 GMT',
                'published_parsed': (2025, 6, 1, 12, 0, 0, 2, 152, 0),
                'link': 'https://example.com/episodes/1',
                'enclosures': [{
                    'href': 'https://example.com/audio/test-ep1.mp3',
                    'type': 'audio/mpeg',
                    'length': '5242880'
                }],
                'itunes_duration': '30:00'
            }]
            
            with patch('src.feed_parser.feedparser.parse', return_value=mock_feed):
                # Mock audio file download for Gemini client
                with patch('urllib.request.urlopen') as mock_urlopen:
                    # Mock audio download
                    mock_audio_resp = Mock()
                    with open(mock_audio_file, 'rb') as f:
                        audio_content = f.read()
                    mock_audio_resp.read.return_value = audio_content
                    mock_audio_resp.__enter__ = Mock(return_value=mock_audio_resp)
                    mock_audio_resp.__exit__ = Mock(return_value=None)
                    
                    mock_urlopen.return_value = mock_audio_resp
                    
                    # Mock Gemini API
                    mock_uploaded_file = Mock()
                    mock_uploaded_file.name = "uploaded_test_audio.mp3"
                    
                    with patch('src.gemini_client.genai.upload_file') as mock_upload:
                        mock_upload.return_value = mock_uploaded_file
                        
                        with patch('src.gemini_client.genai.delete_file') as mock_delete:
                            with patch('src.gemini_client.genai.configure'):
                                # Mock Gemini model
                                mock_model = MagicMock()
                                mock_transcript_resp = Mock()
                                mock_transcript_resp.text = mock_vtt_transcript
                                
                                mock_speaker_resp = Mock()
                                mock_speaker_resp.text = json.dumps(mock_speaker_mapping)
                                
                                mock_model.generate_content_async = AsyncMock(
                                    side_effect=[mock_transcript_resp, mock_speaker_resp]
                                )
                                
                                with patch('src.gemini_client.genai.GenerativeModel', 
                                         return_value=mock_model):
                                    # Initialize orchestrator with config
                                    # Patch Config to use our test config
                                    with patch('src.orchestrator.Config') as mock_config_cls:
                                        test_config = Config(config_file=str(config_file))
                                        mock_config_cls.return_value = test_config
                                        
                                        orchestrator = TranscriptionOrchestrator(
                                            output_dir=Path(test_config.output.default_dir),
                                            data_dir=data_dir
                                        )
                                    
                                    # Process the feed
                                    await orchestrator.process_feed("https://example.com/feed.xml")
                                    
                                    # Verify audio was downloaded and uploaded
                                    assert mock_upload.called
                                    upload_call = mock_upload.call_args[0][0]
                                    assert upload_call.endswith('.mp3')
                                    
                                    # Verify file was deleted after use
                                    assert mock_delete.called
                                    assert mock_delete.call_args[0][0] == "uploaded_test_audio.mp3"
                                    
                                    # Verify output files were created
                                    transcript_dir = data_dir / "transcripts" / "E2E_Test_Podcast"
                                    assert transcript_dir.exists()
                                    
                                    vtt_files = list(transcript_dir.glob("*.vtt"))
                                    assert len(vtt_files) == 1
                                    
                                    # Verify VTT content
                                    vtt_file = vtt_files[0]
                                    content = vtt_file.read_text()
                                    
                                    # Check VTT structure
                                    assert "WEBVTT" in content
                                    assert "NOTE" in content
                                    assert "E2E Test Podcast" in content
                                    assert "Test Episode 1" in content
                                    
                                    # Check speaker replacements
                                    assert "E2E Test Host" in content
                                    assert "Guest Speaker" in content
                                    assert "SPEAKER_1" not in content  # Should be replaced
                                    assert "SPEAKER_2" not in content  # Should be replaced
                                    
                                    # Verify manifest
                                    manifest_file = data_dir / "transcripts" / "manifest.json"
                                    assert manifest_file.exists()
                                    
                                    with open(manifest_file) as f:
                                        manifest = json.load(f)
                                    
                                    assert len(manifest["episodes"]) == 1
                                    episode = manifest["episodes"][0]
                                    assert episode["title"] == "Test Episode 1"
                                    assert episode["podcast_name"] == "E2E Test Podcast"
                                    assert "E2E Test Host" in episode["speakers"]
                                    assert "Guest Speaker" in episode["speakers"]
                                    
                                    # Verify progress tracking
                                    progress_file = data_dir / ".progress.json"
                                    assert progress_file.exists()
                                    
                                    with open(progress_file) as f:
                                        progress = json.load(f)
                                    
                                    assert len(progress["episodes"]) == 1
                                    ep_progress = list(progress["episodes"].values())[0]
                                    assert ep_progress["status"] == "completed"
                                    assert ep_progress["guid"] == "e2e-test-ep1"
    
    @pytest.mark.asyncio
    async def test_pipeline_audio_download_failure(self, tmp_path, mock_rss_response):
        """Test pipeline handling when audio download fails."""
        # Setup directories
        data_dir = tmp_path / "data"
        config_dir = tmp_path / "config"
        data_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        
        # Create config
        config_file = config_dir / "test_config.yaml"
        config_content = {
            "output": {
                "default_dir": str(data_dir / "transcripts")
            }
        }
        
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_content, f)
        
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'test_key_1',
            'PODCAST_CONFIG_PATH': str(config_file)
        }):
            # Mock feedparser
            with patch('urllib.request.urlopen') as mock_urlopen:
                # Mock RSS response
                mock_rss_resp = Mock()
                mock_rss_resp.read.return_value = mock_rss_response.encode('utf-8')
                mock_rss_resp.__enter__ = Mock(return_value=mock_rss_resp)
                mock_rss_resp.__exit__ = Mock(return_value=None)
                
                # Mock audio download failure
                def urlopen_side_effect(request, timeout=None):
                    if hasattr(request, 'full_url'):
                        url = request.full_url
                    else:
                        url = request
                    
                    if 'feed.xml' in url or 'rss' in url:
                        return mock_rss_resp
                    elif '.mp3' in url:
                        from urllib.error import HTTPError
                        raise HTTPError(url, 404, "Not Found", {}, None)
                    else:
                        raise Exception(f"Unexpected URL: {url}")
                
                mock_urlopen.side_effect = urlopen_side_effect
                
                with patch('src.gemini_client.genai.configure'):
                    mock_model = MagicMock()
                    with patch('src.gemini_client.genai.GenerativeModel', return_value=mock_model):
                        # Initialize orchestrator with config
                        with patch('src.orchestrator.Config') as mock_config_cls:
                            test_config = Config(config_file=str(config_file))
                            mock_config_cls.return_value = test_config
                            
                            orchestrator = TranscriptionOrchestrator(
                                output_dir=Path(test_config.output.default_dir),
                                data_dir=data_dir
                            )
                        
                        # Process should handle the error gracefully
                        await orchestrator.process_feed("https://example.com/feed.xml")
                        
                        # Verify episode was marked as failed
                        progress_file = data_dir / ".progress.json"
                        assert progress_file.exists()
                        
                        with open(progress_file) as f:
                            progress = json.load(f)
                        
                        assert len(progress["episodes"]) == 1
                        ep_progress = list(progress["episodes"].values())[0]
                        assert ep_progress["status"] == "failed"
                        assert "404" in ep_progress["error_message"]