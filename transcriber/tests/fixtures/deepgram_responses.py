"""Mock Deepgram API responses for testing.

This module provides realistic mock responses matching Deepgram's actual format
for various transcription scenarios.
"""

from typing import Dict, Any


def get_successful_transcription() -> Dict[str, Any]:
    """Get a successful transcription response with multiple speakers."""
    return {
        "metadata": {
            "transaction_key": "mock_transaction_abc123",
            "request_id": "mock_request_def456",
            "sha256": "mock_sha256_hash",
            "created": "2024-06-09T18:00:00.000Z",
            "duration": 300.5,
            "channels": 1,
            "models": ["nova-2"],
            "model_info": {
                "nova-2": {
                    "version": "2024-01-01",
                    "arch": "nova",
                    "name": "nova-2"
                }
            }
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "Welcome everyone to today's episode. I'm your host, and we have a very special guest with us today. Thank you so much for having me on the show. I'm excited to be here. So let's dive right in. Can you tell us about your latest project?",
                    "confidence": 0.98234,
                    "words": [
                        {"word": "Welcome", "start": 0.0, "end": 0.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "everyone", "start": 0.4, "end": 0.8, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "to", "start": 0.8, "end": 0.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "today's", "start": 0.9, "end": 1.3, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "episode.", "start": 1.3, "end": 1.8, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "I'm", "start": 2.0, "end": 2.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "your", "start": 2.2, "end": 2.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "host,", "start": 2.4, "end": 2.7, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "and", "start": 2.8, "end": 2.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "we", "start": 2.9, "end": 3.0, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "have", "start": 3.0, "end": 3.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "a", "start": 3.2, "end": 3.3, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "very", "start": 3.3, "end": 3.5, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "special", "start": 3.5, "end": 3.9, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "guest", "start": 3.9, "end": 4.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "with", "start": 4.2, "end": 4.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.89},
                        {"word": "us", "start": 4.4, "end": 4.5, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.89},
                        {"word": "today.", "start": 4.5, "end": 4.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.89},
                        {"word": "Thank", "start": 5.5, "end": 5.8, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "you", "start": 5.8, "end": 5.9, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "so", "start": 5.9, "end": 6.0, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "much", "start": 6.0, "end": 6.2, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "for", "start": 6.2, "end": 6.3, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "having", "start": 6.3, "end": 6.6, "confidence": 0.98, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "me", "start": 6.6, "end": 6.7, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "on", "start": 6.7, "end": 6.8, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.87},
                        {"word": "the", "start": 6.8, "end": 6.9, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.87},
                        {"word": "show.", "start": 6.9, "end": 7.2, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.87},
                        {"word": "I'm", "start": 7.4, "end": 7.6, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.86},
                        {"word": "excited", "start": 7.6, "end": 8.0, "confidence": 0.98, "speaker": 1, "speaker_confidence": 0.86},
                        {"word": "to", "start": 8.0, "end": 8.1, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.86},
                        {"word": "be", "start": 8.1, "end": 8.2, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.86},
                        {"word": "here.", "start": 8.2, "end": 8.5, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.86},
                        {"word": "So", "start": 9.0, "end": 9.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "let's", "start": 9.2, "end": 9.5, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "dive", "start": 9.5, "end": 9.8, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "right", "start": 9.8, "end": 10.0, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "in.", "start": 10.0, "end": 10.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.91},
                        {"word": "Can", "start": 10.4, "end": 10.6, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "you", "start": 10.6, "end": 10.7, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "tell", "start": 10.7, "end": 10.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "us", "start": 10.9, "end": 11.0, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "about", "start": 11.0, "end": 11.3, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "your", "start": 11.3, "end": 11.5, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "latest", "start": 11.5, "end": 11.9, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.90},
                        {"word": "project?", "start": 11.9, "end": 12.4, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.90}
                    ]
                }]
            }],
            "utterances": [
                {
                    "start": 0.0,
                    "end": 4.9,
                    "confidence": 0.98,
                    "channel": 0,
                    "transcript": "Welcome everyone to today's episode. I'm your host, and we have a very special guest with us today.",
                    "words": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
                    "speaker": 0
                },
                {
                    "start": 5.5,
                    "end": 8.5,
                    "confidence": 0.98,
                    "channel": 0,
                    "transcript": "Thank you so much for having me on the show. I'm excited to be here.",
                    "words": [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32],
                    "speaker": 1
                },
                {
                    "start": 9.0,
                    "end": 12.4,
                    "confidence": 0.98,
                    "channel": 0,
                    "transcript": "So let's dive right in. Can you tell us about your latest project?",
                    "words": [33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],
                    "speaker": 0
                }
            ]
        }
    }


def get_single_speaker_transcription() -> Dict[str, Any]:
    """Get a transcription with only one speaker (monologue/solo podcast)."""
    return {
        "metadata": {
            "transaction_key": "mock_transaction_xyz789",
            "request_id": "mock_request_uvw012",
            "sha256": "mock_sha256_hash",
            "created": "2024-06-09T18:30:00.000Z",
            "duration": 120.0,
            "channels": 1,
            "models": ["nova-2"],
            "model_info": {
                "nova-2": {
                    "version": "2024-01-01",
                    "arch": "nova",
                    "name": "nova-2"
                }
            }
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "Hello and welcome to my daily podcast. Today I want to share some thoughts about productivity and time management.",
                    "confidence": 0.97856,
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.3, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "and", "start": 0.3, "end": 0.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "welcome", "start": 0.4, "end": 0.8, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "to", "start": 0.8, "end": 0.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "my", "start": 0.9, "end": 1.0, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "daily", "start": 1.0, "end": 1.3, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "podcast.", "start": 1.3, "end": 1.8, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.95},
                        {"word": "Today", "start": 2.0, "end": 2.3, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "I", "start": 2.3, "end": 2.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "want", "start": 2.4, "end": 2.6, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "to", "start": 2.6, "end": 2.7, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "share", "start": 2.7, "end": 3.0, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "some", "start": 3.0, "end": 3.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "thoughts", "start": 3.2, "end": 3.6, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "about", "start": 3.6, "end": 3.9, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "productivity", "start": 3.9, "end": 4.5, "confidence": 0.97, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "and", "start": 4.5, "end": 4.6, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "time", "start": 4.6, "end": 4.8, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.94},
                        {"word": "management.", "start": 4.8, "end": 5.4, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.94}
                    ]
                }]
            }]
        }
    }


def get_multi_speaker_panel() -> Dict[str, Any]:
    """Get a transcription with multiple speakers (panel discussion)."""
    return {
        "metadata": {
            "transaction_key": "mock_transaction_panel123",
            "request_id": "mock_request_panel456",
            "sha256": "mock_sha256_hash",
            "created": "2024-06-09T19:00:00.000Z",
            "duration": 180.0,
            "channels": 1,
            "models": ["nova-2"],
            "model_info": {
                "nova-2": {
                    "version": "2024-01-01",
                    "arch": "nova",
                    "name": "nova-2"
                }
            }
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "Welcome to our panel discussion. I'd like each of you to introduce yourselves. Hi, I'm Alice. Hello, I'm Bob. And I'm Charlie.",
                    "confidence": 0.96543,
                    "words": [
                        {"word": "Welcome", "start": 0.0, "end": 0.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.93},
                        {"word": "to", "start": 0.4, "end": 0.5, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.93},
                        {"word": "our", "start": 0.5, "end": 0.7, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.93},
                        {"word": "panel", "start": 0.7, "end": 1.0, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.93},
                        {"word": "discussion.", "start": 1.0, "end": 1.6, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.93},
                        {"word": "I'd", "start": 1.8, "end": 2.0, "confidence": 0.98, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "like", "start": 2.0, "end": 2.2, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "each", "start": 2.2, "end": 2.4, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "of", "start": 2.4, "end": 2.5, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "you", "start": 2.5, "end": 2.6, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "to", "start": 2.6, "end": 2.7, "confidence": 0.99, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "introduce", "start": 2.7, "end": 3.2, "confidence": 0.97, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "yourselves.", "start": 3.2, "end": 3.7, "confidence": 0.97, "speaker": 0, "speaker_confidence": 0.92},
                        {"word": "Hi,", "start": 4.0, "end": 4.2, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "I'm", "start": 4.2, "end": 4.4, "confidence": 0.99, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "Alice.", "start": 4.4, "end": 4.8, "confidence": 0.98, "speaker": 1, "speaker_confidence": 0.88},
                        {"word": "Hello,", "start": 5.0, "end": 5.3, "confidence": 0.99, "speaker": 2, "speaker_confidence": 0.85},
                        {"word": "I'm", "start": 5.3, "end": 5.5, "confidence": 0.99, "speaker": 2, "speaker_confidence": 0.85},
                        {"word": "Bob.", "start": 5.5, "end": 5.8, "confidence": 0.98, "speaker": 2, "speaker_confidence": 0.85},
                        {"word": "And", "start": 6.0, "end": 6.2, "confidence": 0.99, "speaker": 3, "speaker_confidence": 0.82},
                        {"word": "I'm", "start": 6.2, "end": 6.4, "confidence": 0.99, "speaker": 3, "speaker_confidence": 0.82},
                        {"word": "Charlie.", "start": 6.4, "end": 6.9, "confidence": 0.98, "speaker": 3, "speaker_confidence": 0.82}
                    ]
                }]
            }]
        }
    }


def get_empty_transcription() -> Dict[str, Any]:
    """Get a transcription result with no speech detected."""
    return {
        "metadata": {
            "transaction_key": "mock_transaction_empty",
            "request_id": "mock_request_empty",
            "sha256": "mock_sha256_hash",
            "created": "2024-06-09T20:00:00.000Z",
            "duration": 30.0,
            "channels": 1,
            "models": ["nova-2"],
            "model_info": {
                "nova-2": {
                    "version": "2024-01-01",
                    "arch": "nova",
                    "name": "nova-2"
                }
            }
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "",
                    "confidence": 0.0,
                    "words": []
                }]
            }]
        }
    }


def get_error_response() -> Dict[str, Any]:
    """Get an error response for testing error handling."""
    return {
        "error": {
            "message": "Invalid audio format",
            "type": "invalid_request_error",
            "code": "audio_format_unsupported"
        }
    }