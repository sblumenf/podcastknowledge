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

# Import test fixtures
from tests.fixtures.config import test_config, mock_env_vars, test_config_minimal
from tests.fixtures.mocks import (
    mock_google_generativeai, mock_feedparser_module, mock_file_system,
    mock_tenacity, mock_datetime, mock_progress_bar, mock_usage_state,
    mock_checkpoint_state, mock_all_external_deps
)


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


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Automatically set up test environment for all tests."""
    # Set default test API keys if not already set
    if 'GEMINI_API_KEY_1' not in os.environ:
        monkeypatch.setenv('GEMINI_API_KEY_1', 'test_key_1')
    if 'GEMINI_API_KEY_2' not in os.environ:
        monkeypatch.setenv('GEMINI_API_KEY_2', 'test_key_2')


@pytest.fixture
def mock_gemini_client():
    """Mock Google Generative AI client."""
    mock_client = MagicMock()
    mock_model = MagicMock()
    
    # Mock the model's generate_content method
    mock_response = MagicMock()
    mock_response.text = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to the test podcast.

00:00:05.000 --> 00:00:10.000
<v Guest>Thanks for having me.
"""
    mock_model.generate_content.return_value = mock_response
    
    # Mock the client to return the model
    mock_client.GenerativeModel.return_value = mock_model
    
    return mock_client


@pytest.fixture
def mock_feedparser():
    """Mock feedparser for RSS feed parsing."""
    mock_parser = MagicMock()
    mock_parser.parse.return_value = {
        'feed': {
            'title': 'Test Podcast',
            'description': 'A test podcast',
            'link': 'https://example.com/podcast'
        },
        'entries': [
            {
                'title': 'Test Episode',
                'description': 'Test episode description',
                'published': 'Mon, 15 Jan 2024 10:00:00 GMT',
                'link': 'https://example.com/episode1',
                'enclosures': [{'href': 'https://example.com/episode1.mp3'}]
            }
        ],
        'bozo': False
    }
    return mock_parser


@pytest.fixture
def mock_file_operations(tmp_path):
    """Mock file system operations to use temporary directory."""
    import builtins
    original_open = builtins.open
    
    def mock_open(file, mode='r', *args, **kwargs):
        # Convert to Path object for easier manipulation
        file_path = Path(file)
        
        # If it's a relative path or specific test paths, redirect to tmp_path
        if not file_path.is_absolute() or 'test' in str(file_path):
            file_path = tmp_path / file_path.name
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        return original_open(str(file_path), mode, *args, **kwargs)
    
    return mock_open


@pytest.fixture
def mock_network_requests():
    """Mock network requests for external APIs."""
    import requests
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'status': 'ok'}
    mock_response.text = 'Mock response'
    mock_session.get.return_value = mock_response
    mock_session.post.return_value = mock_response
    
    return mock_session