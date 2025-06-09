"""
Shared VTT test fixtures for efficient testing.

This module provides reusable VTT data and mocks to reduce test setup overhead
and improve test performance.
"""

from pathlib import Path
from typing import List, Dict, Any
import tempfile
import shutil

import pytest

from src.core.interfaces import TranscriptSegment
from src.vtt.vtt_parser import VTTParser, VTTCue
from src.vtt.vtt_segmentation import VTTSegmenter


# Sample VTT content for testing
SAMPLE_VTT_CONTENT = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to TechTalk podcast. Today we're discussing AI in healthcare.

00:00:05.000 --> 00:00:10.000
<v Host>I'm joined by Dr. Sarah Johnson, an AI researcher.

00:00:10.000 --> 00:00:15.000
<v Dr. Johnson>Thanks for having me. I'm excited to share our latest findings.

00:00:15.000 --> 00:00:20.000
<v Dr. Johnson>We've developed a machine learning model that can detect cancer with 97% accuracy.

00:00:20.000 --> 00:00:25.000
<v Host>That's incredible! How does it work?

00:00:25.000 --> 00:00:30.000
<v Dr. Johnson>It analyzes medical imaging using advanced neural networks.
"""

MINIMAL_VTT_CONTENT = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello world.
"""

COMPLEX_VTT_CONTENT = """WEBVTT
Kind: captions
Language: en

NOTE
This is a complex VTT file with multiple features

1
00:00:00.000 --> 00:00:03.000 position:50% align:center
Welcome to our show.

2
00:00:03.000 --> 00:00:06.000
<v Speaker1>This has multiple lines
of text that should be preserved.

3
00:00:06.000 --> 00:00:10.000 align:left size:80%
<v Speaker2>Thanks to our sponsor, TechCorp,
for making this episode possible.
"""


@pytest.fixture(scope="session")
def vtt_parser():
    """Shared VTT parser instance."""
    return VTTParser()


@pytest.fixture(scope="session")
def vtt_segmenter():
    """Shared VTT segmenter instance."""
    return VTTSegmenter()


@pytest.fixture
def sample_vtt_content():
    """Basic sample VTT content."""
    return SAMPLE_VTT_CONTENT


@pytest.fixture
def minimal_vtt_content():
    """Minimal VTT content for simple tests."""
    return MINIMAL_VTT_CONTENT


@pytest.fixture
def complex_vtt_content():
    """Complex VTT content with multiple features."""
    return COMPLEX_VTT_CONTENT


@pytest.fixture
def temp_vtt_file(tmp_path):
    """Create a temporary VTT file."""
    vtt_file = tmp_path / "test.vtt"
    vtt_file.write_text(SAMPLE_VTT_CONTENT)
    return vtt_file


@pytest.fixture
def multiple_vtt_files(tmp_path):
    """Create multiple VTT files for batch testing."""
    files = []
    
    # Episode 1
    ep1 = tmp_path / "episode1.vtt"
    ep1.write_text(SAMPLE_VTT_CONTENT)
    files.append(ep1)
    
    # Episode 2  
    ep2 = tmp_path / "episode2.vtt"
    ep2.write_text("""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome back to episode 2 of TechTalk.

00:00:05.000 --> 00:00:10.000
<v Host>Today we're exploring quantum computing.

00:00:10.000 --> 00:00:15.000
<v Guest>Quantum computers will revolutionize cryptography.
""")
    files.append(ep2)
    
    # Episode 3 (minimal)
    ep3 = tmp_path / "episode3.vtt"
    ep3.write_text(MINIMAL_VTT_CONTENT)
    files.append(ep3)
    
    return files


@pytest.fixture
def parsed_segments():
    """Pre-parsed VTT segments to avoid parsing overhead."""
    return [
        TranscriptSegment(
            id="seg_0",
            text="Welcome to TechTalk podcast. Today we're discussing AI in healthcare.",
            start_time=0.0,
            end_time=5.0,
            speaker="Host",
            confidence=1.0
        ),
        TranscriptSegment(
            id="seg_1", 
            text="I'm joined by Dr. Sarah Johnson, an AI researcher.",
            start_time=5.0,
            end_time=10.0,
            speaker="Host",
            confidence=1.0
        ),
        TranscriptSegment(
            id="seg_2",
            text="Thanks for having me. I'm excited to share our latest findings.",
            start_time=10.0,
            end_time=15.0,
            speaker="Dr. Johnson",
            confidence=1.0
        ),
        TranscriptSegment(
            id="seg_3",
            text="We've developed a machine learning model that can detect cancer with 97% accuracy.",
            start_time=15.0,
            end_time=20.0,
            speaker="Dr. Johnson",
            confidence=1.0
        ),
        TranscriptSegment(
            id="seg_4",
            text="That's incredible! How does it work?",
            start_time=20.0,
            end_time=25.0,
            speaker="Host",
            confidence=1.0
        ),
        TranscriptSegment(
            id="seg_5",
            text="It analyzes medical imaging using advanced neural networks.",
            start_time=25.0,
            end_time=30.0,
            speaker="Dr. Johnson",
            confidence=1.0
        )
    ]


@pytest.fixture
def vtt_cues():
    """Pre-created VTT cues for testing."""
    return [
        VTTCue(
            index=0,
            start_time=0.0,
            end_time=5.0,
            text="Welcome to TechTalk podcast. Today we're discussing AI in healthcare.",
            speaker="Host"
        ),
        VTTCue(
            index=1,
            start_time=5.0,
            end_time=10.0,
            text="I'm joined by Dr. Sarah Johnson, an AI researcher.",
            speaker="Host"
        ),
        VTTCue(
            index=2,
            start_time=10.0,
            end_time=15.0,
            text="Thanks for having me. I'm excited to share our latest findings.",
            speaker="Dr. Johnson"
        )
    ]


@pytest.fixture
def mock_vtt_processing_result():
    """Mock result from VTT processing pipeline."""
    return {
        "transcript": [
            {
                "text": "Welcome to TechTalk podcast. Today we're discussing AI in healthcare.",
                "start_time": 0.0,
                "end_time": 5.0,
                "speaker": "Host",
                "segment_index": 0,
                "word_count": 11,
                "duration_seconds": 5.0,
                "is_advertisement": False,
                "sentiment": {
                    "score": 0.2,
                    "polarity": "positive",
                    "positive_count": 1,
                    "negative_count": 0
                }
            }
        ],
        "metadata": {
            "total_segments": 6,
            "total_duration": 30.0,
            "total_words": 68,
            "average_segment_duration": 5.0,
            "advertisement_count": 0,
            "advertisement_percentage": 0.0,
            "unique_speakers": 2,
            "speakers": ["Dr. Johnson", "Host"],
            "sentiment_distribution": {
                "positive": 0.5,
                "negative": 0.0,
                "neutral": 0.5
            }
        }
    }


# Cached VTT data for performance
_CACHED_PARSED_SEGMENTS = None


@pytest.fixture(scope="session")
def cached_parsed_segments(vtt_parser):
    """Session-scoped parsed segments to avoid re-parsing."""
    global _CACHED_PARSED_SEGMENTS
    if _CACHED_PARSED_SEGMENTS is None:
        _CACHED_PARSED_SEGMENTS = vtt_parser.parse_content(SAMPLE_VTT_CONTENT)
    return _CACHED_PARSED_SEGMENTS