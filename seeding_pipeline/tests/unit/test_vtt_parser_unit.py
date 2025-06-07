"""Comprehensive unit tests for VTT parser module."""

from pathlib import Path
from typing import List
from unittest.mock import Mock, patch, mock_open

import pytest

from src.core.exceptions import ValidationError
from src.core.interfaces import TranscriptSegment
from src.vtt.vtt_parser import VTTParser, VTTCue
class TestVTTCue:
    """Test VTTCue dataclass."""
    
    def test_vtt_cue_creation(self):
        """Test creating a VTT cue."""
        cue = VTTCue(
            index=0,
            start_time=1.5,
            end_time=3.0,
            text="Hello world",
            speaker="Speaker1",
            settings={"position": "50%"}
        )
        
        assert cue.index == 0
        assert cue.start_time == 1.5
        assert cue.end_time == 3.0
        assert cue.text == "Hello world"
        assert cue.speaker == "Speaker1"
        assert cue.settings == {"position": "50%"}
    
    def test_vtt_cue_defaults(self):
        """Test VTT cue with default values."""
        cue = VTTCue(
            index=1,
            start_time=0.0,
            end_time=1.0,
            text="Test"
        )
        
        assert cue.speaker is None
        assert cue.settings is None


class TestVTTParser:
    """Test VTT parser functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create a VTT parser instance."""
        return VTTParser()
    
    def test_parser_initialization(self, parser):
        """Test parser initialization."""
        assert parser.cues == []
        assert hasattr(parser, 'TIMESTAMP_PATTERN')
        assert hasattr(parser, 'CUE_TIMING_PATTERN')
        assert hasattr(parser, 'SPEAKER_PATTERN')
    
    def test_parse_file_not_found(self, parser):
        """Test parsing non-existent file."""
        with pytest.raises(ValidationError, match="VTT file not found"):
            parser.parse_file(Path("/non/existent/file.vtt"))
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', mock_open(read_data="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello"))
    def test_parse_file_success(self, mock_exists, parser):
        """Test parsing a valid VTT file."""
        mock_exists.return_value = True
        segments = parser.parse_file(Path("test.vtt"))
        
        assert len(segments) == 1
        assert segments[0].text == "Hello"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 1.0
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', side_effect=IOError("Read error"))
    def test_parse_file_read_error(self, mock_file, mock_exists, parser):
        """Test file read error."""
        mock_exists.return_value = True
        with pytest.raises(ValidationError, match="Failed to read VTT file"):
            parser.parse_file(Path("test.vtt"))
    
    def test_parse_content_missing_header(self, parser):
        """Test parsing content without WEBVTT header."""
        with pytest.raises(ValidationError, match="Missing WEBVTT header"):
            parser.parse_content("00:00:00.000 --> 00:00:01.000\nHello")
    
    def test_parse_content_valid(self, parser):
        """Test parsing valid VTT content."""
        content = """WEBVTT

00:00:00.000 --> 00:00:02.000
First caption

00:00:02.000 --> 00:00:04.000
Second caption
"""
        segments = parser.parse_content(content)
        
        assert len(segments) == 2
        assert segments[0].text == "First caption"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 2.0
        assert segments[1].text == "Second caption"
        assert segments[1].start_time == 2.0
        assert segments[1].end_time == 4.0
    
    def test_parse_content_with_speaker(self, parser):
        """Test parsing content with speaker tags."""
        content = """WEBVTT

00:00:00.000 --> 00:00:02.000
<v Speaker1>Hello there

00:00:02.000 --> 00:00:04.000
<v Speaker2>Hi back
"""
        segments = parser.parse_content(content)
        
        assert len(segments) == 2
        assert segments[0].speaker == "Speaker1"
        assert segments[0].text == "Hello there"
        assert segments[1].speaker == "Speaker2"
        assert segments[1].text == "Hi back"
    
    def test_parse_content_with_settings(self, parser):
        """Test parsing content with cue settings."""
        content = """WEBVTT

00:00:00.000 --> 00:00:02.000 position:50% align:center
Centered text
"""
        parser.parse_content(content)
        
        assert len(parser.cues) == 1
        assert parser.cues[0].settings == {"position": "50%", "align": "center"}
    
    def test_parse_content_with_cue_identifiers(self, parser):
        """Test parsing content with cue identifiers."""
        content = """WEBVTT

cue-1
00:00:00.000 --> 00:00:02.000
First caption

cue-2
00:00:02.000 --> 00:00:04.000
Second caption
"""
        segments = parser.parse_content(content)
        
        assert len(segments) == 2
        assert segments[0].text == "First caption"
        assert segments[1].text == "Second caption"
    
    def test_parse_content_multiline_text(self, parser):
        """Test parsing multi-line captions."""
        content = """WEBVTT

00:00:00.000 --> 00:00:02.000
Line one
Line two
Line three
"""
        segments = parser.parse_content(content)
        
        assert len(segments) == 1
        assert segments[0].text == "Line one\nLine two\nLine three"
    
    def test_is_timestamp_line(self, parser):
        """Test timestamp line detection."""
        assert parser._is_timestamp_line("00:00:00.000 --> 00:00:01.000")
        assert parser._is_timestamp_line("1:23:45.678 --> 1:23:46.789")
        assert not parser._is_timestamp_line("This is not a timestamp")
        assert not parser._is_timestamp_line("")
    
    def test_parse_timestamp_valid(self, parser):
        """Test parsing valid timestamps."""
        assert parser._parse_timestamp("00:00:00.000") == 0.0
        assert parser._parse_timestamp("00:00:01.500") == 1.5
        assert parser._parse_timestamp("00:01:00.000") == 60.0
        assert parser._parse_timestamp("01:00:00.000") == 3600.0
        assert parser._parse_timestamp("1:23:45.678") == 5025.678
    
    def test_parse_timestamp_invalid(self, parser):
        """Test parsing invalid timestamps."""
        with pytest.raises(ValidationError, match="Invalid timestamp format"):
            parser._parse_timestamp("invalid")
        
        with pytest.raises(ValidationError, match="Invalid timestamp format"):
            parser._parse_timestamp("00:00")
        
        with pytest.raises(ValidationError, match="Invalid timestamp format"):
            parser._parse_timestamp("00:00:00")
    
    def test_parse_settings(self, parser):
        """Test parsing cue settings."""
        settings = parser._parse_settings("position:50% align:center size:80%")
        assert settings == {"position": "50%", "align": "center", "size": "80%"}
        
        settings = parser._parse_settings("vertical:rl")
        assert settings == {"vertical": "rl"}
        
        settings = parser._parse_settings("")
        assert settings == {}
        
        settings = parser._parse_settings(None)
        assert settings == {}
    
    def test_extract_speaker(self, parser):
        """Test speaker extraction."""
        assert parser._extract_speaker("<v Speaker1>Hello") == "Speaker1"
        assert parser._extract_speaker("<v John Doe>Speaking") == "John Doe"
        assert parser._extract_speaker("<v>Empty speaker") == ""
        assert parser._extract_speaker("No speaker tag") is None
        assert parser._extract_speaker("<v Speaker1>Multiple <v Speaker2>speakers") == "Speaker1"
    
    def test_convert_to_segments(self, parser):
        """Test converting VTT cues to transcript segments."""
        cues = [
            VTTCue(0, 0.0, 1.0, "First", "Speaker1"),
            VTTCue(1, 1.0, 2.0, "Second", "Speaker2"),
            VTTCue(2, 2.0, 3.0, "Third", None)
        ]
        
        segments = parser._convert_to_segments(cues)
        
        assert len(segments) == 3
        assert all(isinstance(seg, TranscriptSegment) for seg in segments)
        
        assert segments[0].id == "seg_0"
        assert segments[0].text == "First"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 1.0
        assert segments[0].speaker == "Speaker1"
        assert segments[0].confidence == 1.0
        
        assert segments[2].speaker is None
    
    def test_merge_short_segments_basic(self, parser):
        """Test basic segment merging."""
        segments = [
            TranscriptSegment("seg_0", "Hi", 0.0, 0.5, "Speaker1", 1.0),
            TranscriptSegment("seg_1", "there", 0.5, 1.0, "Speaker1", 1.0),
            TranscriptSegment("seg_2", "How are you?", 1.0, 3.0, "Speaker1", 1.0)
        ]
        
        merged = parser.merge_short_segments(segments, min_duration=1.0)
        
        assert len(merged) == 2
        assert merged[0].text == "Hi there"
        assert merged[0].start_time == 0.0
        assert merged[0].end_time == 1.0
        assert merged[1].text == "How are you?"
    
    def test_merge_short_segments_different_speakers(self, parser):
        """Test segment merging with different speakers."""
        segments = [
            TranscriptSegment("seg_0", "Hi", 0.0, 0.5, "Speaker1", 1.0),
            TranscriptSegment("seg_1", "Hello", 0.5, 1.0, "Speaker2", 1.0),
            TranscriptSegment("seg_2", "there", 1.0, 1.5, "Speaker2", 1.0)
        ]
        
        merged = parser.merge_short_segments(segments, min_duration=1.0)
        
        assert len(merged) == 2
        assert merged[0].speaker == "Speaker1"
        assert merged[1].text == "Hello there"
        assert merged[1].speaker == "Speaker2"
    
    def test_merge_short_segments_non_consecutive(self, parser):
        """Test segment merging with non-consecutive segments."""
        segments = [
            TranscriptSegment("seg_0", "Hi", 0.0, 0.5, "Speaker1", 1.0),
            TranscriptSegment("seg_1", "there", 1.0, 1.5, "Speaker1", 1.0),  # Gap
            TranscriptSegment("seg_2", "friend", 1.5, 2.0, "Speaker1", 1.0)
        ]
        
        merged = parser.merge_short_segments(segments, min_duration=1.0)
        
        # Should not merge due to gap
        assert len(merged) == 2
    
    def test_merge_short_segments_empty(self, parser):
        """Test merging empty segment list."""
        assert parser.merge_short_segments([]) == []
    
    def test_merge_short_segments_confidence(self, parser):
        """Test that merging preserves minimum confidence."""
        segments = [
            TranscriptSegment("seg_0", "Hi", 0.0, 0.5, "Speaker1", 0.9),
            TranscriptSegment("seg_1", "there", 0.5, 1.0, "Speaker1", 0.7),
            TranscriptSegment("seg_2", "friend", 1.0, 1.5, "Speaker1", 0.8)
        ]
        
        merged = parser.merge_short_segments(segments, min_duration=2.0)
        
        assert len(merged) == 1
        assert merged[0].confidence == 0.7  # Minimum confidence
    
    def test_normalize_segment_basic(self, parser):
        """Test basic segment normalization."""
        segment_dict = {
            "id": "test_1",
            "text": "Hello world",
            "start_time": 1.5,
            "end_time": 3.0,
            "speaker": "Speaker1",
            "confidence": 0.95
        }
        
        segment = parser.normalize_segment(segment_dict)
        
        assert isinstance(segment, TranscriptSegment)
        assert segment.id == "test_1"
        assert segment.text == "Hello world"
        assert segment.start_time == 1.5
        assert segment.end_time == 3.0
        assert segment.speaker == "Speaker1"
        assert segment.confidence == 0.95
    
    def test_normalize_segment_alternate_fields(self, parser):
        """Test segment normalization with alternate field names."""
        segment_dict = {
            "index": 5,
            "text": "Test text",
            "start": 0.0,
            "end": 2.0
        }
        
        segment = parser.normalize_segment(segment_dict)
        
        assert segment.id == "seg_5"
        assert segment.start_time == 0.0
        assert segment.end_time == 2.0
        assert segment.confidence == 1.0
    
    def test_normalize_segment_missing_fields(self, parser):
        """Test segment normalization with missing fields."""
        segment_dict = {}
        
        segment = parser.normalize_segment(segment_dict)
        
        assert segment.id == "seg_0"
        assert segment.text == ""
        assert segment.start_time == 0.0
        assert segment.end_time == 0.0
        assert segment.speaker is None
        assert segment.confidence == 1.0
    
    def test_parse_complex_vtt(self, parser):
        """Test parsing a complex VTT file with various features."""
        content = """WEBVTT
Kind: captions
Language: en

NOTE
This is a comment

00:00:00.000 --> 00:00:02.500 align:start position:0%
<v Speaker1>Welcome to our podcast.

00:00:02.500 --> 00:00:05.000
<v Speaker2>Thanks for having me!

NOTE Another comment

1
00:00:05.000 --> 00:00:08.000 line:90%
<v Speaker1>Let's talk about
technology today.

00:00:08.000 --> 00:00:10.000
<v>And the future of AI.
"""
        segments = parser.parse_content(content)
        
        assert len(segments) == 4
        assert segments[0].speaker == "Speaker1"
        assert segments[0].text == "Welcome to our podcast."
        assert segments[1].speaker == "Speaker2"
        assert segments[2].text == "Let's talk about\ntechnology today."
        assert segments[3].speaker == ""  # Empty speaker tag
        assert segments[3].text == "And the future of AI."