"""Service layer initialization and factory functions."""

from typing import Optional, Tuple
from pathlib import Path
import logging

from ..storage import GraphStorageService
from .embeddings import EmbeddingsService
from .embeddings_gemini import GeminiEmbeddingsService
from .llm import LLMService
from src.utils.key_rotation_manager import create_key_rotation_manager
from src.utils.rotation_state_manager import RotationStateManager

logger = logging.getLogger(__name__)


def create_gemini_services(
    llm_model: str = 'gemini-2.5-flash',
    embeddings_model: str = 'models/text-embedding-004',
    temperature: float = 0.7,
    max_tokens: int = 4096,
    embeddings_batch_size: int = 100,
    enable_cache: bool = True,
    cache_ttl: int = 3600,
    state_dir: Optional[Path] = None
) -> Tuple[LLMService, GeminiEmbeddingsService]:
    """Create LLM and embeddings services with shared API key rotation.
    
    This factory function ensures both services share the same KeyRotationManager
    instance for coordinated quota tracking across all Gemini API calls.
    
    Args:
        llm_model: Model name for LLM service (default: gemini-2.5-flash)
        embeddings_model: Model name for embeddings (default: models/text-embedding-004)
        temperature: Generation temperature for LLM (default: 0.7)
        max_tokens: Maximum output tokens for LLM (default: 4096)
        embeddings_batch_size: Batch size for embeddings (default: 100)
        enable_cache: Enable response caching for LLM (default: True)
        cache_ttl: Cache time-to-live in seconds (default: 3600)
        state_dir: Directory for rotation state files (default: uses env or 'data')
        
    Returns:
        Tuple of (LLMService, GeminiEmbeddingsService)
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    # Ensure state persistence is configured
    if state_dir is None:
        state_dir = RotationStateManager.get_state_directory()
    
    if not RotationStateManager.ensure_state_persistence():
        logger.warning("Failed to ensure state persistence for API key rotation")
    
    # Create shared key rotation manager
    key_rotation_manager = create_key_rotation_manager(state_dir)
    
    if not key_rotation_manager:
        raise ValueError(
            "No API keys found in environment. Please set one of: "
            "GOOGLE_API_KEY, GEMINI_API_KEY, or GEMINI_API_KEY_1 through GEMINI_API_KEY_9"
        )
    
    logger.info(f"Creating Gemini services with {key_rotation_manager.get_status_summary()['total_keys']} API keys")
    
    # Create LLM service
    llm_service = LLMService(
        key_rotation_manager=key_rotation_manager,
        model_name=llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )
    
    # Create embeddings service with shared rotation manager
    embeddings_service = GeminiEmbeddingsService(
        key_rotation_manager=key_rotation_manager,
        model_name=embeddings_model,
        batch_size=embeddings_batch_size
    )
    
    logger.info("Initialized LLM and embeddings services with shared API key rotation")
    
    return llm_service, embeddings_service


def create_llm_service_only(
    model_name: str = 'gemini-2.5-flash',
    temperature: float = 0.7,
    max_tokens: int = 4096,
    enable_cache: bool = True,
    cache_ttl: int = 3600,
    state_dir: Optional[Path] = None
) -> LLMService:
    """Create only the LLM service with API key rotation.
    
    Args:
        model_name: Model name for LLM service (default: gemini-2.5-flash)
        temperature: Generation temperature (default: 0.7)
        max_tokens: Maximum output tokens (default: 4096)
        enable_cache: Enable response caching (default: True)
        cache_ttl: Cache time-to-live in seconds (default: 3600)
        state_dir: Directory for rotation state files (default: uses env or 'data')
        
    Returns:
        LLMService instance
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    key_rotation_manager = create_key_rotation_manager(state_dir)
    
    if not key_rotation_manager:
        raise ValueError(
            "No API keys found in environment. Please set one of: "
            "GOOGLE_API_KEY, GEMINI_API_KEY, or GEMINI_API_KEY_1 through GEMINI_API_KEY_9"
        )
    
    return LLMService(
        key_rotation_manager=key_rotation_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )


def create_embeddings_service_only(
    model_name: str = 'models/text-embedding-004',
    batch_size: int = 100,
    state_dir: Optional[Path] = None
) -> GeminiEmbeddingsService:
    """Create only the embeddings service with API key rotation.
    
    Args:
        model_name: Model name for embeddings (default: models/text-embedding-004)
        batch_size: Batch size for embeddings (default: 100)
        state_dir: Directory for rotation state files (default: uses env or 'data')
        
    Returns:
        GeminiEmbeddingsService instance
        
    Raises:
        ValueError: If no API keys are found in environment
    """
    key_rotation_manager = create_key_rotation_manager(state_dir)
    
    if not key_rotation_manager:
        raise ValueError(
            "No API keys found in environment. Please set one of: "
            "GOOGLE_API_KEY, GEMINI_API_KEY, or GEMINI_API_KEY_1 through GEMINI_API_KEY_9"
        )
    
    return GeminiEmbeddingsService(
        key_rotation_manager=key_rotation_manager,
        model_name=model_name,
        batch_size=batch_size
    )


# Export all classes and factory functions
__all__ = [
    'LLMService',
    'GraphStorageService',
    'EmbeddingsService',
    'GeminiEmbeddingsService',
    'create_gemini_services',
    'create_llm_service_only',
    'create_embeddings_service_only'
]