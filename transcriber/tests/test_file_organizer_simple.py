"""Simple test suite for the File Organizer module focusing on core functionality."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.file_organizer import FileOrganizer, EpisodeMetadata
from src.config import Config


class TestEpisodeMetadata:
    """Test EpisodeMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating episode metadata."""
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2024-01-01",
            file_path="/path/to/file.vtt",
            speakers=["Host", "Guest"],
            duration=1800,
            episode_number=5
        )
        
        assert metadata.title == "Test Episode"
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.publication_date == "2024-01-01"
        assert metadata.file_path == "/path/to/file.vtt"
        assert metadata.speakers == ["Host", "Guest"]
        assert metadata.duration == 1800
        assert metadata.episode_number == 5
        assert metadata.processed_date != ""  # Auto-generated
    
    def test_metadata_auto_processed_date(self):
        """Test automatic processed date generation."""
        metadata = EpisodeMetadata(
            title="Test",
            podcast_name="Test",
            publication_date="2024-01-01",
            file_path="/test.vtt",
            speakers=[]
        )
        
        # Should have auto-generated processed date
        assert metadata.processed_date != ""
        assert "2025" in metadata.processed_date  # Current year


class TestFileOrganizer:
    """Test FileOrganizer class core functionality."""
    
    @pytest.fixture
    def temp_base_dir(self, tmp_path):
        """Create temporary base directory."""
        base_dir = tmp_path / "transcripts"
        base_dir.mkdir()
        return base_dir
    
    @pytest.fixture
    def organizer(self, temp_base_dir):
        """Create FileOrganizer instance."""
        return FileOrganizer(base_dir=str(temp_base_dir))
    
    def test_init_with_base_dir(self, temp_base_dir):
        """Test initialization with base directory."""
        organizer = FileOrganizer(base_dir=str(temp_base_dir))
        assert organizer.base_dir == Path(temp_base_dir)
        assert organizer.base_dir.exists()
    
    def test_init_with_config(self, temp_base_dir):
        """Test initialization with config."""
        mock_config = Mock(spec=Config)
        mock_config.get.return_value = str(temp_base_dir)
        
        organizer = FileOrganizer(config=mock_config)
        assert organizer.base_dir == Path(temp_base_dir)
        mock_config.get.assert_called_with('file_organizer.base_dir', 'data/transcripts')
    
    def test_sanitize_name(self, organizer):
        """Test name sanitization for directories/files."""
        # Test various problematic characters
        assert organizer._sanitize_name("Test/Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test:Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test?Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test<>Podcast") == "Test__Podcast"
        assert organizer._sanitize_name("Test|Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test\\Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test*Podcast") == "Test_Podcast"
        
        # Test spaces
        assert organizer._sanitize_name("Test Podcast") == "Test_Podcast"
        assert organizer._sanitize_name("Test  Podcast") == "Test__Podcast"
    
    def test_get_podcast_dir(self, organizer, temp_base_dir):
        """Test getting podcast-specific directory."""
        podcast_name = "Test Podcast"
        podcast_dir = organizer.get_podcast_dir(podcast_name)
        
        assert podcast_dir == temp_base_dir / "Test_Podcast"
        assert podcast_dir.exists()
        assert podcast_dir.is_dir()
    
    def test_generate_filename(self, organizer):
        """Test filename generation."""
        metadata = EpisodeMetadata(
            title="Episode Title",
            podcast_name="Test Podcast",
            publication_date="2024-01-15",
            file_path="/original.vtt",
            speakers=[],
            episode_number=42
        )
        
        filename = organizer.generate_filename(metadata)
        assert "2024-01-15" in filename
        assert "EP042" in filename
        assert "Episode_Title" in filename
        assert filename.endswith(".vtt")
    
    def test_generate_filename_no_episode_number(self, organizer):
        """Test filename generation without episode number."""
        metadata = EpisodeMetadata(
            title="Special Episode",
            podcast_name="Test Podcast",
            publication_date="2024-02-01",
            file_path="/original.vtt",
            speakers=[]
        )
        
        filename = organizer.generate_filename(metadata)
        assert "2024-02-01" in filename
        assert "Special_Episode" in filename
        assert "EP" not in filename
        assert filename.endswith(".vtt")
    
    def test_organize_file(self, organizer, temp_base_dir, tmp_path):
        """Test organizing a single file."""
        # Create source file
        source_file = tmp_path / "test.vtt"
        source_file.write_text("WEBVTT\n\nTest content")
        
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2024-01-01",
            file_path=str(source_file),
            speakers=["Host"]
        )
        
        # Organize file
        new_path = organizer.organize_file(str(source_file), metadata)
        
        assert new_path is not None
        assert Path(new_path).exists()
        assert "Test_Podcast" in str(new_path)
        assert Path(new_path).read_text() == "WEBVTT\n\nTest content"
        
        # Metadata file should exist
        meta_path = Path(new_path).with_suffix('.vtt.meta.json')
        assert meta_path.exists()
    
    def test_save_metadata(self, organizer, temp_base_dir):
        """Test metadata saving."""
        vtt_path = temp_base_dir / "Test_Podcast" / "test.vtt"
        vtt_path.parent.mkdir(exist_ok=True)
        vtt_path.write_text("WEBVTT\n\nContent")
        
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2024-01-01",
            file_path=str(vtt_path),
            speakers=["Host", "Guest"]
        )
        
        organizer.save_metadata(vtt_path, metadata)
        
        meta_path = vtt_path.with_suffix('.vtt.meta.json')
        assert meta_path.exists()
        
        # Load and verify metadata
        with open(meta_path) as f:
            saved_meta = json.load(f)
        
        assert saved_meta['title'] == "Test Episode"
        assert saved_meta['speakers'] == ["Host", "Guest"]
    
    def test_load_metadata(self, organizer, temp_base_dir):
        """Test metadata loading."""
        vtt_path = temp_base_dir / "Test_Podcast" / "test.vtt"
        vtt_path.parent.mkdir(exist_ok=True)
        
        # Create metadata file
        metadata_dict = {
            'title': 'Test Episode',
            'podcast_name': 'Test Podcast',
            'publication_date': '2024-01-01',
            'file_path': str(vtt_path),
            'speakers': ['Host'],
            'duration': 1800
        }
        
        meta_path = vtt_path.with_suffix('.vtt.meta.json')
        with open(meta_path, 'w') as f:
            json.dump(metadata_dict, f)
        
        # Load metadata
        loaded = organizer.load_metadata(vtt_path)
        
        assert loaded is not None
        assert loaded.title == 'Test Episode'
        assert loaded.duration == 1800
    
    def test_scan_directory(self, organizer, temp_base_dir):
        """Test scanning directory for VTT files."""
        # Create test structure
        podcast1 = temp_base_dir / "Podcast_A"
        podcast1.mkdir()
        (podcast1 / "episode1.vtt").write_text("VTT content 1")
        (podcast1 / "episode2.vtt").write_text("VTT content 2")
        
        podcast2 = temp_base_dir / "Podcast_B"
        podcast2.mkdir()
        (podcast2 / "episode1.vtt").write_text("VTT content 3")
        
        # Add non-VTT file that should be ignored
        (podcast1 / "notes.txt").write_text("Should be ignored")
        
        # Scan directory
        vtt_files = organizer.scan_directory()
        
        assert len(vtt_files) == 3
        assert all(str(f).endswith('.vtt') for f in vtt_files)
    
    def test_get_statistics(self, organizer, temp_base_dir):
        """Test getting organization statistics."""
        # Create test structure
        podcast1 = temp_base_dir / "Podcast_A"
        podcast1.mkdir()
        
        # Create episodes with metadata
        for i in range(3):
            vtt_path = podcast1 / f"episode{i}.vtt"
            vtt_path.write_text(f"VTT content {i}")
            
            metadata = EpisodeMetadata(
                title=f"Episode {i}",
                podcast_name="Podcast A",
                publication_date=f"2024-01-0{i+1}",
                file_path=str(vtt_path),
                speakers=["Host"],
                duration=1800 + i * 300
            )
            organizer.save_metadata(vtt_path, metadata)
        
        stats = organizer.get_statistics()
        
        assert stats['total_podcasts'] == 1
        assert stats['total_episodes'] == 3
        assert stats['total_duration_hours'] > 0
        assert 'Podcast_A' in stats['by_podcast']
        assert stats['by_podcast']['Podcast_A']['episode_count'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])