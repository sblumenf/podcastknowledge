"""Comprehensive tests for CLI module to improve coverage from 2.48% to 15%."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import tempfile
import json
import argparse

from src.cli import main, parse_arguments, transcribe_command, query_command, state_command, show_quota_command
from src.config import Config


class TestCLICommandParsing:
    """Test command parsing functionality."""
    
    def test_help_command(self):
        """Test help output."""
        with patch('sys.argv', ['cli.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code == 0
    
    def test_transcribe_command_parsing(self):
        """Test transcribe command parsing."""
        args = parse_arguments(['transcribe', '--feed-url', 'https://example.com/feed.xml'])
        assert args.command == 'transcribe'
        assert args.feed_url == 'https://example.com/feed.xml'
    
    def test_transcribe_command_with_options(self):
        """Test transcribe command with various options."""
        args = parse_arguments([
            '--verbose',
            'transcribe', '--feed-url', 'https://example.com/feed.xml',
            '--max-episodes', '10',
            '--output-dir', '/tmp/output',
            '--resume'
        ])
        assert args.command == 'transcribe'
        assert args.max_episodes == 10
        assert args.output_dir == '/tmp/output'
        assert args.verbose is True
        assert args.resume is True
    
    def test_query_command_parsing(self):
        """Test query command parsing."""
        args = parse_arguments(['query', '--keywords', 'test query', '--limit', '5'])
        assert args.command == 'query'
        assert args.keywords == 'test query'
        assert args.limit == 5
    
    def test_state_command_parsing(self):
        """Test state command parsing."""
        args = parse_arguments(['state', 'show'])
        assert args.command == 'state'
        assert args.state_command == 'show'
        
        args = parse_arguments(['state', 'reset', '--force'])
        assert args.command == 'state'
        assert args.state_command == 'reset'
        assert args.force is True
    
    def test_validate_feed_command_parsing(self):
        """Test validate-feed command parsing."""
        args = parse_arguments(['validate-feed', 'https://example.com/feed.xml', '--detailed'])
        assert args.command == 'validate-feed'
        assert args.feed_url == 'https://example.com/feed.xml'
        assert args.detailed is True
    
    def test_test_api_command_parsing(self):
        """Test test-api command parsing."""
        args = parse_arguments(['test-api', '--quick'])
        assert args.command == 'test-api'
        assert args.quick is True
    
    def test_show_quota_command_parsing(self):
        """Test show-quota command parsing."""
        args = parse_arguments(['show-quota', '--export-csv', 'quota.csv'])
        assert args.command == 'show-quota'
        assert args.export_csv == 'quota.csv'


class TestCLIErrorHandling:
    """Test CLI error handling."""
    
    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handling(self):
        """Test handling of keyboard interrupt."""
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir='output',
            verbose=False,
            resume=False,
            dry_run=False,
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        with patch('feedparser.parse') as mock_parse:
            mock_parse.side_effect = KeyboardInterrupt()
            
            result = await transcribe_command(args)
            assert result != 0
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, tmp_path, monkeypatch):
        """Test handling of network errors."""
        # Use isolated temp directory for this test
        test_output_dir = tmp_path / "output"
        test_data_dir = tmp_path / "data"
        
        # Set isolated environment variables
        monkeypatch.setenv('STATE_DIR', str(test_data_dir))
        
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir=str(test_output_dir),
            verbose=False,
            resume=False,
            dry_run=False,
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        # Mock the TranscriptionOrchestrator in the cli module namespace
        with patch('src.cli.TranscriptionOrchestrator') as mock_orchestrator:
            mock_orchestrator.side_effect = Exception("Network error: Connection refused")
            
            result = await transcribe_command(args)
            assert result != 0
    
    def test_invalid_output_directory(self):
        """Test handling of invalid output directory."""
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir='/root/forbidden',  # Typically no write access
            verbose=False,
            resume=False,
            dry_run=False,
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            result = asyncio.run(transcribe_command(args))
            assert result != 0
    
    def test_invalid_arguments(self):
        """Test handling of invalid arguments."""
        # Test missing required argument
        with pytest.raises(SystemExit):
            parse_arguments(['transcribe'])  # Missing URL
        
        # Test invalid command
        with pytest.raises(SystemExit):
            parse_arguments(['invalid-command'])


class TestCLIProgressDisplay:
    """Test CLI progress display functionality."""
    
    @pytest.mark.asyncio
    async def test_progress_display_enabled(self):
        """Test progress display when enabled."""
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir='output',
            verbose=False,
            resume=False,
            dry_run=False,
            no_progress=False,  # Progress enabled
            retry_failed=False,
            reset_state=False
        )
        
        with patch('src.orchestrator.TranscriptionOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.process_feed = AsyncMock(return_value={
                'status': 'completed',
                'processed': 5,
                'failed': 0,
                'skipped': 0,
                'episodes': []
            })
            
            result = await transcribe_command(args)
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_verbose_output(self, tmp_path, monkeypatch):
        """Test verbose output mode."""
        # Use isolated temp directory for this test
        test_output_dir = tmp_path / "output"
        test_data_dir = tmp_path / "data"
        
        # Set isolated environment variables
        monkeypatch.setenv('STATE_DIR', str(test_data_dir))
        
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir=str(test_output_dir),
            verbose=True,  # Verbose enabled
            resume=False,
            dry_run=False,
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        with patch('src.orchestrator.TranscriptionOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.process_feed = AsyncMock(return_value={
                'status': 'completed',
                'processed': 3,
                'failed': 0,
                'skipped': 0,
                'episodes': []
            })
            mock_instance.gemini_client.get_usage_summary.return_value = {
                'key_1': {
                    'requests_today': 10,
                    'requests_remaining': 15,
                    'tokens_today': 100000,
                    'tokens_remaining': 900000
                }
            }
            
            # Patch the logger directly in the cli module
            with patch('src.cli.logger') as mock_logger:
                result = await transcribe_command(args)
                assert result == 0
                # Verbose mode should log more info
                assert mock_logger.info.call_count > 0
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test dry run mode doesn't process episodes."""
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir='output',
            verbose=False,
            resume=False,
            dry_run=True,  # Dry run enabled
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        with patch('src.orchestrator.TranscriptionOrchestrator') as mock_orchestrator:
            result = await transcribe_command(args)
            assert result == 0
            # In dry run, orchestrator should not be called to process
            mock_orchestrator.return_value.process_feed.assert_not_called()


class TestCLIIntegration:
    """Test CLI integration with other components."""
    
    @pytest.mark.asyncio
    async def test_resume_functionality(self):
        """Test resume from checkpoint."""
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir='output',
            verbose=False,
            resume=True,  # Resume enabled
            dry_run=False,
            no_progress=True,
            retry_failed=False,
            reset_state=False
        )
        
        with patch('src.orchestrator.TranscriptionOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            # Mock progress tracker with existing progress
            mock_instance.progress_tracker.state.episodes = {
                'ep1': Mock(status=Mock(value='completed')),
                'ep2': Mock(status=Mock(value='failed'))
            }
            mock_instance.process_feed = AsyncMock(return_value={
                'status': 'completed',
                'processed': 2,
                'failed': 0,
                'resumed': True,
                'episodes': []
            })
            
            result = await transcribe_command(args)
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_retry_failed_episodes(self, tmp_path, monkeypatch):
        """Test retry failed episodes functionality."""
        # Use isolated temp directory for this test
        test_output_dir = tmp_path / "output"
        test_data_dir = tmp_path / "data"
        
        # Set isolated environment variables
        monkeypatch.setenv('STATE_DIR', str(test_data_dir))
        
        args = argparse.Namespace(
            command='transcribe',
            feed_url='https://example.com/feed.xml',
            max_episodes=5,
            output_dir=str(test_output_dir),
            verbose=False,
            resume=False,
            dry_run=False,
            no_progress=True,
            retry_failed=True,  # Retry failed enabled
            reset_state=False
        )
        
        with patch('src.orchestrator.TranscriptionOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            # Mock failed episodes
            mock_instance.progress_tracker.get_failed.return_value = [
                Mock(title='Episode 1', error='Network error', attempt_count=1),
                Mock(title='Episode 2', error='API error', attempt_count=2)
            ]
            
            with patch('src.cli._retry_failed_episodes', new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = 0
                result = await transcribe_command(args)
                mock_retry.assert_called_once()
    
    def test_state_command_functionality(self):
        """Test state command functionality."""
        args = argparse.Namespace(
            command='state',
            state_command='show',
            verbose=False
        )
        
        with patch('src.utils.state_management.show_state_status') as mock_show:
            mock_show.return_value = {
                'state_directory': '/tmp/state',
                'state_files': {
                    'progress.json': {
                        'exists': True,
                        'size_bytes': 1024,
                        'modified': '2024-01-01',
                        'episodes': 10
                    }
                }
            }
            
            result = state_command(args)
            assert result == 0
            mock_show.assert_called_once()


class TestCommandFunctions:
    """Test individual command functions."""
    
    def test_query_command(self):
        """Test query command functionality."""
        args = argparse.Namespace(
            command='query',
            speaker=None,
            podcast=None,
            date=None,
            date_range=None,
            keywords='test search',
            all=None,
            export_csv=None,
            limit=10,
            stats=False,
            verbose=False
        )
        
        with patch('src.cli.get_metadata_index') as mock_get_index:
            mock_index = Mock()
            mock_index.search_by_keywords.return_value = Mock(
                query='test search',
                total_results=1,
                episodes=[
                    Mock(
                        title='Episode 1',
                        podcast_name='Test Podcast',
                        publication_date='2024-01-01',
                        file_path='/test/path.vtt',
                        speakers=['Host'],
                        duration=1800,
                        episode_number=1
                    )
                ],
                search_time_ms=5.0
            )
            mock_get_index.return_value = mock_index
            
            result = query_command(args)
            assert result == 0
            mock_index.search_by_keywords.assert_called_once_with('test search')
    
    def test_show_quota_command(self):
        """Test show quota command."""
        args = argparse.Namespace(
            command='show-quota',
            export_csv=None,
            reset_usage=False,
            verbose=False
        )
        
        with patch('src.config.Config') as mock_config_class:
            mock_config = mock_config_class.return_value
            with patch('src.gemini_client.create_gemini_client') as mock_create_client:
                with patch('src.key_rotation_manager.create_key_rotation_manager') as mock_create_krm:
                    mock_client = Mock()
                    mock_client.get_usage_summary.return_value = {
                        'key_1': {
                            'requests_today': 10,
                            'tokens_today': 50000,
                            'requests_remaining': 15,
                            'tokens_remaining': 950000
                        }
                    }
                    mock_create_client.return_value = mock_client
                    mock_create_krm.return_value = Mock()
                    
                    result = show_quota_command(args)
                    assert result == 0


class TestMainFunction:
    """Test the main entry point."""
    
    def test_main_function_transcribe(self):
        """Test main function with transcribe command."""
        test_args = ['cli.py', 'transcribe', '--feed-url', 'https://example.com/feed.xml']
        
        with patch('sys.argv', test_args):
            with patch('asyncio.run') as mock_run:
                mock_run.return_value = 0
                with patch('sys.exit') as mock_exit:
                    main()
                    mock_exit.assert_called_once_with(0)
    
    def test_main_function_query(self):
        """Test main function with query command."""
        test_args = ['cli.py', 'query', '--keywords', 'test search']
        
        with patch('sys.argv', test_args):
            with patch('src.cli.query_command') as mock_query:
                mock_query.return_value = 0
                with patch('sys.exit') as mock_exit:
                    main()
                    mock_exit.assert_called_once_with(0)
    
    def test_main_function_error_handling(self):
        """Test main function error handling."""
        test_args = ['cli.py', 'unknown-command']
        
        with patch('sys.argv', test_args):
            with patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_once_with(1)