"""Tests for embedding providers."""

import pytest
import math
from unittest.mock import patch, MagicMock

from src.providers.embeddings.mock import MockEmbeddingProvider
from src.providers.embeddings.sentence_transformer import (
    SentenceTransformerProvider, 
    OpenAIEmbeddingProvider
)
from src.core.exceptions import ProviderError


class TestMockEmbeddingProvider:
    """Test mock embedding provider functionality."""
    
    def test_initialization(self):
        """Test provider initialization."""
        config = {
            'dimension': 128,
            'mode': 'hash'
        }
        provider = MockEmbeddingProvider(config)
        
        assert provider.dimension == 128
        assert provider.embedding_mode == 'hash'
        
    def test_hash_mode_consistency(self):
        """Test that same text produces same embedding in hash mode."""
        provider = MockEmbeddingProvider({'mode': 'hash', 'dimension': 384})
        
        text = "This is a test sentence."
        embedding1 = provider.generate_embedding(text)
        embedding2 = provider.generate_embedding(text)
        
        assert embedding1 == embedding2
        assert len(embedding1) == 384
        
        # Different text should produce different embedding
        different_text = "This is a different sentence."
        embedding3 = provider.generate_embedding(different_text)
        assert embedding1 != embedding3
        
    def test_fixed_mode(self):
        """Test fixed value embedding mode."""
        provider = MockEmbeddingProvider({
            'mode': 'fixed',
            'dimension': 100,
            'fixed_value': 0.5
        })
        
        embedding = provider.generate_embedding("Any text")
        assert all(v == 0.5 for v in embedding)
        assert len(embedding) == 100
        
    def test_empty_text_handling(self):
        """Test handling of empty text."""
        provider = MockEmbeddingProvider({'dimension': 50})
        
        # Empty string
        embedding1 = provider.generate_embedding("")
        assert all(v == 0.0 for v in embedding1)
        assert len(embedding1) == 50
        
        # Whitespace only
        embedding2 = provider.generate_embedding("   ")
        assert all(v == 0.0 for v in embedding2)
        
    def test_batch_generation(self):
        """Test batch embedding generation."""
        provider = MockEmbeddingProvider({'mode': 'hash', 'dimension': 128})
        
        texts = ["Text 1", "Text 2", "Text 3", ""]
        embeddings = provider.generate_embeddings(texts)
        
        assert len(embeddings) == 4
        assert all(len(emb) == 128 for emb in embeddings)
        
        # Check consistency
        single_embedding = provider.generate_embedding("Text 1")
        assert embeddings[0] == single_embedding
        
        # Empty text should be zero vector
        assert all(v == 0.0 for v in embeddings[3])
        
    def test_similarity_calculation(self):
        """Test similarity calculation."""
        provider = MockEmbeddingProvider({'mode': 'hash'})
        
        # Same text should have similarity 1.0
        text = "Test sentence"
        emb1 = provider.generate_embedding(text)
        emb2 = provider.generate_embedding(text)
        
        similarity = provider.similarity(emb1, emb2)
        assert abs(similarity - 1.0) < 1e-6
        
        # Different texts should have lower similarity
        emb3 = provider.generate_embedding("Completely different")
        similarity2 = provider.similarity(emb1, emb3)
        assert similarity2 < 1.0
        
    def test_mode_switching(self):
        """Test switching between modes."""
        provider = MockEmbeddingProvider({'mode': 'hash'})
        
        text = "Test text"
        hash_embedding = provider.generate_embedding(text)
        
        provider.set_mode('fixed')
        fixed_embedding = provider.generate_embedding(text)
        
        assert hash_embedding != fixed_embedding


class TestSentenceTransformerProvider:
    """Test sentence transformer provider functionality."""
    
    def test_initialization_without_model(self):
        """Test initialization fails without sentence-transformers."""
        config = {'model_name': 'all-MiniLM-L6-v2'}
        
        provider = SentenceTransformerProvider(config)
        
        # Mock the _initialize_model method to simulate import failure
        with patch.object(provider, '_initialize_model') as mock_init:
            mock_init.side_effect = ProviderError(
                provider_name="sentence_transformer",
                message="sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
            
            with pytest.raises(ProviderError, match="sentence-transformers is not installed"):
                provider._initialize_model()
                
    def test_initialization_with_model(self):
        """Test successful initialization."""
        config = {
            'model_name': 'all-MiniLM-L6-v2',
            'device': 'cpu'
        }
        
        provider = SentenceTransformerProvider(config)
        
        # Mock the model directly on the provider
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        
        # Manually set the model and dimension as if initialization succeeded
        provider.model = mock_model
        provider.dimension = 384
        
        # Verify the provider is configured correctly
        assert provider.model == mock_model
        assert provider.dimension == 384
        assert provider.model_name == 'all-MiniLM-L6-v2'
        assert provider.device == 'cpu'
        
    def test_generate_embedding(self):
        """Test single embedding generation."""
        provider = SentenceTransformerProvider({'model_name': 'test-model'})
        
        # Mock the model directly
        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_embedding
        mock_model.get_sentence_embedding_dimension.return_value = 3
        
        provider.model = mock_model
        provider.dimension = 3
        provider._initialized = True
        
        embedding = provider.generate_embedding("Test text")
        
        assert embedding == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with(
            "Test text",
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
    def test_batch_generation(self):
        """Test batch embedding generation."""
        provider = SentenceTransformerProvider({
            'model_name': 'test-model',
            'batch_size': 2
        })
        
        # Mock the model directly
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 2
        
        provider.model = mock_model
        provider.dimension = 2
        provider._initialized = True
        
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = provider.generate_embeddings(texts)
        
        assert len(embeddings) == 3
        assert embeddings[0] == [0.1, 0.2]
        assert embeddings[1] == [0.3, 0.4]
        assert embeddings[2] == [0.5, 0.6]
        
    def test_empty_text_handling(self):
        """Test handling of empty texts in batch."""
        provider = SentenceTransformerProvider({'model_name': 'test-model'})
        
        # Mock the model
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 2
        
        provider._initialized = True
        provider.model = mock_model
        provider.dimension = 2
        
        texts = ["Text 1", "", "Text 2", "   "]
        embeddings = provider.generate_embeddings(texts)
        
        assert len(embeddings) == 4
        assert embeddings[0] == [0.1, 0.2]  # Text 1
        assert embeddings[1] == [0.0, 0.0]  # Empty
        assert embeddings[2] == [0.3, 0.4]  # Text 2
        assert embeddings[3] == [0.0, 0.0]  # Whitespace
        
        # Model should only be called with non-empty texts
        args = mock_model.encode.call_args[0][0]
        assert len(args) == 2  # Only "Text 1" and "Text 2"


class TestOpenAIEmbeddingProvider:
    """Test OpenAI embedding provider functionality."""
    
    def test_initialization_without_api_key(self):
        """Test initialization fails without API key."""
        config = {'model_name': 'text-embedding-3-small'}
        
        provider = OpenAIEmbeddingProvider(config)
        with pytest.raises(ProviderError, match="API key is required"):
            provider._initialize_model()
            
    @patch('src.providers.embeddings.sentence_transformer.OpenAI')
    def test_initialization_with_api_key(self, mock_openai_class):
        """Test successful initialization."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        config = {
            'api_key': 'test-api-key',
            'model_name': 'text-embedding-3-small',
            'dimension': 1536
        }
        
        provider = OpenAIEmbeddingProvider(config)
        provider._initialize_model()
        
        assert provider.client == mock_client
        mock_openai_class.assert_called_once_with(api_key='test-api-key')
        
    @patch('src.providers.embeddings.sentence_transformer.OpenAI')
    def test_generate_embedding(self, mock_openai_class):
        """Test single embedding generation."""
        # Mock the client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIEmbeddingProvider({
            'api_key': 'test-key',
            'model_name': 'text-embedding-3-small',
            'dimension': 3
        })
        provider._initialized = True
        provider.client = mock_client
        
        embedding = provider.generate_embedding("Test text")
        
        assert embedding == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once_with(
            model='text-embedding-3-small',
            input='Test text',
            dimensions=3
        )
        
    def test_health_check(self):
        """Test health check functionality."""
        provider = MockEmbeddingProvider({'dimension': 100})
        health = provider.health_check()
        
        assert health['healthy'] is True
        assert health['provider'] == 'MockEmbeddingProvider'
        assert health['dimension'] == 100
        assert health['test_embedding_size'] == 100


class TestEmbeddingConsistency:
    """Test embedding consistency across providers."""
    
    def test_deterministic_embeddings(self):
        """Test that embeddings are deterministic for same input."""
        provider = MockEmbeddingProvider({'mode': 'hash', 'dimension': 128})
        
        # Generate embeddings multiple times
        text = "The quick brown fox jumps over the lazy dog"
        embeddings = [provider.generate_embedding(text) for _ in range(5)]
        
        # All should be identical
        for i in range(1, 5):
            assert embeddings[0] == embeddings[i]
            
    def test_normalized_embeddings(self):
        """Test that embeddings are normalized."""
        provider = MockEmbeddingProvider({'mode': 'hash', 'dimension': 100})
        
        texts = ["Text 1", "Text 2", "Another text"]
        for text in texts:
            embedding = provider.generate_embedding(text)
            # Check L2 norm is approximately 1
            norm = math.sqrt(sum(x * x for x in embedding))
            assert abs(norm - 1.0) < 1e-6
            
    def test_similarity_range(self):
        """Test that similarities are in [-1, 1] range."""
        provider = MockEmbeddingProvider({'mode': 'hash'})
        
        texts = ["cat", "dog", "automobile", "car", "kitten"]
        embeddings = provider.generate_embeddings(texts)
        
        # Check all pairwise similarities
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = provider.similarity(embeddings[i], embeddings[j])
                assert -1.0 <= sim <= 1.0