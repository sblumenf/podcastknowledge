"""Direct Gemini API client with native prompt caching support."""

import logging
import time
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.retry import ExponentialBackoff
from src.utils.metrics import get_pipeline_metrics
from src.utils.api_key import get_gemini_api_key

logger = logging.getLogger(__name__)


class GeminiDirectService:
    """Direct Gemini API service with native caching support."""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model_name: str = 'gemini-2.5-flash-001',
                 temperature: float = 0.7,
                 max_tokens: int = 4096,
                 enable_cache: bool = True,
                 cache_ttl: int = 3600):
        """Initialize Gemini Direct service with caching support.
        
        Args:
            api_key: Gemini API key (uses environment if not provided)
            model_name: Model to use (default: gemini-2.5-flash-001)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
            enable_cache: Enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        self.api_key = api_key or get_gemini_api_key()
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider = "gemini"
        
        # Caching configuration
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._response_cache = {} if enable_cache else None
        self._context_cache = {}  # Store cached content references
        
        # Client will be initialized on first use
        self.client = None
        
        # Resilience features
        self.backoff = ExponentialBackoff(base=2.0, max_delay=60.0)
        
    def _ensure_client(self) -> None:
        """Ensure the Gemini client is initialized."""
        if self.client is not None:
            return
            
        try:
            from google import genai
            from google.genai.types import GenerateContentConfig
        except ImportError:
            raise ImportError(
                "google-genai is not installed. "
                "Install with: pip install google-genai>=1.0.0"
            )
            
        # Initialize client with API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Import types after client initialization
        global types
        from google.genai import types
        
        logger.debug(f"Initialized Gemini Direct client with model: {self.model_name}")
        
    def _get_cache_key(self, content: str, prefix: str = "response") -> str:
        """Generate cache key for content."""
        key_str = f"{prefix}_{content}_{self.temperature}_{self.model_name}"
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
            
    def create_cached_content(self, 
                            content: str, 
                            episode_id: str,
                            system_instruction: Optional[str] = None) -> Optional[str]:
        """Create cached content for episode transcript.
        
        Args:
            content: The transcript content to cache
            episode_id: Unique identifier for the episode
            system_instruction: Optional system instruction for the cache
            
        Returns:
            Cache name/ID if successful, None otherwise
        """
        if not self.enable_cache:
            return None
            
        cache_key = f"episode_{episode_id}"
        
        # Check if already cached
        if cache_key in self._context_cache:
            cached_info = self._context_cache[cache_key]
            # Check if still valid (within TTL)
            if (datetime.now() - cached_info['created']).total_seconds() < self.cache_ttl:
                logger.debug(f"Using existing cache for episode: {episode_id}")
                return cached_info['name']
            else:
                # Remove expired cache
                del self._context_cache[cache_key]
        
        try:
            # Ensure client is initialized
            self._ensure_client()
            
            # Prepare cache configuration
            cache_config = types.CreateCachedContentConfig(
                contents=[
                    types.Content(
                        role='user',
                        parts=[types.Part.from_text(content)]
                    )
                ],
                display_name=cache_key,
                ttl=f'{self.cache_ttl}s'
            )
            
            # Add system instruction if provided
            if system_instruction:
                cache_config.system_instruction = system_instruction
                
            # Create the cache
            cached_content = self.client.caches.create(
                model=self.model_name,
                config=cache_config
            )
            
            # Store cache reference
            self._context_cache[cache_key] = {
                'name': cached_content.name,
                'created': datetime.now()
            }
            
            logger.info(f"Created cache for episode {episode_id}: {cached_content.name}")
            return cached_content.name
            
        except Exception as e:
            logger.error(f"Failed to create cache for episode {episode_id}: {e}")
            return None
            
    def complete(self, prompt: str, cached_content_name: Optional[str] = None) -> str:
        """Generate completion with optional cached content.
        
        Args:
            prompt: Input prompt text
            cached_content_name: Optional name of cached content to use
            
        Returns:
            Generated completion text
            
        Raises:
            RateLimitError: If rate limits are exceeded
            ProviderError: If API call fails after all retries
        """
        # Get metrics instance
        metrics = get_pipeline_metrics()
        api_start_time = time.time()
        
        # Check response cache first
        cache_key = self._get_cache_key(prompt)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            metrics.record_api_call(self.provider, success=True, latency=0)
            return cached_response
        
        # Ensure client is initialized
        self._ensure_client()
        
        # Try with exponential backoff
        self.backoff.reset()
        last_exception = None
        
        for attempt in range(3):  # Max 3 attempts
            try:
                # Prepare generation config
                config_params = {
                    'temperature': self.temperature,
                    'max_output_tokens': self.max_tokens,
                }
                
                # Add cached content if provided
                if cached_content_name:
                    config_params['cached_content'] = cached_content_name
                    
                config = types.GenerateContentConfig(**config_params)
                
                # Make the request
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                
                # Extract text from response
                result = response.text
                
                # Cache successful response
                self._cache_response(cache_key, result)
                
                # Record metrics
                api_latency = time.time() - api_start_time
                metrics.record_api_call(self.provider, success=True, latency=api_latency)
                
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
        metrics.record_api_call(self.provider, success=False, latency=api_latency)
        
        raise ProviderError(self.provider, f"Gemini completion failed after all retries: {last_exception}")
        
    def complete_with_options(self, 
                            prompt: str, 
                            temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None,
                            cached_content_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate completion with custom options.
        
        Args:
            prompt: Input prompt text
            temperature: Override default temperature
            max_tokens: Override default max tokens
            cached_content_name: Optional name of cached content to use
            
        Returns:
            Dict with content and metadata
        """
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Ensure client is initialized
        self._ensure_client()
        
        try:
            # Prepare generation config
            config_params = {
                'temperature': temp,
                'max_output_tokens': tokens,
            }
            
            if cached_content_name:
                config_params['cached_content'] = cached_content_name
                
            config = types.GenerateContentConfig(**config_params)
            
            # Make the request
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            return {
                'content': response.text,
                'model': self.model_name,
                'temperature': temp,
                'max_tokens': tokens,
                'cached_content': cached_content_name
            }
            
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit error: {e}")
            raise ProviderError("gemini", f"Gemini completion failed: {e}")
            
    def generate(self, prompt: str, **kwargs) -> str:
        """Alias for complete method to match expected interface."""
        cached_content_name = kwargs.get('cached_content_name')
        return self.complete(prompt, cached_content_name)
        
    def batch_complete(self, 
                      prompts: List[str], 
                      cached_content_name: Optional[str] = None,
                      max_concurrent: int = 1) -> List[str]:
        """Process multiple prompts with batch optimization.
        
        Args:
            prompts: List of prompts to process
            cached_content_name: Optional cached content to use for all prompts
            max_concurrent: Maximum concurrent requests (default: 1)
            
        Returns:
            List of generated completions
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            logger.debug(f"Processing prompt {i+1}/{len(prompts)}")
            result = self.complete(prompt, cached_content_name)
            results.append(result)
            
            # Small delay between requests
            if i < len(prompts) - 1:
                time.sleep(0.1)
                
        return results
        
    def generate_completion(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Any] = None,
        temperature: Optional[float] = None,
        cached_content_name: Optional[str] = None
    ) -> Any:
        """Generate completion with structured output support.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            response_format: Pydantic model or schema for structured output
            temperature: Override default temperature
            cached_content_name: Optional cached content to use
            
        Returns:
            Parsed response according to response_format, or string if no format
            
        Raises:
            ProviderError: If completion fails
        """
        import json
        
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
        
        # Get completion
        temp = temperature if temperature is not None else self.temperature
        result = self.complete_with_options(
            full_prompt, 
            temperature=temp, 
            cached_content_name=cached_content_name
        )
        content = result['content']
        
        # Parse response if format specified
        if response_format:
            try:
                # Clean up response - Gemini sometimes adds markdown code blocks
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.startswith("```"):
                    content = content[3:]  # Remove ```
                if content.endswith("```"):
                    content = content[:-3]  # Remove ```
                content = content.strip()
                
                # Parse JSON
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
        
    def get_cached_content_info(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get information about cached content for an episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Dict with cache info or None if not cached
        """
        cache_key = f"episode_{episode_id}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
        return None
        
    def clear_expired_caches(self):
        """Clear expired caches from memory."""
        now = datetime.now()
        
        # Clear expired response caches
        if self._response_cache:
            expired_keys = [
                key for key, value in self._response_cache.items()
                if (now - value['timestamp']).total_seconds() >= self.cache_ttl
            ]
            for key in expired_keys:
                del self._response_cache[key]
                
        # Clear expired context caches
        expired_contexts = [
            key for key, value in self._context_cache.items()
            if (now - value['created']).total_seconds() >= self.cache_ttl
        ]
        for key in expired_contexts:
            del self._context_cache[key]
            
        if expired_keys or expired_contexts:
            logger.info(f"Cleared {len(expired_keys)} response caches and {len(expired_contexts)} context caches")