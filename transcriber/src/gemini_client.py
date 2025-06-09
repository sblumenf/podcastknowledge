"""Gemini API Client with Rate Limiting for Podcast Transcription Pipeline.

This module provides a rate-limited interface to Google's Gemini API,
supporting multi-key authentication and tracking API usage within free tier constraints.
"""

import asyncio
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import json
import urllib.request
import urllib.parse
import tempfile
import mimetypes

import google.generativeai as genai
from google.generativeai import types, GenerationConfig
from google.generativeai.generative_models import GenerativeModel

from src.utils.logging import get_logger, log_api_request
from src.retry_wrapper import (
    with_retry_and_circuit_breaker,
    QuotaExceededException,
    CircuitBreakerOpenException,
    should_skip_episode
)

logger = get_logger('gemini_client')


# Rate limit configuration for Gemini 2.5 Pro Experimental
RATE_LIMITS = {
    'rpm': 5,           # 5 requests per minute
    'tpm': 250_000,     # 250K tokens per minute
    'rpd': 25,          # 25 requests per day
    'tpd': 1_000_000,   # 1M tokens per day
}

# Model configuration
DEFAULT_MODEL = 'gemini-2.5-pro-preview-05-06'


@dataclass
class APIKeyUsage:
    """Tracks usage statistics for a single API key."""
    key_index: int
    requests_today: int = 0
    tokens_today: int = 0
    last_request_time: Optional[datetime] = None
    last_reset: datetime = None
    is_available: bool = True
    
    def __post_init__(self):
        if self.last_reset is None:
            self.last_reset = datetime.now(timezone.utc)
    
    def can_make_request(self, is_paid_tier: bool = False) -> bool:
        """Check if this key can make a request based on rate limits.
        
        Args:
            is_paid_tier: If True, bypass quota limits for paid tier keys
            
        Returns:
            True if key can make a request
        """
        # For paid tier keys, skip quota checks but still check availability
        if is_paid_tier:
            return self.is_available
            
        now = datetime.now(timezone.utc)
        
        # Check daily limits for free tier keys
        if self.requests_today >= RATE_LIMITS['rpd']:
            logger.warning(f"API key {self.key_index + 1} hit daily request limit")
            return False
            
        if self.tokens_today >= RATE_LIMITS['tpd']:
            logger.warning(f"API key {self.key_index + 1} hit daily token limit")
            return False
        
        # Check requests per minute
        if self.last_request_time:
            time_since_last = (now - self.last_request_time).total_seconds()
            if time_since_last < 60 / RATE_LIMITS['rpm']:  # 12 seconds between requests
                return False
        
        return self.is_available
    
    def update_usage(self, tokens_used: int):
        """Update usage statistics after a successful request."""
        self.requests_today += 1
        self.tokens_today += tokens_used
        self.last_request_time = datetime.now(timezone.utc)
    
    def reset_daily_usage(self):
        """Reset daily usage counters."""
        self.requests_today = 0
        self.tokens_today = 0
        self.last_reset = datetime.now(timezone.utc)
        logger.info(f"Reset daily usage for API key {self.key_index + 1}")


class RateLimitedGeminiClient:
    """Gemini API client with rate limiting and multi-key support."""
    
    def __init__(self, api_keys: List[str], model_name: str = DEFAULT_MODEL, 
                 key_rotation_manager = None):
        """Initialize client with multiple API keys.
        
        Args:
            api_keys: List of Gemini API keys
            model_name: Model to use for generation
            key_rotation_manager: Optional KeyRotationManager for advanced quota handling
        """
        if not api_keys:
            raise ValueError("At least one API key must be provided")
        
        self.api_keys = api_keys
        self.model_name = model_name
        self.key_rotation_manager = key_rotation_manager
        self.models: List[GenerativeModel] = []
        self.usage_trackers: List[APIKeyUsage] = []
        
        # Initialize models and usage trackers for each key
        for i, api_key in enumerate(api_keys):
            # Configure API key for this model instance
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            self.models.append(model)
            self.usage_trackers.append(APIKeyUsage(key_index=i))
        
        logger.info(f"Initialized Gemini client with {len(api_keys)} API keys")
        
        # Load usage state if exists
        self._load_usage_state()
    
    def is_paid_tier(self, key_index: int) -> bool:
        """Check if a key is paid tier.
        
        Args:
            key_index: Index of the key to check
            
        Returns:
            True if key is paid tier
        """
        # Use key rotation manager's method if available
        if self.key_rotation_manager and hasattr(self.key_rotation_manager, 'is_paid_tier'):
            return self.key_rotation_manager.is_paid_tier(key_index)
        
        # Fallback: check if USE_PAID_KEY_ONLY is set and this is the first key
        use_paid_only = os.getenv('USE_PAID_KEY_ONLY', 'false').lower() == 'true'
        return key_index == 0 and use_paid_only
    
    def _load_usage_state(self):
        """Load usage state from file if it exists."""
        state_file = Path("data/.gemini_usage.json")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    
                for tracker_data in data.get('trackers', []):
                    idx = tracker_data['key_index']
                    if idx < len(self.usage_trackers):
                        tracker = self.usage_trackers[idx]
                        tracker.requests_today = tracker_data.get('requests_today', 0)
                        tracker.tokens_today = tracker_data.get('tokens_today', 0)
                        
                        # Check if we need to reset (new day)
                        last_reset = datetime.fromisoformat(tracker_data.get('last_reset'))
                        if last_reset.date() < datetime.now(timezone.utc).date():
                            tracker.reset_daily_usage()
                        else:
                            tracker.last_reset = last_reset
                            
                logger.info("Loaded usage state from file")
            except Exception as e:
                logger.warning(f"Failed to load usage state: {e}")
    
    def _save_usage_state(self):
        """Save current usage state to file."""
        state_file = Path("data/.gemini_usage.json")
        state_file.parent.mkdir(exist_ok=True)
        
        data = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'trackers': [
                {
                    'key_index': t.key_index,
                    'requests_today': t.requests_today,
                    'tokens_today': t.tokens_today,
                    'last_reset': t.last_reset.isoformat()
                }
                for t in self.usage_trackers
            ]
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage state: {e}")
    
    def _get_available_client(self) -> Tuple[Optional[GenerativeModel], Optional[int]]:
        """Get an available model and its index based on rate limits.
        
        Returns:
            Tuple of (model, key_index) or (None, None) if no keys available
        """
        # If we have a key rotation manager, use it for smart key selection
        if self.key_rotation_manager:
            try:
                api_key, key_index = self.key_rotation_manager.get_next_key()
                # Configure the API key for this request
                genai.configure(api_key=api_key)
                return self.models[key_index], key_index
            except Exception as e:
                logger.error(f"Key rotation manager failed: {e}")
                # Fall through to legacy logic
        
        # Legacy logic for backward compatibility
        # Check for daily reset needs
        now = datetime.now(timezone.utc)
        for tracker in self.usage_trackers:
            if tracker.last_reset.date() < now.date():
                tracker.reset_daily_usage()
        
        # Find available key
        for i, tracker in enumerate(self.usage_trackers):
            is_paid = self.is_paid_tier(i)
            if tracker.can_make_request(is_paid_tier=is_paid):
                # For free tier keys, wait if needed for rate limiting
                if not is_paid and tracker.last_request_time:
                    time_since_last = (now - tracker.last_request_time).total_seconds()
                    wait_time = (60 / RATE_LIMITS['rpm']) - time_since_last
                    if wait_time > 0:
                        logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                
                # Configure the API key for this request
                genai.configure(api_key=self.api_keys[i])
                if is_paid:
                    logger.info(f"Using paid tier key {i + 1} (no quota limits)")
                return self.models[i], i
        
        logger.error("No API keys available due to rate limits")
        return None, None
    
    async def transcribe_audio(self, audio_url: str, episode_metadata: Dict[str, Any], 
                             validation_config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Transcribe audio from URL to VTT format with speaker diarization.
        
        Args:
            audio_url: URL of the audio file to transcribe
            episode_metadata: Episode information for context
            validation_config: Optional validation configuration
            
        Returns:
            VTT-formatted transcript or None if failed
        """
        model, key_index = self._get_available_client()
        if not model:
            raise Exception("No API keys available")
        
        # Check if we should skip this episode to preserve quota (skip for paid tier keys)
        tracker = self.usage_trackers[key_index]
        is_paid = self.is_paid_tier(key_index)
        if not is_paid and should_skip_episode(tracker.requests_today):
            logger.warning(f"Skipping episode to preserve daily quota")
            return None
        elif is_paid:
            logger.info(f"Using paid tier key - not checking episode skip quota")
        
        logger.info(f"Starting transcription for: {episode_metadata.get('title', 'Unknown')}")
        logger.info(f"Using API key {key_index + 1}")
        
        # Use the retry wrapper for the actual API call
        try:
            transcript = await self._transcribe_with_retry(
                model, key_index, audio_url, episode_metadata
            )
            
            # Validate and continue transcript if enabled and duration is available
            if (transcript and validation_config and 
                validation_config.get('enabled', True) and
                episode_metadata.get('duration')):
                
                # Parse duration to seconds for validation
                duration_str = episode_metadata.get('duration', '0:00')
                duration_seconds = self._parse_duration_to_seconds(duration_str)
                
                if duration_seconds > 0:
                    # Start continuation loop
                    transcript, continuation_info = await self._continuation_loop(
                        transcript, audio_url, episode_metadata, duration_seconds, validation_config
                    )
                    
                    # Store continuation info in episode metadata for progress tracking
                    episode_metadata['_continuation_info'] = continuation_info
            
            return transcript
        except (QuotaExceededException, CircuitBreakerOpenException) as e:
            logger.error(f"Cannot retry transcription: {e}")
            tracker.is_available = False
            # Report error to key rotation manager if available
            if self.key_rotation_manager and 'key_index' in locals():
                self.key_rotation_manager.mark_key_failure(key_index, str(e))
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            if "quota" in str(e).lower():
                tracker.is_available = False
            # Report error to key rotation manager if available
            if self.key_rotation_manager and 'key_index' in locals():
                self.key_rotation_manager.mark_key_failure(key_index, str(e))
            return None
    
    @with_retry_and_circuit_breaker('transcribe_audio', max_attempts=2)
    async def _transcribe_with_retry(self, model: GenerativeModel, key_index: int, 
                                   audio_url: str, episode_metadata: Dict[str, Any]) -> str:
        """Internal method that performs the actual transcription with retry logic.
        
        Args:
            model: Gemini model instance
            key_index: Index of the API key being used
            audio_url: URL of the audio file
            episode_metadata: Episode information
            
        Returns:
            VTT-formatted transcript
            
        Raises:
            Exception: If transcription fails
        """
        # Build transcription prompt
        prompt = self._build_transcription_prompt(episode_metadata)
        
        # Estimate tokens (rough estimate: 2000 tokens per minute of audio)
        duration_str = episode_metadata.get('duration', '0:00')
        duration_minutes = self._parse_duration(duration_str)
        estimated_tokens = int(duration_minutes * 2000)
        
        # Check if we'll exceed token limits (skip for paid tier keys)
        tracker = self.usage_trackers[key_index]
        is_paid = self.is_paid_tier(key_index)
        if not is_paid and tracker.tokens_today + estimated_tokens > RATE_LIMITS['tpd']:
            raise QuotaExceededException("Would exceed daily token limit with this request")
        elif is_paid:
            logger.info(f"Using paid tier key - bypassing token limit check ({estimated_tokens} tokens estimated)")
        
        # Make the API call
        start_time = time.time()
        
        # Download and upload the audio file
        uploaded_file = None
        temp_file_path = None
        try:
            # Download audio file to temporary location
            logger.info(f"Downloading audio from: {audio_url}")
            temp_file_path = await self._download_audio_file(audio_url)
            
            # Upload to Gemini
            logger.info("Uploading audio file to Gemini")
            uploaded_file = await asyncio.to_thread(genai.upload_file, temp_file_path)
            logger.info(f"Uploaded file: {uploaded_file.name}")
            
            # Generate content with both the audio file and prompt
            response = await model.generate_content_async(
                [uploaded_file, prompt],
                generation_config=GenerationConfig(
                    max_output_tokens=8192,  # Maximum for transcripts
                    temperature=0.1,  # Low temperature for accuracy
                )
            )
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            
            # Clean up uploaded file from Gemini
            if uploaded_file:
                try:
                    await asyncio.to_thread(genai.delete_file, uploaded_file.name)
                    logger.debug(f"Deleted uploaded file from Gemini: {uploaded_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete uploaded file: {e}")
        
        elapsed_time = time.time() - start_time
        
        # Extract transcript
        raw_transcript = response.text
        if not raw_transcript:
            raise Exception("Empty transcript returned from API")
        
        # Save raw response as intermediate .txt file for debugging
        if episode_metadata.get('title'):
            self._save_raw_transcript(raw_transcript, episode_metadata)
        
        # Parse the raw transcript response
        parsed_transcript = self._parse_transcript_response(raw_transcript, episode_metadata)
        
        # Update usage tracking
        # Note: Actual token count would come from response metadata if available
        tracker.update_usage(estimated_tokens)
        log_api_request(key_index + 1, 'transcribe_audio', estimated_tokens)
        
        # Report usage to key rotation manager if available
        if self.key_rotation_manager:
            self.key_rotation_manager.update_key_usage(key_index, estimated_tokens)
            self.key_rotation_manager.mark_key_success(key_index)
        
        self._save_usage_state()
        
        logger.info(f"Transcription completed in {elapsed_time:.1f}s")
        return parsed_transcript
    
    async def identify_speakers(self, transcript: str, episode_metadata: Dict[str, Any]) -> Dict[str, str]:
        """Identify speakers in transcript based on context.
        
        Args:
            transcript: VTT transcript with generic speaker labels
            episode_metadata: Episode and podcast information
            
        Returns:
            Dictionary mapping speaker labels to identified names/roles
        """
        model, key_index = self._get_available_client()
        if not model:
            raise Exception("No API keys available")
        
        # Check if we should skip this to preserve quota (skip for paid tier keys)
        tracker = self.usage_trackers[key_index]
        is_paid = self.is_paid_tier(key_index)
        if not is_paid and should_skip_episode(tracker.requests_today):
            logger.warning(f"Skipping speaker identification to preserve daily quota")
            return {}
        elif is_paid:
            logger.info(f"Using paid tier key - not checking speaker identification quota")
        
        logger.info("Starting speaker identification")
        logger.info(f"Using API key {key_index + 1}")
        
        # Use the retry wrapper for the actual API call
        try:
            speaker_mapping = await self._identify_speakers_with_retry(
                model, key_index, transcript, episode_metadata
            )
            return speaker_mapping
        except (QuotaExceededException, CircuitBreakerOpenException) as e:
            logger.error(f"Cannot retry speaker identification: {e}")
            tracker.is_available = False
            # Report error to key rotation manager if available
            if self.key_rotation_manager and 'key_index' in locals():
                self.key_rotation_manager.mark_key_failure(key_index, str(e))
            return {}
        except Exception as e:
            logger.error(f"Speaker identification failed: {str(e)}")
            if "quota" in str(e).lower():
                tracker.is_available = False
            # Report error to key rotation manager if available
            if self.key_rotation_manager and 'key_index' in locals():
                self.key_rotation_manager.mark_key_failure(key_index, str(e))
            return {}
    
    @with_retry_and_circuit_breaker('identify_speakers', max_attempts=2)
    async def _identify_speakers_with_retry(self, model: GenerativeModel, key_index: int,
                                          transcript: str, episode_metadata: Dict[str, Any]) -> Dict[str, str]:
        """Internal method that performs speaker identification with retry logic.
        
        Args:
            model: Gemini model instance
            key_index: Index of the API key being used
            transcript: VTT transcript with generic labels
            episode_metadata: Episode information
            
        Returns:
            Dictionary mapping speaker labels to names
            
        Raises:
            Exception: If identification fails
        """
        # Build speaker identification prompt
        prompt = self._build_speaker_identification_prompt(transcript, episode_metadata)
        
        # Estimate tokens (prompt + transcript analysis)
        estimated_tokens = len(prompt.split()) * 2  # Rough estimate
        
        tracker = self.usage_trackers[key_index]
        is_paid = self.is_paid_tier(key_index)
        if not is_paid and tracker.tokens_today + estimated_tokens > RATE_LIMITS['tpd']:
            raise QuotaExceededException("Would exceed daily token limit with this request")
        elif is_paid:
            logger.info(f"Using paid tier key for speaker identification - bypassing token limit check")
        
        # Make the API call
        response = await model.generate_content_async(
            prompt,
            generation_config=GenerationConfig(
                max_output_tokens=1024,
                temperature=0.3,  # Some creativity for inference
                response_mime_type='application/json',
            )
        )
        
        # Parse response
        try:
            speaker_mapping = json.loads(response.text)
            if not isinstance(speaker_mapping, dict):
                raise ValueError("Response is not a dictionary")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse speaker identification response: {e}")
            raise Exception("Invalid response format from API")
        
        # Update usage tracking
        tracker.update_usage(estimated_tokens)
        log_api_request(key_index + 1, 'identify_speakers', estimated_tokens)
        
        # Report usage to key rotation manager if available
        if self.key_rotation_manager:
            self.key_rotation_manager.update_key_usage(key_index, estimated_tokens)
            self.key_rotation_manager.mark_key_success(key_index)
        
        self._save_usage_state()
        
        logger.info(f"Identified speakers: {speaker_mapping}")
        return speaker_mapping
    
    def _build_transcription_prompt(self, metadata: Dict[str, Any]) -> str:
        """Build simplified prompt for audio transcription."""
        # Get basic episode context
        podcast_name = metadata.get('podcast_name', 'Unknown')
        episode_title = metadata.get('title', 'Unknown')
        description = metadata.get('description', '')
        
        # Extract guest info from description if available
        guest_info = ""
        if description:
            # Simple extraction of guest info - look for common patterns
            lines = description.split('\n')
            for line in lines[:3]:  # Check first 3 lines
                if any(word in line.lower() for word in ['guest', 'interview', 'with', 'featuring']):
                    guest_info = f"\nGuest info: {line.strip()}"
                    break
        
        return f"""I would like a full transcript, time stamped and diarized with clear identification of speaker changes.

Podcast: {podcast_name}
Episode: {episode_title}{guest_info}"""
    
    def _save_raw_transcript(self, raw_transcript: str, metadata: Dict[str, Any]):
        """Save raw transcript response to .txt file for debugging.
        
        Args:
            raw_transcript: Raw transcript text from API
            metadata: Episode metadata
        """
        try:
            # Create safe filename from episode title
            title = metadata.get('title', 'Unknown')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
            
            # Save to data directory
            data_dir = Path("data/raw_transcripts")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{safe_title}_raw.txt"
            filepath = data_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Raw Transcript Response\n")
                f.write(f"# Podcast: {metadata.get('podcast_name', 'Unknown')}\n")
                f.write(f"# Episode: {metadata.get('title', 'Unknown')}\n")
                f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(raw_transcript)
            
            logger.info(f"Saved raw transcript to: {filepath}")
            
        except Exception as e:
            logger.warning(f"Failed to save raw transcript: {e}")
    
    def _parse_transcript_response(self, raw_transcript: str, metadata: Dict[str, Any]) -> str:
        """Parse raw transcript response and extract timestamps.
        
        Args:
            raw_transcript: Raw transcript text from API
            metadata: Episode metadata
            
        Returns:
            Processed transcript with extracted timestamps
        """
        try:
            # For now, return the raw transcript as-is
            # This will be enhanced in Phase 4 when we build the text-to-VTT converter
            logger.info("Processing raw transcript response (Phase 2 - minimal processing)")
            
            # Basic cleaning - remove excessive whitespace
            cleaned_transcript = '\n'.join(line.strip() for line in raw_transcript.split('\n') if line.strip())
            
            return cleaned_transcript
            
        except Exception as e:
            logger.error(f"Failed to parse transcript response: {e}")
            # Return raw transcript as fallback
            return raw_transcript
    
    def _build_speaker_identification_prompt(self, transcript: str, metadata: Dict[str, Any]) -> str:
        """Build prompt for speaker identification."""
        description = metadata.get('description', '')
        
        return f"""Identify the speakers in this podcast transcript using the context provided.

EPISODE: {metadata.get('title', 'Unknown')}
HOST: {metadata.get('author', 'Unknown')}
DESCRIPTION: {description}

TRANSCRIPT EXCERPT:
{transcript[:2000]}

Return a JSON mapping of speaker labels to names. Use actual names from the description when available.

Example: {{"SPEAKER_1": "Mel Robbins (Host)", "SPEAKER_2": "Bryan Stevenson"}}"""
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string to minutes."""
        if not duration_str:
            return 60.0  # Default to 1 hour
        
        # Handle different duration formats
        parts = duration_str.split(':')
        try:
            if len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 60 + minutes + seconds / 60
            elif len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes + seconds / 60
            else:
                return float(duration_str)  # Assume minutes
        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}. Using default 60 minutes.")
            return 60.0  # Default to 1 hour
    
    def _parse_duration_to_seconds(self, duration_str: str) -> int:
        """Parse duration string to total seconds."""
        if not duration_str:
            return 3600  # Default to 1 hour
        
        # Handle different duration formats
        parts = duration_str.split(':')
        try:
            if len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:
                return int(float(duration_str) * 60)  # Assume minutes, convert to seconds
        except Exception as e:
            logger.warning(f"Failed to parse duration to seconds '{duration_str}': {e}. Using default 3600 seconds.")
            return 3600  # Default to 1 hour
    
    def validate_transcript_completeness(self, transcript: str, duration_seconds: int) -> Tuple[bool, float]:
        """Validate if transcript covers the full episode duration.
        
        Args:
            transcript: VTT-formatted transcript
            duration_seconds: Expected episode duration in seconds
            
        Returns:
            Tuple of (is_complete, coverage_percentage)
        """
        if not transcript or not duration_seconds:
            return False, 0.0
        
        try:
            # Find all timestamp lines in the transcript
            import re
            timestamp_pattern = r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})'
            matches = re.findall(timestamp_pattern, transcript)
            
            if not matches:
                logger.warning("No timestamps found in transcript")
                return False, 0.0
            
            # Get the last end timestamp
            last_end_timestamp = matches[-1][1]  # End time of last segment
            
            # Parse the timestamp to seconds
            last_seconds = self._parse_timestamp_to_seconds(last_end_timestamp)
            
            # Calculate coverage percentage
            coverage = last_seconds / duration_seconds
            
            # Consider complete if coverage is at least 85%
            min_coverage = 0.85
            is_complete = coverage >= min_coverage
            
            logger.info(f"Transcript coverage: {coverage:.1%} ({last_seconds}s of {duration_seconds}s)")
            
            return is_complete, coverage
            
        except Exception as e:
            logger.error(f"Failed to validate transcript completeness: {e}")
            return False, 0.0
    
    def _parse_timestamp_to_seconds(self, timestamp: str) -> float:
        """Parse VTT timestamp to seconds.
        
        Args:
            timestamp: Timestamp in format HH:MM:SS.mmm or MM:SS.mmm
            
        Returns:
            Total seconds as float
        """
        parts = timestamp.split(':')
        
        if len(parts) == 3:  # HH:MM:SS.mmm
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_with_ms = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds_with_ms
        elif len(parts) == 2:  # MM:SS.mmm
            minutes = int(parts[0])
            seconds_with_ms = float(parts[1])
            return minutes * 60 + seconds_with_ms
        else:
            return float(timestamp)
    
    async def request_continuation(self, 
                                 audio_file: str, 
                                 existing_transcript: str,
                                 last_timestamp: float,
                                 episode_metadata: Dict[str, Any]) -> Optional[str]:
        """Request continuation of transcript from the last timestamp.
        
        Args:
            audio_file: URL of the audio file
            existing_transcript: Current partial transcript
            last_timestamp: Timestamp (in seconds) where transcript ended
            episode_metadata: Episode information for context
            
        Returns:
            Continuation transcript or None if failed
        """
        model, key_index = self._get_available_client()
        if not model:
            logger.error("No API keys available for continuation request")
            return None
        
        try:
            # Get the last few lines of the existing transcript for context
            context_lines = self._extract_context_from_transcript(existing_transcript, last_timestamp)
            
            # Build continuation prompt
            prompt = self._build_continuation_prompt(
                episode_metadata, last_timestamp, context_lines
            )
            
            logger.info(f"Requesting continuation from {last_timestamp:.1f}s")
            
            # Make the API call with same settings as original transcription
            response = await model.generate_content_async(
                prompt,
                generation_config=GenerationConfig(
                    max_output_tokens=8192,  # Same as original
                    temperature=0.1,  # Low temperature for accuracy
                )
            )
            
            continuation = response.text
            if not continuation:
                logger.warning("Empty continuation returned from API")
                return None
            
            # Update usage tracking
            tracker = self.usage_trackers[key_index]
            estimated_tokens = 2000  # Rough estimate for continuation
            tracker.update_usage(estimated_tokens)
            
            logger.info(f"Received continuation transcript ({len(continuation)} chars)")
            return continuation
            
        except Exception as e:
            logger.error(f"Continuation request failed: {e}")
            return None
    
    def _extract_context_from_transcript(self, transcript: str, last_timestamp: float) -> List[str]:
        """Extract the last few lines from transcript for context.
        
        Args:
            transcript: Current transcript
            last_timestamp: Last timestamp in seconds
            
        Returns:
            List of context lines
        """
        try:
            import re
            
            # Find all VTT cues
            cue_pattern = r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*\n([^0-9]+?)(?=\n\d{1,2}:\d{2}:\d{2}\.\d{3}|$)'
            matches = re.findall(cue_pattern, transcript, re.DOTALL | re.MULTILINE)
            
            if not matches:
                return []
            
            # Get the last 3-5 cues for context
            context_cues = matches[-5:] if len(matches) >= 5 else matches
            
            context_lines = []
            for start_time, end_time, text in context_cues:
                # Clean up the text (remove voice tags for readability)
                clean_text = re.sub(r'<v [^>]+>', '', text.strip())
                context_lines.append(f"{start_time} --> {end_time}: {clean_text}")
            
            return context_lines
            
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
        # Convert timestamp to VTT format
        hours = int(last_timestamp // 3600)
        minutes = int((last_timestamp % 3600) // 60)
        seconds = int(last_timestamp % 60)
        milliseconds = int((last_timestamp * 1000) % 1000)
        start_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
        context_section = "\n".join(context_lines) if context_lines else "No previous context available"
        
        return f"""Continue transcribing this podcast episode from timestamp {start_time} onward.

Episode Information:
- Podcast: {metadata.get('podcast_name', 'Unknown')}
- Title: {metadata.get('title', 'Unknown')}
- Date: {metadata.get('publication_date', 'Unknown')}

Previous transcript context (last few segments):
{context_section}

Please continue the transcript from {start_time} onward using the same format:
1. Use WebVTT format with proper timestamps (HH:MM:SS.mmm --> HH:MM:SS.mmm)
2. Include speaker identification with <v SPEAKER_N> tags
3. Maintain consistent speaker numbering from the context above
4. Keep segments 5-7 seconds long and under 2 lines of text
5. Start immediately from {start_time} - do not repeat previous content

Continue the transcript:"""
    
    async def _continuation_loop(self, 
                               initial_transcript: str,
                               audio_url: str,
                               episode_metadata: Dict[str, Any],
                               duration_seconds: int,
                               validation_config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Execute the full continuation loop until transcript is complete.
        
        Args:
            initial_transcript: Initial transcript from first request
            audio_url: Audio file URL
            episode_metadata: Episode metadata
            duration_seconds: Expected duration in seconds
            validation_config: Validation configuration
            
        Returns:
            Tuple of (complete transcript, continuation tracking info)
        """
        segments = [initial_transcript]
        attempts = 0
        max_attempts = validation_config.get('max_continuation_attempts', 10)
        min_coverage = validation_config.get('min_coverage_ratio', 0.85)
        
        logger.info("Starting transcript validation and continuation loop")
        
        while attempts < max_attempts:
            # Stitch all segments so far
            current_transcript = self.stitch_transcripts(segments)
            
            # Validate completeness
            is_complete, coverage = self.validate_transcript_completeness(
                current_transcript, duration_seconds
            )
            
            logger.info(f"Attempt {attempts + 1}: {coverage:.1%} coverage, "
                       f"{'COMPLETE' if is_complete else 'INCOMPLETE'}")
            
            if is_complete:
                logger.info(f"Transcript validation passed: {coverage:.1%} coverage")
                tracking_info = {
                    'continuation_attempts': attempts,
                    'final_coverage_ratio': coverage,
                    'segment_count': len(segments)
                }
                return current_transcript, tracking_info
            
            # Extract last timestamp for continuation
            try:
                import re
                timestamp_pattern = r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})'
                matches = re.findall(timestamp_pattern, current_transcript)
                
                if not matches:
                    logger.error("No timestamps found in transcript for continuation")
                    break
                
                last_timestamp_str = matches[-1][1]  # End time of last segment
                last_timestamp = self._parse_timestamp_to_seconds(last_timestamp_str)
                
                logger.info(f"Requesting continuation from {last_timestamp:.1f}s "
                           f"({coverage:.1%} -> target: {min_coverage:.1%})")
                
                # Request continuation
                continuation = await self.request_continuation(
                    audio_url, current_transcript, last_timestamp, episode_metadata
                )
                
                if not continuation:
                    logger.warning(f"Failed to get continuation on attempt {attempts + 1}")
                    break
                
                # Add continuation to segments
                segments.append(continuation)
                attempts += 1
                
                logger.info(f"Received continuation segment {len(segments)}")
                
            except Exception as e:
                logger.error(f"Error in continuation loop: {e}")
                break
        
        # Final stitching and validation
        final_transcript = self.stitch_transcripts(segments)
        final_complete, final_coverage = self.validate_transcript_completeness(
            final_transcript, duration_seconds
        )
        
        if attempts >= max_attempts:
            logger.warning(f"Reached maximum continuation attempts ({max_attempts})")
        
        logger.info(f"Final transcript: {final_coverage:.1%} coverage with {len(segments)} segments")
        
        if not final_complete:
            logger.warning(f"Transcript remains incomplete: {final_coverage:.1%} coverage "
                          f"(minimum: {min_coverage:.1%})")
        
        tracking_info = {
            'continuation_attempts': attempts,
            'final_coverage_ratio': final_coverage,
            'segment_count': len(segments)
        }
        
        return final_transcript, tracking_info
    
    def stitch_transcripts(self, segments: List[str], overlap_seconds: float = 2.0) -> str:
        """Combine transcript segments into a single VTT file.
        
        Args:
            segments: List of VTT transcript segments to combine
            overlap_seconds: Overlap tolerance in seconds for removing duplicates
            
        Returns:
            Combined VTT transcript
        """
        if not segments:
            return ""
        
        if len(segments) == 1:
            return segments[0]
        
        try:
            # Parse all segments into structured data
            all_cues = []
            for i, segment in enumerate(segments):
                cues = self._parse_vtt_cues(segment)
                logger.info(f"Segment {i+1}: {len(cues)} cues")
                all_cues.extend(cues)
            
            # Sort cues by start time
            all_cues.sort(key=lambda cue: cue['start_seconds'])
            
            # Remove overlapping/duplicate cues
            deduplicated_cues = self._remove_overlapping_cues(all_cues, overlap_seconds)
            
            # Rebuild VTT file
            stitched_transcript = self._rebuild_vtt_from_cues(deduplicated_cues)
            
            logger.info(f"Stitched transcript: {len(deduplicated_cues)} total cues")
            return stitched_transcript
            
        except Exception as e:
            logger.error(f"Failed to stitch transcripts: {e}")
            # Fallback: concatenate segments with basic header cleanup
            return self._simple_concatenate(segments)
    
    def _parse_vtt_cues(self, vtt_content: str) -> List[Dict[str, Any]]:
        """Parse VTT content into structured cue data.
        
        Args:
            vtt_content: VTT content string
            
        Returns:
            List of cue dictionaries
        """
        import re
        
        cues = []
        
        # Pattern to match VTT cues
        cue_pattern = r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*\n(.+?)(?=\n\d{1,2}:\d{2}:\d{2}\.\d{3}|\n\n|$)'
        matches = re.findall(cue_pattern, vtt_content, re.DOTALL | re.MULTILINE)
        
        for start_time, end_time, text in matches:
            try:
                cue = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_seconds': self._parse_timestamp_to_seconds(start_time),
                    'end_seconds': self._parse_timestamp_to_seconds(end_time),
                    'text': text.strip()
                }
                cues.append(cue)
            except Exception as e:
                logger.warning(f"Failed to parse cue: {e}")
                continue
        
        return cues
    
    def _remove_overlapping_cues(self, cues: List[Dict[str, Any]], 
                                overlap_seconds: float) -> List[Dict[str, Any]]:
        """Remove overlapping or duplicate cues.
        
        Args:
            cues: List of cue dictionaries sorted by start time
            overlap_seconds: Overlap tolerance in seconds
            
        Returns:
            Deduplicated list of cues
        """
        if not cues:
            return []
        
        deduplicated = [cues[0]]  # Always keep first cue
        
        for current_cue in cues[1:]:
            last_cue = deduplicated[-1]
            
            # Check if this cue overlaps significantly with the last one
            time_gap = current_cue['start_seconds'] - last_cue['end_seconds']
            
            if time_gap >= -overlap_seconds:  # No significant overlap
                deduplicated.append(current_cue)
            else:
                # Check if the texts are similar (might be duplicate)
                if self._are_texts_similar(current_cue['text'], last_cue['text']):
                    # Skip this cue as it's likely a duplicate
                    logger.debug(f"Skipping duplicate cue at {current_cue['start_time']}")
                    continue
                else:
                    # Different text but overlapping time - adjust start time
                    adjusted_start = last_cue['end_seconds'] + 0.1  # Small gap
                    current_cue['start_seconds'] = adjusted_start
                    current_cue['start_time'] = self._seconds_to_vtt_timestamp(adjusted_start)
                    deduplicated.append(current_cue)
                    logger.debug(f"Adjusted overlapping cue start time to {current_cue['start_time']}")
        
        return deduplicated
    
    def _are_texts_similar(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Check if two text strings are similar enough to be considered duplicates.
        
        Args:
            text1: First text
            text2: Second text
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            True if texts are similar
        """
        # Remove voice tags and normalize
        import re
        clean_text1 = re.sub(r'<v [^>]+>', '', text1).strip().lower()
        clean_text2 = re.sub(r'<v [^>]+>', '', text2).strip().lower()
        
        if not clean_text1 or not clean_text2:
            return False
        
        # Simple similarity check - could be improved with proper text similarity
        if clean_text1 == clean_text2:
            return True
        
        # Check if one text is contained in the other (common with continuations)
        shorter, longer = (clean_text1, clean_text2) if len(clean_text1) < len(clean_text2) else (clean_text2, clean_text1)
        return shorter in longer and len(shorter) / len(longer) > threshold
    
    def _seconds_to_vtt_timestamp(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            VTT timestamp string (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds * 1000) % 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    def _rebuild_vtt_from_cues(self, cues: List[Dict[str, Any]]) -> str:
        """Rebuild VTT content from cue data.
        
        Args:
            cues: List of cue dictionaries
            
        Returns:
            Complete VTT content
        """
        lines = ["WEBVTT", ""]
        
        for cue in cues:
            lines.append(f"{cue['start_time']} --> {cue['end_time']}")
            lines.append(cue['text'])
            lines.append("")  # Empty line between cues
        
        return '\n'.join(lines)
    
    def _simple_concatenate(self, segments: List[str]) -> str:
        """Simple fallback concatenation of VTT segments.
        
        Args:
            segments: List of VTT segments
            
        Returns:
            Concatenated VTT content
        """
        # Start with header from first segment
        result = "WEBVTT\n\n"
        
        for segment in segments:
            # Remove WEBVTT header and NOTE blocks from subsequent segments
            lines = segment.split('\n')
            in_content = False
            
            for line in lines:
                if line.strip() and not line.startswith('WEBVTT') and not line.startswith('NOTE'):
                    in_content = True
                
                if in_content:
                    result += line + '\n'
        
        return result
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary for all API keys."""
        return {
            f"key_{i+1}": {
                "requests_today": tracker.requests_today,
                "tokens_today": tracker.tokens_today,
                "requests_remaining": RATE_LIMITS['rpd'] - tracker.requests_today,
                "tokens_remaining": RATE_LIMITS['tpd'] - tracker.tokens_today,
                "is_available": tracker.is_available
            }
            for i, tracker in enumerate(self.usage_trackers)
        }
    
    async def _download_audio_file(self, audio_url: str) -> str:
        """Download audio file from URL to temporary location.
        
        Args:
            audio_url: URL of the audio file to download
            
        Returns:
            Path to the downloaded temporary file
            
        Raises:
            Exception: If download fails
        """
        try:
            # Create a temporary file with appropriate extension
            url_path = urllib.parse.urlparse(audio_url).path
            extension = os.path.splitext(url_path)[1] or '.mp3'
            
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
                temp_path = temp_file.name
                
            # Download the file
            logger.info(f"Downloading audio to: {temp_path}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            request = urllib.request.Request(audio_url, headers=headers)
            
            # Use asyncio to avoid blocking
            def download():
                with urllib.request.urlopen(request, timeout=300) as response:
                    with open(temp_path, 'wb') as f:
                        # Download in chunks
                        chunk_size = 1024 * 1024  # 1MB chunks
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
            
            await asyncio.to_thread(download)
            
            # Verify file was downloaded
            file_size = os.path.getsize(temp_path)
            logger.info(f"Downloaded {file_size / (1024*1024):.1f}MB")
            
            if file_size == 0:
                os.unlink(temp_path)
                raise Exception("Downloaded file is empty")
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to download audio file: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


def create_gemini_client(key_rotation_manager=None) -> RateLimitedGeminiClient:
    """Create a Gemini client with API keys from environment.
    
    Args:
        key_rotation_manager: Optional KeyRotationManager for quota handling
    """
    api_keys = []
    
    # Try to load multiple API keys
    for i in range(1, 5):  # Support up to 4 keys
        key = os.getenv(f'GEMINI_API_KEY_{i}')
        if key:
            api_keys.append(key)
    
    # Fallback to single key variable
    if not api_keys:
        single_key = os.getenv('GEMINI_API_KEY')
        if single_key:
            api_keys.append(single_key)
    
    if not api_keys:
        raise ValueError("No Gemini API keys found in environment")
    
    logger.info(f"Found {len(api_keys)} API key(s) in environment")
    
    return RateLimitedGeminiClient(api_keys, key_rotation_manager=key_rotation_manager)