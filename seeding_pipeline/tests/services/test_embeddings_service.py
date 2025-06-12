"""Tests for embeddings service implementation."""

from unittest.mock import Mock, patch, MagicMock

import numpy as np
import pytest

from src.services.embeddings import EmbeddingsService
class TestEmbeddingsService:
    """Test suite for EmbeddingsService."""
    
    @pytest.fixture
    def service(self):
        """Create embeddings service instance."""
        with patch('src.services.embeddings.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_st.return_value = mock_model
            service = EmbeddingsService(model_name="test-model")
            service.model = mock_model
            return service
    
    def test_initialization(self):
        """Test service initialization."""
        with patch('src.services.embeddings.SentenceTransformer') as mock_st:
            service = EmbeddingsService(model_name="all-MiniLM-L6-v2")
            mock_st.assert_called_once_with("all-MiniLM-L6-v2")
            assert service.model_name == "all-MiniLM-L6-v2"
    
    def test_initialization_default_model(self):
        """Test initialization with default model."""
        with patch('src.services.embeddings.SentenceTransformer') as mock_st:
            service = EmbeddingsService()
            mock_st.assert_called_once_with("sentence-transformers/all-mpnet-base-v2")
    
    def test_embed_single_text(self, service):
        """Test embedding single text."""
        # Mock encode to return numpy array
        expected_embedding = np.array([0.1, 0.2, 0.3])
        service.model.encode.return_value = expected_embedding
        
        result = service.embed("Test text")
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert result == [0.1, 0.2, 0.3]
        service.model.encode.assert_called_once_with("Test text", convert_to_numpy=True)
    
    def test_embed_batch(self, service):
        """Test batch embedding."""
        texts = ["Text 1", "Text 2", "Text 3"]
        expected_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        service.model.encode.return_value = expected_embeddings
        
        results = service.embed_batch(texts)
        
        assert len(results) == 3
        assert all(isinstance(emb, list) for emb in results)
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[2] == [0.7, 0.8, 0.9]
        service.model.encode.assert_called_once_with(texts, convert_to_numpy=True)
    
    def test_calculate_similarity(self, service):
        """Test similarity calculation."""
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0]
        emb3 = [1.0, 0.0, 0.0]
        
        # Orthogonal vectors should have similarity near 0
        sim1 = service.calculate_similarity(emb1, emb2)
        assert -0.1 < sim1 < 0.1
        
        # Same vectors should have similarity 1
        sim2 = service.calculate_similarity(emb1, emb3)
        assert 0.99 < sim2 <= 1.0
    
    def test_empty_text_handling(self, service):
        """Test handling of empty text."""
        service.model.encode.return_value = np.array([0.0] * 768)
        
        result = service.embed("")
        assert isinstance(result, list)
        assert all(v == 0.0 for v in result)
    
    def test_error_handling(self, service):
        """Test error handling."""
        service.model.encode.side_effect = Exception("Model error")
        
        with pytest.raises(Exception, match="Model error"):
            service.embed("Test text")