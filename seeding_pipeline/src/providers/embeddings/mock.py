"""Mock embedding provider for testing."""

import hashlib
import math
import random
from typing import List, Dict, Any

from src.providers.embeddings.base import BaseEmbeddingProvider
from src.core.plugin_discovery import provider_plugin


@provider_plugin('embedding', 'mock', version='1.0.0', author='Test', 
                description='Mock embedding provider for testing')
class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock embedding provider that generates deterministic embeddings for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock provider."""
        super().__init__(config)
        self.embedding_mode = config.get('mode', 'hash')  # hash, random, fixed
        self.fixed_value = config.get('fixed_value', 0.1)
        
    def _initialize_model(self) -> None:
        """No model initialization needed for mock provider."""
        pass
        
    def generate_embedding(self, text: str) -> List[float]:
        """Generate mock embedding for a single text."""
        self._ensure_initialized()
        
        if not text or not text.strip():
            return [0.0] * self.dimension
            
        if self.embedding_mode == 'fixed':
            # Fixed value embedding
            return [self.fixed_value] * self.dimension
            
        elif self.embedding_mode == 'random':
            # Random but deterministic based on text
            random.seed(hash(text) % 2**32)
            # Generate random values
            embedding = [random.gauss(0, 1) for _ in range(self.dimension)]
            # Normalize
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
            
        else:  # hash mode
            # Generate deterministic embedding based on text hash
            # This ensures same text always gets same embedding
            text_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Convert hash to numbers
            embedding = []
            for i in range(0, len(text_hash), 2):
                if len(embedding) >= self.dimension:
                    break
                # Convert hex pair to float in [-1, 1]
                hex_pair = text_hash[i:i+2]
                value = (int(hex_pair, 16) - 128) / 128.0
                embedding.append(value)
                
            # Pad with zeros if needed
            while len(embedding) < self.dimension:
                embedding.append(0.0)
                
            # Truncate if needed
            embedding = embedding[:self.dimension]
            
            # Normalize
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [v / norm for v in embedding]
                
            return embedding
            
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the mock model."""
        return {
            'model_name': f'mock-{self.embedding_mode}',
            'dimension': self.dimension,
            'mode': self.embedding_mode,
            'provider': 'Mock'
        }
        
    # Additional methods for testing
    
    def set_mode(self, mode: str) -> None:
        """Change embedding generation mode."""
        if mode in ['hash', 'random', 'fixed']:
            self.embedding_mode = mode
        else:
            raise ValueError(f"Invalid mode: {mode}")
            
    def reset(self) -> None:
        """Reset any internal state (no-op for mock)."""
        pass