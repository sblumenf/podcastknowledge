"""Unit tests for audio providers."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from src.providers.audio import (
    BaseAudioProvider,
    WhisperAudioProvider,
    MockAudioProvider,
)
from src.core import (
    TranscriptSegment,
    DiarizationSegment,
    AudioProcessingError,
)


class TestMockAudioProvider:
    """Test the mock audio provider."""
    
    def test_mock_provider_initialization(self):
        """Test mock provider initialization."""
        provider = MockAudioProvider()
        assert provider.mock_segments == 5
        assert provider.mock_speakers == 2
        assert provider._initialized is True
        
    def test_mock_transcription(self):
        """Test mock transcription returns expected segments."""
        provider = MockAudioProvider(config={"mock_segments": 3})
        
        segments = provider.transcribe("fake_audio.mp3")
        
        assert len(segments) == 3
        assert all(isinstance(s, TranscriptSegment) for s in segments)
        assert all(s.text for s in segments)
        assert all(s.start_time < s.end_time for s in segments)
        
    def test_mock_diarization(self):
        """Test mock diarization returns expected segments."""
        provider = MockAudioProvider(config={
            "mock_segments": 3,
            "mock_speakers": 2
        })
        
        segments = provider.diarize("fake_audio.mp3")
        
        assert len(segments) > 0
        assert all(isinstance(s, DiarizationSegment) for s in segments)
        assert all(s.speaker in ["Speaker_0", "Speaker_1"] for s in segments)
        
    def test_mock_failure_modes(self):
        """Test mock provider can simulate failures."""
        # Test transcription failure
        provider = MockAudioProvider(config={"fail_transcription": True})
        with pytest.raises(AudioProcessingError):
            provider.transcribe("fake_audio.mp3")
            
        # Test diarization failure
        provider = MockAudioProvider(config={"fail_diarization": True})
        with pytest.raises(AudioProcessingError):
            provider.diarize("fake_audio.mp3")
            
    def test_mock_health_check(self):
        """Test mock provider health check."""
        provider = MockAudioProvider()
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["mock_mode"] is True
        assert "mock_segments" in health


class TestWhisperAudioProvider:
    """Test the Whisper audio provider."""
    
    def test_whisper_initialization(self):
        """Test Whisper provider initialization."""
        config = {
            "whisper_model_size": "base",
            "use_faster_whisper": False,
            "device": "cpu"
        }
        provider = WhisperAudioProvider(config)
        
        assert provider.whisper_model_size == "base"
        assert provider.use_faster_whisper is False
        assert provider.device == "cpu"
        
    def test_audio_validation(self):
        """Test audio file validation."""
        provider = WhisperAudioProvider()
        
        # Test non-existent file
        with pytest.raises(AudioProcessingError) as exc_info:
            provider._validate_audio_path("/nonexistent/audio.mp3")
        assert "not found" in str(exc_info.value)
        
        # Test invalid extension
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            with pytest.raises(AudioProcessingError) as exc_info:
                provider._validate_audio_path(f.name)
            assert "Unsupported audio format" in str(exc_info.value)
            
    @patch('src.providers.audio.whisper.WhisperModel')
    def test_faster_whisper_transcription(self, mock_whisper_model):
        """Test transcription with faster-whisper."""
        # Mock the transcription result
        mock_model = Mock()
        mock_segment = Mock()
        mock_segment.text = "Test transcript"
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        
        mock_model.transcribe.return_value = ([mock_segment], {})
        mock_whisper_model.return_value = mock_model
        
        provider = WhisperAudioProvider(config={"use_faster_whisper": True})
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            segments = provider.transcribe(f.name)
            
        assert len(segments) == 1
        assert segments[0].text == "Test transcript"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 5.0
        
    @patch('whisper.load_model')
    def test_standard_whisper_transcription(self, mock_load_model):
        """Test transcription with standard whisper."""
        # Mock the model and transcription result
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "segments": [
                {
                    "text": "Test transcript",
                    "start": 0.0,
                    "end": 5.0
                }
            ]
        }
        mock_load_model.return_value = mock_model
        
        provider = WhisperAudioProvider(config={"use_faster_whisper": False})
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            segments = provider.transcribe(f.name)
            
        assert len(segments) == 1
        assert segments[0].text == "Test transcript"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 5.0
        
    def test_diarization_without_token(self):
        """Test diarization fails gracefully without HF token."""
        provider = WhisperAudioProvider()
        
        # Remove HF_TOKEN if it exists
        with patch.dict('os.environ', {}, clear=True):
            segments = provider.diarize("fake_audio.mp3")
            
        assert segments == []
        
    @patch('pyannote.audio.Pipeline')
    def test_diarization_with_token(self, mock_pipeline_class):
        """Test diarization with HF token."""
        # Mock the diarization pipeline
        mock_pipeline = Mock()
        mock_turn = Mock()
        mock_turn.start = 0.0
        mock_turn.end = 5.0
        
        # Mock itertracks to return one segment
        mock_pipeline.return_value = [(mock_turn, None, "SPEAKER_00")]
        mock_pipeline.itertracks.return_value = [(mock_turn, None, "SPEAKER_00")]
        
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        
        # Set HF_TOKEN
        with patch.dict('os.environ', {'HF_TOKEN': 'test_token'}):
            provider = WhisperAudioProvider()
            
            # Create a temporary audio file
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                segments = provider.diarize(f.name)
                
        assert len(segments) == 1
        assert segments[0].speaker == "Speaker_SPEAKER_00"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 5.0
        
    def test_health_check(self):
        """Test Whisper provider health check."""
        provider = WhisperAudioProvider()
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "WhisperAudioProvider"
        assert "whisper_model_size" in health
        assert "device" in health


class TestBaseAudioProvider:
    """Test the base audio provider functionality."""
    
    def test_alignment_with_diarization(self):
        """Test transcript alignment with diarization."""
        # Create a concrete implementation for testing
        class TestProvider(BaseAudioProvider):
            def transcribe(self, audio_path: str):
                pass
            def diarize(self, audio_path: str):
                pass
            def _provider_specific_health_check(self):
                return {}
                
        provider = TestProvider()
        
        # Create test transcript segments
        transcript_segments = [
            TranscriptSegment(text="Hello", start_time=0.0, end_time=2.0),
            TranscriptSegment(text="World", start_time=2.5, end_time=4.0),
        ]
        
        # Create test diarization segments
        diarization_segments = [
            DiarizationSegment(speaker="Speaker_0", start_time=0.0, end_time=2.2),
            DiarizationSegment(speaker="Speaker_1", start_time=2.3, end_time=4.5),
        ]
        
        # Align segments
        aligned = provider.align_transcript_with_diarization(
            transcript_segments,
            diarization_segments
        )
        
        assert len(aligned) == 2
        assert aligned[0].speaker == "Speaker_0"
        assert aligned[1].speaker == "Speaker_1"
        assert aligned[0].text == "Hello"
        assert aligned[1].text == "World"
        
    def test_alignment_without_diarization(self):
        """Test alignment handles missing diarization gracefully."""
        class TestProvider(BaseAudioProvider):
            def transcribe(self, audio_path: str):
                pass
            def diarize(self, audio_path: str):
                pass
            def _provider_specific_health_check(self):
                return {}
                
        provider = TestProvider()
        
        transcript_segments = [
            TranscriptSegment(text="Hello", start_time=0.0, end_time=2.0),
        ]
        
        # Empty diarization
        aligned = provider.align_transcript_with_diarization(
            transcript_segments,
            []
        )
        
        assert len(aligned) == 1
        assert aligned[0].speaker is None
        assert aligned[0].text == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])