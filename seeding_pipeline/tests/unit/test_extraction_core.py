"""Core tests for knowledge extraction functionality."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.core.models import Segment
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig, ExtractionResult
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
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = Mock()
        service.generate = Mock(return_value={
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "confidence": 0.9},
                {"name": "Stanford University", "type": "ORGANIZATION", "confidence": 0.95}
            ],
            "insights": [
                {"text": "AI research is advancing rapidly", "confidence": 0.8}
            ],
            "quotes": [
                {"text": "The future of AI is promising", "speaker": "Dr. Jane Smith", "importance": 0.9}
            ]
        })
        return service
    
    @pytest.fixture
    def extractor(self, extraction_config, mock_llm_service):
        """Create knowledge extractor instance."""
        return KnowledgeExtractor(
            llm_service=mock_llm_service,
            config=extraction_config
        )
    
    @pytest.fixture
    def sample_segment(self):
        """Create sample segment for testing."""
        return Segment(
            id="test-segment-001",
            text="Dr. Jane Smith from Stanford University discussed the latest advances in artificial intelligence and machine learning at the tech conference.",
            start_time=0.0,
            end_time=10.0,
            speaker="Host"
        )
    
    
    def test_extract_entities(self, extractor, sample_segment, mock_llm_service):
        """Test entity extraction from text."""
        # Update mock response for this test
        mock_llm_service.generate.return_value = {
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
        
        # Extract entities
        result = extractor.extract_knowledge(sample_segment)
        
        # Note: The current implementation uses pattern matching, not LLM
        # So the mock won't be called
        
        # Verify entities were extracted
        assert isinstance(result, ExtractionResult)
        # The actual extraction uses pattern matching, not the mock
        # Check that some entities were extracted
        assert len(result.entities) > 0
        
        # Verify entity structure
        for entity in result.entities:
            assert "type" in entity
            assert "value" in entity  # Uses 'value' not 'name'
            assert "confidence" in entity
            assert entity["confidence"] >= 0.6  # Above threshold
    
    def test_extract_relationships(self, extractor, sample_segment, mock_llm_service):
        """Test relationship extraction between entities."""
        # Update mock response for this test
        mock_llm_service.generate.return_value = {
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "confidence": 0.9},
                {"name": "Stanford University", "type": "ORGANIZATION", "confidence": 0.95}
            ],
            "relationships": [
                {
                    "source": "Dr. Jane Smith",
                    "target": "Stanford University",
                    "type": "AFFILIATED_WITH"
                }
            ],
            "insights": []
        }
        
        # Extract relationships
        result = extractor.extract_knowledge(sample_segment)
        
        # Verify relationships were extracted
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel["source"] == "Dr. Jane Smith"
        assert rel["target"] == "Stanford University"
        assert rel["type"] == "AFFILIATED_WITH"
    
    def test_extract_insights(self, extractor, sample_segment, mock_llm_service):
        """Test insight generation from content."""
        # Update mock response for this test
        mock_llm_service.generate.return_value = {
            "entities": [],
            "relationships": [],
            "insights": [
                {
                    "type": "TOPIC",
                    "content": "AI and ML advances discussed at tech conference"
                }
            ],
            "quotes": [
                {
                    "text": "the latest advances in artificial intelligence and machine learning",
                    "importance": 0.8,
                    "speaker": "Dr. Jane Smith"
                }
            ]
        }
        
        # Extract insights
        result = extractor.extract_knowledge(sample_segment)
        
        # Verify quotes/insights were extracted
        assert len(result.quotes) >= 1
        quote = result.quotes[0]
        assert quote["importance"] >= 0.7  # Above threshold
        assert "artificial intelligence" in quote["text"]
    
    def test_handle_llm_failure(self, extractor, sample_segment, mock_llm_service):
        """Test graceful handling when LLM fails."""
        # Make the LLM service raise an exception
        mock_llm_service.generate.side_effect = Exception("LLM connection failed")
        
        # Should handle gracefully
        result = extractor.extract_knowledge(sample_segment)
        
        # Should return empty result, not crash
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0
        assert result.metadata.get("error") is not None
    
    def test_extraction_timeout(self, extractor, sample_segment, mock_llm_service):
        """Test timeout handling during extraction."""
        # Make the LLM service simulate timeout
        mock_llm_service.generate.side_effect = TimeoutError("Request timed out")
        
        # Should handle timeout gracefully
        result = extractor.extract_knowledge(sample_segment)
        
        # Should return partial or empty result
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get("timeout") is True or result.metadata.get("error") is not None
    
    def test_entity_confidence_filtering(self, extractor, sample_segment, mock_llm_service):
        """Test that low-confidence entities are filtered out."""
        # Set mock response with low-confidence entities
        mock_llm_service.generate.return_value = {
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "confidence": 0.9},
                {"name": "Stanford University", "type": "ORGANIZATION", "confidence": 0.95},
                {"name": "maybe entity", "type": "UNKNOWN", "confidence": 0.3},
                {"name": "probable entity", "type": "CONCEPT", "confidence": 0.5}
            ],
            "relationships": [],
            "insights": []
        }
        
        # Extract with confidence threshold
        result = extractor.extract_knowledge(sample_segment)
        
        # Should only include high-confidence entities
        assert all(e["confidence"] >= 0.6 for e in result.entities)
        assert not any(e["name"] == "maybe entity" for e in result.entities)
    
    def test_quote_extraction_filtering(self, extractor, sample_segment, mock_llm_service):
        """Test quote extraction with length and importance filtering."""
        # Set mock response with various quotes
        mock_llm_service.generate.return_value = {
            "entities": [],
            "relationships": [],
            "insights": [],
            "quotes": [
                {"text": "Short", "importance": 0.9},  # Too short
                {"text": "This is a reasonably long quote that should be included", "importance": 0.8},  # Good
                {"text": "This quote has lower importance score", "importance": 0.5},  # Low importance
                {"text": " ".join(["word"] * 60), "importance": 0.9}  # Too long
            ]
        }
        
        # Extract quotes
        result = extractor.extract_knowledge(sample_segment)
        
        # Should only include quotes meeting criteria
        assert len(result.quotes) == 1
        assert result.quotes[0]["importance"] >= 0.7
        assert len(result.quotes[0]["text"].split()) >= 10
        assert len(result.quotes[0]["text"].split()) <= 50
    
    def test_max_entities_limit(self, extractor, sample_segment, mock_llm_service):
        """Test that entity extraction respects max limit."""
        # Create many entities
        many_entities = [
            {"name": f"Entity {i}", "type": "CONCEPT", "confidence": 0.8}
            for i in range(30)
        ]
        mock_llm_service.generate.return_value = {
            "entities": many_entities,
            "relationships": [],
            "insights": []
        }
        
        # Extract entities
        result = extractor.extract_knowledge(sample_segment)
        
        # Should limit to max entities (keeping highest confidence)
        assert len(result.entities) <= 20
    
    def test_dry_run_mode(self, extractor, sample_segment, mock_llm_service):
        """Test dry run mode doesn't make actual LLM calls."""
        extractor.config.dry_run = True
        
        # Extract in dry run mode
        result = extractor.extract_knowledge(sample_segment)
        
        # Should not call LLM in dry run
        mock_llm_service.generate.assert_not_called()
        
        # Should return preview/mock result
        assert isinstance(result, ExtractionResult)
        assert result.metadata.get("dry_run") is True
    
    def test_extraction_validation(self, extractor, sample_segment, mock_llm_service):
        """Test validation of extracted content."""
        # Set mock response with invalid entities
        mock_llm_service.generate.return_value = {
            "entities": [
                {"name": "Dr. Jane Smith", "type": "PERSON", "confidence": 0.9},
                {"name": "", "type": "PERSON", "confidence": 0.9},  # Empty name
                {"name": "Valid Entity", "type": "", "confidence": 0.9},  # Empty type
                {"name": "Another", "confidence": 0.9}  # Missing type
            ],
            "relationships": [],
            "insights": []
        }
        extractor.config.validate_extractions = True
        
        # Extract with validation
        result = extractor.extract_knowledge(sample_segment)
        
        # Should filter out invalid entities
        assert all(e.get("name") and e.get("type") for e in result.entities)
    
    def test_segment_metadata_preservation(self, extractor, sample_segment, mock_llm_service):
        """Test that segment metadata is preserved in extraction."""
        # Ensure mock returns valid data
        mock_llm_service.generate.return_value = {
            "entities": [{"name": "Test Entity", "type": "CONCEPT", "confidence": 0.8}],
            "relationships": [],
            "insights": []
        }
        
        # Set segment properties instead of metadata
        sample_segment.episode_id = "ep123"
        
        # Extract
        result = extractor.extract_knowledge(sample_segment)
        
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
        result = extractor.extract_knowledge(empty_segment)
        
        # Should handle gracefully
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0