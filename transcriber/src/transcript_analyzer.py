"""Transcript Coverage Analysis System for Podcast Transcription Pipeline.

This module provides tools to analyze transcript completeness and detect
when transcriptions are incomplete relative to the full episode duration.
"""

import re
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path
from datetime import datetime, timezone

from src.utils.logging import get_logger

logger = get_logger('transcript_analyzer')


class TranscriptAnalyzer:
    """Analyzes transcript coverage and completeness."""
    
    def __init__(self):
        """Initialize the transcript analyzer."""
        # Common timestamp patterns in transcripts
        self.timestamp_patterns = [
            # HH:MM:SS format
            r'(\d{1,2}):(\d{2}):(\d{2})',
            # MM:SS format
            r'(\d{1,2}):(\d{2})',
            # [HH:MM:SS] format
            r'\[(\d{1,2}):(\d{2}):(\d{2})\]',
            # [MM:SS] format
            r'\[(\d{1,2}):(\d{2})\]',
            # (HH:MM:SS) format
            r'\((\d{1,2}):(\d{2}):(\d{2})\)',
            # At MM:SS or At HH:MM:SS
            r'[Aa]t\s+(\d{1,2}):(\d{2})(?::(\d{2}))?',
            # Time: HH:MM:SS or Time: MM:SS
            r'[Tt]ime:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?',
        ]
        
        logger.info("Initialized TranscriptAnalyzer")
    
    def calculate_coverage(self, transcript: str, total_episode_duration: int) -> Tuple[bool, float, Dict[str, Any]]:
        """Calculate transcript coverage percentage.
        
        Args:
            transcript: Raw transcript text
            total_episode_duration: Total episode duration in seconds
            
        Returns:
            Tuple of (is_complete, coverage_percentage, analysis_details)
        """
        if not transcript or not total_episode_duration:
            return False, 0.0, {"error": "Missing transcript or duration"}
        
        try:
            # Extract all timestamps from the transcript
            timestamps = self._extract_timestamps(transcript)
            
            if not timestamps:
                logger.warning("No timestamps found in transcript")
                return False, 0.0, {"error": "No timestamps found", "timestamp_count": 0}
            
            # Get the last (highest) timestamp
            last_timestamp = max(timestamps)
            
            # Calculate coverage percentage
            coverage = last_timestamp / total_episode_duration
            
            # Consider complete if coverage is at least 85%
            min_coverage = 0.85
            is_complete = coverage >= min_coverage
            
            analysis_details = {
                "last_timestamp_seconds": last_timestamp,
                "total_duration_seconds": total_episode_duration,
                "coverage_ratio": coverage,
                "timestamp_count": len(timestamps),
                "min_coverage_threshold": min_coverage,
                "timestamps_found": timestamps[:5] if len(timestamps) > 5 else timestamps  # First 5 for debugging
            }
            
            logger.info(f"Coverage analysis: {coverage:.1%} ({last_timestamp}s of {total_episode_duration}s)")
            
            return is_complete, coverage, analysis_details
            
        except Exception as e:
            logger.error(f"Failed to calculate coverage: {e}")
            return False, 0.0, {"error": str(e)}
    
    def _extract_timestamps(self, transcript: str) -> List[float]:
        """Extract all timestamps from transcript text.
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            List of timestamps in seconds (sorted)
        """
        timestamps = []
        
        for pattern in self.timestamp_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            
            for match in matches:
                try:
                    timestamp_seconds = self._parse_timestamp_match(match)
                    if timestamp_seconds is not None:
                        timestamps.append(timestamp_seconds)
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp match {match}: {e}")
                    continue
        
        # Remove duplicates and sort
        unique_timestamps = sorted(list(set(timestamps)))
        
        logger.debug(f"Extracted {len(unique_timestamps)} unique timestamps")
        return unique_timestamps
    
    def _parse_timestamp_match(self, match: tuple) -> Optional[float]:
        """Parse a regex match tuple into seconds.
        
        Args:
            match: Tuple from regex match (hours, minutes, seconds) or (minutes, seconds)
            
        Returns:
            Timestamp in seconds or None if invalid
        """
        try:
            # Handle different match tuple formats
            if len(match) == 3:  # (hours, minutes, seconds)
                hours, minutes, seconds = match
                hours = int(hours) if hours else 0
                minutes = int(minutes) if minutes else 0
                seconds = int(seconds) if seconds else 0
                return hours * 3600 + minutes * 60 + seconds
            
            elif len(match) == 2:  # (minutes, seconds)
                minutes, seconds = match
                minutes = int(minutes) if minutes else 0
                seconds = int(seconds) if seconds else 0
                return minutes * 60 + seconds
            
            else:
                logger.debug(f"Unexpected match format: {match}")
                return None
                
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse timestamp components {match}: {e}")
            return None
    
    def get_last_timestamp(self, transcript: str) -> Optional[float]:
        """Get the last timestamp from a transcript.
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Last timestamp in seconds or None if none found
        """
        timestamps = self._extract_timestamps(transcript)
        return max(timestamps) if timestamps else None
    
    def validate_transcript_format(self, transcript: str) -> Dict[str, Any]:
        """Validate the format and structure of a transcript.
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            "has_timestamps": False,
            "has_speaker_identification": False,
            "estimated_format": "unknown",
            "line_count": 0,
            "character_count": len(transcript),
            "issues": []
        }
        
        if not transcript:
            validation["issues"].append("Empty transcript")
            return validation
        
        lines = transcript.split('\n')
        validation["line_count"] = len(lines)
        
        # Check for timestamps
        timestamps = self._extract_timestamps(transcript)
        validation["has_timestamps"] = len(timestamps) > 0
        validation["timestamp_count"] = len(timestamps)
        
        # Check for speaker identification patterns
        speaker_patterns = [
            r'Speaker\s*\d+',
            r'SPEAKER\s*\d+',
            r'[A-Z][a-z]+:',  # Name followed by colon
            r'Host:',
            r'Guest:',
            r'\[Speaker\s*\d+\]',
        ]
        
        speaker_matches = 0
        for pattern in speaker_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            speaker_matches += len(matches)
        
        validation["has_speaker_identification"] = speaker_matches > 0
        validation["speaker_mention_count"] = speaker_matches
        
        # Estimate format
        if "WEBVTT" in transcript:
            validation["estimated_format"] = "webvtt"
        elif "-->" in transcript:
            validation["estimated_format"] = "vtt_like"
        elif validation["has_timestamps"] and validation["has_speaker_identification"]:
            validation["estimated_format"] = "timestamped_text"
        elif validation["has_timestamps"]:
            validation["estimated_format"] = "timestamped_text_no_speakers"
        else:
            validation["estimated_format"] = "plain_text"
        
        # Check for potential issues
        if not validation["has_timestamps"]:
            validation["issues"].append("No timestamps detected")
        
        if not validation["has_speaker_identification"]:
            validation["issues"].append("No speaker identification detected")
        
        if validation["character_count"] < 100:
            validation["issues"].append("Transcript appears very short")
        
        logger.info(f"Transcript validation: {validation['estimated_format']} format, "
                   f"{validation['timestamp_count']} timestamps, "
                   f"{validation['speaker_mention_count']} speaker mentions")
        
        return validation
    
    def analyze_transcript_quality(self, transcript: str, episode_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive quality analysis of a transcript.
        
        Args:
            transcript: Raw transcript text
            episode_metadata: Episode metadata including duration
            
        Returns:
            Dictionary with quality analysis results
        """
        analysis = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode_title": episode_metadata.get('title', 'Unknown'),
            "format_validation": {},
            "coverage_analysis": {},
            "quality_score": 0.0,
            "recommendations": []
        }
        
        # Format validation
        analysis["format_validation"] = self.validate_transcript_format(transcript)
        
        # Coverage analysis
        duration_str = episode_metadata.get('duration', '0:00')
        total_duration = self._parse_duration_to_seconds(duration_str)
        
        if total_duration > 0:
            is_complete, coverage, details = self.calculate_coverage(transcript, total_duration)
            analysis["coverage_analysis"] = {
                "is_complete": is_complete,
                "coverage_percentage": coverage,
                "details": details
            }
        else:
            analysis["coverage_analysis"] = {"error": "No valid episode duration provided"}
        
        # Calculate quality score (0-100)
        score = 0
        
        # Format quality (40 points max)
        if analysis["format_validation"]["has_timestamps"]:
            score += 20
        if analysis["format_validation"]["has_speaker_identification"]:
            score += 20
        
        # Coverage quality (40 points max)
        if "coverage_percentage" in analysis["coverage_analysis"]:
            coverage_pct = analysis["coverage_analysis"]["coverage_percentage"]
            score += min(40, coverage_pct * 40)  # Scale to 40 points max
        
        # Length quality (20 points max)
        char_count = analysis["format_validation"]["character_count"]
        if char_count > 1000:
            score += min(20, char_count / 1000 * 5)  # Scale based on length
        
        analysis["quality_score"] = min(100, score)
        
        # Generate recommendations
        if not analysis["format_validation"]["has_timestamps"]:
            analysis["recommendations"].append("Add timestamp information")
        
        if not analysis["format_validation"]["has_speaker_identification"]:
            analysis["recommendations"].append("Improve speaker identification")
        
        if "coverage_percentage" in analysis["coverage_analysis"]:
            if analysis["coverage_analysis"]["coverage_percentage"] < 0.85:
                analysis["recommendations"].append("Request continuation to achieve full coverage")
        
        if analysis["quality_score"] < 70:
            analysis["recommendations"].append("Overall quality is low - consider re-transcription")
        
        logger.info(f"Quality analysis complete: score {analysis['quality_score']:.1f}/100")
        
        return analysis
    
    def _parse_duration_to_seconds(self, duration_str: str) -> int:
        """Parse duration string to total seconds.
        
        Args:
            duration_str: Duration in format HH:MM:SS or MM:SS
            
        Returns:
            Total seconds
        """
        if not duration_str:
            return 0
        
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:
                return int(float(duration_str) * 60)  # Assume minutes
        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}")
            return 0