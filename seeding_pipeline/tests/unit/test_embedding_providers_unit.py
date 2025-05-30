"""Tests for embedding provider implementations."""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from src.providers.embeddings.base import EmbeddingProvider
from src.providers.embeddings.mock import MockEmbeddingProvider
from src.providers.embeddings.sentence_transformer import SentenceTransformerProvider
from src.providers.embeddings.sentence_transformer_adapter import SentenceTransformerGraphRAGAdapter


class TestMockEmbeddingProvider:
    """Test MockEmbeddingProvider implementation."""
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        provider = MockEmbeddingProvider()
        assert provider.name == "mock"
        assert provider.model_name == "mock-embeddings"
        assert provider.embedding_dim == 384
    
    def test_mock_provider_with_config(self):
        """Test mock provider with configuration."""
        config = {
            "embedding_dim": 768,
            "model_name": "mock-large",
            "normalize": True
        }
        
        provider = MockEmbeddingProvider(config)
        assert provider.embedding_dim == 768
        assert provider.model_name == "mock-large"
        assert provider.normalize is True
    
    def test_mock_provider_embed_single(self):
        """Test embedding single text."""
        provider = MockEmbeddingProvider({"embedding_dim": 128})
        
        text = "This is a test sentence"
        embedding = provider.embed(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 128
        assert all(isinstance(x, float) for x in embedding)
        assert all(-1 <= x <= 1 for x in embedding)
    
    def test_mock_provider_embed_batch(self):
        """Test batch embedding."""
        provider = MockEmbeddingProvider({"embedding_dim": 256})
        
        texts = [
            "First sentence",
            "Second sentence",
            "Third sentence"
        ]
        
        embeddings = provider.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == 256 for emb in embeddings)
        
        # Embeddings should be different for different texts
        assert embeddings[0] != embeddings[1]
        assert embeddings[1] != embeddings[2]
    
    def test_mock_provider_deterministic(self):
        """Test deterministic embeddings for same text."""
        provider = MockEmbeddingProvider({"seed": 42})
        
        text = "Test sentence"
        embedding1 = provider.embed(text)
        embedding2 = provider.embed(text)
        
        # Should be identical for same text
        assert embedding1 == embedding2
    
    def test_mock_provider_similarity(self):
        """Test embedding similarity calculation."""
        provider = MockEmbeddingProvider()
        
        # Similar texts should have higher similarity
        emb1 = provider.embed("The cat sat on the mat")
        emb2 = provider.embed("The cat sits on the mat")
        emb3 = provider.embed("The dog runs in the park")
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)
        
        # Similar sentences should have higher similarity
        assert sim_12 > sim_13
    
    def test_mock_provider_empty_text(self):
        """Test handling empty text."""
        provider = MockEmbeddingProvider()
        
        # Should handle empty string
        embedding = provider.embed("")
        assert isinstance(embedding, list)
        assert len(embedding) == provider.embedding_dim
    
    def test_mock_provider_health_check(self):
        """Test provider health check."""
        provider = MockEmbeddingProvider()
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "mock"
        assert health["model"] == "mock-embeddings"
        assert health["embedding_dim"] == 384


class TestSentenceTransformerProvider:
    """Test SentenceTransformerProvider implementation."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_initialization(self, mock_st_class):
        """Test SentenceTransformer provider initialization."""
        mock_model = MagicMock()
        mock_st_class.return_value = mock_model
        
        config = {"model_name": "all-MiniLM-L6-v2"}
        provider = SentenceTransformerProvider(config)
        
        mock_st_class.assert_called_once_with("all-MiniLM-L6-v2")
        assert provider.model_name == "all-MiniLM-L6-v2"
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_embed(self, mock_st_class):
        """Test SentenceTransformer embedding."""
        mock_model = MagicMock()
        mock_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        mock_model.encode.return_value = mock_embedding
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider()
        
        text = "Test sentence"
        embedding = provider.embed(text)
        
        assert isinstance(embedding, list)
        assert embedding == mock_embedding.tolist()
        mock_model.encode.assert_called_once_with(text, convert_to_tensor=False)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_embed_batch(self, mock_st_class):
        """Test SentenceTransformer batch embedding."""
        mock_model = MagicMock()
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        mock_model.encode.return_value = mock_embeddings
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider()
        
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = provider.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]
        assert embeddings[2] == [0.7, 0.8, 0.9]
        
        mock_model.encode.assert_called_once_with(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_tensor=False
        )
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_with_normalization(self, mock_st_class):
        """Test SentenceTransformer with normalization."""
        mock_model = MagicMock()
        mock_embedding = np.array([3.0, 4.0])  # Length = 5
        mock_model.encode.return_value = mock_embedding
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider({"normalize_embeddings": True})
        
        embedding = provider.embed("Test")
        
        # Should be normalized to unit length
        embedding_array = np.array(embedding)
        length = np.linalg.norm(embedding_array)
        assert abs(length - 1.0) < 0.001
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_error_handling(self, mock_st_class):
        """Test error handling in SentenceTransformer provider."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("Encoding failed")
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider()
        
        with pytest.raises(RuntimeError, match="Encoding failed"):
            provider.embed("Test text")
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_custom_pooling(self, mock_st_class):
        """Test SentenceTransformer with custom pooling."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.5, 0.5, 0.5])
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider({
            "model_name": "custom-model",
            "pooling_mode": "max"
        })
        
        embedding = provider.embed("Test")
        
        # Check encode was called with custom params
        call_kwargs = mock_model.encode.call_args[1]
        assert "convert_to_tensor" in call_kwargs
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_sentence_transformer_health_check(self, mock_st_class):
        """Test SentenceTransformer health check."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model
        
        provider = SentenceTransformerProvider()
        
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "sentence_transformer"
        assert health["embedding_dim"] == 384


class TestSentenceTransformerGraphRAGAdapter:
    """Test SentenceTransformerGraphRAGAdapter implementation."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_adapter_initialization(self, mock_st_class):
        """Test adapter initialization."""
        mock_model = MagicMock()
        mock_st_class.return_value = mock_model
        
        adapter = SentenceTransformerGraphRAGAdapter(model_name="adapter-model")
        
        assert adapter.model_name == "adapter-model"
        mock_st_class.assert_called_once_with("adapter-model")
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_adapter_interface_compatibility(self, mock_st_class):
        """Test adapter implements correct interface."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2])
        mock_st_class.return_value = mock_model
        
        adapter = SentenceTransformerGraphRAGAdapter()
        
        # Should implement EmbeddingProvider interface
        assert hasattr(adapter, 'embed')
        assert hasattr(adapter, 'embed_batch')
        assert hasattr(adapter, 'health_check')
        
        # Test methods work
        embedding = adapter.embed("Test")
        assert isinstance(embedding, list)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_adapter_caching(self, mock_st_class):
        """Test adapter with caching enabled."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.5, 0.5])
        mock_st_class.return_value = mock_model
        
        adapter = SentenceTransformerGraphRAGAdapter(enable_cache=True)
        
        # First call
        embedding1 = adapter.embed("Test text")
        assert mock_model.encode.call_count == 1
        
        # Second call with same text (should use cache)
        embedding2 = adapter.embed("Test text")
        assert mock_model.encode.call_count == 1  # Not called again
        assert embedding1 == embedding2
        
        # Different text
        embedding3 = adapter.embed("Different text")
        assert mock_model.encode.call_count == 2
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_adapter_preprocessing(self, mock_st_class):
        """Test adapter with text preprocessing."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2])
        mock_st_class.return_value = mock_model
        
        adapter = SentenceTransformerGraphRAGAdapter(
            preprocess_func=lambda x: x.lower().strip()
        )
        
        adapter.embed("  TEST TEXT  ")
        
        # Check preprocessing was applied
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == "test text"


class TestEmbeddingProviderIntegration:
    """Test embedding provider integration scenarios."""
    
    def test_provider_dimension_consistency(self):
        """Test embedding dimension consistency."""
        provider = MockEmbeddingProvider({"embedding_dim": 512})
        
        # Single embedding
        single = provider.embed("Test")
        assert len(single) == 512
        
        # Batch embeddings
        batch = provider.embed_batch(["Test1", "Test2", "Test3"])
        assert all(len(emb) == 512 for emb in batch)
    
    def test_provider_similarity_search(self):
        """Test using embeddings for similarity search."""
        provider = MockEmbeddingProvider({"embedding_dim": 128})
        
        # Create embeddings for documents
        documents = [
            "Machine learning is a subset of AI",
            "Deep learning uses neural networks",
            "Python is a programming language",
            "JavaScript is used for web development"
        ]
        
        doc_embeddings = provider.embed_batch(documents)
        
        # Query embedding
        query = "What is machine learning?"
        query_embedding = provider.embed(query)
        
        # Calculate similarities
        similarities = []
        for doc_emb in doc_embeddings:
            similarity = np.dot(query_embedding, doc_emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb)
            )
            similarities.append(similarity)
        
        # Most similar should be first document
        most_similar_idx = np.argmax(similarities)
        assert most_similar_idx == 0  # "Machine learning is a subset of AI"
    
    def test_provider_multilingual_support(self):
        """Test embedding multilingual text."""
        provider = MockEmbeddingProvider()
        
        texts = [
            "Hello world",  # English
            "Hola mundo",   # Spanish
            "Bonjour monde", # French
            "你好世界",      # Chinese
        ]
        
        embeddings = provider.embed_batch(texts)
        
        # All should produce valid embeddings
        assert len(embeddings) == 4
        assert all(len(emb) == provider.embedding_dim for emb in embeddings)
        
        # Different languages should have different embeddings
        assert embeddings[0] != embeddings[1]
        assert embeddings[1] != embeddings[2]
    
    def test_provider_edge_cases(self):
        """Test embedding edge cases."""
        provider = MockEmbeddingProvider()
        
        edge_cases = [
            "",  # Empty string
            " ",  # Whitespace
            "a",  # Single character
            "!" * 100,  # Repeated punctuation
            "word " * 1000,  # Very long text
        ]
        
        for text in edge_cases:
            embedding = provider.embed(text)
            assert isinstance(embedding, list)
            assert len(embedding) == provider.embedding_dim
            assert all(isinstance(x, float) for x in embedding)