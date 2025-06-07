"""Comprehensive unit tests for schemaless adapter module."""

from typing import List, Dict, Any
from unittest.mock import Mock, patch
import json

import pytest

from src.core.extraction_interface import (
from src.processing.adapters.schemaless_adapter import SchemalessAdapter
    Segment, Entity, Relationship, Quote, Insight
)


class TestSchemalessAdapter:
    """Test SchemalessAdapter functionality."""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        return Mock()
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create mock embedding provider."""
        return Mock()
    
    @pytest.fixture
    def adapter(self, mock_llm_provider, mock_embedding_provider):
        """Create SchemalessAdapter instance."""
        return SchemalessAdapter(mock_llm_provider, mock_embedding_provider)
    
    @pytest.fixture
    def sample_segment(self):
        """Create sample segment."""
        return Segment(
            text="John Smith founded TechCorp in 2020. The company focuses on AI research.",
            speaker="Host",
            start=10.0,
            end=15.0,
            id="seg_1"
        )
    
    def test_initialization(self, adapter, mock_llm_provider, mock_embedding_provider):
        """Test adapter initialization."""
        assert adapter.llm_provider == mock_llm_provider
        assert adapter.embedding_provider == mock_embedding_provider
        assert adapter._extraction_mode == "schemaless"
        assert isinstance(adapter._discovered_types, set)
        assert len(adapter._discovered_types) == 0
    
    def test_extract_entities_success(self, adapter, sample_segment, mock_llm_provider):
        """Test successful entity extraction."""
        mock_response = {
            "entities": [
                {
                    "name": "John Smith",
                    "type": "Founder",
                    "description": "Founder of TechCorp",
                    "confidence": 0.9,
                    "properties": {"role": "CEO"}
                },
                {
                    "name": "TechCorp",
                    "type": "AI Company",
                    "description": "Company focused on AI research",
                    "confidence": 0.85,
                    "properties": {"founded": "2020"}
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        entities = adapter.extract_entities(sample_segment)
        
        assert len(entities) == 2
        assert all(isinstance(e, Entity) for e in entities)
        
        # Check first entity
        assert entities[0].name == "John Smith"
        assert entities[0].type == "Founder"
        assert entities[0].description == "Founder of TechCorp"
        assert entities[0].confidence == 0.9
        assert entities[0].properties == {"role": "CEO"}
        
        # Check discovered types
        assert "Founder" in adapter._discovered_types
        assert "AI Company" in adapter._discovered_types
    
    def test_extract_entities_error(self, adapter, sample_segment, mock_llm_provider):
        """Test entity extraction with error."""
        mock_llm_provider.generate.side_effect = Exception("LLM error")
        
        entities = adapter.extract_entities(sample_segment)
        
        assert entities == []
    
    def test_extract_entities_invalid_json(self, adapter, sample_segment, mock_llm_provider):
        """Test entity extraction with invalid JSON response."""
        mock_llm_provider.generate.return_value = "Invalid JSON"
        
        entities = adapter.extract_entities(sample_segment)
        
        assert entities == []
    
    def test_extract_entities_missing_fields(self, adapter, sample_segment, mock_llm_provider):
        """Test entity extraction with missing fields."""
        mock_response = {
            "entities": [
                {
                    "name": "John Smith"
                    # Missing type and other fields
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        entities = adapter.extract_entities(sample_segment)
        
        assert len(entities) == 1
        assert entities[0].type == "Unknown"  # Default value
        assert entities[0].confidence == 0.7  # Default value
    
    def test_extract_relationships_success(self, adapter, sample_segment, mock_llm_provider):
        """Test successful relationship extraction."""
        # Mock entity extraction first
        mock_entity_response = {
            "entities": [
                {"name": "John Smith", "type": "Person"},
                {"name": "TechCorp", "type": "Company"}
            ]
        }
        
        mock_rel_response = {
            "relationships": [
                {
                    "source": "John Smith",
                    "target": "TechCorp",
                    "type": "FOUNDED",
                    "confidence": 0.95,
                    "properties": {"year": 2020}
                }
            ]
        }
        
        mock_llm_provider.generate.side_effect = [
            json.dumps(mock_entity_response),
            json.dumps(mock_rel_response)
        ]
        
        relationships = adapter.extract_relationships(sample_segment)
        
        assert len(relationships) == 1
        assert isinstance(relationships[0], Relationship)
        assert relationships[0].source == "John Smith"
        assert relationships[0].target == "TechCorp"
        assert relationships[0].type == "FOUNDED"
        assert relationships[0].confidence == 0.95
        assert relationships[0].properties == {"year": 2020}
    
    def test_extract_relationships_error(self, adapter, sample_segment, mock_llm_provider):
        """Test relationship extraction with error."""
        mock_llm_provider.generate.side_effect = Exception("LLM error")
        
        relationships = adapter.extract_relationships(sample_segment)
        
        assert relationships == []
    
    def test_extract_quotes_success(self, adapter, sample_segment, mock_llm_provider):
        """Test successful quote extraction."""
        mock_response = {
            "quotes": [
                {
                    "text": "The company focuses on AI research",
                    "speaker": "Host",
                    "context": "Describing TechCorp's mission",
                    "confidence": 0.8
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        quotes = adapter.extract_quotes(sample_segment)
        
        assert len(quotes) == 1
        assert isinstance(quotes[0], Quote)
        assert quotes[0].text == "The company focuses on AI research"
        assert quotes[0].speaker == "Host"
        assert quotes[0].context == "Describing TechCorp's mission"
        assert quotes[0].confidence == 0.8
        assert quotes[0].timestamp == 10.0  # From segment start
    
    def test_extract_quotes_no_speaker(self, adapter, mock_llm_provider):
        """Test quote extraction with no speaker in segment."""
        segment = Segment(
            text="This is important.",
            speaker=None,
            start=0.0,
            end=5.0,
            id="seg_1"
        )
        
        mock_response = {
            "quotes": [
                {
                    "text": "This is important",
                    "confidence": 0.7
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        quotes = adapter.extract_quotes(segment)
        
        assert quotes[0].speaker == "Unknown"
    
    def test_extract_insights_success(self, adapter, sample_segment, mock_llm_provider):
        """Test successful insight extraction."""
        mock_response = {
            "insights": [
                {
                    "content": "AI startups are emerging rapidly",
                    "speaker": "Host",
                    "category": "industry_trend",
                    "confidence": 0.75
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        insights = adapter.extract_insights(sample_segment)
        
        assert len(insights) == 1
        assert isinstance(insights[0], Insight)
        assert insights[0].content == "AI startups are emerging rapidly"
        assert insights[0].speaker == "Host"
        assert insights[0].category == "industry_trend"
        assert insights[0].confidence == 0.75
    
    def test_extract_insights_default_category(self, adapter, sample_segment, mock_llm_provider):
        """Test insight extraction with default category."""
        mock_response = {
            "insights": [
                {
                    "content": "Important observation",
                    "confidence": 0.7
                }
            ]
        }
        mock_llm_provider.generate.return_value = json.dumps(mock_response)
        
        insights = adapter.extract_insights(sample_segment)
        
        assert insights[0].category == "observation"  # Default value
    
    def test_extract_all(self, adapter, sample_segment, mock_llm_provider):
        """Test extracting all components from segment."""
        # Mock responses for each extraction
        entity_response = {
            "entities": [
                {"name": "John Smith", "type": "Person", "confidence": 0.9}
            ]
        }
        rel_response = {
            "relationships": [
                {"source": "John Smith", "target": "TechCorp", "type": "FOUNDED"}
            ]
        }
        quote_response = {
            "quotes": [
                {"text": "AI is the future", "speaker": "Host", "confidence": 0.8}
            ]
        }
        insight_response = {
            "insights": [
                {"content": "Tech sector growth", "confidence": 0.7}
            ]
        }
        
        mock_llm_provider.generate.side_effect = [
            json.dumps(entity_response),
            json.dumps(entity_response),  # For relationship extraction
            json.dumps(rel_response),
            json.dumps(quote_response),
            json.dumps(insight_response)
        ]
        
        result = adapter.extract_all(sample_segment)
        
        assert 'entities' in result
        assert 'relationships' in result
        assert 'quotes' in result
        assert 'insights' in result
        assert 'metadata' in result
        
        # Check metadata
        metadata = result['metadata']
        assert metadata['extraction_mode'] == 'schemaless'
        assert 'Person' in metadata['discovered_types']
        assert metadata['segment_duration'] == 5.0
        assert metadata['entity_count'] == 1
        assert metadata['relationship_count'] == 1
    
    def test_get_extraction_mode(self, adapter):
        """Test getting extraction mode."""
        assert adapter.get_extraction_mode() == "schemaless"
    
    def test_get_discovered_types(self, adapter):
        """Test getting discovered types."""
        # Initially empty
        assert adapter.get_discovered_types() == []
        
        # Add some types
        adapter._discovered_types.add("Person")
        adapter._discovered_types.add("Company")
        adapter._discovered_types.add("AI Technology")
        
        # Should return sorted list
        types = adapter.get_discovered_types()
        assert types == ["AI Technology", "Company", "Person"]
    
    def test_build_entity_prompt(self, adapter, sample_segment):
        """Test entity extraction prompt building."""
        prompt = adapter._build_entity_prompt(sample_segment)
        
        assert "Extract all entities" in prompt
        assert sample_segment.text in prompt
        assert sample_segment.speaker in prompt
        assert "creative entity types" in prompt
        assert "JSON" in prompt
    
    def test_build_relationship_prompt(self, adapter, sample_segment):
        """Test relationship extraction prompt building."""
        entity_names = ["John Smith", "TechCorp"]
        prompt = adapter._build_relationship_prompt(sample_segment, entity_names)
        
        assert "Extract relationships" in prompt
        assert "John Smith" in prompt
        assert "TechCorp" in prompt
        assert sample_segment.text in prompt
        assert "SPECIFIC_RELATIONSHIP_TYPE" in prompt
    
    def test_build_quotes_prompt(self, adapter, sample_segment):
        """Test quote extraction prompt building."""
        prompt = adapter._build_quotes_prompt(sample_segment)
        
        assert "notable or insightful quotes" in prompt
        assert sample_segment.text in prompt
        assert sample_segment.speaker in prompt
        assert "exact quote text" in prompt
    
    def test_build_insights_prompt(self, adapter, sample_segment):
        """Test insight extraction prompt building."""
        prompt = adapter._build_insights_prompt(sample_segment)
        
        assert "key insights or observations" in prompt
        assert sample_segment.text in prompt
        assert "category" in prompt
    
    @patch('src.processing.adapters.schemaless_adapter.logger')
    def test_logging_on_errors(self, mock_logger, adapter, sample_segment, mock_llm_provider):
        """Test that errors are logged properly."""
        mock_llm_provider.generate.side_effect = Exception("Test error")
        
        # Test each extraction method
        adapter.extract_entities(sample_segment)
        mock_logger.error.assert_called_with("Error extracting entities: Test error")
        
        adapter.extract_relationships(sample_segment)
        mock_logger.error.assert_called_with("Error extracting relationships: Test error")
        
        adapter.extract_quotes(sample_segment)
        mock_logger.error.assert_called_with("Error extracting quotes: Test error")
        
        adapter.extract_insights(sample_segment)
        mock_logger.error.assert_called_with("Error extracting insights: Test error")
    
    def test_empty_responses(self, adapter, sample_segment, mock_llm_provider):
        """Test handling of empty responses."""
        empty_response = {"entities": [], "relationships": [], "quotes": [], "insights": []}
        mock_llm_provider.generate.return_value = json.dumps(empty_response)
        
        entities = adapter.extract_entities(sample_segment)
        assert entities == []
        
        relationships = adapter.extract_relationships(sample_segment)
        assert relationships == []
        
        quotes = adapter.extract_quotes(sample_segment)
        assert quotes == []
        
        insights = adapter.extract_insights(sample_segment)
        assert insights == []