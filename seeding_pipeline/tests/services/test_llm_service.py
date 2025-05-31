"""Tests for LLM service implementation."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.services.llm import LLMService
class TestLLMService:
    """Test suite for LLMService."""
    
    @pytest.fixture
    def service(self):
        """Create LLM service instance."""
        with patch('src.services.llm.genai') as mock_genai:
            service = LLMService(api_key="test_key")
            return service
    
    def test_initialization(self):
        """Test service initialization."""
        with patch('src.services.llm.genai') as mock_genai:
            service = LLMService(api_key="test_key", model_name="gemini-pro")
            mock_genai.configure.assert_called_once_with(api_key="test_key")
            assert service.model_name == "gemini-pro"
    
    def test_initialization_no_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="API key is required"):
            LLMService(api_key=None)
    
    @patch('src.services.llm.genai')
    def test_generate_content(self, mock_genai):
        """Test content generation."""
        # Setup mock
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated content"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = LLMService(api_key="test_key")
        result = service.generate(prompt="Test prompt")
        
        assert result == "Generated content"
        mock_model.generate_content.assert_called_once_with("Test prompt")
    
    @patch('src.services.llm.genai')
    def test_extract_entities(self, mock_genai):
        """Test entity extraction."""
        # Setup mock
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''[
            {"name": "John Doe", "type": "PERSON"},
            {"name": "OpenAI", "type": "ORGANIZATION"}
        ]'''
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = LLMService(api_key="test_key")
        entities = service.extract_entities("John Doe works at OpenAI")
        
        assert len(entities) == 2
        assert entities[0]["name"] == "John Doe"
        assert entities[1]["type"] == "ORGANIZATION"
    
    @patch('src.services.llm.genai')
    def test_error_handling(self, mock_genai):
        """Test error handling."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = LLMService(api_key="test_key")
        
        with pytest.raises(Exception, match="API Error"):
            service.generate("Test prompt")