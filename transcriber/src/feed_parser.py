"""RSS Feed Parser Module for Podcast Transcription Pipeline.

This module handles parsing RSS feeds to extract episode metadata and audio URLs.
Supports both standard RSS and iTunes podcast formats.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import feedparser

from src.utils.logging import get_logger

logger = get_logger('feed_parser')


@dataclass
class Episode:
    """Data class representing a podcast episode with all relevant metadata."""
    
    # Required fields
    title: str
    audio_url: str
    guid: str
    
    # Optional fields with defaults
    description: str = ""
    published_date: Optional[datetime] = None
    duration: Optional[str] = None
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    link: Optional[str] = None
    author: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    youtube_url: Optional[str] = None
    
    # Metadata for processing
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.title:
            raise ValueError("Episode title is required")
        if not self.audio_url:
            raise ValueError("Episode audio URL is required")
        if not self.guid:
            raise ValueError("Episode GUID is required")
        
        # Validate audio URL
        parsed = urlparse(self.audio_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid audio URL: {self.audio_url}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert episode to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'audio_url': self.audio_url,
            'guid': self.guid,
            'description': self.description,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'duration': self.duration,
            'episode_number': self.episode_number,
            'season_number': self.season_number,
            'link': self.link,
            'author': self.author,
            'keywords': self.keywords,
            'youtube_url': self.youtube_url,
            'file_size': self.file_size,
            'mime_type': self.mime_type
        }


@dataclass
class PodcastMetadata:
    """Data class representing podcast-level metadata."""
    
    title: str
    description: str = ""
    link: Optional[str] = None
    language: Optional[str] = None
    author: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    category: Optional[str] = None
    explicit: bool = False
    image_url: Optional[str] = None


def parse_feed(rss_url: str) -> tuple[PodcastMetadata, List[Episode]]:
    """Parse RSS feed and extract podcast metadata and episodes.
    
    Args:
        rss_url: URL of the RSS feed to parse
        
    Returns:
        Tuple of (PodcastMetadata, List[Episode])
        
    Raises:
        ValueError: If feed parsing fails or feed is invalid
        Exception: For network or other errors
    """
    logger.info(f"Parsing RSS feed: {rss_url}")
    
    try:
        # Parse the feed
        feed = feedparser.parse(rss_url)
        
        # Check for parsing errors
        if feed.bozo:
            error_msg = f"Feed parsing error: {getattr(feed.bozo_exception, 'getMessage', lambda: str(feed.bozo_exception))()}"
            logger.error(error_msg)
            # Continue anyway as feedparser is forgiving
        
        # Extract podcast metadata
        podcast_metadata = _extract_podcast_metadata(feed)
        logger.info(f"Parsed podcast: {podcast_metadata.title}")
        
        # Extract episodes
        episodes = _extract_episodes(feed, podcast_metadata)
        logger.info(f"Found {len(episodes)} episodes in feed")
        
        if not episodes:
            logger.warning("No episodes found in feed")
        
        return podcast_metadata, episodes
        
    except Exception as e:
        logger.error(f"Failed to parse feed {rss_url}: {str(e)}")
        raise


def _extract_podcast_metadata(feed: feedparser.FeedParserDict) -> PodcastMetadata:
    """Extract podcast-level metadata from parsed feed."""
    feed_info = feed.feed
    
    # iTunes namespace helpers
    itunes_author = getattr(feed_info, 'itunes_author', None)
    itunes_owner = getattr(feed_info, 'itunes_owner', {})
    itunes_category = getattr(feed_info, 'itunes_category', None)
    itunes_explicit = getattr(feed_info, 'itunes_explicit', 'no')
    
    # Extract image URL
    image_url = None
    if hasattr(feed_info, 'image') and feed_info.image:
        if hasattr(feed_info.image, 'get'):
            image_url = feed_info.image.get('href') or feed_info.image.get('url')
        elif hasattr(feed_info.image, 'href'):
            image_url = feed_info.image.href
    elif hasattr(feed_info, 'itunes_image'):
        if isinstance(feed_info.itunes_image, dict):
            image_url = feed_info.itunes_image.get('href')
        elif hasattr(feed_info.itunes_image, 'href'):
            image_url = feed_info.itunes_image.href
        else:
            image_url = getattr(feed_info.itunes_image, 'href', None)
    
    return PodcastMetadata(
        title=feed_info.get('title', 'Unknown Podcast'),
        description=feed_info.get('description', ''),
        link=feed_info.get('link'),
        language=feed_info.get('language'),
        author=itunes_author or feed_info.get('author'),
        owner_name=itunes_owner.get('itunes_name') if isinstance(itunes_owner, dict) else None,
        owner_email=itunes_owner.get('itunes_email') if isinstance(itunes_owner, dict) else None,
        category=itunes_category,
        explicit=itunes_explicit.lower() in ('yes', 'true', '1') if itunes_explicit else False,
        image_url=image_url
    )


def _extract_episodes(feed: feedparser.FeedParserDict, podcast_metadata: PodcastMetadata) -> List[Episode]:
    """Extract episodes from parsed feed."""
    episodes = []
    
    for entry in feed.entries:
        try:
            episode = _parse_episode(entry, podcast_metadata)
            if episode:
                episodes.append(episode)
        except Exception as e:
            logger.warning(f"Failed to parse episode '{entry.get('title', 'Unknown')}': {str(e)}")
            continue
    
    # Sort episodes by publication date (newest first)
    episodes.sort(key=lambda e: e.published_date or datetime.min, reverse=True)
    
    return episodes


def _parse_episode(entry: feedparser.FeedParserDict, podcast_metadata: PodcastMetadata) -> Optional[Episode]:
    """Parse a single episode entry."""
    # Extract audio URL from enclosures
    audio_url = None
    file_size = None
    mime_type = None
    
    for enclosure in entry.get('enclosures', []):
        # Handle both dict and object access patterns
        if isinstance(enclosure, dict):
            enc_type = enclosure.get('type', '')
            enc_href = enclosure.get('href') or enclosure.get('url')
            enc_length = enclosure.get('length', 0)
        else:
            # Handle feedparser objects
            enc_type = getattr(enclosure, 'type', '')
            enc_href = getattr(enclosure, 'href', None) or getattr(enclosure, 'url', None)
            enc_length = getattr(enclosure, 'length', 0)
            
        if enc_type.startswith('audio/'):
            audio_url = enc_href
            file_size = int(enc_length) if enc_length else None
            mime_type = enc_type
            break
    
    # Skip if no audio URL found
    if not audio_url:
        logger.debug(f"No audio URL found for episode: {entry.get('title', 'Unknown')}")
        return None
    
    # Extract publication date
    published_date = None
    published_parsed = entry.get('published_parsed')
    updated_parsed = entry.get('updated_parsed')
    
    if published_parsed:
        published_date = datetime(*published_parsed[:6])
    elif updated_parsed:
        published_date = datetime(*updated_parsed[:6])
    
    # Extract iTunes metadata
    duration = entry.get('itunes_duration')
    episode_number = None
    season_number = None
    
    itunes_episode = entry.get('itunes_episode')
    if itunes_episode:
        try:
            episode_number = int(itunes_episode)
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse episode number '{itunes_episode}': {e}")
            pass
    
    itunes_season = entry.get('itunes_season')
    if itunes_season:
        try:
            season_number = int(itunes_season)
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse season number '{itunes_season}': {e}")
            pass
    
    # Extract keywords
    keywords = []
    itunes_keywords = entry.get('itunes_keywords')
    if itunes_keywords:
        keywords = [k.strip() for k in itunes_keywords.split(',') if k.strip()]
    elif entry.get('tags'):
        keywords = [tag.get('term', '') for tag in entry.get('tags', []) if tag.get('term')]
    
    # Use GUID or link as unique identifier
    guid = entry.get('guid') or entry.get('id') or entry.get('link') or audio_url
    
    return Episode(
        title=entry.get('title', 'Untitled Episode'),
        audio_url=audio_url,
        guid=guid,
        description=entry.get('description', '') or entry.get('summary', ''),
        published_date=published_date,
        duration=duration,
        episode_number=episode_number,
        season_number=season_number,
        link=entry.get('link'),
        author=entry.get('itunes_author') or entry.get('author') or podcast_metadata.author,
        keywords=keywords,
        file_size=file_size,
        mime_type=mime_type
    )


# Utility functions for common RSS feed URLs
def parse_apple_podcasts_url(apple_url: str) -> str:
    """Convert Apple Podcasts URL to RSS feed URL.
    
    Note: This is a placeholder - actual implementation would need to
    fetch the Apple page and extract the RSS URL.
    """
    raise NotImplementedError("Apple Podcasts URL conversion not yet implemented")


def validate_feed_url(url: str) -> bool:
    """Validate if a URL points to a valid RSS feed."""
    try:
        parsed = urlparse(url)
        # For file URLs, check scheme and path
        if parsed.scheme == 'file':
            return bool(parsed.path)
        # For http/https URLs, check scheme and netloc
        return bool(parsed.scheme and parsed.netloc)
    except Exception as e:
        logger.debug(f"URL validation failed for '{url}': {e}")
        return False