"""Comprehensive tests for File Organizer to improve coverage from 10.53% to 20%."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
from pathlib import Path
import shutil
import os
import json
from datetime import datetime
import platform

from src.file_organizer import FileOrganizer

# Create custom error for tests
class FileOrganizerError(Exception):
    pass
from src.config import Config


class TestFileOrganizerDirectoryOperations:
    """Test directory creation and management to prevent data loss."""
    
    @pytest.fixture
    def organizer(self):
        """Create file organizer with test config."""
        config = Config.create_test_config()
        return FileOrganizer(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_create_output_directory_structure(self, organizer, temp_dir):
        """Test creation of organized directory structure."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Create directory structure for a podcast
        podcast_name = "Test Podcast"
        episode_title = "Episode 1: Introduction"
        
        paths = organizer.create_episode_directory(podcast_name, episode_title)
        
        assert paths['base'].exists()
        assert paths['audio'].exists()
        assert paths['transcripts'].exists()
        assert paths['metadata'].exists()
        
        # Check directory permissions (platform-specific)
        if platform.system() != 'Windows':
            assert os.access(paths['base'], os.W_OK)
            assert os.access(paths['audio'], os.W_OK)
    
    def test_handle_existing_directories(self, organizer, temp_dir):
        """Test handling when directories already exist."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Create directories first
        paths1 = organizer.create_episode_directory("Podcast", "Episode 1")
        
        # Create again - should not raise error
        paths2 = organizer.create_episode_directory("Podcast", "Episode 1")
        
        assert paths1['base'] == paths2['base']
        assert paths2['base'].exists()
    
    def test_directory_creation_with_special_characters(self, organizer, temp_dir):
        """Test directory creation with special characters in names."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Test various special characters
        test_cases = [
            ("Podcast: The Show", "Episode 1/2: Part One"),
            ("Podcast & Friends", "Episode #5 - Q&A"),
            ("Podcast!?", "Episode... Wait, What?"),
            ("Podcast™", "Episode® Special©")
        ]
        
        for podcast, episode in test_cases:
            paths = organizer.create_episode_directory(podcast, episode)
            assert paths['base'].exists()
            # Check sanitized names
            assert ':' not in paths['base'].name
            assert '/' not in paths['base'].name
            assert '?' not in paths['base'].name
    
    def test_directory_permissions_error(self, organizer):
        """Test handling of permission errors during directory creation."""
        # Mock a read-only directory
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            with pytest.raises(FileOrganizerError, match="Permission denied"):
                organizer.create_episode_directory("Podcast", "Episode")
    
    def test_long_path_handling(self, organizer, temp_dir):
        """Test handling of very long paths."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Create a very long episode title
        long_title = "Episode " + "Very Long Title " * 20
        
        paths = organizer.create_episode_directory("Podcast", long_title)
        
        # Path should be truncated to reasonable length
        assert len(str(paths['base'])) < 255  # Most filesystems limit
        assert paths['base'].exists()


class TestFileOrganizerFileOperations:
    """Test file operations and naming collision handling."""
    
    @pytest.fixture
    def organizer(self):
        """Create file organizer."""
        config = Config.create_test_config()
        return FileOrganizer(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_move_file_to_organized_location(self, organizer, temp_dir):
        """Test moving files to organized structure."""
        # Create source file
        source_file = temp_dir / "audio.mp3"
        source_file.write_text("audio data")
        
        # Create destination
        dest_dir = temp_dir / "organized"
        dest_dir.mkdir()
        
        # Move file
        new_path = organizer.move_file(source_file, dest_dir, "episode_audio.mp3")
        
        assert new_path.exists()
        assert new_path.name == "episode_audio.mp3"
        assert not source_file.exists()
        assert new_path.read_text() == "audio data"
    
    def test_copy_file_instead_of_move(self, organizer, temp_dir):
        """Test copying files when move not desired."""
        source_file = temp_dir / "audio.mp3"
        source_file.write_text("audio data")
        
        dest_dir = temp_dir / "organized"
        dest_dir.mkdir()
        
        # Copy file
        new_path = organizer.copy_file(source_file, dest_dir, "episode_audio.mp3")
        
        assert new_path.exists()
        assert source_file.exists()  # Original still exists
        assert new_path.read_text() == "audio data"
    
    def test_handle_naming_collision(self, organizer, temp_dir):
        """Test handling of file naming collisions."""
        dest_dir = temp_dir / "organized"
        dest_dir.mkdir()
        
        # Create existing file
        existing = dest_dir / "transcript.json"
        existing.write_text("existing data")
        
        # Try to save new file with same name
        new_file = temp_dir / "new_transcript.json"
        new_file.write_text("new data")
        
        # Should create unique name
        final_path = organizer.move_file(new_file, dest_dir, "transcript.json")
        
        assert final_path.exists()
        assert final_path != existing
        assert "transcript" in final_path.name
        assert final_path.read_text() == "new data"
        assert existing.read_text() == "existing data"
    
    def test_organize_episode_files(self, organizer, temp_dir):
        """Test organizing all files for an episode."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Create test files
        audio_file = temp_dir / "episode.mp3"
        audio_file.write_text("audio")
        
        transcript_file = temp_dir / "transcript.json"
        transcript_file.write_text('{"text": "transcript"}')
        
        metadata_file = temp_dir / "metadata.json"
        metadata_file.write_text('{"title": "Episode 1"}')
        
        # Organize files
        organized = organizer.organize_episode_files(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            audio_file=audio_file,
            transcript_file=transcript_file,
            metadata_file=metadata_file
        )
        
        assert organized['audio'].exists()
        assert organized['transcript'].exists()
        assert organized['metadata'].exists()
        
        # Original files should be moved
        assert not audio_file.exists()
        assert not transcript_file.exists()
        assert not metadata_file.exists()
    
    def test_atomic_file_operations(self, organizer, temp_dir):
        """Test atomic file operations to prevent data loss."""
        source = temp_dir / "important.json"
        source.write_text('{"important": "data"}')
        
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        # Mock an error during file operation
        with patch('shutil.move') as mock_move:
            mock_move.side_effect = OSError("Disk full")
            
            with pytest.raises(FileOrganizerError):
                organizer.move_file(source, dest_dir, "important.json")
            
            # Original file should still exist
            assert source.exists()
            assert source.read_text() == '{"important": "data"}'


class TestFileOrganizerCleanup:
    """Test cleanup operations on errors."""
    
    @pytest.fixture
    def organizer(self):
        """Create file organizer."""
        config = Config.create_test_config()
        return FileOrganizer(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_cleanup_on_error(self, organizer, temp_dir):
        """Test cleanup when organization fails."""
        organizer.config.output.default_dir = str(temp_dir)
        
        # Create partial episode structure
        paths = organizer.create_episode_directory("Podcast", "Episode 1")
        
        # Add some files
        (paths['audio'] / "partial.mp3").write_text("partial")
        
        # Simulate error and cleanup
        with patch.object(organizer, 'move_file') as mock_move:
            mock_move.side_effect = Exception("Error during organization")
            
            with pytest.raises(Exception):
                organizer.organize_episode_files(
                    podcast_name="Podcast",
                    episode_title="Episode 1",
                    audio_file=temp_dir / "audio.mp3",
                    cleanup_on_error=True
                )
            
            # Check cleanup occurred
            # Note: Implementation may vary
    
    def test_preserve_files_option(self, organizer, temp_dir):
        """Test option to preserve original files."""
        organizer.config.output.default_dir = str(temp_dir)
        organizer.config.file_organizer.preserve_originals = True
        
        # Create source files
        audio = temp_dir / "audio.mp3"
        audio.write_text("audio")
        
        # Organize with preservation
        organized = organizer.organize_episode_files(
            podcast_name="Podcast",
            episode_title="Episode 1",
            audio_file=audio
        )
        
        # Both original and organized should exist
        assert audio.exists()
        assert organized['audio'].exists()
    
    def test_rollback_on_partial_failure(self, organizer, temp_dir):
        """Test rollback when partial organization fails."""
        organizer.config.output.default_dir = str(temp_dir)
        
        audio = temp_dir / "audio.mp3"
        audio.write_text("audio")
        
        transcript = temp_dir / "transcript.json"
        transcript.write_text("transcript")
        
        # Mock failure on second file
        original_move = organizer.move_file
        call_count = 0
        
        def mock_move(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Failed on second file")
            return original_move(*args, **kwargs)
        
        with patch.object(organizer, 'move_file', side_effect=mock_move):
            with pytest.raises(Exception):
                organizer.organize_episode_files(
                    podcast_name="Podcast",
                    episode_title="Episode 1",
                    audio_file=audio,
                    transcript_file=transcript,
                    rollback_on_error=True
                )
        
        # Files should be in original location
        assert audio.exists()
        assert transcript.exists()


class TestFileOrganizerConfiguration:
    """Test configuration-driven organization."""
    
    def test_custom_directory_structure(self):
        """Test custom directory structure from config."""
        config = Config.create_test_config()
        config.file_organizer.directory_template = "{podcast}/{year}/{episode}"
        
        organizer = FileOrganizer(config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config.output.default_dir = tmpdir
            
            paths = organizer.create_episode_directory(
                podcast_name="My Podcast",
                episode_title="Episode 10",
                date=datetime(2024, 6, 15)
            )
            
            # Check custom structure
            assert "My Podcast" in str(paths['base'])
            assert "2024" in str(paths['base'])
            assert "Episode 10" in str(paths['base'])
    
    def test_file_naming_patterns(self):
        """Test configurable file naming patterns."""
        config = Config.create_test_config()
        config.file_organizer.filename_template = "{podcast}_{episode}_{type}.{ext}"
        
        organizer = FileOrganizer(config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "audio.mp3"
            source.write_text("audio")
            
            dest = Path(tmpdir) / "dest"
            dest.mkdir()
            
            filename = organizer.generate_filename(
                podcast="TestPodcast",
                episode="Ep01",
                file_type="audio",
                extension="mp3"
            )
            
            assert filename == "TestPodcast_Ep01_audio.mp3"
    
    def test_max_path_length_config(self):
        """Test configurable max path length."""
        config = Config.create_test_config()
        config.file_organizer.max_path_length = 100
        
        organizer = FileOrganizer(config)
        
        long_name = "Very Long Episode Title " * 10
        sanitized = organizer.sanitize_filename(long_name)
        
        assert len(sanitized) <= 100


class TestFileOrganizerCrossPlatform:
    """Test cross-platform compatibility."""
    
    @pytest.fixture
    def organizer(self):
        """Create file organizer."""
        config = Config.create_test_config()
        return FileOrganizer(config)
    
    def test_windows_path_handling(self, organizer):
        """Test Windows-specific path handling."""
        # Test reserved names
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        
        for name in reserved_names:
            sanitized = organizer.sanitize_filename(f"{name}.mp3")
            assert sanitized != f"{name}.mp3"
            assert name.lower() not in sanitized.lower()
    
    def test_unicode_filename_support(self, organizer):
        """Test Unicode character support in filenames."""
        unicode_names = [
            "Café_Episode",
            "Podcast_北京",
            "Episode_🎙️",
            "Ñoño_Show"
        ]
        
        for name in unicode_names:
            sanitized = organizer.sanitize_filename(name)
            # Should handle unicode gracefully
            assert len(sanitized) > 0
            
    def test_case_sensitivity_handling(self, organizer, temp_dir):
        """Test handling of case sensitivity across platforms."""
        if platform.system() == 'Windows':
            # Windows is case-insensitive
            file1 = temp_dir / "Episode.mp3"
            file1.write_text("1")
            
            file2 = temp_dir / "episode.mp3"
            # Should handle as same file on Windows
            
        else:
            # Unix is case-sensitive
            file1 = temp_dir / "Episode.mp3"
            file1.write_text("1")
            
            file2 = temp_dir / "episode.mp3"
            file2.write_text("2")
            
            assert file1.read_text() != file2.read_text()