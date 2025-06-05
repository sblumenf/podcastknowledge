"""Tests for knowledge extraction from VTT transcript segments."""

from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, MagicMock, patch
import os
import tempfile

import pytest

from src.core.interfaces import TranscriptSegment, LLMProvider
from src.extraction.extraction import EntityType, InsightType
from src.core.extraction_interface import Entity, Insight, Quote, QuoteType
from src.extraction.extraction import KnowledgeExtractor, ExtractionResult
from src.vtt.vtt_parser import VTTParser
from src.seeding.transcript_ingestion import TranscriptIngestion, VTTFile
class TestVTTKnowledgeExtraction:
    """Test suite for knowledge extraction from VTT segments."""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = MagicMock()
        # Set up default return value for process method
        provider.process.return_value = "{}"
        return provider
    
    @pytest.fixture
    def vtt_parser(self):
        """Create VTT parser instance."""
        return VTTParser()
    
    @pytest.fixture
    def extractor(self, mock_llm_provider):
        """Create KnowledgeExtractor instance."""
        return KnowledgeExtractor(
            llm_service=mock_llm_provider,
            embedding_service=None,
            config=None
        )
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Sample VTT content with rich dialogue."""
        return """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our podcast on artificial intelligence. Today we have Dr. Sarah Johnson with us.

00:00:05.000 --> 00:00:12.000
<v Dr. Johnson>Thank you for having me. I'm excited to discuss how machine learning is revolutionizing healthcare diagnostics.

00:00:12.000 --> 00:00:20.000
<v Host>Let's start with your recent work on cancer detection. Can you tell us about the 95% accuracy rate you achieved?

00:00:20.000 --> 00:00:30.000
<v Dr. Johnson>Certainly. We developed a neural network that analyzes medical imaging data. It can detect early-stage tumors that human radiologists might miss.

00:00:30.000 --> 00:00:38.000
<v Host>That's remarkable! What about the ethical implications of AI making medical decisions?

00:00:38.000 --> 00:00:48.000
<v Dr. Johnson>Ethics is crucial. We must ensure transparency, prevent bias, and maintain human oversight. AI should augment, not replace, human doctors.
"""

    @pytest.fixture
    def mock_vtt_segments(self):
        """Mock VTT segments for testing."""
        return [
            TranscriptSegment(
                id="seg_0",
                text="Welcome to our podcast on artificial intelligence. Today we have Dr. Sarah Johnson with us.",
                start_time=0.0,
                end_time=5.0,
                speaker="Host",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_1",
                text="Thank you for having me. I'm excited to discuss how machine learning is revolutionizing healthcare diagnostics.",
                start_time=5.0,
                end_time=12.0,
                speaker="Dr. Johnson",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_2",
                text="Let's start with your recent work on cancer detection. Can you tell us about the 95% accuracy rate you achieved?",
                start_time=12.0,
                end_time=20.0,
                speaker="Host",
                confidence=1.0
            ),
            TranscriptSegment(
                id="seg_3",
                text="Certainly. We developed a neural network that analyzes medical imaging data. It can detect early-stage tumors that human radiologists might miss.",
                start_time=20.0,
                end_time=30.0,
                speaker="Dr. Johnson",
                confidence=1.0
            )
        ]
    
    def test_vtt_to_segments_parsing(self, vtt_parser, sample_vtt_content):
        """Test parsing VTT content into segments."""
        segments = vtt_parser.parse_content(sample_vtt_content)
        
        assert len(segments) == 6
        assert segments[0].speaker == "Host"
        assert segments[1].speaker == "Dr. Johnson"
        assert "artificial intelligence" in segments[0].text
        assert "machine learning" in segments[1].text
    
    def test_extract_entities_from_vtt_segments(self, extractor, mock_llm_provider, mock_vtt_segments):
        """Test entity extraction from VTT segments."""
        # Combine segment texts
        full_text = "\n".join([f"{seg.speaker}: {seg.text}" for seg in mock_vtt_segments])
        
        # Mock LLM response for entity extraction
        mock_llm_provider.process.return_value = """
        Entities found:
        1. **Dr. Sarah Johnson** - Type: PERSON - AI researcher and healthcare expert
        2. **artificial intelligence** - Type: TECHNOLOGY - Main topic of the podcast
        3. **machine learning** - Type: TECHNOLOGY - Specific AI technology discussed
        4. **healthcare diagnostics** - Type: CONCEPT - Application area for AI
        5. **cancer detection** - Type: CONCEPT - Specific medical application
        6. **neural network** - Type: TECHNOLOGY - AI architecture used
        7. **medical imaging** - Type: TECHNOLOGY - Data type analyzed by AI
        """
        
        # Extract entities
        entities = extractor.extract_entities(full_text)
        
        assert len(entities) == 7
        assert any(e.name == "Dr. Sarah Johnson" for e in entities)
        assert any(e.name == "artificial intelligence" for e in entities)
        assert any(e.name == "neural network" for e in entities)
        
        # Verify entity types
        # Entity objects have 'type' attribute in extraction_interface
        person_entities = [e for e in entities if hasattr(e, 'type') and e.type == EntityType.PERSON.value]
        tech_entities = [e for e in entities if hasattr(e, 'type') and e.type == EntityType.CONCEPT.value]
        assert len(person_entities) == 1
        assert len(tech_entities) >= 3
    
    def test_extract_insights_from_vtt_segments(self, extractor, mock_llm_provider, mock_vtt_segments):
        """Test insight extraction from VTT segments."""
        # Combine segment texts
        full_text = "\n".join([f"{seg.speaker}: {seg.text}" for seg in mock_vtt_segments])
        
        # Mock LLM response for insights
        mock_llm_provider.process.return_value = """
        Key insights:
        1. **AI achieves 95% accuracy in cancer detection** - Machine learning models can identify tumors with higher accuracy than traditional methods
        2. **Early detection of tumors** - Neural networks can identify early-stage cancers that humans might miss
        3. **AI revolutionizing healthcare** - Machine learning is transforming diagnostic capabilities in medicine
        """
        
        # Extract insights
        insights = extractor.extract_insights(full_text)
        
        assert len(insights) >= 3
        assert any("95% accuracy" in i.content for i in insights)
        assert any("Early detection" in i.content for i in insights)
        # Insights have different structure in extraction_interface
        assert all(hasattr(i, 'content') for i in insights)
    
    def test_extract_quotes_from_vtt_segments(self, extractor, mock_llm_provider, mock_vtt_segments):
        """Test quote extraction from VTT segments."""
        # Format segments with speakers
        formatted_segments = []
        for seg in mock_vtt_segments:
            formatted_segments.append({
                'speaker': seg.speaker,
                'text': seg.text,
                'start_time': seg.start_time,
                'end_time': seg.end_time
            })
        
        # Mock LLM response for quotes
        mock_llm_provider.process.return_value = """
        Notable quotes:
        1. "I'm excited to discuss how machine learning is revolutionizing healthcare diagnostics." - Dr. Johnson - Shows enthusiasm for AI in healthcare
        2. "We developed a neural network that analyzes medical imaging data. It can detect early-stage tumors that human radiologists might miss." - Dr. Johnson - Highlights AI's superior detection capabilities
        """
        
        # Extract quotes
        quotes = extractor.extract_quotes(formatted_segments)
        
        assert len(quotes) >= 2
        assert all(q.speaker == "Dr. Johnson" for q in quotes)
        assert any("machine learning" in q.text for q in quotes)
        assert any("neural network" in q.text for q in quotes)
    
    def test_full_extraction_pipeline_with_vtt(self, extractor, mock_llm_provider, vtt_parser, sample_vtt_content):
        """Test complete extraction pipeline with VTT input."""
        # Parse VTT to segments
        segments = vtt_parser.parse_content(sample_vtt_content)
        
        # Mock all LLM responses
        mock_llm_provider.process.side_effect = [
            # Entities response
            """
            Entities:
            1. **Dr. Sarah Johnson** - Type: PERSON - AI researcher
            2. **artificial intelligence** - Type: TECHNOLOGY - Main topic
            3. **healthcare** - Type: CONCEPT - Application domain
            """,
            # Insights response
            """
            Insights:
            1. **AI achieving 95% accuracy** - Revolutionary performance in medical diagnosis
            2. **Ethics in AI healthcare** - Importance of transparency and human oversight
            """,
            # Quotes response
            """
            Quotes:
            1. "AI should augment, not replace, human doctors." - Dr. Johnson - Ethical stance on AI role
            """,
            # Topics response
            """
            Topics:
            1. Artificial Intelligence in Healthcare
            2. Medical Imaging and Diagnostics
            3. AI Ethics and Transparency
            """
        ]
        
        # Extract all knowledge
        full_text = "\n".join([f"{seg.speaker}: {seg.text}" for seg in segments])
        formatted_segments = [{'speaker': seg.speaker, 'text': seg.text} for seg in segments]
        
        entities = extractor.extract_entities(full_text)
        insights = extractor.extract_insights(full_text)
        quotes = extractor.extract_quotes(formatted_segments)
        topics = extractor.extract_topics(full_text)
        
        # Verify extraction results
        assert len(entities) >= 3
        assert len(insights) >= 2
        assert len(quotes) >= 1
        assert len(topics) >= 3
        
        # Create extraction result
        result = ExtractionResult(
            entities=entities,
            insights=insights,
            quotes=quotes,
            topics=topics,
            metadata={
                'source': 'vtt',
                'segment_count': len(segments),
                'duration': segments[-1].end_time if segments else 0
            }
        )
        
        assert result.metadata['segment_count'] == 6
        assert result.metadata['duration'] == 48.0  # Last segment ends at 48s
    
    def test_extraction_with_merged_segments(self, extractor, mock_llm_provider, vtt_parser):
        """Test extraction with merged short segments."""
        # VTT with very short segments
        short_vtt = """WEBVTT

00:00:00.000 --> 00:00:01.000
<v Speaker1>Hello

00:00:01.000 --> 00:00:01.500
<v Speaker1>everyone,

00:00:01.500 --> 00:00:03.000
<v Speaker1>welcome to our show.

00:00:03.000 --> 00:00:05.000
<v Speaker2>Thanks for having me!
"""
        
        # Parse and merge segments
        segments = vtt_parser.parse_content(short_vtt)
        merged_segments = vtt_parser.merge_short_segments(segments, min_duration=2.0)
        
        # Should merge first 3 segments
        assert len(merged_segments) == 2
        assert merged_segments[0].text == "Hello everyone, welcome to our show."
        assert merged_segments[0].speaker == "Speaker1"
        assert merged_segments[1].text == "Thanks for having me!"
        assert merged_segments[1].speaker == "Speaker2"
    
    def test_extraction_preserves_segment_metadata(self, extractor, vtt_parser):
        """Test that extraction preserves VTT segment metadata."""
        vtt_with_metadata = """WEBVTT
Kind: captions
Language: en

NOTE
This is a test transcript

00:00:00.000 --> 00:00:05.000 align:start position:0%
<v Dr. Smith>Testing metadata preservation.

00:00:05.000 --> 00:00:10.000 align:middle position:50%
<v Host>Indeed, metadata is important.
"""
        
        segments = vtt_parser.parse_content(vtt_with_metadata)
        
        assert len(segments) == 2
        assert segments[0].speaker == "Dr. Smith"
        assert segments[0].confidence == 1.0  # VTT always has confidence 1.0
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 5.0
    
    def test_empty_vtt_extraction(self, extractor, vtt_parser):
        """Test handling of empty VTT file."""
        empty_vtt = "WEBVTT\n\n"
        
        segments = vtt_parser.parse_content(empty_vtt)
        assert len(segments) == 0
        
        # Extraction should handle empty segments gracefully
        # (Implementation would need to handle this case)
    
    def test_vtt_extraction_error_handling(self, extractor, mock_llm_provider, vtt_parser):
        """Test error handling in VTT extraction pipeline."""
        # VTT with valid format but LLM fails
        valid_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>This is a test segment.
"""
        
        segments = vtt_parser.parse_content(valid_vtt)
        
        # Mock LLM failure
        mock_llm_provider.process.side_effect = Exception("LLM API error")
        
        # Extraction should handle errors gracefully
        with pytest.raises(Exception):
            extractor.extract_entities("\n".join([seg.text for seg in segments]))
    
    def test_vtt_segment_id_preservation(self, vtt_parser):
        """Test that segment IDs are properly assigned and preserved."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000
First segment

00:00:02.000 --> 00:00:04.000
Second segment

00:00:04.000 --> 00:00:06.000
Third segment
"""
        
        segments = vtt_parser.parse_content(vtt_content)
        
        assert segments[0].id == "seg_0"
        assert segments[1].id == "seg_1"
        assert segments[2].id == "seg_2"
        
        # After merging, IDs should be reassigned
        merged = vtt_parser.merge_short_segments(segments, min_duration=3.0)
        assert merged[0].id == "seg_0"
        if len(merged) > 1:
            assert merged[1].id == "seg_1"