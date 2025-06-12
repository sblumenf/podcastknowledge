"""Mock objects and fixtures for external dependencies.

This module provides comprehensive mocking for all external services
and dependencies used in the podcast transcription pipeline.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path
import tempfile
import json
from datetime import datetime


@pytest.fixture
def mock_google_generativeai(monkeypatch):
    """Mock the entire google.generativeai module."""
    mock_genai = MagicMock()
    
    # Mock GenerativeModel class
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Mocked transcription response"
    mock_response.candidates = [{
        'content': {
            'parts': [{'text': 'WEBVTT\\n\\n00:00:00.000 --> 00:00:05.000\\nMocked transcript'}]
        }
    }]
    
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    
    # Mock configure method
    mock_genai.configure = MagicMock()
    
    # Patch the import
    monkeypatch.setattr('google.generativeai', mock_genai)
    monkeypatch.setattr('src.gemini_client.genai', mock_genai)
    
    return mock_genai


@pytest.fixture
def mock_feedparser_module(monkeypatch):
    """Mock the feedparser module for RSS feed parsing."""
    def mock_parse(url):
        return {
            'feed': {
                'title': 'Mock Podcast',
                'description': 'A mocked podcast feed',
                'link': url,
                'language': 'en-us',
                'itunes_author': 'Mock Author',
                'itunes_category': {'text': 'Technology'},
                'image': {'href': 'https://example.com/mock.jpg'}
            },
            'entries': [
                {
                    'title': 'Mock Episode 1',
                    'description': 'First mock episode',
                    'published': 'Mon, 15 Jan 2024 10:00:00 GMT',
                    'published_parsed': (2024, 1, 15, 10, 0, 0, 0, 15, 0),
                    'link': 'https://example.com/episode1',
                    'enclosures': [{'href': 'https://example.com/episode1.mp3', 'type': 'audio/mpeg'}],
                    'itunes_duration': '30:00',
                    'itunes_episode': '1'
                }
            ],
            'bozo': False
        }
    
    mock_module = MagicMock()
    mock_module.parse = mock_parse
    
    monkeypatch.setattr('feedparser', mock_module)
    monkeypatch.setattr('src.feed_parser.feedparser', mock_module)
    
    return mock_module


@pytest.fixture
def mock_file_system(tmp_path):
    """Mock file system operations with temporary directory."""
    class MockFileSystem:
        def __init__(self, base_path):
            self.base_path = Path(base_path)
            self.files = {}
        
        def write_file(self, path, content):
            """Write content to a mocked file."""
            full_path = self.base_path / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            self.files[str(path)] = content
            return full_path
        
        def read_file(self, path):
            """Read content from a mocked file."""
            full_path = self.base_path / path
            if full_path.exists():
                return full_path.read_text()
            return self.files.get(str(path), '')
        
        def exists(self, path):
            """Check if a mocked file exists."""
            full_path = self.base_path / path
            return full_path.exists() or str(path) in self.files
        
        def list_files(self, pattern='*'):
            """List files in the mocked file system."""
            return list(self.base_path.rglob(pattern))
    
    return MockFileSystem(tmp_path)


@pytest.fixture
def mock_tenacity(monkeypatch):
    """Mock tenacity retry library to avoid delays in tests."""
    # Create a mock that immediately returns the wrapped function
    def mock_retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    mock_module = MagicMock()
    mock_module.retry = mock_retry
    mock_module.stop_after_attempt = MagicMock()
    mock_module.wait_exponential = MagicMock()
    mock_module.retry_if_exception_type = MagicMock()
    
    monkeypatch.setattr('tenacity', mock_module)
    monkeypatch.setattr('src.retry_wrapper.retry', mock_retry)
    
    return mock_module


@pytest.fixture
def mock_datetime(monkeypatch):
    """Mock datetime for consistent time-based tests."""
    fixed_time = datetime(2024, 1, 15, 10, 0, 0)
    
    class MockDateTime:
        @classmethod
        def now(cls):
            return fixed_time
        
        @classmethod
        def utcnow(cls):
            return fixed_time
        
        @classmethod
        def fromtimestamp(cls, timestamp):
            return fixed_time
        
        def __init__(self, *args, **kwargs):
            pass
        
        def strftime(self, fmt):
            return fixed_time.strftime(fmt)
    
    monkeypatch.setattr('datetime.datetime', MockDateTime)
    return MockDateTime


@pytest.fixture
def mock_progress_bar(monkeypatch):
    """Mock progress bar to avoid terminal output during tests."""
    mock_bar = MagicMock()
    mock_bar.update = MagicMock()
    mock_bar.set_description = MagicMock()
    mock_bar.close = MagicMock()
    
    def mock_progress_bar_class(*args, **kwargs):
        return mock_bar
    
    monkeypatch.setattr('src.utils.progress.ProgressBar', mock_progress_bar_class)
    monkeypatch.setattr('tqdm.tqdm', mock_progress_bar_class)
    
    return mock_bar


@pytest.fixture
def mock_usage_state(tmp_path):
    """Mock usage state for Gemini client."""
    state_file = tmp_path / 'usage_state.json'
    initial_state = {
        '1': {
            'daily_requests': 0,
            'daily_tokens': 0,
            'last_reset': '2024-01-15',
            'last_request_time': 0
        },
        '2': {
            'daily_requests': 0,
            'daily_tokens': 0,
            'last_reset': '2024-01-15',
            'last_request_time': 0
        }
    }
    state_file.write_text(json.dumps(initial_state))
    return state_file


@pytest.fixture
def mock_checkpoint_state(tmp_path):
    """Mock checkpoint state for recovery."""
    checkpoint_file = tmp_path / 'checkpoint.json'
    checkpoint_data = {
        'podcast_name': 'Test Podcast',
        'total_episodes': 10,
        'completed_episodes': [],
        'failed_episodes': [],
        'in_progress': None,
        'last_update': '2024-01-15T10:00:00',
        'config': {}
    }
    checkpoint_file.write_text(json.dumps(checkpoint_data))
    return checkpoint_file


@pytest.fixture
def mock_all_external_deps(
    mock_google_generativeai,
    mock_feedparser_module,
    mock_file_system,
    mock_tenacity,
    mock_progress_bar,
    mock_env_vars
):
    """Convenience fixture that mocks all external dependencies."""
    return {
        'genai': mock_google_generativeai,
        'feedparser': mock_feedparser_module,
        'file_system': mock_file_system,
        'tenacity': mock_tenacity,
        'progress_bar': mock_progress_bar,
        'env_vars': mock_env_vars
    }