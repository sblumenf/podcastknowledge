"""YouTube Data API v3 client for episode matching.

This module provides a centralized client for interacting with the YouTube Data API v3,
including search functionality, quota management, and error handling.
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import GoogleAuthError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from src.utils.logging import get_logger
from src.config import Config

logger = get_logger('youtube_api_client')


class YouTubeAPIError(Exception):
    """Base exception for YouTube API errors."""
    pass


class QuotaExceededError(YouTubeAPIError):
    """Raised when YouTube API quota is exceeded."""
    pass


class YouTubeAPIClient:
    """Client for interacting with YouTube Data API v3."""
    
    # API quota costs (in units)
    SEARCH_COST = 100
    VIDEO_LIST_COST = 1
    CHANNEL_LIST_COST = 1
    DAILY_QUOTA_LIMIT = 10000
    
    def __init__(self, api_key: str):
        """Initialize YouTube API client.
        
        Args:
            api_key: YouTube Data API v3 key
            
        Raises:
            ValueError: If API key is invalid
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Valid API key required")
            
        self.api_key = api_key
        self._service = None
        self._quota_used = 0
        self._quota_reset_time = self._get_next_quota_reset()
        
    def _get_next_quota_reset(self) -> datetime:
        """Calculate next quota reset time (midnight Pacific Time)."""
        now = datetime.utcnow()
        # YouTube quotas reset at midnight Pacific Time (UTC-8)
        next_reset = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour >= 8:
            next_reset += timedelta(days=1)
        return next_reset
        
    def _check_quota(self, cost: int) -> None:
        """Check if operation would exceed quota.
        
        Args:
            cost: Cost in quota units
            
        Raises:
            QuotaExceededError: If quota would be exceeded
        """
        # Reset quota counter if past reset time
        if datetime.utcnow() >= self._quota_reset_time:
            self._quota_used = 0
            self._quota_reset_time = self._get_next_quota_reset()
            
        if self._quota_used + cost > self.DAILY_QUOTA_LIMIT:
            hours_until_reset = (self._quota_reset_time - datetime.utcnow()).total_seconds() / 3600
            raise QuotaExceededError(
                f"Daily quota would be exceeded. Used: {self._quota_used}, "
                f"Cost: {cost}, Limit: {self.DAILY_QUOTA_LIMIT}. "
                f"Resets in {hours_until_reset:.1f} hours."
            )
            
    def _use_quota(self, cost: int) -> None:
        """Record quota usage.
        
        Args:
            cost: Cost in quota units
        """
        self._quota_used += cost
        logger.debug(f"Quota used: {cost} units. Total today: {self._quota_used}/{self.DAILY_QUOTA_LIMIT}")
        
    @property
    def service(self):
        """Lazy initialization of YouTube service."""
        if self._service is None:
            try:
                self._service = build('youtube', 'v3', developerKey=self.api_key)
                self._validate_api_key()
            except Exception as e:
                raise YouTubeAPIError(f"Failed to initialize YouTube service: {str(e)}")
        return self._service
        
    def _validate_api_key(self) -> None:
        """Validate API key with a minimal request.
        
        Raises:
            YouTubeAPIError: If API key is invalid
        """
        try:
            # Use a minimal request to validate the key
            self._check_quota(self.CHANNEL_LIST_COST)
            self.service.channels().list(
                part='id',
                id='UC_x5XG1OV2P6uZZ5FSM9Ttw'  # Google Developers channel
            ).execute()
            self._use_quota(self.CHANNEL_LIST_COST)
            logger.info("YouTube API key validated successfully")
        except HttpError as e:
            if e.resp.status == 403:
                raise YouTubeAPIError("Invalid API key or insufficient permissions")
            raise YouTubeAPIError(f"API key validation failed: {str(e)}")
            
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((HttpError,))
    )
    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        order: str = 'relevance',
        published_after: Optional[datetime] = None,
        channel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for videos on YouTube.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            order: Sort order (relevance, date, rating, title, viewCount)
            published_after: Only return videos published after this date
            channel_id: Restrict search to specific channel
            
        Returns:
            List of video search results
            
        Raises:
            YouTubeAPIError: If search fails
            QuotaExceededError: If quota would be exceeded
        """
        self._check_quota(self.SEARCH_COST)
        
        try:
            search_params = {
                'q': query,
                'part': 'id,snippet',
                'maxResults': max_results,
                'order': order,
                'type': 'video'
            }
            
            if published_after:
                search_params['publishedAfter'] = published_after.isoformat() + 'Z'
                
            if channel_id:
                search_params['channelId'] = channel_id
                
            logger.debug(f"Searching YouTube with query: '{query}' (max_results={max_results})")
            
            response = self.service.search().list(**search_params).execute()
            self._use_quota(self.SEARCH_COST)
            
            results = []
            for item in response.get('items', []):
                results.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail_url': item['snippet']['thumbnails']['default']['url']
                })
                
            logger.info(f"Found {len(results)} videos for query: '{query}'")
            return results
            
        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                raise QuotaExceededError("YouTube API quota exceeded")
            raise YouTubeAPIError(f"Video search failed: {str(e)}")
            
    def get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """Get detailed information for videos.
        
        Args:
            video_ids: List of video IDs to get details for
            
        Returns:
            List of video details
            
        Raises:
            YouTubeAPIError: If request fails
            QuotaExceededError: If quota would be exceeded
        """
        if not video_ids:
            return []
            
        # YouTube allows up to 50 video IDs per request
        cost = self.VIDEO_LIST_COST * ((len(video_ids) - 1) // 50 + 1)
        self._check_quota(cost)
        
        try:
            all_details = []
            
            # Process in batches of 50
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                
                response = self.service.videos().list(
                    part='contentDetails,statistics',
                    id=','.join(batch_ids)
                ).execute()
                
                for item in response.get('items', []):
                    duration_iso = item['contentDetails']['duration']
                    duration_seconds = self._parse_iso_duration(duration_iso)
                    
                    all_details.append({
                        'video_id': item['id'],
                        'duration_seconds': duration_seconds,
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'comment_count': int(item['statistics'].get('commentCount', 0))
                    })
                    
            self._use_quota(cost)
            return all_details
            
        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get video details: {str(e)}")
            
    def _parse_iso_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration to seconds.
        
        Args:
            duration: ISO 8601 duration string (e.g., 'PT1H30M45S')
            
        Returns:
            Duration in seconds
        """
        # Remove 'PT' prefix
        duration = duration[2:]
        
        seconds = 0
        
        # Extract hours
        if 'H' in duration:
            hours, duration = duration.split('H')
            seconds += int(hours) * 3600
            
        # Extract minutes
        if 'M' in duration:
            minutes, duration = duration.split('M')
            seconds += int(minutes) * 60
            
        # Extract seconds
        if 'S' in duration:
            secs = duration.rstrip('S')
            if secs:
                seconds += int(secs)
                
        return seconds
        
    def get_channel_uploads_playlist(self, channel_id: str) -> Optional[str]:
        """Get the uploads playlist ID for a channel.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Uploads playlist ID or None if not found
            
        Raises:
            YouTubeAPIError: If request fails
        """
        self._check_quota(self.CHANNEL_LIST_COST)
        
        try:
            response = self.service.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            self._use_quota(self.CHANNEL_LIST_COST)
            
            items = response.get('items', [])
            if items:
                return items[0]['contentDetails']['relatedPlaylists']['uploads']
                
            return None
            
        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get channel uploads playlist: {str(e)}")
            
    def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota usage status.
        
        Returns:
            Dictionary with quota usage information
        """
        return {
            'used': self._quota_used,
            'limit': self.DAILY_QUOTA_LIMIT,
            'remaining': self.DAILY_QUOTA_LIMIT - self._quota_used,
            'reset_time': self._quota_reset_time.isoformat(),
            'hours_until_reset': (self._quota_reset_time - datetime.utcnow()).total_seconds() / 3600
        }