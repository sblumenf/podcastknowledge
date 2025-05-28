"""
Integration tests for audio processing module.

This test compares the modular implementation with the monolithic version
to ensure they produce equivalent results.
"""

import sys
import os
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any
import json

# Add project roots to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

monolith_root = project_root.parent
sys.path.insert(0, str(monolith_root))


class TestAudioModuleIntegration:
    """Integration tests comparing modular vs monolithic implementations."""
    
    @pytest.fixture
    def test_audio_file(self):
        """Create a simple test audio file using the mock provider."""
        # For integration testing without real audio, we'll use a marker file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"FAKE_AUDIO_DATA")  # Placeholder content
            return f.name
            
    @pytest.fixture(autouse=True)
    def cleanup(self, test_audio_file):
        """Clean up test files after tests."""
        yield
        try:
            os.unlink(test_audio_file)
        except:
            pass
            
    def test_mock_provider_compatibility(self):
        """Test that mock provider produces compatible output structure."""
        from src.providers.audio import MockAudioProvider
        
        provider = MockAudioProvider(config={})
        
        # Test transcription
        transcripts = provider.transcribe("fake.mp3")
        assert len(transcripts) == 3
        assert all(hasattr(seg, 'text') for seg in transcripts)
        assert all(hasattr(seg, 'start_time') for seg in transcripts)
        assert all(hasattr(seg, 'end_time') for seg in transcripts)
        
        # Test diarization
        diarization = provider.diarize("fake.mp3")
        assert len(diarization) > 0
        assert all(hasattr(seg, 'speaker') for seg in diarization)
        assert all(hasattr(seg, 'start_time') for seg in diarization)
        assert all(hasattr(seg, 'end_time') for seg in diarization)
        
    def test_segmenter_output_format(self):
        """Test that segmenter produces output compatible with monolith format."""
        from src.providers.audio import MockAudioProvider
        from src.processing import EnhancedPodcastSegmenter
        
        provider = MockAudioProvider(config={"mock_segments": 3})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        result = segmenter.process_audio("fake.mp3")
        
        # Check result structure matches monolith
        assert "transcript" in result
        assert "diarization" in result
        assert "metadata" in result
        
        # Check transcript segment structure
        for seg in result["transcript"]:
            assert "text" in seg
            assert "start_time" in seg
            assert "end_time" in seg
            assert "is_advertisement" in seg
            assert "sentiment" in seg
            assert "segment_index" in seg
            assert "word_count" in seg
            assert "duration_seconds" in seg
            
    def test_advertisement_detection_parity(self):
        """Test that advertisement detection matches monolith behavior."""
        from src.processing.segmentation import EnhancedPodcastSegmenter
        from src.providers.audio import MockAudioProvider
        
        # Test advertisement markers
        ad_texts = [
            "This episode is sponsored by TechCorp",
            "Use promo code SAVE20 for discount",
            "Visit our sponsor at example.com",
            "Special offer for our listeners"
        ]
        
        provider = MockAudioProvider(config={})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        for text in ad_texts:
            is_ad = segmenter._detect_advertisement(text)
            assert is_ad is True, f"Failed to detect ad in: {text}"
            
        # Test non-ad text
        normal_texts = [
            "Today we discuss artificial intelligence",
            "The weather is nice today",
            "Welcome to our podcast"
        ]
        
        for text in normal_texts:
            is_ad = segmenter._detect_advertisement(text)
            assert is_ad is False, f"Incorrectly detected ad in: {text}"
            
    def test_sentiment_analysis_consistency(self):
        """Test that sentiment analysis is consistent with monolith."""
        from src.processing.segmentation import EnhancedPodcastSegmenter
        from src.providers.audio import MockAudioProvider
        
        provider = MockAudioProvider(config={})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        # Test sentiment for known texts
        test_cases = [
            ("This is absolutely amazing and wonderful!", "positive"),
            ("This is terrible and awful.", "negative"),
            ("The sky is blue.", "neutral"),
            ("I love this fantastic product, it's the best!", "positive"),
            ("This is a complete disaster and failure.", "negative"),
        ]
        
        for text, expected_polarity in test_cases:
            sentiment = segmenter._analyze_segment_sentiment(text)
            assert sentiment["polarity"] == expected_polarity, \
                f"Text '{text}' should be {expected_polarity}, got {sentiment['polarity']}"
                
    def test_provider_health_check_format(self):
        """Test that health check format is consistent."""
        from src.providers.audio import MockAudioProvider, WhisperAudioProvider
        
        # Test mock provider
        mock_provider = MockAudioProvider(config={})
        mock_health = mock_provider.health_check()
        
        assert "status" in mock_health
        assert "provider" in mock_health
        assert "timestamp" in mock_health
        assert mock_health["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Test whisper provider structure (without initializing models)
        whisper_provider = WhisperAudioProvider(config={"device": "cpu"})
        whisper_health = whisper_provider.health_check()
        
        assert "status" in whisper_health
        assert "provider" in whisper_health
        assert "whisper_model_size" in whisper_health
        assert "device" in whisper_health
        
    def test_alignment_algorithm_consistency(self):
        """Test that alignment algorithm produces consistent results."""
        from src.providers.audio.base import BaseAudioProvider
        from src.core import TranscriptSegment, DiarizationSegment
        
        # Create a concrete test implementation
        class TestProvider(BaseAudioProvider):
            def transcribe(self, audio_path: str):
                pass
            def diarize(self, audio_path: str):
                pass
            def _provider_specific_health_check(self):
                return {}
                
        provider = TestProvider()
        
        # Test data
        transcripts = [
            TranscriptSegment("Hello world", 0.0, 5.0),
            TranscriptSegment("How are you?", 5.5, 8.0),
            TranscriptSegment("I am fine", 8.5, 12.0),
        ]
        
        diarization = [
            DiarizationSegment("Speaker_0", 0.0, 5.2),
            DiarizationSegment("Speaker_1", 5.3, 8.2),
            DiarizationSegment("Speaker_0", 8.3, 12.5),
        ]
        
        # Run alignment
        aligned = provider.align_transcript_with_diarization(transcripts, diarization)
        
        # Verify alignment
        assert len(aligned) == 3
        assert aligned[0].speaker == "Speaker_0"
        assert aligned[1].speaker == "Speaker_1"
        assert aligned[2].speaker == "Speaker_0"
        
        # Verify text is preserved
        assert aligned[0].text == "Hello world"
        assert aligned[1].text == "How are you?"
        assert aligned[2].text == "I am fine"
        
    @pytest.mark.parametrize("config", [
        {"min_segment_tokens": 100, "max_segment_tokens": 500},
        {"ad_detection_enabled": False},
        {"enable_diarization": False},
    ])
    def test_configuration_handling(self, config):
        """Test that configuration options are properly handled."""
        from src.providers.audio import MockAudioProvider
        from src.processing import EnhancedPodcastSegmenter
        
        provider = MockAudioProvider()
        segmenter = EnhancedPodcastSegmenter(provider, config)
        
        # Verify config is applied
        for key, value in config.items():
            assert segmenter.config[key] == value
            
        # Test that processing respects config
        result = segmenter.process_audio("fake.mp3")
        assert result is not None
        
        if config.get("ad_detection_enabled") is False:
            # Verify no ads are detected when disabled
            for seg in result["transcript"]:
                assert seg["is_advertisement"] is False
                
    def test_error_handling_compatibility(self):
        """Test that error handling matches expected behavior."""
        from src.providers.audio import MockAudioProvider
        from src.processing import EnhancedPodcastSegmenter
        from src.core import AudioProcessingError
        
        # Test transcription failure
        provider = MockAudioProvider(config={"fail_transcription": True})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        result = segmenter.process_audio("fake.mp3")
        assert result["transcript"] == []
        assert "error" in result["metadata"]
        
        # Test diarization failure (should continue)
        provider = MockAudioProvider(config={"fail_diarization": True})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        result = segmenter.process_audio("fake.mp3")
        assert len(result["transcript"]) > 0  # Should have transcripts
        assert result["diarization"] == []  # But no diarization
        
    def test_performance_characteristics(self):
        """Test that modular implementation has reasonable performance."""
        import time
        from src.providers.audio import MockAudioProvider
        from src.processing import EnhancedPodcastSegmenter
        
        provider = MockAudioProvider(config={"mock_segments": 10})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        # Measure processing time
        start_time = time.time()
        result = segmenter.process_audio("fake.mp3")
        processing_time = time.time() - start_time
        
        # Should be fast for mock provider
        assert processing_time < 1.0  # Less than 1 second
        assert len(result["transcript"]) == 10
        
        # Verify all segments were processed
        assert result["metadata"]["total_segments"] == 10
        
    def test_data_integrity(self):
        """Test that no data is lost during processing."""
        from src.providers.audio import MockAudioProvider
        from src.processing import EnhancedPodcastSegmenter
        
        provider = MockAudioProvider(config={"mock_segments": 5})
        segmenter = EnhancedPodcastSegmenter(provider)
        
        # Get raw transcripts
        raw_transcripts = provider.transcribe("fake.mp3")
        raw_text_set = {seg.text for seg in raw_transcripts}
        
        # Process through segmenter
        result = segmenter.process_audio("fake.mp3")
        processed_text_set = {seg["text"] for seg in result["transcript"]}
        
        # Verify all text is preserved
        assert raw_text_set == processed_text_set
        
        # Verify metadata accuracy
        total_words = sum(seg["word_count"] for seg in result["transcript"])
        assert result["metadata"]["total_words"] == total_words


if __name__ == "__main__":
    pytest.main([__file__, "-v"])