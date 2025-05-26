"""Podcast feed processing utilities for RSS parsing and audio download."""

import os
import re
import time
import hashlib
import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Try to import feedparser
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    feedparser = None

logger = logging.getLogger(__name__)


class FeedProcessingError(Exception):
    """Base exception for feed processing errors."""
    pass


class FeedParsingError(FeedProcessingError):
    """Error parsing RSS feed."""
    pass


class AudioDownloadError(FeedProcessingError):
    """Error downloading audio file."""
    pass


def fetch_podcast_feed(podcast_config: Dict[str, Any], 
                      max_episodes: int = 1) -> Dict[str, Any]:
    """Fetch podcast feed and episode information.
    
    Args:
        podcast_config: Dictionary with podcast configuration containing:
            - id: Podcast unique identifier
            - name: Podcast name
            - rss_url: RSS feed URL
            - description: Optional podcast description
        max_episodes: Maximum number of episodes to fetch (0 for all)
        
    Returns:
        Dictionary with podcast and episode information
        
    Raises:
        FeedParsingError: If feed cannot be parsed
    """
    if not HAS_FEEDPARSER:
        raise ImportError("feedparser is required. Install with: pip install feedparser")
    
    if not podcast_config.get('rss_url'):
        raise ValueError("RSS URL is required in podcast configuration")
    
    logger.info(f"Fetching RSS feed: {podcast_config['rss_url']}")
    
    try:
        feed = feedparser.parse(podcast_config['rss_url'])
    except Exception as e:
        raise FeedParsingError(f"Failed to parse RSS feed: {e}")
    
    if feed.bozo:
        logger.warning(f"RSS feed may be malformed. Bozo bit set: {feed.bozo_exception}")
    
    # Extract podcast information
    podcast_info = {
        "id": podcast_config["id"],
        "title": feed.feed.get("title", podcast_config.get("name", "Unknown Podcast")),
        "description": feed.feed.get("subtitle", feed.feed.get("description", 
                                                               podcast_config.get("description", ""))),
        "link": feed.feed.get("link", ""),
        "image": _extract_feed_image(feed),
        "language": feed.feed.get("language", ""),
        "author": feed.feed.get("author", feed.feed.get("itunes_author", "")),
        "categories": _extract_categories(feed),
        "episodes": []
    }
    
    # Process episodes
    episodes = _extract_episodes(feed.entries, max_episodes)
    podcast_info["episodes"] = episodes
    
    logger.info(f"Found {len(episodes)} episodes for '{podcast_info['title']}'")
    return podcast_info


def _extract_feed_image(feed: Any) -> str:
    """Extract podcast image URL from feed.
    
    Args:
        feed: Parsed feed object
        
    Returns:
        Image URL or empty string
    """
    # Try different image locations
    if hasattr(feed.feed, 'image') and feed.feed.image:
        if hasattr(feed.feed.image, 'href'):
            return feed.feed.image.href
        elif hasattr(feed.feed.image, 'url'):
            return feed.feed.image.url
    
    # Try iTunes image
    if hasattr(feed.feed, 'itunes_image'):
        return feed.feed.itunes_image
    
    return ""


def _extract_categories(feed: Any) -> List[str]:
    """Extract podcast categories from feed.
    
    Args:
        feed: Parsed feed object
        
    Returns:
        List of category names
    """
    categories = []
    
    # Try iTunes categories
    if hasattr(feed.feed, 'itunes_category'):
        categories.append(feed.feed.itunes_category)
    
    # Try regular categories
    if hasattr(feed.feed, 'categories'):
        for cat in feed.feed.categories:
            if isinstance(cat, tuple) and len(cat) > 0:
                categories.append(cat[0])
            elif isinstance(cat, str):
                categories.append(cat)
    
    return list(set(categories))  # Remove duplicates


def _extract_episodes(entries: List[Any], max_episodes: int) -> List[Dict[str, Any]]:
    """Extract episode information from feed entries.
    
    Args:
        entries: List of feed entries
        max_episodes: Maximum episodes to extract (0 for all)
        
    Returns:
        List of episode dictionaries
    """
    episodes = []
    episode_count = 0
    
    for entry in entries:
        if max_episodes > 0 and episode_count >= max_episodes:
            break
        
        # Find audio URL
        audio_url = _find_audio_url(entry)
        if not audio_url:
            logger.warning(f"Could not find audio URL for episode: {entry.get('title', 'Unknown Title')}")
            continue
        
        # Generate unique episode ID
        episode_id = _generate_episode_id(entry, audio_url)
        
        # Extract episode information
        episode = {
            "id": episode_id,
            "title": entry.get("title", "Untitled Episode"),
            "description": entry.get("summary", entry.get("description", "")),
            "published_date": _parse_date(entry.get("published", entry.get("updated", ""))),
            "audio_url": audio_url,
            "duration": entry.get("itunes_duration", ""),
            "episode_number": entry.get("itunes_episode", ""),
            "season_number": entry.get("itunes_season", ""),
            "keywords": _extract_keywords(entry),
            "explicit": entry.get("itunes_explicit", "no").lower() == "yes"
        }
        
        episodes.append(episode)
        episode_count += 1
    
    return episodes


def _find_audio_url(entry: Any) -> Optional[str]:
    """Find audio URL in feed entry.
    
    Args:
        entry: Feed entry object
        
    Returns:
        Audio URL or None
    """
    audio_url = None
    audio_extensions = ['.mp3', '.m4a', '.wav', '.ogg', '.aac', '.opus']
    
    # Check links for audio type
    if hasattr(entry, 'links'):
        for link in entry.links:
            if hasattr(link, "type") and "audio" in link.type.lower():
                audio_url = link.href
                break
    
    # Check enclosures
    if not audio_url and hasattr(entry, "enclosures") and entry.enclosures:
        for enclosure in entry.enclosures:
            if hasattr(enclosure, "type") and "audio" in enclosure.type.lower():
                audio_url = enclosure.href
                break
            elif hasattr(enclosure, "href"):
                # Check by extension if type not specified
                if any(ext in enclosure.href.lower() for ext in audio_extensions):
                    audio_url = enclosure.href
                    break
    
    # Last resort: check all links for audio extensions
    if not audio_url and hasattr(entry, 'links'):
        for link in entry.links:
            if hasattr(link, 'href') and any(ext in link.href.lower() for ext in audio_extensions):
                audio_url = link.href
                break
    
    return audio_url


def _generate_episode_id(entry: Any, audio_url: str) -> str:
    """Generate unique episode ID.
    
    Args:
        entry: Feed entry object
        audio_url: Episode audio URL
        
    Returns:
        Unique episode ID
    """
    # Try to use existing unique identifiers
    episode_id_base = entry.get("id", entry.get("guid", None))
    
    if not episode_id_base:
        # Generate ID from title and URL
        title_for_id = entry.get("title", f"untitled_episode_{time.time()}")
        link_for_id = entry.get("link", audio_url)
        episode_id_base = f"{title_for_id}_{link_for_id}"
    
    # Create hash for consistent ID
    return hashlib.sha256(episode_id_base.encode()).hexdigest()[:32]


def _parse_date(date_str: str) -> str:
    """Parse and normalize date string.
    
    Args:
        date_str: Date string from feed
        
    Returns:
        ISO format date string
    """
    if not date_str:
        return datetime.now().isoformat()
    
    try:
        # Try parsing with dateutil if available
        from dateutil.parser import parse as date_parse
        parsed = date_parse(date_str)
        return parsed.isoformat()
    except (ImportError, ValueError):
        # Return as-is if can't parse
        return date_str


def _extract_keywords(entry: Any) -> List[str]:
    """Extract keywords/tags from entry.
    
    Args:
        entry: Feed entry object
        
    Returns:
        List of keywords
    """
    keywords = []
    
    # iTunes keywords
    if hasattr(entry, 'itunes_keywords'):
        keywords.extend(entry.itunes_keywords.split(','))
    
    # Regular tags
    if hasattr(entry, 'tags'):
        for tag in entry.tags:
            if hasattr(tag, 'term'):
                keywords.append(tag.term)
    
    # Clean and deduplicate
    keywords = [k.strip() for k in keywords if k.strip()]
    return list(set(keywords))


def download_episode_audio(episode: Dict[str, Any], 
                         podcast_id: str,
                         output_dir: str = "audio_files",
                         max_retries: int = 3,
                         user_agent: str = "Mozilla/5.0") -> Optional[str]:
    """Download episode audio file.
    
    Args:
        episode: Dictionary with episode information
        podcast_id: Podcast ID
        output_dir: Directory to save audio files
        max_retries: Maximum download retry attempts
        user_agent: User agent string for requests
        
    Returns:
        Path to downloaded audio file or None if download fails
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create safe filename
    safe_podcast_id = re.sub(r'[^\w\-_\.]', '_', str(podcast_id))
    safe_episode_id = re.sub(r'[^\w\-_\.]', '_', str(episode['id']))
    
    # Try to extract extension from URL
    audio_url = episode['audio_url']
    url_path = urllib.parse.urlparse(audio_url).path
    extension = os.path.splitext(url_path)[1] or '.mp3'
    
    filename = f"{safe_podcast_id}_{safe_episode_id}{extension}"
    output_path = os.path.join(output_dir, filename)
    
    # Check if file already exists
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        logger.info(f"File already exists and is non-empty: {output_path}")
        return output_path
    
    # Download with retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading: {episode['title']} (ID: {episode['id']}) - Attempt {attempt + 1}")
            
            # Create request with headers
            req = urllib.request.Request(
                audio_url,
                headers={
                    'User-Agent': user_agent,
                    'Accept': 'audio/*',
                    'Accept-Encoding': 'identity'
                }
            )
            
            # Download file
            with urllib.request.urlopen(req, timeout=300) as response:
                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if 'audio' not in content_type and 'octet-stream' not in content_type:
                    logger.warning(f"Unexpected content type: {content_type}")
                
                # Download in chunks to handle large files
                chunk_size = 1024 * 1024  # 1MB chunks
                with open(output_path, 'wb') as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
            
            # Verify download
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise AudioDownloadError(f"Downloaded file is empty: {output_path}")
            
            logger.info(f"Successfully downloaded to {output_path} ({file_size / 1024 / 1024:.1f} MB)")
            return output_path
            
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error {e.code}: {e.reason}")
            if e.code == 404:
                break  # Don't retry on 404
        except Exception as e:
            logger.error(f"Error downloading {episode['title']}: {e}")
            
        # Clean up failed download
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        
        # Wait before retry
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return None


def validate_podcast_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate podcast configuration.
    
    Args:
        config: Podcast configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Required fields
    required_fields = ['id', 'rss_url']
    for field in required_fields:
        if field not in config or not config[field]:
            errors.append(f"Missing required field: {field}")
    
    # Validate RSS URL
    if 'rss_url' in config:
        url = config['rss_url']
        if not url.startswith(('http://', 'https://')):
            errors.append("RSS URL must start with http:// or https://")
    
    # Validate ID format
    if 'id' in config:
        podcast_id = config['id']
        if not re.match(r'^[a-zA-Z0-9_-]+$', podcast_id):
            errors.append("Podcast ID must contain only letters, numbers, hyphens, and underscores")
    
    return len(errors) == 0, errors


def parse_duration(duration_str: str) -> Optional[int]:
    """Parse podcast duration string to seconds.
    
    Args:
        duration_str: Duration string (e.g., "01:23:45", "1:23:45", "23:45")
        
    Returns:
        Duration in seconds or None
    """
    if not duration_str:
        return None
    
    # Remove extra whitespace
    duration_str = duration_str.strip()
    
    # Try different formats
    patterns = [
        (r'^(\d+):(\d+):(\d+)$', lambda m: int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])),  # HH:MM:SS
        (r'^(\d+):(\d+)$', lambda m: int(m[1]) * 60 + int(m[2])),  # MM:SS
        (r'^(\d+)$', lambda m: int(m[1])),  # Seconds only
    ]
    
    for pattern, parser in patterns:
        match = re.match(pattern, duration_str)
        if match:
            try:
                return parser(match)
            except ValueError:
                pass
    
    return None