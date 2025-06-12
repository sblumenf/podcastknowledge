"""Core tests for VTT parser functionality."""

from pathlib import Path

import pytest

from src.core.exceptions import ValidationError
from src.vtt.vtt_parser import VTTParser
class TestVTTParserCore:
    """Core tests for VTT parsing functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create VTT parser instance."""
        return VTTParser()
    
    @pytest.fixture
    def vtt_samples_dir(self):
        """Get path to VTT samples directory."""
        return Path(__file__).parent.parent / "fixtures" / "vtt_samples"
    
    def test_parse_minimal_vtt(self, parser, vtt_samples_dir):
        """Test parsing minimal VTT file."""
        vtt_file = vtt_samples_dir / "minimal.vtt"
        
        # Parse the file
        segments = parser.parse_file(vtt_file)
        
        # Verify correct number of segments
        assert len(segments) > 0, "Should parse at least one segment"
        
        # Verify first segment
        first_segment = segments[0]
        assert hasattr(first_segment, 'start_time')
        assert hasattr(first_segment, 'end_time')
        assert hasattr(first_segment, 'text')
        assert first_segment.start_time >= 0
        assert first_segment.end_time > first_segment.start_time
        assert len(first_segment.text) > 0
    
    def test_parse_standard_vtt(self, parser, vtt_samples_dir):
        """Test parsing standard VTT file with multiple features."""
        vtt_file = vtt_samples_dir / "standard.vtt"
        
        # Parse the file
        segments = parser.parse_file(vtt_file)
        
        # Verify multiple segments parsed
        assert len(segments) > 1, "Should parse multiple segments"
        
        # Verify timestamps are sequential
        for i in range(1, len(segments)):
            assert segments[i].start_time >= segments[i-1].end_time, \
                f"Segment {i} should start after previous segment ends"
        
        # Verify all segments have content
        for i, segment in enumerate(segments):
            assert segment.text and segment.text.strip(), \
                f"Segment {i} should have non-empty text"
    
    def test_handle_malformed_vtt(self, parser):
        """Test handling of malformed VTT content."""
        malformed_content = """NOT A VTT FILE
        
        This is just random text
        00:00:00 -> 00:00:05
        With bad formatting
        """
        
        # Should either raise error or return empty list
        try:
            result = parser.parse_content(malformed_content)
            # If no error, should return empty or handle gracefully
            assert isinstance(result, list)
        except ValidationError:
            # Expected behavior - malformed VTT raises error
            pass
    
    def test_parse_empty_file(self, parser):
        """Test parsing empty VTT file."""
        empty_content = """WEBVTT
        
        """
        
        # Parse empty VTT
        segments = parser.parse_content(empty_content)
        
        # Should return empty list, not error
        assert isinstance(segments, list)
        assert len(segments) == 0
    
    def test_parse_large_timestamps(self, parser):
        """Test parsing VTT with timestamps > 1 hour."""
        long_content = """WEBVTT
        
        01:30:00.000 --> 01:30:05.000
        Content after 90 minutes
        
        02:45:30.500 --> 02:45:35.000  
        Content after 2 hours 45 minutes
        """
        
        # Parse content with large timestamps
        segments = parser.parse_content(long_content)
        
        assert len(segments) == 2
        
        # Verify first segment (90 minutes)
        assert segments[0].start_time == 90 * 60  # 5400 seconds
        assert segments[0].end_time == 90 * 60 + 5  # 5405 seconds
        
        # Verify second segment (2:45:30)
        expected_start = 2 * 3600 + 45 * 60 + 30.5  # 9930.5 seconds
        assert abs(segments[1].start_time - expected_start) < 0.01
    
    def test_parse_vtt_with_speakers(self, parser):
        """Test parsing VTT with speaker tags."""
        speaker_content = """WEBVTT
        
        00:00:00.000 --> 00:00:05.000
        <v John> Hello, I'm John.
        
        00:00:05.000 --> 00:00:10.000
        <v Sarah> Hi John, I'm Sarah.
        """
        
        # Parse content with speakers
        segments = parser.parse_content(speaker_content)
        
        assert len(segments) == 2
        
        # Check if parser extracts speaker information
        # (Implementation may vary - check for speaker in text or as attribute)
        assert "John" in segments[0].text or (hasattr(segments[0], 'speaker') and segments[0].speaker == "John")
        assert "Sarah" in segments[1].text or (hasattr(segments[1], 'speaker') and segments[1].speaker == "Sarah")
    
    def test_parse_multiline_cues(self, parser):
        """Test parsing VTT with multi-line cue text."""
        multiline_content = """WEBVTT
        
        00:00:00.000 --> 00:00:05.000
        This is a cue with
        multiple lines of text
        that should be preserved.
        
        00:00:05.000 --> 00:00:10.000
        Single line cue.
        """
        
        # Parse content
        segments = parser.parse_content(multiline_content)
        
        assert len(segments) == 2
        
        # First segment should contain all lines
        assert "multiple lines" in segments[0].text
        assert "preserved" in segments[0].text
        
        # Second segment is single line
        assert "Single line" in segments[1].text
    
    def test_timestamp_parsing_edge_cases(self, parser):
        """Test edge cases in timestamp parsing."""
        edge_cases = """WEBVTT
        
        00:00:00.000 --> 00:00:00.001
        Very short duration
        
        00:00:00.999 --> 00:00:01.000
        Millisecond precision
        
        23:59:59.999 --> 24:00:00.000
        Day boundary
        """
        
        # Parse edge cases
        segments = parser.parse_content(edge_cases)
        
        assert len(segments) == 3
        
        # Very short duration
        assert segments[0].end_time - segments[0].start_time == 0.001
        
        # Millisecond precision
        assert abs(segments[1].start_time - 0.999) < 0.001
        assert abs(segments[1].end_time - 1.0) < 0.001
        
        # Day boundary
        assert segments[2].start_time == 23 * 3600 + 59 * 60 + 59.999
    
    def test_vtt_with_metadata(self, parser):
        """Test parsing VTT with NOTE and other metadata."""
        metadata_content = """WEBVTT
        Kind: captions
        Language: en
        
        NOTE
        This is a comment that should be ignored
        
        00:00:00.000 --> 00:00:05.000
        Actual content after metadata
        
        NOTE Another comment
        
        00:00:05.000 --> 00:00:10.000
        More content
        """
        
        # Parse content with metadata
        segments = parser.parse_content(metadata_content)
        
        # Should only parse actual segments, not metadata
        assert len(segments) == 2
        assert "Actual content" in segments[0].text
        assert "More content" in segments[1].text
        
        # Comments should not appear in segments
        for segment in segments:
            assert "NOTE" not in segment.text
            assert "comment" not in segment.text