"""Comprehensive tests for Gemini Client to improve coverage from 17.13% to 30%."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import asyncio
from datetime import datetime, timedelta
import tempfile
from pathlib import Path
import json
import time

from src.gemini_client import RateLimitedGeminiClient
from src.retry_wrapper import QuotaExceededException

# Create aliases for expected error types
class RateLimitError(Exception):
    pass

class QuotaExceededError(Exception):
    pass

class TranscriptionError(Exception):
    pass

class AudioTooLargeError(Exception):
    pass
from src.config import Config


class TestRateLimitedGeminiClientRateLimiting:
    """Test rate limiting functionality to prevent API overages."""
    
    @pytest.fixture
    def client(self):
        """Create Gemini client with test config."""
        config = Config.create_test_config()
        config.gemini.requests_per_minute = 2
        config.gemini.daily_quota = 100
        return RateLimitedGeminiClient(config)
    
    def test_rate_limit_enforcement(self, client):
        """Test that rate limiting prevents rapid requests."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'text': 'test'}
            
            # First request should succeed
            client.transcribe_audio('test1.mp3')
            
            # Second request should succeed
            client.transcribe_audio('test2.mp3')
            
            # Third request within same minute should raise rate limit
            with pytest.raises(RateLimitError):
                client.transcribe_audio('test3.mp3')
    
    def test_rate_limit_reset(self, client):
        """Test rate limit resets after time window."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'text': 'test'}
            
            # Make requests up to limit
            client.transcribe_audio('test1.mp3')
            client.transcribe_audio('test2.mp3')
            
            # Mock time passing
            with patch('time.time', return_value=time.time() + 61):
                # Should succeed after rate limit window
                result = client.transcribe_audio('test3.mp3')
                assert result is not None
    
    def test_concurrent_rate_limiting(self, client):
        """Test rate limiting with concurrent requests."""
        async def make_request(filename):
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = {'text': f'transcribed {filename}'}
                return client.transcribe_audio(filename)
        
        async def run_concurrent():
            tasks = [make_request(f'test{i}.mp3') for i in range(5)]
            results = []
            errors = []
            
            for task in asyncio.as_completed([asyncio.create_task(t) for t in tasks]):
                try:
                    result = await task
                    results.append(result)
                except RateLimitError as e:
                    errors.append(e)
            
            return results, errors
        
        results, errors = asyncio.run(run_concurrent())
        assert len(results) <= 2  # Only 2 should succeed due to rate limit
        assert len(errors) >= 3  # Others should fail


class TestRateLimitedGeminiClientQuotaManagement:
    """Test quota tracking to prevent costly overages."""
    
    @pytest.fixture
    def client(self):
        """Create client with low quota for testing."""
        config = Config.create_test_config()
        config.gemini.daily_quota = 10
        config.gemini.cost_per_request = 5
        return RateLimitedGeminiClient(config)
    
    def test_quota_tracking(self, client):
        """Test quota is tracked correctly."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'text': 'test'}
            
            # First request uses 5 units
            client.transcribe_audio('test1.mp3')
            assert client.get_quota_status()['used'] == 5
            assert client.get_quota_status()['remaining'] == 5
            
            # Second request uses another 5 units
            client.transcribe_audio('test2.mp3')
            assert client.get_quota_status()['used'] == 10
            assert client.get_quota_status()['remaining'] == 0
            
            # Third request should exceed quota
            with pytest.raises(QuotaExceededError):
                client.transcribe_audio('test3.mp3')
    
    def test_quota_reset_daily(self, client):
        """Test quota resets daily."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'text': 'test'}
            
            # Use up quota
            client.transcribe_audio('test1.mp3')
            client.transcribe_audio('test2.mp3')
            
            # Mock next day
            tomorrow = datetime.now() + timedelta(days=1)
            with patch('datetime.datetime') as mock_datetime:
                mock_datetime.now.return_value = tomorrow
                mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
                
                # Quota should be reset
                client._check_quota()  # This should reset the quota
                assert client.get_quota_status()['used'] == 0
                assert client.get_quota_status()['remaining'] == 10
    
    def test_quota_persistence(self, client):
        """Test quota state is saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            quota_file = Path(tmpdir) / 'quota.json'
            client._quota_file = quota_file
            
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = {'text': 'test'}
                
                # Make request and save quota
                client.transcribe_audio('test.mp3')
                client._save_quota_state()
                
                # Create new client and load quota
                new_client = RateLimitedGeminiClient(client.config)
                new_client._quota_file = quota_file
                new_client._load_quota_state()
                
                assert new_client.get_quota_status()['used'] == 5


class TestRateLimitedGeminiClientAudioProcessing:
    """Test audio file validation and processing."""
    
    @pytest.fixture
    def client(self):
        """Create basic client."""
        config = Config.create_test_config()
        return RateLimitedGeminiClient(config)
    
    def test_audio_file_validation(self, client):
        """Test validation of audio files."""
        # Test non-existent file
        with pytest.raises(FileNotFoundError):
            client.transcribe_audio('/nonexistent/audio.mp3')
        
        # Test invalid file extension
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            with pytest.raises(ValueError, match="Unsupported audio format"):
                client.transcribe_audio(f.name)
    
    def test_audio_size_limit(self, client):
        """Test audio file size limits."""
        with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
            # Write large file (mock)
            f.write(b'0' * (client.config.gemini.max_file_size + 1))
            f.flush()
            
            with pytest.raises(AudioTooLargeError):
                client.transcribe_audio(f.name)
    
    def test_audio_duration_estimation(self, client):
        """Test audio duration estimation for quota calculation."""
        with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
            # Mock audio file
            f.write(b'mock audio data' * 1000)
            f.flush()
            
            # Mock duration check
            with patch.object(client, '_get_audio_duration', return_value=300):  # 5 minutes
                with patch.object(client, '_make_request') as mock_request:
                    mock_request.return_value = {'text': 'transcribed'}
                    
                    result = client.transcribe_audio(f.name)
                    assert result is not None
                    
                    # Check that appropriate quota was used based on duration
                    assert client.get_quota_status()['used'] > 0


class TestRateLimitedGeminiClientRetryLogic:
    """Test retry logic with exponential backoff."""
    
    @pytest.fixture
    def client(self):
        """Create client with retry config."""
        config = Config.create_test_config()
        config.gemini.max_retries = 3
        config.gemini.retry_delay = 0.1  # Short delay for tests
        return RateLimitedGeminiClient(config)
    
    def test_retry_on_transient_error(self, client):
        """Test retry on transient errors."""
        call_count = 0
        
        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TranscriptionError("Temporary error")
            return {'text': 'success'}
        
        with patch.object(client, '_make_request', side_effect=mock_request):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                result = client.transcribe_audio(f.name)
                assert result['text'] == 'success'
                assert call_count == 3
    
    def test_exponential_backoff(self, client):
        """Test exponential backoff between retries."""
        delays = []
        original_sleep = time.sleep
        
        def mock_sleep(duration):
            delays.append(duration)
        
        with patch('time.sleep', side_effect=mock_sleep):
            with patch.object(client, '_make_request') as mock_request:
                mock_request.side_effect = TranscriptionError("Error")
                
                with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                    f.write(b'audio')
                    f.flush()
                    
                    with pytest.raises(TranscriptionError):
                        client.transcribe_audio(f.name)
                
                # Check exponential increase in delays
                assert len(delays) == client.config.gemini.max_retries
                for i in range(1, len(delays)):
                    assert delays[i] > delays[i-1]
    
    def test_no_retry_on_permanent_error(self, client):
        """Test no retry on permanent errors."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = AudioTooLargeError("File too large")
            
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                with pytest.raises(AudioTooLargeError):
                    client.transcribe_audio(f.name)
                
                # Should only be called once (no retries)
                assert mock_request.call_count == 1


class TestRateLimitedGeminiClientResponseParsing:
    """Test response parsing and error handling."""
    
    @pytest.fixture
    def client(self):
        """Create basic client."""
        config = Config.create_test_config()
        return RateLimitedGeminiClient(config)
    
    def test_parse_valid_response(self, client):
        """Test parsing valid API response."""
        mock_response = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': 'This is the transcribed text.'
                    }]
                }
            }]
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                result = client.transcribe_audio(f.name)
                assert result['text'] == 'This is the transcribed text.'
    
    def test_parse_empty_response(self, client):
        """Test handling of empty response."""
        mock_response = {'candidates': []}
        
        with patch.object(client, '_make_request', return_value=mock_response):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                with pytest.raises(TranscriptionError, match="No transcription"):
                    client.transcribe_audio(f.name)
    
    def test_parse_malformed_response(self, client):
        """Test handling of malformed response."""
        mock_response = {'unexpected': 'format'}
        
        with patch.object(client, '_make_request', return_value=mock_response):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                with pytest.raises(TranscriptionError):
                    client.transcribe_audio(f.name)
    
    def test_response_with_metadata(self, client):
        """Test extraction of response metadata."""
        mock_response = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Transcribed text'}]
                },
                'finishReason': 'STOP',
                'safetyRatings': [
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE'}
                ]
            }],
            'usageMetadata': {
                'promptTokenCount': 100,
                'candidatesTokenCount': 50,
                'totalTokenCount': 150
            }
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                result = client.transcribe_audio(f.name, return_metadata=True)
                assert result['text'] == 'Transcribed text'
                assert result['metadata']['token_count'] == 150
                assert result['metadata']['finish_reason'] == 'STOP'


class TestRateLimitedGeminiClientIntegration:
    """Integration tests for Gemini client."""
    
    @pytest.fixture
    def client(self):
        """Create client with full config."""
        config = Config.create_test_config()
        config.gemini.api_key = 'test-key'
        config.gemini.model_name = 'gemini-1.5-flash'
        return RateLimitedGeminiClient(config)
    
    def test_full_transcription_flow(self, client):
        """Test complete transcription flow."""
        mock_response = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Full transcription of audio file.'}]
                }
            }]
        }
        
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_instance = Mock()
            mock_instance.generate_content.return_value = Mock(text='Full transcription of audio file.')
            mock_model.return_value = mock_instance
            
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio data')
                f.flush()
                
                result = client.transcribe_audio(f.name)
                assert 'Full transcription' in result['text']
    
    def test_batch_transcription(self, client):
        """Test batch transcription of multiple files."""
        audio_files = []
        
        # Create test audio files
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            f.write(b'audio data')
            f.close()
            audio_files.append(f.name)
        
        try:
            with patch.object(client, '_make_request') as mock_request:
                mock_request.return_value = {
                    'candidates': [{
                        'content': {'parts': [{'text': 'Transcribed'}]}
                    }]
                }
                
                results = []
                for audio_file in audio_files:
                    result = client.transcribe_audio(audio_file)
                    results.append(result)
                
                assert len(results) == 3
                assert all(r['text'] == 'Transcribed' for r in results)
        
        finally:
            # Clean up
            for f in audio_files:
                Path(f).unlink(missing_ok=True)
    
    def test_error_recovery(self, client):
        """Test recovery from errors during processing."""
        # Simulate network error followed by success
        responses = [
            TranscriptionError("Network error"),
            {'candidates': [{'content': {'parts': [{'text': 'Success'}]}}]}
        ]
        
        with patch.object(client, '_make_request', side_effect=responses):
            with tempfile.NamedTemporaryFile(suffix='.mp3') as f:
                f.write(b'audio')
                f.flush()
                
                result = client.transcribe_audio(f.name)
                assert result['text'] == 'Success'