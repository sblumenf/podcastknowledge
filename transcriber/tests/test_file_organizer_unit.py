"""Unit tests for file organizer module."""

import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open

from src.file_organizer import FileOrganizer, EpisodeMetadata


class TestEpisodeMetadata:
    """Test EpisodeMetadata dataclass."""
    
    def test_init_minimal(self):
        """Test EpisodeMetadata initialization with minimal fields."""
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2025-06-01",
            file_path="/data/test.vtt",
            speakers=["Host", "Guest"]
        )
        
        assert metadata.title == "Test Episode"
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.publication_date == "2025-06-01"
        assert metadata.file_path == "/data/test.vtt"
        assert metadata.speakers == ["Host", "Guest"]
        assert metadata.duration is None
        assert metadata.episode_number is None
        assert metadata.description is None
        # processed_date should be set automatically
        assert metadata.processed_date != ""
    
    def test_init_all_fields(self):
        """Test EpisodeMetadata initialization with all fields."""
        metadata = EpisodeMetadata(
            title="Test Episode",
            podcast_name="Test Podcast",
            publication_date="2025-06-01",
            file_path="/data/test.vtt",
            speakers=["Host", "Guest"],
            duration=2700,  # 45 minutes
            episode_number=10,
            description="A great episode",
            processed_date="2025-06-01 12:00:00"
        )
        
        assert metadata.duration == 2700
        assert metadata.episode_number == 10
        assert metadata.description == "A great episode"
        assert metadata.processed_date == "2025-06-01 12:00:00"
    
    @patch('src.file_organizer.datetime')
    def test_auto_processed_date(self, mock_datetime):
        """Test automatic processed_date generation."""
        mock_datetime.now.return_value.strftime.return_value = "2025-06-01 15:30:00"
        
        metadata = EpisodeMetadata(
            title="Test",
            podcast_name="Test",
            publication_date="2025-06-01",
            file_path="/test.vtt",
            speakers=[]
        )
        
        assert metadata.processed_date == "2025-06-01 15:30:00"


class TestFileOrganizer:
    """Test FileOrganizer class."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for tests."""
        return tmp_path / "test_transcripts"
    
    @pytest.fixture
    def organizer(self, temp_dir):
        """Create FileOrganizer instance with temp directory."""
        return FileOrganizer(str(temp_dir))
    
    def test_init_creates_directory(self, temp_dir):
        """Test that initialization creates the base directory."""
        assert not temp_dir.exists()
        organizer = FileOrganizer(str(temp_dir))
        assert temp_dir.exists()
    
    def test_init_loads_existing_manifest(self, temp_dir):
        """Test loading existing manifest on initialization."""
        # Create manifest file
        temp_dir.mkdir(parents=True)
        manifest_data = [
            {
                "title": "Existing Episode",
                "podcast_name": "Test Podcast",
                "publication_date": "2025-06-01",
                "file_path": "/existing.vtt",
                "speakers": ["Host"],
                "processed_date": "2025-06-01 10:00:00"
            }
        ]
        manifest_file = temp_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        
        organizer = FileOrganizer(str(temp_dir))
        
        assert len(organizer.episodes) == 1
        assert organizer.episodes[0].title == "Existing Episode"
        assert "/existing.vtt" in organizer._used_filenames
    
    def test_sanitize_filename_basic(self, organizer):
        """Test basic filename sanitization."""
        assert organizer.sanitize_filename("Normal Title") == "Normal_Title"
        assert organizer.sanitize_filename("Title: With Colon") == "Title_With_Colon"
        assert organizer.sanitize_filename("Title / With / Slashes") == "Title__With__Slashes"
    
    def test_sanitize_filename_special_chars(self, organizer):
        """Test sanitizing special characters."""
        assert organizer.sanitize_filename('Title "With" Quotes') == "Title_With_Quotes"
        assert organizer.sanitize_filename("Title?With*Special|Chars") == "TitleWithSpecialChars"
        assert organizer.sanitize_filename("Title<>With<>Brackets") == "TitleWithBrackets"
    
    def test_sanitize_filename_whitespace(self, organizer):
        """Test handling of whitespace."""
        assert organizer.sanitize_filename("  Title  With   Spaces  ") == "Title_With_Spaces"
        assert organizer.sanitize_filename("Title\nWith\tTabs") == "Title_With_Tabs"
    
    def test_sanitize_filename_edge_cases(self, organizer):
        """Test edge cases in filename sanitization."""
        # Empty string
        assert organizer.sanitize_filename("") == "unknown"
        
        # Only special characters
        assert organizer.sanitize_filename("***???|||") == "untitled"
        
        # Leading/trailing dots and underscores
        assert organizer.sanitize_filename("...Title...") == "Title"
        assert organizer.sanitize_filename("___Title___") == "Title"
    
    def test_sanitize_filename_length_limit(self, organizer):
        """Test filename length truncation."""
        long_name = "A" * 250
        result = organizer.sanitize_filename(long_name)
        assert len(result) == 200
        assert result == "A" * 200
    
    def test_sanitize_filename_safe_chars(self, organizer):
        """Test that safe characters are preserved."""
        safe_name = "Episode_123-Part_2_(Guest).mp3"
        result = organizer.sanitize_filename(safe_name)
        assert result == "Episode_123-Part_2_(Guest).mp3"
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open', new_callable=mock_open, read_data='[]')
    def test_load_manifest_empty(self, mock_file, mock_exists):
        """Test loading empty manifest."""
        mock_exists.return_value = True
        
        organizer = FileOrganizer("/test")
        
        assert organizer.episodes == []
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open', new_callable=mock_open, read_data='invalid json')
    def test_load_manifest_corrupted(self, mock_file, mock_exists):
        """Test handling corrupted manifest file."""
        mock_exists.return_value = True
        
        organizer = FileOrganizer("/test")
        
        # Should handle gracefully and return empty list
        assert organizer.episodes == []
    
    def test_generate_filename(self, organizer):
        """Test filename generation."""
        episode_data = {
            'title': 'Great Episode',
            'publication_date': '2025-06-01'
        }
        
        filename = organizer.generate_filename(episode_data)
        assert filename == "2025-06-01_Great_Episode.vtt"
    
    def test_generate_filename_invalid_date(self, organizer):
        """Test filename generation with invalid date."""
        episode_data = {
            'title': 'Episode',
            'publication_date': 'invalid-date'
        }
        
        filename = organizer.generate_filename(episode_data)
        assert filename == "unknown_Episode.vtt"
    
    def test_generate_filename_missing_fields(self, organizer):
        """Test filename generation with missing fields."""
        filename = organizer.generate_filename({})
        assert filename == "unknown_untitled.vtt"
    
    def test_organize_transcript_basic(self, temp_dir, organizer):
        """Test basic transcript organization."""
        # Create source file
        source_file = temp_dir / "source.vtt"
        source_file.write_text("WEBVTT\n\nTest content")
        
        episode_data = {
            'title': 'Test Episode',
            'podcast_name': 'Test Podcast',
            'publication_date': '2025-06-01',
            'speakers': ['Host', 'Guest']
        }
        
        result = organizer.organize_transcript(str(source_file), episode_data)
        
        # Check result
        assert result['success'] is True
        assert 'Test_Podcast' in result['file_path']
        assert '2025-06-01_Test_Episode.vtt' in result['file_path']
        
        # Check file was moved
        assert Path(result['file_path']).exists()
        assert not source_file.exists()
        
        # Check manifest was updated
        assert len(organizer.episodes) == 1
        assert organizer.episodes[0].title == 'Test Episode'
    
    def test_organize_transcript_duplicate_handling(self, temp_dir, organizer):
        """Test handling of duplicate filenames."""
        # Create source files
        source1 = temp_dir / "source1.vtt"
        source1.write_text("WEBVTT\n\nFirst")
        source2 = temp_dir / "source2.vtt"
        source2.write_text("WEBVTT\n\nSecond")
        
        episode_data = {
            'title': 'Same Title',
            'podcast_name': 'Test Podcast',
            'publication_date': '2025-06-01'
        }
        
        # Organize first file
        result1 = organizer.organize_transcript(str(source1), episode_data)
        assert '2025-06-01_Same_Title.vtt' in result1['file_path']
        
        # Organize second file with same metadata
        result2 = organizer.organize_transcript(str(source2), episode_data)
        assert '2025-06-01_Same_Title_2.vtt' in result2['file_path']
    
    def test_organize_transcript_file_not_found(self, organizer):
        """Test organizing non-existent file."""
        result = organizer.organize_transcript(
            "/nonexistent/file.vtt",
            {'title': 'Test'}
        )
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_update_manifest(self, temp_dir, organizer):
        """Test manifest updating."""
        metadata = EpisodeMetadata(
            title="New Episode",
            podcast_name="Test",
            publication_date="2025-06-01",
            file_path="/test.vtt",
            speakers=["Host"]
        )
        
        organizer.episodes.append(metadata)
        organizer.update_manifest()
        
        # Check manifest file was created
        manifest_file = temp_dir / "manifest.json"
        assert manifest_file.exists()
        
        # Check content
        with open(manifest_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]['title'] == "New Episode"
    
    def test_search_episodes_by_title(self, organizer):
        """Test searching episodes by title."""
        # Add test episodes
        organizer.episodes = [
            EpisodeMetadata("AI Discussion", "Tech", "2025-06-01", "/1.vtt", []),
            EpisodeMetadata("Machine Learning", "Tech", "2025-06-02", "/2.vtt", []),
            EpisodeMetadata("Deep Learning", "Tech", "2025-06-03", "/3.vtt", [])
        ]
        
        results = organizer.search_episodes(title_pattern="learning")
        assert len(results) == 2
        assert all("Learning" in ep.title for ep in results)
    
    def test_search_episodes_by_speaker(self, organizer):
        """Test searching episodes by speaker."""
        organizer.episodes = [
            EpisodeMetadata("Ep1", "Pod", "2025-06-01", "/1.vtt", ["John", "Jane"]),
            EpisodeMetadata("Ep2", "Pod", "2025-06-02", "/2.vtt", ["John", "Bob"]),
            EpisodeMetadata("Ep3", "Pod", "2025-06-03", "/3.vtt", ["Alice", "Bob"])
        ]
        
        results = organizer.search_episodes(speaker="John")
        assert len(results) == 2
        
        results = organizer.search_episodes(speaker="Bob")
        assert len(results) == 2
    
    def test_search_episodes_by_date_range(self, organizer):
        """Test searching episodes by date range."""
        organizer.episodes = [
            EpisodeMetadata("Ep1", "Pod", "2025-06-01", "/1.vtt", []),
            EpisodeMetadata("Ep2", "Pod", "2025-06-15", "/2.vtt", []),
            EpisodeMetadata("Ep3", "Pod", "2025-06-30", "/3.vtt", [])
        ]
        
        results = organizer.search_episodes(
            start_date="2025-06-10",
            end_date="2025-06-20"
        )
        assert len(results) == 1
        assert results[0].title == "Ep2"
    
    def test_get_statistics(self, organizer):
        """Test getting statistics."""
        organizer.episodes = [
            EpisodeMetadata("Ep1", "Pod1", "2025-06-01", "/1.vtt", ["Host"], duration=1800),
            EpisodeMetadata("Ep2", "Pod1", "2025-06-02", "/2.vtt", ["Host"], duration=2700),
            EpisodeMetadata("Ep3", "Pod2", "2025-06-03", "/3.vtt", ["Host", "Guest"], duration=3600)
        ]
        
        stats = organizer.get_statistics()
        
        assert stats['total_episodes'] == 3
        assert stats['total_podcasts'] == 2
        assert stats['total_duration_seconds'] == 8100
        assert stats['total_duration_formatted'] == "2h 15m"
        assert stats['podcasts']['Pod1'] == 2
        assert stats['podcasts']['Pod2'] == 1
    
    def test_cleanup_old_files(self, temp_dir, organizer):
        """Test cleanup of orphaned files."""
        # Create some VTT files
        podcast_dir = temp_dir / "Test_Podcast"
        podcast_dir.mkdir()
        
        file1 = podcast_dir / "episode1.vtt"
        file1.write_text("content")
        file2 = podcast_dir / "episode2.vtt"
        file2.write_text("content")
        
        # Only track one file in manifest
        organizer.episodes = [
            EpisodeMetadata("Ep1", "Test Podcast", "2025-06-01", str(file1), [])
        ]
        
        # Run cleanup
        removed = organizer.cleanup_orphaned_files()
        
        assert len(removed) == 1
        assert str(file2) in removed
        assert file1.exists()
        assert not file2.exists()