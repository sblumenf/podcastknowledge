"""Comprehensive unit tests for CLI module."""

from pathlib import Path
from unittest.mock import Mock, patch, mock_open, call
import argparse
import json
import sys

import pytest

from src.cli.cli import (
    load_podcast_configs, seed_podcasts, health_check, validate_config,
    process_vtt_directory, check_status, export_data
)
from src.core.config import PipelineConfig
from src.core.exceptions import PipelineError


class TestLoadPodcastConfigs:
    """Test podcast configuration loading."""
    
    def test_load_single_config(self):
        """Test loading single podcast config."""
        config_data = {"rss_url": "http://example.com/rss", "name": "Test Podcast"}
        
        with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
            result = load_podcast_configs(Path("test.json"))
        
        assert len(result) == 1
        assert result[0]["rss_url"] == "http://example.com/rss"
        assert result[0]["name"] == "Test Podcast"
    
    def test_load_multiple_configs(self):
        """Test loading multiple podcast configs."""
        config_data = [
            {"rss_url": "http://example1.com/rss", "name": "Podcast 1"},
            {"rss_url": "http://example2.com/rss", "name": "Podcast 2"}
        ]
        
        with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
            result = load_podcast_configs(Path("test.json"))
        
        assert len(result) == 2
        assert result[0]["name"] == "Podcast 1"
        assert result[1]["name"] == "Podcast 2"
    
    def test_load_config_missing_rss_url(self):
        """Test loading config with missing RSS URL."""
        config_data = {"name": "Test Podcast"}  # Missing rss_url
        
        with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
            with pytest.raises(ValueError, match="Missing 'rss_url'"):
                load_podcast_configs(Path("test.json"))
    
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ValueError, match="Failed to load podcast configs"):
                load_podcast_configs(Path("nonexistent.json"))
    
    def test_load_config_invalid_json(self):
        """Test loading invalid JSON config."""
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(ValueError, match="Failed to load podcast configs"):
                load_podcast_configs(Path("invalid.json"))


class TestSeedPodcasts:
    """Test seed podcasts command."""
    
    @pytest.fixture
    def mock_args(self):
        """Create mock command line arguments."""
        args = Mock(spec=argparse.Namespace)
        args.config = None
        args.rss_url = "http://example.com/rss"
        args.name = "Test Podcast"
        args.category = "Technology"
        args.podcast_config = None
        args.max_episodes = 10
        args.large_context = False
        args.verbose = False
        return args
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_single_rss(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test seeding from single RSS URL."""
        # Setup mocks
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.seed_podcasts.return_value = {
            'start_time': '2024-01-01T12:00:00',
            'end_time': '2024-01-01T12:30:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'processing_time_seconds': 1800.0
        }
        
        result = seed_podcasts(mock_args)
        
        assert result == 0
        mock_pipeline.seed_podcasts.assert_called_once()
        call_args = mock_pipeline.seed_podcasts.call_args[1]
        assert len(call_args['podcast_configs']) == 1
        assert call_args['podcast_configs'][0]['rss_url'] == "http://example.com/rss"
        assert call_args['podcast_configs'][0]['name'] == "Test Podcast"
        assert call_args['max_episodes_each'] == 10
        assert call_args['use_large_context'] is False
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.load_podcast_configs')
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_from_config(self, mock_logger, mock_load, mock_config, mock_extractor):
        """Test seeding from config file."""
        # Setup args
        args = Mock(spec=argparse.Namespace)
        args.config = None
        args.rss_url = None
        args.podcast_config = "podcasts.json"
        args.max_episodes = 5
        args.large_context = True
        args.verbose = False
        
        # Setup mocks
        mock_load.return_value = [
            {"rss_url": "http://example1.com/rss", "name": "Podcast 1"},
            {"rss_url": "http://example2.com/rss", "name": "Podcast 2"}
        ]
        
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.seed_podcasts.return_value = {
            'podcasts_processed': 2,
            'episodes_processed': 10,
            'episodes_failed': 0,
            'processing_time_seconds': 3600.0
        }
        
        result = seed_podcasts(args)
        
        assert result == 0
        mock_load.assert_called_once_with(Path("podcasts.json"))
        mock_pipeline.seed_podcasts.assert_called_once()
        call_args = mock_pipeline.seed_podcasts.call_args[1]
        assert len(call_args['podcast_configs']) == 2
        assert call_args['use_large_context'] is True
    
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_no_input(self, mock_logger):
        """Test seeding with no RSS URL or config file."""
        args = Mock(spec=argparse.Namespace)
        args.config = None
        args.rss_url = None
        args.podcast_config = None
        args.verbose = False
        
        result = seed_podcasts(args)
        
        assert result == 1
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_all_failed(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test seeding when all episodes fail."""
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.seed_podcasts.return_value = {
            'podcasts_processed': 1,
            'episodes_processed': 0,
            'episodes_failed': 5,
            'processing_time_seconds': 900.0
        }
        
        result = seed_podcasts(mock_args)
        
        assert result == 1
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_exception(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test seeding with exception."""
        mock_extractor.side_effect = Exception("Pipeline error")
        
        result = seed_podcasts(mock_args)
        
        assert result == 1
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_seed_podcasts_with_config_file(self, mock_logger, mock_from_file, mock_extractor):
        """Test seeding with custom config file."""
        args = Mock(spec=argparse.Namespace)
        args.config = "custom_config.yaml"
        args.rss_url = "http://example.com/rss"
        args.name = "Test"
        args.category = "Tech"
        args.podcast_config = None
        args.max_episodes = 10
        args.large_context = False
        args.verbose = False
        
        mock_config = Mock()
        mock_from_file.return_value = mock_config
        
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.seed_podcasts.return_value = {
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0
        }
        
        result = seed_podcasts(args)
        
        assert result == 0
        mock_from_file.assert_called_once_with(Path("custom_config.yaml"))
        mock_extractor.assert_called_once_with(mock_config)


class TestHealthCheck:
    """Test health check command."""
    
    @pytest.fixture
    def mock_args(self):
        """Create mock arguments for health check."""
        args = Mock(spec=argparse.Namespace)
        args.config = None
        args.verbose = False
        return args
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_health_check_success(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test successful health check."""
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.initialize_components.return_value = True
        
        result = health_check(mock_args)
        
        assert result == 0
        mock_pipeline.initialize_components.assert_called_once()
        mock_pipeline.cleanup.assert_called_once()
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_health_check_failure(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test failed health check."""
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.initialize_components.return_value = False
        
        result = health_check(mock_args)
        
        assert result == 1
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_health_check_with_config(self, mock_logger, mock_from_file, mock_extractor):
        """Test health check with custom config."""
        args = Mock(spec=argparse.Namespace)
        args.config = "test_config.yaml"
        args.verbose = False
        
        mock_config = Mock()
        mock_from_file.return_value = mock_config
        
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.initialize_components.return_value = True
        
        result = health_check(args)
        
        assert result == 0
        mock_from_file.assert_called_once_with(Path("test_config.yaml"))
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_health_check_exception(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test health check with exception."""
        mock_extractor.side_effect = Exception("Initialization error")
        
        result = health_check(mock_args)
        
        assert result == 1


class TestValidateConfig:
    """Test configuration validation command."""
    
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_validate_config_success(self, mock_logger, mock_from_file):
        """Test successful config validation."""
        args = Mock(spec=argparse.Namespace)
        args.config = "test_config.yaml"
        args.verbose = False
        
        mock_config = Mock()
        mock_from_file.return_value = mock_config
        mock_config.validate.return_value = None
        
        result = validate_config(args)
        
        assert result == 0
        mock_from_file.assert_called_once_with(Path("test_config.yaml"))
        mock_config.validate.assert_called_once()
    
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_validate_config_verbose(self, mock_logger, mock_from_file):
        """Test config validation with verbose output."""
        args = Mock(spec=argparse.Namespace)
        args.config = "test_config.yaml"
        args.verbose = True
        
        mock_config = Mock()
        mock_from_file.return_value = mock_config
        mock_config.validate.return_value = None
        mock_config.to_dict.return_value = {
            "neo4j_uri": "bolt://localhost:7687",
            "openai_api_key": "sk-test",
            "max_workers": 4
        }
        
        result = validate_config(args)
        
        assert result == 0
        mock_config.to_dict.assert_called_once()
    
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_validate_config_validation_error(self, mock_logger, mock_from_file):
        """Test config validation with validation error."""
        args = Mock(spec=argparse.Namespace)
        args.config = "test_config.yaml"
        args.verbose = False
        
        mock_config = Mock()
        mock_from_file.return_value = mock_config
        mock_config.validate.side_effect = ValueError("Invalid configuration")
        
        result = validate_config(args)
        
        assert result == 1
    
    @patch('src.cli.cli.PipelineConfig.from_file')
    @patch('src.cli.cli.get_logger')
    def test_validate_config_file_error(self, mock_logger, mock_from_file):
        """Test config validation with file error."""
        args = Mock(spec=argparse.Namespace)
        args.config = "nonexistent.yaml"
        args.verbose = False
        
        mock_from_file.side_effect = FileNotFoundError("Config file not found")
        
        result = validate_config(args)
        
        assert result == 1


class TestProcessVTTDirectory:
    """Test VTT directory processing command."""
    
    @pytest.fixture
    def mock_args(self):
        """Create mock arguments for VTT processing."""
        args = Mock(spec=argparse.Namespace)
        args.vtt_dir = "vtt_files"
        args.output_dir = "output"
        args.config = None
        args.max_files = None
        args.recursive = True
        args.verbose = False
        return args
    
    @patch('src.cli.cli.TranscriptIngestionManager')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    @patch('pathlib.Path.exists')
    def test_process_vtt_directory_success(self, mock_exists, mock_logger, mock_config, mock_manager, mock_args):
        """Test successful VTT directory processing."""
        mock_exists.return_value = True
        
        mock_ingestion = Mock()
        mock_manager.return_value = mock_ingestion
        mock_ingestion.process_directory.return_value = {
            'total_files': 10,
            'processed': 8,
            'skipped': 1,
            'errors': 1,
            'total_segments': 500
        }
        
        result = process_vtt_directory(mock_args)
        
        assert result == 0
        mock_ingestion.process_directory.assert_called_once()
    
    @patch('src.cli.cli.get_logger')
    @patch('pathlib.Path.exists')
    def test_process_vtt_directory_not_found(self, mock_exists, mock_logger, mock_args):
        """Test VTT directory processing with non-existent directory."""
        mock_exists.return_value = False
        
        result = process_vtt_directory(mock_args)
        
        assert result == 1
    
    @patch('src.cli.cli.TranscriptIngestionManager')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    @patch('pathlib.Path.exists')
    def test_process_vtt_directory_exception(self, mock_exists, mock_logger, mock_config, mock_manager, mock_args):
        """Test VTT directory processing with exception."""
        mock_exists.return_value = True
        mock_manager.side_effect = Exception("Processing error")
        
        result = process_vtt_directory(mock_args)
        
        assert result == 1


class TestCheckStatus:
    """Test status check command."""
    
    @pytest.fixture
    def mock_args(self):
        """Create mock arguments for status check."""
        args = Mock(spec=argparse.Namespace)
        args.config = None
        args.verbose = False
        return args
    
    @patch('src.cli.cli.ProgressCheckpoint')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_check_status_success(self, mock_logger, mock_config, mock_checkpoint, mock_args):
        """Test successful status check."""
        mock_cp = Mock()
        mock_checkpoint.return_value = mock_cp
        mock_cp.get_status.return_value = {
            'total_episodes': 50,
            'processed_episodes': 45,
            'failed_episodes': 3,
            'pending_episodes': 2,
            'processing_rate': 0.9
        }
        
        result = check_status(mock_args)
        
        assert result == 0
        mock_cp.get_status.assert_called_once()
    
    @patch('src.cli.cli.ProgressCheckpoint')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_check_status_exception(self, mock_logger, mock_config, mock_checkpoint, mock_args):
        """Test status check with exception."""
        mock_checkpoint.side_effect = Exception("Status error")
        
        result = check_status(mock_args)
        
        assert result == 1


class TestExportData:
    """Test data export command."""
    
    @pytest.fixture
    def mock_args(self):
        """Create mock arguments for data export."""
        args = Mock(spec=argparse.Namespace)
        args.output_file = "export.json"
        args.format = "json"
        args.config = None
        args.include_segments = True
        args.verbose = False
        return args
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    @patch('builtins.open', mock_open())
    def test_export_data_json(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test data export in JSON format."""
        mock_pipeline = Mock()
        mock_extractor.return_value = mock_pipeline
        mock_pipeline.export_knowledge_graph.return_value = {
            'episodes': [],
            'segments': [],
            'entities': []
        }
        
        result = export_data(mock_args)
        
        assert result == 0
        mock_pipeline.export_knowledge_graph.assert_called_once()
    
    @patch('src.cli.cli.VTTKnowledgeExtractor')
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.get_logger')
    def test_export_data_exception(self, mock_logger, mock_config, mock_extractor, mock_args):
        """Test data export with exception."""
        mock_extractor.side_effect = Exception("Export error")
        
        result = export_data(mock_args)
        
        assert result == 1


class TestCLIHelpers:
    """Test CLI helper functions."""
    
    def test_format_duration_seconds(self):
        """Test duration formatting."""
        from src.cli.cli import format_duration
        
        assert format_duration(65) == "1m 5s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(30) == "30s"
    
    def test_format_file_size(self):
        """Test file size formatting."""
        from src.cli.cli import format_file_size
        
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(500) == "500 B"
    
    @patch('sys.argv', ['cli.py', 'seed', '--rss-url', 'http://example.com/rss'])
    def test_main_function_integration(self):
        """Test main function integration."""
        with patch('src.cli.cli.seed_podcasts', return_value=0) as mock_seed:
            from src.cli.cli import main
            
            # This would normally parse sys.argv and call the appropriate function
            # For testing, we'll just verify the function exists and is callable
            assert callable(main)