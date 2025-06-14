"""
Optional Google generativeai dependency management.

This module provides fallbacks for the google-generativeai package
to ensure the application can run even when this package is not available.
"""

import logging
from typing import Any, List, Optional, Dict

logger = logging.getLogger(__name__)

# Try to import google.generativeai
try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False
    genai = None
    logger.warning("google-generativeai not available - Gemini embeddings disabled")


class MockGeminiEmbedding:
    """Mock embedding response for when Gemini is not available."""
    
    def __init__(self, values: List[float]):
        self.values = values


class MockGeminiModel:
    """Mock Gemini model for when google-generativeai is not available."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        logger.info(f"Using mock Gemini model: {model_name}")
    
    def embed_content(self, model: str, content: str, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return mock embeddings matching Gemini API response format."""
        # Return a 768-dimensional zero vector (typical embedding size)
        return {'embedding': [0.0] * 768}
    
    def embed_content_batch(self, texts: List[str], task_type: Optional[str] = None) -> List[MockGeminiEmbedding]:
        """Return mock embeddings for batch."""
        return [self.embed_content(text, task_type) for text in texts]


class MockGenAI:
    """Mock google.generativeai module."""
    
    @staticmethod
    def configure(api_key: str):
        """Mock configure method."""
        logger.debug(f"Mock Gemini configuration (API key length: {len(api_key)})")
    
    @staticmethod
    def GenerativeModel(model_name: str) -> MockGeminiModel:
        """Return mock model."""
        return MockGeminiModel(model_name)
    
    @staticmethod
    def embed_content(model: str, content: Any, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Mock embed_content matching Gemini API."""
        if isinstance(content, list):
            # Batch embedding
            return {'embedding': [[0.0] * 768 for _ in content]}
        else:
            # Single embedding
            return {'embedding': [0.0] * 768}


def get_genai():
    """Get google.generativeai module or mock if not available."""
    if GOOGLE_AI_AVAILABLE:
        return genai
    else:
        return MockGenAI()


def is_gemini_available() -> bool:
    """Check if Gemini API is available."""
    return GOOGLE_AI_AVAILABLE