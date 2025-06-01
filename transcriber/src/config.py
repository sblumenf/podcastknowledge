"""Configuration management for the Podcast Transcription Pipeline.

This module provides a flexible configuration system that loads settings from
YAML files and allows environment variable overrides for deployment flexibility.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from src.utils.logging import get_logger

logger = get_logger('config')


@dataclass
class APIConfig:
    """API configuration settings."""
    timeout: int = 300
    max_attempts: int = 2
    backoff_multiplier: int = 2
    max_backoff: int = 30
    max_episodes_per_day: int = 12
    max_requests_per_key: int = 25
    max_tokens_per_key: int = 1000000


@dataclass
class ProcessingConfig:
    """Processing configuration settings."""
    parallel_workers: int = 1
    enable_progress_bar: bool = True
    checkpoint_enabled: bool = True
    max_episode_length: int = 60


@dataclass
class OutputConfig:
    """Output configuration settings."""
    default_dir: str = "data/transcripts"
    naming_pattern: str = "{podcast_name}/{date}_{episode_title}.vtt"
    sanitize_filenames: bool = True
    max_filename_length: int = 200
    include_metadata: bool = True
    speaker_voice_tags: bool = True
    timestamp_precision: int = 3


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    max_file_size_mb: int = 10
    backup_count: int = 5
    log_dir: str = "logs"


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    api_key_vars: List[str] = None
    rotation_strategy: str = "round_robin"
    fail_over_enabled: bool = True
    
    def __post_init__(self):
        if self.api_key_vars is None:
            self.api_key_vars = ["GEMINI_API_KEY_1", "GEMINI_API_KEY_2"]


@dataclass
class DevelopmentConfig:
    """Development configuration settings."""
    dry_run: bool = False
    debug_mode: bool = False
    save_raw_responses: bool = False
    test_mode: bool = False
    mock_api_calls: bool = False


class Config:
    """Main configuration class that manages all settings."""
    
    def __init__(self, config_file: Optional[str] = None, test_mode: bool = False):
        """Initialize configuration.
        
        Args:
            config_file: Path to YAML configuration file. If None, uses default.
            test_mode: Whether to run in test mode with relaxed validation.
        """
        self.config_file = config_file
        self._raw_config = {}
        
        # Initialize configuration sections
        self.api = APIConfig()
        self.processing = ProcessingConfig()
        self.output = OutputConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        self.development = DevelopmentConfig()
        
        # Set test mode if specified
        if test_mode:
            self.development.test_mode = True
            self.development.mock_api_calls = True
        
        # Check for test environment
        if os.getenv('PYTEST_CURRENT_TEST') is not None:
            self.development.test_mode = True
            self.logging.console_level = 'WARNING'  # Reduce logging noise in tests
        
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file and apply environment overrides."""
        # Determine config file path
        if self.config_file:
            config_path = Path(self.config_file)
        else:
            # Use default config file relative to this module
            config_path = Path(__file__).parent.parent / "config" / "default.yaml"
        
        # Load YAML configuration
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._raw_config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from: {config_path}")
            else:
                logger.warning(f"Configuration file not found: {config_path}")
                logger.info("Using default configuration values")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Using default configuration values")
        
        # Apply configuration sections
        self._apply_config_section('api', self.api)
        self._apply_config_section('processing', self.processing)
        self._apply_config_section('output', self.output)
        self._apply_config_section('logging', self.logging)
        self._apply_config_section('security', self.security)
        self._apply_config_section('development', self.development)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Validate configuration
        self.validate()
    
    def _apply_config_section(self, section_name: str, config_obj: Any):
        """Apply configuration from YAML section to dataclass object.
        
        Args:
            section_name: Name of the configuration section
            config_obj: Dataclass object to update
        """
        section_config = self._raw_config.get(section_name, {})
        
        if section_name == 'api':
            # Handle nested API configuration
            config_obj.timeout = section_config.get('timeout', config_obj.timeout)
            
            retry_config = section_config.get('retry', {})
            config_obj.max_attempts = retry_config.get('max_attempts', config_obj.max_attempts)
            config_obj.backoff_multiplier = retry_config.get('backoff_multiplier', config_obj.backoff_multiplier)
            config_obj.max_backoff = retry_config.get('max_backoff', config_obj.max_backoff)
            
            quota_config = section_config.get('quota', {})
            config_obj.max_episodes_per_day = quota_config.get('max_episodes_per_day', config_obj.max_episodes_per_day)
            config_obj.max_requests_per_key = quota_config.get('max_requests_per_key', config_obj.max_requests_per_key)
            config_obj.max_tokens_per_key = quota_config.get('max_tokens_per_key', config_obj.max_tokens_per_key)
        
        elif section_name == 'output':
            # Handle nested output configuration
            config_obj.default_dir = section_config.get('default_dir', config_obj.default_dir)
            
            naming_config = section_config.get('naming', {})
            config_obj.naming_pattern = naming_config.get('pattern', config_obj.naming_pattern)
            config_obj.sanitize_filenames = naming_config.get('sanitize_filenames', config_obj.sanitize_filenames)
            config_obj.max_filename_length = naming_config.get('max_filename_length', config_obj.max_filename_length)
            
            vtt_config = section_config.get('vtt', {})
            config_obj.include_metadata = vtt_config.get('include_metadata', config_obj.include_metadata)
            config_obj.speaker_voice_tags = vtt_config.get('speaker_voice_tags', config_obj.speaker_voice_tags)
            config_obj.timestamp_precision = vtt_config.get('timestamp_precision', config_obj.timestamp_precision)
        
        elif section_name == 'security':
            # Handle security configuration
            config_obj.api_key_vars = section_config.get('api_key_vars', config_obj.api_key_vars)
            
            rotation_config = section_config.get('rotation', {})
            config_obj.rotation_strategy = rotation_config.get('strategy', config_obj.rotation_strategy)
            config_obj.fail_over_enabled = rotation_config.get('fail_over_enabled', config_obj.fail_over_enabled)
        
        else:
            # Handle simple flat configurations
            for key, value in section_config.items():
                if hasattr(config_obj, key):
                    setattr(config_obj, key, value)
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides using standard naming convention."""
        # API configuration overrides
        self._apply_env_override('PODCAST_API_TIMEOUT', 'api.timeout', int)
        self._apply_env_override('PODCAST_API_MAX_ATTEMPTS', 'api.max_attempts', int)
        self._apply_env_override('PODCAST_API_MAX_EPISODES', 'api.max_episodes_per_day', int)
        
        # Output configuration overrides
        self._apply_env_override('PODCAST_OUTPUT_DIR', 'output.default_dir', str)
        self._apply_env_override('PODCAST_OUTPUT_PATTERN', 'output.naming_pattern', str)
        
        # Processing configuration overrides
        self._apply_env_override('PODCAST_MAX_EPISODE_LENGTH', 'processing.max_episode_length', int)
        self._apply_env_override('PODCAST_ENABLE_PROGRESS', 'processing.enable_progress_bar', bool)
        
        # Logging configuration overrides
        self._apply_env_override('PODCAST_LOG_LEVEL', 'logging.console_level', str)
        self._apply_env_override('PODCAST_LOG_DIR', 'logging.log_dir', str)
        
        # Development configuration overrides
        self._apply_env_override('PODCAST_DRY_RUN', 'development.dry_run', bool)
        self._apply_env_override('PODCAST_DEBUG_MODE', 'development.debug_mode', bool)
    
    def _apply_env_override(self, env_var: str, config_path: str, value_type: type):
        """Apply a single environment variable override.
        
        Args:
            env_var: Environment variable name
            config_path: Dot notation path to config value (e.g., 'api.timeout')
            value_type: Type to convert the value to
        """
        env_value = os.getenv(env_var)
        if env_value is not None:
            try:
                # Convert value to appropriate type
                if value_type == bool:
                    converted_value = env_value.lower() in ('true', '1', 'yes', 'on')
                elif value_type == int:
                    converted_value = int(env_value)
                elif value_type == float:
                    converted_value = float(env_value)
                else:
                    converted_value = env_value
                
                # Apply to configuration object
                path_parts = config_path.split('.')
                config_obj = getattr(self, path_parts[0])
                setattr(config_obj, path_parts[1], converted_value)
                
                logger.info(f"Applied environment override: {env_var}={converted_value}")
                
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to apply environment override {env_var}: {e}")
    
    def validate(self):
        """Validate configuration values."""
        errors = []
        
        # Skip strict validation in test mode
        if self.development.test_mode:
            logger.info("Running in test mode - relaxed validation")
            return
        
        # Validate API configuration
        if self.api.timeout <= 0:
            errors.append("API timeout must be positive")
        
        if self.api.max_attempts < 1 or self.api.max_attempts > 5:
            errors.append("API max_attempts must be between 1 and 5")
        
        if self.api.max_episodes_per_day < 1:
            errors.append("Max episodes per day must be positive")
        
        # Validate processing configuration
        if self.processing.max_episode_length <= 0:
            errors.append("Max episode length must be positive")
        
        # Validate output configuration
        if not self.output.default_dir:
            errors.append("Output directory cannot be empty")
        
        if self.output.timestamp_precision < 0 or self.output.timestamp_precision > 3:
            errors.append("Timestamp precision must be between 0 and 3")
        
        # Validate logging configuration
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging.console_level not in valid_log_levels:
            errors.append(f"Console log level must be one of: {valid_log_levels}")
        
        if self.logging.file_level not in valid_log_levels:
            errors.append(f"File log level must be one of: {valid_log_levels}")
        
        # Validate security configuration
        if not self.security.api_key_vars:
            errors.append("At least one API key variable must be configured")
        
        valid_strategies = ['round_robin', 'random']
        if self.security.rotation_strategy not in valid_strategies:
            errors.append(f"Rotation strategy must be one of: {valid_strategies}")
        
        # Check for API key availability
        available_keys = 0
        for key_var in self.security.api_key_vars:
            if os.getenv(key_var):
                available_keys += 1
        
        # In development mode with mock API calls, we don't need real API keys
        if available_keys == 0 and not self.development.mock_api_calls:
            errors.append(f"No API keys found in environment variables: {self.security.api_key_vars}")
        
        if errors:
            error_msg = "Configuration validation failed:\\n" + "\\n".join(f"  - {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def get_api_keys(self) -> List[str]:
        """Get list of available API keys from environment.
        
        Returns:
            List of API key values (not variable names)
        """
        keys = []
        for key_var in self.security.api_key_vars:
            key_value = os.getenv(key_var)
            if key_value:
                keys.append(key_value)
        return keys
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'api': {
                'timeout': self.api.timeout,
                'max_attempts': self.api.max_attempts,
                'backoff_multiplier': self.api.backoff_multiplier,
                'max_backoff': self.api.max_backoff,
                'max_episodes_per_day': self.api.max_episodes_per_day,
                'max_requests_per_key': self.api.max_requests_per_key,
                'max_tokens_per_key': self.api.max_tokens_per_key
            },
            'processing': {
                'parallel_workers': self.processing.parallel_workers,
                'enable_progress_bar': self.processing.enable_progress_bar,
                'checkpoint_enabled': self.processing.checkpoint_enabled,
                'max_episode_length': self.processing.max_episode_length
            },
            'output': {
                'default_dir': self.output.default_dir,
                'naming_pattern': self.output.naming_pattern,
                'sanitize_filenames': self.output.sanitize_filenames,
                'max_filename_length': self.output.max_filename_length,
                'include_metadata': self.output.include_metadata,
                'speaker_voice_tags': self.output.speaker_voice_tags,
                'timestamp_precision': self.output.timestamp_precision
            },
            'logging': {
                'console_level': self.logging.console_level,
                'file_level': self.logging.file_level,
                'max_file_size_mb': self.logging.max_file_size_mb,
                'backup_count': self.logging.backup_count,
                'log_dir': self.logging.log_dir
            },
            'security': {
                'api_key_vars': self.security.api_key_vars,
                'rotation_strategy': self.security.rotation_strategy,
                'fail_over_enabled': self.security.fail_over_enabled
            },
            'development': {
                'dry_run': self.development.dry_run,
                'debug_mode': self.development.debug_mode,
                'save_raw_responses': self.development.save_raw_responses,
                'test_mode': self.development.test_mode,
                'mock_api_calls': self.development.mock_api_calls
            }
        }
    
    @classmethod
    def create_test_config(cls, **overrides) -> 'Config':
        """Create a configuration suitable for testing.
        
        Args:
            **overrides: Configuration overrides to apply
            
        Returns:
            Config instance configured for testing
        """
        # Create config in test mode
        config = cls(test_mode=True)
        
        # Apply test-specific defaults
        config.api.timeout = 10  # Shorter timeout for tests
        config.api.max_attempts = 1  # No retries in tests
        config.processing.enable_progress_bar = False  # No progress bars in tests
        config.logging.console_level = 'ERROR'  # Only show errors in tests
        config.output.default_dir = 'test_output'  # Use test directory
        
        # Apply any overrides
        for key, value in overrides.items():
            if '.' in key:
                section, attr = key.split('.', 1)
                if hasattr(config, section):
                    setattr(getattr(config, section), attr, value)
            else:
                if hasattr(config, key):
                    setattr(config, key, value)
        
        return config


# Global configuration instance
_config_instance = None


def get_config(config_file: Optional[str] = None) -> Config:
    """Get the global configuration instance.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


def reload_config(config_file: Optional[str] = None):
    """Reload the global configuration instance.
    
    Args:
        config_file: Optional path to configuration file
    """
    global _config_instance
    _config_instance = Config(config_file)