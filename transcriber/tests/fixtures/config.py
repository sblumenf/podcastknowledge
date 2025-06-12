"""Test configuration fixtures for the Podcast Transcription Pipeline.

This module provides test-specific configuration fixtures that mock
environment variables and provide valid test configurations.
"""

import os
import pytest
from pathlib import Path
from typing import Dict, Any
from src.config import Config


def get_test_config_dict() -> Dict[str, Any]:
    """Get a dictionary of test configuration values."""
    return {
        'api': {
            'timeout': 30,
            'retry': {
                'max_attempts': 2,
                'backoff_multiplier': 2,
                'max_backoff': 10
            },
            'quota': {
                'max_episodes_per_day': 5,
                'max_requests_per_key': 10,
                'max_tokens_per_key': 10000
            }
        },
        'processing': {
            'parallel_workers': 1,
            'enable_progress_bar': False,
            'checkpoint_enabled': True,
            'max_episode_length': 30
        },
        'output': {
            'default_dir': 'test_data/transcripts',
            'naming': {
                'pattern': '{podcast_name}/{date}_{episode_title}.vtt',
                'sanitize_filenames': True,
                'max_filename_length': 100
            },
            'vtt': {
                'include_metadata': True,
                'speaker_voice_tags': True,
                'timestamp_precision': 3
            }
        },
        'logging': {
            'console_level': 'WARNING',
            'file_level': 'DEBUG',
            'max_file_size_mb': 5,
            'backup_count': 2,
            'log_dir': 'test_logs'
        },
        'security': {
            'api_key_vars': ['TEST_API_KEY_1', 'TEST_API_KEY_2'],
            'rotation': {
                'strategy': 'round_robin',
                'fail_over_enabled': True
            }
        },
        'development': {
            'dry_run': False,
            'debug_mode': True,
            'save_raw_responses': False,
            'test_mode': True,
            'mock_api_calls': True
        }
    }


@pytest.fixture
def test_config():
    """Provide a valid test configuration object."""
    # Set test API keys in environment
    os.environ['TEST_API_KEY_1'] = 'test_key_1'
    os.environ['TEST_API_KEY_2'] = 'test_key_2'
    
    # Create temporary config file
    import tempfile
    import yaml
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(get_test_config_dict(), f)
        config_file = f.name
    
    try:
        # Create config with test file
        config = Config(config_file=config_file)
        config.development.test_mode = True
        yield config
    finally:
        # Cleanup
        os.unlink(config_file)
        os.environ.pop('TEST_API_KEY_1', None)
        os.environ.pop('TEST_API_KEY_2', None)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    original_env = dict(os.environ)
    
    # Set test environment variables
    test_env = {
        'TEST_API_KEY_1': 'test_key_1',
        'TEST_API_KEY_2': 'test_key_2',
        'GEMINI_API_KEY_1': 'gemini_test_key_1',
        'GEMINI_API_KEY_2': 'gemini_test_key_2',
        'PODCAST_API_TIMEOUT': '60',
        'PODCAST_API_MAX_ATTEMPTS': '3',
        'PODCAST_LOG_LEVEL': 'DEBUG'
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    yield test_env
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def test_config_minimal():
    """Provide a minimal test configuration for quick tests."""
    # Set minimal API keys
    os.environ['GEMINI_API_KEY_1'] = 'test_key_minimal'
    
    try:
        config = Config()
        config.development.test_mode = True
        config.development.mock_api_calls = True
        yield config
    finally:
        os.environ.pop('GEMINI_API_KEY_1', None)