"""Unified embeddings service for text embedding generation.

This module provides the Gemini embeddings implementation directly.
Sentence-transformers implementation has been removed as it's not used.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import os

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.api_key import get_gemini_api_key
from src.core.dependencies import get_dependency, is_available, GOOGLE_AI_AVAILABLE, HAS_NUMPY

# Make numpy optional
if HAS_NUMPY:
    import numpy as np
else:
    np = None

logger = logging.getLogger(__name__)


class GeminiEmbeddingsService:
    """Gemini API-based embeddings service using text-embedding-004."""
    
    def __init__(self, api_key: Optional[str] = None,
                 model_name: str = 'models/text-embedding-004',
                 batch_size: int = 100):
        """Initialize Gemini embeddings service.
        
        Args:
            api_key: Gemini API key (uses environment if not provided)
            model_name: Embedding model name (default: models/text-embedding-004)
            batch_size: Batch size for processing multiple texts
        """
        self.api_key = api_key or get_gemini_api_key()
        self.model_name = model_name
        self.batch_size = batch_size
        self.dimension = 768  # text-embedding-004 dimension
        self._configured = False
        
        # Log availability status
        if not GOOGLE_AI_AVAILABLE:
            logger.warning("google-generativeai not available - using mock embeddings")
        if not HAS_NUMPY:
            logger.warning("numpy not available - using pure Python for similarity calculations")
            
        logger.info(f"Initialized GeminiEmbeddingsService with model: {self.model_name}")
        
    def _ensure_configured(self) -> None:
        """Ensure the Gemini API is configured."""
        if not self._configured:
            genai = get_dependency('google.generativeai')
            genai.configure(api_key=self.api_key)
            self._configured = True
            
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
            
        Raises:
            RateLimitError: If rate limits are exceeded
            ProviderError: If API call fails
        """
        # Handle empty text
        if not text or not text.strip():
            logger.debug("Empty text provided, returning zero vector")
            return [0.0] * self.dimension
            
        # Clean text
        cleaned_text = text.replace("\n", " ").strip()
        
        try:
            # Configure API
            self._ensure_configured()
            
            # Generate embedding
            genai = get_dependency('google.generativeai')
            response = genai.embed_content(
                model=self.model_name,
                content=cleaned_text,
                task_type="retrieval_document"
            )
            
            # Extract embedding
            if 'embedding' in response:
                return response['embedding']
            else:
                raise ValueError("No embedding in response")
                
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate" in error_msg or "resource exhausted" in error_msg:
                raise RateLimitError("gemini", f"Gemini rate limit error: {e}")
            elif "invalid" in error_msg or "not found" in error_msg:
                raise ProviderError("gemini", f"Invalid request: {e}")
            else:
                raise ProviderError("gemini", f"Gemini embedding failed: {e}")
                
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
            
        Raises:
            RateLimitError: If rate limits are exceeded
            ProviderError: If API call fails
        """
        if not texts:
            return []
            
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # Clean texts and track empty ones
            cleaned_batch = []
            empty_indices = []
            
            for j, text in enumerate(batch):
                if not text or not text.strip():
                    empty_indices.append(j)
                    cleaned_batch.append("")  # Placeholder
                else:
                    cleaned_batch.append(text.replace("\n", " ").strip())
                    
            # Filter out empty texts for API call
            non_empty_texts = [t for t in cleaned_batch if t]
            
            if non_empty_texts:
                try:
                    # Configure API
                    self._ensure_configured()
                    
                    # Generate embeddings for non-empty texts
                    genai = get_dependency('google.generativeai')
                    response = genai.embed_content(
                        model=self.model_name,
                        content=non_empty_texts,
                        task_type="retrieval_document"
                    )
                    
                    # Extract embeddings
                    if 'embedding' in response:
                        batch_embeddings = response['embedding']
                        # Handle single embedding response
                        if isinstance(batch_embeddings[0], float):
                            batch_embeddings = [batch_embeddings]
                    else:
                        raise ValueError("No embeddings in response")
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    if "quota" in error_msg or "rate" in error_msg or "resource exhausted" in error_msg:
                        raise RateLimitError("gemini", f"Gemini rate limit error: {e}")
                    else:
                        raise ProviderError("gemini", f"Gemini batch embedding failed: {e}")
            else:
                batch_embeddings = []
                
            # Reconstruct full batch with zero vectors for empty texts
            batch_results = []
            embedding_idx = 0
            zero_vector = [0.0] * self.dimension
            
            for j in range(len(batch)):
                if j in empty_indices:
                    batch_results.append(zero_vector)
                else:
                    batch_results.append(batch_embeddings[embedding_idx])
                    embedding_idx += 1
                    
            embeddings.extend(batch_results)
            
        return embeddings
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model.
        
        Returns:
            Model information dictionary
        """
        return {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'api_based': True,
            'batch_size': self.batch_size,
            'rate_limits': {
                'requests_per_minute': 1500,
                'tokens_per_minute': 4000000,
                'requests_per_day': 1500000
            }
        }
        
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if HAS_NUMPY:
            # Use numpy for efficient computation
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return float(dot_product / (norm1 * norm2))
        else:
            # Pure Python implementation
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = sum(a * a for a in embedding1) ** 0.5
            norm2 = sum(b * b for b in embedding2) ** 0.5
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return dot_product / (norm1 * norm2)
        
    def find_similar(self, query_embedding: List[float], 
                    embeddings: List[List[float]], 
                    top_k: int = 5) -> List[Tuple[int, float]]:
        """Find most similar embeddings to a query.
        
        Args:
            query_embedding: Query embedding vector
            embeddings: List of embeddings to search
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples sorted by similarity
        """
        similarities = []
        
        for i, embedding in enumerate(embeddings):
            similarity = self.compute_similarity(query_embedding, embedding)
            similarities.append((i, similarity))
            
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
        
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status from key rotation manager.
        
        Returns:
            Dict with rate limit information
        """
        # Key rotation manager not implemented yet
        return {
            'status': 'active',
            'requests_remaining': 'unknown',
            'reset_time': 'unknown'
        }


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


# Alias for convenience
EmbeddingsService = GeminiEmbeddingsService

# Log the consolidation
logger.info("EmbeddingsService consolidated - using GeminiEmbeddingsService implementation")