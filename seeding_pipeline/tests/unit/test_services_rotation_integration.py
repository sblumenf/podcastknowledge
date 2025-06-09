"""Integration tests for services with API key rotation."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.services import (
    create_gemini_services, 
    create_llm_service_only,
    create_embeddings_service_only,
    LLMService,
    GeminiEmbeddingsService
)


class TestServicesRotationIntegration:
    """Test service initialization with rotation support."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for state files."""
        return tmp_path
    
    @pytest.fixture
    def mock_api_keys(self, monkeypatch):
        """Set up mock API keys in environment."""
        monkeypatch.setenv("GEMINI_API_KEY_1", "test_key_1")
        monkeypatch.setenv("GEMINI_API_KEY_2", "test_key_2")
        monkeypatch.setenv("GEMINI_API_KEY_3", "test_key_3")
    
    def test_create_gemini_services_with_rotation(self, mock_api_keys, temp_dir):
        """Test creating both LLM and embeddings services with shared rotation."""
        llm_service, embeddings_service = create_gemini_services(
            state_dir=temp_dir,
            llm_model='gemini-2.5-flash',
            embeddings_model='models/text-embedding-004'
        )
        
        # Verify services were created
        assert isinstance(llm_service, LLMService)
        assert isinstance(embeddings_service, GeminiEmbeddingsService)
        
        # Verify they share the same key rotation manager
        assert llm_service.key_rotation_manager is not None
        assert embeddings_service.key_rotation_manager is not None
        assert llm_service.key_rotation_manager is embeddings_service.key_rotation_manager
        
        # Verify rotation manager has correct number of keys
        assert len(llm_service.key_rotation_manager.api_keys) == 3
    
    def test_create_gemini_services_no_keys(self, temp_dir, monkeypatch):
        """Test error when no API keys are available."""
        # Clear all API keys
        for key in ["GOOGLE_API_KEY", "GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(1, 10)]:
            monkeypatch.delenv(key, raising=False)
        
        with pytest.raises(ValueError, match="No API keys found"):
            create_gemini_services(state_dir=temp_dir)
    
    def test_create_llm_service_only(self, mock_api_keys, temp_dir):
        """Test creating only LLM service with rotation."""
        service = create_llm_service_only(
            model_name='gemini-2.5-flash',
            temperature=0.5,
            max_tokens=2048,
            state_dir=temp_dir
        )
        
        assert isinstance(service, LLMService)
        assert service.key_rotation_manager is not None
        assert service.model_name == 'gemini-2.5-flash'
        assert service.temperature == 0.5
        assert service.max_tokens == 2048
    
    def test_create_embeddings_service_only(self, mock_api_keys, temp_dir):
        """Test creating only embeddings service with rotation."""
        service = create_embeddings_service_only(
            model_name='models/text-embedding-004',
            batch_size=50,
            state_dir=temp_dir
        )
        
        assert isinstance(service, GeminiEmbeddingsService)
        assert service.key_rotation_manager is not None
        assert service.model_name == 'models/text-embedding-004'
        assert service.batch_size == 50
    
    def test_backward_compatibility_google_api_key(self, temp_dir, monkeypatch):
        """Test backward compatibility with GOOGLE_API_KEY."""
        monkeypatch.setenv("GOOGLE_API_KEY", "legacy_google_key")
        
        llm_service, embeddings_service = create_gemini_services(state_dir=temp_dir)
        
        assert llm_service.key_rotation_manager is not None
        assert len(llm_service.key_rotation_manager.api_keys) == 1
        assert llm_service.key_rotation_manager.api_keys[0] == "legacy_google_key"
    
    def test_state_persistence_initialization(self, mock_api_keys, temp_dir):
        """Test that state persistence is properly initialized."""
        with patch('src.services.RotationStateManager.ensure_state_persistence') as mock_ensure:
            mock_ensure.return_value = True
            
            llm_service, embeddings_service = create_gemini_services(state_dir=temp_dir)
            
            # Verify state persistence was initialized
            mock_ensure.assert_called_once()
    
    def test_services_with_all_options(self, mock_api_keys, temp_dir):
        """Test creating services with all configuration options."""
        llm_service, embeddings_service = create_gemini_services(
            llm_model='gemini-2.0-flash',
            embeddings_model='models/text-embedding-004',
            temperature=0.3,
            max_tokens=8192,
            embeddings_batch_size=200,
            enable_cache=False,
            cache_ttl=7200,
            state_dir=temp_dir
        )
        
        # Verify LLM configuration
        assert llm_service.model_name == 'gemini-2.0-flash'
        assert llm_service.temperature == 0.3
        assert llm_service.max_tokens == 8192
        assert llm_service.enable_cache is False
        assert llm_service.cache_ttl == 7200
        
        # Verify embeddings configuration
        assert embeddings_service.model_name == 'models/text-embedding-004'
        assert embeddings_service.batch_size == 200
    
    @patch('google.generativeai.configure')
    def test_api_key_configuration(self, mock_configure, mock_api_keys, temp_dir):
        """Test that API keys are properly configured in services."""
        service = create_llm_service_only(state_dir=temp_dir)
        
        # The service should have a rotation manager with keys
        assert service.key_rotation_manager is not None
        assert len(service.key_rotation_manager.api_keys) == 3