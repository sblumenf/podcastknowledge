"""Integration tests for FileOrganizer with Config."""

import pytest
import tempfile
from pathlib import Path

from src.file_organizer import FileOrganizer
from src.config import Config


@pytest.mark.integration
class TestFileOrganizerIntegration:
    """Test FileOrganizer integration with real Config."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp
    
    @pytest.fixture
    def test_config(self, temp_dir):
        """Create a test config with custom settings."""
        # Create test config
        config = Config.create_test_config()
        
        # Override some settings
        config.output.default_dir = temp_dir
        config.output.naming_pattern = "{podcast_name}/episodes/{date}_{episode_title}.vtt"
        config.output.max_filename_length = 100
        config.output.sanitize_filenames = True
        
        return config
    
    def test_full_workflow_with_config(self, test_config):
        """Test complete workflow with config injection."""
        # Create organizer with config
        organizer = FileOrganizer(config=test_config)
        
        # Create multiple episodes
        episodes = [
            {
                "podcast_name": "Tech Talks",
                "episode_title": "Introduction to AI",
                "publication_date": "2024-01-01",
                "speakers": ["Dr. Smith", "John Doe"],
                "content": "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v Dr. Smith>Welcome everyone!"
            },
            {
                "podcast_name": "Tech Talks",
                "episode_title": "Machine Learning Basics",
                "publication_date": "2024-01-08",
                "speakers": ["Dr. Smith", "Jane Doe"],
                "content": "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v Dr. Smith>Let's talk about ML!"
            },
            {
                "podcast_name": "Science Hour",
                "episode_title": "Quantum Computing",
                "publication_date": "2024-01-10",
                "speakers": ["Prof. Johnson"],
                "content": "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v Prof. Johnson>Quantum mechanics..."
            }
        ]
        
        # Create all episodes
        for ep in episodes:
            metadata = organizer.create_episode_file(**ep)
            assert metadata is not None
        
        # Verify directory structure follows custom pattern
        tech_talks_dir = Path(test_config.output.default_dir) / "Tech_Talks" / "episodes"
        science_hour_dir = Path(test_config.output.default_dir) / "Science_Hour" / "episodes"
        
        assert tech_talks_dir.exists()
        assert science_hour_dir.exists()
        
        # Check files exist with correct naming
        assert (tech_talks_dir / "2024-01-01_Introduction_to_AI.vtt").exists()
        assert (tech_talks_dir / "2024-01-08_Machine_Learning_Basics.vtt").exists()
        assert (science_hour_dir / "2024-01-10_Quantum_Computing.vtt").exists()
        
        # Test statistics
        stats = organizer.get_stats()
        assert stats['total_episodes'] == 3
        assert stats['total_podcasts'] == 2
        
        # Test search functionality
        tech_episodes = organizer.get_episodes_by_podcast("Tech Talks")
        assert len(tech_episodes) == 2
        
        # Test date range search
        jan_episodes = organizer.get_episodes_by_date_range("2024-01-01", "2024-01-08")
        assert len(jan_episodes) == 2
        
        # Test speaker search
        smith_episodes = organizer.get_episodes_by_speaker("Dr. Smith")
        assert len(smith_episodes) == 2
    
    def test_filename_length_limit_from_config(self, test_config):
        """Test that filename length limit from config is respected."""
        test_config.output.max_filename_length = 50
        
        organizer = FileOrganizer(config=test_config)
        
        # Create episode with very long title
        long_title = "This is a very long episode title that should be truncated according to the configuration settings"
        
        metadata = organizer.create_episode_file(
            podcast_name="Test Podcast",
            episode_title=long_title,
            publication_date="2024-01-15",
            speakers=["Host"],
            content="WEBVTT\n\nTest content"
        )
        
        # Check that filename was truncated
        filename = Path(metadata.file_path).name
        # Remove .vtt extension and date prefix for length check
        name_part = filename.replace(".vtt", "").split("_", 1)[1]
        assert len(name_part) <= 50
    
    def test_sanitization_toggle(self, test_config):
        """Test enabling/disabling filename sanitization via config."""
        # First with sanitization enabled
        test_config.output.sanitize_filenames = True
        organizer_sanitized = FileOrganizer(config=test_config)
        
        result_sanitized = organizer_sanitized.sanitize_filename("Episode: Test!")
        assert result_sanitized == "Episode_Test"
        
        # Now with sanitization disabled
        test_config.output.sanitize_filenames = False
        organizer_unsanitized = FileOrganizer(config=test_config)
        
        result_unsanitized = organizer_unsanitized.sanitize_filename("Episode: Test!")
        assert result_unsanitized == "Episode: Test!"
    
    def test_manifest_with_config(self, test_config):
        """Test that manifest works correctly with config."""
        organizer = FileOrganizer(config=test_config)
        
        # Create an episode
        organizer.create_episode_file(
            podcast_name="Test Pod",
            episode_title="Test Episode",
            publication_date="2024-01-20",
            speakers=["Host"],
            content="WEBVTT\n\nContent",
            duration=1800,
            episode_number=1,
            description="Test description"
        )
        
        # Reload organizer to test manifest loading
        new_organizer = FileOrganizer(config=test_config)
        
        assert len(new_organizer.episodes) == 1
        episode = new_organizer.episodes[0]
        assert episode.title == "Test Episode"
        assert episode.duration == 1800
        assert episode.episode_number == 1
        assert episode.description == "Test description"