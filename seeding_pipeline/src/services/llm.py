"""Direct LLM service for Gemini API interaction with error resilience."""

from typing import Dict, Any, Optional, List
import logging
import time
import hashlib
import json
from datetime import datetime, timedelta
from functools import lru_cache

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.rate_limiting import WindowedRateLimiter
from src.utils.retry import ExponentialBackoff, CircuitState
from src.utils.metrics import get_pipeline_metrics

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for API calls."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before trying half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    def call_succeeded(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        
    def call_failed(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
    def can_attempt_call(self) -> bool:
        """Check if call can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            # Check if we should try half-open
            if self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker entering half-open state")
                    return True
                    
        return self.state == CircuitState.HALF_OPEN


class LLMService:
    """Direct Gemini LLM service with resilience features."""
    
    def __init__(self, api_key: str, model_name: str = 'gemini-2.5-flash', 
                 temperature: float = 0.7, max_tokens: int = 4096,
                 enable_cache: bool = True, cache_ttl: int = 3600):
        """Initialize LLM service with direct configuration.
        
        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
            enable_cache: Enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        if not api_key:
            raise ValueError("Gemini API key is required")
            
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        
        # Resilience features
        self.circuit_breaker = CircuitBreaker()
        self.backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._response_cache = {} if enable_cache else None
        
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
            
    def _fallback_extraction(self, prompt: str) -> str:
        """Pattern-based extraction fallback when API fails."""
        logger.info("Using pattern-based fallback extraction")
        
        # Simple pattern-based extraction for entities
        if "entities" in prompt.lower() or "extract" in prompt.lower():
            # Look for capitalized words as potential entities
            import re
            words = re.findall(r'\b[A-Z][a-z]+\b', prompt)
            entities = list(set(words))[:5]  # Limit to 5 entities
            
            return json.dumps({
                "entities": [{"name": e, "type": "UNKNOWN"} for e in entities],
                "source": "pattern_fallback"
            })
            
        # Default fallback
        return json.dumps({"error": "API unavailable", "source": "fallback"})

    def complete(self, prompt: str) -> str:
        """Generate completion with resilience features.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated completion text
            
        Raises:
            RateLimitError: If rate limits are exceeded
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
            
        # Check circuit breaker
        if not self.circuit_breaker.can_attempt_call():
            logger.warning("Circuit breaker is open, using fallback")
            return self._fallback_extraction(prompt)
        
        self._ensure_client()
        
        # Estimate tokens (rough approximation)
        estimated_tokens = len(prompt.split()) * 1.3
        
        # Check rate limits
        if not self.rate_limiter.can_make_request(self.model_name, estimated_tokens):
            logger.warning("Rate limit exceeded, using fallback")
            return self._fallback_extraction(prompt)
            
        # Try with exponential backoff
        self.backoff.reset()
        last_exception = None
        
        for attempt in range(3):  # Max 3 attempts
            try:
                # Make the request
                response = self.client.invoke(prompt)
                
                # Record successful request
                self.rate_limiter.record_request(self.model_name, estimated_tokens)
                self.circuit_breaker.call_succeeded()
                
                # Extract content from response
                if hasattr(response, 'content'):
                    result = response.content
                else:
                    result = str(response)
                    
                # Cache successful response
                self._cache_response(cache_key, result)
                
                # Record successful API call
                api_latency = time.time() - api_start_time
                metrics.record_api_call(self.provider, success=True, latency=api_latency)
                
                return result
                
            except Exception as e:
                last_exception = e
                self.rate_limiter.record_error(self.model_name, str(type(e).__name__))
                
                # Check if it's a rate limit error
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    if attempt == 0:  # First attempt, try backoff
                        delay = self.backoff.get_next_delay()
                        logger.warning(f"Rate limit hit, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.warning("Rate limit persists, using fallback")
                        self.circuit_breaker.call_failed()
                        return self._fallback_extraction(prompt)
                        
                # Other errors
                if attempt < 2:
                    delay = self.backoff.get_next_delay()
                    logger.warning(f"API error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    self.circuit_breaker.call_failed()
                    
        # All retries failed
        logger.error(f"All API attempts failed, using fallback")
        
        # Record failed API call
        api_latency = time.time() - api_start_time
        metrics.record_api_call(self.provider, success=False, latency=api_latency)
        
        return self._fallback_extraction(prompt)
            
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
        """Get current rate limit status.
        
        Returns:
            Dict with rate limit information
        """
        return self.rate_limiter.get_status()
