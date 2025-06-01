"""Core tests for knowledge extraction functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig, ExtractionResult
from src.core.models import Segment


class TestKnowledgeExtractionCore:
    """Core tests for knowledge extraction functionality."""
    
    @pytest.fixture
    def extraction_config(self):
        """Create extraction configuration."""
        return ExtractionConfig(
            min_quote_length=10,
            max_quote_length=50,
            extract_quotes=True,
            quote_importance_threshold=0.7,
            entity_confidence_threshold=0.6,
            max_entities_per_segment=20,
            validate_extractions=True,
            dry_run=False
        )
    
    @pytest.fixture
    def extractor(self, extraction_config):
        """Create knowledge extractor instance."""
        return KnowledgeExtractor(config=extraction_config)
    
    @pytest.fixture
    def sample_segment(self):
        """Create sample segment for testing."""
        return Segment(
            text="Dr. Jane Smith from Stanford University discussed the latest advances in artificial intelligence and machine learning at the tech conference.",
            start_time=0.0,
            end_time=10.0,
            speaker="Host"
        )
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = Mock()
        provider.generate.return_value = {
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "confidence": 0.9},
                {"name": "Stanford University", "type": "ORGANIZATION", "confidence": 0.95},
                {"name": "artificial intelligence", "type": "TECHNOLOGY", "confidence": 0.85},
                {"name": "machine learning", "type": "TECHNOLOGY", "confidence": 0.85}
            ],
            "relationships": [
                {
                    "source": "Dr. Jane Smith",
                    "target": "Stanford University",
                    "type": "AFFILIATED_WITH"
                }
            ],
            "insights": [
                {
                    "type": "TOPIC",
                    "content": "AI and ML advances discussed at tech conference"
                }
            ]
        }
        return provider
    
    def test_extract_entities(self, extractor, sample_segment, mock_llm_provider):
        """Test entity extraction from text."""
        # Set up the extractor with mock provider
        extractor.llm_provider = mock_llm_provider
        
        # Extract entities
        result = extractor.extract(sample_segment)
        
        # Verify extraction was called
        mock_llm_provider.generate.assert_called_once()
        
        # Verify entities were extracted
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 4
        
        # Verify entity details
        person_entity = next(e for e in result.entities if e["type"] == "PERSON")
        assert person_entity["name"] == "Dr. Jane Smith"
        assert person_entity["confidence"] >= 0.6  # Above threshold
    
    def test_extract_relationships(self, extractor, sample_segment, mock_llm_provider):
        """Test relationship extraction between entities."""
        extractor.llm_provider = mock_llm_provider
        
        # Extract relationships
        result = extractor.extract(sample_segment)
        
        # Verify relationships were extracted
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel["source"] == "Dr. Jane Smith"
        assert rel["target"] == "Stanford University"
        assert rel["type"] == "AFFILIATED_WITH"
    
    def test_extract_insights(self, extractor, sample_segment, mock_llm_provider):
        """Test insight generation from content."""
        # Modify mock to include insights in response
        mock_llm_provider.generate.return_value["quotes"] = [
            {
                "text": "the latest advances in artificial intelligence and machine learning",
                "importance": 0.8,
                "speaker": "Dr. Jane Smith"
            }
        ]
        
        extractor.llm_provider = mock_llm_provider
        
        # Extract insights
        result = extractor.extract(sample_segment)
        
        # Verify quotes/insights were extracted
        assert len(result.quotes) >= 1
        quote = result.quotes[0]
        assert quote["importance"] >= 0.7  # Above threshold
        assert "artificial intelligence" in quote["text"]
    
    def test_handle_llm_failure(self, extractor, sample_segment):
        """Test graceful handling when LLM fails."""
        # Create mock that raises exception
        mock_llm = Mock()
        mock_llm.generate.side_effect = Exception("LLM connection failed")
        extractor.llm_provider = mock_llm
        
        # Should handle gracefully
        result = extractor.extract(sample_segment)
        
        # Should return empty result, not crash
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0
        assert result.metadata.get("error") is not None
    
    def test_extraction_timeout(self, extractor, sample_segment):
        """Test timeout handling during extraction."""
        # Create mock that simulates timeout
        mock_llm = Mock()
        mock_llm.generate.side_effect = TimeoutError("Request timed out")
        extractor.llm_provider = mock_llm
        
        # Should handle timeout gracefully
        result = extractor.extract(sample_segment)
        
        # Should return partial or empty result
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get("timeout") is True or result.metadata.get("error") is not None
    
    def test_entity_confidence_filtering(self, extractor, sample_segment, mock_llm_provider):
        """Test that low-confidence entities are filtered out."""
        # Add low-confidence entities to mock response
        mock_llm_provider.generate.return_value["entities"].extend([
            {"name": "maybe entity", "type": "UNKNOWN", "confidence": 0.3},
            {"name": "probable entity", "type": "CONCEPT", "confidence": 0.5}
        ])
        
        extractor.llm_provider = mock_llm_provider
        
        # Extract with confidence threshold
        result = extractor.extract(sample_segment)
        
        # Should only include high-confidence entities
        assert all(e["confidence"] >= 0.6 for e in result.entities)
        assert not any(e["name"] == "maybe entity" for e in result.entities)
    
    def test_quote_extraction_filtering(self, extractor, sample_segment, mock_llm_provider):
        """Test quote extraction with length and importance filtering."""
        # Add various quotes to mock response
        mock_llm_provider.generate.return_value["quotes"] = [
            {"text": "Short", "importance": 0.9},  # Too short
            {"text": "This is a reasonably long quote that should be included", "importance": 0.8},  # Good
            {"text": "This quote has lower importance score", "importance": 0.5},  # Low importance
            {"text": " ".join(["word"] * 60), "importance": 0.9}  # Too long
        ]
        
        extractor.llm_provider = mock_llm_provider
        
        # Extract quotes
        result = extractor.extract(sample_segment)
        
        # Should only include quotes meeting criteria
        assert len(result.quotes) == 1
        assert result.quotes[0]["importance"] >= 0.7
        assert len(result.quotes[0]["text"].split()) >= 10
        assert len(result.quotes[0]["text"].split()) <= 50
    
    def test_max_entities_limit(self, extractor, sample_segment, mock_llm_provider):
        """Test that entity extraction respects max limit."""
        # Create many entities
        many_entities = [
            {"name": f"Entity {i}", "type": "CONCEPT", "confidence": 0.8}
            for i in range(30)
        ]
        mock_llm_provider.generate.return_value["entities"] = many_entities
        
        extractor.llm_provider = mock_llm_provider
        extractor.config.max_entities_per_segment = 20
        
        # Extract entities
        result = extractor.extract(sample_segment)
        
        # Should limit to max entities (keeping highest confidence)
        assert len(result.entities) <= 20
    
    def test_dry_run_mode(self, extractor, sample_segment, mock_llm_provider):
        """Test dry run mode doesn't make actual LLM calls."""
        extractor.llm_provider = mock_llm_provider
        extractor.config.dry_run = True
        
        # Extract in dry run mode
        result = extractor.extract(sample_segment)
        
        # Should not call LLM in dry run
        mock_llm_provider.generate.assert_not_called()
        
        # Should return preview/mock result
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get("dry_run") is True
    
    def test_extraction_validation(self, extractor, sample_segment, mock_llm_provider):
        """Test validation of extracted content."""
        # Add invalid entities to mock response
        mock_llm_provider.generate.return_value["entities"].extend([
            {"name": "", "type": "PERSON", "confidence": 0.9},  # Empty name
            {"name": "Valid Entity", "type": "", "confidence": 0.9},  # Empty type
            {"name": "Another", "confidence": 0.9}  # Missing type
        ])
        
        extractor.llm_provider = mock_llm_provider
        extractor.config.validate_extractions = True
        
        # Extract with validation
        result = extractor.extract(sample_segment)
        
        # Should filter out invalid entities
        assert all(e.get("name") and e.get("type") for e in result.entities)
    
    def test_segment_metadata_preservation(self, extractor, sample_segment, mock_llm_provider):
        """Test that segment metadata is preserved in extraction."""
        extractor.llm_provider = mock_llm_provider
        
        # Add metadata to segment
        sample_segment.metadata = {
            "episode_id": "ep123",
            "podcast_name": "Tech Talk"
        }
        
        # Extract
        result = extractor.extract(sample_segment)
        
        # Should preserve segment metadata
        assert result.metadata.get("segment_start") == sample_segment.start_time
        assert result.metadata.get("segment_end") == sample_segment.end_time
        assert result.metadata.get("speaker") == sample_segment.speaker
    
    def test_extraction_with_no_content(self, extractor, mock_llm_provider):
        """Test extraction with empty or minimal content."""
        empty_segment = Segment(
            text="",
            start_time=0.0,
            end_time=1.0
        )
        
        extractor.llm_provider = mock_llm_provider
        
        # Extract from empty segment
        result = extractor.extract(empty_segment)
        
        # Should handle gracefully
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0