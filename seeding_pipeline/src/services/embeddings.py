"""Direct embeddings service for text embedding generation."""

from typing import List, Dict, Any, Optional, Tuple
import logging

from src.core.exceptions import ProviderError
logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Direct sentence transformer embeddings service."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', 
                 device: str = 'cpu', batch_size: int = 32,
                 normalize_embeddings: bool = True):
        """Initialize embeddings service.
        
        Args:
            model_name: Sentence transformer model name (default: all-MiniLM-L6-v2)
            device: Device to run on (cpu or cuda)
            batch_size: Batch size for processing multiple texts
            normalize_embeddings: Whether to normalize embeddings
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.model = None
        self.dimension = None
        
    def _ensure_model(self) -> None:
        """Ensure the sentence transformer model is loaded."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Install with: pip install sentence-transformers"
                )
                
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            
            # Get embedding dimension
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                f"Initialized SentenceTransformer model: {self.model_name} "
                f"(dimension: {self.dimension}, device: {self.device})"
            )
            
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        self._ensure_model()
        
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension
            
        try:
            # Clean text
            text = text.replace("\n", " ").strip()
            
            # Generate embedding
            embedding = self.model.encode(
                text,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise ProviderError("embeddings", f"Embedding generation failed: {e}")
            
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        self._ensure_model()
        
        if not texts:
            return []
            
        try:
            # Clean texts and track empty ones
            cleaned_texts = []
            empty_indices = []
            
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    empty_indices.append(i)
                    cleaned_texts.append("")  # Placeholder
                else:
                    cleaned_texts.append(text.replace("\n", " ").strip())
                    
            # Generate embeddings for non-empty texts
            non_empty_texts = [t for t in cleaned_texts if t]
            
            if non_empty_texts:
                embeddings = self.model.encode(
                    non_empty_texts,
                    batch_size=self.batch_size,
                    normalize_embeddings=self.normalize_embeddings,
                    show_progress_bar=False
                )
                embeddings_list = embeddings.tolist()
            else:
                embeddings_list = []
                
            # Build result with zero vectors for empty texts
            result = []
            embedding_idx = 0
            zero_vector = [0.0] * self.dimension
            
            for i, text in enumerate(cleaned_texts):
                if i in empty_indices:
                    result.append(zero_vector)
                else:
                    result.append(embeddings_list[embedding_idx])
                    embedding_idx += 1
                    
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise ProviderError("embeddings", f"Batch embedding generation failed: {e}")
            
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model.
        
        Returns:
            Model information dictionary
        """
        self._ensure_model()
        
        info = {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'device': self.device,
            'normalize_embeddings': self.normalize_embeddings,
            'batch_size': self.batch_size,
            'max_seq_length': None
        }
        
        if self.model:
            try:
                info['max_seq_length'] = self.model.max_seq_length
            except:
                pass
                
        return info
        
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        import numpy as np
        
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
            List of (index, similarity_score) tuples
        """
        similarities = []
        
        for i, embedding in enumerate(embeddings):
            similarity = self.compute_similarity(query_embedding, embedding)
            similarities.append((i, similarity))
            
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
