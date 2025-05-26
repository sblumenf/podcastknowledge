"""Smoke tests for LLM providers."""

import pytest
from unittest.mock import patch, MagicMock

from src.providers.llm.mock import MockLLMProvider
from src.providers.llm.gemini import GeminiProvider
from src.core.exceptions import ProviderError, RateLimitError


class TestMockLLMProvider:
    """Test mock LLM provider functionality."""
    
    def test_initialization(self):
        """Test provider initialization."""
        config = {
            'model_name': 'mock-model',
            'temperature': 0.5,
            'default_response': 'Test response'
        }
        provider = MockLLMProvider(config)
        
        assert provider.model_name == 'mock-model'
        assert provider.temperature == 0.5
        assert provider.default_response == 'Test response'
        
    def test_complete_fixed_mode(self):
        """Test completion in fixed mode."""
        config = {
            'response_mode': 'fixed',
            'responses': {
                'hello': 'Hi there!',
                'test': 'Test successful'
            },
            'default_response': 'Default'
        }
        provider = MockLLMProvider(config)
        
        assert provider.complete("Say hello") == "Hi there!"
        assert provider.complete("Run test") == "Test successful"
        assert provider.complete("Unknown") == "Default"
        
    def test_complete_echo_mode(self):
        """Test completion in echo mode."""
        config = {'response_mode': 'echo'}
        provider = MockLLMProvider(config)
        
        prompt = "Echo this text"
        assert provider.complete(prompt) == f"Echo: {prompt}"
        
    def test_complete_json_mode(self):
        """Test completion in JSON mode."""
        config = {'response_mode': 'json'}
        provider = MockLLMProvider(config)
        
        response = provider.complete("Extract entities")
        assert 'entities' in response
        assert 'insights' in response
        
    def test_batch_complete(self):
        """Test batch completion."""
        config = {'default_response': 'Response'}
        provider = MockLLMProvider(config)
        
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        responses = provider.batch_complete(prompts)
        
        assert len(responses) == 3
        assert all(r == 'Response' for r in responses)
        
    def test_call_tracking(self):
        """Test call count and prompt tracking."""
        provider = MockLLMProvider({})
        
        provider.complete("First prompt")
        provider.complete("Second prompt")
        
        assert provider.call_count == 2
        assert provider.get_last_prompts() == ["First prompt", "Second prompt"]
        
        provider.reset_stats()
        assert provider.call_count == 0
        assert provider.get_last_prompts() == []
        
    def test_health_check(self):
        """Test health check."""
        provider = MockLLMProvider({'model_name': 'test-model'})
        health = provider.health_check()
        
        assert health['healthy'] is True
        assert health['model'] == 'test-model'
        assert 'call_count' in health


class TestGeminiProvider:
    """Test Gemini LLM provider functionality."""
    
    def test_initialization_without_api_key(self):
        """Test initialization fails without API key."""
        config = {'model_name': 'gemini-2.0-flash'}
        
        with pytest.raises(ProviderError, match="API key is required"):
            GeminiProvider(config)
            
    @patch('src.providers.llm.gemini.ChatGoogleGenerativeAI')
    def test_initialization_with_api_key(self, mock_llm_class):
        """Test successful initialization with API key."""
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key',
            'temperature': 0.7
        }
        
        provider = GeminiProvider(config)
        provider._initialize_client()
        
        assert provider.api_key == 'test-api-key'
        assert provider.model_name == 'gemini-2.0-flash'
        mock_llm_class.assert_called_once()
        
    @patch('src.providers.llm.gemini.ChatGoogleGenerativeAI')
    def test_complete_success(self, mock_llm_class):
        """Test successful completion."""
        # Set up mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Generated response"
        mock_client.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_client
        
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key'
        }
        
        provider = GeminiProvider(config)
        response = provider.complete("Test prompt")
        
        assert response == "Generated response"
        mock_client.invoke.assert_called_once_with("Test prompt")
        
    @patch('src.providers.llm.gemini.ChatGoogleGenerativeAI')
    def test_rate_limit_check(self, mock_llm_class):
        """Test rate limit checking."""
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key',
            'rate_limits': {
                'gemini-2.0-flash': {
                    'rpm': 1,  # Very low limit for testing
                    'tpm': 100,
                    'rpd': 10
                }
            }
        }
        
        # Set up mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_client.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_client
        
        provider = GeminiProvider(config)
        
        # First request should succeed
        provider.complete("Test 1")
        
        # Second request should be rate limited
        with pytest.raises(RateLimitError):
            provider.complete("Test 2")
            
    @patch('src.providers.llm.gemini.ChatGoogleGenerativeAI')
    def test_complete_with_options(self, mock_llm_class):
        """Test completion with custom options."""
        # Set up mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Custom response"
        mock_client.invoke.return_value = mock_response
        
        # Mock the class to return different instances
        mock_llm_class.return_value = mock_client
        
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key',
            'temperature': 0.7
        }
        
        provider = GeminiProvider(config)
        result = provider.complete_with_options(
            "Test prompt",
            {'temperature': 0.9, 'max_tokens': 2048}
        )
        
        assert result['content'] == "Custom response"
        assert result['temperature'] == 0.9
        assert result['max_tokens'] == 2048
        
    @patch('src.providers.llm.gemini.ChatGoogleGenerativeAI')
    def test_health_check(self, mock_llm_class):
        """Test health check functionality."""
        # Set up mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "OK"
        mock_client.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_client
        
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key'
        }
        
        provider = GeminiProvider(config)
        health = provider.health_check()
        
        assert health['healthy'] is True
        assert health['model'] == 'gemini-2.0-flash'
        assert 'test_response' in health
        
    def test_missing_import(self):
        """Test handling of missing langchain_google_genai."""
        config = {
            'model_name': 'gemini-2.0-flash',
            'api_key': 'test-api-key'
        }
        
        with patch('src.providers.llm.gemini.ChatGoogleGenerativeAI', side_effect=ImportError):
            provider = GeminiProvider(config)
            with pytest.raises(ProviderError, match="langchain_google_genai is not installed"):
                provider._initialize_client()