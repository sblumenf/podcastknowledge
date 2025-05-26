"""
Base audio provider implementation.

This module provides the abstract base class for audio providers,
implementing the AudioProvider protocol from core.interfaces.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

from ...core import (
    AudioProvider,
    DiarizationSegment,
    TranscriptSegment,
    AudioProcessingError,
    ErrorSeverity,
)


logger = logging.getLogger(__name__)


class BaseAudioProvider(ABC, AudioProvider):
    """
    Abstract base class for audio providers.
    
    This class provides common functionality for all audio providers
    and ensures they implement the AudioProvider protocol.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the audio provider.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._initialized = False
        self._last_health_check = None
        
    @abstractmethod
    def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
        """
        Transcribe audio file to text segments.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of transcript segments with timestamps
            
        Raises:
            AudioProcessingError: If transcription fails
        """
        pass
    
    @abstractmethod
    def diarize(self, audio_path: str) -> List[DiarizationSegment]:
        """
        Perform speaker diarization on audio file.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of speaker segments with timestamps
            
        Raises:
            AudioProcessingError: If diarization fails
        """
        pass
    
    def align_transcript_with_diarization(
        self, 
        transcript_segments: List[TranscriptSegment], 
        diarization_segments: List[DiarizationSegment]
    ) -> List[TranscriptSegment]:
        """
        Align transcript segments with speaker diarization.
        
        This is a common implementation that can be overridden by specific providers.
        
        Args:
            transcript_segments: List of transcript segments
            diarization_segments: List of speaker segments
            
        Returns:
            Transcript segments with speaker information added
        """
        if not diarization_segments:
            logger.warning("No diarization segments provided. Returning transcript without speakers.")
            return transcript_segments
            
        # Convert diarization segments to a time-based lookup
        speaker_map = {}
        for segment in diarization_segments:
            # Add entries at small intervals for better alignment
            step = 0.1  # 100ms steps
            current_time = segment.start_time
            while current_time <= segment.end_time:
                speaker_map[current_time] = segment.speaker
                current_time += step
                
        # Align speakers with transcript segments
        from collections import defaultdict
        
        aligned_segments = []
        for segment in transcript_segments:
            # Find the most frequent speaker in this time range
            speaker_counts = defaultdict(int)
            
            # Check several points within the segment
            segment_duration = segment.end_time - segment.start_time
            check_points = min(10, max(1, int(segment_duration / 0.5)))  # At least 1, max 10
            
            for i in range(check_points):
                check_time = segment.start_time + (segment_duration * i / check_points)
                
                # Find the closest key in speaker_map
                if speaker_map:
                    closest_time = min(
                        speaker_map.keys(), 
                        key=lambda k: abs(k - check_time)
                    )
                    
                    if abs(closest_time - check_time) < 1.0:  # within 1 second
                        speaker_counts[speaker_map[closest_time]] += 1
            
            # Assign the most common speaker
            if speaker_counts:
                most_common_speaker = max(speaker_counts.items(), key=lambda x: x[1])[0]
                speaker = most_common_speaker
            else:
                speaker = None
                
            # Create aligned segment
            aligned_segment = TranscriptSegment(
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                speaker=speaker
            )
            aligned_segments.append(aligned_segment)
            
        return aligned_segments
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the audio provider.
        
        Returns:
            Dict containing health status information
        """
        try:
            # Basic health check - can be overridden by specific providers
            status = {
                "status": "healthy",
                "provider": self.__class__.__name__,
                "initialized": self._initialized,
                "config": {k: v for k, v in self.config.items() if k not in ["api_key", "token"]},
                "timestamp": self._get_timestamp(),
            }
            
            # Provider-specific checks
            status.update(self._provider_specific_health_check())
            
            self._last_health_check = status
            return status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "provider": self.__class__.__name__,
                "error": str(e),
                "timestamp": self._get_timestamp(),
            }
    
    @abstractmethod
    def _provider_specific_health_check(self) -> Dict[str, Any]:
        """
        Provider-specific health check implementation.
        
        Returns:
            Additional health check information
        """
        pass
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    def _validate_audio_path(self, audio_path: str) -> None:
        """
        Validate that the audio file exists and is accessible.
        
        Args:
            audio_path: Path to validate
            
        Raises:
            AudioProcessingError: If file doesn't exist or isn't accessible
        """
        from pathlib import Path
        
        path = Path(audio_path)
        if not path.exists():
            raise AudioProcessingError(
                f"Audio file not found: {audio_path}",
                severity=ErrorSeverity.CRITICAL,
                details={"path": audio_path}
            )
            
        if not path.is_file():
            raise AudioProcessingError(
                f"Path is not a file: {audio_path}",
                severity=ErrorSeverity.CRITICAL,
                details={"path": audio_path}
            )
            
        # Check file extension
        valid_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma']
        if path.suffix.lower() not in valid_extensions:
            raise AudioProcessingError(
                f"Unsupported audio format: {path.suffix}",
                severity=ErrorSeverity.WARNING,
                details={
                    "path": audio_path,
                    "extension": path.suffix,
                    "supported": valid_extensions
                }
            )