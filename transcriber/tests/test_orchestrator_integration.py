"""Integration tests for the orchestrator and CLI components."""

import pytest
import asyncio
import json
import os
import sys
import gc
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
from argparse import Namespace

from src.orchestrator import TranscriptionOrchestrator
from src.cli import main, parse_arguments as parse_args
from src.config import Config
from src.progress_tracker import ProgressTracker


@pytest.mark.integration
@pytest.mark.timeout(120)  # 2 minute timeout for orchestrator integration tests
class TestOrchestratorIntegration:
    """Test the transcription orchestrator with all components."""
    
    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration."""
        with patch('src.config.get_config') as mock_get_config:
            config = Config()
            config.output.default_dir = str(Path(tmp_path) / 'transcripts')
            config.api.max_episodes_per_day = 5
            config.processing.enable_progress_bar = True
            config.development.dry_run = False
            mock_get_config.return_value = config
            yield config
    
    @pytest.fixture
    def mock_feed_episodes(self):
        """Create mock feed episodes."""
        from src.feed_parser import Episode, PodcastMetadata
        from datetime import datetime
        
        podcast = PodcastMetadata(
            title="Test Podcast",
            description="A test podcast",
            author="Test Host"
        )
        
        episodes = [
            Episode(
                title=f"Episode {i}",
                audio_url=f"https://example.com/episode{i}.mp3",
                guid=f"ep{i}-guid",
                description=f"Episode {i} description",
                published_date=datetime(2024, 1, i+10),
                duration="30:00",
                episode_number=i
            )
            for i in range(1, 4)
        ]
        
        return podcast, episodes
    
    @pytest.mark.asyncio
    async def test_orchestrator_full_workflow(self, tmp_path, mock_config, mock_feed_episodes):
        """Test orchestrator processing multiple episodes."""
        podcast_metadata, episodes = mock_feed_episodes
        
        # Mock dependencies
        mock_feed_parser = MagicMock()
        mock_feed_parser.parse_feed.return_value = (podcast_metadata, episodes)
        
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Welcome to the test."""
        
        mock_speaker_response = MagicMock()
        mock_speaker_response.text = json.dumps({
            "SPEAKER_1": "Test Host (Host)"
        })
        
        mock_gemini_client = MagicMock()
        mock_gemini_client.api_keys = ['test_key_1', 'test_key_2']  # Mock has 2 keys
        mock_gemini_client.transcribe_audio = AsyncMock(return_value=mock_gemini_response.text)
        mock_gemini_client.identify_speakers = AsyncMock(
            return_value={"SPEAKER_1": "Test Host (Host)"}
        )
        mock_gemini_client.get_usage_summary.return_value = {
            'key_1': {'requests_today': 0, 'requests_remaining': 25},
            'key_2': {'requests_today': 0, 'requests_remaining': 25}
        }
        
        # Mock the transcription processor
        mock_transcription_processor = MagicMock()
        mock_transcription_processor.transcribe_episode = AsyncMock(return_value=mock_gemini_response.text)
        
        # Mock the key rotation manager to return proper tuple
        mock_key_rotation_manager = MagicMock()
        mock_key_rotation_manager.get_next_key.return_value = ('test_key_1', 0)
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager') as mock_rotation:
                    mock_rotation.return_value = mock_key_rotation_manager
                    
                    # Patch ProgressTracker to use temp directory
                    with patch('src.orchestrator.ProgressTracker') as mock_progress_class:
                        mock_progress_tracker = MagicMock()
                        mock_progress_tracker.state.episodes = {}
                        mock_progress_class.return_value = mock_progress_tracker
                        
                        # Create orchestrator
                        orchestrator = TranscriptionOrchestrator(
                            output_dir=Path(mock_config.output.default_dir),
                            enable_checkpoint=True,
                            resume=False
                        )
                        
                        # Patch the transcription processor on the orchestrator
                        orchestrator.transcription_processor = mock_transcription_processor
                    
                        # Run processing
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=2  # Process only 2 episodes
                        )
                    
                        # Extract counts from results
                        success_count = results.get('processed', 0)
                        failure_count = results.get('failed', 0)
                        
                        # Verify results
                        assert success_count == 2
                        assert failure_count == 0
                        
                        # Check API calls
                        assert mock_transcription_processor.transcribe_episode.call_count == 2
                        assert mock_gemini_client.identify_speakers.call_count == 2
                        
                        # Check output files
                        output_dir = Path(mock_config.output.default_dir)
                        vtt_files = list(output_dir.rglob("*.vtt"))
                        assert len(vtt_files) == 2
                        
                        # Check report
                        report_file = output_dir / "Test Podcast_report.json"
                        assert report_file.exists()
                        
                        with open(report_file, 'r') as f:
                            report = json.load(f)
                        assert report['summary']['total_processed'] == 2
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, tmp_path, mock_config, mock_feed_episodes):
        """Test orchestrator handling errors gracefully."""
        podcast_metadata, episodes = mock_feed_episodes
        
        # Mock dependencies with some failures
        mock_feed_parser = MagicMock()
        mock_feed_parser.parse_feed.return_value = (podcast_metadata, episodes)
        
        # Mock gemini client
        mock_gemini_client = MagicMock()
        mock_gemini_client.api_keys = ['test_key_1', 'test_key_2']  # Mock has 2 keys
        mock_gemini_client.identify_speakers = AsyncMock(
            return_value={"SPEAKER_1": "Host"}
        )
        mock_gemini_client.get_usage_summary.return_value = {
            'key_1': {'requests_today': 0, 'requests_remaining': 25},
            'key_2': {'requests_today': 0, 'requests_remaining': 25}
        }
        
        # Mock transcription processor - First call succeeds, second fails, third succeeds
        mock_transcription_processor = MagicMock()
        mock_transcription_processor.transcribe_episode = AsyncMock(
            side_effect=[
                "Successful transcript",
                Exception("API error"),
                "Another successful transcript"
            ]
        )
        
        # Mock key rotation manager
        mock_key_rotation_manager = MagicMock()
        mock_key_rotation_manager.get_next_key.return_value = ('test_key_1', 0)
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager') as mock_rotation:
                    mock_rotation.return_value = mock_key_rotation_manager
                    
                    # Patch ProgressTracker to use temp directory
                    with patch('src.orchestrator.ProgressTracker') as mock_progress_class:
                        mock_progress_tracker = MagicMock()
                        mock_progress_tracker.state.episodes = {}
                        mock_progress_class.return_value = mock_progress_tracker
                        
                        orchestrator = TranscriptionOrchestrator(
                            output_dir=Path(mock_config.output.default_dir),
                            enable_checkpoint=False,  # Disable checkpoint for this test
                            resume=False,
                            data_dir=tmp_path / "data"
                        )
                        
                        # Patch the transcription processor
                        orchestrator.transcription_processor = mock_transcription_processor
                    
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=3
                        )
                    
                        success_count = results.get('processed', 0)
                        failure_count = results.get('failed', 0)
                        
                        # Should have 2 successes and 1 failure
                        assert success_count == 2
                        assert failure_count == 1
                        
                        # Check that processing continued after failure
                        assert mock_transcription_processor.transcribe_episode.call_count == 3
    
    @pytest.mark.asyncio
    async def test_orchestrator_resume_functionality(self, tmp_path, mock_config, mock_feed_episodes):
        """Test orchestrator resuming from previous state."""
        podcast_metadata, episodes = mock_feed_episodes
        
        # Create existing progress file with one completed episode
        progress_data = {
            'meta': {
                'total_processed': 1,
                'daily_quota_used': 2,
                'last_updated': '2024-01-15T10:00:00'
            },
            'episodes': {
                'ep1-guid': {
                    'guid': 'ep1-guid',
                    'status': 'completed',
                    'title': 'Episode 1',
                    'podcast_name': 'Test Podcast',
                    'attempt_count': 1,
                    'output_file': 'Test_Podcast/2024-01-11_Episode_1.vtt'
                }
            }
        }
        
        progress_file = Path(tmp_path) / '.progress.json'
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
        
        # Mock dependencies
        mock_feed_parser = MagicMock()
        mock_feed_parser.parse_feed.return_value = (podcast_metadata, episodes)
        
        mock_gemini_client = MagicMock()
        mock_gemini_client.api_keys = ['test_key_1', 'test_key_2']  # Mock has 2 keys
        mock_gemini_client.identify_speakers = AsyncMock(return_value={})
        mock_gemini_client.get_usage_summary.return_value = {
            'key_1': {'requests_today': 0, 'requests_remaining': 25},
            'key_2': {'requests_today': 0, 'requests_remaining': 25}
        }
        
        # Mock transcription processor
        mock_transcription_processor = MagicMock()
        mock_transcription_processor.transcribe_episode = AsyncMock(return_value="Transcript")
        
        # Mock key rotation manager
        mock_key_rotation_manager = MagicMock()
        mock_key_rotation_manager.get_next_key.return_value = ('test_key_1', 0)
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager') as mock_rotation:
                    mock_rotation.return_value = mock_key_rotation_manager
                    
                    # Patch ProgressTracker to use temp directory with existing progress
                    with patch('src.orchestrator.ProgressTracker') as mock_progress_class:
                        # Create a mock progress tracker with existing episode
                        from src.progress_tracker import ProgressState, EpisodeProgress, EpisodeStatus
                        
                        mock_state = ProgressState()
                        mock_state.episodes['ep1-guid'] = EpisodeProgress(
                            guid='ep1-guid',
                            status=EpisodeStatus.COMPLETED,
                            title='Episode 1',
                            podcast_name='Test Podcast',
                            attempt_count=1,
                            output_file='Test_Podcast/2024-01-11_Episode_1.vtt'
                        )
                        
                        mock_progress_tracker = MagicMock()
                        mock_progress_tracker.state = mock_state
                        mock_progress_tracker.load.return_value = None
                        mock_progress_class.return_value = mock_progress_tracker
                        
                        orchestrator = TranscriptionOrchestrator(
                            output_dir=Path(mock_config.output.default_dir),
                            enable_checkpoint=True,
                            resume=True
                        )
                        
                        # Patch the transcription processor
                        orchestrator.transcription_processor = mock_transcription_processor
                        
                        # Should have components initialized
                        assert orchestrator.progress_tracker is not None
                        assert len(orchestrator.progress_tracker.state.episodes) == 1
                        
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=3
                        )
                        success_count = results.get('processed', 0)
                        failure_count = results.get('failed', 0)
                    
                        # Should only process remaining 2 episodes
                        assert mock_transcription_processor.transcribe_episode.call_count == 2
                        assert success_count == 2
                        assert failure_count == 0


class TestCLIIntegration:
    """Test CLI interface integration."""
    
    @pytest.fixture(autouse=True)
    def cleanup_coroutines(self):
        """Clean up any unawaited coroutines to prevent warnings."""
        yield
        # Clean up after test
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited")
            gc.collect()
    
    def test_parse_args_basic(self):
        """Test basic argument parsing."""
        # Need to provide the command
        args = parse_args(['transcribe', '--feed-url', 'https://example.com/feed.xml'])
        
        assert args.feed_url == 'https://example.com/feed.xml'
        assert args.output_dir == 'data/transcripts'  # Default value
        assert args.max_episodes == 12  # Default value
        assert args.resume is False
        assert args.dry_run is False
    
    def test_parse_args_all_options(self):
        """Test parsing all command line options."""
        args = parse_args([
            'transcribe',
            '--feed-url', 'https://example.com/feed.xml',
            '--output-dir', '/custom/output',
            '--max-episodes', '10',
            '--resume',
            '--dry-run'
        ])
        
        assert args.feed_url == 'https://example.com/feed.xml'
        assert args.output_dir == '/custom/output'
        assert args.max_episodes == 10
        assert args.resume is True
        assert args.dry_run is True
    
    @patch('src.cli.TranscriptionOrchestrator')
    def test_main_function_basic(self, mock_orchestrator_class):
        """Test main CLI function with basic arguments."""
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_feed = AsyncMock(return_value={
            'status': 'completed',
            'processed': 5,
            'failed': 0,
            'skipped': 0,
            'episodes': []
        })
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Run CLI - should exit with code 0 for success
        with patch('sys.argv', ['podcast-transcriber', 'transcribe', '--feed-url', 'https://example.com/feed.xml']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        
        # Verify orchestrator was created with correct arguments
        mock_orchestrator_class.assert_called_once_with(
            output_dir=Path('data/transcripts'),
            enable_checkpoint=True,
            resume=False
        )
    
    def test_main_function_no_feed_url(self):
        """Test main function without required feed URL."""
        with patch('sys.argv', ['podcast-transcriber', 'transcribe']):
            with pytest.raises(SystemExit):
                main()
    
    
    @patch('src.cli.TranscriptionOrchestrator')
    @patch('src.cli.asyncio.run') 
    def test_main_with_dry_run(self, mock_asyncio_run, mock_orchestrator_class):
        """Test CLI in dry-run mode."""
        # Mock asyncio.run to return the result from transcribe_command (0 for dry run)
        mock_asyncio_run.return_value = 0
        
        # Dry run should not create orchestrator, just exit
        with patch('sys.argv', ['podcast-transcriber', 'transcribe', '--feed-url', 'https://example.com/feed.xml', '--dry-run']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        
        # Verify orchestrator was NOT created (dry run exits early)
        mock_orchestrator_class.assert_not_called()
    
    @patch('src.cli.logger')
    @patch('src.cli.TranscriptionOrchestrator')
    def test_main_with_processing_error(self, mock_orchestrator_class, mock_logger):
        """Test CLI handling processing errors."""
        # Mock orchestrator to raise exception
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_feed = AsyncMock(side_effect=Exception("Processing failed"))
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Run CLI - should exit with error code
        with patch('sys.argv', ['podcast-transcriber', 'transcribe', '--feed-url', 'https://example.com/feed.xml']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        
        # Check error was logged
        mock_logger.error.assert_called()
        assert "Processing failed" in str(mock_logger.error.call_args)