"""Tests for VTT parser functionality."""

from pathlib import Path
import os
import tempfile

import pytest

from src.core.exceptions import ValidationError
from src.core.interfaces import TranscriptSegment
from src.processing.vtt_parser import VTTParser, VTTCue
class TestVTTParser:
    """Test suite for VTT parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = VTTParser()
    
    # Test data samples
    VALID_VTT_SIMPLE = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hello, this is a test.

00:00:02.000 --> 00:00:05.000
This is the second line.
"""

    VALID_VTT_WITH_SPEAKER = """WEBVTT

00:00:00.000 --> 00:00:02.000
<v Speaker1>Hello, I'm the first speaker.

00:00:02.000 --> 00:00:05.000
<v Speaker2>And I'm the second speaker.

00:00:05.000 --> 00:00:08.000
<v Speaker1>Back to the first speaker.
"""

    VALID_VTT_WITH_IDS = """WEBVTT

1
00:00:00.000 --> 00:00:02.000
First cue with ID.

2
00:00:02.000 --> 00:00:05.000
Second cue with ID.
"""

    VALID_VTT_WITH_SETTINGS = """WEBVTT

00:00:00.000 --> 00:00:02.000 position:50% align:center
Centered text with settings.

00:00:02.000 --> 00:00:05.000 align:left size:80%
Left-aligned text.
"""

    VALID_VTT_MULTILINE = """WEBVTT

00:00:00.000 --> 00:00:03.000
This is a multi-line cue.
It has multiple lines of text.
All should be preserved.

00:00:03.000 --> 00:00:06.000
<v Speaker>This also has multiple lines
with a speaker tag.
"""

    INVALID_VTT_NO_HEADER = """00:00:00.000 --> 00:00:02.000
Missing WEBVTT header.
"""

    INVALID_VTT_BAD_TIMESTAMP = """WEBVTT

00:00:00.000 --> invalid_timestamp
Bad timestamp format.
"""

    MALFORMED_VTT_PARTIAL = """WEBVTT

00:00:00.000 --> 00:00:02.000
First cue is fine.

00:00:02.000 -->"""

    # Tests for basic functionality
    def test_parse_simple_vtt(self):
        """Test parsing a simple VTT file."""
        segments = self.parser.parse_content(self.VALID_VTT_SIMPLE)
        
        assert len(segments) == 2
        assert segments[0].text == "Hello, this is a test."
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 2.0
        assert segments[1].text == "This is the second line."
        assert segments[1].start_time == 2.0
        assert segments[1].end_time == 5.0
    
    def test_parse_vtt_with_speakers(self):
        """Test parsing VTT with speaker annotations."""
        segments = self.parser.parse_content(self.VALID_VTT_WITH_SPEAKER)
        
        assert len(segments) == 3
        assert segments[0].speaker == "Speaker1"
        assert segments[0].text == "Hello, I'm the first speaker."
        assert segments[1].speaker == "Speaker2"
        assert segments[1].text == "And I'm the second speaker."
        assert segments[2].speaker == "Speaker1"
        assert segments[2].text == "Back to the first speaker."
    
    def test_parse_vtt_with_cue_ids(self):
        """Test parsing VTT with cue identifiers."""
        segments = self.parser.parse_content(self.VALID_VTT_WITH_IDS)
        
        assert len(segments) == 2
        assert segments[0].text == "First cue with ID."
        assert segments[1].text == "Second cue with ID."
    
    def test_parse_vtt_with_settings(self):
        """Test parsing VTT with cue settings."""
        # Parse the content
        segments = self.parser.parse_content(self.VALID_VTT_WITH_SETTINGS)
        
        assert len(segments) == 2
        # Settings are parsed but not stored in TranscriptSegment
        assert segments[0].text == "Centered text with settings."
        assert segments[1].text == "Left-aligned text."
    
    def test_parse_multiline_cues(self):
        """Test parsing multi-line cues."""
        segments = self.parser.parse_content(self.VALID_VTT_MULTILINE)
        
        assert len(segments) == 2
        # Multi-line text should be preserved with newlines
        assert "This is a multi-line cue." in segments[0].text
        assert "It has multiple lines of text." in segments[0].text
        assert "All should be preserved." in segments[0].text
        
        assert segments[1].speaker == "Speaker"
        assert "This also has multiple lines" in segments[1].text
        assert "with a speaker tag." in segments[1].text
    
    # Tests for timestamp parsing
    def test_parse_timestamp_formats(self):
        """Test various timestamp formats."""
        # Standard format
        assert self.parser._parse_timestamp("00:00:00.000") == 0.0
        assert self.parser._parse_timestamp("00:00:01.000") == 1.0
        assert self.parser._parse_timestamp("00:01:00.000") == 60.0
        assert self.parser._parse_timestamp("01:00:00.000") == 3600.0
        
        # With milliseconds
        assert self.parser._parse_timestamp("00:00:00.500") == 0.5
        assert self.parser._parse_timestamp("00:00:01.250") == 1.25
        
        # Complex times
        assert self.parser._parse_timestamp("01:23:45.678") == 5025.678
    
    def test_invalid_timestamp_format(self):
        """Test invalid timestamp formats."""
        with pytest.raises(ValidationError):
            self.parser._parse_timestamp("invalid")
        
        with pytest.raises(ValidationError):
            self.parser._parse_timestamp("00:00")
        
        with pytest.raises(ValidationError):
            self.parser._parse_timestamp("00:00:00")
    
    # Tests for speaker extraction
    def test_extract_speaker(self):
        """Test speaker extraction from voice spans."""
        assert self.parser._extract_speaker("<v John>Hello") == "John"
        assert self.parser._extract_speaker("<v Jane Doe>Hello") == "Jane Doe"
        assert self.parser._extract_speaker("No speaker here") is None
        assert self.parser._extract_speaker("<v>Empty speaker") == ""
    
    # Tests for error handling
    def test_missing_webvtt_header(self):
        """Test that missing WEBVTT header raises error."""
        with pytest.raises(ValidationError, match="Missing WEBVTT header"):
            self.parser.parse_content(self.INVALID_VTT_NO_HEADER)
    
    def test_invalid_timestamp_in_content(self):
        """Test handling of invalid timestamps in content."""
        # Should skip invalid cues but not crash
        segments = self.parser.parse_content(self.INVALID_VTT_BAD_TIMESTAMP)
        assert len(segments) == 0  # Invalid cue should be skipped
    
    def test_malformed_vtt(self):
        """Test handling of partially malformed VTT."""
        segments = self.parser.parse_content(self.MALFORMED_VTT_PARTIAL)
        assert len(segments) == 1  # Only the valid cue should be parsed
        assert segments[0].text == "First cue is fine."
    
    def test_empty_content(self):
        """Test parsing empty content."""
        with pytest.raises(ValidationError):
            self.parser.parse_content("")
    
    def test_whitespace_only_content(self):
        """Test parsing whitespace-only content."""
        with pytest.raises(ValidationError):
            self.parser.parse_content("   \n\n   ")
    
    # Tests for file operations
    def test_parse_file(self):
        """Test parsing from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(self.VALID_VTT_SIMPLE)
            temp_path = Path(f.name)
        
        try:
            segments = self.parser.parse_file(temp_path)
            assert len(segments) == 2
            assert segments[0].text == "Hello, this is a test."
        finally:
            os.unlink(temp_path)
    
    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file."""
        with pytest.raises(ValidationError, match="VTT file not found"):
            self.parser.parse_file(Path("/nonexistent/file.vtt"))
    
    # Tests for segment merging
    def test_merge_short_segments(self):
        """Test merging short segments."""
        segments = [
            TranscriptSegment(
                id="seg_0",
                text="Hello",
                start_time=0.0,
                end_time=1.0,
                speaker="Speaker1",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_1",
                text="world",
                start_time=1.0,
                end_time=1.5,
                speaker="Speaker1",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_2",
                text="from Python",
                start_time=1.5,
                end_time=5.0,
                speaker="Speaker1",
                confidence=1.0
            )
        ]
        
        merged = self.parser.merge_short_segments(segments, min_duration=2.0)
        
        # First two segments should be merged
        assert len(merged) == 2
        assert merged[0].text == "Hello world"
        assert merged[0].start_time == 0.0
        assert merged[0].end_time == 1.5
        assert merged[1].text == "from Python"
    
    def test_merge_segments_different_speakers(self):
        """Test that segments with different speakers are not merged."""
        segments = [
            TranscriptSegment(
                id="seg_0",
                text="Hello",
                start_time=0.0,
                end_time=1.0,
                speaker="Speaker1",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_1",
                text="world",
                start_time=1.0,
                end_time=1.5,
                speaker="Speaker2",  # Different speaker
                confidence=1.0
            )
        ]
        
        merged = self.parser.merge_short_segments(segments, min_duration=2.0)
        
        # Segments should not be merged due to different speakers
        assert len(merged) == 2
        assert merged[0].text == "Hello"
        assert merged[1].text == "world"
    
    def test_merge_empty_segments_list(self):
        """Test merging empty list of segments."""
        merged = self.parser.merge_short_segments([])
        assert merged == []
    
    # Tests for segment normalization
    def test_normalize_segment(self):
        """Test segment normalization from various formats."""
        # Standard format
        segment_dict = {
            'id': 'test_1',
            'text': 'Test text',
            'start_time': 1.0,
            'end_time': 2.0,
            'speaker': 'TestSpeaker',
            'confidence': 0.95
        }
        
        normalized = self.parser.normalize_segment(segment_dict)
        assert normalized.id == 'test_1'
        assert normalized.text == 'Test text'
        assert normalized.start_time == 1.0
        assert normalized.end_time == 2.0
        assert normalized.speaker == 'TestSpeaker'
        assert normalized.confidence == 0.95
    
    def test_normalize_segment_alternate_fields(self):
        """Test normalization with alternate field names."""
        segment_dict = {
            'index': 5,
            'text': 'Test text',
            'start': 1.0,  # Alternate field name
            'end': 2.0,    # Alternate field name
        }
        
        normalized = self.parser.normalize_segment(segment_dict)
        assert normalized.id == 'seg_5'
        assert normalized.start_time == 1.0
        assert normalized.end_time == 2.0
        assert normalized.confidence == 1.0  # Default value
    
    def test_normalize_segment_minimal(self):
        """Test normalization with minimal data."""
        segment_dict = {
            'text': 'Minimal segment'
        }
        
        normalized = self.parser.normalize_segment(segment_dict)
        assert normalized.id == 'seg_0'
        assert normalized.text == 'Minimal segment'
        assert normalized.start_time == 0.0
        assert normalized.end_time == 0.0
        assert normalized.speaker is None
        assert normalized.confidence == 1.0
    
    # Edge cases
    def test_vtt_with_only_header(self):
        """Test VTT with only header and no cues."""
        vtt_content = "WEBVTT\n\n"
        segments = self.parser.parse_content(vtt_content)
        assert len(segments) == 0
    
    def test_vtt_with_metadata(self):
        """Test VTT with metadata after header."""
        vtt_content = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
Text with metadata.
"""
        segments = self.parser.parse_content(vtt_content)
        assert len(segments) == 1
        assert segments[0].text == "Text with metadata."
    
    def test_cue_with_empty_text(self):
        """Test handling of cue with empty text."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000

00:00:02.000 --> 00:00:04.000
Non-empty text.
"""
        segments = self.parser.parse_content(vtt_content)
        # Empty cues might be skipped or included based on implementation
        assert len(segments) >= 1
        # The non-empty cue should definitely be present
        assert any(seg.text == "Non-empty text." for seg in segments)