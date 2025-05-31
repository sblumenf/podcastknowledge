"""Direct LLM service for Gemini API interaction."""

from typing import Dict, Any, Optional, List
import logging

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.rate_limiting import WindowedRateLimiter
logger = logging.getLogger(__name__)


class LLMService:
    """Direct Gemini LLM service without provider abstraction."""
    
    def __init__(self, api_key: str, model_name: str = 'gemini-2.5-flash', 
                 temperature: float = 0.7, max_tokens: int = 4096):
        """Initialize LLM service with direct configuration.
        
        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
        """
        if not api_key:
            raise ValueError("Gemini API key is required")
            
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        
        # Set up rate limiter with Gemini-specific limits
        self.rate_limiter = WindowedRateLimiter({
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
        })
        
    def _ensure_client(self) -> None:
        """Ensure the Gemini client is initialized."""
        if self.client is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError:
                raise ImportError(
                    "langchain_google_genai is not installed. "
                    "Install with: pip install langchain-google-genai"
                )
                
            self.client = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )
            logger.info(f"Initialized Gemini client with model: {self.model_name}")
            
    def complete(self, prompt: str) -> str:
        """Generate completion for the given prompt.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated completion text
            
        Raises:
            RateLimitError: If rate limits are exceeded
            ProviderError: If API call fails
        """
        self._ensure_client()
        
        # Estimate tokens (rough approximation)
        estimated_tokens = len(prompt.split()) * 1.3
        
        # Check rate limits
        if not self.rate_limiter.can_make_request(self.model_name, estimated_tokens):
            raise RateLimitError(
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
            
    def complete_with_options(self, prompt: str, temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Generate completion with custom options.
        
        Args:
            prompt: Input prompt text
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Dict with content and metadata
        """
        self._ensure_client()
        
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Create a temporary client if settings differ
        if temp != self.temperature or tokens != self.max_tokens:
            from langchain_google_genai import ChatGoogleGenerativeAI
            temp_client = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=temp,
                max_output_tokens=tokens,
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
                'temperature': temp,
                'max_tokens': tokens,
                'usage': {'estimated_tokens': int(estimated_tokens)}
            }
            
        except Exception as e:
            self.rate_limiter.record_error(self.model_name, str(type(e).__name__))
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit error: {e}")
            raise ProviderError("gemini", f"Gemini completion failed: {e}")
            
    def batch_complete(self, prompts: List[str]) -> List[str]:
        """Process multiple prompts sequentially.
        
        Args:
            prompts: List of prompts to process
            
        Returns:
            List of generated completions
        """
        return [self.complete(prompt) for prompt in prompts]
        
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status.
        
        Returns:
            Dict with rate limit information
        """
        return self.rate_limiter.get_status()
