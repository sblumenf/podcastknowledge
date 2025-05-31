"""Shared pytest fixtures for the podcast transcription pipeline tests."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after the test."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock the logger to avoid logging during tests."""
    mock = Mock()
    monkeypatch.setattr('src.utils.logging.get_logger', lambda name: mock)
    return mock


@pytest.fixture
def sample_episode_metadata():
    """Provide sample episode metadata for testing."""
    from src.file_organizer import EpisodeMetadata
    return EpisodeMetadata(
        title="Test Episode",
        podcast_name="Test Podcast",
        publication_date="2024-01-15",
        file_path="Test_Podcast/2024-01-15_Test_Episode.vtt",
        speakers=["Host", "Guest"],
        duration=1800,
        episode_number=1,
        description="A test episode for unit testing"
    )


@pytest.fixture
def sample_vtt_content():
    """Provide sample VTT content for testing."""
    return """WEBVTT

00:00:01.000 --> 00:00:05.000
Hello and welcome to the test podcast.

00:00:05.000 --> 00:00:10.000
Today we're discussing unit testing.
"""


@pytest.fixture
def mock_rss_feed():
    """Provide a mock RSS feed structure."""
    return {
        'feed': {
            'title': 'Test Podcast',
            'description': 'A podcast for testing',
            'link': 'https://example.com/podcast'
        },
        'entries': [
            {
                'title': 'Episode 1: Introduction',
                'description': 'First test episode',
                'published': 'Mon, 15 Jan 2024 10:00:00 GMT',
                'link': 'https://example.com/episode1',
                'enclosures': [{'href': 'https://example.com/episode1.mp3', 'type': 'audio/mpeg'}]
            },
            {
                'title': 'Episode 2: Deep Dive',
                'description': 'Second test episode',
                'published': 'Mon, 22 Jan 2024 10:00:00 GMT',
                'link': 'https://example.com/episode2',
                'enclosures': [{'href': 'https://example.com/episode2.mp3', 'type': 'audio/mpeg'}]
            }
        ]
    }


@pytest.fixture
def mock_gemini_response():
    """Provide a mock Gemini API response for transcription."""
    return {
        'candidates': [{
            'content': {
                'parts': [{
                    'text': """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello and welcome to our podcast.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thanks for having me on the show.

00:00:10.000 --> 00:00:15.000
<v SPEAKER_1>Today we'll discuss testing strategies.
"""
                }]
            }
        }]
    }


@pytest.fixture
def mock_speaker_identification_response():
    """Provide a mock response for speaker identification."""
    return {
        'candidates': [{
            'content': {
                'parts': [{
                    'text': """Speaker Identification Results:
SPEAKER_1: John Smith (Host)
SPEAKER_2: Jane Doe (Guest, Software Engineer)
"""
                }]
            }
        }]
    }


@pytest.fixture
def config_file_content():
    """Provide sample configuration file content."""
    return """# Test Configuration
api:
  timeout: 300
  retry:
    max_attempts: 2
    backoff_multiplier: 2
    max_backoff: 30
  quota:
    max_episodes_per_day: 12
    max_requests_per_key: 25
    max_tokens_per_key: 1000000

processing:
  parallel_workers: 1
  enable_progress_bar: true
  checkpoint_enabled: true
  max_episode_length: 60

output:
  default_dir: "data/transcripts"
  naming:
    pattern: "{podcast_name}/{date}_{episode_title}.vtt"
    sanitize_filenames: true
    max_filename_length: 200
  vtt:
    include_metadata: true
    speaker_voice_tags: true
    timestamp_precision: 3

logging:
  console_level: "INFO"
  file_level: "DEBUG"
  max_file_size_mb: 10
  backup_count: 5
  log_dir: "logs"

security:
  api_key_vars:
    - "GEMINI_API_KEY_1"
    - "GEMINI_API_KEY_2"
  rotation:
    strategy: "round_robin"
    fail_over_enabled: true

development:
  dry_run: false
  debug_mode: false
  save_raw_responses: false
  test_mode: false
  mock_api_calls: false
"""