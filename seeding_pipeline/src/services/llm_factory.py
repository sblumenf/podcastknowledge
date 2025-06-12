"""Factory for creating LLM services."""

import logging
import os
from typing import Union, Optional
from enum import Enum

from src.services.llm import LLMService
from src.services.llm_gemini_direct import GeminiDirectService
from src.services.cache_manager import CacheManager
from src.services.cached_prompt_service import CachedPromptService

logger = logging.getLogger(__name__)


class LLMServiceType(str, Enum):
    """Available LLM service implementations."""
    LANGCHAIN = "langchain"
    GEMINI_DIRECT = "gemini_direct"
    GEMINI_CACHED = "gemini_cached"


class LLMServiceFactory:
    """Factory for creating LLM service instances."""
    
    @staticmethod
    def create_service(
        api_key: Optional[str] = None,
        service_type: Optional[str] = None,
        model_name: str = 'gemini-2.5-flash',
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_cache: bool = True,
        cache_ttl: int = 3600,
        use_large_context: bool = True
    ) -> Union[LLMService, GeminiDirectService, CachedPromptService]:
        """Create an LLM service instance.
        
        Args:
            api_key: Gemini API key (uses environment if not provided)
            service_type: Type of service to create (defaults to env var or langchain)
            model_name: Model to use
            temperature: Generation temperature
            max_tokens: Maximum output tokens
            enable_cache: Enable response caching
            cache_ttl: Cache TTL in seconds
            use_large_context: Use large context prompts
            
        Returns:
            LLM service instance
        """
        # Determine service type
        if service_type is None:
            service_type = os.getenv('LLM_SERVICE_TYPE', LLMServiceType.LANGCHAIN)
        
        # Validate service type
        try:
            service_type = LLMServiceType(service_type)
        except ValueError:
            logger.warning(f"Invalid service type: {service_type}, defaulting to langchain")
            service_type = LLMServiceType.LANGCHAIN
            
        logger.info(f"Creating LLM service: {service_type}")
        
        # Convert model name for direct API if needed
        if service_type in [LLMServiceType.GEMINI_DIRECT, LLMServiceType.GEMINI_CACHED]:
            # Add version suffix for stable caching
            if model_name == 'gemini-2.5-flash' and '-001' not in model_name:
                model_name = 'gemini-2.5-flash-001'
            elif model_name == 'gemini-2.5-pro' and '-001' not in model_name:
                model_name = 'gemini-2.5-pro-001'
        
        # Create service based on type
        if service_type == LLMServiceType.LANGCHAIN:
            return LLMService(
                api_key=api_key,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_cache=enable_cache,
                cache_ttl=cache_ttl
            )
            
        elif service_type == LLMServiceType.GEMINI_DIRECT:
            return GeminiDirectService(
                api_key=api_key,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_cache=enable_cache,
                cache_ttl=cache_ttl
            )
            
        elif service_type == LLMServiceType.GEMINI_CACHED:
            # Create base service
            base_service = GeminiDirectService(
                api_key=api_key,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_cache=enable_cache,
                cache_ttl=cache_ttl
            )
            
            # Create cache manager
            cache_manager = CacheManager(default_ttl=cache_ttl)
            
            # Create cached prompt service
            cached_service = CachedPromptService(
                llm_service=base_service,
                cache_manager=cache_manager,
                use_large_context=use_large_context
            )
            
            # Warm prompt caches
            try:
                cached_service.warm_caches()
            except Exception as e:
                logger.warning(f"Failed to warm prompt caches: {e}")
            
            # Return the base service with cache manager attached
            base_service._cache_manager = cache_manager
            base_service._cached_prompt_service = cached_service
            
            return base_service
            
        else:
            raise ValueError(f"Unknown service type: {service_type}")
            
    @staticmethod
    def get_service_info(service_type: str) -> dict:
        """Get information about a service type.
        
        Args:
            service_type: Service type to get info for
            
        Returns:
            Dict with service information
        """
        info = {
            LLMServiceType.LANGCHAIN: {
                'name': 'LangChain LLM Service',
                'description': 'Original LangChain-based implementation',
                'features': ['API key rotation', 'Response caching', 'Retry logic'],
                'dependencies': ['langchain-google-genai'],
                'status': 'stable'
            },
            LLMServiceType.GEMINI_DIRECT: {
                'name': 'Gemini Direct Service',
                'description': 'Direct Gemini API implementation',
                'features': ['API key rotation', 'Response caching', 'Context caching', 'Lower latency'],
                'dependencies': ['google-genai'],
                'status': 'stable'
            },
            LLMServiceType.GEMINI_CACHED: {
                'name': 'Gemini Cached Service',
                'description': 'Direct API with prompt and context caching',
                'features': ['All Direct features', 'Prompt template caching', 'Episode caching', 'Cost optimization'],
                'dependencies': ['google-genai'],
                'status': 'experimental'
            }
        }
        
        return info.get(service_type, {'error': 'Unknown service type'})