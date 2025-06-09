"""
VTT-based segmentation module for transcript processing.

This module handles the segmentation and post-processing of VTT transcripts,
including advertisement detection and sentiment analysis.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging
import re

from ..core import constants
from ..core.interfaces import TranscriptSegment
logger = logging.getLogger(__name__)


@dataclass
class SegmentMetadata:
    """Additional metadata for a segment."""
    is_advertisement: bool = False
    sentiment: Optional[Dict[str, Any]] = None
    segment_index: int = 0
    word_count: int = 0
    duration_seconds: float = 0.0


class VTTSegmenter:
    """
    VTT transcript segmenter with advanced features.
    
    This class processes VTT transcript segments and adds metadata
    such as advertisement detection and sentiment analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize VTT segmenter with configuration.
        
        Args:
            config: Configuration dictionary with parameters:
                - min_segment_tokens: Minimum tokens per segment
                - max_segment_tokens: Maximum tokens per segment
                - ad_detection_enabled: Enable advertisement detection
                - use_semantic_boundaries: Use semantic boundaries for segmentation
        """
        # Default configuration
        default_config = {
            'min_segment_tokens': constants.MIN_SEGMENT_TOKENS,
            'max_segment_tokens': constants.MAX_SEGMENT_TOKENS,
            'ad_detection_enabled': True,
            'use_semantic_boundaries': True,
        }
        
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        logger.info(f"Initialized VTTSegmenter with config: {self.config}")
        
    def process_segments(self, segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """
        Process VTT transcript segments.
        
        Args:
            segments: List of transcript segments from VTT parser
            
        Returns:
            Dictionary with processing results:
                - transcript: List of processed transcript segments
                - metadata: Additional processing metadata
        """
        logger.info(f"Processing {len(segments)} VTT segments")
        
        if not segments:
            logger.warning("No segments to process")
            return {
                "transcript": [],
                "metadata": {"warning": "No segments provided"}
            }
            
        # Post-process segments
        logger.info("Post-processing segments...")
        processed_segments = self._post_process_segments(segments)
        
        # Calculate metadata
        metadata = self._calculate_metadata(processed_segments)
        
        return {
            "transcript": processed_segments,
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
            if self.config.get('ad_detection_enabled', True):
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
        # Convert to lowercase for matching
        text_lower = text.lower()
        
        # Check for common ad markers
        ad_markers = [
            "brought to you by", "sponsored by", "thanks to our sponsor",
            "visit our sponsor", "check out", "promo code", "discount code",
            "special offer", "limited time", "sign up today", "free trial",
            "our partners at", "today's sponsor", "this episode is sponsored"
        ]
        
        for marker in ad_markers:
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
        positive_threshold = 0.1
        negative_threshold = -0.1
        
        if score > positive_threshold:
            polarity = "positive"
        elif score < negative_threshold:
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