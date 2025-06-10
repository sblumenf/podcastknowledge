"""Unit tests for Gemini Direct LLM service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.services.llm_gemini_direct import GeminiDirectService
from src.core.exceptions import ProviderError, RateLimitError


class TestGeminiDirectService:
    """Test suite for GeminiDirectService."""
    
    @pytest.fixture
    def mock_key_manager(self):
        """Mock key rotation manager."""
        manager = Mock()
        manager.get_next_key.return_value = ("test-api-key", 0)
        manager.mark_key_success = Mock()
        manager.mark_key_failure = Mock()
        manager.update_key_usage = Mock()
        return manager
        
    @pytest.fixture
    def service(self, mock_key_manager):
        """Create service instance with mocked dependencies."""
        return GeminiDirectService(
            key_rotation_manager=mock_key_manager,
            model_name='gemini-2.5-flash-001',
            temperature=0.7,
            max_tokens=4096
        )
        
    def test_initialization(self, mock_key_manager):
        """Test service initialization."""
        service = GeminiDirectService(
            key_rotation_manager=mock_key_manager,
            model_name='gemini-2.5-pro-001',
            temperature=0.5,
            max_tokens=2048,
            enable_cache=False
        )
        
        assert service.model_name == 'gemini-2.5-pro-001'
        assert service.temperature == 0.5
        assert service.max_tokens == 2048
        assert service.enable_cache is False
        assert service._response_cache is None
        
    def test_initialization_requires_key_manager(self):
        """Test that initialization fails without key manager."""
        with pytest.raises(ValueError, match="KeyRotationManager is required"):
            GeminiDirectService(key_rotation_manager=None)
            
    @patch('src.services.llm_gemini_direct.genai')
    def test_ensure_client(self, mock_genai, service, mock_key_manager):
        """Test client initialization."""
        mock_client = Mock()
        mock_genai.Client.return_value = mock_client
        
        service._ensure_client("test-api-key")
        
        mock_genai.Client.assert_called_once_with(api_key="test-api-key")
        assert service.client == mock_client
        assert service._current_api_key == "test-api-key"
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_ensure_client_reuse(self, mock_genai, service):
        """Test that client is reused for same API key."""
        mock_client = Mock()
        mock_genai.Client.return_value = mock_client
        
        # First call
        service._ensure_client("test-api-key")
        assert mock_genai.Client.call_count == 1
        
        # Second call with same key - should not recreate
        service._ensure_client("test-api-key")
        assert mock_genai.Client.call_count == 1
        
        # Call with different key - should recreate
        service._ensure_client("different-api-key")
        assert mock_genai.Client.call_count == 2
        
    def test_cache_key_generation(self, service):
        """Test cache key generation."""
        key1 = service._get_cache_key("test prompt")
        key2 = service._get_cache_key("test prompt")
        key3 = service._get_cache_key("different prompt")
        
        assert key1 == key2  # Same prompt should generate same key
        assert key1 != key3  # Different prompts should generate different keys
        
    def test_response_caching(self, service):
        """Test response caching functionality."""
        cache_key = "test-key"
        response = "test response"
        
        # Cache should be empty initially
        assert service._get_cached_response(cache_key) is None
        
        # Cache response
        service._cache_response(cache_key, response)
        
        # Should retrieve cached response
        assert service._get_cached_response(cache_key) == response
        
        # Test cache expiry
        service._response_cache[cache_key]['timestamp'] = datetime.now() - timedelta(seconds=3700)
        assert service._get_cached_response(cache_key) is None
        assert cache_key not in service._response_cache
        
    def test_caching_disabled(self, mock_key_manager):
        """Test behavior when caching is disabled."""
        service = GeminiDirectService(
            key_rotation_manager=mock_key_manager,
            enable_cache=False
        )
        
        # Should not cache when disabled
        service._cache_response("key", "response")
        assert service._response_cache is None
        
        # Should return None when checking cache
        assert service._get_cached_response("key") is None
        
    @patch('src.services.llm_gemini_direct.genai')
    @patch('src.services.llm_gemini_direct.get_pipeline_metrics')
    def test_complete_success(self, mock_metrics, mock_genai, service, mock_key_manager):
        """Test successful completion."""
        # Setup mocks
        mock_response = Mock()
        mock_response.text = "Generated response"
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        mock_metric_instance = Mock()
        mock_metrics.return_value = mock_metric_instance
        
        # Make request
        result = service.complete("test prompt")
        
        # Verify result
        assert result == "Generated response"
        
        # Verify API was called correctly
        mock_client.models.generate_content.assert_called_once()
        
        # Verify key manager interactions
        mock_key_manager.get_next_key.assert_called_once_with('gemini-2.5-flash-001')
        mock_key_manager.mark_key_success.assert_called_once_with(0)
        mock_key_manager.update_key_usage.assert_called_once()
        
        # Verify metrics were recorded
        mock_metric_instance.record_api_call.assert_called_once_with(
            'gemini', success=True, latency=pytest.approx(0, abs=1)
        )
        
    @patch('src.services.llm_gemini_direct.genai')
    @patch('src.services.llm_gemini_direct.get_pipeline_metrics')
    def test_complete_with_cached_content(self, mock_metrics, mock_genai, service, mock_key_manager):
        """Test completion with cached content."""
        # Setup mocks
        mock_response = Mock()
        mock_response.text = "Generated with cache"
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        # Import types mock
        mock_types = Mock()
        mock_genai.types = mock_types
        
        # Make request with cached content
        result = service.complete("test prompt", cached_content_name="cache-123")
        
        assert result == "Generated with cache"
        
        # Verify the config included cached_content
        call_args = mock_client.models.generate_content.call_args
        assert call_args[1]['model'] == 'gemini-2.5-flash-001'
        assert call_args[1]['contents'] == "test prompt"
        
    @patch('src.services.llm_gemini_direct.genai')
    @patch('src.services.llm_gemini_direct.get_pipeline_metrics')
    def test_complete_cache_hit(self, mock_metrics, mock_genai, service):
        """Test completion with cache hit."""
        mock_metric_instance = Mock()
        mock_metrics.return_value = mock_metric_instance
        
        # Pre-populate cache
        cache_key = service._get_cache_key("test prompt")
        service._cache_response(cache_key, "cached response")
        
        # Make request - should hit cache
        result = service.complete("test prompt")
        
        assert result == "cached response"
        
        # Verify no API call was made
        assert not mock_genai.Client.called
        
        # Verify metrics show cache hit (0 latency)
        mock_metric_instance.record_api_call.assert_called_once_with(
            'gemini', success=True, latency=0
        )
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_complete_rate_limit_error(self, mock_genai, service, mock_key_manager):
        """Test handling of rate limit errors."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("quota exceeded")
        mock_genai.Client.return_value = mock_client
        
        # Should try multiple keys before failing
        mock_key_manager.get_next_key.side_effect = [
            ("key1", 0),
            ("key2", 1),
            ("key3", 2)
        ]
        
        with pytest.raises(ProviderError, match="Gemini completion failed after all retries"):
            service.complete("test prompt")
            
        # Should have tried 3 times
        assert mock_key_manager.get_next_key.call_count == 3
        assert mock_key_manager.mark_key_failure.call_count == 3
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_complete_no_keys_available(self, mock_genai, service, mock_key_manager):
        """Test handling when no API keys are available."""
        mock_key_manager.get_next_key.side_effect = Exception("No API keys available")
        
        with pytest.raises(RateLimitError, match="All API keys have exceeded their quotas"):
            service.complete("test prompt")
            
    @patch('src.services.llm_gemini_direct.genai')
    def test_create_cached_content(self, mock_genai, service, mock_key_manager):
        """Test creating cached content."""
        # Setup mocks
        mock_cached_content = Mock()
        mock_cached_content.name = "cache-abc123"
        
        mock_client = Mock()
        mock_client.caches.create.return_value = mock_cached_content
        mock_genai.Client.return_value = mock_client
        
        # Create cache
        cache_name = service.create_cached_content(
            content="Long transcript content",
            episode_id="episode-123",
            system_instruction="Extract knowledge from podcast"
        )
        
        assert cache_name == "cache-abc123"
        
        # Verify cache was created correctly
        mock_client.caches.create.assert_called_once()
        
        # Verify cache is stored internally
        assert "episode_episode-123" in service._context_cache
        assert service._context_cache["episode_episode-123"]["name"] == "cache-abc123"
        
    def test_create_cached_content_disabled(self, mock_key_manager):
        """Test cache creation when caching is disabled."""
        service = GeminiDirectService(
            key_rotation_manager=mock_key_manager,
            enable_cache=False
        )
        
        result = service.create_cached_content("content", "episode-123")
        assert result is None
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_batch_complete(self, mock_genai, service, mock_key_manager):
        """Test batch completion."""
        # Setup mocks
        mock_responses = [Mock(text=f"Response {i}") for i in range(3)]
        
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = mock_responses
        mock_genai.Client.return_value = mock_client
        
        # Process batch
        prompts = ["prompt1", "prompt2", "prompt3"]
        results = service.batch_complete(prompts)
        
        assert len(results) == 3
        assert results == ["Response 0", "Response 1", "Response 2"]
        assert mock_client.models.generate_content.call_count == 3
        
    def test_clear_expired_caches(self, service):
        """Test clearing expired caches."""
        # Add some caches
        now = datetime.now()
        
        # Response cache - one expired, one valid
        service._response_cache["expired"] = {
            'response': 'old',
            'timestamp': now - timedelta(seconds=4000)
        }
        service._response_cache["valid"] = {
            'response': 'new',
            'timestamp': now - timedelta(seconds=1000)
        }
        
        # Context cache - one expired, one valid
        service._context_cache["episode_old"] = {
            'name': 'cache-old',
            'created': now - timedelta(seconds=4000)
        }
        service._context_cache["episode_new"] = {
            'name': 'cache-new',
            'created': now - timedelta(seconds=1000)
        }
        
        # Clear expired
        service.clear_expired_caches()
        
        # Check that only valid caches remain
        assert "expired" not in service._response_cache
        assert "valid" in service._response_cache
        assert "episode_old" not in service._context_cache
        assert "episode_new" in service._context_cache
        
    def test_complete_with_options(self, service, mock_key_manager):
        """Test complete_with_options method."""
        with patch('src.services.llm_gemini_direct.genai') as mock_genai:
            # Setup mocks
            mock_response = Mock()
            mock_response.text = "Custom response"
            
            mock_client = Mock()
            mock_client.models.generate_content.return_value = mock_response
            mock_genai.Client.return_value = mock_client
            
            # Call with custom options
            result = service.complete_with_options(
                prompt="test prompt",
                temperature=0.3,
                max_tokens=1024,
                cached_content_name="cache-123"
            )
            
            assert result['content'] == "Custom response"
            assert result['temperature'] == 0.3
            assert result['max_tokens'] == 1024
            assert result['cached_content'] == "cache-123"
            assert result['model'] == 'gemini-2.5-flash-001'
            
    def test_generate_alias(self, service):
        """Test that generate method works as alias for complete."""
        with patch.object(service, 'complete') as mock_complete:
            mock_complete.return_value = "test response"
            
            result = service.generate("test prompt", cached_content_name="cache-123")
            
            assert result == "test response"
            mock_complete.assert_called_once_with("test prompt", "cache-123")