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
        
        # Create progress file in the data directory
        data_dir = Path(tmp_path) / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        progress_file = data_dir / '.progress.json'
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
                            resume=True,
                            data_dir=tmp_path / 'data'
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


@pytest.mark.integration
@pytest.mark.timeout(120)
class TestOrchestratorStateManagement:
    """Test state management specific scenarios for the orchestrator."""
    
    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration."""
        config = Config()
        config.output.default_dir = str(Path(tmp_path) / 'transcripts')
        config.api.max_episodes_per_day = 5
        config.processing.enable_progress_bar = False
        return config
    
    @pytest.fixture
    def setup_state_files(self, tmp_path):
        """Set up various state files for testing."""
        # Create progress file
        progress_data = {
            'meta': {
                'total_processed': 2,
                'daily_quota_used': 4,
                'last_updated': '2024-01-15T10:00:00',
                'api_keys_usage': {
                    'key1': {'requests_today': 2, 'last_reset': '2024-01-15T00:00:00'},
                    'key2': {'requests_today': 2, 'last_reset': '2024-01-15T00:00:00'}
                }
            },
            'episodes': {
                'ep1-guid': {
                    'guid': 'ep1-guid',
                    'status': 'completed',
                    'title': 'Episode 1',
                    'attempt_count': 1
                },
                'ep2-guid': {
                    'guid': 'ep2-guid', 
                    'status': 'in_progress',
                    'title': 'Episode 2',
                    'attempt_count': 2,
                    'last_error': 'API timeout'
                },
                'ep3-guid': {
                    'guid': 'ep3-guid',
                    'status': 'failed',
                    'title': 'Episode 3',
                    'attempt_count': 3,
                    'last_error': 'Max retries exceeded'
                },
                'ep4-guid': {
                    'guid': 'ep4-guid',
                    'status': 'pending',
                    'title': 'Episode 4'
                }
            }
        }
        
        # Create progress file in the data directory
        data_dir = Path(tmp_path) / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        progress_file = data_dir / '.progress.json'
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
        
        # Create checkpoint files in the data directory (hardcoded location)
        data_dir = Path(tmp_path) / 'data'
        checkpoint_dir = data_dir / 'checkpoints' / 'temp'
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # In-progress checkpoint
        checkpoint_data = {
            'episode_id': 'ep2-guid',
            'stage': 'speaker_identification',
            'title': 'Episode 2',
            'audio_url': 'http://test.com/ep2.mp3',
            'metadata': {
                'podcast_name': 'Test Podcast',
                'published_date': '2024-01-12T00:00:00'
            }
        }
        
        checkpoint_file = checkpoint_dir / 'ep2-guid.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
        
        return {
            'progress_file': progress_file,
            'checkpoint_dir': checkpoint_dir,
            'checkpoint_file': checkpoint_file,
            'data_dir': data_dir
        }
    
    @pytest.mark.asyncio
    async def test_checkpoint_directory_location(self, tmp_path, mock_config):
        """Test that checkpoint files are created in the correct data_dir location."""
        from src.orchestrator import TranscriptionOrchestrator
        
        # Create data directory for this test
        data_dir = tmp_path / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                data_dir=data_dir
            )
            
            # Verify checkpoint manager uses the correct directory
            assert orchestrator.checkpoint_manager.data_dir == data_dir
            assert orchestrator.checkpoint_manager.checkpoint_dir == data_dir / "checkpoints"
            assert orchestrator.checkpoint_manager.temp_dir == data_dir / "checkpoints" / "temp"
            assert orchestrator.checkpoint_manager.completed_dir == data_dir / "checkpoints" / "completed"
            
            # Verify directories were created
            assert (data_dir / "checkpoints").exists()
            assert (data_dir / "checkpoints" / "temp").exists()
            assert (data_dir / "checkpoints" / "completed").exists()
    
    @pytest.mark.asyncio
    async def test_checkpoint_file_detection(self, tmp_path, mock_config, setup_state_files):
        """Test that checkpoint files created by setup are found in the correct location."""
        from src.orchestrator import TranscriptionOrchestrator
        
        state_files = setup_state_files
        data_dir = state_files['data_dir']
        
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                data_dir=data_dir
            )
            
            # Verify checkpoint manager can find the checkpoint file from setup
            checkpoint_file = state_files['checkpoint_file']
            assert checkpoint_file.exists()
            assert checkpoint_file.parent == orchestrator.checkpoint_manager.temp_dir
    
    @pytest.mark.asyncio
    async def test_concurrent_state_access_protection(self, tmp_path, mock_config, setup_state_files):
        """Test that concurrent access to state files is properly handled."""
        from src.feed_parser import Episode, PodcastMetadata
        from src.orchestrator import TranscriptionOrchestrator
        import tempfile
        
        # Simulate concurrent orchestrator instances
        orchestrator1 = TranscriptionOrchestrator(
            output_dir=Path(mock_config.output.default_dir),
            enable_checkpoint=True,
            data_dir=tmp_path / 'data'
        )
        
        orchestrator2 = TranscriptionOrchestrator(
            output_dir=Path(mock_config.output.default_dir),
            enable_checkpoint=True,
            data_dir=tmp_path / 'data'
        )
        
        # Both should read the same initial state
        assert orchestrator1.progress_tracker.get_episode_status('ep1-guid') == 'completed'
        assert orchestrator2.progress_tracker.get_episode_status('ep1-guid') == 'completed'
        
        # Update state from orchestrator1
        orchestrator1.progress_tracker.update_episode_status(
            'ep4-guid',
            'in-progress',
            title='Episode 4'
        )
        
        # Orchestrator2 should be able to read updated state after reloading
        orchestrator2.progress_tracker._load_state()
        assert orchestrator2.progress_tracker.get_episode_status('ep4-guid') == 'in-progress'
    
    @pytest.mark.asyncio
    async def test_state_recovery_with_corrupted_files(self, tmp_path, mock_config):
        """Test recovery when state files are corrupted."""
        from src.orchestrator import TranscriptionOrchestrator
        
        # Create corrupted progress file
        progress_file = Path(tmp_path) / '.progress.json'
        progress_file.write_text('{"invalid": json"corrupted"}')
        
        # Orchestrator should handle corrupted file gracefully
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                data_dir=tmp_path / 'data'
            )
            
            # Should start with empty state
            assert orchestrator.progress_tracker.state.total_processed == 0
            assert len(orchestrator.progress_tracker.state.episodes) == 0
    
    @pytest.mark.asyncio
    async def test_state_cleanup_on_successful_completion(self, tmp_path, mock_config, setup_state_files):
        """Test that temporary state files are cleaned up after successful completion."""
        from src.feed_parser import Episode, PodcastMetadata
        from src.orchestrator import TranscriptionOrchestrator
        
        state_files = setup_state_files
        
        # Create a simple episode that's in progress
        episodes = [
            Episode(guid='ep2-guid', title='Episode 2', audio_url='http://test.com/ep2.mp3')
        ]
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        # Mock successful processing
        async def mock_process_episode(episode, metadata):
            return {
                'status': 'completed',
                'episode_id': episode.guid,
                'title': episode.title,
                'output_file': f'{episode.guid}.vtt'
            }
        
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                resume=True,  # Resume from checkpoint
                data_dir=tmp_path / 'data'
            )
            
            with patch('src.orchestrator.parse_feed') as mock_parse:
                mock_parse.return_value = (podcast_metadata, episodes)
                
                # Mock checkpoint manager
                orchestrator.checkpoint_manager.can_resume = MagicMock(return_value=True)
                orchestrator._resume_processing = AsyncMock(return_value={
                    'status': 'resumed',
                    'processed': 1,
                    'failed': 0,
                    'episodes': [{'status': 'completed', 'episode_id': 'ep2-guid'}]
                })
                orchestrator._generate_summary_report = MagicMock()
                
                result = await orchestrator.process_feed("http://test.com/feed.xml")
                
                # Verify checkpoint was cleaned up
                assert not state_files['checkpoint_file'].exists()
    
    @pytest.mark.asyncio
    async def test_quota_tracking_across_interruptions(self, tmp_path, mock_config, setup_state_files):
        """Test that quota tracking persists correctly across interruptions."""
        from src.feed_parser import Episode, PodcastMetadata
        from src.orchestrator import TranscriptionOrchestrator
        from src.gemini_client import QuotaExceededException
        
        episodes = [
            Episode(guid='ep7-guid', title='Episode 7', audio_url='http://test.com/ep7.mp3'),
            Episode(guid='ep8-guid', title='Episode 8', audio_url='http://test.com/ep8.mp3')
        ]
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        # First run - process one episode then hit quota
        call_count = 0
        async def mock_process_episode_quota(episode, metadata):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    'status': 'completed',
                    'episode_id': episode.guid,
                    'title': episode.title
                }
            else:
                raise QuotaExceededException("Daily quota exceeded")
        
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                data_dir=tmp_path / 'data'
            )
            
            with patch('src.orchestrator.parse_feed') as mock_parse:
                mock_parse.return_value = (podcast_metadata, episodes)
                orchestrator._process_episode = mock_process_episode_quota
                orchestrator._generate_summary_report = MagicMock()
                
                # Mock quota wait to return False (don't wait)
                orchestrator._wait_for_quota_reset = AsyncMock(return_value=False)
                
                result = await orchestrator.process_feed("http://test.com/feed.xml")
                
                assert result['processed'] == 1
                assert result['status'] == 'quota_reached'
                
                # Check quota was tracked
                progress_data = json.loads(setup_state_files['progress_file'].read_text())
                assert progress_data['meta']['daily_quota_used'] > 4  # Should have incremented
    
    @pytest.mark.asyncio
    async def test_episode_retry_state_tracking(self, tmp_path, mock_config, setup_state_files):
        """Test that episode retry attempts are properly tracked in state."""
        from src.feed_parser import Episode, PodcastMetadata
        from src.orchestrator import TranscriptionOrchestrator
        
        # Test retrying a failed episode
        episodes = [
            Episode(guid='ep3-guid', title='Episode 3', audio_url='http://test.com/ep3.mp3')
        ]
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        # Mock to fail again
        async def mock_process_episode_fail(episode, metadata):
            raise Exception("Still failing")
        
        with patch('src.config.get_config', return_value=mock_config):
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(mock_config.output.default_dir),
                enable_checkpoint=True,
                data_dir=tmp_path / 'data'
            )
            
            # Reset episode status to pending to allow retry
            orchestrator.progress_tracker.update_episode_status('ep3-guid', 'pending')
            
            with patch('src.orchestrator.parse_feed') as mock_parse:
                mock_parse.return_value = (podcast_metadata, episodes)
                orchestrator._process_episode = mock_process_episode_fail
                orchestrator._generate_summary_report = MagicMock()
                
                result = await orchestrator.process_feed("http://test.com/feed.xml")
                
                # Check retry count was incremented
                progress_data = json.loads(setup_state_files['progress_file'].read_text())
                episode_state = progress_data['episodes']['ep3-guid']
                assert episode_state['status'] == 'failed'
                assert episode_state['attempt_count'] == 4  # Was 3, now 4
                assert 'Still failing' in episode_state['last_error']