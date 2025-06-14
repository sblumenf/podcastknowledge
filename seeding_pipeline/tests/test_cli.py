"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import tempfile

import pytest
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.cli import main, load_podcast_configs, process_vtt, checkpoint_status, checkpoint_clean, validate_vtt_file, find_vtt_files
from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline


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
    
    @patch('src.cli.cli.PipelineConfig')
    @patch('src.cli.cli.EnhancedKnowledgePipeline')
    def test_process_vtt_dry_run(self, mock_pipeline_class, mock_config_class):
        """Test dry run mode for VTT processing."""
        # Create mock config
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        # Create mock pipeline instance
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create test VTT file
        temp_dir = tempfile.mkdtemp()
        test_file = Path(temp_dir) / 'test.vtt'
        test_file.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest content')
        
        # Create args
        args = Mock()
        args.config = None
        args.folder = temp_dir
        args.pattern = '*.vtt'
        args.recursive = False
        args.dry_run = True
        args.skip_errors = False
        args.no_checkpoint = True
        args.checkpoint_dir = 'checkpoints'
        args.verbose = False
        
        # Run process_vtt
        exit_code = process_vtt(args)
        
        # Verify
        assert exit_code == 0
        mock_pipeline_class.assert_called_once()
        # In dry run, process_vtt_file should NOT be called
        mock_pipeline.cleanup.assert_called_once()
    
    def test_checkpoint_status_deprecated(self):
        """Test checkpoint status command shows deprecation message."""
        # Create temporary checkpoint directory
        temp_dir = tempfile.mkdtemp()
        checkpoint_dir = Path(temp_dir) / 'checkpoints'
        checkpoint_dir.mkdir()
        
        # Create args
        args = Mock()
        args.checkpoint_dir = str(checkpoint_dir)
        args.verbose = False
        
        # Run checkpoint_status
        exit_code = checkpoint_status(args)
        
        # Verify it returns success and shows deprecation
        assert exit_code == 0
    
    def test_checkpoint_clean(self):
        """Test checkpoint clean command."""
        # Create temporary checkpoint directory
        temp_dir = tempfile.mkdtemp()
        checkpoint_dir = Path(temp_dir) / 'checkpoints'
        checkpoint_dir.mkdir()
        
        # Create some checkpoint files
        (checkpoint_dir / 'vtt_checkpoint1.json').write_text('{}')
        (checkpoint_dir / 'vtt_checkpoint2.json').write_text('{}')
        
        # Create args
        args = Mock()
        args.checkpoint_dir = str(checkpoint_dir)
        args.pattern = None
        args.force = True
        args.verbose = False
        
        # Run checkpoint_clean
        exit_code = checkpoint_clean(args)
        
        # Verify
        assert exit_code == 0
        # Check files were deleted
        assert len(list(checkpoint_dir.glob('*.json'))) == 0
    
    def test_main_process_vtt_command(self):
        """Test main with process-vtt command."""
        with patch('sys.argv', ['cli.py', 'process-vtt', '--folder', '/tmp', '--dry-run']):
            with patch('src.cli.cli.process_vtt') as mock_process:
                mock_process.return_value = 0
                
                exit_code = main()
                
                assert exit_code == 0
                mock_process.assert_called_once()
    
    def test_main_checkpoint_status_command(self):
        """Test main with checkpoint-status command."""
        with patch('sys.argv', ['cli.py', 'checkpoint-status']):
            with patch('src.cli.cli.checkpoint_status') as mock_status:
                mock_status.return_value = 0
                
                exit_code = main()
                
                assert exit_code == 0
                mock_status.assert_called_once()
    
    def test_main_checkpoint_clean_command(self):
        """Test main with checkpoint-clean command."""
        with patch('sys.argv', ['cli.py', 'checkpoint-clean', '--force']):
            with patch('src.cli.cli.checkpoint_clean') as mock_clean:
                mock_clean.return_value = 0
                
                exit_code = main()
                
                assert exit_code == 0
                mock_clean.assert_called_once()
    
    def test_main_help(self):
        """Test CLI help output."""
        with patch('sys.argv', ['cli.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Help should exit with 0
            assert exc_info.value.code == 0
    
    def test_main_no_command(self):
        """Test main with no command."""
        with patch('sys.argv', ['cli.py']):
            exit_code = main()
            
            assert exit_code == 1
    
    def test_validate_vtt_file(self):
        """Test VTT file validation."""
        # Create valid VTT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write('WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest content')
            f.flush()
            
            is_valid, error = validate_vtt_file(Path(f.name))
            assert is_valid
            assert error is None
        
        # Test invalid file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Not a VTT file')
            f.flush()
            
            is_valid, error = validate_vtt_file(Path(f.name))
            assert not is_valid
            assert 'Not a VTT file' in error
    
    def test_find_vtt_files(self):
        """Test finding VTT files in directory."""
        # Create temporary directory with VTT files
        temp_dir = tempfile.mkdtemp()
        
        # Create some VTT files
        (Path(temp_dir) / 'file1.vtt').write_text('WEBVTT\n\ntest')
        (Path(temp_dir) / 'file2.vtt').write_text('WEBVTT\n\ntest')
        (Path(temp_dir) / 'other.txt').write_text('not vtt')
        
        # Test finding files
        vtt_files = find_vtt_files(Path(temp_dir))
        assert len(vtt_files) == 2
        assert all(f.suffix == '.vtt' for f in vtt_files)