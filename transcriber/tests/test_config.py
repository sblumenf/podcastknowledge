"""Unit tests for the configuration management module."""

import pytest
import os
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.config import (
    Config, APIConfig, ProcessingConfig, OutputConfig, 
    LoggingConfig, SecurityConfig, DevelopmentConfig,
    get_config, reload_config
)


@pytest.mark.unit
class TestAPIConfig:
    """Test APIConfig dataclass."""
    
    def test_default_values(self):
        """Test default APIConfig values."""
        config = APIConfig()
        assert config.timeout == 300
        assert config.max_attempts == 2
        assert config.backoff_multiplier == 2
        assert config.max_backoff == 30
        assert config.max_episodes_per_day == 12
        assert config.max_requests_per_key == 25
        assert config.max_tokens_per_key == 1000000


@pytest.mark.unit
class TestProcessingConfig:
    """Test ProcessingConfig dataclass."""
    
    def test_default_values(self):
        """Test default ProcessingConfig values."""
        config = ProcessingConfig()
        assert config.parallel_workers == 1
        assert config.enable_progress_bar is True
        assert config.checkpoint_enabled is True
        assert config.max_episode_length == 60


@pytest.mark.unit
class TestOutputConfig:
    """Test OutputConfig dataclass."""
    
    def test_default_values(self):
        """Test default OutputConfig values."""
        config = OutputConfig()
        assert config.default_dir == "data/transcripts"
        assert config.naming_pattern == "{podcast_name}/{date}_{episode_title}.vtt"
        assert config.sanitize_filenames is True
        assert config.max_filename_length == 200
        assert config.include_metadata is True
        assert config.speaker_voice_tags is True
        assert config.timestamp_precision == 3


@pytest.mark.unit
class TestLogginConfig:
    """Test LoggingConfig dataclass."""
    
    def test_default_values(self):
        """Test default LoggingConfig values."""
        config = LoggingConfig()
        assert config.console_level == "INFO"
        assert config.file_level == "DEBUG"
        assert config.max_file_size_mb == 10
        assert config.backup_count == 5
        assert config.log_dir == "logs"


@pytest.mark.unit
class TestSecurityConfig:
    """Test SecurityConfig dataclass."""
    
    def test_default_values(self):
        """Test default SecurityConfig values."""
        config = SecurityConfig()
        assert config.api_key_vars == ["GEMINI_API_KEY_1", "GEMINI_API_KEY_2"]
        assert config.rotation_strategy == "round_robin"
        assert config.fail_over_enabled is True
    
    def test_custom_api_key_vars(self):
        """Test custom API key variables."""
        config = SecurityConfig(api_key_vars=["KEY1", "KEY2", "KEY3"])
        assert config.api_key_vars == ["KEY1", "KEY2", "KEY3"]


@pytest.mark.unit
class TestDevelopmentConfig:
    """Test DevelopmentConfig dataclass."""
    
    def test_default_values(self):
        """Test default DevelopmentConfig values."""
        config = DevelopmentConfig()
        assert config.dry_run is False
        assert config.debug_mode is False
        assert config.save_raw_responses is False
        assert config.test_mode is False
        assert config.mock_api_calls is False


@pytest.mark.unit
class TestConfig:
    """Test main Config class."""
    
    def test_default_initialization(self, mock_logger):
        """Test Config initialization with defaults."""
        config = Config()
        
        # Check all sections are initialized
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.processing, ProcessingConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.development, DevelopmentConfig)
    
    def test_load_from_yaml_file(self, tmp_path, mock_logger, config_file_content):
        """Test loading configuration from YAML file."""
        # Create temporary config file
        config_path = Path(tmp_path) / "test_config.yaml"
        with open(config_path, 'w') as f:
            f.write(config_file_content)
        
        # Load configuration
        config = Config(str(config_path))
        
        # Verify values from YAML
        assert config.api.timeout == 300
        assert config.api.max_attempts == 2
        assert config.processing.max_episode_length == 60
        assert config.output.default_dir == "data/transcripts"
        assert config.logging.console_level == "INFO"
        assert config.security.rotation_strategy == "round_robin"
    
    def test_missing_config_file(self, mock_logger):
        """Test handling of missing config file."""
        config = Config("/non/existent/config.yaml")
        
        # Should use defaults when file doesn't exist
        assert config.api.timeout == 300
        assert config.processing.enable_progress_bar is True
    
    def test_invalid_yaml_file(self, tmp_path, mock_logger):
        """Test handling of invalid YAML file."""
        # Create invalid YAML file
        config_path = Path(tmp_path) / "invalid_config.yaml"
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: content: [}")
        
        # Should use defaults when YAML is invalid
        config = Config(str(config_path))
        assert config.api.timeout == 300
    
    def test_environment_overrides(self, mock_logger):
        """Test environment variable overrides."""
        with patch.dict(os.environ, {
            'PODCAST_API_TIMEOUT': '600',
            'PODCAST_API_MAX_ATTEMPTS': '3',
            'PODCAST_API_MAX_EPISODES': '20',
            'PODCAST_OUTPUT_DIR': '/custom/output',
            'PODCAST_OUTPUT_PATTERN': '{date}/{podcast_name}.vtt',
            'PODCAST_MAX_EPISODE_LENGTH': '90',
            'PODCAST_ENABLE_PROGRESS': 'false',
            'PODCAST_LOG_LEVEL': 'DEBUG',
            'PODCAST_LOG_DIR': '/custom/logs',
            'PODCAST_DRY_RUN': 'true',
            'PODCAST_DEBUG_MODE': '1'
        }):
            config = Config()
            
            assert config.api.timeout == 600
            assert config.api.max_attempts == 3
            assert config.api.max_episodes_per_day == 20
            assert config.output.default_dir == '/custom/output'
            assert config.output.naming_pattern == '{date}/{podcast_name}.vtt'
            assert config.processing.max_episode_length == 90
            assert config.processing.enable_progress_bar is False
            assert config.logging.console_level == 'DEBUG'
            assert config.logging.log_dir == '/custom/logs'
            assert config.development.dry_run is True
            assert config.development.debug_mode is True
    
    def test_validation_errors(self, mock_logger):
        """Test configuration validation errors."""
        config = Config()
        
        # Disable test mode to enable strict validation
        config.development.test_mode = False
        
        # Test invalid API timeout
        config.api.timeout = -1
        with pytest.raises(ValueError, match="API timeout must be positive"):
            config.validate()
        
        # Test invalid max attempts
        config.api.timeout = 300
        config.api.max_attempts = 10
        with pytest.raises(ValueError, match="API max_attempts must be between 1 and 5"):
            config.validate()
        
        # Test invalid max episodes
        config.api.max_attempts = 2
        config.api.max_episodes_per_day = 0
        with pytest.raises(ValueError, match="Max episodes per day must be positive"):
            config.validate()
        
        # Test invalid log level
        config.api.max_episodes_per_day = 12
        config.logging.console_level = 'INVALID'
        with pytest.raises(ValueError, match="Console log level must be one of"):
            config.validate()
        
        # Test missing API keys
        config.logging.console_level = 'INFO'
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="No API keys found"):
                config.validate()
    
    def test_get_api_keys(self, mock_logger):
        """Test retrieving API keys from environment."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'key1_value',
            'GEMINI_API_KEY_2': 'key2_value',
            'GEMINI_API_KEY_3': 'key3_value'
        }):
            config = Config()
            keys = config.get_api_keys()
            
            assert len(keys) == 2  # Default config only looks for KEY_1 and KEY_2
            assert 'key1_value' in keys
            assert 'key2_value' in keys
    
    def test_get_api_keys_custom_vars(self, mock_logger):
        """Test retrieving API keys with custom variable names."""
        with patch.dict(os.environ, {
            'CUSTOM_KEY_1': 'custom1',
            'CUSTOM_KEY_2': 'custom2'
        }):
            config = Config()
            config.security.api_key_vars = ['CUSTOM_KEY_1', 'CUSTOM_KEY_2']
            keys = config.get_api_keys()
            
            assert len(keys) == 2
            assert 'custom1' in keys
            assert 'custom2' in keys
    
    def test_to_dict(self, mock_logger):
        """Test configuration serialization to dictionary."""
        config = Config()
        config_dict = config.to_dict()
        
        # Check structure
        assert 'api' in config_dict
        assert 'processing' in config_dict
        assert 'output' in config_dict
        assert 'logging' in config_dict
        assert 'security' in config_dict
        assert 'development' in config_dict
        
        # Check some values
        assert config_dict['api']['timeout'] == 300
        assert config_dict['processing']['enable_progress_bar'] is True
        assert config_dict['output']['default_dir'] == "data/transcripts"
        # In test mode, console level is automatically set to WARNING
        assert config_dict['logging']['console_level'] == "WARNING"
        assert config_dict['security']['rotation_strategy'] == "round_robin"
        assert config_dict['development']['dry_run'] is False
    
    def test_apply_config_section_api(self, mock_logger):
        """Test applying API configuration section from YAML."""
        config = Config()
        config._raw_config = {
            'api': {
                'timeout': 600,
                'retry': {
                    'max_attempts': 3,
                    'backoff_multiplier': 3,
                    'max_backoff': 60
                },
                'quota': {
                    'max_episodes_per_day': 20,
                    'max_requests_per_key': 30,
                    'max_tokens_per_key': 2000000
                }
            }
        }
        
        config._apply_config_section('api', config.api)
        
        assert config.api.timeout == 600
        assert config.api.max_attempts == 3
        assert config.api.backoff_multiplier == 3
        assert config.api.max_backoff == 60
        assert config.api.max_episodes_per_day == 20
        assert config.api.max_requests_per_key == 30
        assert config.api.max_tokens_per_key == 2000000
    
    def test_apply_config_section_output(self, mock_logger):
        """Test applying output configuration section from YAML."""
        config = Config()
        config._raw_config = {
            'output': {
                'default_dir': '/custom/dir',
                'naming': {
                    'pattern': '{episode_title}.vtt',
                    'sanitize_filenames': False,
                    'max_filename_length': 100
                },
                'vtt': {
                    'include_metadata': False,
                    'speaker_voice_tags': False,
                    'timestamp_precision': 2
                }
            }
        }
        
        config._apply_config_section('output', config.output)
        
        assert config.output.default_dir == '/custom/dir'
        assert config.output.naming_pattern == '{episode_title}.vtt'
        assert config.output.sanitize_filenames is False
        assert config.output.max_filename_length == 100
        assert config.output.include_metadata is False
        assert config.output.speaker_voice_tags is False
        assert config.output.timestamp_precision == 2
    
    def test_validate_timestamp_precision(self, mock_logger):
        """Test timestamp precision validation."""
        config = Config()
        
        # Disable test mode to enable strict validation
        config.development.test_mode = False
        
        # Test invalid precision
        config.output.timestamp_precision = 5
        with pytest.raises(ValueError, match="Timestamp precision must be between 0 and 3"):
            config.validate()
        
        # Test valid precision
        config.output.timestamp_precision = 2
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            config.validate()  # Should not raise
    
    def test_validate_rotation_strategy(self, mock_logger):
        """Test rotation strategy validation."""
        config = Config()
        
        # Disable test mode to enable strict validation
        config.development.test_mode = False
        
        # Test invalid strategy
        config.security.rotation_strategy = 'invalid_strategy'
        with pytest.raises(ValueError, match="Rotation strategy must be one of"):
            config.validate()
        
        # Test valid strategies
        config.security.rotation_strategy = 'round_robin'
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            config.validate()  # Should not raise
        
        config.security.rotation_strategy = 'random'
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            config.validate()  # Should not raise


@pytest.mark.unit
class TestConfigSingleton:
    """Test global configuration singleton functionality."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the global config instance before each test."""
        import src.config
        src.config._config_instance = None
        yield
        src.config._config_instance = None
    
    def test_get_config_singleton(self, mock_logger):
        """Test that get_config returns the same instance."""
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            config1 = get_config()
            config2 = get_config()
            
            assert config1 is config2
    
    def test_reload_config(self, mock_logger):
        """Test reloading configuration."""
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            config1 = get_config()
            config1.api.timeout = 999  # Modify the instance
            
            reload_config()
            
            config2 = get_config()
            assert config1 is not config2
            assert config2.api.timeout == 300  # Default value