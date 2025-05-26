"""
SentenceTransformer Adapter for Neo4j GraphRAG SimpleKGPipeline.

This adapter allows the existing SentenceTransformerProvider to work with neo4j-graphrag's
Embedder interface which expects embed_query and embed_documents methods.
"""

import logging
from typing import List, Dict, Any, Optional

from src.providers.embeddings.sentence_transformer import SentenceTransformerProvider

logger = logging.getLogger(__name__)


class SentenceTransformerGraphRAGAdapter:
    """
    Adapter class that makes SentenceTransformerProvider compatible with neo4j-graphrag's
    Embedder interface.
    
    The neo4j-graphrag library expects embedder objects to have:
    - embed_query(text: str) -> List[float]
    - embed_documents(texts: List[str]) -> List[List[float]]
    
    This adapter bridges our existing SentenceTransformerProvider with that interface.
    """
    
    def __init__(
        self, 
        sentence_transformer_provider: Optional[SentenceTransformerProvider] = None,
        **kwargs
    ):
        """
        Initialize the adapter with a SentenceTransformerProvider instance or config.
        
        Args:
            sentence_transformer_provider: Existing SentenceTransformerProvider instance
            **kwargs: Configuration parameters if creating new provider
        """
        if sentence_transformer_provider:
            self.provider = sentence_transformer_provider
        else:
            # Create new provider with provided config
            # Set defaults appropriate for GraphRAG usage
            config = kwargs.copy()
            config.setdefault('model_name', 'all-MiniLM-L6-v2')  # Fast, good quality
            config.setdefault('normalize_embeddings', True)  # For cosine similarity
            config.setdefault('device', 'cpu')  # Can be changed to 'cuda' if available
            
            self.provider = SentenceTransformerProvider(config)
        
        # Store model info for neo4j-graphrag compatibility
        self.model = self.provider.model_name
        self._dimension = None
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        Compatible with neo4j-graphrag's embedder interface.
        
        Args:
            text: Query text to embed
            
        Returns:
            List of floats representing the embedding
        """
        try:
            return self.provider.generate_embedding(text)
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise
    
    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        Compatible with neo4j-graphrag's embedder interface.
        
        Args:
            documents: List of document texts to embed
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        try:
            return self.provider.generate_embeddings(documents)
        except Exception as e:
            logger.error(f"Error generating document embeddings: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if self._dimension is None:
            # Ensure provider is initialized to get actual dimension
            self.provider._ensure_initialized()
            self._dimension = self.provider.dimension
        return self._dimension
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model.
        Alternative method name for compatibility.
        """
        return self.dimension
    
    # Additional compatibility methods
    
    async def aembed_query(self, text: str) -> List[float]:
        """Async version of embed_query for compatibility."""
        # For now, just wrap the sync version
        # In future, could implement true async support
        return self.embed_query(text)
    
    async def aembed_documents(self, documents: List[str]) -> List[List[float]]:
        """Async version of embed_documents for compatibility."""
        # For now, just wrap the sync version
        return self.embed_documents(documents)
    
    @property
    def supports_async(self) -> bool:
        """Indicate async support."""
        return True
    
    def __repr__(self) -> str:
        """String representation."""
        return f"SentenceTransformerGraphRAGAdapter(model={self.model})"
    
    # Pass through utility methods from provider
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        return self.provider.similarity(embedding1, embedding2)
    
    def find_most_similar(
        self, 
        query_embedding: List[float], 
        embeddings: List[List[float]], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find the most similar embeddings to a query embedding."""
        return self.provider.find_most_similar(query_embedding, embeddings, top_k)


# Convenience function to create adapter from config
def create_sentence_transformer_adapter(config: Dict[str, Any]) -> SentenceTransformerGraphRAGAdapter:
    """
    Create a SentenceTransformerGraphRAGAdapter from configuration.
    
    Args:
        config: Configuration dict with sentence transformer settings
        
    Returns:
        Configured SentenceTransformerGraphRAGAdapter instance
    """
    return SentenceTransformerGraphRAGAdapter(**config)