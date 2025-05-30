"""Comprehensive tests for LLM provider modules.

Tests for src/providers/llm/*.py covering all LLM provider functionality.
"""

import pytest
from unittest import mock
import json
from typing import Dict, Any, List

from src.providers.llm.base import LLMProvider, LLMResponse
from src.providers.llm.gemini import GeminiProvider
from src.providers.llm.mock import MockLLMProvider
from src.core.exceptions import ProviderError


class TestLLMProviderBase:
    """Test LLMProvider base class."""
    
    def test_llm_response_creation(self):
        """Test LLMResponse dataclass."""
        response = LLMResponse(
            content="Test response",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            metadata={"temperature": 0.7}
        )
        
        assert response.content == "Test response"
        assert response.model == "gpt-4"
        assert response.usage["prompt_tokens"] == 10
        assert response.metadata["temperature"] == 0.7
    
    def test_base_provider_abstract_methods(self):
        """Test that base provider enforces abstract methods."""
        with pytest.raises(TypeError):
            # Should not be able to instantiate abstract base class
            LLMProvider()


class TestMockLLMProvider:
    """Test MockLLMProvider class."""
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock LLM provider instance."""
        return MockLLMProvider(
            responses=["Response 1", "Response 2"],
            response_delay=0.0
        )
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        provider = MockLLMProvider(
            responses=["Test"],
            response_delay=0.1,
            error_rate=0.5
        )
        
        assert provider.responses == ["Test"]
        assert provider.response_delay == 0.1
        assert provider.error_rate == 0.5
        assert provider.call_count == 0
    
    def test_mock_provider_complete(self, mock_provider):
        """Test mock provider completion."""
        response = mock_provider.complete("Test prompt")
        
        assert response == "Response 1"
        assert mock_provider.call_count == 1
        assert mock_provider.last_prompt == "Test prompt"
        
        # Second call should return second response
        response = mock_provider.complete("Another prompt")
        assert response == "Response 2"
        assert mock_provider.call_count == 2
        
        # Third call should cycle back
        response = mock_provider.complete("Third prompt")
        assert response == "Response 1"
    
    def test_mock_provider_with_callback(self):
        """Test mock provider with response callback."""
        def custom_response(prompt: str) -> str:
            if "entity" in prompt.lower():
                return json.dumps([{"name": "Test Entity", "type": "Person"}])
            return "Default response"
        
        provider = MockLLMProvider(response_callback=custom_response)
        
        response = provider.complete("Extract entities")
        assert "Test Entity" in response
        
        response = provider.complete("Other prompt")
        assert response == "Default response"
    
    def test_mock_provider_error_simulation(self):
        """Test mock provider error simulation."""
        provider = MockLLMProvider(
            responses=["Success"],
            error_rate=1.0  # Always error
        )
        
        with pytest.raises(ProviderError):
            provider.complete("Test")
    
    def test_mock_provider_structured_complete(self, mock_provider):
        """Test mock provider structured completion."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            }
        }
        
        mock_provider.responses = [json.dumps({"name": "John", "age": 30})]
        
        response = mock_provider.complete_structured("Test", schema)
        
        assert isinstance(response, dict)
        assert response["name"] == "John"
        assert response["age"] == 30
    
    def test_mock_provider_health_check(self, mock_provider):
        """Test mock provider health check."""
        health = mock_provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "mock"
        assert "call_count" in health
    
    def test_mock_provider_cleanup(self, mock_provider):
        """Test mock provider cleanup."""
        mock_provider.call_count = 10
        mock_provider.cleanup()
        
        # Cleanup should reset state
        assert mock_provider.call_count == 0
        assert mock_provider.last_prompt is None


class TestGeminiProvider:
    """Test GeminiProvider class."""
    
    @pytest.fixture
    def mock_genai(self):
        """Create mock Google GenerativeAI."""
        with mock.patch('src.providers.llm.gemini.genai') as mock_genai:
            yield mock_genai
    
    @pytest.fixture
    def gemini_provider(self, mock_genai):
        """Create Gemini provider instance."""
        # Mock the model
        mock_model = mock.Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(
            api_key="test-key",
            model_name="gemini-pro",
            temperature=0.7,
            max_output_tokens=1000
        )
        provider.model = mock_model
        return provider
    
    def test_gemini_initialization(self, mock_genai):
        """Test Gemini provider initialization."""
        provider = GeminiProvider(
            api_key="test-key",
            model_name="gemini-pro-vision",
            temperature=0.5,
            max_output_tokens=2000,
            top_p=0.9,
            top_k=40
        )
        
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        assert provider.model_name == "gemini-pro-vision"
        assert provider.temperature == 0.5
        assert provider.max_output_tokens == 2000
    
    def test_gemini_complete_success(self, gemini_provider):
        """Test successful Gemini completion."""
        # Mock response
        mock_response = mock.Mock()
        mock_response.text = "Generated response"
        gemini_provider.model.generate_content.return_value = mock_response
        
        result = gemini_provider.complete("Test prompt")
        
        assert result == "Generated response"
        gemini_provider.model.generate_content.assert_called_once()
        
        # Check generation config
        call_args = gemini_provider.model.generate_content.call_args
        assert "Test prompt" in call_args[0]
    
    def test_gemini_complete_with_system_prompt(self, gemini_provider):
        """Test Gemini completion with system prompt."""
        mock_response = mock.Mock()
        mock_response.text = "Response with context"
        gemini_provider.model.generate_content.return_value = mock_response
        
        result = gemini_provider.complete(
            "User prompt",
            system_prompt="You are a helpful assistant"
        )
        
        assert result == "Response with context"
        
        # Check that system prompt is included
        call_args = gemini_provider.model.generate_content.call_args
        prompt = call_args[0][0]
        assert "You are a helpful assistant" in prompt
        assert "User prompt" in prompt
    
    def test_gemini_complete_structured(self, gemini_provider):
        """Test Gemini structured completion."""
        schema = {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string"},
                "score": {"type": "number"}
            }
        }
        
        mock_response = mock.Mock()
        mock_response.text = json.dumps({"sentiment": "positive", "score": 0.8})
        gemini_provider.model.generate_content.return_value = mock_response
        
        result = gemini_provider.complete_structured("Analyze sentiment", schema)
        
        assert isinstance(result, dict)
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.8
    
    def test_gemini_error_handling(self, gemini_provider):
        """Test Gemini error handling."""
        # Simulate API error
        gemini_provider.model.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(ProviderError) as exc_info:
            gemini_provider.complete("Test")
        
        assert "Failed to generate" in str(exc_info.value)
    
    def test_gemini_retry_logic(self, gemini_provider):
        """Test Gemini retry on failure."""
        # First call fails, second succeeds
        mock_response = mock.Mock()
        mock_response.text = "Success after retry"
        
        gemini_provider.model.generate_content.side_effect = [
            Exception("Temporary error"),
            mock_response
        ]
        
        # Should retry and succeed
        with mock.patch('time.sleep'):  # Skip delay
            result = gemini_provider.complete("Test")
        
        assert result == "Success after retry"
        assert gemini_provider.model.generate_content.call_count == 2
    
    def test_gemini_rate_limiting(self, gemini_provider):
        """Test Gemini rate limit handling."""
        # Simulate rate limit error
        rate_limit_error = Exception("429: Resource exhausted")
        gemini_provider.model.generate_content.side_effect = rate_limit_error
        
        with pytest.raises(ProviderError):
            with mock.patch('time.sleep'):  # Skip delay
                gemini_provider.complete("Test")
    
    def test_gemini_health_check(self, gemini_provider):
        """Test Gemini health check."""
        # Mock successful generation
        mock_response = mock.Mock()
        mock_response.text = "Health check response"
        gemini_provider.model.generate_content.return_value = mock_response
        
        health = gemini_provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "gemini"
        assert health["model"] == "gemini-pro"
    
    def test_gemini_cleanup(self, gemini_provider):
        """Test Gemini cleanup."""
        gemini_provider.cleanup()
        
        # Should clear model reference
        assert gemini_provider.model is None


class TestProviderComparison:
    """Test different providers with same inputs."""
    
    def test_providers_consistency(self):
        """Test that different providers handle same inputs consistently."""
        prompt = "Extract entities from: OpenAI released GPT-4"
        
        # Mock provider
        mock_provider = MockLLMProvider(
            responses=[json.dumps([
                {"name": "OpenAI", "type": "Organization"},
                {"name": "GPT-4", "type": "Technology"}
            ])]
        )
        
        # Gemini provider (mocked)
        with mock.patch('src.providers.llm.gemini.genai'):
            gemini_provider = GeminiProvider(api_key="test")
            gemini_provider.model = mock.Mock()
            mock_response = mock.Mock()
            mock_response.text = json.dumps([
                {"name": "OpenAI", "type": "Organization"},
                {"name": "GPT-4", "type": "Technology"}
            ])
            gemini_provider.model.generate_content.return_value = mock_response
        
        # Both should parse to same structure
        mock_result = json.loads(mock_provider.complete(prompt))
        gemini_result = json.loads(gemini_provider.complete(prompt))
        
        assert len(mock_result) == len(gemini_result)
        assert mock_result[0]["name"] == gemini_result[0]["name"]


class TestEdgeCases:
    """Test edge cases for LLM providers."""
    
    def test_empty_prompt_handling(self):
        """Test handling of empty prompts."""
        provider = MockLLMProvider(responses=["Default"])
        
        # Should handle empty prompt
        result = provider.complete("")
        assert result == "Default"
        
        result = provider.complete(None)
        assert result == "Default"
    
    def test_very_long_prompt(self):
        """Test handling of very long prompts."""
        provider = MockLLMProvider(responses=["Handled"])
        
        # Create a very long prompt
        long_prompt = "Test " * 10000  # ~50k characters
        
        result = provider.complete(long_prompt)
        assert result == "Handled"
        assert provider.last_prompt == long_prompt
    
    def test_unicode_prompts(self):
        """Test handling of unicode in prompts."""
        provider = MockLLMProvider(responses=["Unicode handled"])
        
        unicode_prompt = "Analyze: 日本語 中文 한국어 🌍🚀"
        result = provider.complete(unicode_prompt)
        
        assert result == "Unicode handled"
        assert provider.last_prompt == unicode_prompt
    
    def test_structured_output_validation(self):
        """Test structured output validation."""
        provider = MockLLMProvider(
            responses=['{"invalid": "json"']  # Missing closing brace
        )
        
        schema = {"type": "object"}
        
        with pytest.raises(json.JSONDecodeError):
            provider.complete_structured("Test", schema)
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import threading
        
        provider = MockLLMProvider(
            responses=["Response 1", "Response 2", "Response 3"],
            response_delay=0.01
        )
        
        results = []
        errors = []
        
        def make_request(prompt):
            try:
                result = provider.complete(prompt)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=make_request, args=(f"Prompt {i}",))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should handle concurrent requests
        assert len(errors) == 0
        assert len(results) == 5
        assert provider.call_count == 5