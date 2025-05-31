"""Tests for consolidated knowledge extractor."""

from unittest.mock import Mock, patch

import pytest

from src.core.models import Segment
from src.processing.extraction import KnowledgeExtractor, ExtractionConfig
class TestKnowledgeExtractor:
    """Test suite for KnowledgeExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create knowledge extractor instance."""
        return KnowledgeExtractor(None, None)  # Mock services

    @pytest.fixture
    def sample_segment(self):
        """Create sample segment with quotes."""
        return Segment(
            start_time=10.5,
            end_time=45.3,
            text="""Dr. Smith said, "The future of AI is not about replacing humans, but augmenting them."
            
            Later, she added: "We need to think about AI ethics from day one, not as an afterthought."
            
            The host responded, "That's a fascinating perspective on the human-AI collaboration."
            
            As Dr. Smith emphasized, 'The key is finding the right balance between automation and human judgment.'""",
            speaker="Dr. Smith",
            confidence=0.95
        )

    @pytest.fixture
    def extraction_results(self):
        """Create sample SimpleKGPipeline extraction results."""
        return {
            "entities": [
                {"text": "Dr. Smith", "type": "PERSON"},
                {"text": "AI", "type": "TECHNOLOGY"},
                {"text": "AI ethics", "type": "CONCEPT"}
            ],
            "relationships": [
                {
                    "source": "Dr. Smith",
                    "target": "AI ethics",
                    "type": "DISCUSSES"
                }
            ]
        }

    def test_extract_quotes_basic(self, extractor, sample_segment):
        """Test basic quote extraction."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(sample_segment)
        
        assert "quotes" in result
        assert "metadata" in result
        
        quotes = result["quotes"]
        assert len(quotes) == 4
        
        # Check first quote
        first_quote = quotes[0]
        assert first_quote["text"] == "The future of AI is not about replacing humans, but augmenting them."
        assert first_quote["speaker"] == "Dr. Smith"
        assert first_quote["timestamp_start"] == 10.5
        assert first_quote["timestamp_end"] == 45.3
        assert "importance_score" in first_quote

    def test_extract_quotes_with_patterns(self, extractor, sample_segment):
        """Test different quote patterns."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(sample_segment)
        
        quotes = result["quotes"]
        
        # Check different quote patterns
        quote_texts = [q["text"] for q in quotes]
        assert "The future of AI is not about replacing humans, but augmenting them." in quote_texts
        assert "We need to think about AI ethics from day one, not as an afterthought." in quote_texts
        assert "That's a fascinating perspective on the human-AI collaboration." in quote_texts
        assert "The key is finding the right balance between automation and human judgment." in quote_texts

    def test_quote_validation(self, extractor):
        """Test quote validation against source."""
        segment = Segment(
            start_time=0,
            end_time=10,
            text='He said, "This is a test quote."',
            speaker="Speaker1"
        )
        
        # Valid quote
        quote = {
            "text": "This is a test quote.",
            "speaker": "Speaker1"
        }
        assert extractor._validate_quote(quote, segment.text) is True
        
        # Invalid quote (not in source)
        quote = {
            "text": "This quote doesn't exist.",
            "speaker": "Speaker1"
        }
        assert extractor._validate_quote(quote, segment.text) is False

    def test_importance_scoring(self, extractor):
        """Test quote importance scoring."""
        # Long, keyword-rich quote
        quote1 = {
            "text": "The breakthrough in artificial intelligence and machine learning has revolutionized how we approach complex problems in healthcare and scientific research.",
            "speaker": "Expert"
        }
        score1 = extractor._score_importance(quote1)
        
        # Short, simple quote
        quote2 = {
            "text": "Yes, I agree.",
            "speaker": "Host"
        }
        score2 = extractor._score_importance(quote2)
        
        # Score1 should be higher due to length and keywords
        assert score1 > score2
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1

    def test_integration_with_extraction_results(self, extractor, sample_segment, extraction_results):
        """Test integration with SimpleKGPipeline results."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(sample_segment, extraction_results)
        
        # Should have both quotes and integrated results
        assert "quotes" in result
        assert "integrated_results" in result
        
        integrated = result["integrated_results"]
        assert "entities" in integrated
        assert "relationships" in integrated
        assert "quotes" in integrated
        
        # Quotes should be added to entities
        quote_entities = [e for e in integrated["entities"] if e.get("type") == "QUOTE"]
        assert len(quote_entities) > 0

    def test_empty_segment(self, extractor):
        """Test extraction from segment with no quotes."""
        segment = Segment(
            start_time=0,
            end_time=10,
            text="This is just regular text without any quotes.",
            speaker="Speaker1"
        )
        
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(segment)
        
        assert result["quotes"] == []
        assert result["metadata"]["quotes_found"] == 0

    def test_malformed_quotes(self, extractor):
        """Test handling of malformed quotes."""
        segment = Segment(
            start_time=0,
            end_time=10,
            text='He said, "This quote is not closed properly',
            speaker="Speaker1"
        )
        
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(segment)
        
        # Should handle gracefully
        assert "quotes" in result
        assert "error" not in result

    def test_nested_quotes(self, extractor):
        """Test handling of nested quotes."""
        segment = Segment(
            start_time=0,
            end_time=10,
            text='''She said, "When he told me 'This is important', I knew it was serious."''',
            speaker="Speaker1"
        )
        
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(segment)
        
        # Should extract the outer quote
        assert len(result["quotes"]) >= 1
        assert "When he told me" in result["quotes"][0]["text"]

    def test_quote_relationships(self, extractor, sample_segment, extraction_results):
        """Test creation of quote relationships."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = extractor.extract_quotes(sample_segment, extraction_results)
        
        integrated = result["integrated_results"]
        relationships = integrated["relationships"]
        
        # Should have SPEAKS relationships
        speaks_rels = [r for r in relationships if r["type"] == "SPEAKS"]
        assert len(speaks_rels) > 0
        
        # Should have MENTIONS relationships for entities in quotes
        mentions_rels = [r for r in relationships if r["type"] == "MENTIONS"]
        assert len(mentions_rels) > 0

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_component_tracking(self, mock_log, extractor, sample_segment):
        """Test component tracking integration."""
        result = extractor.extract_quotes(sample_segment)
        
        # Should log execution
        assert mock_log.called
        
        # Check logged data
        call_args = mock_log.call_args[1]
        assert "input_size" in call_args
        assert "output_size" in call_args
        assert "contributions" in call_args
        assert call_args["contributions"]["quotes_extracted"] == len(result["quotes"])