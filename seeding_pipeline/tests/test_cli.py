"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import tempfile

import pytest
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.cli import main, load_podcast_configs, seed_podcasts, health_check, validate_config


class TestCLI:
    """Test CLI functionality."""
    
    def test_load_podcast_configs_single(self):
        """Test loading single podcast config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "name": "Test Podcast",
                "rss_url": "https://example.com/feed.xml",
                "category": "Technology"
            }
            json.dump(config, f)
            f.flush()
            
            configs = load_podcast_configs(Path(f.name))
            assert len(configs) == 1
            assert configs[0]['name'] == 'Test Podcast'
            assert configs[0]['rss_url'] == 'https://example.com/feed.xml'
    
    def test_load_podcast_configs_multiple(self):
        """Test loading multiple podcast configs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            configs = [
                {
                    "name": "Podcast 1",
                    "rss_url": "https://example1.com/feed.xml"
                },
                {
                    "name": "Podcast 2",
                    "rss_url": "https://example2.com/feed.xml"
                }
            ]
            json.dump(configs, f)
            f.flush()
            
            loaded = load_podcast_configs(Path(f.name))
            assert len(loaded) == 2
            assert loaded[0]['name'] == 'Podcast 1'
            assert loaded[1]['name'] == 'Podcast 2'
    
    def test_load_podcast_configs_missing_rss_url(self):
        """Test loading config with missing RSS URL."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {"name": "Test Podcast"}
            json.dump(config, f)
            f.flush()
            
            with pytest.raises(ValueError, match="Missing 'rss_url'"):
                load_podcast_configs(Path(f.name))
    
    @patch('cli.VTTKnowledgeExtractor')
    def test_seed_podcasts_with_rss_url(self, mock_pipeline_class):
        """Test seeding with RSS URL argument."""
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline.seed_podcasts.return_value = {
            'start_time': '2024-01-01T00:00:00',
            'end_time': '2024-01-01T01:00:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'processing_time_seconds': 3600.0
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create args
        args = Mock()
        args.config = None
        args.podcast_config = None
        args.rss_url = 'https://example.com/feed.xml'
        args.name = 'Test Podcast'
        args.category = 'Tech'
        args.max_episodes = 5
        args.large_context = False
        args.verbose = False
        
        # Run seed_podcasts
        exit_code = seed_podcasts(args)
        
        # Verify
        assert exit_code == 0
        mock_pipeline_class.assert_called_once()
        mock_pipeline.seed_podcasts.assert_called_once_with(
            podcast_configs=[{
                'name': 'Test Podcast',
                'rss_url': 'https://example.com/feed.xml',
                'category': 'Tech'
            }],
            max_episodes_each=5,
            use_large_context=False
        )
        mock_pipeline.cleanup.assert_called_once()
    
    @patch('cli.VTTKnowledgeExtractor')
    def test_seed_podcasts_with_config_file(self, mock_pipeline_class):
        """Test seeding with podcast config file."""
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline.seed_podcasts.return_value = {
            'start_time': '2024-01-01T00:00:00',
            'end_time': '2024-01-01T01:00:00',
            'podcasts_processed': 2,
            'episodes_processed': 10,
            'episodes_failed': 1,
            'processing_time_seconds': 7200.0
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create podcast config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            configs = [
                {"name": "Podcast 1", "rss_url": "https://example1.com/feed.xml"},
                {"name": "Podcast 2", "rss_url": "https://example2.com/feed.xml"}
            ]
            json.dump(configs, f)
            f.flush()
            
            # Create args
            args = Mock()
            args.config = None
            args.podcast_config = f.name
            args.rss_url = None
            args.max_episodes = 10
            args.large_context = True
            args.verbose = False
            
            # Run seed_podcasts
            exit_code = seed_podcasts(args)
            
            # Verify
            assert exit_code == 0  # Success even with some failures
            mock_pipeline.seed_podcasts.assert_called_once()
    
    @patch('cli.VTTKnowledgeExtractor')
    def test_seed_podcasts_all_failed(self, mock_pipeline_class):
        """Test seeding when all episodes fail."""
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline.seed_podcasts.return_value = {
            'start_time': '2024-01-01T00:00:00',
            'end_time': '2024-01-01T01:00:00',
            'podcasts_processed': 1,
            'episodes_processed': 0,
            'episodes_failed': 5,
            'processing_time_seconds': 100.0
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create args
        args = Mock()
        args.config = None
        args.rss_url = 'https://example.com/feed.xml'
        args.name = None
        args.category = None
        args.podcast_config = None
        args.max_episodes = 5
        args.large_context = False
        args.verbose = False
        
        # Run seed_podcasts
        exit_code = seed_podcasts(args)
        
        # Verify
        assert exit_code == 1  # Failure when all episodes fail
    
    @patch('cli.VTTKnowledgeExtractor')
    def test_health_check_success(self, mock_pipeline_class):
        """Test successful health check."""
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline.initialize_components.return_value = True
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create args
        args = Mock()
        args.config = None
        args.large_context = False
        args.verbose = False
        
        # Run health check
        exit_code = health_check(args)
        
        # Verify
        assert exit_code == 0
        mock_pipeline.initialize_components.assert_called_once_with(use_large_context=False)
        mock_pipeline.cleanup.assert_called_once()
    
    @patch('cli.VTTKnowledgeExtractor')
    def test_health_check_failure(self, mock_pipeline_class):
        """Test failed health check."""
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline.initialize_components.return_value = False
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create args
        args = Mock()
        args.config = None
        args.large_context = True
        args.verbose = False
        
        # Run health check
        exit_code = health_check(args)
        
        # Verify
        assert exit_code == 1
        mock_pipeline.initialize_components.assert_called_once_with(use_large_context=True)
    
    @patch('cli.Config')
    def test_validate_config_success(self, mock_config_class):
        """Test successful config validation."""
        # Create mock config
        mock_config = Mock()
        mock_config.neo4j_uri = 'neo4j://localhost:7687'
        mock_config.model_name = 'gemini-pro'
        mock_config.batch_size = 10
        mock_config.max_workers = 4
        mock_config.checkpoint_enabled = True
        mock_config_class.from_file.return_value = mock_config
        
        # Create args
        args = Mock()
        args.config = 'config/test.yml'
        
        # Run validate config
        exit_code = validate_config(args)
        
        # Verify
        assert exit_code == 0
        mock_config_class.from_file.assert_called_once_with('config/test.yml')
    
    @patch('cli.Config')
    def test_validate_config_failure(self, mock_config_class):
        """Test failed config validation."""
        # Make config loading fail
        mock_config_class.from_file.side_effect = ValueError("Invalid config")
        
        # Create args
        args = Mock()
        args.config = 'config/bad.yml'
        
        # Run validate config
        exit_code = validate_config(args)
        
        # Verify
        assert exit_code == 1
    
    @patch('sys.argv')
    def test_main_help(self, mock_argv):
        """Test CLI help output."""
        mock_argv.__getitem__.side_effect = lambda x: ['cli.py', '--help'][x]
        mock_argv.__len__.return_value = 2
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Help should exit with 0
        assert exc_info.value.code == 0
    
    @patch('sys.argv')
    @patch('cli.seed_podcasts')
    def test_main_seed_command(self, mock_seed_podcasts, mock_argv):
        """Test main with seed command."""
        mock_argv.__getitem__.side_effect = lambda x: [
            'cli.py', 'seed', '--rss-url', 'https://example.com/feed.xml'
        ][x]
        mock_argv.__len__.return_value = 4
        
        mock_seed_podcasts.return_value = 0
        
        exit_code = main()
        
        assert exit_code == 0
        mock_seed_podcasts.assert_called_once()
    
    @patch('sys.argv')
    @patch('cli.health_check')
    def test_main_health_command(self, mock_health_check, mock_argv):
        """Test main with health command."""
        mock_argv.__getitem__.side_effect = lambda x: ['cli.py', 'health'][x]
        mock_argv.__len__.return_value = 2
        
        mock_health_check.return_value = 0
        
        exit_code = main()
        
        assert exit_code == 0
        mock_health_check.assert_called_once()
    
    @patch('sys.argv')
    def test_main_no_command(self, mock_argv):
        """Test main with no command."""
        mock_argv.__getitem__.side_effect = lambda x: ['cli.py'][x]
        mock_argv.__len__.return_value = 1
        
        exit_code = main()
        
        assert exit_code == 1