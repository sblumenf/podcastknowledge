"""YouTube search functionality for finding podcast episode URLs.

This module provides a simple YouTube search implementation to find YouTube URLs
for podcast episodes that don't have them in their VTT metadata.
"""

import os
import logging
import time
from typing import Optional, List, Dict
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeSearcher:
    """Simple YouTube search functionality for finding podcast episode URLs."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube searcher.
        
        Args:
            api_key: YouTube Data API key. If not provided, will look for
                    YOUTUBE_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YouTube API key not provided. Set YOUTUBE_API_KEY environment variable or pass api_key parameter.")
        
        # Initialize YouTube API client
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        
        # Rate limiting - YouTube allows 10,000 units per day
        # Search costs 100 units, so we can do ~100 searches per day
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds between requests
    
    def search_youtube_url(
        self, 
        podcast_name: str, 
        episode_title: str,
        published_date: Optional[str] = None
    ) -> Optional[str]:
        """Search for a YouTube URL for a podcast episode.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            published_date: Optional publication date (YYYY-MM-DD format)
            
        Returns:
            YouTube URL if found, None otherwise
        """
        # Rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        
        # Build search query
        query = f'"{podcast_name}" "{episode_title}"'
        
        try:
            # Execute search
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=5,
                type='video'
            ).execute()
            
            self.last_request_time = time.time()
            
            # Process results
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                # Basic validation - check if podcast name appears in channel or title
                channel_title = snippet.get('channelTitle', '').lower()
                video_title = snippet.get('title', '').lower()
                
                podcast_name_lower = podcast_name.lower()
                episode_words = set(episode_title.lower().split())
                
                # Check if this looks like the right video
                if (podcast_name_lower in channel_title or 
                    podcast_name_lower in video_title):
                    
                    # Check if at least some episode words appear in video title
                    title_words = set(video_title.split())
                    matching_words = episode_words & title_words
                    
                    if len(matching_words) >= min(3, len(episode_words) // 2):
                        # Build YouTube URL
                        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        logger.info(f"Found YouTube URL for '{episode_title}': {youtube_url}")
                        return youtube_url
            
            logger.warning(f"No suitable YouTube URL found for '{podcast_name}' - '{episode_title}'")
            return None
            
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during YouTube search: {e}")
            return None
    
    def batch_search(
        self, 
        episodes: List[Dict[str, str]], 
        delay: float = 1.0
    ) -> Dict[str, Optional[str]]:
        """Search for YouTube URLs for multiple episodes.
        
        Args:
            episodes: List of dicts with 'podcast_name', 'episode_title', 
                     and optionally 'published_date'
            delay: Delay between searches in seconds
            
        Returns:
            Dict mapping episode identifiers to YouTube URLs (or None)
        """
        results = {}
        
        for episode in episodes:
            podcast_name = episode.get('podcast_name', '')
            episode_title = episode.get('episode_title', '')
            published_date = episode.get('published_date')
            
            if not podcast_name or not episode_title:
                logger.warning("Skipping episode with missing podcast_name or episode_title")
                continue
            
            # Create identifier for this episode
            episode_id = f"{podcast_name}::{episode_title}"
            
            # Search for URL
            youtube_url = self.search_youtube_url(
                podcast_name, 
                episode_title,
                published_date
            )
            
            results[episode_id] = youtube_url
            
            # Delay between requests
            if delay > 0:
                time.sleep(delay)
        
        return results


# Convenience function for simple usage
def search_youtube_url(
    podcast_name: str, 
    episode_title: str,
    published_date: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[str]:
    """Convenience function to search for a YouTube URL.
    
    Args:
        podcast_name: Name of the podcast
        episode_title: Title of the episode
        published_date: Optional publication date (YYYY-MM-DD format)
        api_key: Optional API key (uses environment variable if not provided)
        
    Returns:
        YouTube URL if found, None otherwise
    """
    try:
        searcher = YouTubeSearcher(api_key)
        return searcher.search_youtube_url(podcast_name, episode_title, published_date)
    except ValueError as e:
        logger.error(f"Failed to initialize YouTube searcher: {e}")
        return None