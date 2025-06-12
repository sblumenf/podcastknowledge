"""Service layer initialization and factory functions."""

from typing import Optional, Tuple
from pathlib import Path
import logging

from ..storage import GraphStorageService
from .embeddings import EmbeddingsService
from .embeddings_gemini import GeminiEmbeddingsService
from .llm import LLMService
from .llm_gemini_direct import GeminiDirectService
from .llm_factory import LLMServiceFactory, LLMServiceType
from .cache_manager import CacheManager
from .cached_prompt_service import CachedPromptService

logger = logging.getLogger(__name__)


def create_gemini_services(
    api_key: Optional[str] = None,
    llm_model: str = 'gemini-2.5-flash',
    embeddings_model: str = 'models/text-embedding-004',
    temperature: float = 0.7,
    max_tokens: int = 4096,
    embeddings_batch_size: int = 100,
    enable_cache: bool = True,
    cache_ttl: int = 3600
) -> Tuple[LLMService, GeminiEmbeddingsService]:
    """Create LLM and embeddings services.
    
    Args:
        api_key: Gemini API key (uses environment if not provided)
        llm_model: Model name for LLM service (default: gemini-2.5-flash)
        embeddings_model: Model name for embeddings (default: models/text-embedding-004)
        temperature: Generation temperature for LLM (default: 0.7)
        max_tokens: Maximum output tokens for LLM (default: 4096)
        embeddings_batch_size: Batch size for embeddings (default: 100)
        enable_cache: Enable response caching for LLM (default: True)
        cache_ttl: Cache time-to-live in seconds (default: 3600)
        
    Returns:
        Tuple of (LLMService, GeminiEmbeddingsService)
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    logger.info("Creating Gemini services")
    
    # Create LLM service using factory
    llm_service = LLMServiceFactory.create_service(
        api_key=api_key,
        model_name=llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )
    
    # Create embeddings service
    embeddings_service = GeminiEmbeddingsService(
        api_key=api_key,
        model_name=embeddings_model,
        batch_size=embeddings_batch_size
    )
    
    logger.info("Initialized LLM and embeddings services")
    
    return llm_service, embeddings_service


def create_llm_service_only(
    api_key: Optional[str] = None,
    model_name: str = 'gemini-2.5-flash',
    temperature: float = 0.7,
    max_tokens: int = 4096,
    enable_cache: bool = True,
    cache_ttl: int = 3600
) -> LLMService:
    """Create only the LLM service.
    
    Args:
        api_key: Gemini API key (uses environment if not provided)
        model_name: Model name for LLM service (default: gemini-2.5-flash)
        temperature: Generation temperature (default: 0.7)
        max_tokens: Maximum output tokens (default: 4096)
        enable_cache: Enable response caching (default: True)
        cache_ttl: Cache time-to-live in seconds (default: 3600)
        
    Returns:
        LLMService instance
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    return LLMServiceFactory.create_service(
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )


def create_embeddings_service_only(
    api_key: Optional[str] = None,
    model_name: str = 'models/text-embedding-004',
    batch_size: int = 100
) -> GeminiEmbeddingsService:
    """Create only the embeddings service.
    
    Args:
        api_key: Gemini API key (uses environment if not provided)
        model_name: Model name for embeddings (default: models/text-embedding-004)
        batch_size: Batch size for embeddings (default: 100)
        
    Returns:
        GeminiEmbeddingsService instance
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    return GeminiEmbeddingsService(
        api_key=api_key,
        model_name=model_name,
        batch_size=batch_size
    )


# Export all classes and factory functions
__all__ = [
    'LLMService',
    'GeminiDirectService',
    'LLMServiceFactory',
    'LLMServiceType',
    'CacheManager',
    'CachedPromptService',
    'GraphStorageService',
    'EmbeddingsService',
    'GeminiEmbeddingsService',
    'create_gemini_services',
    'create_llm_service_only',
    'create_embeddings_service_only'
]