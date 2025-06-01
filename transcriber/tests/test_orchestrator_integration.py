"""Integration tests for the orchestrator and CLI components."""

import pytest
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
from argparse import Namespace

from src.orchestrator import TranscriptionOrchestrator
from src.cli import main, parse_arguments
from src.config import Config


class TestOrchestratorIntegration:
    """Test the transcription orchestrator with all components."""
    
    @pytest.fixture
    def mock_config(self, temp_dir):
        """Create a mock configuration."""
        with patch('src.config.get_config') as mock_get_config:
            config = Config()
            config.output.default_dir = str(Path(temp_dir) / 'transcripts')
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
    async def test_orchestrator_full_workflow(self, temp_dir, mock_config, mock_feed_episodes):
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
        mock_gemini_client.transcribe_audio = AsyncMock(return_value=mock_gemini_response.text)
        mock_gemini_client.identify_speakers = AsyncMock(
            return_value={"SPEAKER_1": "Test Host (Host)"}
        )
        mock_gemini_client.get_usage_summary.return_value = {
            'key_1': {'requests_today': 0, 'requests_remaining': 25}
        }
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager') as mock_rotation:
                    mock_rotation.return_value = MagicMock()
                    
                    # Create orchestrator
                    orchestrator = TranscriptionOrchestrator(
                        feed_url="https://example.com/feed.xml",
                        output_dir=mock_config.output.default_dir,
                        max_episodes=2  # Process only 2 episodes
                    )
                    
                    # Run processing
                    success_count, failure_count = await orchestrator.process_feed()
                    
                    # Verify results
                    assert success_count == 2
                    assert failure_count == 0
                    
                    # Check API calls
                    assert mock_gemini_client.transcribe_audio.call_count == 2
                    assert mock_gemini_client.identify_speakers.call_count == 2
                    
                    # Check output files
                    output_dir = Path(mock_config.output.default_dir)
                    vtt_files = list(output_dir.rglob("*.vtt"))
                    assert len(vtt_files) == 2
                    
                    # Check manifest
                    manifest_file = output_dir / "manifest.json"
                    assert manifest_file.exists()
                    
                    with open(manifest_file, 'r') as f:
                        manifest = json.load(f)
                    assert manifest['total_episodes'] == 2
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, temp_dir, mock_config, mock_feed_episodes):
        """Test orchestrator handling errors gracefully."""
        podcast_metadata, episodes = mock_feed_episodes
        
        # Mock dependencies with some failures
        mock_feed_parser = MagicMock()
        mock_feed_parser.parse_feed.return_value = (podcast_metadata, episodes)
        
        # First call succeeds, second fails, third succeeds
        mock_gemini_client = MagicMock()
        mock_gemini_client.transcribe_audio = AsyncMock(
            side_effect=[
                "Successful transcript",
                Exception("API error"),
                "Another successful transcript"
            ]
        )
        mock_gemini_client.identify_speakers = AsyncMock(
            return_value={"SPEAKER_1": "Host"}
        )
        mock_gemini_client.get_usage_summary.return_value = {}
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager'):
                    orchestrator = TranscriptionOrchestrator(
                        feed_url="https://example.com/feed.xml",
                        output_dir=mock_config.output.default_dir,
                        max_episodes=3
                    )
                    
                    success_count, failure_count = await orchestrator.process_feed()
                    
                    # Should have 2 successes and 1 failure
                    assert success_count == 2
                    assert failure_count == 1
                    
                    # Check that processing continued after failure
                    assert mock_gemini_client.transcribe_audio.call_count == 3
    
    @pytest.mark.asyncio
    async def test_orchestrator_resume_functionality(self, temp_dir, mock_config, mock_feed_episodes):
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
        
        progress_file = Path(temp_dir) / '.progress.json'
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
        
        # Mock dependencies
        mock_feed_parser = MagicMock()
        mock_feed_parser.parse_feed.return_value = (podcast_metadata, episodes)
        
        mock_gemini_client = MagicMock()
        mock_gemini_client.transcribe_audio = AsyncMock(return_value="Transcript")
        mock_gemini_client.identify_speakers = AsyncMock(return_value={})
        mock_gemini_client.get_usage_summary.return_value = {}
        
        with patch('src.orchestrator.parse_feed', mock_feed_parser.parse_feed):
            with patch('src.orchestrator.create_gemini_client', return_value=mock_gemini_client):
                with patch('src.orchestrator.create_key_rotation_manager'):
                    orchestrator = TranscriptionOrchestrator(
                        feed_url="https://example.com/feed.xml",
                        output_dir=mock_config.output.default_dir,
                        resume=True
                    )
                    
                    # Should load existing progress
                    assert orchestrator.progress_tracker is not None
                    assert len(orchestrator.progress_tracker.state.episodes) == 1
                    
                    success_count, failure_count = await orchestrator.process_feed()
                    
                    # Should only process remaining 2 episodes
                    assert mock_gemini_client.transcribe_audio.call_count == 2
                    assert success_count == 2
                    assert failure_count == 0


class TestCLIIntegration:
    """Test CLI interface integration."""
    
    def test_parse_args_basic(self):
        """Test basic argument parsing."""
        args = parse_args(['--feed-url', 'https://example.com/feed.xml'])
        
        assert args.feed_url == 'https://example.com/feed.xml'
        assert args.output_dir is None
        assert args.max_episodes is None
        assert args.resume is False
        assert args.dry_run is False
    
    def test_parse_args_all_options(self):
        """Test parsing all command line options."""
        args = parse_args([
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
    @patch('src.cli.get_config')
    @patch('src.cli.asyncio.run')
    def test_main_function_basic(self, mock_asyncio_run, mock_get_config, mock_orchestrator_class):
        """Test main CLI function with basic arguments."""
        # Mock config
        config = MagicMock()
        config.output.default_dir = '/default/output'
        config.api.max_episodes_per_day = 12
        config.development.dry_run = False
        mock_get_config.return_value = config
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_feed = AsyncMock(return_value=(5, 0))
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock asyncio.run to execute the coroutine
        async def run_async(coro):
            return await coro
        mock_asyncio_run.side_effect = lambda coro: asyncio.get_event_loop().run_until_complete(coro)
        
        # Run CLI
        with patch('sys.argv', ['transcribe', '--feed-url', 'https://example.com/feed.xml']):
            with patch('src.cli.asyncio.run', side_effect=run_async):
                main()
        
        # Verify orchestrator was created with correct arguments
        mock_orchestrator_class.assert_called_once_with(
            feed_url='https://example.com/feed.xml',
            output_dir='/default/output',
            max_episodes=12,
            resume=False,
            dry_run=False
        )
    
    @patch('src.cli.get_config')
    def test_main_function_no_feed_url(self, mock_get_config):
        """Test main function without required feed URL."""
        with patch('sys.argv', ['transcribe']):
            with pytest.raises(SystemExit):
                main()
    
    def test_progress_bar_creation(self):
        """Test progress bar utility function."""
        # Test with progress bar enabled
        with patch('src.cli.tqdm') as mock_tqdm:
            items = [1, 2, 3]
            progress = create_progress_bar(items, desc="Testing", enabled=True)
            
            mock_tqdm.assert_called_once_with(
                items,
                desc="Testing",
                unit="episode",
                leave=True
            )
        
        # Test with progress bar disabled
        items = [1, 2, 3]
        progress = create_progress_bar(items, desc="Testing", enabled=False)
        assert progress == items  # Should return items unchanged
    
    @patch('src.cli.TranscriptionOrchestrator')
    @patch('src.cli.get_config')
    def test_main_with_dry_run(self, mock_get_config, mock_orchestrator_class):
        """Test CLI in dry-run mode."""
        # Mock config
        config = MagicMock()
        config.output.default_dir = '/default/output'
        config.api.max_episodes_per_day = 12
        config.development.dry_run = True  # Dry run enabled in config
        mock_get_config.return_value = config
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Run CLI with dry-run flag
        with patch('sys.argv', ['transcribe', '--feed-url', 'https://example.com/feed.xml', '--dry-run']):
            main()
        
        # Verify orchestrator was created with dry_run=True
        _, kwargs = mock_orchestrator_class.call_args
        assert kwargs['dry_run'] is True
    
    @patch('src.cli.logger')
    @patch('src.cli.TranscriptionOrchestrator')
    @patch('src.cli.get_config')
    @patch('src.cli.asyncio.run')
    def test_main_with_processing_error(self, mock_asyncio_run, mock_get_config, 
                                      mock_orchestrator_class, mock_logger):
        """Test CLI handling processing errors."""
        # Mock config
        config = MagicMock()
        mock_get_config.return_value = config
        
        # Mock orchestrator to raise exception
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_feed = AsyncMock(side_effect=Exception("Processing failed"))
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock asyncio.run
        mock_asyncio_run.side_effect = lambda coro: asyncio.get_event_loop().run_until_complete(coro)
        
        # Run CLI - should exit with error code
        with patch('sys.argv', ['transcribe', '--feed-url', 'https://example.com/feed.xml']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        # Check error was logged
        mock_logger.error.assert_called()
        assert "Processing failed" in str(mock_logger.error.call_args)
        
        # Check exit code
        assert exc_info.value.code == 1