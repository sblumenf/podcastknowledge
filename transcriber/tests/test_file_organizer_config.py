"""Tests for FileOrganizer with Config injection."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import json

from src.file_organizer import FileOrganizer, EpisodeMetadata
from src.config import Config


@pytest.mark.unit
class TestFileOrganizerWithConfig:
    """Test FileOrganizer functionality with Config injection."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock Config object."""
        config = Mock(spec=Config)
        config.output = Mock()
        config.output.default_dir = "/custom/output/dir"
        config.output.naming_pattern = "{podcast_name}/{date}_{episode_title}.vtt"
        config.output.sanitize_filenames = True
        config.output.max_filename_length = 150
        return config
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp
    
    def test_init_with_config(self, mock_config, temp_dir):
        """Test FileOrganizer initialization with config."""
        mock_config.output.default_dir = temp_dir
        
        organizer = FileOrganizer(config=mock_config)
        
        assert organizer.config == mock_config
        assert str(organizer.base_dir) == temp_dir
        assert Path(temp_dir).exists()
    
    def test_init_base_dir_overrides_config(self, mock_config, temp_dir):
        """Test that explicit base_dir overrides config."""
        custom_dir = f"{temp_dir}/custom"
        
        organizer = FileOrganizer(base_dir=custom_dir, config=mock_config)
        
        assert str(organizer.base_dir) == custom_dir
        assert Path(custom_dir).exists()
    
    def test_init_without_config_uses_default(self, temp_dir):
        """Test FileOrganizer initialization without config uses default."""
        with patch('src.file_organizer.Path.mkdir'):
            organizer = FileOrganizer()
            
        assert organizer.config is None
        assert str(organizer.base_dir) == "data/transcripts"
    
    def test_sanitize_filename_with_config(self, mock_config):
        """Test filename sanitization respects config settings."""
        organizer = FileOrganizer(base_dir="/test", config=mock_config)
        
        # Test with max length from config
        long_name = "a" * 200
        result = organizer.sanitize_filename(long_name)
        assert len(result) == 150  # Config max_filename_length
        
    def test_sanitize_filename_disabled(self, mock_config):
        """Test filename sanitization when disabled in config."""
        mock_config.output.sanitize_filenames = False
        organizer = FileOrganizer(base_dir="/test", config=mock_config)
        
        # When sanitization is disabled, only strip whitespace
        test_name = "  Test Episode: Special Characters!?  "
        result = organizer.sanitize_filename(test_name)
        assert result == "Test Episode: Special Characters!?"
    
    def test_generate_filename_with_custom_pattern(self, mock_config, temp_dir):
        """Test filename generation with custom naming pattern from config."""
        # Test different naming patterns
        mock_config.output.naming_pattern = "{date}/{podcast_name}_{episode_title}.vtt"
        mock_config.output.default_dir = temp_dir
        
        organizer = FileOrganizer(config=mock_config)
        
        relative_path, full_path = organizer.generate_filename(
            "Tech Talk",
            "AI Innovations",
            "2024-01-15"
        )
        
        assert relative_path == "2024-01-15/Tech_Talk_AI_Innovations.vtt"
        assert full_path == str(Path(temp_dir) / relative_path)
    
    def test_generate_filename_without_directory_in_pattern(self, mock_config, temp_dir):
        """Test filename generation when pattern has no directory."""
        mock_config.output.naming_pattern = "{date}_{podcast_name}_{episode_title}"
        mock_config.output.default_dir = temp_dir
        
        organizer = FileOrganizer(config=mock_config)
        
        relative_path, full_path = organizer.generate_filename(
            "Tech Talk",
            "AI Innovations", 
            "2024-01-15"
        )
        
        # Should use podcast name as directory
        assert relative_path == "Tech_Talk/2024-01-15_Tech_Talk_AI_Innovations.vtt"
    
    def test_create_episode_file_with_config(self, mock_config, temp_dir):
        """Test creating episode file with config settings."""
        mock_config.output.default_dir = temp_dir
        
        organizer = FileOrganizer(config=mock_config)
        
        metadata = organizer.create_episode_file(
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            publication_date="2024-01-15",
            speakers=["Host", "Guest"],
            content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v Host>Welcome to the show!"
        )
        
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.title == "Test Episode"
        
        # Check file was created in the right place
        expected_path = Path(temp_dir) / "Test_Podcast" / "2024-01-15_Test_Episode.vtt"
        assert expected_path.exists()
    
    def test_backward_compatibility(self, temp_dir):
        """Test that FileOrganizer still works without config (backward compatibility)."""
        organizer = FileOrganizer(base_dir=temp_dir)
        
        # Should work without config
        assert organizer.config is None
        
        # Test sanitize_filename works with default behavior
        result = organizer.sanitize_filename("Test: Episode!")
        assert result == "Test_Episode"
        
        # Test generate_filename works with default pattern
        relative_path, full_path = organizer.generate_filename(
            "Podcast Name",
            "Episode Title",
            "2024-01-15"
        )
        assert relative_path == "Podcast_Name/2024-01-15_Episode_Title.vtt"
    
    def test_manifest_format_with_config(self, mock_config, temp_dir):
        """Test that manifest format is consistent with and without config."""
        mock_config.output.default_dir = temp_dir
        
        # Create organizer with config
        organizer = FileOrganizer(config=mock_config)
        
        # Add an episode
        organizer.episodes.append(EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2024-01-15",
            file_path="test.vtt",
            speakers=["Host"]
        ))
        
        # Save manifest
        organizer._save_manifest()
        
        # Load and check manifest
        manifest_path = Path(temp_dir) / "manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        
        # Should have production format (not test format)
        assert 'version' in data
        assert 'total_episodes' in data
        assert data['total_episodes'] == 1