"""Tests for meaningful unit knowledge extraction."""

import pytest
from unittest.mock import Mock, MagicMock
from src.extraction.meaningful_unit_extractor import (
    MeaningfulUnitExtractor,
    MeaningfulUnitExtractionResult
)
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig, ExtractionResult
from src.services.segment_regrouper import MeaningfulUnit
from src.core.interfaces import TranscriptSegment


class TestMeaningfulUnitExtractor:
    """Test meaningful unit extraction functionality."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        return Mock()
    
    @pytest.fixture
    def base_extractor(self, mock_llm_service):
        """Create base knowledge extractor."""
        return KnowledgeExtractor(
            llm_service=mock_llm_service,
            config=ExtractionConfig()
        )
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for a meaningful unit."""
        return [
            TranscriptSegment(
                id="seg_0",
                text="Dr. Johnson discusses how machine learning is revolutionizing healthcare.",
                start_time=0.0,
                end_time=5.0,
                speaker="Dr. Johnson"
            ),
            TranscriptSegment(
                id="seg_1", 
                text="We've developed neural networks that can detect cancer earlier than ever before.",
                start_time=5.0,
                end_time=10.0,
                speaker="Dr. Johnson"
            ),
            TranscriptSegment(
                id="seg_2",
                text="The accuracy rates are incredible, exceeding 95% in clinical trials.",
                start_time=10.0,
                end_time=15.0,
                speaker="Dr. Johnson"
            )
        ]
    
    @pytest.fixture
    def sample_meaningful_unit(self, sample_segments):
        """Create sample meaningful unit."""
        return MeaningfulUnit(
            id="test_episode_001_unit_001_topic_discussion",
            segments=sample_segments,
            unit_type="topic_discussion",
            summary="Discussion of AI applications in cancer detection",
            themes=["Healthcare AI", "Cancer Detection"],
            start_time=0.0,
            end_time=15.0,
            speaker_distribution={"Dr. Johnson": 100.0},
            is_complete=True,
            metadata={
                "original_indices": {"start": 0, "end": 2},
                "completeness_note": "Complete discussion captured"
            }
        )
    
    def test_extract_from_unit_basic(self, base_extractor, sample_meaningful_unit):
        """Test basic extraction from meaningful unit."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        assert isinstance(result, MeaningfulUnitExtractionResult)
        assert result.unit_id == "test_episode_001_unit_001_topic_discussion"
        assert len(result.entities) > 0
        assert len(result.insights) > 0
        assert result.themes == ["Healthcare AI", "Cancer Detection"]
    
    def test_entity_deduplication(self, base_extractor, sample_meaningful_unit):
        """Test that entities are deduplicated across segments."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        # Mock the base extractor to return duplicate entities
        mock_result = ExtractionResult(
            entities=[
                {'type': 'PERSON', 'value': 'Dr. Johnson', 'confidence': 0.9, 'start_time': 0.0},
                {'type': 'CONCEPT', 'value': 'machine learning', 'confidence': 0.8, 'start_time': 0.0}
            ],
            quotes=[],
            relationships=[],
            metadata={}
        )
        base_extractor.extract_knowledge = Mock(return_value=mock_result)
        
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        # Check deduplication
        entity_values = [e['value'] for e in result.entities]
        assert len(entity_values) == len(set(entity_values))  # No duplicates
        
        # Check occurrence counting
        dr_johnson = next((e for e in result.entities if e['value'] == 'Dr. Johnson'), None)
        assert dr_johnson is not None
        assert dr_johnson['occurrences'] == 3  # Appears in all 3 segments
    
    def test_unit_level_insights(self, base_extractor, sample_meaningful_unit):
        """Test generation of unit-level insights."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        # Should have topic summary insight
        summary_insights = [i for i in result.insights if i.get('type') == 'SUMMARY']
        assert len(summary_insights) > 0
        assert sample_meaningful_unit.summary in summary_insights[0]['content']
        
        # Should have theme insights
        theme_insights = [i for i in result.insights if i.get('type') == 'THEME']
        assert len(theme_insights) > 0
    
    def test_quote_enhancement(self, base_extractor, sample_meaningful_unit):
        """Test that quotes are enhanced with unit context."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        # Mock base extractor to return a quote
        mock_result = ExtractionResult(
            entities=[],
            quotes=[{
                'type': 'Quote',
                'value': 'We can detect cancer earlier than ever before',
                'speaker': 'Dr. Johnson',
                'start_time': 7.0,
                'importance_score': 0.7,
                'confidence': 0.9
            }],
            relationships=[],
            metadata={}
        )
        base_extractor.extract_knowledge = Mock(return_value=mock_result)
        
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        assert len(result.quotes) == 3  # One per segment
        quote = result.quotes[0]
        assert quote['unit_id'] == sample_meaningful_unit.id
        assert quote['unit_type'] == 'topic_discussion'
        assert 'unit_context' in quote['properties']
        assert quote['properties']['unit_themes'] == ["Healthcare AI", "Cancer Detection"]
    
    def test_unit_relationships(self, base_extractor, sample_meaningful_unit):
        """Test creation of unit-level relationships."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        # Mock to return entities
        mock_result = ExtractionResult(
            entities=[
                {'type': 'CONCEPT', 'value': 'cancer detection', 'confidence': 0.9, 
                 'start_time': 0.0, 'occurrences': 2}
            ],
            quotes=[],
            relationships=[],
            metadata={}
        )
        base_extractor.extract_knowledge = Mock(return_value=mock_result)
        
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        # Should have theme-entity relationships
        theme_rels = [r for r in result.relationships if r['type'] == 'RELATED_TO_THEME']
        assert len(theme_rels) > 0
        
        # Should have speaker-topic relationships
        speaker_rels = [r for r in result.relationships if r['type'] == 'DISCUSSES']
        assert len(speaker_rels) > 0
        assert speaker_rels[0]['source'] == 'Dr. Johnson'
    
    def test_incomplete_unit_handling(self, base_extractor, sample_segments):
        """Test handling of incomplete units."""
        incomplete_unit = MeaningfulUnit(
            id="test_episode_001_unit_002_conclusion",
            segments=sample_segments,
            unit_type="conclusion",
            summary="Partial conclusion about future of AI in medicine",
            themes=["Future Outlook"],
            start_time=0.0,
            end_time=15.0,
            speaker_distribution={"Dr. Johnson": 100.0},
            is_complete=False,
            metadata={
                "completeness_note": "Cut off mid-sentence"
            }
        )
        
        extractor = MeaningfulUnitExtractor(base_extractor)
        result = extractor.extract_from_unit(incomplete_unit)
        
        # Should have meta insight about incompleteness
        meta_insights = [i for i in result.insights if i.get('type') == 'META']
        assert len(meta_insights) > 0
        assert 'incomplete' in meta_insights[0]['content'].lower()
    
    def test_batch_extraction(self, base_extractor, sample_meaningful_unit):
        """Test batch extraction from multiple units."""
        units = [sample_meaningful_unit] * 3  # Use same unit 3 times
        
        extractor = MeaningfulUnitExtractor(base_extractor)
        results = extractor.extract_from_units_batch(units)
        
        assert len(results) == 3
        assert all(isinstance(r, MeaningfulUnitExtractionResult) for r in results)
        assert all(r.unit_id == "test_episode_001_unit_001_topic_discussion" for r in results)
    
    def test_extraction_metadata(self, base_extractor, sample_meaningful_unit):
        """Test extraction metadata generation."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        episode_metadata = {'episode_id': 'ep123', 'podcast': 'AI Today'}
        result = extractor.extract_from_unit(sample_meaningful_unit, episode_metadata)
        
        metadata = result.metadata
        assert metadata['unit_id'] == sample_meaningful_unit.id
        assert metadata['unit_type'] == 'topic_discussion'
        assert metadata['extraction_mode'] == 'meaningful_unit'
        assert metadata['segment_count'] == 3
        assert metadata['unit_duration'] == 15.0
        assert metadata['is_complete_unit'] is True
        assert metadata['episode_metadata'] == episode_metadata
        assert 'extraction_time' in metadata
    
    def test_error_handling(self, base_extractor, sample_meaningful_unit):
        """Test error handling during extraction."""
        extractor = MeaningfulUnitExtractor(base_extractor)
        
        # Make base extractor raise an error
        base_extractor.extract_knowledge = Mock(side_effect=Exception("Extraction failed"))
        
        # Should still return a result, but with empty extractions
        result = extractor.extract_from_unit(sample_meaningful_unit)
        
        assert result.unit_id == sample_meaningful_unit.id
        assert len(result.entities) == 0
        assert len(result.quotes) == 0
        assert len(result.insights) > 0  # Still generates unit-level insights