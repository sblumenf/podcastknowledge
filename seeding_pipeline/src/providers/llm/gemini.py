"""Gemini LLM provider implementation."""

import logging
from typing import Dict, Any, Optional, List

from src.providers.llm.base import BaseLLMProvider, LLMResponse
from src.core.exceptions import ProviderError, RateLimitError
from src.core.plugin_discovery import provider_plugin
from src.utils.rate_limiting import WindowedRateLimiter


logger = logging.getLogger(__name__)


@provider_plugin('llm', 'gemini', version='1.0.0', author='Google', 
                description='LLM provider using Google Gemini')
class GeminiProvider(BaseLLMProvider):
    """Gemini LLM provider using langchain_google_genai."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini provider with configuration."""
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ProviderError("gemini", "Gemini API key is required")
            
        self.client = None
        # Set up rate limiter with Gemini-specific limits
        rate_limits = config.get('rate_limits', {})
        if not rate_limits:
            rate_limits = {
                'gemini-2.5-flash': {
                    'rpm': 10,      # Requests per minute
                    'tpm': 250000,  # Tokens per minute
                    'rpd': 500      # Requests per day
                },
                'gemini-2.0-flash': {
                    'rpm': 15,
                    'tpm': 1000000,
                    'rpd': 1500
                },
                'default': {
                    'rpm': 10,
                    'tpm': 100000,
                    'rpd': 500
                }
            }
        self.rate_limiter = WindowedRateLimiter(rate_limits)
        
    def _initialize_client(self) -> None:
        """Initialize the Gemini client."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ProviderError(
                "gemini",
                "langchain_google_genai is not installed. "
                "Install with: pip install langchain-google-genai"
            )
            
        try:
            self.client = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )
            logger.info(f"Initialized Gemini client with model: {self.model_name}")
        except Exception as e:
            raise ProviderError("gemini", f"Failed to initialize Gemini client: {e}")
            
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate completion for the given prompt."""
        self._ensure_initialized()
        
        # Estimate tokens (rough approximation)
        estimated_tokens = len(prompt.split()) * 1.3
        
        # Check rate limits
        if not self.rate_limiter.can_make_request(self.model_name, estimated_tokens):
            raise RateLimitError(
                "gemini",
                f"Rate limit exceeded for model {self.model_name}. "
                "Please wait before making another request."
            )
            
        try:
            # Make the request
            response = self.client.invoke(prompt)
            
            # Record successful request
            self.rate_limiter.record_request(self.model_name, estimated_tokens)
            
            # Extract content from response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)
                
        except Exception as e:
            self.rate_limiter.record_error(self.model_name, str(type(e).__name__))
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit error: {e}")
            raise ProviderError("gemini", f"Gemini completion failed: {e}")
            
    def complete_with_options(self, prompt: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion with additional options."""
        self._ensure_initialized()
        
        # Extract options
        temperature = options.get('temperature', self.temperature)
        max_tokens = options.get('max_tokens', self.max_tokens)
        
        # Create a temporary client with custom settings if needed
        if temperature != self.temperature or max_tokens != self.max_tokens:
            from langchain_google_genai import ChatGoogleGenerativeAI
            temp_client = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        else:
            temp_client = self.client
            
        # Estimate tokens
        estimated_tokens = len(prompt.split()) * 1.3
        
        # Check rate limits
        if not self.rate_limiter.can_make_request(self.model_name, estimated_tokens):
            raise RateLimitError(f"Rate limit exceeded for model {self.model_name}")
            
        try:
            response = temp_client.invoke(prompt)
            self.rate_limiter.record_request(self.model_name, estimated_tokens)
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'content': content,
                'model': self.model_name,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'usage': {'estimated_tokens': int(estimated_tokens)}
            }
            
        except Exception as e:
            self.rate_limiter.record_error(self.model_name, str(type(e).__name__))
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit error: {e}")
            raise ProviderError("gemini", f"Gemini completion failed: {e}")
            
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return self.rate_limiter.get_status()