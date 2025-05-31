"""Unit tests for the VTT generator module."""

import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.vtt_generator import VTTMetadata, VTTGenerator


class TestVTTMetadata:
    """Test VTTMetadata dataclass."""
    
    def test_vtt_metadata_creation(self):
        """Test creating VTT metadata."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2024-01-15",
            duration="1:23:45",
            host="John Doe",
            guests=["Jane Smith", "Bob Johnson"],
            description="Test episode description",
            transcription_date="2024-01-20T10:00:00",
            speakers={"SPEAKER_1": "John Doe (Host)", "SPEAKER_2": "Jane Smith (Guest)"}
        )
        
        assert metadata.podcast_name == "Test Podcast"
        assert metadata.episode_title == "Episode 1"
        assert len(metadata.guests) == 2
        assert metadata.speakers["SPEAKER_1"] == "John Doe (Host)"
    
    def test_to_note_block_full(self):
        """Test converting metadata to NOTE block with all fields."""
        metadata = VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            publication_date="2024-01-15",
            duration="1:23:45",
            host="John Doe",
            guests=["Jane Smith", "Bob Johnson"],
            transcription_date="2024-01-20T10:00:00",
            speakers={"SPEAKER_1": "John Doe (Host)"}
        )
        
        note_block = metadata.to_note_block()
        
        assert "NOTE" in note_block
        assert "Podcast: Test Podcast" in note_block
        assert "Episode: Episode 1" in note_block
        assert "Date: 2024-01-15" in note_block
        assert "Duration: 1:23:45" in note_block
        assert "Host: John Doe" in note_block
        assert "Guests: Jane Smith, Bob Johnson" in note_block
        assert "Transcribed: 2024-01-20T10:00:00" in note_block
        
        # Check JSON metadata
        assert "NOTE JSON Metadata" in note_block
        assert '"podcast": "Test Podcast"' in note_block
        assert '"speakers": {' in note_block
    
    def test_to_note_block_minimal(self):
        """Test converting minimal metadata to NOTE block."""
        metadata = VTTMetadata(
            podcast_name="Minimal Podcast",
            episode_title="Minimal Episode",
            publication_date="2024-01-15"
        )
        
        note_block = metadata.to_note_block()
        
        assert "NOTE" in note_block
        assert "Podcast: Minimal Podcast" in note_block
        assert "Episode: Minimal Episode" in note_block
        assert "Date: 2024-01-15" in note_block
        
        # Optional fields should not appear
        assert "Duration:" not in note_block
        assert "Host:" not in note_block
        assert "Guests:" not in note_block
        
        # JSON should only have non-None values
        json_start = note_block.find('{')
        json_str = note_block[json_start:]
        json_data = json.loads(json_str)
        assert "duration" not in json_data
        assert "host" not in json_data
        assert "guests" not in json_data


class TestVTTGenerator:
    """Test VTTGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a VTT generator instance."""
        return VTTGenerator()
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        return VTTMetadata(
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            publication_date="2024-01-15",
            speakers={"SPEAKER_1": "Host", "SPEAKER_2": "Guest"}
        )
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Create sample VTT content."""
        return """00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello and welcome to the podcast.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thanks for having me on the show."""
    
    def test_generate_vtt_basic(self, generator, sample_metadata, sample_vtt_content):
        """Test generating basic VTT file."""
        result = generator.generate_vtt(sample_vtt_content, sample_metadata)
        
        # Check header
        assert result.startswith("WEBVTT\n")
        
        # Check metadata
        assert "NOTE" in result
        assert "Podcast: Test Podcast" in result
        
        # Check content
        assert "00:00:01.000 --> 00:00:05.000" in result
        assert "<v SPEAKER_1>Hello and welcome to the podcast." in result
    
    def test_generate_vtt_with_style(self, generator, sample_metadata, sample_vtt_content):
        """Test generating VTT with style block."""
        result = generator.generate_vtt(sample_vtt_content, sample_metadata)
        
        # Should include style block for speakers
        assert "STYLE" in result
        assert "::cue(v[voice=\"Host\"])" in result
        assert "color: #3498db" in result  # First speaker color
        assert "::cue(v[voice=\"Guest\"])" in result
        assert "color: #2ecc71" in result  # Second speaker color
    
    def test_generate_vtt_save_to_file(self, generator, sample_metadata, sample_vtt_content, temp_dir):
        """Test saving VTT to file."""
        output_path = Path(temp_dir) / "test.vtt"
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = generator.generate_vtt(sample_vtt_content, sample_metadata, output_path)
            
            # Should have called open to write file
            mock_file.assert_called_once_with(output_path, 'w', encoding='utf-8')
            
            # Should have written content
            handle = mock_file()
            handle.write.assert_called_once()
            written_content = handle.write.call_args[0][0]
            assert written_content.startswith("WEBVTT")
    
    def test_process_vtt_content(self, generator):
        """Test processing VTT content."""
        raw_content = """WEBVTT

NOTE This should be removed

00:00:01.000 --> 00:00:05.000
This text has <special> & characters

00:00:05.000 --> 00:00:10.000
<v Speaker>This is voiced text & more"""
        
        processed = generator._process_vtt_content(raw_content)
        
        # Should remove WEBVTT header
        assert not processed.startswith("WEBVTT")
        
        # Should remove NOTE blocks
        assert "NOTE This should be removed" not in processed
        
        # Should escape special characters
        assert "&lt;special&gt; &amp; characters" in processed
        
        # Should preserve voice tags but escape content
        assert "<v Speaker>This is voiced text &amp; more" in processed
    
    def test_escape_cue_text(self, generator):
        """Test escaping special characters in cue text."""
        # Test plain text
        assert generator._escape_cue_text("Test & more") == "Test &amp; more"
        assert generator._escape_cue_text("Test < and >") == "Test &lt; and &gt;"
        
        # Test voice tag preservation
        voice_text = "<v Speaker>Text with & and < characters"
        escaped = generator._escape_cue_text(voice_text)
        assert escaped == "<v Speaker>Text with &amp; and &lt; characters"
    
    def test_is_timestamp_line(self, generator):
        """Test timestamp line detection."""
        # Valid timestamps
        assert generator._is_timestamp_line("00:00:01.000 --> 00:00:05.000")
        assert generator._is_timestamp_line("1:23:45.678 --> 1:23:50.000")
        assert generator._is_timestamp_line("  00:00:01.000 --> 00:00:05.000  ")
        
        # Invalid timestamps
        assert not generator._is_timestamp_line("00:00:01 --> 00:00:05")  # Missing milliseconds
        assert not generator._is_timestamp_line("This is not a timestamp")
        assert not generator._is_timestamp_line("00:00:01.000 -> 00:00:05.000")  # Wrong arrow
    
    def test_normalize_line_endings(self, generator):
        """Test line ending normalization."""
        # Test CRLF to LF
        content = "Line 1\r\nLine 2\r\nLine 3"
        normalized = generator._normalize_line_endings(content)
        assert "\r\n" not in normalized
        assert normalized.count('\n') == 3  # 2 line breaks + final newline
        
        # Test multiple newlines
        content = "Line 1\n\n\n\nLine 2"
        normalized = generator._normalize_line_endings(content)
        assert "\n\n\n" not in normalized
        assert "Line 1\n\nLine 2\n" == normalized
        
        # Test ensuring final newline
        content = "No final newline"
        normalized = generator._normalize_line_endings(content)
        assert normalized.endswith('\n')
    
    def test_generate_style_block(self, generator):
        """Test generating CSS style block."""
        # Test with speakers
        speakers = {
            "SPEAKER_1": "John Doe (Host)",
            "SPEAKER_2": "Jane Smith (Guest)",
            "SPEAKER_3": "Bob Johnson (Guest)"
        }
        
        style = generator._generate_style_block(speakers)
        
        assert style.startswith("STYLE")
        assert "::cue(v[voice=\"John\\ Doe\\ \\(Host\\)\"]) {" in style
        assert "::cue(v[voice=\"Jane\\ Smith\\ \\(Guest\\)\"]) {" in style
        assert "color: #3498db" in style  # First color
        assert "color: #2ecc71" in style  # Second color
        assert "color: #e74c3c" in style  # Third color
        
        # Test with no speakers
        assert generator._generate_style_block(None) is None
        assert generator._generate_style_block({}) is None
    
    def test_sanitize_filename(self, generator):
        """Test filename sanitization."""
        # Test removing invalid characters
        assert generator.sanitize_filename('test<>:"|?*file') == 'test_______file'
        
        # Test removing slashes
        assert generator.sanitize_filename('path/to\\file') == 'path_to_file'
        
        # Test trimming dots and spaces
        assert generator.sanitize_filename('  .filename.  ') == 'filename'
        
        # Test length limit
        long_name = 'a' * 250
        sanitized = generator.sanitize_filename(long_name)
        assert len(sanitized) == 200
        
        # Test empty name
        assert generator.sanitize_filename('') == 'untitled'
        assert generator.sanitize_filename('   ') == 'untitled'
    
    def test_create_metadata_from_episode(self, generator):
        """Test creating metadata from episode data."""
        episode_data = {
            'podcast_name': 'Tech Talk',
            'title': 'AI Discussion',
            'publication_date': '2024-01-15',
            'duration': '45:30',
            'author': 'Default Host',
            'description': 'Discussion about AI'
        }
        
        speaker_mapping = {
            'SPEAKER_1': 'John Smith (Host)',
            'SPEAKER_2': 'Jane Doe (Guest, AI Expert)',
            'SPEAKER_3': 'Bob Johnson (Guest)'
        }
        
        metadata = generator.create_metadata_from_episode(episode_data, speaker_mapping)
        
        assert metadata.podcast_name == 'Tech Talk'
        assert metadata.episode_title == 'AI Discussion'
        assert metadata.host == 'John Smith'  # Extracted from speaker mapping
        assert len(metadata.guests) == 2
        assert 'Jane Doe' in metadata.guests
        assert 'Bob Johnson' in metadata.guests
        assert metadata.speakers == speaker_mapping
    
    def test_create_metadata_from_episode_minimal(self, generator):
        """Test creating metadata from minimal episode data."""
        episode_data = {'title': 'Minimal'}
        
        metadata = generator.create_metadata_from_episode(episode_data)
        
        assert metadata.podcast_name == 'Unknown Podcast'
        assert metadata.episode_title == 'Minimal'
        assert metadata.publication_date == 'Unknown'
        assert metadata.host is None
        assert metadata.guests is None
    
    def test_generate_output_path(self, generator, temp_dir):
        """Test generating output path for VTT file."""
        episode_data = {
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1: Introduction',
            'publication_date': '2024-01-15T10:00:00Z'
        }
        
        output_path = generator.generate_output_path(episode_data, Path(temp_dir))
        
        assert output_path.parent.name == 'Test_Podcast'
        assert output_path.name == '2024-01-15_Episode_1__Introduction.vtt'
        assert output_path.suffix == '.vtt'
    
    def test_generate_output_path_special_cases(self, generator, temp_dir):
        """Test generating output path with special cases."""
        # Test with invalid characters in names
        episode_data = {
            'podcast_name': 'Test/Podcast<>',
            'title': 'Episode:1|Question?',
            'publication_date': 'invalid-date'
        }
        
        output_path = generator.generate_output_path(episode_data, Path(temp_dir))
        
        assert '/' not in output_path.parent.name
        assert '<>' not in output_path.parent.name
        assert ':' not in output_path.name
        assert '|' not in output_path.name
        assert '?' not in output_path.name
    
    def test_vtt_with_checkpoint_manager(self, generator, sample_metadata, sample_vtt_content, temp_dir):
        """Test VTT generation with checkpoint manager."""
        mock_checkpoint = MagicMock()
        generator.checkpoint_manager = mock_checkpoint
        
        output_path = Path(temp_dir) / "test.vtt"
        
        with patch('builtins.open', mock_open()):
            generator.generate_vtt(sample_vtt_content, sample_metadata, output_path)
        
        # Should mark checkpoint stages
        mock_checkpoint.complete_stage.assert_called_with('vtt_generation')
        mock_checkpoint.mark_completed.assert_called_with(str(output_path))