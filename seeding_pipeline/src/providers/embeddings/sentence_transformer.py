"""Sentence Transformer embedding provider implementation."""

import logging
from typing import List, Dict, Any, Optional

from src.providers.embeddings.base import BaseEmbeddingProvider
from src.core.exceptions import ProviderError


logger = logging.getLogger(__name__)


class SentenceTransformerProvider(BaseEmbeddingProvider):
    """Embedding provider using sentence-transformers library."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize sentence transformer provider."""
        super().__init__(config)
        self.model = None
        self.normalize_embeddings = config.get('normalize_embeddings', True)
        self.device = config.get('device', 'cpu')
        
    def _initialize_model(self) -> None:
        """Initialize the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ProviderError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
            
        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            
            # Update dimension based on model
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                f"Initialized SentenceTransformer model: {self.model_name} "
                f"(dimension: {self.dimension}, device: {self.device})"
            )
            
        except Exception as e:
            raise ProviderError(f"Failed to initialize SentenceTransformer: {e}")
            
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        self._ensure_initialized()
        
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
            raise ProviderError(f"Embedding generation failed: {e}")
            
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (batch processing)."""
        self._ensure_initialized()
        
        if not texts:
            return []
            
        try:
            # Clean texts
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
            raise ProviderError(f"Batch embedding generation failed: {e}")
            
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        self._ensure_initialized()
        
        info = {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'device': self.device,
            'normalize_embeddings': self.normalize_embeddings,
            'max_seq_length': None
        }
        
        if self.model:
            try:
                info['max_seq_length'] = self.model.max_seq_length
            except:
                pass
                
        return info
        
    def encode_with_pooling(
        self, 
        texts: List[str], 
        pooling_strategy: str = 'mean'
    ) -> List[List[float]]:
        """
        Encode texts with custom pooling strategy.
        
        Args:
            texts: List of texts to encode
            pooling_strategy: 'mean', 'max', or 'cls'
            
        Returns:
            List of embeddings
        """
        self._ensure_initialized()
        
        if pooling_strategy not in ['mean', 'max', 'cls']:
            raise ValueError(f"Invalid pooling strategy: {pooling_strategy}")
            
        try:
            # For sentence-transformers, the pooling is handled internally
            # This is just a wrapper for compatibility
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False
            )
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Failed to encode with pooling: {e}")
            raise ProviderError(f"Encoding failed: {e}")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider using OpenAI's text-embedding models."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI embedding provider."""
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.client = None
        
        # OpenAI specific settings
        self.model_name = config.get('model_name', 'text-embedding-3-small')
        self.dimension = config.get('dimension', 1536)
        
    def _initialize_model(self) -> None:
        """Initialize the OpenAI client."""
        if not self.api_key:
            raise ProviderError("OpenAI API key is required")
            
        try:
            from openai import OpenAI
        except ImportError:
            raise ProviderError(
                "openai is not installed. "
                "Install with: pip install openai"
            )
            
        try:
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"Initialized OpenAI embedding client with model: {self.model_name}")
            
        except Exception as e:
            raise ProviderError(f"Failed to initialize OpenAI client: {e}")
            
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        self._ensure_initialized()
        
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension
            
        try:
            # Clean text
            text = text.replace("\n", " ").strip()
            
            # Generate embedding
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text,
                dimensions=self.dimension
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embedding: {e}")
            raise ProviderError(f"OpenAI embedding generation failed: {e}")
            
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        self._ensure_initialized()
        
        if not texts:
            return []
            
        try:
            # Clean texts and track empty ones
            cleaned_texts = []
            empty_indices = []
            
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    empty_indices.append(i)
                else:
                    cleaned_texts.append(text.replace("\n", " ").strip())
                    
            embeddings = []
            zero_vector = [0.0] * self.dimension
            
            if cleaned_texts:
                # OpenAI supports batch embedding
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=cleaned_texts,
                    dimensions=self.dimension
                )
                
                # Extract embeddings
                api_embeddings = [item.embedding for item in response.data]
                
                # Build result with zero vectors for empty texts
                api_idx = 0
                for i in range(len(texts)):
                    if i in empty_indices:
                        embeddings.append(zero_vector)
                    else:
                        embeddings.append(api_embeddings[api_idx])
                        api_idx += 1
            else:
                # All texts were empty
                embeddings = [zero_vector] * len(texts)
                
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate OpenAI batch embeddings: {e}")
            raise ProviderError(f"OpenAI batch embedding generation failed: {e}")
            
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        return {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'provider': 'OpenAI',
            'max_tokens': 8191  # For text-embedding-3 models
        }