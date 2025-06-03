"""Gemini embeddings service for text embedding generation using Google's API."""

from typing import List, Dict, Any, Optional, Tuple
import logging

import numpy as np
import google.generativeai as genai

from src.core.exceptions import ProviderError, RateLimitError
from src.utils.rate_limiting import WindowedRateLimiter

logger = logging.getLogger(__name__)


class GeminiEmbeddingsService:
    """Gemini API-based embeddings service using text-embedding-004."""
    
    def __init__(self, api_key: str, model_name: str = 'models/text-embedding-004',
                 batch_size: int = 100):
        """Initialize Gemini embeddings service.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Embedding model name (default: models/text-embedding-004)
            batch_size: Batch size for processing multiple texts
        """
        if not api_key:
            raise ValueError("Gemini API key is required")
            
        self.api_key = api_key
        self.model_name = model_name
        self.batch_size = batch_size
        self.dimension = 768  # text-embedding-004 dimension
        self._configured = False
        
        # Set up rate limiter with Gemini-specific limits
        self.rate_limiter = WindowedRateLimiter({
            'text-embedding-004': {
                'rpm': 1500,      # Requests per minute
                'tpm': 4000000,   # Tokens per minute (characters)
                'rpd': 1500000    # Requests per day
            },
            'default': {
                'rpm': 1000,
                'tpm': 2000000,
                'rpd': 1000000
            }
        })
        
        logger.info(f"Initialized GeminiEmbeddingsService with model: {self.model_name}")
        
    def _ensure_configured(self) -> None:
        """Ensure the Gemini API is configured."""
        if not self._configured:
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
        self._ensure_configured()
        
        # Handle empty text
        if not text or not text.strip():
            logger.debug("Empty text provided, returning zero vector")
            return [0.0] * self.dimension
            
        # Clean text
        cleaned_text = text.replace("\n", " ").strip()
        
        # Estimate tokens (characters for Gemini)
        estimated_tokens = len(cleaned_text)
        
        # Check rate limits
        model_key = 'text-embedding-004' if 'text-embedding-004' in self.model_name else 'default'
        if not self.rate_limiter.can_make_request(model_key, estimated_tokens):
            raise RateLimitError(
                f"Rate limit exceeded for model {self.model_name}. "
                "Please wait before making another request."
            )
            
        try:
            # Generate embedding
            response = genai.embed_content(
                model=self.model_name,
                content=cleaned_text,
                task_type="retrieval_document"
            )
            
            # Record successful request
            self.rate_limiter.record_request(model_key, estimated_tokens)
            
            # Extract embedding
            if 'embedding' in response:
                return response['embedding']
            else:
                raise ValueError("No embedding in response")
                
        except Exception as e:
            self.rate_limiter.record_error(model_key, str(type(e).__name__))
            
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate" in error_msg or "resource exhausted" in error_msg:
                raise RateLimitError(f"Gemini rate limit error: {e}")
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
        self._ensure_configured()
        
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
                # Estimate tokens
                estimated_tokens = sum(len(t) for t in non_empty_texts)
                
                # Check rate limits
                model_key = 'text-embedding-004' if 'text-embedding-004' in self.model_name else 'default'
                if not self.rate_limiter.can_make_request(model_key, estimated_tokens):
                    raise RateLimitError(
                        f"Rate limit exceeded for model {self.model_name}. "
                        "Please wait before making another request."
                    )
                    
                try:
                    # Generate embeddings for non-empty texts
                    response = genai.embed_content(
                        model=self.model_name,
                        content=non_empty_texts,
                        task_type="retrieval_document"
                    )
                    
                    # Record successful request
                    self.rate_limiter.record_request(model_key, estimated_tokens)
                    
                    # Extract embeddings
                    if 'embedding' in response:
                        batch_embeddings = response['embedding']
                        # Handle single embedding response
                        if isinstance(batch_embeddings[0], float):
                            batch_embeddings = [batch_embeddings]
                    else:
                        raise ValueError("No embeddings in response")
                        
                except Exception as e:
                    self.rate_limiter.record_error(model_key, str(type(e).__name__))
                    
                    error_msg = str(e).lower()
                    if "quota" in error_msg or "rate" in error_msg or "resource exhausted" in error_msg:
                        raise RateLimitError(f"Gemini rate limit error: {e}")
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
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return float(dot_product / (norm1 * norm2))
        
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
        """Get current rate limit status.
        
        Returns:
            Dict with rate limit information
        """
        return self.rate_limiter.get_status()