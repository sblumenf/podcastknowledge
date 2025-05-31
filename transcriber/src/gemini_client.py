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

from google import genai
from google.genai import types

from utils.logging import get_logger, log_api_request
from retry_wrapper import (
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
DEFAULT_MODEL = 'gemini-2.5-pro-experimental'


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
    
    def can_make_request(self) -> bool:
        """Check if this key can make a request based on rate limits."""
        now = datetime.now(timezone.utc)
        
        # Check daily limits
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
    
    def __init__(self, api_keys: List[str], model_name: str = DEFAULT_MODEL):
        """Initialize client with multiple API keys.
        
        Args:
            api_keys: List of Gemini API keys
            model_name: Model to use for generation
        """
        if not api_keys:
            raise ValueError("At least one API key must be provided")
        
        self.api_keys = api_keys
        self.model_name = model_name
        self.clients: List[genai.Client] = []
        self.usage_trackers: List[APIKeyUsage] = []
        
        # Initialize clients and usage trackers for each key
        for i, api_key in enumerate(api_keys):
            client = genai.Client(api_key=api_key)
            self.clients.append(client)
            self.usage_trackers.append(APIKeyUsage(key_index=i))
        
        logger.info(f"Initialized Gemini client with {len(api_keys)} API keys")
        
        # Load usage state if exists
        self._load_usage_state()
    
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
    
    def _get_available_client(self) -> Tuple[Optional[genai.Client], Optional[int]]:
        """Get an available client and its index based on rate limits.
        
        Returns:
            Tuple of (client, key_index) or (None, None) if no keys available
        """
        # Check for daily reset needs
        now = datetime.now(timezone.utc)
        for tracker in self.usage_trackers:
            if tracker.last_reset.date() < now.date():
                tracker.reset_daily_usage()
        
        # Find available key
        for i, tracker in enumerate(self.usage_trackers):
            if tracker.can_make_request():
                # Wait if needed for rate limiting
                if tracker.last_request_time:
                    time_since_last = (now - tracker.last_request_time).total_seconds()
                    wait_time = (60 / RATE_LIMITS['rpm']) - time_since_last
                    if wait_time > 0:
                        logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                
                return self.clients[i], i
        
        logger.error("No API keys available due to rate limits")
        return None, None
    
    async def transcribe_audio(self, audio_url: str, episode_metadata: Dict[str, Any]) -> Optional[str]:
        """Transcribe audio from URL to VTT format with speaker diarization.
        
        Args:
            audio_url: URL of the audio file to transcribe
            episode_metadata: Episode information for context
            
        Returns:
            VTT-formatted transcript or None if failed
        """
        client, key_index = self._get_available_client()
        if not client:
            raise Exception("No API keys available")
        
        # Check if we should skip this episode to preserve quota
        tracker = self.usage_trackers[key_index]
        if should_skip_episode(tracker.requests_today):
            logger.warning(f"Skipping episode to preserve daily quota")
            return None
        
        logger.info(f"Starting transcription for: {episode_metadata.get('title', 'Unknown')}")
        logger.info(f"Using API key {key_index + 1}")
        
        # Use the retry wrapper for the actual API call
        try:
            transcript = await self._transcribe_with_retry(
                client, key_index, audio_url, episode_metadata
            )
            return transcript
        except (QuotaExceededException, CircuitBreakerOpenException) as e:
            logger.error(f"Cannot retry transcription: {e}")
            tracker.is_available = False
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            if "quota" in str(e).lower():
                tracker.is_available = False
            return None
    
    @with_retry_and_circuit_breaker('transcribe_audio', max_attempts=2)
    async def _transcribe_with_retry(self, client: genai.Client, key_index: int, 
                                   audio_url: str, episode_metadata: Dict[str, Any]) -> str:
        """Internal method that performs the actual transcription with retry logic.
        
        Args:
            client: Gemini client instance
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
        
        # Check if we'll exceed token limits
        tracker = self.usage_trackers[key_index]
        if tracker.tokens_today + estimated_tokens > RATE_LIMITS['tpd']:
            raise QuotaExceededException("Would exceed daily token limit with this request")
        
        # Make the API call
        start_time = time.time()
        
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=[
                prompt,
                types.Part.from_uri(
                    file_uri=audio_url,
                    mime_type='audio/mpeg'
                )
            ],
            config=types.GenerateContentConfig(
                max_output_tokens=8192,  # Maximum for transcripts
                temperature=0.1,  # Low temperature for accuracy
            )
        )
        
        elapsed_time = time.time() - start_time
        
        # Extract transcript
        transcript = response.text
        if not transcript:
            raise Exception("Empty transcript returned from API")
        
        # Update usage tracking
        # Note: Actual token count would come from response metadata if available
        tracker.update_usage(estimated_tokens)
        log_api_request(key_index + 1, 'transcribe_audio', estimated_tokens)
        
        self._save_usage_state()
        
        logger.info(f"Transcription completed in {elapsed_time:.1f}s")
        return transcript
    
    async def identify_speakers(self, transcript: str, episode_metadata: Dict[str, Any]) -> Dict[str, str]:
        """Identify speakers in transcript based on context.
        
        Args:
            transcript: VTT transcript with generic speaker labels
            episode_metadata: Episode and podcast information
            
        Returns:
            Dictionary mapping speaker labels to identified names/roles
        """
        client, key_index = self._get_available_client()
        if not client:
            raise Exception("No API keys available")
        
        # Check if we should skip this to preserve quota
        tracker = self.usage_trackers[key_index]
        if should_skip_episode(tracker.requests_today):
            logger.warning(f"Skipping speaker identification to preserve daily quota")
            return {}
        
        logger.info("Starting speaker identification")
        logger.info(f"Using API key {key_index + 1}")
        
        # Use the retry wrapper for the actual API call
        try:
            speaker_mapping = await self._identify_speakers_with_retry(
                client, key_index, transcript, episode_metadata
            )
            return speaker_mapping
        except (QuotaExceededException, CircuitBreakerOpenException) as e:
            logger.error(f"Cannot retry speaker identification: {e}")
            tracker.is_available = False
            return {}
        except Exception as e:
            logger.error(f"Speaker identification failed: {str(e)}")
            if "quota" in str(e).lower():
                tracker.is_available = False
            return {}
    
    @with_retry_and_circuit_breaker('identify_speakers', max_attempts=2)
    async def _identify_speakers_with_retry(self, client: genai.Client, key_index: int,
                                          transcript: str, episode_metadata: Dict[str, Any]) -> Dict[str, str]:
        """Internal method that performs speaker identification with retry logic.
        
        Args:
            client: Gemini client instance
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
        if tracker.tokens_today + estimated_tokens > RATE_LIMITS['tpd']:
            raise QuotaExceededException("Would exceed daily token limit with this request")
        
        # Make the API call
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
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
        
        self._save_usage_state()
        
        logger.info(f"Identified speakers: {speaker_mapping}")
        return speaker_mapping
    
    def _build_transcription_prompt(self, metadata: Dict[str, Any]) -> str:
        """Build prompt for audio transcription."""
        return f"""Please transcribe this podcast episode into WebVTT (VTT) format with the following requirements:

1. Include accurate timestamps in HH:MM:SS.mmm format
2. Identify different speakers as SPEAKER_1, SPEAKER_2, etc.
3. Use <v SPEAKER_N> tags for speaker identification
4. Keep each subtitle segment under 2 lines and about 5-7 seconds
5. Include a NOTE block at the beginning with episode metadata

Episode Information:
- Podcast: {metadata.get('podcast_name', 'Unknown')}
- Title: {metadata.get('title', 'Unknown')}
- Date: {metadata.get('publication_date', 'Unknown')}
- Description: {metadata.get('description', '')[:200]}...

Format the output as a valid WebVTT file starting with:
WEBVTT

NOTE
Podcast: {metadata.get('podcast_name', 'Unknown')}
Episode: {metadata.get('title', 'Unknown')}
Date: {metadata.get('publication_date', 'Unknown')}

Then include the timed transcript with speaker tags."""
    
    def _build_speaker_identification_prompt(self, transcript: str, metadata: Dict[str, Any]) -> str:
        """Build prompt for speaker identification."""
        return f"""Analyze this podcast transcript and identify the speakers based on context clues.

Podcast Information:
- Podcast Name: {metadata.get('podcast_name', 'Unknown')}
- Host/Author: {metadata.get('author', 'Unknown')}
- Episode Title: {metadata.get('title', 'Unknown')}
- Description: {metadata.get('description', '')[:300]}...

Transcript excerpt (first 1000 characters):
{transcript[:1000]}...

Please identify each speaker (SPEAKER_1, SPEAKER_2, etc.) based on:
1. Self-introductions or introductions by others
2. References to names in conversation
3. Speaking patterns (host usually introduces the show and guests)
4. Context from the episode title and description

Return a JSON object mapping speaker labels to identified names or roles.
If you cannot identify a speaker with confidence, use descriptive roles like "HOST", "GUEST_1", etc.

Example response format:
{{
  "SPEAKER_1": "Lisa Park (Host)",
  "SPEAKER_2": "Dr. Rahman (Guest)",
  "SPEAKER_3": "GUEST_2"
}}"""
    
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
        except:
            return 60.0  # Default to 1 hour
    
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


def create_gemini_client() -> RateLimitedGeminiClient:
    """Create a Gemini client with API keys from environment."""
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
    
    return RateLimitedGeminiClient(api_keys)