"""YouTube description fetcher service.

This module provides an adapter to reuse the existing YouTube API client from the transcriber module
for fetching video descriptions for speaker identification.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import re
from urllib.parse import urlparse, parse_qs

# Add transcriber module to path to import its YouTube client
transcriber_path = Path(__file__).parent.parent.parent.parent / 'transcriber'
if str(transcriber_path) not in sys.path:
    sys.path.insert(0, str(transcriber_path))

try:
    from src.youtube_api_client import YouTubeAPIClient, YouTubeAPIError, QuotaExceededError
except ImportError:
    # Fallback - create placeholder classes if transcriber module not available
    class YouTubeAPIClient:
        def __init__(self, api_key): pass
    class YouTubeAPIError(Exception): pass
    class QuotaExceededError(Exception): pass

from src.utils.logging import get_logger

logger = get_logger(__name__)


class YouTubeDescriptionFetcher:
    """Adapter class for fetching YouTube video descriptions."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the YouTube description fetcher.
        
        Args:
            api_key: YouTube API key (defaults to env var YOUTUBE_API_KEY)
        """
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            logger.warning("YouTube API key not found. YouTube description fetching will be disabled.")
            self.client = None
        else:
            try:
                self.client = YouTubeAPIClient(self.api_key)
                logger.info("YouTube API client initialized for description fetching")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API client: {e}")
                self.client = None
        
        self._cache = {}  # Simple cache for descriptions
    
    def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Video ID or None if not found
        """
        if not youtube_url:
            return None
        
        # Handle various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        # Try parsing as URL
        try:
            parsed = urlparse(youtube_url)
            if parsed.hostname in ['www.youtube.com', 'youtube.com']:
                query_params = parse_qs(parsed.query)
                if 'v' in query_params:
                    return query_params['v'][0]
            elif parsed.hostname == 'youtu.be':
                return parsed.path.lstrip('/')
        except:
            pass
        
        return None
    
    def get_video_description(self, video_id_or_url: str) -> Optional[str]:
        """Get full video description from YouTube.
        
        Args:
            video_id_or_url: YouTube video ID or URL
            
        Returns:
            Full video description or None if not available
        """
        if not self.client:
            return None
        
        # Extract video ID if URL provided
        if video_id_or_url.startswith('http'):
            video_id = self.extract_video_id(video_id_or_url)
            if not video_id:
                logger.warning(f"Could not extract video ID from URL: {video_id_or_url}")
                return None
        else:
            video_id = video_id_or_url
        
        # Check cache
        if video_id in self._cache:
            logger.debug(f"Returning cached description for video {video_id}")
            return self._cache[video_id]
        
        try:
            # Use the YouTube API client to get video details
            # We need to make a custom request since the existing method doesn't include description
            response = self.client.service.videos().list(
                part='snippet',
                id=video_id
            ).execute()
            
            # Update quota tracking
            self.client._use_quota(self.client.VIDEO_LIST_COST)
            
            items = response.get('items', [])
            if items:
                description = items[0]['snippet'].get('description', '')
                # Cache the description
                self._cache[video_id] = description
                logger.info(f"Retrieved description for video {video_id} ({len(description)} chars)")
                return description
            else:
                logger.warning(f"No video found with ID: {video_id}")
                return None
                
        except QuotaExceededError as e:
            logger.error(f"YouTube API quota exceeded: {e}")
            return None
        except YouTubeAPIError as e:
            logger.error(f"YouTube API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching video description: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if YouTube API is available."""
        return self.client is not None