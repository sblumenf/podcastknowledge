"""Mock audio provider for testing."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from src.providers.audio.base import BaseAudioProvider
from src.core.interfaces import TranscriptSegment, DiarizationSegment
from src.core.plugin_discovery import provider_plugin


@provider_plugin('audio', 'mock', version='1.0.0', author='Test', 
                description='Mock audio provider for testing')
class MockAudioProvider(BaseAudioProvider):
    """Mock audio provider that returns predefined responses for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock audio provider."""
        super().__init__(config)
        
        # Mock configuration
        self.mock_response = config.get('mock_response', {})
        self.mock_segments = config.get('mock_segments', [])
        self.mock_speakers = config.get('mock_speakers', ['Speaker 1', 'Speaker 2'])
        self.fail_transcription = config.get('fail_transcription', False)
        self.fail_diarization = config.get('fail_diarization', False)
        
        # Mark as initialized since mock doesn't need actual initialization
        self._initialized = True
        
    def _initialize_model(self) -> None:
        """No model initialization needed for mock provider."""
        pass
        
    def _ensure_initialized(self) -> None:
        """Ensure the provider is initialized."""
        if not self._initialized:
            self._initialize_model()
            self._initialized = True
        
    def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
        """Return mock transcription."""
        # Skip initialization check for mock
        
        if self.fail_transcription:
            raise Exception("Mock transcription failure")
            
        # Use provided segments or generate default ones
        if self.mock_segments:
            return self.mock_segments
            
        # Generate default segments from mock response
        if 'segments' in self.mock_response:
            segments = []
            for seg_data in self.mock_response['segments']:
                segment = TranscriptSegment(
                    id=str(uuid.uuid4()),
                    text=seg_data['text'],
                    start_time=seg_data.get('start', 0.0),
                    end_time=seg_data.get('end', 1.0),
                    confidence=seg_data.get('confidence', 0.95)
                )
                segments.append(segment)
            return segments
            
        # Default mock segments
        return [
            TranscriptSegment(
                id="mock_seg_1",
                text="This is the first mock segment.",
                start_time=0.0,
                end_time=5.0,
                confidence=0.95
            ),
            TranscriptSegment(
                id="mock_seg_2",
                text="This is the second mock segment.",
                start_time=5.0,
                end_time=10.0,
                confidence=0.90
            ),
            TranscriptSegment(
                id="mock_seg_3",
                text="And this is the third mock segment.",
                start_time=10.0,
                end_time=15.0,
                confidence=0.92
            )
        ]
        
    def diarize(self, audio_path: str) -> List[DiarizationSegment]:
        """Return mock diarization."""
        # Skip initialization check for mock
        
        if self.fail_diarization:
            raise Exception("Mock diarization failure")
            
        # Generate mock diarization segments
        segments = []
        duration = 15.0  # Total duration
        segment_duration = duration / len(self.mock_speakers)
        
        for i, speaker in enumerate(self.mock_speakers):
            start = i * segment_duration
            end = (i + 1) * segment_duration
            
            segment = DiarizationSegment(
                speaker=speaker,
                start_time=start,
                end_time=end,
                confidence=0.85 + (i * 0.05)  # Varying confidence
            )
            segments.append(segment)
            
        return segments
        
    def transcribe_with_diarization(self, audio_path: str) -> Dict[str, Any]:
        """Return mock transcription with diarization."""
        transcription = self.transcribe(audio_path)
        diarization = self.diarize(audio_path)
        
        # Combine results
        combined_segments = []
        
        # Simple mock: assign speakers to transcript segments
        for i, trans_seg in enumerate(transcription):
            speaker_idx = i % len(self.mock_speakers)
            speaker = self.mock_speakers[speaker_idx]
            
            combined_segments.append({
                'id': trans_seg.id,
                'text': trans_seg.text,
                'start_time': trans_seg.start_time,
                'end_time': trans_seg.end_time,
                'speaker': speaker,
                'confidence': trans_seg.confidence
            })
            
        return {
            'segments': combined_segments,
            'transcription': transcription,
            'diarization': diarization,
            'speakers': self.mock_speakers
        }
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get mock model information."""
        return {
            'name': 'mock',
            'version': '1.0.0',
            'type': 'mock',
            'device': 'mock',
            'config': self.config
        }
        
        
    # Additional methods for testing
    
    def set_mock_response(self, response: Dict[str, Any]) -> None:
        """Set mock response data."""
        self.mock_response = response
        
    def set_failure_mode(self, fail_transcription: bool = False, fail_diarization: bool = False) -> None:
        """Set failure modes for testing error handling."""
        self.fail_transcription = fail_transcription
        self.fail_diarization = fail_diarization
        
    def _provider_specific_health_check(self) -> Dict[str, Any]:
        """Mock implementation of provider-specific health check."""
        return {
            'mock_mode': True,
            'mock_segments': len(self.mock_segments) if self.mock_segments else 3,
            'mock_speakers': len(self.mock_speakers) if self.mock_speakers else 2,
            'fail_transcription': self.fail_transcription,
            'fail_diarization': self.fail_diarization,
            'mock_provider': 'available',
            'test_mode': True
        }