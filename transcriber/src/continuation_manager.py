"""Continuation Management System for Podcast Transcription Pipeline.

This module provides automatic continuation logic to ensure complete episode
transcription regardless of token limits or response cutoffs.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

from src.utils.logging import get_logger
from src.transcript_analyzer import TranscriptAnalyzer

logger = get_logger('continuation_manager')


class ContinuationManager:
    """Manages automatic continuation requests for incomplete transcripts."""
    
    def __init__(self, gemini_client=None, max_attempts: int = 10):
        """Initialize the continuation manager.
        
        Args:
            gemini_client: GeminiClient instance for making API calls
            max_attempts: Maximum number of continuation attempts
        """
        self.gemini_client = gemini_client
        self.max_attempts = max_attempts
        self.analyzer = TranscriptAnalyzer()
        
        logger.info(f"Initialized ContinuationManager with max {max_attempts} attempts")
    
    async def request_continuation(self, 
                                 audio_url: str,
                                 existing_transcript: str,
                                 last_timestamp: float,
                                 episode_metadata: Dict[str, Any]) -> Optional[str]:
        """Request continuation of transcript from the last timestamp.
        
        Args:
            audio_url: URL of the audio file
            existing_transcript: Current partial transcript
            last_timestamp: Timestamp (in seconds) where transcript ended
            episode_metadata: Episode information for context
            
        Returns:
            Continuation transcript or None if failed
        """
        if not self.gemini_client:
            logger.error("No Gemini client available for continuation request")
            return None
        
        try:
            logger.info(f"Requesting continuation from {last_timestamp:.1f}s")
            
            # Extract context from existing transcript
            context_lines = self._extract_context_from_transcript(existing_transcript, last_timestamp)
            
            # Build continuation prompt
            prompt = self._build_continuation_prompt(
                episode_metadata, last_timestamp, context_lines
            )
            
            # Make API call through the Gemini client
            # Use the existing request_continuation method if available
            if hasattr(self.gemini_client, 'request_continuation'):
                continuation = await self.gemini_client.request_continuation(
                    audio_url, existing_transcript, last_timestamp, episode_metadata
                )
            else:
                # Fallback: use direct transcription call with continuation prompt
                continuation = await self._request_continuation_direct(
                    audio_url, prompt, episode_metadata
                )
            
            if continuation:
                logger.info(f"Received continuation transcript ({len(continuation)} chars)")
                return continuation
            else:
                logger.warning("Empty continuation received")
                return None
                
        except Exception as e:
            logger.error(f"Continuation request failed: {e}")
            return None
    
    async def ensure_complete_transcript(self,
                                       initial_transcript: str,
                                       audio_url: str,
                                       episode_metadata: Dict[str, Any],
                                       min_coverage: float = 0.85) -> Tuple[str, Dict[str, Any]]:
        """Execute continuation loop until transcript is complete.
        
        Args:
            initial_transcript: Initial transcript from first request
            audio_url: Audio file URL
            episode_metadata: Episode metadata including duration
            min_coverage: Minimum coverage ratio to consider complete
            
        Returns:
            Tuple of (complete_transcript, continuation_info)
        """
        segments = [initial_transcript]
        attempts = 0
        continuation_info = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "attempts": 0,
            "final_coverage": 0.0,
            "success": False,
            "segments_count": 1,
            "error": None,
            "consecutive_failures": 0,
            "api_errors": []
        }
        
        # Parse episode duration
        duration_str = episode_metadata.get('duration', '0:00')
        total_duration = self._parse_duration_to_seconds(duration_str)
        
        if total_duration <= 0:
            logger.warning("No valid episode duration - cannot perform coverage analysis")
            continuation_info["error"] = "No valid episode duration"
            return initial_transcript, continuation_info
        
        logger.info(f"Starting continuation loop for {total_duration}s episode (target: {min_coverage:.1%} coverage)")
        
        while attempts < self.max_attempts:
            # Combine all segments so far
            current_transcript = self._simple_concatenate(segments)
            
            # Analyze coverage
            is_complete, coverage, analysis_details = self.analyzer.calculate_coverage(
                current_transcript, total_duration
            )
            
            logger.info(f"Attempt {attempts + 1}: {coverage:.1%} coverage, "
                       f"{'COMPLETE' if is_complete else 'INCOMPLETE'}")
            
            continuation_info["final_coverage"] = coverage
            continuation_info["attempts"] = attempts
            
            # Check if we've reached sufficient coverage
            if coverage >= min_coverage:
                logger.info(f"Transcript complete: {coverage:.1%} coverage achieved")
                continuation_info["success"] = True
                break
            
            # Get last timestamp for continuation
            last_timestamp = self.analyzer.get_last_timestamp(current_transcript)
            if not last_timestamp:
                logger.error("Cannot find last timestamp for continuation")
                continuation_info["error"] = "No timestamp found for continuation"
                break
            
            logger.info(f"Requesting continuation from {last_timestamp:.1f}s "
                       f"({coverage:.1%} -> target: {min_coverage:.1%})")
            
            # Request continuation
            try:
                continuation = await self.request_continuation(
                    audio_url, current_transcript, last_timestamp, episode_metadata
                )
                
                if not continuation:
                    logger.warning(f"Failed to get continuation on attempt {attempts + 1}")
                    continuation_info["consecutive_failures"] += 1
                    continuation_info["api_errors"].append(f"Empty response on attempt {attempts + 1}")
                    
                    # Fail after 3 consecutive empty responses
                    if continuation_info["consecutive_failures"] >= 3:
                        continuation_info["error"] = "Too many consecutive empty continuation responses"
                        continuation_info["failure_type"] = "consecutive_api_failures"
                        break
                    
                    attempts += 1
                    continue
                
                # Reset consecutive failures on success
                continuation_info["consecutive_failures"] = 0
                
                # Add continuation to segments
                segments.append(continuation)
                attempts += 1
                
                logger.info(f"Added continuation segment {len(segments)} ({len(continuation)} chars)")
                
                # Brief pause between requests to avoid overwhelming the API
                if attempts < self.max_attempts:
                    await self._async_sleep(2.0)
                
            except Exception as e:
                logger.error(f"Error requesting continuation: {e}")
                continuation_info["consecutive_failures"] += 1
                continuation_info["api_errors"].append(f"API error on attempt {attempts + 1}: {str(e)}")
                
                # Fail after 3 consecutive API errors
                if continuation_info["consecutive_failures"] >= 3:
                    continuation_info["error"] = f"Too many consecutive API errors: {str(e)}"
                    continuation_info["failure_type"] = "consecutive_api_failures"
                    break
                
                attempts += 1
                # Longer pause after errors
                if attempts < self.max_attempts:
                    await self._async_sleep(5.0)
        
        # Final processing
        final_transcript = self._simple_concatenate(segments)
        final_coverage, _, _ = self.analyzer.calculate_coverage(final_transcript, total_duration)
        
        continuation_info["final_coverage"] = final_coverage
        continuation_info["segments_count"] = len(segments)
        continuation_info["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Determine failure conditions
        if attempts >= self.max_attempts:
            logger.warning(f"Reached maximum continuation attempts ({self.max_attempts})")
            continuation_info["error"] = f"Max attempts ({self.max_attempts}) reached"
            continuation_info["failure_type"] = "max_attempts_exceeded"
        
        elif final_coverage < min_coverage:
            logger.warning(f"Insufficient coverage: {final_coverage:.1%} < {min_coverage:.1%}")
            continuation_info["error"] = f"Insufficient coverage: {final_coverage:.1%} < {min_coverage:.1%}"
            continuation_info["failure_type"] = "insufficient_coverage"
        
        elif len(segments) == 1 and final_coverage < 0.5:
            logger.warning(f"Very low coverage on initial transcript: {final_coverage:.1%}")
            continuation_info["error"] = f"Very low initial coverage: {final_coverage:.1%}"
            continuation_info["failure_type"] = "initial_transcript_too_short"
        
        # Additional failure conditions
        if not continuation_info["success"]:
            if not continuation_info.get("error"):
                continuation_info["error"] = "Unknown failure in continuation process"
                continuation_info["failure_type"] = "unknown"
            
            # Clean up temporary files on failure
            self._cleanup_on_failure(segments)
        
        logger.info(f"Continuation loop completed: {final_coverage:.1%} coverage with {len(segments)} segments")
        
        if continuation_info.get("failure_type"):
            logger.error(f"Episode failed: {continuation_info['failure_type']} - {continuation_info['error']}")
        
        return final_transcript, continuation_info
    
    def _extract_context_from_transcript(self, transcript: str, last_timestamp: float) -> List[str]:
        """Extract the last few lines from transcript for context.
        
        Args:
            transcript: Current transcript
            last_timestamp: Last timestamp in seconds
            
        Returns:
            List of context lines
        """
        try:
            # Split transcript into lines and get the last meaningful lines
            lines = [line.strip() for line in transcript.split('\n') if line.strip()]
            
            # Get last 5-10 lines for context
            context_lines = lines[-10:] if len(lines) >= 10 else lines
            
            # Filter out very short lines or pure timestamp lines
            meaningful_lines = []
            for line in context_lines:
                if len(line) > 10 and not line.replace(':', '').replace(' ', '').isdigit():
                    meaningful_lines.append(line)
            
            # Take last 3-5 meaningful lines
            final_context = meaningful_lines[-5:] if len(meaningful_lines) >= 5 else meaningful_lines
            
            logger.debug(f"Extracted {len(final_context)} context lines")
            return final_context
            
        except Exception as e:
            logger.warning(f"Failed to extract context: {e}")
            return []
    
    def _build_continuation_prompt(self, 
                                 metadata: Dict[str, Any], 
                                 last_timestamp: float,
                                 context_lines: List[str]) -> str:
        """Build prompt for transcript continuation.
        
        Args:
            metadata: Episode metadata
            last_timestamp: Last timestamp in seconds
            context_lines: Previous transcript lines for context
            
        Returns:
            Continuation prompt
        """
        # Convert timestamp to readable format
        hours = int(last_timestamp // 3600)
        minutes = int((last_timestamp % 3600) // 60)
        seconds = int(last_timestamp % 60)
        
        if hours > 0:
            time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            time_str = f"{minutes}:{seconds:02d}"
        
        context_section = "\n".join(context_lines) if context_lines else "No previous context available"
        
        return f"""Please continue the transcript from {time_str}. Maintain the same format with timestamps and speaker identification.

Format each line as: [MM:SS] Speaker Name: What they said

Previous context:
{context_section}

Continue from [{time_str}]:"""
    
    async def _request_continuation_direct(self, 
                                         audio_url: str, 
                                         prompt: str,
                                         episode_metadata: Dict[str, Any]) -> Optional[str]:
        """Make direct continuation request when no specific method exists.
        
        Args:
            audio_url: Audio file URL
            prompt: Continuation prompt
            episode_metadata: Episode metadata
            
        Returns:
            Continuation transcript or None
        """
        try:
            # This would use the Gemini client's general transcription method
            # with the continuation prompt
            logger.info("Making direct continuation request")
            
            # For now, return None since this needs integration with actual client
            # This will be implemented when integrating with the orchestrator
            logger.warning("Direct continuation requests not yet implemented")
            return None
            
        except Exception as e:
            logger.error(f"Direct continuation request failed: {e}")
            return None
    
    def _simple_concatenate(self, segments: List[str]) -> str:
        """Simple concatenation of transcript segments.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Combined transcript
        """
        if not segments:
            return ""
        
        if len(segments) == 1:
            return segments[0]
        
        # Simple concatenation with double newlines between segments
        return "\n\n".join(segment.strip() for segment in segments if segment.strip())
    
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
    
    async def _async_sleep(self, seconds: float):
        """Async sleep helper.
        
        Args:
            seconds: Time to sleep in seconds
        """
        import asyncio
        await asyncio.sleep(seconds)
    
    def _cleanup_on_failure(self, segments: List[str]):
        """Clean up temporary files and resources on failure.
        
        Args:
            segments: List of transcript segments that may have temporary files
        """
        try:
            # For now, just log the cleanup
            # In the future, this could clean up actual temporary files
            logger.info(f"Cleaning up after failure: {len(segments)} segments processed")
            
            # Could implement:
            # - Delete temporary raw transcript files
            # - Clean up partial VTT files
            # - Reset any state variables
            
        except Exception as e:
            logger.warning(f"Failed to cleanup on failure: {e}")
    
    def should_fail_episode(self, continuation_info: Dict[str, Any]) -> bool:
        """Check if episode should be failed based on continuation results.
        
        Args:
            continuation_info: Continuation tracking information
            
        Returns:
            True if episode should be failed
        """
        # Check for explicit failure conditions
        if continuation_info.get("failure_type"):
            return True
        
        # Check for very low coverage
        final_coverage = continuation_info.get("final_coverage", 0.0)
        if final_coverage < 0.3:  # Less than 30% coverage is always a failure
            return True
        
        # Check for no progress (stuck in loop)
        attempts = continuation_info.get("attempts", 0)
        segments_count = continuation_info.get("segments_count", 1)
        if attempts > 5 and segments_count <= 2:  # Many attempts but few segments
            return True
        
        return False
    
    def get_failure_reason(self, continuation_info: Dict[str, Any]) -> str:
        """Get human-readable failure reason.
        
        Args:
            continuation_info: Continuation tracking information
            
        Returns:
            Formatted failure reason
        """
        failure_type = continuation_info.get("failure_type", "unknown")
        error = continuation_info.get("error", "Unknown error")
        final_coverage = continuation_info.get("final_coverage", 0.0)
        attempts = continuation_info.get("attempts", 0)
        
        if failure_type == "max_attempts_exceeded":
            return f"Maximum continuation attempts ({attempts}) reached with {final_coverage:.1%} coverage"
        elif failure_type == "insufficient_coverage":
            return f"Insufficient coverage achieved: {final_coverage:.1%}"
        elif failure_type == "initial_transcript_too_short":
            return f"Initial transcript too short: {final_coverage:.1%} coverage"
        else:
            return f"Episode failed: {error}"
    
    def get_continuation_stats(self) -> Dict[str, Any]:
        """Get statistics about continuation manager usage.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "max_attempts": self.max_attempts,
            "analyzer_initialized": self.analyzer is not None,
            "client_available": self.gemini_client is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }