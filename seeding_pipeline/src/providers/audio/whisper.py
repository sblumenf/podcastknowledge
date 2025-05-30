"""
Whisper-based audio provider implementation.

This module provides audio transcription and diarization using OpenAI Whisper
and pyannote.audio for speaker diarization.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from .base import BaseAudioProvider
from ...core import (
    TranscriptSegment,
    DiarizationSegment,
    AudioProcessingError,
    ErrorSeverity,
    constants,
)
from ...core.plugin_discovery import provider_plugin
from ...tracing import trace_method, add_span_attributes


logger = logging.getLogger(__name__)


@provider_plugin('audio', 'whisper', version='1.0.0', author='OpenAI', 
                description='Audio transcription using OpenAI Whisper')
class WhisperAudioProvider(BaseAudioProvider):
    """
    Audio provider using Whisper for transcription and pyannote for diarization.
    
    This provider supports both standard whisper and faster-whisper implementations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Whisper audio provider.
        
        Args:
            config: Configuration dictionary with options:
                - whisper_model_size: Model size (default: "large-v3")
                - use_faster_whisper: Use faster-whisper if available (default: True)
                - device: Device to use ("cuda" or "cpu", auto-detected if not specified)
                - min_speakers: Minimum speakers for diarization (default: 1)
                - max_speakers: Maximum speakers for diarization (default: 10)
                - enable_diarization: Enable speaker diarization (default: True)
        """
        super().__init__(config)
        
        # Set defaults
        self.whisper_model_size = self.config.get("whisper_model_size", constants.DEFAULT_WHISPER_MODEL)
        self.use_faster_whisper = self.config.get("use_faster_whisper", True)
        self.min_speakers = self.config.get("min_speakers", 1)
        self.max_speakers = self.config.get("max_speakers", 10)
        self.enable_diarization = self.config.get("enable_diarization", True)
        
        # Determine device
        self._setup_device()
        
        # Models (lazy loaded)
        self._whisper_model = None
        self._diarization_pipeline = None
        
    def _setup_device(self):
        """Set up the compute device (CPU or CUDA)."""
        try:
            import torch
            self.device = self.config.get("device", "cuda" if torch.cuda.is_available() else "cpu")
            self.torch_available = True
            logger.info(f"Using {self.device} for audio processing")
        except ImportError:
            self.device = "cpu"
            self.torch_available = False
            logger.warning("PyTorch not available. Using CPU for audio processing.")
            
    def _ensure_whisper_model(self):
        """Ensure Whisper model is loaded."""
        if self._whisper_model is not None:
            return
            
        try:
            if self.use_faster_whisper:
                try:
                    from faster_whisper import WhisperModel
                    
                    compute_type = "float16" if self.device == "cuda" else "int8"
                    self._whisper_model = WhisperModel(
                        self.whisper_model_size,
                        device=self.device,
                        compute_type=compute_type
                    )
                    self._whisper_type = "faster"
                    logger.info(f"Loaded faster-whisper model: {self.whisper_model_size}")
                    
                except ImportError:
                    logger.warning("faster-whisper not available, falling back to standard whisper")
                    self._load_standard_whisper()
            else:
                self._load_standard_whisper()
                
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to load Whisper model: {e}",
                severity=ErrorSeverity.CRITICAL,
                details={"model": self.whisper_model_size, "error": str(e)}
            )
            
    def _load_standard_whisper(self):
        """Load standard Whisper model."""
        try:
            import whisper
            
            self._whisper_model = whisper.load_model(
                self.whisper_model_size,
                device=self.device
            )
            self._whisper_type = "standard"
            logger.info(f"Loaded standard whisper model: {self.whisper_model_size}")
            
        except ImportError:
            raise AudioProcessingError(
                "Neither whisper nor faster-whisper is available",
                severity=ErrorSeverity.CRITICAL,
                details={"attempted_models": ["faster-whisper", "whisper"]}
            )
            
    @trace_method(name="whisper.transcribe")
    def transcribe(self, audio_path: str) -> List[TranscriptSegment]:
        """
        Transcribe audio file using Whisper.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of transcript segments with timestamps
            
        Raises:
            AudioProcessingError: If transcription fails
        """
        # Validate audio file
        self._validate_audio_path(audio_path)
        
        # Ensure model is loaded
        self._ensure_whisper_model()
        
        try:
            if self._whisper_type == "faster":
                return self._transcribe_faster_whisper(audio_path)
            else:
                return self._transcribe_standard_whisper(audio_path)
                
        except Exception as e:
            raise AudioProcessingError(
                f"Transcription failed: {e}",
                severity=ErrorSeverity.WARNING,
                details={"audio_path": audio_path, "error": str(e)}
            )
            
    @trace_method(name="whisper.transcribe_faster_whisper")
    def _transcribe_faster_whisper(self, audio_path: str) -> List[TranscriptSegment]:
        """Transcribe using faster-whisper."""
        logger.info(f"Transcribing with faster-whisper model {self.whisper_model_size}...")
        
        # Add span attributes
        add_span_attributes({
            "whisper.implementation": "faster-whisper",
            "whisper.model_size": self.whisper_model_size,
            "audio.path": audio_path,
        })
        
        segments, info = self._whisper_model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True
        )
        
        # Process segments
        transcript_segments = []
        for i, segment in enumerate(segments):
            transcript_segment = TranscriptSegment(
                id=f"seg_{i}",
                text=segment.text.strip(),
                start_time=segment.start,
                end_time=segment.end
            )
            transcript_segments.append(transcript_segment)
            
        logger.info(f"Transcription completed with {len(transcript_segments)} segments")
        
        # Add result metrics
        add_span_attributes({
            "whisper.segments_count": len(transcript_segments),
            "whisper.language": info.language if hasattr(info, 'language') else 'unknown',
        })
        
        return transcript_segments
        
    def _transcribe_standard_whisper(self, audio_path: str) -> List[TranscriptSegment]:
        """Transcribe using standard whisper."""
        logger.info(f"Transcribing with whisper model {self.whisper_model_size}...")
        
        result = self._whisper_model.transcribe(
            audio_path,
            word_timestamps=True
        )
        
        # Process segments
        transcript_segments = []
        for i, segment in enumerate(result["segments"]):
            transcript_segment = TranscriptSegment(
                id=f"seg_{i}",
                text=segment["text"].strip(),
                start_time=segment["start"],
                end_time=segment["end"]
            )
            transcript_segments.append(transcript_segment)
            
        logger.info(f"Transcription completed with {len(transcript_segments)} segments")
        return transcript_segments
        
    def diarize(self, audio_path: str) -> List[DiarizationSegment]:
        """
        Perform speaker diarization using pyannote.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of speaker segments with timestamps
            
        Raises:
            AudioProcessingError: If diarization fails
        """
        if not self.enable_diarization:
            logger.info("Diarization is disabled")
            return []
            
        # Check if HF_TOKEN is available
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.warning("No Hugging Face token. Skipping diarization.")
            return []
            
        # Validate audio file
        self._validate_audio_path(audio_path)
        
        # Ensure diarization pipeline is loaded
        self._ensure_diarization_pipeline(hf_token)
        
        try:
            logger.info("Running speaker diarization...")
            
            diarization = self._diarization_pipeline(
                audio_path,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers
            )
            
            # Convert to DiarizationSegment objects
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segment = DiarizationSegment(
                    speaker=f"Speaker_{speaker}",
                    start_time=turn.start,
                    end_time=turn.end
                )
                segments.append(segment)
                
            # Get unique speakers
            unique_speakers = len(set(s.speaker for s in segments))
            logger.info(f"Diarization completed with {unique_speakers} speakers")
            
            return segments
            
        except Exception as e:
            raise AudioProcessingError(
                f"Diarization failed: {e}",
                severity=ErrorSeverity.WARNING,
                details={"audio_path": audio_path, "error": str(e)}
            )
            
    def _ensure_diarization_pipeline(self, hf_token: str):
        """Ensure diarization pipeline is loaded."""
        if self._diarization_pipeline is not None:
            return
            
        try:
            from pyannote.audio import Pipeline
            
            self._diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            if self.device == "cuda" and self.torch_available:
                import torch
                self._diarization_pipeline = self._diarization_pipeline.to(torch.device("cuda"))
                
            logger.info("Loaded pyannote diarization pipeline")
            
        except ImportError:
            raise AudioProcessingError(
                "pyannote.audio not available for speaker diarization",
                severity=ErrorSeverity.WARNING,
                details={"required_package": "pyannote.audio"}
            )
            
    def _provider_specific_health_check(self) -> Dict[str, Any]:
        """
        Whisper-specific health check.
        
        Returns:
            Additional health check information
        """
        health_info = {
            "whisper_model_size": self.whisper_model_size,
            "whisper_type": getattr(self, "_whisper_type", "not_loaded"),
            "whisper_loaded": self._whisper_model is not None,
            "diarization_loaded": self._diarization_pipeline is not None,
            "device": self.device,
            "torch_available": self.torch_available,
        }
        
        # Check GPU memory if using CUDA
        if self.device == "cuda" and self.torch_available:
            try:
                import torch
                gpu_memory = torch.cuda.memory_allocated() / (1024**3)
                gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                health_info["gpu_memory_gb"] = f"{gpu_memory:.1f}/{gpu_total:.1f}"
            except Exception:
                health_info["gpu_memory_gb"] = "unavailable"
                
        return health_info
        
    def cleanup_resources(self):
        """Clean up GPU memory and resources."""
        if self.device == "cuda" and self.torch_available:
            try:
                import torch
                import gc
                
                # Clear models
                self._whisper_model = None
                self._diarization_pipeline = None
                
                # Clear GPU cache
                torch.cuda.empty_cache()
                gc.collect()
                
                logger.info("Cleaned up GPU resources")
            except Exception as e:
                logger.warning(f"Failed to clean up GPU resources: {e}")