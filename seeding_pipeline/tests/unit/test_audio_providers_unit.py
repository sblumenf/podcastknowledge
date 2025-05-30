"""Tests for audio provider implementations."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile
import os
from pathlib import Path

from src.providers.audio.base import AudioProvider
from src.providers.audio.mock import MockAudioProvider
from src.providers.audio.whisper import WhisperAudioProvider


class TestMockAudioProvider:
    """Test MockAudioProvider implementation."""
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        provider = MockAudioProvider()
        assert provider.name == "mock"
        assert provider.model_name == "mock-audio-v1"
    
    def test_mock_provider_transcribe(self):
        """Test mock provider transcription."""
        provider = MockAudioProvider()
        
        result = provider.transcribe("test.mp3")
        
        assert isinstance(result, dict)
        assert "text" in result
        assert "segments" in result
        assert "duration" in result
        assert len(result["text"]) > 0
    
    def test_mock_provider_health_check(self):
        """Test mock provider health check."""
        provider = MockAudioProvider()
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "mock"
    
    def test_mock_provider_custom_response(self):
        """Test mock provider with custom response."""
        provider = MockAudioProvider()
        
        # Set custom response
        custom_text = "This is a custom transcription"
        provider.mock_response = {
            "text": custom_text,
            "segments": [{"text": custom_text, "start": 0.0, "end": 5.0}],
            "duration": 5.0
        }
        
        result = provider.transcribe("test.mp3")
        assert result["text"] == custom_text


class TestWhisperAudioProvider:
    """Test WhisperAudioProvider implementation."""
    
    @patch('whisper.load_model')
    def test_whisper_provider_initialization(self, mock_load_model):
        """Test Whisper provider initialization."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        config = {"model_size": "base"}
        provider = WhisperAudioProvider(config)
        
        assert provider.name == "whisper"
        assert provider.model_size == "base"
        mock_load_model.assert_called_once_with("base")
    
    @patch('whisper.load_model')
    def test_whisper_provider_transcribe(self, mock_load_model):
        """Test Whisper provider transcription."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        # Mock transcription result
        mock_result = {
            "text": " Hello world",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.0,
                    "text": " Hello world",
                    "tokens": [123, 456],
                    "temperature": 0.0,
                    "avg_logprob": -0.5,
                    "compression_ratio": 1.2,
                    "no_speech_prob": 0.01
                }
            ],
            "language": "en"
        }
        mock_model.transcribe.return_value = mock_result
        
        provider = WhisperAudioProvider({"model_size": "base"})
        result = provider.transcribe("test.mp3")
        
        assert result["text"] == "Hello world"  # Stripped
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "Hello world"
        mock_model.transcribe.assert_called_once_with("test.mp3")
    
    @patch('whisper.load_model')
    def test_whisper_provider_health_check(self, mock_load_model):
        """Test Whisper provider health check."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        provider = WhisperAudioProvider({"model_size": "base"})
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "whisper"
        assert health["model_size"] == "base"
    
    @patch('whisper.load_model')
    def test_whisper_provider_error_handling(self, mock_load_model):
        """Test Whisper provider error handling."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        mock_model.transcribe.side_effect = Exception("Transcription failed")
        
        provider = WhisperAudioProvider({"model_size": "base"})
        
        with pytest.raises(Exception, match="Transcription failed"):
            provider.transcribe("test.mp3")
    
    @patch('whisper.load_model')
    def test_whisper_provider_model_not_available(self, mock_load_model):
        """Test Whisper provider when model loading fails."""
        mock_load_model.side_effect = RuntimeError("Model not found")
        
        with pytest.raises(RuntimeError, match="Model not found"):
            WhisperAudioProvider({"model_size": "large"})
    
    @patch('whisper.load_model')
    @patch('os.path.exists')
    def test_whisper_provider_file_not_found(self, mock_exists, mock_load_model):
        """Test Whisper provider with non-existent file."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        mock_exists.return_value = False
        
        provider = WhisperAudioProvider({"model_size": "base"})
        
        # Whisper should handle this internally
        mock_model.transcribe.side_effect = FileNotFoundError("Audio file not found")
        
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            provider.transcribe("/non/existent/file.mp3")