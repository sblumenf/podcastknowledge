"""
Segmentation module for podcast transcript processing.

This module handles the segmentation and post-processing of podcast transcripts,
including advertisement detection and sentiment analysis.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..core import (
    TranscriptSegment,
    DiarizationSegment,
    AudioProvider,
    constants,
)


logger = logging.getLogger(__name__)


@dataclass
class SegmentMetadata:
    """Additional metadata for a segment."""
    is_advertisement: bool = False
    sentiment: Optional[Dict[str, Any]] = None
    segment_index: int = 0
    word_count: int = 0
    duration_seconds: float = 0.0


class EnhancedPodcastSegmenter:
    """
    Enhanced podcast segmenter with advanced features.
    
    This class orchestrates audio processing and adds metadata to segments
    such as advertisement detection and sentiment analysis.
    """
    
    def __init__(self, audio_provider: AudioProvider, config: Optional[Dict[str, Any]] = None):
        """
        Initialize podcast segmenter with audio provider and configuration.
        
        Args:
            audio_provider: Audio provider for transcription and diarization
            config: Configuration dictionary with parameters:
                - min_segment_tokens: Minimum tokens per segment
                - max_segment_tokens: Maximum tokens per segment
                - ad_detection_enabled: Enable advertisement detection
                - use_semantic_boundaries: Use semantic boundaries for segmentation
                - min_speakers: Minimum speakers for diarization
                - max_speakers: Maximum speakers for diarization
        """
        self.audio_provider = audio_provider
        
        # Default configuration
        default_config = {
            'min_segment_tokens': constants.MIN_SEGMENT_TOKENS,
            'max_segment_tokens': constants.MAX_SEGMENT_TOKENS,
            'ad_detection_enabled': True,
            'use_semantic_boundaries': True,
            'min_speakers': 1,
            'max_speakers': 10
        }
        
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        logger.info(f"Initialized EnhancedPodcastSegmenter with config: {self.config}")
        
    def process_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Process audio file through transcription and diarization.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dictionary with processing results:
                - transcript: List of processed transcript segments
                - diarization: List of diarization segments
                - metadata: Additional processing metadata
        """
        logger.info(f"Processing audio: {audio_path}")
        
        # Transcribe audio
        try:
            transcript_segments = self.audio_provider.transcribe(audio_path)
            logger.info(f"Transcription completed with {len(transcript_segments)} segments")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "transcript": [],
                "diarization": [],
                "metadata": {"error": str(e)}
            }
            
        if not transcript_segments:
            logger.warning("No transcript segments generated")
            return {
                "transcript": [],
                "diarization": [],
                "metadata": {"warning": "No transcript segments"}
            }
            
        # Perform speaker diarization
        diarization_segments = []
        if self.config.get('enable_diarization', True):
            try:
                logger.info("Performing speaker diarization...")
                diarization_segments = self.audio_provider.diarize(audio_path)
                logger.info(f"Diarization completed with {len(diarization_segments)} segments")
            except Exception as e:
                logger.warning(f"Diarization failed: {e}")
                # Continue without diarization
                
        # Align transcript with diarization
        if diarization_segments:
            logger.info("Aligning transcript with speaker diarization...")
            transcript_segments = self.audio_provider.align_transcript_with_diarization(
                transcript_segments,
                diarization_segments
            )
            
        # Post-process segments
        logger.info("Post-processing segments...")
        processed_segments = self._post_process_segments(transcript_segments)
        
        # Calculate metadata
        metadata = self._calculate_metadata(processed_segments)
        
        return {
            "transcript": processed_segments,
            "diarization": diarization_segments,
            "metadata": metadata
        }
        
    def _post_process_segments(self, segments: List[TranscriptSegment]) -> List[Dict[str, Any]]:
        """
        Post-process segments for better quality.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            List of processed segment dictionaries with additional metadata
        """
        processed_segments = []
        
        for i, segment in enumerate(segments):
            # Skip empty segments
            if not segment.text.strip():
                continue
                
            # Create segment dictionary
            segment_dict = {
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "speaker": segment.speaker,
                "segment_index": i,
                "word_count": len(segment.text.split()),
                "duration_seconds": segment.end_time - segment.start_time
            }
            
            # Detect advertisements
            segment_dict["is_advertisement"] = self._detect_advertisement(segment.text)
            
            # Analyze sentiment
            segment_dict["sentiment"] = self._analyze_segment_sentiment(segment.text)
            
            processed_segments.append(segment_dict)
            
        return processed_segments
        
    def _detect_advertisement(self, text: str) -> bool:
        """
        Detect if a segment contains advertisement content.
        
        Args:
            text: Segment text
            
        Returns:
            Boolean indicating if segment is an advertisement
        """
        if not self.config.get('ad_detection_enabled', True):
            return False
            
        # Convert to lowercase for matching
        text_lower = text.lower()
        
        # Check for common ad markers
        for marker in constants.AD_MARKERS:
            if marker in text_lower:
                logger.debug(f"Advertisement detected: '{marker}' found in text")
                return True
                
        return False
        
    def _analyze_segment_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze segment sentiment using simple lexicon-based approach.
        
        Args:
            text: Segment text
            
        Returns:
            Dictionary with sentiment analysis results:
                - score: Sentiment score (-1 to 1)
                - polarity: "positive", "negative", or "neutral"
                - positive_count: Number of positive words
                - negative_count: Number of negative words
        """
        # Simple lexicon-based sentiment analysis
        positive_words = {
            "good", "great", "excellent", "amazing", "love", "best", "positive",
            "happy", "excited", "wonderful", "fantastic", "superior", "beneficial",
            "brilliant", "outstanding", "remarkable", "impressive", "delightful",
            "perfect", "enjoyable", "beautiful", "awesome", "incredible"
        }
        
        negative_words = {
            "bad", "terrible", "awful", "hate", "worst", "negative", "poor",
            "horrible", "failure", "inadequate", "disappointing", "problem",
            "wrong", "difficult", "unfortunate", "ugly", "nasty", "disaster",
            "pathetic", "inferior", "useless", "annoying", "frustrating"
        }
        
        # Extract words from text
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Count sentiment words
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            score = 0.0  # neutral
        else:
            score = (positive_count - negative_count) / total
            
        # Determine polarity using thresholds
        if score > constants.SENTIMENT_THRESHOLDS["positive"]:
            polarity = "positive"
        elif score < constants.SENTIMENT_THRESHOLDS["negative"]:
            polarity = "negative"
        else:
            polarity = "neutral"
            
        return {
            "score": round(score, 3),
            "polarity": polarity,
            "positive_count": positive_count,
            "negative_count": negative_count
        }
        
    def _calculate_metadata(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate metadata for the processed segments.
        
        Args:
            segments: List of processed segments
            
        Returns:
            Dictionary with metadata about the processing
        """
        if not segments:
            return {
                "total_segments": 0,
                "total_duration": 0.0,
                "total_words": 0,
                "advertisement_count": 0,
                "sentiment_distribution": {}
            }
            
        total_duration = segments[-1]["end_time"] if segments else 0.0
        total_words = sum(seg["word_count"] for seg in segments)
        ad_count = sum(1 for seg in segments if seg.get("is_advertisement", False))
        
        # Calculate sentiment distribution
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for seg in segments:
            if seg.get("sentiment"):
                polarity = seg["sentiment"].get("polarity", "neutral")
                sentiment_counts[polarity] = sentiment_counts.get(polarity, 0) + 1
                
        total_with_sentiment = sum(sentiment_counts.values())
        sentiment_distribution = {
            k: round(v / total_with_sentiment, 3) if total_with_sentiment > 0 else 0.0
            for k, v in sentiment_counts.items()
        }
        
        # Find unique speakers
        speakers = set()
        for seg in segments:
            if seg.get("speaker"):
                speakers.add(seg["speaker"])
                
        return {
            "total_segments": len(segments),
            "total_duration": round(total_duration, 2),
            "total_words": total_words,
            "average_segment_duration": round(total_duration / len(segments), 2) if segments else 0.0,
            "advertisement_count": ad_count,
            "advertisement_percentage": round(ad_count / len(segments), 3) if segments else 0.0,
            "unique_speakers": len(speakers),
            "speakers": sorted(list(speakers)),
            "sentiment_distribution": sentiment_distribution,
        }