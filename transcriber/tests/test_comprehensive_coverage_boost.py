"""Comprehensive tests to boost coverage to 25% by testing multiple modules."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from datetime import datetime, timedelta
import asyncio

from src.config import Config
from src.utils.logging import get_logger, setup_logging
from src.utils.batch_progress import BatchProgressTracker
from src.utils.progress import ProgressBar
from src.feed_parser import parse_feed, Episode, PodcastMetadata
from src.file_organizer import FileOrganizer
from src.metadata_index import MetadataIndex
from src.vtt_generator import VTTGenerator
from src.speaker_identifier import SpeakerIdentifier
from src.transcription_processor import TranscriptionProcessor
from src.gemini_client import RateLimitedGeminiClient
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.checkpoint_recovery import CheckpointManager, CheckpointError
from src.key_rotation_manager import KeyRotationManager
from src.retry_wrapper import RetryWrapper, RetryConfig
from src.orchestrator import TranscriptionOrchestrator


class TestCoreUtilities:
    """Test core utility modules."""
    
    def test_logging_setup(self, tmp_path):
        """Test logging setup and configuration."""
        log_dir = tmp_path / "logs"
        
        # Test setup with custom directory
        setup_logging(
            log_level="DEBUG",
            log_dir=str(log_dir),
            log_to_console=True,
            log_format="simple"
        )
        
        assert log_dir.exists()
        
        # Test getting logger
        logger = get_logger("test_module")
        assert logger is not None
        
        # Test logging
        logger.info("Test message")
        logger.debug("Debug message")
        logger.warning("Warning message")
        logger.error("Error message")
    
    def test_batch_progress_tracker(self):
        """Test batch progress tracking."""
        tracker = BatchProgressTracker(total_items=10, batch_size=3)
        
        assert tracker.total_items == 10
        assert tracker.batch_size == 3
        assert tracker.completed_items == 0
        
        # Process batches
        tracker.update_batch(3)
        assert tracker.completed_items == 3
        assert tracker.get_progress_percentage() == 30.0
        
        tracker.update_batch(3)
        assert tracker.completed_items == 6
        assert tracker.get_progress_percentage() == 60.0
        
        # Test time estimates
        estimate = tracker.get_time_estimate()
        assert 'elapsed' in estimate
        assert 'remaining' in estimate
    
    def test_progress_reporters(self):
        """Test different progress reporter implementations."""
        # Console progress bar
        console_bar = ConsoleProgressBar(total=100, desc="Testing")
        console_bar.update(50)
        console_bar.close()
        
        # Log progress reporter
        log_reporter = LogProgressReporter(total=100, desc="Testing")
        log_reporter.update(25)
        log_reporter.set_postfix({"rate": "10 items/s"})
        log_reporter.close()
        
        # Base progress reporter
        base_reporter = ProgressReporter.create(
            total=100,
            desc="Test",
            use_console=False
        )
        assert isinstance(base_reporter, LogProgressReporter)


class TestFeedParserComprehensive:
    """Comprehensive tests for feed parser."""
    
    @pytest.fixture
    def parser(self):
        """Create feed parser instance."""
        config = Config.create_test_config()
        return FeedParser(config)
    
    def test_feed_parser_initialization(self, parser):
        """Test feed parser initialization."""
        assert parser.config is not None
        assert hasattr(parser, 'parse_feed')
    
    @patch('feedparser.parse')
    def test_parse_valid_feed(self, mock_parse, parser):
        """Test parsing valid RSS feed."""
        # Mock feed response
        mock_parse.return_value = {
            'feed': {
                'title': 'Test Podcast',
                'description': 'A test podcast',
                'link': 'https://example.com'
            },
            'entries': [
                {
                    'title': 'Episode 1',
                    'link': 'https://example.com/ep1',
                    'published_parsed': (2024, 1, 1, 0, 0, 0, 0, 1, -1),
                    'enclosures': [{'url': 'https://example.com/ep1.mp3'}]
                }
            ]
        }
        
        result = parser.parse_feed('https://example.com/feed.xml')
        
        assert result['title'] == 'Test Podcast'
        assert len(result['episodes']) == 1
        assert result['episodes'][0]['title'] == 'Episode 1'
    
    def test_parse_invalid_feed(self, parser):
        """Test parsing invalid feed URL."""
        with pytest.raises(FeedParserError):
            parser.parse_feed('https://invalid-url-that-does-not-exist.com/feed')
    
    @patch('feedparser.parse')
    def test_extract_youtube_urls(self, mock_parse, parser):
        """Test extracting YouTube URLs from feed."""
        mock_parse.return_value = {
            'feed': {'title': 'Test'},
            'entries': [
                {
                    'title': 'Episode 1',
                    'description': 'Watch on YouTube: https://youtube.com/watch?v=abc123'
                },
                {
                    'title': 'Episode 2',
                    'link': 'https://youtu.be/xyz789'
                }
            ]
        }
        
        result = parser.parse_feed('https://example.com/feed.xml')
        
        # Should extract YouTube URLs
        assert any('youtube.com' in str(ep) for ep in result['episodes'])


class TestFileOrganizerComprehensive:
    """Comprehensive tests for file organizer."""
    
    @pytest.fixture
    def organizer(self, tmp_path):
        """Create file organizer instance."""
        config = Config.create_test_config()
        config.output.default_dir = str(tmp_path)
        return FileOrganizer(config)
    
    def test_create_directory_structure(self, organizer, tmp_path):
        """Test creating organized directory structure."""
        paths = organizer.create_episode_directory(
            podcast_name="Test Podcast",
            episode_title="Episode 1: Introduction"
        )
        
        assert paths['base'].exists()
        assert paths['audio'].exists()
        assert paths['transcripts'].exists()
        assert paths['metadata'].exists()
    
    def test_sanitize_filename(self, organizer):
        """Test filename sanitization."""
        test_cases = [
            ("Episode: Test?", "Episode Test"),
            ("File/Name\\With<>Chars", "File Name With Chars"),
            ("Name|With*Special:Chars", "Name With Special Chars"),
            ("   Spaces   ", "Spaces")
        ]
        
        for input_name, expected in test_cases:
            result = organizer._sanitize_filename(input_name)
            assert result == expected
    
    def test_organize_files(self, organizer, tmp_path):
        """Test organizing files into structure."""
        # Create test files
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio content")
        
        transcript_file = tmp_path / "test.vtt"
        transcript_file.write_text("transcript content")
        
        # Organize files
        organized = organizer.organize_episode_files(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            audio_file=str(audio_file),
            transcript_file=str(transcript_file)
        )
        
        assert Path(organized['audio']).exists()
        assert Path(organized['transcript']).exists()


class TestGeminiClientComprehensive:
    """Comprehensive tests for Gemini client."""
    
    @pytest.fixture
    def client(self):
        """Create Gemini client instance."""
        config = Config.create_test_config()
        config.gemini.api_keys = ["test-key-1", "test-key-2"]
        return GeminiClient(config)
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_initialization(self, mock_model, mock_configure, client):
        """Test Gemini client initialization."""
        assert client.api_keys == ["test-key-1", "test-key-2"]
        assert client.current_key_index == 0
        mock_configure.assert_called_once()
    
    @patch('google.generativeai.upload_file')
    async def test_upload_audio_file(self, mock_upload, client):
        """Test audio file upload."""
        mock_file = Mock()
        mock_file.state.name = "ACTIVE"
        mock_file.uri = "gemini://test-uri"
        mock_upload.return_value = mock_file
        
        result = await client._upload_audio_file("test.mp3")
        assert result == mock_file
    
    @patch('google.generativeai.GenerativeModel')
    async def test_transcribe_audio(self, mock_model_class, client):
        """Test audio transcription."""
        # Mock model and response
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Test transcription"
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        mock_model_class.return_value = mock_model
        
        # Mock file upload
        with patch.object(client, '_upload_audio_file', new_callable=AsyncMock) as mock_upload:
            mock_file = Mock()
            mock_file.uri = "gemini://test-uri"
            mock_upload.return_value = mock_file
            
            result = await client.transcribe_audio("test.mp3")
            
            assert result['transcription'] == "Test transcription"
            assert result['model_used'] == 'gemini-1.5-flash-002'


class TestMetadataIndexComprehensive:
    """Comprehensive tests for metadata index."""
    
    @pytest.fixture
    def index(self, tmp_path):
        """Create metadata index instance."""
        config = Config.create_test_config()
        config.output.metadata_dir = str(tmp_path)
        return MetadataIndex(config)
    
    def test_add_episode_metadata(self, index):
        """Test adding episode metadata."""
        metadata = {
            'podcast_name': 'Test Podcast',
            'episode_title': 'Episode 1',
            'episode_guid': 'guid-123',
            'audio_file': 'episode1.mp3',
            'transcript_file': 'episode1.vtt',
            'youtube_url': 'https://youtube.com/watch?v=123',
            'transcription_date': datetime.utcnow().isoformat()
        }
        
        index.add_episode(metadata)
        
        # Verify episode was added
        assert 'guid-123' in index.episodes
        assert index.episodes['guid-123']['podcast_name'] == 'Test Podcast'
    
    def test_search_episodes(self, index):
        """Test searching episodes."""
        # Add test episodes
        index.add_episode({
            'episode_guid': '1',
            'podcast_name': 'Tech Podcast',
            'episode_title': 'AI Discussion'
        })
        index.add_episode({
            'episode_guid': '2',
            'podcast_name': 'Science Show',
            'episode_title': 'Physics Talk'
        })
        
        # Search by podcast
        results = index.search_episodes(podcast_name='Tech Podcast')
        assert len(results) == 1
        assert results[0]['episode_guid'] == '1'
        
        # Search by title keyword
        results = index.search_episodes(title_contains='Discussion')
        assert len(results) == 1
        assert results[0]['episode_title'] == 'AI Discussion'
    
    def test_save_and_load_index(self, index, tmp_path):
        """Test saving and loading index."""
        # Add data
        index.add_episode({
            'episode_guid': 'test-123',
            'podcast_name': 'Test Show'
        })
        
        # Save
        index.save_index()
        
        # Create new index and load
        new_index = MetadataIndex(index.config)
        new_index.load_index()
        
        assert 'test-123' in new_index.episodes
        assert new_index.episodes['test-123']['podcast_name'] == 'Test Show'


class TestProgressTrackerComprehensive:
    """Comprehensive tests for progress tracker."""
    
    @pytest.fixture
    def tracker(self, tmp_path):
        """Create progress tracker instance."""
        config = Config.create_test_config()
        config.checkpoint.enabled = True
        config.checkpoint.dir = str(tmp_path / "checkpoints")
        return ProgressTracker(config)
    
    def test_start_episode(self, tracker):
        """Test starting episode tracking."""
        progress = tracker.start_episode(
            episode_guid="test-123",
            total_duration=3600
        )
        
        assert isinstance(progress, TranscriptionProgress)
        assert progress.episode_guid == "test-123"
        assert progress.total_duration == 3600
        assert progress.status == "in_progress"
    
    def test_update_progress(self, tracker):
        """Test updating progress."""
        progress = tracker.start_episode("test-123", 3600)
        
        # Update progress
        tracker.update_progress("test-123", processed_duration=1800)
        
        updated = tracker.get_progress("test-123")
        assert updated.processed_duration == 1800
        assert updated.percentage_complete == 50.0
    
    def test_checkpoint_saving(self, tracker):
        """Test checkpoint saving."""
        progress = tracker.start_episode("test-123", 3600)
        tracker.update_progress("test-123", processed_duration=1800)
        
        # Save checkpoint
        tracker.save_checkpoint("test-123")
        
        # Verify checkpoint file exists
        checkpoint_file = Path(tracker.checkpoint_dir) / "test-123.json"
        assert checkpoint_file.exists()
    
    def test_resume_from_checkpoint(self, tracker):
        """Test resuming from checkpoint."""
        # Create checkpoint
        progress = tracker.start_episode("test-123", 3600)
        tracker.update_progress("test-123", processed_duration=1800)
        tracker.save_checkpoint("test-123")
        
        # Create new tracker and resume
        new_tracker = ProgressTracker(tracker.config)
        resumed = new_tracker.resume_episode("test-123")
        
        assert resumed is not None
        assert resumed.processed_duration == 1800
        assert resumed.percentage_complete == 50.0


class TestOrchestratorIntegration:
    """Integration tests for the orchestrator."""
    
    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance with mocked dependencies."""
        config = Config.create_test_config()
        config.output.default_dir = str(tmp_path)
        config.gemini.api_keys = ["test-key"]
        config.youtube_search.enabled = True
        
        with patch('src.orchestrator.GeminiClient'), \
             patch('src.orchestrator.YouTubeSearcher'), \
             patch('src.orchestrator.FileOrganizer'), \
             patch('src.orchestrator.VTTGenerator'), \
             patch('src.orchestrator.MetadataIndex'), \
             patch('src.orchestrator.ProgressTracker'), \
             patch('src.orchestrator.SpeakerIdentifier'):
            
            return TranscriptionOrchestrator(config)
    
    @pytest.mark.asyncio
    async def test_process_single_episode(self, orchestrator):
        """Test processing a single episode."""
        episode = {
            'title': 'Test Episode',
            'guid': 'test-123',
            'audio_url': 'https://example.com/episode.mp3'
        }
        
        # Mock dependencies
        orchestrator.youtube_searcher.search_youtube_url = AsyncMock(
            return_value="https://youtube.com/watch?v=123"
        )
        orchestrator.gemini_client.transcribe_audio = AsyncMock(
            return_value={'transcription': 'Test transcript'}
        )
        orchestrator.file_organizer.organize_episode_files = Mock(
            return_value={'transcript': 'path/to/transcript.vtt'}
        )
        
        result = await orchestrator.process_episode(episode, "Test Podcast")
        
        assert result['success'] == True
        assert result['youtube_url'] == "https://youtube.com/watch?v=123"
    
    @pytest.mark.asyncio
    async def test_process_feed(self, orchestrator):
        """Test processing entire feed."""
        feed_data = {
            'title': 'Test Podcast',
            'episodes': [
                {'title': 'Episode 1', 'guid': '1', 'audio_url': 'url1'},
                {'title': 'Episode 2', 'guid': '2', 'audio_url': 'url2'}
            ]
        }
        
        # Mock episode processing
        orchestrator.process_episode = AsyncMock(
            return_value={'success': True}
        )
        
        results = await orchestrator.process_feed(
            feed_url="https://example.com/feed.xml",
            feed_data=feed_data
        )
        
        assert len(results) == 2
        assert all(r['success'] for r in results)


# Run this to get comprehensive coverage
if __name__ == "__main__":
    pytest.main([__file__, "-v"])