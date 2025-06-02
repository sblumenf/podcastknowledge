"""Unit tests for VTT generator module."""

import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.vtt_generator import VTTGenerator, VTTMetadata


class TestVTTMetadata:
    """Test VTTMetadata dataclass and methods."""
    
    def test_init_required_fields(self):
        """Test VTTMetadata initialization with required fields."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2025-06-01"
        )
        
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.episode_title == "Episode 1"
        assert metadata.publication_date == "2025-06-01"
        assert metadata.duration is None
        assert metadata.host is None
        assert metadata.guests is None
    
    def test_init_all_fields(self):
        """Test VTTMetadata initialization with all fields."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2025-06-01",
            duration="45:00",
            host="John Doe",
            guests=["Jane Smith", "Bob Wilson"],
            description="A great episode",
            youtube_url="https://youtube.com/watch?v=123",
            transcription_date="2025-06-01T10:00:00",
            speakers={"SPEAKER_1": "John Doe", "SPEAKER_2": "Jane Smith"}
        )
        
        assert metadata.duration == "45:00"
        assert metadata.host == "John Doe"
        assert metadata.guests == ["Jane Smith", "Bob Wilson"]
        assert metadata.description == "A great episode"
        assert metadata.youtube_url == "https://youtube.com/watch?v=123"
        assert metadata.transcription_date == "2025-06-01T10:00:00"
        assert metadata.speakers == {"SPEAKER_1": "John Doe", "SPEAKER_2": "Jane Smith"}
    
    def test_to_note_block_minimal(self):
        """Test converting minimal metadata to NOTE block."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2025-06-01"
        )
        
        note_block = metadata.to_note_block()
        
        assert "NOTE" in note_block
        assert "Podcast: Test Podcast" in note_block
        assert "Episode: Episode 1" in note_block
        assert "Date: 2025-06-01" in note_block
        assert "NOTE JSON Metadata" in note_block
        
        # Check JSON is valid
        json_start = note_block.find("{")
        json_data = json.loads(note_block[json_start:])
        assert json_data["podcast"] == "Test Podcast"
        assert json_data["episode"] == "Episode 1"
        assert json_data["date"] == "2025-06-01"
    
    def test_to_note_block_complete(self):
        """Test converting complete metadata to NOTE block."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2025-06-01",
            duration="45:00",
            host="John Doe",
            guests=["Jane Smith", "Bob Wilson"],
            description="A great episode discussing various topics",
            youtube_url="https://youtube.com/watch?v=123",
            transcription_date="2025-06-01T10:00:00",
            speakers={"SPEAKER_1": "John Doe", "SPEAKER_2": "Jane Smith"}
        )
        
        note_block = metadata.to_note_block()
        
        assert "Duration: 45:00" in note_block
        assert "Host: John Doe" in note_block
        assert "Guests: Jane Smith, Bob Wilson" in note_block
        assert "Description: A great episode" in note_block
        assert "YouTube: https://youtube.com/watch?v=123" in note_block
        assert "Transcribed: 2025-06-01T10:00:00" in note_block
    
    def test_to_note_block_long_description(self):
        """Test wrapping long descriptions."""
        long_desc = "This is a very long description that should be wrapped at 80 characters to ensure proper formatting in the VTT file. It contains multiple sentences and should be split across multiple lines."
        
        metadata = VTTMetadata(
            podcast_name="Test",
            episode_title="Episode",
            publication_date="2025-06-01",
            description=long_desc
        )
        
        note_block = metadata.to_note_block()
        lines = note_block.split('\n')
        
        # Check that description lines are wrapped
        desc_lines = [line for line in lines if line.startswith("Description:") or (line and not line.startswith("NOTE") and ":" not in line)]
        for line in desc_lines[:-1]:  # All but last line
            assert len(line) <= 80
    
    def test_wrap_text_short(self):
        """Test _wrap_text with short text."""
        metadata = VTTMetadata("Test", "Episode", "2025-06-01")
        wrapped = metadata._wrap_text("Short text", 80)
        assert wrapped == ["Short text"]
    
    def test_wrap_text_long(self):
        """Test _wrap_text with long text."""
        metadata = VTTMetadata("Test", "Episode", "2025-06-01")
        text = "This is a long text that needs to be wrapped because it exceeds the maximum width"
        wrapped = metadata._wrap_text(text, 30)
        
        assert len(wrapped) > 1
        for line in wrapped[:-1]:
            assert len(line) <= 30
    
    def test_json_metadata_excludes_none(self):
        """Test that None values are excluded from JSON metadata."""
        metadata = VTTMetadata(
            podcast_name="Test",
            episode_title="Episode",
            publication_date="2025-06-01",
            duration=None,
            host=None
        )
        
        note_block = metadata.to_note_block()
        json_start = note_block.find("{")
        json_data = json.loads(note_block[json_start:])
        
        # These should be excluded
        assert "duration" not in json_data
        assert "host" not in json_data
        assert "guests" not in json_data
        
        # But description and youtube_url should be included even if None
        assert "description" in json_data
        assert "youtube_url" in json_data


class TestVTTGenerator:
    """Test VTTGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create VTTGenerator instance."""
        return VTTGenerator()
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        return VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2025-06-01",
            duration="45:00",
            host="John Doe",
            speakers={"SPEAKER_1": "John Doe", "SPEAKER_2": "Jane Smith"}
        )
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Create sample VTT content."""
        return """00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello, welcome to our podcast.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thanks for having me!"""
    
    def test_init(self, generator):
        """Test VTTGenerator initialization."""
        assert generator.encoding == 'utf-8'
        assert generator.checkpoint_manager is None
        assert generator.escape_chars == {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;'
        }
    
    def test_init_with_checkpoint_manager(self):
        """Test VTTGenerator initialization with checkpoint manager."""
        mock_checkpoint = Mock()
        generator = VTTGenerator(checkpoint_manager=mock_checkpoint)
        assert generator.checkpoint_manager == mock_checkpoint
    
    def test_generate_vtt_basic(self, generator, sample_metadata, sample_vtt_content):
        """Test basic VTT generation."""
        result = generator.generate_vtt(sample_vtt_content, sample_metadata)
        
        # Check header
        assert result.startswith("WEBVTT\n\n")
        
        # Check metadata
        assert "NOTE" in result
        assert "Podcast: Test Podcast" in result
        assert "Episode: Episode 1" in result
        
        # Check content
        assert "00:00:01.000 --> 00:00:05.000" in result
        assert "Hello, welcome to our podcast." in result
    
    def test_generate_vtt_with_style(self, generator, sample_metadata, sample_vtt_content):
        """Test VTT generation with style block."""
        result = generator.generate_vtt(sample_vtt_content, sample_metadata)
        
        # Should have style block for speakers
        assert "STYLE" in result
        assert "::cue(v[voice=\"John\\ Doe\"])" in result
        assert "color: #3498db" in result  # First speaker color
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_generate_vtt_with_output_path(self, mock_mkdir, mock_file, generator, sample_metadata, sample_vtt_content):
        """Test VTT generation with file output."""
        output_path = Path("/tmp/test.vtt")
        
        result = generator.generate_vtt(sample_vtt_content, sample_metadata, output_path)
        
        # Check file was written
        mock_file.assert_called_once_with(output_path, 'w', encoding='utf-8')
        handle = mock_file()
        handle.write.assert_called_once()
        written_content = handle.write.call_args[0][0]
        assert written_content == result
    
    def test_generate_style_block_no_speakers(self, generator):
        """Test style block generation with no speakers."""
        result = generator._generate_style_block(None)
        assert result is None
        
        result = generator._generate_style_block({})
        assert result is None
    
    def test_generate_style_block_multiple_speakers(self, generator):
        """Test style block generation with multiple speakers."""
        speakers = {
            "SPEAKER_1": "John Doe",
            "SPEAKER_2": "Jane Smith",
            "SPEAKER_3": "Bob Wilson",
            "SPEAKER_4": "Alice Brown",
            "SPEAKER_5": "Charlie Davis",
            "SPEAKER_6": "Eve Johnson"  # Should wrap around to first color
        }
        
        result = generator._generate_style_block(speakers)
        
        assert "STYLE" in result
        assert "::cue(v[voice=\"John\\ Doe\"])" in result
        assert "::cue(v[voice=\"Jane\\ Smith\"])" in result
        assert "#3498db" in result  # Blue
        assert "#2ecc71" in result  # Green
        assert "#e74c3c" in result  # Red
        assert "#f39c12" in result  # Orange
        assert "#9b59b6" in result  # Purple
    
    def test_generate_style_block_special_chars(self, generator):
        """Test style block with special characters in names."""
        speakers = {"SPEAKER_1": "John (Host) Doe"}
        result = generator._generate_style_block(speakers)
        
        assert "::cue(v[voice=\"John\\ \\(Host\\)\\ Doe\"])" in result
    
    def test_process_vtt_content_basic(self, generator):
        """Test basic VTT content processing."""
        content = """00:00:01.000 --> 00:00:05.000
Hello world

00:00:05.000 --> 00:00:10.000
Another line"""
        
        result = generator._process_vtt_content(content)
        assert "00:00:01.000 --> 00:00:05.000" in result
        assert "Hello world" in result
        assert "Another line" in result
    
    def test_process_vtt_content_removes_header(self, generator):
        """Test that existing WEBVTT header is removed."""
        content = """WEBVTT

00:00:01.000 --> 00:00:05.000
Hello world"""
        
        result = generator._process_vtt_content(content)
        assert not result.startswith("WEBVTT")
        assert "00:00:01.000 --> 00:00:05.000" in result
    
    def test_process_vtt_content_escapes_special_chars(self, generator):
        """Test escaping special characters in cue text."""
        content = """00:00:01.000 --> 00:00:05.000
Hello & welcome < everyone >"""
        
        result = generator._process_vtt_content(content)
        assert "Hello &amp; welcome &lt; everyone &gt;" in result
    
    def test_escape_cue_text_basic(self, generator):
        """Test basic cue text escaping."""
        text = "Hello & welcome < everyone >"
        result = generator._escape_cue_text(text)
        assert result == "Hello &amp; welcome &lt; everyone &gt;"
    
    def test_escape_cue_text_voice_tag(self, generator):
        """Test escaping with voice tag."""
        text = "<v John Doe>Hello & welcome"
        result = generator._escape_cue_text(text)
        assert result == "<v John Doe>Hello &amp; welcome"
        assert "<v John Doe>" in result  # Voice tag not escaped
    
    def test_is_timestamp_line_valid(self, generator):
        """Test timestamp line validation."""
        valid_lines = [
            "00:00:01.000 --> 00:00:05.000",
            "0:00:01.000 --> 0:00:05.000",
            "01:23:45.678 --> 01:23:50.123",
            "00:00:01.000  -->  00:00:05.000",  # Extra spaces
        ]
        
        for line in valid_lines:
            assert generator._is_timestamp_line(line) is True
    
    def test_is_timestamp_line_invalid(self, generator):
        """Test invalid timestamp lines."""
        invalid_lines = [
            "not a timestamp",
            "00:00:01 --> 00:00:05",  # Missing milliseconds
            "00:00:01.000 -> 00:00:05.000",  # Wrong arrow
            "00:00:01.000 --> ",  # Missing end time
        ]
        
        for line in invalid_lines:
            assert generator._is_timestamp_line(line) is False
    
    def test_normalize_line_endings(self, generator):
        """Test line ending normalization."""
        # Test CRLF to LF
        content = "Line 1\r\nLine 2\r\nLine 3"
        result = generator._normalize_line_endings(content)
        assert "\r\n" not in result
        assert result == "Line 1\nLine 2\nLine 3\n"
        
        # Test lone CR
        content = "Line 1\rLine 2"
        result = generator._normalize_line_endings(content)
        assert "\r" not in result
        assert result == "Line 1\nLine 2\n"
        
        # Test multiple newlines
        content = "Line 1\n\n\n\nLine 2"
        result = generator._normalize_line_endings(content)
        assert result == "Line 1\n\nLine 2\n"
        
        # Test ending newline
        content = "Line 1"
        result = generator._normalize_line_endings(content)
        assert result == "Line 1\n"
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_vtt_file(self, mock_mkdir, mock_file, generator):
        """Test saving VTT file."""
        content = "WEBVTT\n\nTest content"
        path = Path("/tmp/test.vtt")
        
        generator._save_vtt_file(content, path)
        
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once_with(path, 'w', encoding='utf-8')
        handle = mock_file()
        handle.write.assert_called_once_with(content)
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    @patch('pathlib.Path.mkdir')
    def test_save_vtt_file_error(self, mock_mkdir, mock_file, generator):
        """Test error handling in save_vtt_file."""
        content = "WEBVTT\n\nTest content"
        path = Path("/tmp/test.vtt")
        
        with pytest.raises(IOError):
            generator._save_vtt_file(content, path)
    
    def test_create_metadata_from_episode_basic(self, generator):
        """Test creating metadata from episode data."""
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1',
            'publication_date': '2025-06-01',
            'duration': '45:00',
            'author': 'John Doe',
            'description': 'Test episode'
        }
        
        metadata = generator.create_metadata_from_episode(episode_data)
        
        assert metadata.podcast_name == 'Test Podcast'
        assert metadata.episode_title == 'Episode 1'
        assert metadata.publication_date == '2025-06-01'
        assert metadata.duration == '45:00'
        assert metadata.host == 'John Doe'
        assert metadata.description == 'Test episode'
    
    def test_create_metadata_from_episode_with_speakers(self, generator):
        """Test creating metadata with speaker mapping."""
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1',
            'publication_date': '2025-06-01'
        }
        
        speaker_mapping = {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Jane Smith (Guest)',
            'SPEAKER_3': 'Bob Wilson (Guest)'
        }
        
        metadata = generator.create_metadata_from_episode(episode_data, speaker_mapping)
        
        assert metadata.host == 'John Doe'
        assert metadata.guests == ['Jane Smith', 'Bob Wilson']
        assert metadata.speakers == speaker_mapping
    
    def test_create_metadata_from_episode_minimal(self, generator):
        """Test creating metadata with minimal data."""
        episode_data = {}
        
        metadata = generator.create_metadata_from_episode(episode_data)
        
        assert metadata.podcast_name == 'Unknown Podcast'
        assert metadata.episode_title == 'Unknown Episode'
        assert metadata.publication_date == 'Unknown'
    
    def test_sanitize_filename_basic(self, generator):
        """Test basic filename sanitization."""
        assert generator.sanitize_filename("Normal Title") == "Normal_Title"
        assert generator.sanitize_filename("Title: With Colon") == "Title__With_Colon"
        assert generator.sanitize_filename('Title "With" Quotes') == 'Title__With__Quotes'
    
    def test_sanitize_filename_special_chars(self, generator):
        """Test sanitizing special characters."""
        assert generator.sanitize_filename("Title<>:|?*") == "Title______"
        assert generator.sanitize_filename("Path/With/Slashes") == "Path_With_Slashes"
        assert generator.sanitize_filename("Path\\With\\Backslashes") == "Path_With_Backslashes"
    
    def test_sanitize_filename_edge_cases(self, generator):
        """Test edge cases in filename sanitization."""
        # Leading/trailing dots and spaces
        assert generator.sanitize_filename("  .Title.  ") == "Title"
        
        # Empty after sanitization
        assert generator.sanitize_filename("....") == "untitled"
        
        # Very long filename
        long_name = "A" * 300
        result = generator.sanitize_filename(long_name)
        assert len(result) == 200
    
    def test_generate_output_path_basic(self, generator):
        """Test basic output path generation."""
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1',
            'publication_date': '2025-06-01T10:00:00Z'
        }
        
        output_dir = Path("/output")
        result = generator.generate_output_path(episode_data, output_dir)
        
        assert result == Path("/output/Test_Podcast/2025-06-01_Episode_1.vtt")
    
    def test_generate_output_path_special_chars(self, generator):
        """Test output path with special characters."""
        episode_data = {
            'podcast_name': 'Test: Podcast!',
            'title': 'Episode "Special"',
            'publication_date': '2025-06-01'
        }
        
        output_dir = Path("/output")
        result = generator.generate_output_path(episode_data, output_dir)
        
        assert result == Path("/output/Test__Podcast_/2025-06-01_Episode__Special_.vtt")
    
    def test_generate_output_path_invalid_date(self, generator):
        """Test output path with invalid date."""
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1',
            'publication_date': 'invalid-date'
        }
        
        output_dir = Path("/output")
        result = generator.generate_output_path(episode_data, output_dir)
        
        assert result == Path("/output/Test_Podcast/invalid-date_Episode_1.vtt")
    
    def test_generate_output_path_missing_data(self, generator):
        """Test output path with missing data."""
        episode_data = {}
        
        output_dir = Path("/output")
        result = generator.generate_output_path(episode_data, output_dir)
        
        assert result == Path("/output/Unknown_Podcast/unknown_untitled.vtt")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_vtt_with_checkpoint_manager(self, mock_mkdir, mock_file, generator):
        """Test saving VTT file with checkpoint manager."""
        mock_checkpoint = Mock()
        generator.checkpoint_manager = mock_checkpoint
        
        content = "WEBVTT\n\nTest"
        path = Path("/tmp/test.vtt")
        
        generator._save_vtt_file(content, path)
        
        # Check checkpoint methods were called
        mock_checkpoint.complete_stage.assert_called_once_with('vtt_generation')
        mock_checkpoint.mark_completed.assert_called_once_with(str(path))