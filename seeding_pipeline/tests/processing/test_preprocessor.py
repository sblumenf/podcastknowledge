"""
Unit tests for schemaless preprocessor.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.processing.preprocessor import (
    TextPreprocessor,
    PreprocessingConfig,
    preprocess_segments_batch
)
from src.core.models import Segment
from src.core.interfaces import TranscriptSegment


class TestTextPreprocessor:
    """Test cases for TextPreprocessor."""
    
    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return Segment(
            id="seg_123",
            text="This is a test segment about artificial intelligence.",
            start_time=15.5,
            end_time=20.3,
            speaker="Dr. Smith",
            confidence=0.95
        )
    
    @pytest.fixture
    def episode_metadata(self):
        """Create sample episode metadata."""
        return {
            "id": "ep_456",
            "title": "AI and the Future",
            "podcast_name": "Tech Talks"
        }
    
    @pytest.fixture
    def preprocessor(self):
        """Create a preprocessor instance."""
        return TextPreprocessor()
    
    def test_preprocessor_initialization(self):
        """Test preprocessor initializes with default config."""
        preprocessor = TextPreprocessor()
        assert preprocessor.config.inject_timestamps
        assert preprocessor.config.inject_speakers
        assert preprocessor.config.inject_segment_id
        assert preprocessor.config.inject_episode_context
    
    def test_custom_config(self):
        """Test preprocessor with custom configuration."""
        config = PreprocessingConfig(
            inject_timestamps=False,
            inject_speakers=True,
            speaker_format="[WHO: {speaker}]"
        )
        preprocessor = TextPreprocessor(config)
        assert not preprocessor.config.inject_timestamps
        assert preprocessor.config.speaker_format == "[WHO: {speaker}]"
    
    def test_inject_temporal_context(self, preprocessor):
        """Test timestamp injection."""
        text = "This is a test."
        enriched = preprocessor.inject_temporal_context(text, 10.5, 15.3)
        
        assert "[TIME: 10.5-15.3s]" in enriched
        assert enriched.startswith("[TIME:")
        assert text in enriched
        assert "[TIME: 10.5-15.3s]" in preprocessor.markers_added
    
    def test_inject_speaker_context(self, preprocessor):
        """Test speaker injection."""
        text = "This is a test."
        enriched = preprocessor.inject_speaker_context(text, "John Doe")
        
        assert "[SPEAKER: John Doe]" in enriched
        assert enriched.startswith("[SPEAKER:")
        assert text in enriched
        assert "[SPEAKER: John Doe]" in preprocessor.markers_added
    
    def test_inject_speaker_after_timestamp(self, preprocessor):
        """Test speaker injection when timestamp is already present."""
        text = "[TIME: 10.0-15.0s] This is a test."
        enriched = preprocessor.inject_speaker_context(text, "Jane Doe")
        
        assert "[TIME: 10.0-15.0s] [SPEAKER: Jane Doe]" in enriched
        assert enriched.index("[SPEAKER:") > enriched.index("[TIME:")
    
    def test_preprocess_segment_full(self, preprocessor, sample_segment, episode_metadata):
        """Test full segment preparation with all metadata."""
        with patch('src.utils.component_tracker.get_tracker') as mock_tracker:
            mock_tracker.return_value = MagicMock()
            
            result = preprocessor.preprocess_segment(
                sample_segment,
                episode_metadata,
                episode_id="ep_456",
                segment_id="seg_123"
            )
        
        assert "processed_text" in result
        assert "original_text" in result
        assert "metrics" in result
        
        enriched = result["processed_text"]
        assert "[SEGMENT: seg_123]" in enriched
        assert "[EPISODE: AI and the Future]" in enriched
        assert "[TIME: 15.5-20.3s]" in enriched
        assert "[SPEAKER: Dr. Smith]" in enriched
        assert sample_segment.text in enriched
    
    def test_prepare_segment_minimal(self, preprocessor):
        """Test segment preparation with minimal data."""
        segment = Segment(
            id=None,
            text="Simple text",
            start_time=None,
            end_time=None,
            speaker=None
        )
        
        result = preprocessor.preprocess_segment(segment, {})
        enriched = result["processed_text"]
        
        # Should have minimal modifications
        assert "[TIME:" not in enriched
        assert "[SPEAKER:" not in enriched
        assert "[SEGMENT:" not in enriched
        assert "Simple text" in enriched
    
    def test_dry_run_mode(self, sample_segment, episode_metadata):
        """Test preview mode without applying changes."""
        config = PreprocessingConfig(dry_run=True)
        preprocessor = TextPreprocessor(config)
        
        result = preprocessor.preprocess_segment(sample_segment, episode_metadata)
        
        assert "would_inject" in result
        assert "preview_text" in result
        assert "original_text" in result
        assert len(result["would_inject"]) > 0
    
    def test_format_for_extraction(self, preprocessor):
        """Test text formatting for optimal extraction."""
        text = "[SEGMENT: 1]  [TIME: 1.0-2.0s]   Multiple   spaces   here."
        formatted = preprocessor.format_for_extraction(text)
        
        # Should normalize spacing
        assert "  " not in formatted
        assert "] [" in formatted  # Proper marker separation
    
    def test_extract_metadata_from_enriched(self, preprocessor):
        """Test metadata extraction from enriched text."""
        enriched = "[SEGMENT: seg_123] [EPISODE: Test Episode] [TIME: 10.5-15.3s] [SPEAKER: John] Test content here."
        
        metadata = preprocessor.extract_metadata_from_enriched(enriched)
        
        assert metadata["segment_id"] == "seg_123"
        assert metadata["episode_title"] == "Test Episode"
        assert metadata["start_time"] == 10.5
        assert metadata["end_time"] == 15.3
        assert metadata["speaker"] == "John"
        assert metadata["clean_text"] == "Test content here."
    
    def test_preprocessing_metrics(self, preprocessor):
        """Test metric calculation."""
        original = "Short text"
        enriched = "[TIME: 1.0-2.0s] [SPEAKER: John] Short text"
        preprocessor.markers_added = ["[TIME: 1.0-2.0s]", "[SPEAKER: John]"]
        
        metrics = preprocessor.get_preprocessing_metrics(original, enriched)
        
        assert metrics["type"] == "preprocessing"
        assert metrics["details"]["original_length"] == len(original)
        assert metrics["details"]["enriched_length"] == len(enriched)
        assert metrics["details"]["markers_injected"] == 2
        assert "TIME" in metrics["details"]["marker_types"]
        assert "SPEAKER" in metrics["details"]["marker_types"]
    
    def test_configurable_preprocessing(self, sample_segment, episode_metadata):
        """Test selective preprocessing based on config."""
        config = PreprocessingConfig(
            inject_timestamps=True,
            inject_speakers=False,
            inject_segment_id=False,
            inject_episode_context=False
        )
        preprocessor = TextPreprocessor(config)
        
        result = preprocessor.preprocess_segment(sample_segment, episode_metadata)
        enriched = result["processed_text"]
        
        assert "[TIME:" in enriched
        assert "[SPEAKER:" not in enriched
        assert "[SEGMENT:" not in enriched
        assert "[EPISODE:" not in enriched
    
    def test_custom_format_strings(self, sample_segment):
        """Test custom format strings for markers."""
        config = PreprocessingConfig(
            timestamp_format="<t:{start}-{end}>",
            speaker_format="<s:{speaker}>",
            segment_format="<seg:{id}>",
            episode_format="<ep:{title}>"
        )
        preprocessor = TextPreprocessor(config)
        
        result = preprocessor.preprocess_segment(
            sample_segment, 
            {"title": "Test Episode"}
        )
        enriched = result["processed_text"]
        
        assert "<t:15.5-20.3>" in enriched
        assert "<s:Dr. Smith>" in enriched
        assert "<seg:seg_123>" in enriched
        assert "<ep:Test Episode>" in enriched


class TestBatchProcessing:
    """Test batch preprocessing functionality."""
    
    def test_preprocess_segments_batch(self):
        """Test batch processing of multiple segments."""
        segments = [
            Segment(
                id=f"seg_{i}",
                text=f"Segment {i} text",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                speaker=f"Speaker_{i % 2}"
            )
            for i in range(3)
        ]
        
        episode_metadata = {"title": "Batch Test Episode"}
        
        results = preprocess_segments_batch(segments, episode_metadata)
        
        assert len(results) == 3
        
        for i, result in enumerate(results):
            assert "processed_text" in result
            assert f"Segment {i} text" in result["processed_text"]
            assert f"[TIME: {i * 10.0}-{(i + 1) * 10.0}s]" in result["processed_text"]
            assert f"[SPEAKER: Speaker_{i % 2}]" in result["processed_text"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_text(self):
        """Test handling of empty segment text."""
        segment = Segment(id="empty", text="", start_time=0, end_time=1)
        preprocessor = TextPreprocessor()
        
        result = preprocessor.preprocess_segment(segment, {})
        assert result["processed_text"] != ""  # Should have markers even if text is empty
    
    def test_none_values(self):
        """Test handling of None values in segment."""
        segment = Segment(
            id="test",
            text="Test text",
            start_time=None,
            end_time=None,
            speaker=None
        )
        preprocessor = TextPreprocessor()
        
        result = preprocessor.preprocess_segment(segment, {})
        enriched = result["processed_text"]
        
        assert "[TIME:" not in enriched  # Should skip if times are None
        assert "[SPEAKER:" not in enriched  # Should skip if speaker is None
        assert "Test text" in enriched
    
    def test_special_characters_in_metadata(self):
        """Test handling of special characters in metadata."""
        segment = Segment(
            id="test",
            text="Test text",
            start_time=10,
            end_time=20,
            speaker="Dr. Smith [PhD]"
        )
        preprocessor = TextPreprocessor()
        
        result = preprocessor.preprocess_segment(segment, {"title": "Episode: \"AI & ML\""})
        enriched = result["processed_text"]
        
        # Should handle special characters properly
        assert "[SPEAKER: Dr. Smith [PhD]]" in enriched
        assert "[EPISODE: Episode: \"AI & ML\"]" in enriched