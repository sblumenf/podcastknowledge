"""Direct LLM service for Gemini API interaction with API key rotation."""

from typing import Dict, Any, Optional, List
import logging
import time
import hashlib
import json
from datetime import datetime

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.retry import ExponentialBackoff
from src.utils.metrics import get_pipeline_metrics
from src.utils.key_rotation_manager import KeyRotationManager

logger = logging.getLogger(__name__)


class LLMService:
    """Direct Gemini LLM service with API key rotation."""
    
    def __init__(self, key_rotation_manager: KeyRotationManager, 
                 model_name: str = 'gemini-2.5-flash', 
                 temperature: float = 0.7, max_tokens: int = 4096,
                 enable_cache: bool = True, cache_ttl: int = 3600):
        """Initialize LLM service with key rotation support.
        
        Args:
            key_rotation_manager: KeyRotationManager instance for API key rotation
            model_name: Model to use (default: gemini-2.5-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
            enable_cache: Enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        if not key_rotation_manager:
            raise ValueError("KeyRotationManager is required")
            
        self.key_rotation_manager = key_rotation_manager
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        self.provider = "gemini"
        
        # Resilience features
        self.backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._response_cache = {} if enable_cache else None
        
    def _ensure_client(self, api_key: str) -> None:
        """Ensure the Gemini client is initialized with the given API key.
        
        Args:
            api_key: API key to use for client initialization
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain_google_genai is not installed. "
                "Install with: pip install langchain-google-genai"
            )
            
        self.client = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        logger.debug(f"Initialized Gemini client with model: {self.model_name}")
            
    def _get_cache_key(self, prompt: str, temperature: Optional[float] = None) -> str:
        """Generate cache key for prompt."""
        temp = temperature if temperature is not None else self.temperature
        key_str = f"{prompt}_{temp}_{self.model_name}"
        return hashlib.md5(key_str.encode()).hexdigest()
        
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        if not self.enable_cache or cache_key not in self._response_cache:
            return None
            
        cached = self._response_cache[cache_key]
        if (datetime.now() - cached['timestamp']).total_seconds() < self.cache_ttl:
            logger.debug(f"Cache hit for key: {cache_key}")
            return cached['response']
            
        # Expired
        del self._response_cache[cache_key]
        return None
        
    def _cache_response(self, cache_key: str, response: str):
        """Cache response with timestamp."""
        if self.enable_cache:
            self._response_cache[cache_key] = {
                'response': response,
                'timestamp': datetime.now()
            }
            

    def complete(self, prompt: str) -> str:
        """Generate completion with API key rotation.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated completion text
            
        Raises:
            RateLimitError: If all API keys are exhausted
            ProviderError: If API call fails after all retries
        """
        # Get metrics instance
        metrics = get_pipeline_metrics()
        api_start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(prompt)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            # Record cache hit as successful API call with 0 latency
            metrics.record_api_call(self.provider, success=True, latency=0)
            return cached_response
        
        # Estimate tokens (rough approximation)
        estimated_tokens = int(len(prompt.split()) * 1.3)
        
        # Try with exponential backoff
        self.backoff.reset()
        last_exception = None
        
        for attempt in range(3):  # Max 3 attempts
            try:
                # Get next available API key
                api_key, key_index = self.key_rotation_manager.get_next_key(self.model_name)
                
                # Ensure client is initialized with this key
                self._ensure_client(api_key)
                
                # Make the request
                response = self.client.invoke(prompt)
                
                # Extract content from response
                if hasattr(response, 'content'):
                    result = response.content
                else:
                    result = str(response)
                
                # Report success to rotation manager
                self.key_rotation_manager.mark_key_success(key_index)
                self.key_rotation_manager.update_key_usage(key_index, estimated_tokens, self.model_name)
                
                # Cache successful response
                self._cache_response(cache_key, result)
                
                # Record successful API call
                api_latency = time.time() - api_start_time
                metrics.record_api_call(self.provider, success=True, latency=api_latency)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if it's a key rotation exception (no keys available)
                if "No API keys available" in str(e):
                    logger.error("All API keys exhausted")
                    raise RateLimitError("All API keys have exceeded their quotas")
                
                # Report failure to rotation manager if we have a key index
                if 'key_index' in locals():
                    self.key_rotation_manager.mark_key_failure(key_index, str(e))
                
                # Check if it's a rate limit error
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    logger.warning(f"Rate limit hit on attempt {attempt + 1}, trying next key...")
                    continue
                    
                # Other errors - retry with backoff
                if attempt < 2:
                    delay = self.backoff.get_next_delay()
                    logger.warning(f"API error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    time.sleep(delay)
                    
        # All retries failed
        logger.error(f"All API attempts failed: {last_exception}")
        
        # Record failed API call
        api_latency = time.time() - api_start_time
        metrics.record_api_call(self.provider, success=False, latency=api_latency)
        
        raise ProviderError(self.provider, f"Gemini completion failed after all retries: {last_exception}")
            
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
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Estimate tokens
        estimated_tokens = int(len(prompt.split()) * 1.3)
        
        try:
            # Get next available API key
            api_key, key_index = self.key_rotation_manager.get_next_key(self.model_name)
            
            # Create client with custom settings
            from langchain_google_genai import ChatGoogleGenerativeAI
            temp_client = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=temp,
                max_output_tokens=tokens,
            )
            
            response = temp_client.invoke(prompt)
            
            # Report success to rotation manager
            self.key_rotation_manager.mark_key_success(key_index)
            self.key_rotation_manager.update_key_usage(key_index, estimated_tokens, self.model_name)
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'content': content,
                'model': self.model_name,
                'temperature': temp,
                'max_tokens': tokens,
                'usage': {'estimated_tokens': estimated_tokens}
            }
            
        except Exception as e:
            # Report failure to rotation manager if we have a key index
            if 'key_index' in locals():
                self.key_rotation_manager.mark_key_failure(key_index, str(e))
                
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit error: {e}")
            raise ProviderError("gemini", f"Gemini completion failed: {e}")
            
    def generate(self, prompt: str, **kwargs) -> str:
        """Alias for complete method to match expected interface."""
        return self.complete(prompt)
        
    def batch_complete(self, prompts: List[str], max_concurrent: int = 1) -> List[str]:
        """Process multiple prompts with batch optimization.
        
        Args:
            prompts: List of prompts to process
            max_concurrent: Maximum concurrent requests (default: 1)
            
        Returns:
            List of generated completions
        """
        results = []
        
        # Process in batches to avoid overwhelming API
        for i, prompt in enumerate(prompts):
            logger.debug(f"Processing prompt {i+1}/{len(prompts)}")
            result = self.complete(prompt)
            results.append(result)
            
            # Small delay between requests to be nice to API
            if i < len(prompts) - 1:
                time.sleep(0.1)
                
        return results
        
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status from key rotation manager.
        
        Returns:
            Dict with rate limit information
        """
        return self.key_rotation_manager.get_status_summary()
