"""
Unit tests for JSON mode implementation verification.

Tests that verify Gemini Native JSON Mode is properly implemented across
all components that were updated in the implementation plan.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.env_config import EnvironmentConfig

from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.services.llm import LLMService
from src.extraction.sentiment_analyzer import SentimentAnalyzer
from src.extraction.parsers import ResponseParser


class TestJSONModeImplementation:
    """Test JSON mode implementation across all updated components."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        llm = Mock()
        llm.complete_with_options.return_value = {
            'content': '{"test": "response"}',
            'json_mode': True
        }
        return llm

    @pytest.fixture
    def knowledge_extractor(self, mock_llm_service):
        """Create knowledge extractor with mock LLM."""
        config = ExtractionConfig()
        return KnowledgeExtractor(
            llm_service=mock_llm_service,
            embedding_service=None,  # No embeddings
            config=config
        )

    @pytest.fixture
    def mock_meaningful_unit(self):
        """Create mock MeaningfulUnit."""
        unit = Mock()
        unit.text = "This is a test conversation about artificial intelligence."
        unit.id = "test-unit"
        unit.themes = ["AI", "technology"]
        unit.speaker_distribution = {"Speaker1": 0.6, "Speaker2": 0.4}
        return unit

    def test_knowledge_extractor_uses_json_mode(self, knowledge_extractor, mock_meaningful_unit):
        """Test that KnowledgeExtractor uses JSON mode for combined extraction."""
        # Mock successful JSON response
        mock_response = {
            'content': json.dumps({
                "entities": [{"name": "AI", "type": "concept", "importance": 8}],
                "quotes": [{"text": "This is interesting", "speaker": "Speaker1"}],
                "insights": [{"content": "AI is advancing", "type": "factual"}],
                "conversation_structure": {"segments": 2}
            }),
            'json_mode': True
        }
        knowledge_extractor.llm_service.complete_with_options.return_value = mock_response

        # Extract knowledge
        result = knowledge_extractor.extract_knowledge_combined(mock_meaningful_unit, {})

        # Verify JSON mode was used
        calls = knowledge_extractor.llm_service.complete_with_options.call_args_list
        assert len(calls) > 0, "Should make LLM calls"
        
        json_mode_call = calls[0]
        assert json_mode_call[1].get('json_mode') is True, "Should use JSON mode"

        # Verify results
        assert len(result.entities) > 0
        assert result.entities[0]['name'] == "AI"

    def test_entity_embedding_removal(self, knowledge_extractor, mock_meaningful_unit):
        """Test that entity embeddings are not generated."""
        # Add mock embedding service
        mock_embedding = Mock()
        knowledge_extractor.embedding_service = mock_embedding

        # Mock JSON response with entities
        mock_response = {
            'content': json.dumps({
                "entities": [{"name": "Machine Learning", "type": "concept", "importance": 9}],
                "quotes": [],
                "insights": [],
                "conversation_structure": {}
            })
        }
        knowledge_extractor.llm_service.complete_with_options.return_value = mock_response

        # Extract knowledge
        result = knowledge_extractor.extract_knowledge_combined(mock_meaningful_unit, {})

        # Verify embedding service was NOT called
        mock_embedding.generate_embedding.assert_not_called()

        # Verify entities were created without embeddings
        assert len(result.entities) > 0
        for entity in result.entities:
            assert 'embedding' not in entity

    def test_sentiment_analyzer_uses_json_mode(self, mock_llm_service):
        """Test that SentimentAnalyzer uses JSON mode."""
        # Mock JSON sentiment response
        sentiment_response = {
            'content': json.dumps({
                "polarity": "positive",
                "score": 0.8,
                "emotions": {"joy": 0.7, "excitement": 0.6},
                "attitudes": {"enthusiastic": 0.9},
                "energy_level": 0.8,
                "engagement_level": 0.9,
                "reasoning": "Very positive sentiment"
            })
        }
        mock_llm_service.complete_with_options.return_value = sentiment_response

        analyzer = SentimentAnalyzer(mock_llm_service)
        
        # Create mock unit for sentiment analysis
        mock_unit = Mock()
        mock_unit.text = "This is amazing! I love this technology."
        mock_unit.id = "sentiment-test"
        mock_unit.speaker_distribution = {"Speaker": 1.0}
        mock_unit.themes = ["technology"]
        mock_unit.unit_type = "discussion"

        # Analyze sentiment
        result = analyzer.analyze_meaningful_unit(mock_unit)

        # Verify JSON mode was used
        calls = mock_llm_service.complete_with_options.call_args_list
        json_mode_calls = [call for call in calls if call[1].get('json_mode') is True]
        assert len(json_mode_calls) > 0, "Should use JSON mode for sentiment analysis"

        # Verify sentiment results
        assert result.overall_sentiment.polarity == "positive"
        assert result.overall_sentiment.score == 0.8

    def test_response_parser_handles_native_json(self):
        """Test that ResponseParser handles native JSON responses efficiently."""
        parser = ResponseParser()

        # Test clean JSON (from native JSON mode)
        clean_json = '[{"name": "Clean Entity", "type": "concept", "importance": 7}]'
        result = parser.parse_json_response(clean_json, list)

        assert result.success
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Clean Entity"
        assert len(result.warnings) == 0  # No warnings for clean JSON

        # Test that it still handles legacy markdown format
        markdown_json = '```json\n[{"name": "Legacy Entity", "type": "person"}]\n```'
        result2 = parser.parse_json_response(markdown_json, list)

        assert result2.success
        assert result2.data[0]["name"] == "Legacy Entity"

    @patch('google.genai.configure')
    @patch('google.genai.Client')
    def test_llm_service_json_mode_integration(self, mock_client_class, mock_configure):
        """Test LLMService native JSON mode integration."""
        # Setup mocks
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = '{"structured": "response", "valid": true}'
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Create LLM service using environment configuration
        llm_service = LLMService(api_key="test_key", model_name=EnvironmentConfig.get_flash_model())

        # Test JSON mode
        result = llm_service.complete_with_options(
            "Test prompt",
            temperature=0.5,
            json_mode=True
        )

        # Verify Google GenAI was used
        mock_configure.assert_called_once_with(api_key="test_key")
        mock_client_class.assert_called_once()

        # Verify result
        assert result['json_mode'] is True
        assert result['content'] == '{"structured": "response", "valid": true}'

        # Verify generate_content was called
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert call_args[1]['model'] == EnvironmentConfig.get_flash_model()
        assert call_args[1]['contents'] == "Test prompt"

    def test_generate_completion_with_response_format(self):
        """Test LLMService.generate_completion uses JSON mode with response_format."""
        llm_service = LLMService(api_key="test_key")
        
        with patch.object(llm_service, 'complete_with_options') as mock_complete:
            mock_complete.return_value = {
                'content': '{"result": "structured response"}',
                'json_mode': True
            }

            # Mock Pydantic model
            mock_format = Mock()
            mock_format.model_json_schema.return_value = {"type": "object"}
            mock_format.model_validate.return_value = {"result": "structured response"}

            result = llm_service.generate_completion(
                "Test prompt",
                response_format=mock_format
            )

            # Verify JSON mode was used
            mock_complete.assert_called_once()
            call_args = mock_complete.call_args
            assert call_args[1]['json_mode'] is True

            # Verify structured response
            assert result == {"result": "structured response"}

    def test_api_call_optimization(self, knowledge_extractor, mock_meaningful_unit):
        """Test that API calls are optimized (no entity embedding calls)."""
        call_count = 0

        def counting_mock(prompt, json_mode=False, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                'content': json.dumps({
                    "entities": [{"name": "Test Entity", "type": "concept"}],
                    "quotes": [],
                    "insights": [],
                    "conversation_structure": {}
                })
            }

        knowledge_extractor.llm_service.complete_with_options.side_effect = counting_mock

        # Extract knowledge
        result = knowledge_extractor.extract_knowledge_combined(mock_meaningful_unit, {})

        # Should be only 1 call (combined extraction, no embedding calls)
        assert call_count == 1, f"Expected 1 API call, got {call_count}"
        assert len(result.entities) > 0
        
        # Verify no embeddings
        for entity in result.entities:
            assert 'embedding' not in entity

    def test_error_handling_in_json_mode(self, knowledge_extractor, mock_meaningful_unit):
        """Test error handling when JSON mode encounters issues."""
        # Mock LLM service to raise exception
        knowledge_extractor.llm_service.complete_with_options.side_effect = Exception("JSON parsing failed")

        # Should handle error gracefully
        result = knowledge_extractor.extract_knowledge_combined(mock_meaningful_unit, {})

        # Should return empty/default results
        assert result.entities == []
        assert result.quotes == []
        assert result.insights == []

    def test_backwards_compatibility(self):
        """Test that implementation maintains backwards compatibility."""
        parser = ResponseParser()

        # Test old-style markdown JSON still works
        old_style = '''```json
        {
            "entities": [
                {"name": "Old Style", "type": "concept"}
            ]
        }
        ```'''

        result = parser.parse_json_response(old_style, dict)
        assert result.success
        assert result.data["entities"][0]["name"] == "Old Style"

        # Test clean JSON (new style) works better
        new_style = '{"entities": [{"name": "New Style", "type": "concept"}]}'
        result2 = parser.parse_json_response(new_style, dict)
        assert result2.success
        assert result2.data["entities"][0]["name"] == "New Style"
        assert len(result2.warnings) == 0  # No warnings for clean JSON