"""Shared pytest fixtures for the podcast transcription pipeline tests."""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from io import StringIO
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

# Import test fixtures
from tests.fixtures.config import test_config, mock_env_vars, test_config_minimal
from tests.fixtures.mocks import (
    mock_google_generativeai, mock_feedparser_module, mock_file_system,
    mock_tenacity, mock_datetime, mock_progress_bar, mock_usage_state,
    mock_checkpoint_state, mock_all_external_deps
)
from src.config import Config


# === Configuration Fixtures ===

@pytest.fixture
def mock_config():
    """Create a mock configuration for unit tests.
    
    Usage:
        def test_orchestrator_with_mock(mock_config):
            orchestrator = TranscriptionOrchestrator(config=mock_config)
            # Test with fully controlled config mock
    """
    config = Mock(spec=Config)
    
    # Set up common config attributes
    config.api = Mock(
        timeout=10,
        max_attempts=1,
        backoff_multiplier=2,
        max_backoff=10,
        max_episodes_per_day=12,
        max_requests_per_key=25,
        max_tokens_per_key=1000000
    )
    config.processing = Mock(
        parallel_workers=1,
        enable_progress_bar=False,
        checkpoint_enabled=True,
        max_episode_length=60,
        quota_wait_enabled=False,
        max_quota_wait_hours=0,
        quota_check_interval_minutes=1
    )
    config.validation = Mock(
        enabled=True,
        min_coverage_ratio=0.85,
        max_continuation_attempts=3
    )
    config.output = Mock(
        default_dir='test_output',
        naming_pattern='{podcast_name}/{date}_{episode_title}.vtt',
        sanitize_filenames=True,
        max_filename_length=200,
        include_metadata=True,
        speaker_voice_tags=True,
        timestamp_precision=3
    )
    config.logging = Mock(
        console_level='WARNING',
        file_level='DEBUG',
        max_file_size_mb=10,
        backup_count=5,
        log_dir='test_logs'
    )
    config.security = Mock(
        api_key_vars=['TEST_API_KEY_1', 'TEST_API_KEY_2'],
        rotation_strategy='round_robin',
        fail_over_enabled=True
    )
    config.youtube_search = Mock(
        enabled=True,
        method='rss_only',
        cache_results=True,
        fuzzy_match_threshold=0.85,
        duration_tolerance=0.1,
        max_search_results=5
    )
    config.development = Mock(
        dry_run=False,
        debug_mode=True,
        save_raw_responses=False,
        test_mode=True,
        mock_api_calls=True
    )
    
    # Add methods that might be called
    config.get_api_keys = Mock(return_value=['test_key_1', 'test_key_2'])
    config.to_dict = Mock(return_value={})
    config.validate = Mock()
    
    return config


# === Efficient Test Data Fixtures ===

@pytest.fixture
def minimal_vtt_content():
    """Minimal VTT content (< 200 bytes)."""
    return """WEBVTT

00:00:01.000 --> 00:00:03.000
Test content.
"""


@pytest.fixture
def minimal_rss_feed():
    """Minimal RSS feed structure with single episode."""
    return {
        'feed': {
            'title': 'Test Pod',
            'description': 'Test',
            'link': 'https://test.com'
        },
        'entries': [{
            'title': 'Ep1',
            'description': 'Test',
            'published': 'Mon, 01 Jan 2024 00:00:00 GMT',
            'link': 'https://test.com/1',
            'enclosures': [{'href': 'https://test.com/1.mp3'}]
        }]
    }


@pytest.fixture
def minimal_episode_metadata():
    """Minimal episode metadata for testing."""
    return {
        'title': 'Test Ep',
        'podcast_name': 'Test Pod',
        'guid': 'test-guid-1',
        'audio_url': 'https://test.com/1.mp3',
        'published_date': '2024-01-01'
    }


@pytest.fixture
def mock_transcript_response():
    """Minimal mock Gemini transcript response."""
    mock = MagicMock()
    mock.text = minimal_vtt_content()
    return mock


@pytest.fixture
def mock_speaker_response():
    """Minimal mock speaker identification response."""
    mock = MagicMock()
    mock.text = json.dumps({
        "SPEAKER_1": "Host"
    })
    return mock


# === File System Fixtures Using tmp_path ===

@pytest.fixture
def test_data_dir(tmp_path):
    """Create a test data directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create subdirectories
    (data_dir / "transcripts").mkdir()
    (data_dir / "checkpoints").mkdir()
    
    return data_dir


@pytest.fixture
def test_config_file(tmp_path):
    """Create a minimal test config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
api:
  timeout: 30
  retry:
    max_attempts: 2
output:
  default_dir: "data/transcripts"
logging:
  console_level: "INFO"
  log_dir: "logs"
""")
    return config_file


@pytest.fixture  
def mock_progress_file(tmp_path):
    """Create an in-memory progress tracker."""
    class InMemoryProgressFile:
        def __init__(self):
            self.data = {"episodes": {}, "meta": {}}
            
        def read(self):
            return json.dumps(self.data)
            
        def write(self, content):
            self.data = json.loads(content)
            
        def exists(self):
            return True
    
    return InMemoryProgressFile()


# === In-Memory Mock Fixtures ===

@pytest.fixture
def mock_logger():
    """Mock logger that captures log messages in memory."""
    class InMemoryLogger:
        def __init__(self):
            self.messages = []
            
        def _log(self, level, msg, *args):
            self.messages.append((level, msg % args if args else msg))
            
        def debug(self, msg, *args):
            self._log('DEBUG', msg, *args)
            
        def info(self, msg, *args):
            self._log('INFO', msg, *args)
            
        def warning(self, msg, *args):
            self._log('WARNING', msg, *args)
            
        def error(self, msg, *args):
            self._log('ERROR', msg, *args)
            
        def clear(self):
            self.messages = []
    
    return InMemoryLogger()


@pytest.fixture
def mock_gemini_client():
    """Lightweight mock Gemini client."""
    mock = MagicMock()
    mock.api_keys = ['test_key_1']
    mock.generate_content_async = AsyncMock()
    mock.get_usage_summary.return_value = {
        'key_1': {'requests_today': 0, 'tokens_today': 0}
    }
    return mock


@pytest.fixture
def in_memory_file_store():
    """In-memory file storage for testing."""
    class InMemoryFileStore:
        def __init__(self):
            self.files = {}
            
        def write(self, path, content):
            self.files[str(path)] = content
            
        def read(self, path):
            return self.files.get(str(path), '')
            
        def exists(self, path):
            return str(path) in self.files
            
        def list_files(self):
            return list(self.files.keys())
            
        def clear(self):
            self.files = {}
    
    return InMemoryFileStore()


# === Performance-Optimized Fixtures ===

@pytest.fixture(scope="session")
def shared_test_config():
    """Session-scoped config to avoid repeated parsing."""
    return {
        'api': {
            'timeout': 30,
            'retry': {'max_attempts': 2},
            'quota': {'max_episodes_per_day': 12}
        },
        'output': {
            'default_dir': 'data/transcripts',
            'naming': {'pattern': '{podcast_name}/{date}_{episode_title}.vtt'}
        },
        'logging': {
            'console_level': 'INFO',
            'log_dir': 'logs'
        }
    }


@pytest.fixture
def fast_mock_feed_parser():
    """Ultra-fast feed parser mock."""
    def parse(url):
        return {
            'feed': {'title': 'Test'},
            'entries': [{'title': 'Ep1', 'link': url}],
            'bozo': False
        }
    
    mock = MagicMock()
    mock.parse = parse
    return mock


# === Automatic Cleanup Fixtures ===

@pytest.fixture(autouse=True)
def cleanup_environment(tmp_path, monkeypatch):
    """Automatically set up and clean test environment."""
    # Set minimal test API keys
    monkeypatch.setenv('GEMINI_API_KEY_1', 'test_key_1')
    
    # Use isolated state directory for each test
    test_state_dir = tmp_path / "test_state"
    test_state_dir.mkdir()
    monkeypatch.setenv('STATE_DIR', str(test_state_dir))
    
    yield
    
    # Cleanup happens automatically via tmp_path


@pytest.fixture
def mock_file_operations():
    """Mock file operations for tests that need it."""
    def mock_open_in_memory(file, mode='r', *args, **kwargs):
        """Mock open() to use StringIO for in-memory operations."""
        if 'b' in mode:
            from io import BytesIO
            return BytesIO()
        return StringIO()
    
    with patch('builtins.open', mock_open_in_memory):
        yield


# === Deprecated fixtures for backward compatibility ===

@pytest.fixture
def temp_dir(tmp_path):
    """DEPRECATED: Use tmp_path directly instead."""
    return str(tmp_path)


@pytest.fixture
def sample_episode_metadata():
    """DEPRECATED: Use minimal_episode_metadata instead."""
    from src.file_organizer import EpisodeMetadata
    return EpisodeMetadata(
        title="Test Episode",
        podcast_name="Test Podcast", 
        published_date="2024-01-15",
        file_path="Test_Podcast/2024-01-15_Test_Episode.vtt",
        speakers=["Host"],
        duration=1800,
        episode_number=1,
        description="Test"
    )


@pytest.fixture
def sample_vtt_content():
    """DEPRECATED: Use minimal_vtt_content instead."""
    return minimal_vtt_content()


@pytest.fixture
def mock_rss_feed():
    """DEPRECATED: Use minimal_rss_feed instead."""
    return minimal_rss_feed()


@pytest.fixture
def config_file_content():
    """DEPRECATED: Use test_config_file instead."""
    return """api:
  timeout: 300
output:
  default_dir: "data/transcripts"
logging:
  console_level: "INFO"
"""