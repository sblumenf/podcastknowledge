"""Comprehensive unit tests for LLM service module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.services.llm import LLMService
from src.core.exceptions import ProviderError, RateLimitError
from src.utils.rate_limiting import WindowedRateLimiter


class TestLLMService:
    """Test LLMService functionality."""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance."""
        return LLMService(
            api_key="test_api_key",
            model_name="gemini-2.5-flash",
            temperature=0.7,
            max_tokens=4096
        )
    
    def test_initialization_success(self):
        """Test successful LLM service initialization."""
        service = LLMService(
            api_key="test_key",
            model_name="gemini-2.0-flash",
            temperature=0.5,
            max_tokens=2048
        )
        
        assert service.api_key == "test_key"
        assert service.model_name == "gemini-2.0-flash"
        assert service.temperature == 0.5
        assert service.max_tokens == 2048
        assert service.client is None
        assert isinstance(service.rate_limiter, WindowedRateLimiter)
    
    def test_initialization_no_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="Gemini API key is required"):
            LLMService(api_key="")
    
    def test_rate_limiter_configuration(self, llm_service):
        """Test rate limiter is configured correctly."""
        # Check that rate limiter has correct limits
        limits = llm_service.rate_limiter.limits
        
        assert 'gemini-2.5-flash' in limits
        assert limits['gemini-2.5-flash']['rpm'] == 10
        assert limits['gemini-2.5-flash']['tpm'] == 250000
        assert limits['gemini-2.5-flash']['rpd'] == 500
        
        assert 'gemini-2.0-flash' in limits
        assert 'default' in limits
    
    @patch('src.services.llm.ChatGoogleGenerativeAI')
    def test_ensure_client_success(self, mock_chat_class, llm_service):
        """Test successful client initialization."""
        mock_client = Mock()
        mock_chat_class.return_value = mock_client
        
        llm_service._ensure_client()
        
        assert llm_service.client == mock_client
        mock_chat_class.assert_called_once_with(
            model="gemini-2.5-flash",
            google_api_key="test_api_key",
            temperature=0.7,
            max_output_tokens=4096
        )
    
    def test_ensure_client_import_error(self, llm_service):
        """Test client initialization with import error."""
        with patch.dict('sys.modules', {'langchain_google_genai': None}):
            with pytest.raises(ImportError, match="langchain_google_genai is not installed"):
                llm_service._ensure_client()
    
    @patch('src.services.llm.ChatGoogleGenerativeAI')
    def test_ensure_client_idempotent(self, mock_chat_class, llm_service):
        """Test that _ensure_client is idempotent."""
        mock_client = Mock()
        mock_chat_class.return_value = mock_client
        
        # Call twice
        llm_service._ensure_client()
        llm_service._ensure_client()
        
        # Should only create client once
        mock_chat_class.assert_called_once()
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_success(self, mock_ensure, llm_service):
        """Test successful completion."""
        mock_response = Mock()
        mock_response.content = "Generated text response"
        
        mock_client = Mock()
        mock_client.invoke.return_value = mock_response
        llm_service.client = mock_client
        
        # Mock rate limiter
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_request = Mock()
        
        result = llm_service.complete("Test prompt")
        
        assert result == "Generated text response"
        mock_client.invoke.assert_called_once_with("Test prompt")
        llm_service.rate_limiter.record_request.assert_called_once()
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_no_content_attribute(self, mock_ensure, llm_service):
        """Test completion when response has no content attribute."""
        mock_response = "String response"
        
        mock_client = Mock()
        mock_client.invoke.return_value = mock_response
        llm_service.client = mock_client
        
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_request = Mock()
        
        result = llm_service.complete("Test prompt")
        
        assert result == "String response"
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_rate_limit_exceeded(self, mock_ensure, llm_service):
        """Test completion when rate limit is exceeded."""
        llm_service.rate_limiter.can_make_request = Mock(return_value=False)
        
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            llm_service.complete("Test prompt")
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_api_quota_error(self, mock_ensure, llm_service):
        """Test completion with API quota error."""
        mock_client = Mock()
        mock_client.invoke.side_effect = Exception("Quota exceeded for API")
        llm_service.client = mock_client
        
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_error = Mock()
        
        with pytest.raises(RateLimitError, match="Gemini rate limit error"):
            llm_service.complete("Test prompt")
        
        llm_service.rate_limiter.record_error.assert_called_once()
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_general_error(self, mock_ensure, llm_service):
        """Test completion with general API error."""
        mock_client = Mock()
        mock_client.invoke.side_effect = Exception("API error")
        llm_service.client = mock_client
        
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_error = Mock()
        
        with pytest.raises(ProviderError, match="Gemini completion failed"):
            llm_service.complete("Test prompt")
    
    @patch('src.services.llm.ChatGoogleGenerativeAI')
    @patch.object(LLMService, '_ensure_client')
    def test_complete_with_options_different_settings(self, mock_ensure, mock_chat_class, llm_service):
        """Test completion with custom options."""
        mock_response = Mock()
        mock_response.content = "Custom response"
        
        mock_temp_client = Mock()
        mock_temp_client.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_temp_client
        
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_request = Mock()
        
        result = llm_service.complete_with_options(
            "Test prompt",
            temperature=0.9,
            max_tokens=2048
        )
        
        assert result['content'] == "Custom response"
        assert result['model'] == "gemini-2.5-flash"
        assert result['temperature'] == 0.9
        assert result['max_tokens'] == 2048
        assert 'usage' in result
        
        # Check temporary client was created with custom settings
        mock_chat_class.assert_called_with(
            model="gemini-2.5-flash",
            google_api_key="test_api_key",
            temperature=0.9,
            max_output_tokens=2048
        )
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_with_options_same_settings(self, mock_ensure, llm_service):
        """Test completion with options using same settings as default."""
        mock_response = Mock()
        mock_response.content = "Response"
        
        mock_client = Mock()
        mock_client.invoke.return_value = mock_response
        llm_service.client = mock_client
        
        llm_service.rate_limiter.can_make_request = Mock(return_value=True)
        llm_service.rate_limiter.record_request = Mock()
        
        result = llm_service.complete_with_options(
            "Test prompt",
            temperature=0.7,  # Same as default
            max_tokens=4096   # Same as default
        )
        
        assert result['content'] == "Response"
        # Should use existing client
        mock_client.invoke.assert_called_once()
    
    @patch.object(LLMService, '_ensure_client')
    def test_complete_with_options_partial_override(self, mock_ensure, llm_service):
        """Test completion with partial option override."""
        mock_response = Mock()
        mock_response.content = "Response"
        
        with patch('src.services.llm.ChatGoogleGenerativeAI') as mock_chat:
            mock_client = Mock()
            mock_client.invoke.return_value = mock_response
            mock_chat.return_value = mock_client
            
            llm_service.rate_limiter.can_make_request = Mock(return_value=True)
            llm_service.rate_limiter.record_request = Mock()
            
            result = llm_service.complete_with_options(
                "Test prompt",
                temperature=0.9  # Only override temperature
            )
            
            assert result['temperature'] == 0.9
            assert result['max_tokens'] == 4096  # Default value
    
    @patch.object(LLMService, 'complete')
    def test_batch_complete(self, mock_complete, llm_service):
        """Test batch completion."""
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        mock_complete.side_effect = ["Response 1", "Response 2", "Response 3"]
        
        results = llm_service.batch_complete(prompts)
        
        assert results == ["Response 1", "Response 2", "Response 3"]
        assert mock_complete.call_count == 3
    
    def test_get_rate_limit_status(self, llm_service):
        """Test getting rate limit status."""
        mock_status = {"requests": 10, "tokens": 1000}
        llm_service.rate_limiter.get_status = Mock(return_value=mock_status)
        
        status = llm_service.get_rate_limit_status()
        
        assert status == mock_status
    
    def test_token_estimation(self, llm_service):
        """Test token estimation calculation."""
        # The service estimates tokens as word_count * 1.3
        prompt = "This is a test prompt with eight words"  # 8 words
        
        with patch.object(llm_service, '_ensure_client'):
            with patch.object(llm_service.rate_limiter, 'can_make_request') as mock_can_request:
                mock_can_request.return_value = False
                
                try:
                    llm_service.complete(prompt)
                except RateLimitError:
                    pass
                
                # Check that estimated tokens were calculated correctly
                # 8 words * 1.3 = 10.4
                mock_can_request.assert_called_with("gemini-2.5-flash", 10.4)
    
    @patch('src.services.llm.logger')
    @patch('src.services.llm.ChatGoogleGenerativeAI')
    def test_client_initialization_logging(self, mock_chat_class, mock_logger, llm_service):
        """Test that client initialization is logged."""
        mock_client = Mock()
        mock_chat_class.return_value = mock_client
        
        llm_service._ensure_client()
        
        mock_logger.info.assert_called_with(
            "Initialized Gemini client with model: gemini-2.5-flash"
        )
    
    def test_different_model_configurations(self):
        """Test service with different model configurations."""
        # Test with gemini-2.0-flash
        service = LLMService(
            api_key="test_key",
            model_name="gemini-2.0-flash"
        )
        
        limits = service.rate_limiter.limits['gemini-2.0-flash']
        assert limits['rpm'] == 15
        assert limits['tpm'] == 1000000
        assert limits['rpd'] == 1500
    
    def test_complete_with_empty_prompt(self, llm_service):
        """Test completion with empty prompt."""
        with patch.object(llm_service, '_ensure_client'):
            mock_client = Mock()
            mock_client.invoke.return_value = Mock(content="Response")
            llm_service.client = mock_client
            
            llm_service.rate_limiter.can_make_request = Mock(return_value=True)
            llm_service.rate_limiter.record_request = Mock()
            
            result = llm_service.complete("")
            
            assert result == "Response"
            # Empty prompt should still work, estimated tokens would be 0