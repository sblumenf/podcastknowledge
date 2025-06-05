"""Comprehensive unit tests for Gemini embeddings service module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from typing import List

from src.services.embeddings_gemini import GeminiEmbeddingsService
from src.core.exceptions import ProviderError, RateLimitError
from src.utils.rate_limiting import WindowedRateLimiter


class TestGeminiEmbeddingsService:
    """Test GeminiEmbeddingsService functionality."""
    
    @pytest.fixture
    def embeddings_service(self):
        """Create embeddings service instance."""
        return GeminiEmbeddingsService(
            api_key="test_api_key",
            model_name="models/text-embedding-004",
            batch_size=100
        )
    
    def test_initialization_success(self):
        """Test successful service initialization."""
        service = GeminiEmbeddingsService(
            api_key="test_key",
            model_name="models/custom-embedding",
            batch_size=50
        )
        
        assert service.api_key == "test_key"
        assert service.model_name == "models/custom-embedding"
        assert service.batch_size == 50
        assert service.dimension == 768
        assert service._configured is False
        assert isinstance(service.rate_limiter, WindowedRateLimiter)
    
    def test_initialization_no_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="Gemini API key is required"):
            GeminiEmbeddingsService(api_key="")
    
    def test_rate_limiter_configuration(self, embeddings_service):
        """Test rate limiter is configured correctly."""
        limits = embeddings_service.rate_limiter.limits
        
        assert 'text-embedding-004' in limits
        assert limits['text-embedding-004']['rpm'] == 1500
        assert limits['text-embedding-004']['tpm'] == 4000000
        assert limits['text-embedding-004']['rpd'] == 1500000
        
        assert 'default' in limits
    
    @patch('src.services.embeddings_gemini.genai')
    def test_ensure_configured(self, mock_genai, embeddings_service):
        """Test API configuration."""
        embeddings_service._ensure_configured()
        
        assert embeddings_service._configured is True
        mock_genai.configure.assert_called_once_with(api_key="test_api_key")
        
        # Should not configure again
        embeddings_service._ensure_configured()
        mock_genai.configure.assert_called_once()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_success(self, mock_genai, embeddings_service):
        """Test successful single embedding generation."""
        mock_response = {'embedding': [0.1, 0.2, 0.3] + [0.0] * 765}  # 768 dimensions
        mock_genai.embed_content.return_value = mock_response
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        result = embeddings_service.generate_embedding("Test text")
        
        assert result == mock_response['embedding']
        mock_genai.embed_content.assert_called_once_with(
            model="models/text-embedding-004",
            content="Test text",
            task_type="retrieval_document"
        )
        embeddings_service.rate_limiter.record_request.assert_called_once()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_empty_text(self, mock_genai, embeddings_service):
        """Test embedding generation with empty text."""
        result = embeddings_service.generate_embedding("")
        
        assert len(result) == 768
        assert all(v == 0.0 for v in result)
        mock_genai.embed_content.assert_not_called()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_whitespace_text(self, mock_genai, embeddings_service):
        """Test embedding generation with whitespace-only text."""
        result = embeddings_service.generate_embedding("   \n\t   ")
        
        assert len(result) == 768
        assert all(v == 0.0 for v in result)
        mock_genai.embed_content.assert_not_called()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_text_cleaning(self, mock_genai, embeddings_service):
        """Test that text is cleaned before embedding."""
        mock_response = {'embedding': [0.1] * 768}
        mock_genai.embed_content.return_value = mock_response
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        embeddings_service.generate_embedding("Test\ntext\nwith\nnewlines")
        
        mock_genai.embed_content.assert_called_with(
            model="models/text-embedding-004",
            content="Test text with newlines",
            task_type="retrieval_document"
        )
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_rate_limit_exceeded(self, mock_genai, embeddings_service):
        """Test embedding generation when rate limit is exceeded."""
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=False)
        
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            embeddings_service.generate_embedding("Test text")
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_no_embedding_in_response(self, mock_genai, embeddings_service):
        """Test handling response without embedding field."""
        mock_genai.embed_content.return_value = {}
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_error = Mock()
        
        with pytest.raises(ProviderError, match="Gemini embedding failed"):
            embeddings_service.generate_embedding("Test text")
        
        embeddings_service.rate_limiter.record_error.assert_called_once()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_quota_error(self, mock_genai, embeddings_service):
        """Test handling quota exceeded error."""
        mock_genai.embed_content.side_effect = Exception("Quota exceeded")
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_error = Mock()
        
        with pytest.raises(RateLimitError, match="Gemini rate limit error"):
            embeddings_service.generate_embedding("Test text")
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embedding_invalid_request(self, mock_genai, embeddings_service):
        """Test handling invalid request error."""
        mock_genai.embed_content.side_effect = Exception("Invalid model name")
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_error = Mock()
        
        with pytest.raises(ProviderError, match="Invalid request"):
            embeddings_service.generate_embedding("Test text")
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embeddings_batch_success(self, mock_genai, embeddings_service):
        """Test successful batch embedding generation."""
        texts = ["Text 1", "Text 2", "Text 3"]
        mock_response = {
            'embedding': [
                [0.1] * 768,
                [0.2] * 768,
                [0.3] * 768
            ]
        }
        mock_genai.embed_content.return_value = mock_response
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        results = embeddings_service.generate_embeddings(texts)
        
        assert len(results) == 3
        assert all(len(emb) == 768 for emb in results)
        mock_genai.embed_content.assert_called_once()
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embeddings_with_empty_texts(self, mock_genai, embeddings_service):
        """Test batch generation with some empty texts."""
        texts = ["Text 1", "", "Text 3", "   ", "Text 5"]
        mock_response = {
            'embedding': [
                [0.1] * 768,
                [0.3] * 768,
                [0.5] * 768
            ]
        }
        mock_genai.embed_content.return_value = mock_response
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        results = embeddings_service.generate_embeddings(texts)
        
        assert len(results) == 5
        # Check that empty texts got zero vectors
        assert all(v == 0.0 for v in results[1])  # Empty string
        assert all(v == 0.0 for v in results[3])  # Whitespace
        # Check that non-empty texts got embeddings
        assert results[0] == [0.1] * 768
        assert results[2] == [0.3] * 768
        assert results[4] == [0.5] * 768
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embeddings_large_batch(self, mock_genai, embeddings_service):
        """Test batch generation with texts exceeding batch size."""
        embeddings_service.batch_size = 2
        texts = ["Text 1", "Text 2", "Text 3", "Text 4", "Text 5"]
        
        # Mock responses for each batch
        mock_genai.embed_content.side_effect = [
            {'embedding': [[0.1] * 768, [0.2] * 768]},
            {'embedding': [[0.3] * 768, [0.4] * 768]},
            {'embedding': [[0.5] * 768]}
        ]
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        results = embeddings_service.generate_embeddings(texts)
        
        assert len(results) == 5
        assert mock_genai.embed_content.call_count == 3
    
    @patch('src.services.embeddings_gemini.genai')
    def test_generate_embeddings_single_embedding_response(self, mock_genai, embeddings_service):
        """Test handling single embedding response format."""
        texts = ["Single text"]
        # API might return single embedding as flat list
        mock_response = {'embedding': [0.1] * 768}
        mock_genai.embed_content.return_value = mock_response
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=True)
        embeddings_service.rate_limiter.record_request = Mock()
        
        results = embeddings_service.generate_embeddings(texts)
        
        assert len(results) == 1
        assert results[0] == [0.1] * 768
    
    def test_generate_embeddings_empty_list(self, embeddings_service):
        """Test generating embeddings for empty list."""
        results = embeddings_service.generate_embeddings([])
        assert results == []
    
    def test_get_model_info(self, embeddings_service):
        """Test getting model information."""
        info = embeddings_service.get_model_info()
        
        assert info['model_name'] == "models/text-embedding-004"
        assert info['dimension'] == 768
        assert info['api_based'] is True
        assert info['batch_size'] == 100
        assert 'rate_limits' in info
        assert info['rate_limits']['requests_per_minute'] == 1500
    
    def test_compute_similarity_normal(self, embeddings_service):
        """Test computing cosine similarity between embeddings."""
        # Create orthogonal vectors
        emb1 = [1.0, 0.0, 0.0] + [0.0] * 765
        emb2 = [0.0, 1.0, 0.0] + [0.0] * 765
        
        similarity = embeddings_service.compute_similarity(emb1, emb2)
        assert pytest.approx(similarity, abs=0.001) == 0.0
        
        # Same vectors
        similarity = embeddings_service.compute_similarity(emb1, emb1)
        assert pytest.approx(similarity, abs=0.001) == 1.0
        
        # Opposite vectors
        emb3 = [-1.0, 0.0, 0.0] + [0.0] * 765
        similarity = embeddings_service.compute_similarity(emb1, emb3)
        assert pytest.approx(similarity, abs=0.001) == -1.0
    
    def test_compute_similarity_zero_vectors(self, embeddings_service):
        """Test computing similarity with zero vectors."""
        zero_vec = [0.0] * 768
        normal_vec = [1.0] + [0.0] * 767
        
        similarity = embeddings_service.compute_similarity(zero_vec, normal_vec)
        assert similarity == 0.0
        
        similarity = embeddings_service.compute_similarity(zero_vec, zero_vec)
        assert similarity == 0.0
    
    def test_find_similar(self, embeddings_service):
        """Test finding similar embeddings."""
        # Create test embeddings
        query = [1.0, 0.0, 0.0] + [0.0] * 765
        embeddings = [
            [0.9, 0.1, 0.0] + [0.0] * 765,  # Most similar
            [0.5, 0.5, 0.0] + [0.0] * 765,  # Medium similar
            [0.0, 1.0, 0.0] + [0.0] * 765,  # Orthogonal
            [-1.0, 0.0, 0.0] + [0.0] * 765, # Opposite
            [0.8, 0.2, 0.0] + [0.0] * 765   # Second most similar
        ]
        
        results = embeddings_service.find_similar(query, embeddings, top_k=3)
        
        assert len(results) == 3
        # Check that results are sorted by similarity
        assert results[0][0] == 0  # Index of most similar
        assert results[1][0] == 4  # Index of second most similar
        assert results[2][0] == 1  # Index of third most similar
        
        # Check similarity scores are descending
        assert results[0][1] > results[1][1] > results[2][1]
    
    def test_find_similar_empty_embeddings(self, embeddings_service):
        """Test finding similar with empty embeddings list."""
        query = [1.0] * 768
        results = embeddings_service.find_similar(query, [], top_k=5)
        assert results == []
    
    def test_find_similar_top_k_larger_than_list(self, embeddings_service):
        """Test finding similar when top_k is larger than embeddings list."""
        query = [1.0] * 768
        embeddings = [[0.5] * 768, [0.7] * 768]
        
        results = embeddings_service.find_similar(query, embeddings, top_k=10)
        
        assert len(results) == 2
    
    def test_get_rate_limit_status(self, embeddings_service):
        """Test getting rate limit status."""
        mock_status = {"requests": 100, "tokens": 50000}
        embeddings_service.rate_limiter.get_status = Mock(return_value=mock_status)
        
        status = embeddings_service.get_rate_limit_status()
        
        assert status == mock_status
    
    @patch('src.services.embeddings_gemini.logger')
    def test_logging(self, mock_logger):
        """Test that initialization is logged."""
        service = GeminiEmbeddingsService(api_key="test_key")
        
        mock_logger.info.assert_called_with(
            "Initialized GeminiEmbeddingsService with model: models/text-embedding-004"
        )
    
    @patch('src.services.embeddings_gemini.genai')
    def test_token_estimation(self, mock_genai, embeddings_service):
        """Test token estimation for rate limiting."""
        text = "This is a test text"  # 5 characters + 12 characters = 17 total
        
        embeddings_service.rate_limiter.can_make_request = Mock(return_value=False)
        
        with pytest.raises(RateLimitError):
            embeddings_service.generate_embedding(text)
        
        # Should use character count as token estimate
        embeddings_service.rate_limiter.can_make_request.assert_called_with(
            'text-embedding-004', 17
        )