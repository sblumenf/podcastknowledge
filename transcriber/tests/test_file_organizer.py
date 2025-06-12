"""Unit tests for the file organizer module."""

import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.file_organizer import EpisodeMetadata, FileOrganizer


@pytest.mark.unit
class TestEpisodeMetadata:
    """Test EpisodeMetadata dataclass."""
    
    def test_episode_metadata_creation(self):
        """Test creating episode metadata."""
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date=datetime(2024, 1, 15),
            file_path="Test_Podcast/2024-01-15_Test_Episode.vtt",
            speakers=["Host", "Guest"],
            duration=3600,
            episode_number=10,
            description="Test description"
        )
        
        assert metadata.title == "Test Episode"
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.publication_date == datetime(2024, 1, 15)
        assert metadata.file_path == "Test_Podcast/2024-01-15_Test_Episode.vtt"
        assert len(metadata.speakers) == 2
        assert metadata.duration == 3600
        assert metadata.episode_number == 10
    
    def test_episode_metadata_auto_processed_date(self):
        """Test automatic processed date generation."""
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date=datetime(2024, 1, 15),
            file_path="test.vtt",
            speakers=[]
        )
        
        assert metadata.processed_date != ""
        # Check date format
        datetime.strptime(metadata.processed_date, "%Y-%m-%d %H:%M:%S")
    
    def test_episode_metadata_custom_processed_date(self):
        """Test custom processed date."""
        custom_date = "2024-01-20 10:00:00"
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date=datetime(2024, 1, 15),
            file_path="test.vtt",
            speakers=[],
            processed_date=custom_date
        )
        
        assert metadata.processed_date == custom_date


@pytest.mark.unit
class TestFileOrganizer:
    """Test FileOrganizer class."""
    
    @pytest.fixture
    def organizer(self, tmp_path):
        """Create a file organizer for testing."""
        return FileOrganizer(base_dir=str(tmp_path))
    
    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates base directory."""
        base_path = tmp_path / "transcripts"
        organizer = FileOrganizer(base_dir=str(base_path))
        
        assert base_path.exists()
        assert base_path.is_dir()
    
    def test_init_loads_existing_manifest(self, tmp_path):
        """Test loading existing manifest on initialization."""
        # Create manifest file
        manifest_data = {
            'version': '1.0',
            'episodes': [
                {
                    'title': 'Existing Episode',
                    'podcast_name': 'Test Podcast',
                    'publication_date': '2024-01-10',
                    'file_path': 'Test_Podcast/2024-01-10_Existing_Episode.vtt',
                    'speakers': ['Host'],
                    'processed_date': '2024-01-10 10:00:00'
                }
            ]
        }
        
        manifest_path = Path(tmp_path) / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f)
        
        organizer = FileOrganizer(base_dir=tmp_path)
        
        assert len(organizer.episodes) == 1
        assert organizer.episodes[0].title == 'Existing Episode'
        assert 'Test_Podcast/2024-01-10_Existing_Episode.vtt' in organizer._used_filenames
    
    def test_sanitize_filename_basic(self, organizer):
        """Test basic filename sanitization."""
        assert organizer.sanitize_filename("Normal Title") == "Normal_Title"
        assert organizer.sanitize_filename("Title: With Colon") == "Title_With_Colon"
        assert organizer.sanitize_filename("Title/With\\Slashes") == "Title__WithSlashes"
        assert organizer.sanitize_filename("Title?With*Special|Chars") == "TitleWithSpecialChars"
    
    def test_sanitize_filename_edge_cases(self, organizer):
        """Test filename sanitization edge cases."""
        # Empty or whitespace
        assert organizer.sanitize_filename("") == "unknown"
        assert organizer.sanitize_filename("   ") == "untitled"
        
        # Multiple spaces
        assert organizer.sanitize_filename("Multiple   Spaces") == "Multiple_Spaces"
        
        # Leading/trailing special chars
        assert organizer.sanitize_filename("...Title...") == "Title"
        assert organizer.sanitize_filename("___Title___") == "Title"
        
        # Very long title
        long_title = "A" * 250
        sanitized = organizer.sanitize_filename(long_title)
        assert len(sanitized) <= 200
        
        # Only special characters
        assert organizer.sanitize_filename("!@#$%^&*()") == "&()"
        assert organizer.sanitize_filename("<<<>>>") == "untitled"
    
    def test_generate_filename_basic(self, organizer):
        """Test basic filename generation."""
        relative_path, full_path = organizer.generate_filename(
            "Test Podcast",
            "Episode Title",
            "2024-01-15"
        )
        
        assert relative_path == "Test_Podcast/2024-01-15_Episode_Title.vtt"
        assert full_path.endswith("Test_Podcast/2024-01-15_Episode_Title.vtt")
    
    def test_generate_filename_duplicate_handling(self, organizer):
        """Test handling of duplicate filenames."""
        # Generate first filename
        path1, _ = organizer.generate_filename(
            "Test Podcast",
            "Same Title",
            "2024-01-15"
        )
        
        # Add to used filenames to simulate it being used
        organizer._used_filenames.add(path1)
        
        # Generate second with same params - should add counter
        path2, _ = organizer.generate_filename(
            "Test Podcast",
            "Same Title",
            "2024-01-15"
        )
        
        assert path1 == "Test_Podcast/2024-01-15_Same_Title.vtt"
        assert path2 == "Test_Podcast/2024-01-15_Same_Title_2.vtt"
    
    def test_generate_filename_invalid_date(self, organizer):
        """Test filename generation with invalid date."""
        from datetime import datetime as real_datetime
        
        # Save the original datetime module
        import src.file_organizer
        original_datetime = src.file_organizer.datetime
        
        with patch.object(src.file_organizer, 'datetime', wraps=real_datetime) as mock_datetime:
            # Mock only the specific methods we need
            mock_datetime.now.return_value = real_datetime(2024, 1, 20)
            mock_datetime.strptime.side_effect = ValueError("Invalid date")
            
            # Ensure isinstance still works with the real datetime class
            mock_datetime.__class__ = type(real_datetime)
            
            relative_path, _ = organizer.generate_filename(
                "Test Podcast",
                "Episode",
                "invalid-date"
            )
            
            assert "2024-01-20" in relative_path  # Should use current date
    
    def test_create_episode_file_success(self, organizer, tmp_path):
        """Test successful episode file creation."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v Host>Hello and welcome."""
        
        metadata = organizer.create_episode_file(
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            publication_date=datetime(2024, 1, 15),
            speakers=["Host", "Guest"],
            content=vtt_content,
            duration=1800,
            episode_number=5,
            description="Test description"
        )
        
        # Check metadata
        assert metadata.title == "Test Episode"
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.duration == 1800
        assert metadata.episode_number == 5
        
        # Check file was created
        file_path = Path(tmp_path) / metadata.file_path
        assert file_path.exists()
        
        # Check content
        with open(file_path, 'r') as f:
            content = f.read()
        assert content == vtt_content
        
        # Check episode was added to list
        assert len(organizer.episodes) == 1
        assert organizer.episodes[0] == metadata
        
        # Check manifest was saved
        manifest_path = Path(tmp_path) / "manifest.json"
        assert manifest_path.exists()
    
    def test_create_episode_file_error(self, organizer):
        """Test episode file creation with write error."""
        with patch('builtins.open', side_effect=IOError("Write error")):
            with pytest.raises(IOError):
                organizer.create_episode_file(
                    podcast_name="Test",
                    episode_title="Test",
                    publication_date=datetime(2024, 1, 15),
                    speakers=[],
                    content="Content"
                )
    
    def test_save_and_load_manifest(self, organizer, tmp_path):
        """Test saving and loading manifest."""
        # Add some episodes
        metadata1 = EpisodeMetadata(
            title="Episode 1",
            podcast_name="Podcast A",
            publication_date=datetime(2024, 1, 10),
            file_path="Podcast_A/2024-01-10_Episode_1.vtt",
            speakers=["Host A"]
        )
        metadata2 = EpisodeMetadata(
            title="Episode 2",
            podcast_name="Podcast B",
            publication_date=datetime(2024, 1, 15),
            file_path="Podcast_B/2024-01-15_Episode_2.vtt",
            speakers=["Host B", "Guest"]
        )
        
        organizer.episodes.extend([metadata1, metadata2])
        organizer._save_manifest()
        
        # Create new organizer and load
        new_organizer = FileOrganizer(base_dir=tmp_path)
        
        assert len(new_organizer.episodes) == 2
        assert new_organizer.episodes[0].title == "Episode 1"
        assert new_organizer.episodes[1].title == "Episode 2"
    
    def test_get_episodes_by_podcast(self, organizer):
        """Test getting episodes by podcast name."""
        # Add episodes from different podcasts
        organizer.episodes = [
            EpisodeMetadata(
                title="Ep1", podcast_name="Podcast A", 
                publication_date=datetime(2024, 1, 1), file_path="a/1.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep2", podcast_name="Podcast A", 
                publication_date=datetime(2024, 1, 2), file_path="a/2.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep3", podcast_name="Podcast B", 
                publication_date=datetime(2024, 1, 3), file_path="b/3.vtt", speakers=[]
            )
        ]
        
        podcast_a_episodes = organizer.get_episodes_by_podcast("Podcast A")
        assert len(podcast_a_episodes) == 2
        assert all(ep.podcast_name == "Podcast A" for ep in podcast_a_episodes)
    
    def test_get_episodes_by_date_range(self, organizer):
        """Test getting episodes by date range."""
        organizer.episodes = [
            EpisodeMetadata(
                title="Ep1", podcast_name="Test", 
                publication_date=datetime(2024, 1, 10), file_path="1.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep2", podcast_name="Test", 
                publication_date=datetime(2024, 1, 15), file_path="2.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep3", podcast_name="Test", 
                publication_date=datetime(2024, 1, 20), file_path="3.vtt", speakers=[]
            )
        ]
        
        episodes = organizer.get_episodes_by_date_range("2024-01-12", "2024-01-18")
        assert len(episodes) == 1
        assert episodes[0].title == "Ep2"
    
    def test_get_episodes_by_speaker(self, organizer):
        """Test getting episodes by speaker."""
        organizer.episodes = [
            EpisodeMetadata(
                title="Ep1", podcast_name="Test", publication_date=datetime(2024, 1, 1),
                file_path="1.vtt", speakers=["John Doe", "Jane Smith"]
            ),
            EpisodeMetadata(
                title="Ep2", podcast_name="Test", publication_date=datetime(2024, 1, 2),
                file_path="2.vtt", speakers=["Bob Johnson"]
            ),
            EpisodeMetadata(
                title="Ep3", podcast_name="Test", publication_date=datetime(2024, 1, 3),
                file_path="3.vtt", speakers=["Jane Smith", "Bob Johnson"]
            )
        ]
        
        # Case insensitive search
        jane_episodes = organizer.get_episodes_by_speaker("jane smith")
        assert len(jane_episodes) == 2
        assert "Ep1" in [ep.title for ep in jane_episodes]
        assert "Ep3" in [ep.title for ep in jane_episodes]
    
    def test_get_directory_structure(self, organizer):
        """Test getting directory structure."""
        organizer.episodes = [
            EpisodeMetadata(
                title="Ep1", podcast_name="Podcast A", publication_date=datetime(2024, 1, 1),
                file_path="Podcast_A/2024-01-01_Ep1.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep2", podcast_name="Podcast A", publication_date=datetime(2024, 1, 2),
                file_path="Podcast_A/2024-01-02_Ep2.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Ep3", podcast_name="Podcast B", publication_date=datetime(2024, 1, 3),
                file_path="Podcast_B/2024-01-03_Ep3.vtt", speakers=[]
            )
        ]
        
        structure = organizer.get_directory_structure()
        
        assert "Podcast_A" in structure
        assert len(structure["Podcast_A"]) == 2
        assert "Podcast_B" in structure
        assert len(structure["Podcast_B"]) == 1
    
    def test_cleanup_empty_directories(self, organizer, tmp_path):
        """Test cleaning up empty directories."""
        # Create some directories
        empty_dir = Path(tmp_path) / "Empty_Podcast"
        empty_dir.mkdir()
        
        non_empty_dir = Path(tmp_path) / "Non_Empty_Podcast"
        non_empty_dir.mkdir()
        (non_empty_dir / "file.vtt").touch()
        
        organizer.cleanup_empty_directories()
        
        assert not empty_dir.exists()
        assert non_empty_dir.exists()
    
    def test_validate_files(self, organizer, tmp_path):
        """Test file validation."""
        # Add episodes to manifest
        organizer.episodes = [
            EpisodeMetadata(
                title="Exists", podcast_name="Test", publication_date=datetime(2024, 1, 1),
                file_path="Test/exists.vtt", speakers=[]
            ),
            EpisodeMetadata(
                title="Missing", podcast_name="Test", publication_date=datetime(2024, 1, 2),
                file_path="Test/missing.vtt", speakers=[]
            )
        ]
        
        # Create only one file
        test_dir = Path(tmp_path) / "Test"
        test_dir.mkdir()
        (test_dir / "exists.vtt").touch()
        
        # Create extra file not in manifest
        (test_dir / "extra.vtt").touch()
        
        validation = organizer.validate_files()
        
        assert len(validation['missing']) == 1
        assert "Test/missing.vtt" in validation['missing']
        assert len(validation['extra']) == 1
        assert "Test/extra.vtt" in validation['extra']
    
    def test_get_stats(self, organizer):
        """Test getting statistics."""
        # Empty stats
        stats = organizer.get_stats()
        assert stats['total_episodes'] == 0
        
        # Add episodes
        organizer.episodes = [
            EpisodeMetadata(
                title="Ep1", podcast_name="Podcast A", publication_date=datetime(2024, 1, 10),
                file_path="a/1.vtt", speakers=["Host", "Guest1"], duration=1800
            ),
            EpisodeMetadata(
                title="Ep2", podcast_name="Podcast A", publication_date=datetime(2024, 1, 15),
                file_path="a/2.vtt", speakers=["Host", "Guest2"], duration=2400
            ),
            EpisodeMetadata(
                title="Ep3", podcast_name="Podcast B", publication_date=datetime(2024, 1, 20),
                file_path="b/3.vtt", speakers=["Host2"], duration=3600
            )
        ]
        
        stats = organizer.get_stats()
        
        assert stats['total_episodes'] == 3
        assert stats['total_podcasts'] == 2
        assert stats['total_speakers'] == 4  # Host, Guest1, Guest2, Host2
        assert stats['date_range'] == ("2024-01-10", "2024-01-20")
        assert stats['total_duration_seconds'] == 7800
        assert stats['total_duration_hours'] == 2.17
        assert stats['average_episode_duration'] == 2600.0