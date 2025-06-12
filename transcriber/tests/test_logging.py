"""Unit tests for the logging utility module."""

import pytest
import logging
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.utils.logging import (
    PodcastTranscriberLogger, get_logger, log_progress, 
    log_api_request, log_error_with_context, setup_logging,
    DEFAULT_LOG_LEVEL, DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT
)


@pytest.mark.unit
class TestPodcastTranscriberLogger:
    """Test PodcastTranscriberLogger class."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test."""
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
        yield
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
    
    def test_singleton_pattern(self):
        """Test that logger follows singleton pattern."""
        logger1 = PodcastTranscriberLogger()
        logger2 = PodcastTranscriberLogger()
        
        assert logger1 is logger2
    
    @patch('src.utils.logging.logging.getLogger')
    @patch('src.utils.logging.Path.mkdir')
    def test_setup_logging_default(self, mock_mkdir, mock_get_logger):
        """Test default logging setup."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger_instance = PodcastTranscriberLogger()
        
        # Check logger was created
        mock_get_logger.assert_called_with('podcast_transcriber')
        
        # Check log directory was created
        mock_mkdir.assert_called_once_with(exist_ok=True)
        
        # Check handlers were added
        assert mock_logger.addHandler.call_count == 3  # console, file, error handlers
        
        # Check initialization was logged
        mock_logger.info.assert_any_call("Logging system initialized")
    
    @patch('src.utils.logging.logging.getLogger')
    @patch('src.utils.logging.Path.mkdir')
    def test_setup_logging_with_env_vars(self, mock_mkdir, mock_get_logger):
        """Test logging setup with environment variables."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_MAX_SIZE_MB': '20',
            'LOG_BACKUP_COUNT': '10'
        }):
            logger_instance = PodcastTranscriberLogger()
            
            # Check log level was set
            mock_logger.setLevel.assert_called_with(logging.DEBUG)
            
            # Verify handlers were configured with env values
            handler_calls = mock_logger.addHandler.call_args_list
            assert len(handler_calls) == 3
    
    @patch('src.utils.logging.logging.getLogger')
    def test_get_logger_main(self, mock_get_logger):
        """Test getting main logger."""
        mock_main_logger = MagicMock()
        mock_get_logger.return_value = mock_main_logger
        
        logger_instance = PodcastTranscriberLogger()
        result = logger_instance.get_logger()
        
        assert result == mock_main_logger
    
    @patch('src.utils.logging.logging.getLogger')
    def test_get_logger_named(self, mock_get_logger):
        """Test getting named logger."""
        logger_instance = PodcastTranscriberLogger()
        result = logger_instance.get_logger('test_module')
        
        # Should get child logger
        mock_get_logger.assert_called_with('podcast_transcriber.test_module')
    
    @patch('src.utils.logging.logging.handlers.RotatingFileHandler')
    @patch('src.utils.logging.logging.StreamHandler')
    @patch('src.utils.logging.logging.getLogger')
    @patch('src.utils.logging.Path.mkdir')
    def test_handler_configuration(self, mock_mkdir, mock_get_logger, 
                                 mock_stream_handler, mock_file_handler):
        """Test handler configuration details."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Create mock handler instances
        console_handler = MagicMock()
        file_handler = MagicMock()
        error_handler = MagicMock()
        
        mock_stream_handler.return_value = console_handler
        mock_file_handler.side_effect = [file_handler, error_handler]
        
        logger_instance = PodcastTranscriberLogger()
        
        # Check console handler setup
        console_handler.setLevel.assert_called_with(logging.INFO)
        console_handler.setFormatter.assert_called_once()
        
        # Check file handlers setup
        assert mock_file_handler.call_count == 2
        
        # First call - main log file
        main_log_call = mock_file_handler.call_args_list[0]
        assert 'podcast_transcriber_' in str(main_log_call[1]['filename'])
        assert main_log_call[1]['maxBytes'] == 10 * 1024 * 1024
        assert main_log_call[1]['backupCount'] == 5
        
        # Second call - error log file
        error_log_call = mock_file_handler.call_args_list[1]
        assert 'errors_' in str(error_log_call[1]['filename'])
        
        # Check handlers were set with correct levels
        file_handler.setLevel.assert_called_with(logging.DEBUG)
        error_handler.setLevel.assert_called_with(logging.ERROR)


@pytest.mark.unit
class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test."""
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
        yield
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
    
    @patch('src.utils.logging.PodcastTranscriberLogger')
    def test_get_logger_function(self, mock_logger_class):
        """Test get_logger convenience function."""
        mock_instance = MagicMock()
        mock_logger_class.return_value = mock_instance
        
        # Test without name
        result = get_logger()
        mock_instance.get_logger.assert_called_with(None)
        
        # Test with name
        result = get_logger('test_module')
        mock_instance.get_logger.assert_called_with('test_module')
    
    @patch('src.utils.logging.get_logger')
    def test_log_progress(self, mock_get_logger):
        """Test log_progress function."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_progress(5, 10, "Test Episode", "completed")
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        
        assert "Progress: 5/10 (50.0%)" in call_args
        assert "Completed episode: Test Episode" in call_args
    
    @patch('src.utils.logging.get_logger')
    def test_log_api_request(self, mock_get_logger):
        """Test log_api_request function."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Test without tokens
        log_api_request(1, "/v1/models/gemini-pro")
        
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "API Request - Key #1" in call_args
        assert "Endpoint: /v1/models/gemini-pro" in call_args
        
        # Test with tokens
        mock_logger.reset_mock()
        log_api_request(2, "/v1/chat", tokens_used=1500)
        
        call_args = mock_logger.debug.call_args[0][0]
        assert "Key #2" in call_args
        assert "Tokens: 1500" in call_args
    
    @patch('src.utils.logging.get_logger')
    def test_log_error_with_context(self, mock_get_logger):
        """Test log_error_with_context function."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        error = ValueError("Test error message")
        context = {
            'episode': 'Test Episode',
            'attempt': 2,
            'api_key': 'key_1'
        }
        
        log_error_with_context(error, context)
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        
        error_msg = call_args[0][0]
        assert "ValueError: Test error message" in error_msg
        assert "episode=Test Episode" in error_msg
        assert "attempt=2" in error_msg
        assert "api_key=key_1" in error_msg
        
        # Check exc_info was passed
        assert call_args[1]['exc_info'] is True
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('src.utils.logging.PodcastTranscriberLogger')
    def test_setup_logging(self, mock_logger_class):
        """Test setup_logging function."""
        # Test with INFO level
        setup_logging(logging.INFO)
        
        assert os.environ['LOG_LEVEL'] == 'INFO'
        assert PodcastTranscriberLogger._initialized is False
        assert PodcastTranscriberLogger._instance is None
        
        # Test with DEBUG level
        setup_logging(logging.DEBUG)
        
        assert os.environ['LOG_LEVEL'] == 'DEBUG'


@pytest.mark.unit
class TestLoggingIntegration:
    """Test logging integration scenarios."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton state before each test."""
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
        yield
        PodcastTranscriberLogger._instance = None
        PodcastTranscriberLogger._initialized = False
    
    @patch('src.utils.logging.Path.mkdir')
    @patch('src.utils.logging.logging.handlers.RotatingFileHandler')
    @patch('src.utils.logging.logging.StreamHandler')
    def test_multiple_logger_requests(self, mock_stream, mock_file, mock_mkdir):
        """Test multiple logger requests don't create multiple handlers."""
        # Setup mock handlers with proper level attribute
        mock_stream_instance = MagicMock()
        mock_stream_instance.level = logging.INFO
        mock_stream.return_value = mock_stream_instance
        
        mock_file_instance = MagicMock()
        mock_file_instance.level = logging.INFO
        mock_file.return_value = mock_file_instance
        
        # Get logger multiple times
        logger1 = get_logger()
        logger2 = get_logger('module1')
        logger3 = get_logger('module2')
        
        # Should only create handlers once
        assert mock_stream.call_count == 1
        assert mock_file.call_count == 2  # main log and error log
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'INVALID'}, clear=True)
    @patch('src.utils.logging.Path.mkdir')
    @patch('src.utils.logging.logging.getLogger')
    def test_invalid_log_level(self, mock_get_logger, mock_mkdir):
        """Test handling of invalid log level."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger_instance = PodcastTranscriberLogger()
        
        # Should fall back to DEFAULT_LOG_LEVEL
        mock_logger.setLevel.assert_called_with(DEFAULT_LOG_LEVEL)