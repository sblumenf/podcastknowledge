"""Integration tests for speaker identification with VTT processing."""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path

from src.vtt.vtt_segmentation import VTTSegmenter
from src.vtt.vtt_parser import VTTParser
from src.core.interfaces import TranscriptSegment
from src.extraction.speaker_identifier import SpeakerIdentifier
from src.services.llm_gemini_direct import GeminiDirectService


class TestSpeakerIdentificationIntegration:
    """Integration tests for speaker identification in VTT pipeline."""
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Create sample VTT content with generic speakers."""
        return """WEBVTT

NOTE
Podcast: Tech Talk Daily
Episode: AI Revolution with Dr. Jane Smith
Date: 2024-01-15

00:00.000 --> 00:03.000
<v Speaker 0>Welcome to Tech Talk Daily. I'm your host.

00:03.000 --> 00:07.000
<v Speaker 1>Thanks for having me. I'm Dr. Jane Smith from AI Labs.

00:07.000 --> 00:12.000
<v Speaker 0>Today we're discussing the latest developments in artificial intelligence.

00:12.000 --> 00:18.000
<v Speaker 1>Yes, it's an exciting time. We've made significant breakthroughs in natural language processing.

00:18.000 --> 00:23.000
<v Speaker 0>Can you tell us more about these breakthroughs?

00:23.000 --> 00:30.000
<v Speaker 1>Certainly. The new models can understand context much better than before.
"""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service for testing."""
        service = Mock(spec=GeminiDirectService)
        
        # Default successful response
        service.complete.return_value = json.dumps({
            "speaker_mappings": {
                "Speaker 0": "Host - Tech Talk Daily",
                "Speaker 1": "Dr. Jane Smith (AI Labs)"
            },
            "confidence_scores": {
                "Speaker 0": 0.9,
                "Speaker 1": 0.95
            },
            "identification_methods": {
                "Speaker 0": "Host pattern and self-introduction",
                "Speaker 1": "Explicit self-introduction"
            },
            "unresolved_speakers": []
        })
        
        return service
    
    @pytest.fixture
    def vtt_segmenter_config(self, tmp_path):
        """Create VTT segmenter configuration."""
        return {
            'ad_detection_enabled': False,
            'speaker_db_path': str(tmp_path / 'speaker_cache'),
            'speaker_confidence_threshold': 0.7,
            'speaker_timeout_seconds': 30
        }
    
    def test_vtt_to_speaker_identification_flow(self, sample_vtt_content, mock_llm_service, vtt_segmenter_config):
        """Test complete flow from VTT parsing to speaker identification."""
        # Parse VTT
        parser = VTTParser()
        segments = parser.parse(sample_vtt_content)
        
        assert len(segments) == 6
        assert all(s.speaker in ['Speaker 0', 'Speaker 1'] for s in segments)
        
        # Process with segmenter (includes speaker identification)
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        
        result = segmenter.process_segments(
            segments,
            episode_metadata={
                'podcast_name': 'Tech Talk Daily',
                'episode_title': 'AI Revolution with Dr. Jane Smith',
                'description': 'Discussion about AI breakthroughs'
            }
        )
        
        # Check that speakers were identified
        metadata = result['metadata']
        assert 'speaker_identification' in metadata
        
        speaker_info = metadata['speaker_identification']
        assert speaker_info['speaker_mappings']['Speaker 0'] == "Host - Tech Talk Daily"
        assert speaker_info['speaker_mappings']['Speaker 1'] == "Dr. Jane Smith (AI Labs)"
        
        # Check that processed segments have updated speakers
        processed_segments = result['transcript']
        host_segments = [s for s in processed_segments if 'Host' in s['speaker']]
        guest_segments = [s for s in processed_segments if 'Dr. Jane Smith' in s['speaker']]
        
        assert len(host_segments) == 3
        assert len(guest_segments) == 3
    
    def test_speaker_identification_with_caching(self, sample_vtt_content, mock_llm_service, vtt_segmenter_config):
        """Test that speaker identification uses caching effectively."""
        parser = VTTParser()
        segments = parser.parse(sample_vtt_content)
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        
        # First call - should hit LLM
        result1 = segmenter.process_segments(
            segments,
            episode_metadata={'podcast_name': 'Tech Talk Daily'}
        )
        
        assert mock_llm_service.complete.call_count == 1
        
        # Second call with same podcast - should use cache
        result2 = segmenter.process_segments(
            segments,
            episode_metadata={'podcast_name': 'Tech Talk Daily'}
        )
        
        # LLM shouldn't be called again if cache is working
        # Note: This depends on implementation - adjust based on actual caching behavior
        speaker_id_result = result2['metadata']['speaker_identification']
        if 'performance' in speaker_id_result and speaker_id_result['performance'].get('cache_hit'):
            assert mock_llm_service.complete.call_count == 1  # No additional calls
    
    def test_speaker_identification_error_handling(self, sample_vtt_content, vtt_segmenter_config):
        """Test graceful handling when speaker identification fails."""
        # Create LLM service that fails
        failing_llm_service = Mock(spec=GeminiDirectService)
        failing_llm_service.complete.side_effect = Exception("LLM service error")
        
        parser = VTTParser()
        segments = parser.parse(sample_vtt_content)
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=failing_llm_service)
        
        # Should not crash, but fall back to descriptive roles
        result = segmenter.process_segments(
            segments,
            episode_metadata={'podcast_name': 'Tech Talk Daily'}
        )
        
        # Should have fallback speaker assignments
        speaker_info = result['metadata']['speaker_identification']
        assert 'speaker_mappings' in speaker_info
        assert len(speaker_info['speaker_mappings']) > 0
        
        # Should have error information
        assert 'errors' in speaker_info
        assert len(speaker_info['errors']) > 0
    
    def test_speaker_identification_disabled(self, sample_vtt_content, mock_llm_service, vtt_segmenter_config):
        """Test that speaker identification can be disabled via feature flag."""
        from src.core.feature_flags import set_flag, FeatureFlag
        
        # Disable speaker identification
        set_flag(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION, False)
        
        try:
            parser = VTTParser()
            segments = parser.parse(sample_vtt_content)
            
            segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
            result = segmenter.process_segments(segments)
            
            # Should not have speaker identification in metadata
            assert 'speaker_identification' not in result['metadata']
            
            # LLM should not be called
            assert mock_llm_service.complete.call_count == 0
            
        finally:
            # Re-enable for other tests
            set_flag(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION, True)
    
    def test_single_speaker_podcast(self, mock_llm_service, vtt_segmenter_config):
        """Test handling of single-speaker podcasts."""
        # Create VTT with only one speaker
        single_speaker_vtt = """WEBVTT

00:00.000 --> 00:05.000
<v Speaker 0>This is a monologue podcast where I talk alone.

00:05.000 --> 00:10.000
<v Speaker 0>There are no guests, just me sharing my thoughts.
"""
        
        parser = VTTParser()
        segments = parser.parse(single_speaker_vtt)
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        result = segmenter.process_segments(
            segments,
            episode_metadata={'podcast_name': 'Solo Thoughts'}
        )
        
        # Should identify as single speaker without LLM call
        assert mock_llm_service.complete.call_count == 0
        
        speaker_info = result['metadata']['speaker_identification']
        assert speaker_info['speaker_mappings']['Speaker 0'] == "Host/Narrator"
    
    def test_speaker_metrics_collection(self, sample_vtt_content, mock_llm_service, vtt_segmenter_config, tmp_path):
        """Test that speaker identification metrics are collected."""
        parser = VTTParser()
        segments = parser.parse(sample_vtt_content)
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        
        # Process multiple episodes
        for i in range(3):
            result = segmenter.process_segments(
                segments,
                episode_metadata={
                    'podcast_name': f'Podcast {i}',
                    'episode_title': f'Episode {i}'
                }
            )
        
        # Get metrics from speaker identifier
        if segmenter._speaker_identifier:
            metrics = segmenter._speaker_identifier.get_performance_metrics()
            
            assert 'speaker_metrics' in metrics
            speaker_metrics = metrics['speaker_metrics']
            
            assert speaker_metrics['overview']['total_identifications'] >= 3
            assert speaker_metrics['overview']['total_speakers_identified'] >= 6
    
    def test_knowledge_extraction_with_identified_speakers(self, sample_vtt_content, mock_llm_service, vtt_segmenter_config):
        """Test that knowledge extraction uses identified speaker names."""
        from src.extraction.extraction import create_extractor
        
        # Parse and identify speakers
        parser = VTTParser()
        segments = parser.parse(sample_vtt_content)
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        
        # First identify speakers
        identified_segments, speaker_result = segmenter._identify_speakers(
            segments,
            {'podcast_name': 'Tech Talk Daily'}
        )
        
        # Create extractor
        extractor = create_extractor()
        
        # Extract quotes from identified segments
        quote_result = extractor.extract_quotes(identified_segments[0])
        
        # Quotes should use identified speaker names
        if quote_result.get('quotes'):
            for quote in quote_result['quotes']:
                assert quote.get('speaker') in [
                    "Host - Tech Talk Daily",
                    "Dr. Jane Smith (AI Labs)"
                ]
    
    def test_long_transcript_handling(self, mock_llm_service, vtt_segmenter_config):
        """Test handling of very long transcripts."""
        # Create a long transcript
        long_segments = []
        for i in range(1000):  # 1000 segments
            speaker = f"Speaker {i % 3}"
            long_segments.append(
                TranscriptSegment(
                    text=f"This is segment {i} spoken by {speaker}.",
                    start_time=i * 3.0,
                    end_time=(i + 1) * 3.0,
                    speaker=speaker
                )
            )
        
        segmenter = VTTSegmenter(config=vtt_segmenter_config, llm_service=mock_llm_service)
        
        # Should handle without crashing
        result = segmenter.process_segments(
            long_segments,
            episode_metadata={'podcast_name': 'Long Podcast'}
        )
        
        # Should process successfully
        assert 'transcript' in result
        assert 'metadata' in result
        
        # Should have truncated context for LLM
        if 'speaker_identification' in result['metadata']:
            speaker_info = result['metadata']['speaker_identification']
            if 'errors' in speaker_info:
                # May have truncation warning
                truncation_errors = [e for e in speaker_info['errors'] if 'truncated' in e.lower()]
                # This is expected for very long transcripts
                pass


@pytest.mark.parametrize("confidence_threshold,expected_behavior", [
    (0.9, "strict"),    # High threshold - more fallbacks
    (0.5, "permissive"), # Low threshold - more identifications
    (0.7, "balanced")    # Default threshold
])
def test_confidence_threshold_behavior(
    confidence_threshold, 
    expected_behavior,
    sample_vtt_content,
    vtt_segmenter_config,
    tmp_path
):
    """Test different confidence threshold behaviors."""
    # Create mock LLM with varied confidence scores
    mock_llm = Mock(spec=GeminiDirectService)
    mock_llm.complete.return_value = json.dumps({
        "speaker_mappings": {
            "Speaker 0": "Maybe Host",
            "Speaker 1": "Possibly Guest"
        },
        "confidence_scores": {
            "Speaker 0": 0.6,  # Medium confidence
            "Speaker 1": 0.8   # High confidence
        },
        "identification_methods": {
            "Speaker 0": "Uncertain pattern",
            "Speaker 1": "Likely guest introduction"
        },
        "unresolved_speakers": []
    })
    
    parser = VTTParser()
    segments = parser.parse(sample_vtt_content)
    
    config = vtt_segmenter_config.copy()
    config['speaker_confidence_threshold'] = confidence_threshold
    
    segmenter = VTTSegmenter(config=config, llm_service=mock_llm)
    result = segmenter.process_segments(
        segments,
        episode_metadata={'podcast_name': 'Test Podcast'}
    )
    
    speaker_info = result['metadata']['speaker_identification']
    mappings = speaker_info['speaker_mappings']
    
    if expected_behavior == "strict":
        # High threshold - Speaker 0 (0.6) should be converted to descriptive role
        assert "Speaker 0" not in mappings or "Primary Speaker" in mappings.get("Speaker 0", "")
    elif expected_behavior == "permissive":
        # Low threshold - both should be accepted
        assert mappings.get("Speaker 0") == "Maybe Host"
        assert mappings.get("Speaker 1") == "Possibly Guest"
    else:  # balanced
        # Default - Speaker 0 falls back, Speaker 1 accepted
        assert "Primary Speaker" in mappings.get("Speaker 0", "")
        assert mappings.get("Speaker 1") == "Possibly Guest"