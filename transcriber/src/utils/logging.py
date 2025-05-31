"""Logging configuration for the Podcast Transcription Pipeline."""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# Default configuration
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5


class PodcastTranscriberLogger:
    """Centralized logging configuration for the podcast transcriber."""
    
    _instance: Optional['PodcastTranscriberLogger'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self._initialized = True
    
    def _setup_logging(self):
        """Configure logging with console and file handlers."""
        # Get log configuration from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_max_size = int(os.getenv('LOG_MAX_SIZE_MB', '10')) * 1024 * 1024
        log_backup_count = int(os.getenv('LOG_BACKUP_COUNT', '5'))
        
        # Create logs directory
        log_dir = Path(__file__).parent.parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger('podcast_transcriber')
        self.logger.setLevel(getattr(logging, log_level, DEFAULT_LOG_LEVEL))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create formatters
        formatter = logging.Formatter(
            fmt=DEFAULT_LOG_FORMAT,
            datefmt=DEFAULT_DATE_FORMAT
        )
        
        # Console handler - INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation - All levels
        log_file = log_dir / f'podcast_transcriber_{datetime.now().strftime("%Y%m%d")}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=log_max_size,
            backupCount=log_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler - ERROR and above only
        error_log_file = log_dir / f'errors_{datetime.now().strftime("%Y%m%d")}.log'
        error_handler = logging.handlers.RotatingFileHandler(
            filename=str(error_log_file),
            maxBytes=log_max_size,
            backupCount=log_backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
        
        # Log initialization
        self.logger.info("Logging system initialized")
        self.logger.info(f"Log level: {log_level}")
        self.logger.info(f"Log directory: {log_dir}")
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get a logger instance.
        
        Args:
            name: Optional logger name. If not provided, returns the main logger.
            
        Returns:
            Logger instance
        """
        if name:
            return logging.getLogger(f'podcast_transcriber.{name}')
        return self.logger


# Convenience functions
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Optional logger name for module-specific logging
        
    Returns:
        Logger instance
    """
    logger_manager = PodcastTranscriberLogger()
    return logger_manager.get_logger(name)


def log_progress(episode_num: int, total_episodes: int, episode_title: str, status: str):
    """Log episode processing progress.
    
    Args:
        episode_num: Current episode number
        total_episodes: Total number of episodes
        episode_title: Title of the current episode
        status: Processing status (e.g., 'starting', 'completed', 'failed')
    """
    logger = get_logger()
    progress_percent = (episode_num / total_episodes) * 100
    logger.info(
        f"Progress: {episode_num}/{total_episodes} ({progress_percent:.1f}%) - "
        f"{status.capitalize()} episode: {episode_title}"
    )


def log_api_request(api_key_index: int, endpoint: str, tokens_used: Optional[int] = None):
    """Log API request details.
    
    Args:
        api_key_index: Index of the API key used (1-based)
        endpoint: API endpoint called
        tokens_used: Optional number of tokens consumed
    """
    logger = get_logger()
    message = f"API Request - Key #{api_key_index}, Endpoint: {endpoint}"
    if tokens_used:
        message += f", Tokens: {tokens_used}"
    logger.debug(message)


def log_error_with_context(error: Exception, context: dict):
    """Log an error with additional context.
    
    Args:
        error: The exception that occurred
        context: Dictionary with contextual information
    """
    logger = get_logger()
    context_str = ", ".join(f"{k}={v}" for k, v in context.items())
    logger.error(f"{type(error).__name__}: {str(error)} | Context: {context_str}", exc_info=True)