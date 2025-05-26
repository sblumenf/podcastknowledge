"""Base embedding provider implementation."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import math

from src.core.interfaces import EmbeddingProvider, HealthCheckable


class BaseEmbeddingProvider(EmbeddingProvider, HealthCheckable, ABC):
    """Base implementation for embedding providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the embedding provider with configuration."""
        self.config = config
        self.model_name = config.get('model_name', 'unknown')
        self.dimension = config.get('dimension', 384)
        self.batch_size = config.get('batch_size', 32)
        self._initialized = False
        
    @abstractmethod
    def _initialize_model(self) -> None:
        """Initialize the underlying embedding model."""
        pass
        
    def _ensure_initialized(self) -> None:
        """Ensure the provider is initialized."""
        if not self._initialized:
            self._initialize_model()
            self._initialized = True
            
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass
        
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        self._ensure_initialized()
        
        # Default implementation: process one by one
        # Subclasses can override for batch processing
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
            
        return embeddings
        
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        pass
        
    def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        try:
            self._ensure_initialized()
            
            # Try to generate a test embedding
            test_text = "This is a test sentence."
            embedding = self.generate_embedding(test_text)
            
            return {
                'healthy': True,
                'provider': self.__class__.__name__,
                'model': self.model_name,
                'dimension': self.dimension,
                'test_embedding_size': len(embedding) if embedding else 0,
                'initialized': self._initialized
            }
        except Exception as e:
            return {
                'healthy': False,
                'provider': self.__class__.__name__,
                'model': self.model_name,
                'error': str(e),
                'initialized': self._initialized
            }
            
    # Utility methods
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimension")
            
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Calculate norms
        norm1 = math.sqrt(sum(x * x for x in embedding1))
        norm2 = math.sqrt(sum(x * x for x in embedding2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)
        
    def batch_similarity(self, embeddings1: List[List[float]], embeddings2: List[List[float]]) -> List[List[float]]:
        """Calculate pairwise cosine similarities between two sets of embeddings."""
        # Calculate similarity matrix
        similarity_matrix = []
        
        for emb1 in embeddings1:
            row = []
            for emb2 in embeddings2:
                sim = self.similarity(emb1, emb2)
                row.append(sim)
            similarity_matrix.append(row)
            
        return similarity_matrix
        
    def find_most_similar(
        self, 
        query_embedding: List[float], 
        embeddings: List[List[float]], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find the most similar embeddings to a query embedding."""
        # Calculate similarities
        similarities = []
        for i, embedding in enumerate(embeddings):
            sim = self.similarity(query_embedding, embedding)
            similarities.append({'index': i, 'similarity': sim})
            
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top k
        return similarities[:top_k]