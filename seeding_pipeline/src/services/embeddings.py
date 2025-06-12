"""Direct embeddings service for text embedding generation.

This module now uses the Gemini embeddings implementation.
The original sentence-transformers implementation is preserved in embeddings_backup.py.
"""

from typing import Optional
import logging
import os

from src.services.embeddings_gemini import GeminiEmbeddingsService
logger = logging.getLogger(__name__)


def create_embeddings_service(api_key: Optional[str] = None, **kwargs):
    """Factory function to create embeddings service with API key from environment."""
    if api_key is None:
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
    
    # Remove any sentence-transformer specific kwargs
    gemini_kwargs = {}
    if 'batch_size' in kwargs:
        gemini_kwargs['batch_size'] = kwargs['batch_size']
    if 'model_name' in kwargs and 'gemini' in kwargs['model_name'].lower():
        gemini_kwargs['model_name'] = kwargs['model_name']
    
    return GeminiEmbeddingsService(api_key=api_key, **gemini_kwargs)


# Alias for backward compatibility
EmbeddingsService = GeminiEmbeddingsService

# Log the migration
logger.info("EmbeddingsService now uses GeminiEmbeddingsService implementation")