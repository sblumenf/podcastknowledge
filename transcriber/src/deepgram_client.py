"""Deepgram API Client for Podcast Transcription.

This module provides a simplified client for transcribing audio using Deepgram's API.
Includes mock support for testing without API calls.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from src.utils.logging import get_logger

logger = get_logger('deepgram_client')


@dataclass
class DeepgramResponse:
    """Structured response from Deepgram API."""
    
    results: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def transcript(self) -> str:
        """Get the full transcript text."""
        if self.results and 'channels' in self.results:
            channel = self.results['channels'][0]
            if 'alternatives' in channel:
                return channel['alternatives'][0].get('transcript', '')
        return ''
    
    @property
    def words(self) -> list:
        """Get word-level data with timestamps and speaker info."""
        if self.results and 'channels' in self.results:
            channel = self.results['channels'][0]
            if 'alternatives' in channel:
                return channel['alternatives'][0].get('words', [])
        return []


class DeepgramClient:
    """Client for interacting with Deepgram API."""
    
    def __init__(self, api_key: Optional[str] = None, mock_enabled: bool = False):
        """Initialize Deepgram client.
        
        Args:
            api_key: Deepgram API key. If not provided, reads from environment.
            mock_enabled: If True, returns mock responses instead of API calls.
        """
        self.api_key = api_key or os.getenv('DEEPGRAM_API_KEY')
        self.model = os.getenv('DEEPGRAM_MODEL', 'nova-2')
        self.mock_enabled = mock_enabled or os.getenv('DEEPGRAM_MOCK_ENABLED', 'false').lower() == 'true'
        
        if not self.mock_enabled and not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is required")
        
        logger.info(f"Initialized DeepgramClient with model: {self.model}, mock: {self.mock_enabled}")
    
    def transcribe_audio(self, audio_url: str) -> DeepgramResponse:
        """Transcribe audio from URL.
        
        Args:
            audio_url: URL of the audio file to transcribe.
            
        Returns:
            DeepgramResponse with transcription results.
        """
        logger.info(f"Starting transcription for: {audio_url}")
        
        if self.mock_enabled:
            return self._get_mock_response(audio_url)
        
        # Import Deepgram SDK
        from deepgram import DeepgramClient as DGClient, PrerecordedOptions, UrlSource
        
        # Initialize Deepgram client
        dg_client = DGClient(self.api_key)
        
        # Configure transcription options
        options = PrerecordedOptions(
            model=self.model,
            punctuate=True,
            diarize=True,
            smart_format=True,
            utterances=True,
            numerals=True,
            paragraphs=True,
        )
        
        # Create URL source
        source = UrlSource(url=audio_url)
        
        try:
            # Import httpx for timeout configuration
            import httpx
            
            # Create a longer timeout (5 minutes for large files)
            timeout = httpx.Timeout(300.0, connect=60.0)
            
            # Synchronous transcription with extended timeout
            response = dg_client.listen.prerecorded.v('1').transcribe_url(
                source, options, timeout=timeout
            )
            
            logger.info("Transcription completed successfully")
            
            # The response is already a PrerecordedResponse object with the data we need
            # Convert to dictionary format that matches our DeepgramResponse structure
            # The response object has a to_dict() method to convert to dictionary
            response_dict = response.to_dict() if hasattr(response, 'to_dict') else response
            
            return DeepgramResponse(
                results=response_dict.get('results', {}),
                metadata=response_dict.get('metadata', {})
            )
        except Exception as e:
            logger.error(f"Error during transcription: {str(e)}")
            raise
    
    def _get_mock_response(self, audio_url: str) -> DeepgramResponse:
        """Generate mock response for testing.
        
        Args:
            audio_url: URL of the audio file (used to vary mock responses).
            
        Returns:
            Mock DeepgramResponse.
        """
        logger.info("Generating mock Deepgram response")
        
        # Import the mock fixtures
        from tests.fixtures.deepgram_responses import get_successful_transcription
        
        # Get a proper mock response
        mock_data = get_successful_transcription()
        
        return DeepgramResponse(
            results=mock_data["results"],
            metadata=mock_data["metadata"]
        )
        
    def _get_mock_response_old(self, audio_url: str) -> DeepgramResponse:
        # Mock response matching Deepgram's actual format
        mock_data = {
            "metadata": {
                "transaction_key": "mock_transaction_123",
                "request_id": "mock_request_456",
                "sha256": "mock_sha256",
                "created": "2024-06-09T18:00:00.000Z",
                "duration": 180.5,
                "channels": 1,
                "models": [self.model],
                "model_info": {
                    self.model: {
                        "version": "2024-01-01",
                        "arch": "nova",
                        "name": self.model
                    }
                }
            },
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Welcome to the podcast. Today we have a special guest joining us to discuss artificial intelligence and its impact on society. Let me introduce our guest speaker.",
                        "confidence": 0.98765,
                        "words": [
                            {
                                "word": "Welcome",
                                "start": 0.0,
                                "end": 0.5,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.85
                            },
                            {
                                "word": "to",
                                "start": 0.5,
                                "end": 0.6,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.85
                            },
                            {
                                "word": "the",
                                "start": 0.6,
                                "end": 0.7,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.85
                            },
                            {
                                "word": "podcast.",
                                "start": 0.7,
                                "end": 1.2,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.85
                            },
                            {
                                "word": "Today",
                                "start": 2.0,
                                "end": 2.3,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "we",
                                "start": 2.3,
                                "end": 2.4,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "have",
                                "start": 2.4,
                                "end": 2.6,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "a",
                                "start": 2.6,
                                "end": 2.7,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "special",
                                "start": 2.7,
                                "end": 3.1,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "guest",
                                "start": 3.1,
                                "end": 3.4,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "joining",
                                "start": 3.4,
                                "end": 3.8,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "us",
                                "start": 3.8,
                                "end": 4.0,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.87
                            },
                            {
                                "word": "to",
                                "start": 4.0,
                                "end": 4.1,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "discuss",
                                "start": 4.1,
                                "end": 4.5,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "artificial",
                                "start": 4.5,
                                "end": 5.0,
                                "confidence": 0.97,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "intelligence",
                                "start": 5.0,
                                "end": 5.6,
                                "confidence": 0.97,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "and",
                                "start": 5.6,
                                "end": 5.8,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "its",
                                "start": 5.8,
                                "end": 6.0,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "impact",
                                "start": 6.0,
                                "end": 6.4,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "on",
                                "start": 6.4,
                                "end": 6.5,
                                "confidence": 0.99,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "society.",
                                "start": 6.5,
                                "end": 7.0,
                                "confidence": 0.98,
                                "speaker": 0,
                                "speaker_confidence": 0.88
                            },
                            {
                                "word": "Let",
                                "start": 8.0,
                                "end": 8.2,
                                "confidence": 0.99,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            },
                            {
                                "word": "me",
                                "start": 8.2,
                                "end": 8.3,
                                "confidence": 0.99,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            },
                            {
                                "word": "introduce",
                                "start": 8.3,
                                "end": 8.8,
                                "confidence": 0.98,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            },
                            {
                                "word": "our",
                                "start": 8.8,
                                "end": 9.0,
                                "confidence": 0.99,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            },
                            {
                                "word": "guest",
                                "start": 9.0,
                                "end": 9.3,
                                "confidence": 0.99,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            },
                            {
                                "word": "speaker.",
                                "start": 9.3,
                                "end": 9.8,
                                "confidence": 0.98,
                                "speaker": 1,
                                "speaker_confidence": 0.82
                            }
                        ]
                    }]
                }],
                "utterances": [
                    {
                        "start": 0.0,
                        "end": 7.0,
                        "confidence": 0.98,
                        "channel": 0,
                        "transcript": "Welcome to the podcast. Today we have a special guest joining us to discuss artificial intelligence and its impact on society.",
                        "words": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                        "speaker": 0
                    },
                    {
                        "start": 8.0,
                        "end": 9.8,
                        "confidence": 0.98,
                        "channel": 0,
                        "transcript": "Let me introduce our guest speaker.",
                        "words": [21, 22, 23, 24, 25, 26],
                        "speaker": 1
                    }
                ]
            }
        }
        
        return DeepgramResponse(
            results=mock_data["results"],
            metadata=mock_data["metadata"]
        )