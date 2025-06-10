"""YouTube URL Search Module for Podcast Transcription Pipeline.

This module handles finding YouTube URLs for podcast episodes through
RSS extraction and optional external search methods.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from src.utils.logging import get_logger
from src.config import Config

logger = get_logger('youtube_searcher')


class YouTubeSearcher:
    """Searches for YouTube URLs related to podcast episodes."""
    
    def __init__(self, config: Config):
        """Initialize YouTube searcher.
        
        Args:
            config: Application configuration
        """
        self.config = config  # Store config for tests
        self.search_enabled = getattr(config.youtube_search, 'enabled', True)
        self.method = getattr(config.youtube_search, 'method', 'rss_only')
        self.cache_results = getattr(config.youtube_search, 'cache_results', True)
        self.fuzzy_match_threshold = getattr(config.youtube_search, 'fuzzy_match_threshold', 0.85)
        self.duration_tolerance = getattr(config.youtube_search, 'duration_tolerance', 0.1)
        self.max_search_results = getattr(config.youtube_search, 'max_search_results', 5)
        
        # Initialize cache
        # Use config-based cache path if available, otherwise default
        cache_dir = getattr(getattr(config, 'output', None), 'base_dir', 'data')
        self.cache_file = Path(cache_dir) / ".youtube_cache.json"
        self.cache = {}
        self._cache_loaded = False
    
    async def search_youtube_url(self, 
                          episode_title: str,
                          episode_description: Optional[str] = None,
                          episode_guid: Optional[str] = None,
                          podcast_name: Optional[str] = None,
                          episode_number: Optional[int] = None,
                          duration_seconds: Optional[int] = None) -> Optional[str]:
        """Search for YouTube URL for the given episode.
        
        Args:
            episode_title: Title of the episode
            episode_description: Episode description (for RSS extraction)
            episode_guid: Unique identifier for the episode
            podcast_name: Name of the podcast
            episode_number: Episode number if available
            duration_seconds: Episode duration for validation
            
        Returns:
            YouTube URL if found, None otherwise
        """
        if not self.search_enabled:
            return None
        
        # Create cache key
        if episode_guid:
            cache_key = f"{episode_title}_{episode_guid}"
        else:
            cache_key = f"{episode_title}_"
        
        # Load cache lazily on first use
        if self.cache_results and not self._cache_loaded:
            self.cache = self._load_cache()
            self._cache_loaded = True
            
        # Check cache first
        if self.cache_results and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            logger.debug(f"Cache hit for {episode_title}: {cached_result}")
            return cached_result if cached_result != "NOT_FOUND" else None
        
        # Try different search methods based on configuration
        youtube_url = None
        
        if self.method == "rss_only":
            # Only extract from RSS description
            if episode_description:
                youtube_url = self._extract_youtube_url_from_text(episode_description)
                if youtube_url:
                    logger.info(f"Found YouTube URL in RSS for {episode_title}: {youtube_url}")
        
        elif self.method == "simple":
            # First try RSS, then simple YouTube API search
            if episode_description:
                youtube_url = self._extract_youtube_url_from_text(episode_description)
                if youtube_url:
                    logger.info(f"Found YouTube URL in RSS for {episode_title}: {youtube_url}")
            
            # If RSS failed, try simple YouTube API search
            if not youtube_url and podcast_name:
                youtube_url = await self._simple_youtube_search(podcast_name, episode_title, duration_seconds)
                if youtube_url:
                    logger.info(f"Found YouTube URL via simple search for {episode_title}: {youtube_url}")
        
        elif self.method == "advanced":
            # RSS first, then use the complex episode matcher system (future implementation)
            if episode_description:
                youtube_url = self._extract_youtube_url_from_text(episode_description)
                if youtube_url:
                    logger.info(f"Found YouTube URL in RSS for {episode_title}: {youtube_url}")
            
            # Future: integrate with youtube_episode_matcher for complex search
            if not youtube_url:
                logger.debug("Advanced YouTube search not yet implemented")
        
        else:
            logger.warning(f"Unknown YouTube search method: {self.method}, falling back to RSS only")
            if episode_description:
                youtube_url = self._extract_youtube_url_from_text(episode_description)
                if youtube_url:
                    logger.info(f"Found YouTube URL in RSS for {episode_title}: {youtube_url}")
        
        # Cache the result
        if self.cache_results:
            cache_value = youtube_url if youtube_url else "NOT_FOUND"
            self.cache[cache_key] = cache_value
            self._save_cache()
        
        return youtube_url
    
    async def _simple_youtube_search(self, podcast_name: str, episode_title: str, 
                                   duration_seconds: Optional[int] = None) -> Optional[str]:
        """Perform a simple YouTube API search for the episode.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            duration_seconds: Expected duration for validation
            
        Returns:
            YouTube URL if found with confidence, None otherwise
        """
        try:
            import requests
            import os
            
            # Get YouTube API key from config
            api_key = getattr(self.config.youtube_api, 'api_key', '') or os.getenv('YOUTUBE_API_KEY')
            if not api_key:
                logger.warning("No YouTube API key configured for simple search")
                return None
            
            # Build simple search query: "Podcast Name" "Episode Title" (truncated)
            episode_title_short = episode_title[:50] if len(episode_title) > 50 else episode_title
            query = f'"{podcast_name}" "{episode_title_short}"'
            
            # YouTube Data API search
            url = 'https://www.googleapis.com/youtube/v3/search'
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': 5,
                'key': api_key
            }
            
            logger.debug(f"Simple YouTube search query: {query}")
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"YouTube API search failed: {response.status_code}")
                return None
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                logger.debug(f"No YouTube results found for query: {query}")
                return None
            
            # Simple validation: take first result if it looks reasonable
            first_result = items[0]
            video_id = first_result['id']['videoId']
            video_title = first_result['snippet']['title']
            channel_title = first_result['snippet']['channelTitle']
            
            # Basic confidence check: video title should contain some podcast keywords
            podcast_words = set(podcast_name.lower().split())
            video_words = set(video_title.lower().split())
            
            # Check if there's reasonable overlap between podcast name and video title/channel
            title_overlap = len(podcast_words & video_words) / len(podcast_words) if podcast_words else 0
            channel_overlap = len(podcast_words & set(channel_title.lower().split())) / len(podcast_words) if podcast_words else 0
            
            confidence = max(title_overlap, channel_overlap)
            min_confidence = 0.3  # Lower threshold for simple mode
            
            if confidence >= min_confidence:
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Simple search found video (confidence: {confidence:.2f}): {video_title} by {channel_title}")
                return youtube_url
            else:
                logger.debug(f"Low confidence match ({confidence:.2f}): {video_title} by {channel_title}")
                return None
                
        except Exception as e:
            logger.warning(f"Simple YouTube search failed: {e}")
            return None
    
    def _extract_youtube_url_from_text(self, text: str) -> Optional[str]:
        """Extract YouTube URL from RSS text content.
        
        Args:
            text: Text content to search (description, content, etc.)
            
        Returns:
            First valid YouTube URL found, None otherwise
        """
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://(?:www\.)?youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            r'https?://(?:m\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://(?:music\.)?youtube\.com/watch\?v=[\w-]+'
        ]
        
        for pattern in youtube_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return the first valid match without normalization
                # to preserve the original format
                return matches[0]
        
        return None
    
    def _extract_from_rss(self, text: str) -> Optional[str]:
        """Alias for _extract_youtube_url_from_text for backward compatibility."""
        return self._extract_youtube_url_from_text(text)
    
    def _normalize_youtube_url(self, url: str) -> str:
        """Normalize YouTube URL to standard format.
        
        Args:
            url: Raw YouTube URL
            
        Returns:
            Normalized YouTube URL
        """
        # Extract video ID from various YouTube URL formats
        video_id_pattern = r'(?:v=|be/|embed/)([a-zA-Z0-9_-]{11})'
        match = re.search(video_id_pattern, url)
        
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Return original URL if can't extract video ID
        return url
    
    def _search_with_yt_dlp(self,
                           podcast_name: str,
                           episode_title: str,
                           episode_number: Optional[int] = None,
                           duration_seconds: Optional[int] = None) -> Optional[str]:
        """Search YouTube using yt-dlp (requires approval for implementation).
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            episode_number: Episode number if available
            duration_seconds: Episode duration for validation
            
        Returns:
            YouTube URL if found, None otherwise
        """
        # This method would be implemented if yt-dlp dependency is approved
        # Implementation would:
        # 1. Use yt-dlp to search YouTube with various query combinations
        # 2. Filter results using fuzzy matching
        # 3. Validate results using duration if available
        # 4. Return best match
        
        logger.debug("yt-dlp search method not implemented (requires approval)")
        return None
    
    def _fuzzy_match(self, search_title: str, result_title: str) -> float:
        """Calculate fuzzy match score between titles.
        
        Args:
            search_title: Title we're searching for
            result_title: Title from search results
            
        Returns:
            Match score between 0.0 and 1.0
        """
        # Normalize titles for comparison
        search_normalized = self._normalize_title(search_title)
        result_normalized = self._normalize_title(result_title)
        
        return SequenceMatcher(None, search_normalized, result_normalized).ratio()
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison.
        
        Args:
            title: Raw title
            
        Returns:
            Normalized title
        """
        # Convert to lowercase and remove common podcast/episode prefixes
        normalized = title.lower()
        
        # Remove common prefixes
        prefixes_to_remove = [
            r'^episode\s*\d+\s*:?\s*',
            r'^ep\.?\s*\d+\s*:?\s*',
            r'^#\d+\s*:?\s*',
            r'^\d+\s*-\s*',
            r'^\d+\.\s*'
        ]
        
        for prefix in prefixes_to_remove:
            normalized = re.sub(prefix, '', normalized)
        
        # Remove extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _create_cache_key(self, 
                         podcast_name: str, 
                         episode_title: str,
                         episode_number: Optional[int] = None) -> str:
        """Create cache key for episode.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            episode_number: Episode number if available
            
        Returns:
            Cache key string
        """
        base_key = f"{podcast_name}|{episode_title}"
        if episode_number is not None:
            base_key += f"|{episode_number}"
        
        # Use hash to keep keys manageable
        return str(hash(base_key))
    
    def _load_cache(self) -> Dict[str, str]:
        """Load cache from file.
        
        Returns:
            Cache dictionary
        """
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load YouTube cache: {e}")
            return {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            # Ensure data directory exists
            self.cache_file.parent.mkdir(exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save YouTube cache: {e}")
    
    def clear_cache(self):
        """Clear the YouTube URL cache."""
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("YouTube URL cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_entries = len(self.cache)
        found_entries = len([v for v in self.cache.values() if v != "NOT_FOUND"])
        not_found_entries = total_entries - found_entries
        
        return {
            'total_entries': total_entries,
            'found_urls': found_entries,
            'not_found': not_found_entries,
            'cache_file_size': self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
    
    def search_youtube(self, query: str) -> Optional[List[Dict[str, str]]]:
        """Synchronous wrapper for YouTube search.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results or None
        """
        import asyncio
        
        # Parse the query to extract podcast and episode info
        # Expected format: "Podcast Name Episode Title"
        parts = query.split(' ', 1)
        if len(parts) >= 2:
            podcast_name = parts[0]
            episode_title = parts[1]
        else:
            podcast_name = ""
            episode_title = query
        
        # Run async search synchronously
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            youtube_url = loop.run_until_complete(
                self.search_youtube_url(
                    episode_title=episode_title,
                    podcast_name=podcast_name
                )
            )
            loop.close()
            
            if youtube_url:
                # Extract video ID from URL
                import re
                video_id_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', youtube_url)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    return [{
                        'video_id': video_id,
                        'url': youtube_url,
                        'title': episode_title
                    }]
            
            return None
            
        except Exception as e:
            logger.error(f"YouTube search failed: {str(e)}", exc_info=True)
            return None