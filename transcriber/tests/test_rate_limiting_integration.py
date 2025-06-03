"""Integration tests for rate limiting and key rotation functionality."""

import pytest
import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock

from src.gemini_client import RateLimitedGeminiClient, create_gemini_client, RATE_LIMITS
from src.key_rotation_manager import KeyRotationManager, create_key_rotation_manager, KeyStatus
from src.orchestrator import TranscriptionOrchestrator
from src.config import Config


@pytest.mark.integration
class TestRateLimitingIntegration:
    """Test rate limiting and key rotation in real-world scenarios."""
    
    @pytest.fixture
    def mock_api_keys(self):
        """Create mock API keys for testing."""
        return ['test_key_1', 'test_key_2', 'test_key_3']
    
    @pytest.fixture
    def mock_genai_model(self):
        """Create mock Gemini model."""
        model = MagicMock()
        model.generate_content_async = AsyncMock()
        return model
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, tmp_path, mock_api_keys):
        """Test that rate limits are properly enforced."""
        # Setup
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': mock_api_keys[0],
            'GEMINI_API_KEY_2': mock_api_keys[1],
            'GEMINI_API_KEY_3': mock_api_keys[2]
        }):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    mock_model = MagicMock()
                    mock_response = Mock()
                    mock_response.text = "Test transcription"
                    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                    mock_model_cls.return_value = mock_model
                    
                    # Initialize client
                    client = RateLimitedGeminiClient(mock_api_keys)
                    
                    # Test requests per minute limit
                    requests_made = 0
                    start_time = time.time()
                    
                    # Try to make more requests than allowed per minute
                    for i in range(RATE_LIMITS['rpm'] + 2):
                        try:
                            # Mock transcription request
                            await client._transcribe_with_retry(
                                mock_model,
                                0,  # key index
                                f"https://example.com/audio{i}.mp3",
                                {'title': f'Test Episode {i}', 'duration': '1:00'}
                            )
                            requests_made += 1
                        except Exception as e:
                            # Should start failing after rpm limit
                            if requests_made >= RATE_LIMITS['rpm']:
                                assert "rate limit" in str(e).lower() or "quota" in str(e).lower()
                            else:
                                raise
                    
                    elapsed_time = time.time() - start_time
                    
                    # Verify we couldn't exceed the rate limit
                    assert requests_made <= RATE_LIMITS['rpm']
                    
                    # If we made all allowed requests, it should have taken less than a minute
                    if requests_made == RATE_LIMITS['rpm']:
                        assert elapsed_time < 60  # Should complete within a minute
    
    @pytest.mark.asyncio
    async def test_key_rotation_on_rate_limit(self, tmp_path, mock_api_keys):
        """Test that keys rotate when one hits rate limit."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': mock_api_keys[0],
            'GEMINI_API_KEY_2': mock_api_keys[1]
        }):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    # First key returns rate limit error
                    mock_model_1 = MagicMock()
                    mock_model_1.generate_content_async = AsyncMock(
                        side_effect=Exception("429: Rate limit exceeded")
                    )
                    
                    # Second key works
                    mock_model_2 = MagicMock()
                    mock_response = Mock()
                    mock_response.text = "Transcription from key 2"
                    mock_model_2.generate_content_async = AsyncMock(return_value=mock_response)
                    
                    # Return different models based on which key is used
                    mock_model_cls.side_effect = [mock_model_1, mock_model_2]
                    
                    # Initialize client
                    client = RateLimitedGeminiClient(mock_api_keys[:2])
                    
                    # First request should fail with key 1 but succeed with key 2
                    episode_data = {
                        'title': 'Test Episode',
                        'audio_url': 'https://example.com/test.mp3',
                        'duration': '30:00'
                    }
                    
                    result = await client.transcribe_audio(
                        episode_data['audio_url'],
                        episode_data
                    )
                    
                    # Should get result from second key
                    assert result == "Transcription from key 2"
                    
                    # Verify first key is marked as rate limited
                    assert not client.usage_trackers[0].is_available
                    assert client.usage_trackers[1].is_available
    
    @pytest.mark.asyncio
    async def test_daily_quota_tracking(self, tmp_path):
        """Test daily quota tracking and enforcement."""
        # Create usage state file with near-quota usage
        usage_state = {
            "last_save": datetime.now(timezone.utc).isoformat(),
            "api_keys": {
                "0": {
                    "requests_today": RATE_LIMITS['rpd'] - 2,  # 2 requests left
                    "tokens_today": RATE_LIMITS['tpd'] - 10000,  # Some tokens left
                    "last_reset": datetime.now(timezone.utc).isoformat(),
                    "is_available": True
                }
            }
        }
        
        usage_file = tmp_path / ".gemini_usage_state.json"
        with open(usage_file, 'w') as f:
            json.dump(usage_state, f)
        
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    mock_model = MagicMock()
                    mock_response = Mock()
                    mock_response.text = "Test transcription"
                    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                    mock_model_cls.return_value = mock_model
                    
                    # Patch Path.home() to use our temp directory
                    with patch('src.gemini_client.Path.home', return_value=tmp_path):
                        client = RateLimitedGeminiClient(['test_key'])
                        
                        # Should load existing usage state
                        assert client.usage_trackers[0].requests_today == RATE_LIMITS['rpd'] - 2
                        
                        # Make one request - should succeed
                        result = await client.transcribe_audio(
                            "https://example.com/audio1.mp3",
                            {'title': 'Test 1', 'duration': '5:00'}
                        )
                        assert result == "Test transcription"
                        
                        # Make another request - should succeed (last one)
                        result = await client.transcribe_audio(
                            "https://example.com/audio2.mp3",
                            {'title': 'Test 2', 'duration': '5:00'}
                        )
                        assert result == "Test transcription"
                        
                        # Next request should fail due to daily quota
                        result = await client.transcribe_audio(
                            "https://example.com/audio3.mp3",
                            {'title': 'Test 3', 'duration': '5:00'}
                        )
                        assert result is None  # Should be rejected
                        
                        # Verify quota is tracked
                        assert client.usage_trackers[0].requests_today >= RATE_LIMITS['rpd']
    
    @pytest.mark.asyncio
    async def test_daily_reset(self, tmp_path):
        """Test that daily usage resets properly."""
        # Create usage state from yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        usage_state = {
            "last_save": yesterday.isoformat(),
            "api_keys": {
                "0": {
                    "requests_today": RATE_LIMITS['rpd'],  # Hit limit yesterday
                    "tokens_today": RATE_LIMITS['tpd'],
                    "last_reset": yesterday.isoformat(),
                    "is_available": False  # Was marked unavailable
                }
            }
        }
        
        usage_file = tmp_path / ".gemini_usage_state.json"
        with open(usage_file, 'w') as f:
            json.dump(usage_state, f)
        
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    mock_model = MagicMock()
                    mock_model_cls.return_value = mock_model
                    
                    with patch('src.gemini_client.Path.home', return_value=tmp_path):
                        client = RateLimitedGeminiClient(['test_key'])
                        
                        # Should reset daily usage
                        assert client.usage_trackers[0].requests_today == 0
                        assert client.usage_trackers[0].tokens_today == 0
                        assert client.usage_trackers[0].is_available is True
    
    def test_key_rotation_manager_integration(self, tmp_path):
        """Test key rotation manager with multiple keys."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'key1',
            'GEMINI_API_KEY_2': 'key2',
            'GEMINI_API_KEY_3': 'key3'
        }):
            manager = create_key_rotation_manager()
            assert manager is not None
            assert len(manager.api_keys) == 3
            
            # Reset the index to start from beginning
            manager.current_index = 0
            manager._save_state()
            
            # Test round-robin rotation
            key1, idx1 = manager.get_next_key()
            assert key1 in ['key1', 'test_key']  # Environment might have test_key
            assert idx1 == 0
            
            key2, idx2 = manager.get_next_key()
            assert key2 == 'key2'
            assert idx2 == 1
            
            key3, idx3 = manager.get_next_key()
            assert key3 == 'key3'
            assert idx3 == 2
            
            # Should wrap around
            key4, idx4 = manager.get_next_key()
            assert key4 == 'key1'
            assert idx4 == 0
            
            # Mark key 1 as failed
            manager.mark_key_failure(0, "Test error")
            
            # Should skip key 1
            key5, idx5 = manager.get_next_key()
            assert key5 == 'key2'
            assert idx5 == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_with_multiple_keys(self, tmp_path):
        """Test handling concurrent requests with multiple API keys."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'key1',
            'GEMINI_API_KEY_2': 'key2'
        }):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    # Create mock models that track which key was used
                    call_counts = {'key1': 0, 'key2': 0}
                    
                    async def mock_generate(prompt, **kwargs):
                        # Determine which key based on prompt content
                        if "key1" in str(mock_model_cls.call_args_list):
                            call_counts['key1'] += 1
                        else:
                            call_counts['key2'] += 1
                        
                        response = Mock()
                        response.text = f"Transcription {sum(call_counts.values())}"
                        return response
                    
                    mock_model = MagicMock()
                    mock_model.generate_content_async = mock_generate
                    mock_model_cls.return_value = mock_model
                    
                    client = RateLimitedGeminiClient(['key1', 'key2'])
                    
                    # Create multiple concurrent transcription tasks
                    tasks = []
                    for i in range(6):  # More than rpm for single key
                        task = client.transcribe_audio(
                            f"https://example.com/audio{i}.mp3",
                            {'title': f'Episode {i}', 'duration': '10:00'}
                        )
                        tasks.append(task)
                    
                    # Run concurrently
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Should have successful results
                    successful = [r for r in results if r and not isinstance(r, Exception)]
                    assert len(successful) > 0
                    
                    # Both keys should have been used
                    assert client.usage_trackers[0].requests_today > 0
                    assert client.usage_trackers[1].requests_today > 0
    
    @pytest.mark.asyncio
    async def test_quota_preservation_strategy(self, tmp_path):
        """Test that the system preserves quota for important episodes."""
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    mock_model = MagicMock()
                    mock_response = Mock()
                    mock_response.text = "Test transcription"
                    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                    mock_model_cls.return_value = mock_model
                    
                    # Start with limited daily quota remaining
                    with patch('src.gemini_client.Path.home', return_value=tmp_path):
                        client = RateLimitedGeminiClient(['test_key'])
                        
                        # Manually set high usage
                        client.usage_trackers[0].requests_today = RATE_LIMITS['rpd'] - 5
                        
                        # Test should_skip_episode logic
                        from src.retry_wrapper import should_skip_episode
                        
                        # Should not skip when we have 5 requests left
                        assert not should_skip_episode(RATE_LIMITS['rpd'] - 5)
                        
                        # Should skip when very close to limit
                        assert should_skip_episode(RATE_LIMITS['rpd'] - 2)
    
    def test_usage_state_persistence(self, tmp_path):
        """Test that usage state is properly saved and loaded."""
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel'):
                    with patch('src.gemini_client.Path.home', return_value=tmp_path):
                        # Create first client and track usage
                        client1 = RateLimitedGeminiClient(['test_key'])
                        client1.usage_trackers[0].update_usage(1000)
                        client1._save_usage_state()
                        
                        # Create second client - should load saved state
                        client2 = RateLimitedGeminiClient(['test_key'])
                        assert client2.usage_trackers[0].tokens_today == 1000
                        assert client2.usage_trackers[0].requests_today == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, tmp_path):
        """Test handling various API errors and recovery."""
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.gemini_client.genai.configure'):
                with patch('src.gemini_client.genai.GenerativeModel') as mock_model_cls:
                    mock_model = MagicMock()
                    
                    # Simulate various errors
                    error_sequence = [
                        Exception("Network error"),  # Transient error
                        Exception("429: Rate limit exceeded"),  # Rate limit
                        Mock(text="Success after retry")  # Success
                    ]
                    
                    mock_model.generate_content_async = AsyncMock(
                        side_effect=error_sequence
                    )
                    mock_model_cls.return_value = mock_model
                    
                    client = RateLimitedGeminiClient(['test_key'])
                    
                    # Should retry and eventually succeed
                    result = await client.transcribe_audio(
                        "https://example.com/test.mp3",
                        {'title': 'Test', 'duration': '10:00'}
                    )
                    
                    # Third attempt should succeed
                    assert result == "Success after retry"