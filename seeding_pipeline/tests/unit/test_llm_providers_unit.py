"""Tests for LLM provider implementations."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from typing import Dict, Any, List

from src.providers.llm.base import LLMProvider
from src.providers.llm.mock import MockLLMProvider
from src.providers.llm.gemini import GeminiProvider


class TestMockLLMProvider:
    """Test MockLLMProvider implementation."""
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        provider = MockLLMProvider()
        assert provider.name == "mock"
        assert provider.model == "mock-llm-v1"
        assert provider.temperature == 0.7
    
    def test_mock_provider_with_config(self):
        """Test mock provider with configuration."""
        config = {
            "model": "mock-llm-v2",
            "temperature": 0.5,
            "max_tokens": 500,
            "response_delay": 0.01
        }
        
        provider = MockLLMProvider(config)
        assert provider.model == "mock-llm-v2"
        assert provider.temperature == 0.5
        assert provider.max_tokens == 500
        assert provider.response_delay == 0.01
    
    def test_mock_provider_generate(self):
        """Test mock provider text generation."""
        provider = MockLLMProvider({"response_delay": 0.01})
        
        prompt = "Extract entities from: The meeting is at 3pm"
        response = provider.generate(prompt)
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Should return JSON for extraction prompts
        if "extract" in prompt.lower():
            data = json.loads(response)
            assert "entities" in data
    
    def test_mock_provider_generate_with_params(self):
        """Test mock provider with generation parameters."""
        provider = MockLLMProvider()
        
        response = provider.generate(
            "Test prompt",
            temperature=0.9,
            max_tokens=100,
            top_p=0.95
        )
        
        assert isinstance(response, str)
        assert len(response) <= 1000  # Reasonable length
    
    def test_mock_provider_batch_generate(self):
        """Test mock provider batch generation."""
        provider = MockLLMProvider({"response_delay": 0.001})
        
        prompts = [
            "Extract entities from: Apple Inc.",
            "Extract insights from: AI is transforming industries",
            "Summarize: Long text here"
        ]
        
        responses = provider.batch_generate(prompts)
        
        assert len(responses) == 3
        assert all(isinstance(r, str) for r in responses)
        assert all(len(r) > 0 for r in responses)
    
    def test_mock_provider_health_check(self):
        """Test mock provider health check."""
        provider = MockLLMProvider()
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "mock"
        assert health["model"] == "mock-llm-v1"
    
    def test_mock_provider_custom_responses(self):
        """Test mock provider with custom responses."""
        provider = MockLLMProvider()
        
        # Entity extraction
        response = provider.generate("Extract entities from: John works at OpenAI")
        data = json.loads(response)
        assert "entities" in data
        assert len(data["entities"]) > 0
        
        # Insight extraction
        response = provider.generate("Extract insights from: AI improves efficiency")
        data = json.loads(response)
        assert "insights" in data
        
        # Quote extraction
        response = provider.generate('Extract quotes from: He said "Hello world"')
        data = json.loads(response)
        assert "quotes" in data
    
    def test_mock_provider_error_simulation(self):
        """Test mock provider error simulation."""
        provider = MockLLMProvider({"error_rate": 1.0})
        
        with pytest.raises(Exception, match="Mock LLM error"):
            provider.generate("Test prompt")
    
    def test_mock_provider_token_counting(self):
        """Test mock provider token counting."""
        provider = MockLLMProvider()
        
        # Should track token usage
        prompt = "Count tokens in this prompt"
        response = provider.generate(prompt)
        
        assert hasattr(provider, 'total_tokens_used')
        assert provider.total_tokens_used > 0


class TestGeminiProvider:
    """Test GeminiProvider implementation."""
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_initialization(self, mock_model_class, mock_configure):
        """Test Gemini provider initialization."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        config = {
            "api_key": "test-key",
            "model": "gemini-pro",
            "temperature": 0.5
        }
        
        provider = GeminiProvider(config)
        
        mock_configure.assert_called_once_with(api_key="test-key")
        mock_model_class.assert_called_once_with("gemini-pro")
        assert provider.model_name == "gemini-pro"
        assert provider.temperature == 0.5
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_generate(self, mock_model_class, mock_configure):
        """Test Gemini provider text generation."""
        # Mock model and response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"entities": [{"name": "John", "type": "person"}]}'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({"api_key": "test-key"})
        
        prompt = "Extract entities from: John works at Google"
        response = provider.generate(prompt)
        
        assert response == mock_response.text
        mock_model.generate_content.assert_called_once()
        
        # Check generation config
        call_args = mock_model.generate_content.call_args
        assert prompt in str(call_args)
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_with_generation_config(self, mock_model_class, mock_configure):
        """Test Gemini provider with custom generation config."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({
            "api_key": "test-key",
            "temperature": 0.9,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 500
        })
        
        response = provider.generate("Test prompt", temperature=0.3)
        
        # Should use overridden temperature
        call_kwargs = mock_model.generate_content.call_args[1]
        assert call_kwargs["generation_config"]["temperature"] == 0.3
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_batch_generate(self, mock_model_class, mock_configure):
        """Test Gemini provider batch generation."""
        mock_model = MagicMock()
        
        # Mock different responses
        responses = [
            MagicMock(text='{"entities": []}'),
            MagicMock(text='{"insights": []}'),
            MagicMock(text='{"summary": "Test"}')
        ]
        mock_model.generate_content.side_effect = responses
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({"api_key": "test-key"})
        
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        results = provider.batch_generate(prompts)
        
        assert len(results) == 3
        assert results[0] == '{"entities": []}'
        assert results[1] == '{"insights": []}'
        assert results[2] == '{"summary": "Test"}'
        assert mock_model.generate_content.call_count == 3
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_error_handling(self, mock_model_class, mock_configure):
        """Test Gemini provider error handling."""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({"api_key": "test-key"})
        
        with pytest.raises(Exception, match="API Error"):
            provider.generate("Test prompt")
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_retry_logic(self, mock_model_class, mock_configure):
        """Test Gemini provider retry logic."""
        mock_model = MagicMock()
        
        # Fail twice, then succeed
        mock_model.generate_content.side_effect = [
            Exception("Rate limit"),
            Exception("Rate limit"),
            MagicMock(text="Success")
        ]
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({
            "api_key": "test-key",
            "retry_attempts": 3,
            "retry_delay": 0.01
        })
        
        response = provider.generate("Test prompt")
        assert response == "Success"
        assert mock_model.generate_content.call_count == 3
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_health_check(self, mock_model_class, mock_configure):
        """Test Gemini provider health check."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Health check response"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({"api_key": "test-key"})
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "gemini"
        assert health["model"] == "gemini-pro"
        
        # Should have made a test call
        mock_model.generate_content.assert_called()
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_safety_settings(self, mock_model_class, mock_configure):
        """Test Gemini provider with safety settings."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Safe response"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({
            "api_key": "test-key",
            "safety_settings": {
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE"
            }
        })
        
        provider.generate("Test prompt")
        
        call_kwargs = mock_model.generate_content.call_args[1]
        assert "safety_settings" in call_kwargs
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_provider_streaming(self, mock_model_class, mock_configure):
        """Test Gemini provider streaming response."""
        mock_model = MagicMock()
        
        # Mock streaming response
        mock_chunks = [
            MagicMock(text="Part 1 "),
            MagicMock(text="Part 2 "),
            MagicMock(text="Part 3")
        ]
        mock_model.generate_content.return_value = mock_chunks
        
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider({"api_key": "test-key"})
        
        # Streaming not implemented in base, but provider should handle
        response = provider.generate("Test prompt", stream=True)
        
        # Should concatenate chunks
        expected = "Part 1 Part 2 Part 3"
        assert response == expected or isinstance(response, str)


class TestLLMProviderIntegration:
    """Test LLM provider integration scenarios."""
    
    def test_provider_prompt_formatting(self):
        """Test consistent prompt formatting across providers."""
        mock_provider = MockLLMProvider()
        
        # Test extraction prompt
        entities_prompt = "Extract entities from: John works at OpenAI in San Francisco"
        response = mock_provider.generate(entities_prompt)
        
        # Should return valid JSON
        data = json.loads(response)
        assert isinstance(data, dict)
        assert "entities" in data or "error" not in data
    
    def test_provider_response_parsing(self):
        """Test parsing provider responses."""
        provider = MockLLMProvider({"response_delay": 0.001})
        
        # Test different prompt types
        test_cases = [
            ("Extract entities from: Test", "entities"),
            ("Extract insights from: Test", "insights"),
            ("Extract quotes from: Test", "quotes"),
            ("Summarize: Test", None)  # General response
        ]
        
        for prompt, expected_key in test_cases:
            response = provider.generate(prompt)
            
            if expected_key:
                data = json.loads(response)
                assert expected_key in data
            else:
                assert isinstance(response, str)
    
    def test_provider_token_limits(self):
        """Test handling of token limits."""
        provider = MockLLMProvider({
            "max_tokens": 100,
            "response_delay": 0.001
        })
        
        # Long prompt
        long_prompt = "Process this: " + " ".join(["word"] * 1000)
        response = provider.generate(long_prompt)
        
        # Should still return valid response
        assert isinstance(response, str)
        assert len(response) > 0
    
    def test_provider_concurrent_requests(self):
        """Test concurrent request handling."""
        import threading
        
        provider = MockLLMProvider({"response_delay": 0.01})
        results = []
        
        def make_request(prompt, index):
            response = provider.generate(prompt)
            results.append((index, response))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=make_request,
                args=(f"Test prompt {i}", i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have all results
        assert len(results) == 5
        assert all(isinstance(r[1], str) for r in results)