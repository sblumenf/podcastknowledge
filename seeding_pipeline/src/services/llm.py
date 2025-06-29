"""Direct LLM service for Gemini API interaction."""

from typing import Dict, Any, Optional, List
import logging
import time
import hashlib
import json
from datetime import datetime

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.retry import ExponentialBackoff
from src.monitoring import get_pipeline_metrics
from src.utils.api_key import get_gemini_api_key

logger = logging.getLogger(__name__)


class LLMService:
    """Direct Gemini LLM service."""
    
    def __init__(self, api_key: Optional[str] = None,
                 model_name: str = 'gemini-1.5-flash', 
                 temperature: float = 0.7, max_tokens: int = 4096,
                 enable_cache: bool = True, cache_ttl: int = 3600):
        """Initialize LLM service.
        
        Args:
            api_key: Gemini API key (uses environment if not provided)
            model_name: Model to use (default: gemini-1.5-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
            enable_cache: Enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        self.api_key = api_key or get_gemini_api_key()
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        self._genai_client = None  # For direct Google GenAI SDK usage
        self.provider = "gemini"
        
        # Resilience features
        self.backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._response_cache = {} if enable_cache else None
        
    def _ensure_client(self) -> None:
        """Ensure the Gemini client is initialized."""
        if self.client is not None:
            return
            
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai is not installed. "
                "Install with: pip install google-genai"
            )
            
        self.client = genai.Client(api_key=self.api_key)
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
        """Generate completion.
        
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
            metrics.record_api_call(self.provider, method='complete', success=True, latency=0)
            return cached_response
        
        # Ensure client is initialized
        self._ensure_client()
        
        # Try with exponential backoff
        self.backoff.reset()
        last_exception = None
        
        for attempt in range(3):  # Max 3 attempts
            try:
                # Make the request using Google GenAI SDK
                from google.genai import types
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens
                    )
                )
                
                result = response.text
                if not result:
                    raise ProviderError(self.provider, "LLM returned empty response (None or empty string).")
                
                # Cache successful response
                self._cache_response(cache_key, result)
                
                # Record successful API call
                api_latency = time.time() - api_start_time
                metrics.record_api_call(self.provider, method='complete', success=True, latency=api_latency)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if it's a rate limit error
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    logger.warning(f"Rate limit hit on attempt {attempt + 1}")
                    raise RateLimitError("gemini", f"Gemini rate limit error: {e}")
                    
                # Other errors - retry with backoff
                if attempt < 2:
                    delay = self.backoff.get_next_delay()
                    logger.warning(f"API error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    time.sleep(delay)
                    
        # All retries failed
        logger.error(f"All API attempts failed: {last_exception}")
        
        # Record failed API call
        api_latency = time.time() - api_start_time
        metrics.record_api_call(self.provider, method='complete', success=False, latency=api_latency)
        
        raise ProviderError(self.provider, f"Gemini completion failed after all retries: {last_exception}")
            
    def complete_with_options(self, prompt: str, temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None, json_mode: bool = False) -> Dict[str, Any]:
        """Generate completion with custom options.
        
        Args:
            prompt: Input prompt text
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: Enable native JSON mode for structured output
            
        Returns:
            Dict with content and metadata
        """
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            if json_mode:
                # Use native JSON mode with Google GenAI SDK
                from google import genai
                from google.genai import types
                
                # Initialize client if needed
                if not hasattr(self, '_genai_client') or self._genai_client is None:
                    self._genai_client = genai.Client(api_key=self.api_key)
                
                # Create safety settings to disable content filtering
                safety_settings = [
                    types.SafetySetting(
                        category='HARM_CATEGORY_HATE_SPEECH',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_DANGEROUS_CONTENT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_HARASSMENT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_CIVIC_INTEGRITY',
                        threshold='BLOCK_NONE',
                    ),
                ]
                
                # Generate content with JSON mode
                response = self._genai_client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        temperature=temp,
                        max_output_tokens=tokens,
                        safety_settings=safety_settings
                    )
                )
                
                content = response.text
                if not content:
                    raise ProviderError(self.provider, "LLM returned empty response (None or empty string).")
            else:
                # Use Google GenAI SDK for non-JSON mode
                from google import genai
                from google.genai import types
                
                # Initialize client if needed
                if not hasattr(self, '_genai_client') or self._genai_client is None:
                    self._genai_client = genai.Client(api_key=self.api_key)
                
                # Create safety settings to disable content filtering
                safety_settings = [
                    types.SafetySetting(
                        category='HARM_CATEGORY_HATE_SPEECH',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_DANGEROUS_CONTENT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_HARASSMENT',
                        threshold='BLOCK_NONE',
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_CIVIC_INTEGRITY',
                        threshold='BLOCK_NONE',
                    ),
                ]
                
                response = self._genai_client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temp,
                        max_output_tokens=tokens,
                        safety_settings=safety_settings
                    )
                )
                
                content = response.text
                if not content:
                    raise ProviderError(self.provider, "LLM returned empty response (None or empty string).")
            
            return {
                'content': content,
                'model': self.model_name,
                'temperature': temp,
                'max_tokens': tokens,
                'json_mode': json_mode
            }
            
        except Exception as e:
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
    
    def generate_completion(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Any] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """Generate completion with structured output support.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            response_format: Pydantic model or schema for structured output
            temperature: Override default temperature
            
        Returns:
            Parsed response according to response_format, or string if no format
            
        Raises:
            ProviderError: If completion fails
        """
        # Build combined prompt
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt
            
        # Add JSON formatting instructions if response format provided
        if response_format:
            # Get JSON schema from Pydantic model
            if hasattr(response_format, 'model_json_schema'):
                schema = response_format.model_json_schema()
                full_prompt += f"\n\nReturn your response as valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            else:
                full_prompt += "\n\nReturn your response as valid JSON."
        
        # Get completion with JSON mode if response format specified
        temp = temperature if temperature is not None else self.temperature
        use_json_mode = response_format is not None
        result = self.complete_with_options(full_prompt, temperature=temp, json_mode=use_json_mode)
        content = result['content']
        
        # Parse response if format specified
        if response_format:
            try:
                # Parse JSON (no cleaning needed with native JSON mode)
                json_data = json.loads(content)
                
                # Validate with Pydantic model if provided
                if hasattr(response_format, 'model_validate'):
                    return response_format.model_validate(json_data)
                else:
                    return json_data
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}\nContent: {content}")
                raise ProviderError(self.provider, f"Invalid JSON response: {e}")
            except Exception as e:
                logger.error(f"Failed to validate response: {e}")
                raise ProviderError(self.provider, f"Response validation failed: {e}")
        
        return content
