"""Fixed integration tests for RSS feed parser with various feed formats."""

import pytest
from datetime import datetime
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
import feedparser

from src.feed_parser import parse_feed


@pytest.mark.integration
@pytest.mark.network
class TestFeedParserFormatsFixed:
    """Test feed parser with various RSS feed formats - fixed version."""
    
    def test_parse_itunes_podcast_feed_fixed(self):
        """Test parsing iTunes-enhanced podcast feed - fixed."""
        with patch('feedparser.parse') as mock_parse:
            # Create mock objects with proper structure
            parsed = Mock()
            parsed.bozo = False
            
            # Setup feed attributes
            parsed.feed = Mock()
            parsed.feed.get = Mock(side_effect=lambda key, default=None: {
                'title': 'iTunes Enhanced Podcast',
                'link': 'https://example.com',
                'description': 'A podcast with iTunes extensions',
                'language': 'en-us'
            }.get(key, default))
            
            # iTunes attributes
            parsed.feed.title = 'iTunes Enhanced Podcast'
            parsed.feed.link = 'https://example.com'
            parsed.feed.description = 'A podcast with iTunes extensions'
            parsed.feed.language = 'en-us'
            parsed.feed.itunes_author = 'John Podcaster'
            parsed.feed.itunes_summary = 'This is a more detailed summary of the podcast'
            parsed.feed.itunes_owner = Mock()
            parsed.feed.itunes_owner.get = Mock(side_effect=lambda key, default=None: {
                'itunes_name': 'John Podcaster',
                'itunes_email': 'john@example.com'
            }.get(key, default))
            
            # iTunes image as object with href attribute
            parsed.feed.itunes_image = Mock()
            parsed.feed.itunes_image.href = 'https://example.com/podcast-logo.jpg'
            parsed.feed.itunes_explicit = 'no'
            parsed.feed.itunes_category = None
            parsed.feed.image = None
            
            # Create episode with proper structure
            ep1 = Mock()
            ep1.get = Mock(side_effect=lambda key, default=None: {
                'title': 'iTunes Episode 1',
                'description': 'Episode with iTunes metadata',
                'id': 'unique-guid-001',
                'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                'enclosures': [{
                    'href': 'https://example.com/itunes-ep1.mp3',
                    'length': '34567890',
                    'type': 'audio/mpeg'
                }],
                'itunes_duration': '45:32',
                'itunes_episode': '1',
                'itunes_season': '1',
                'itunes_episodetype': 'full',
                'itunes_author': 'Guest Speaker',
                'itunes_summary': 'Detailed episode summary with more information'
            }.get(key, default))
            
            parsed.entries = [ep1]
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/itunes-feed.xml")
            
            # Verify iTunes metadata is captured
            assert podcast_metadata.author == "John Podcaster"
            assert podcast_metadata.image_url == "https://example.com/podcast-logo.jpg"
            
            # Verify episode iTunes metadata
            assert len(episodes) == 1
            episode = episodes[0]
            assert episode.duration == "45:32"
            assert episode.episode_number == 1
            assert episode.season_number == 1
            assert episode.author == "Guest Speaker"
    
    def test_parse_feed_without_duration_fixed(self):
        """Test parsing feed with episodes lacking duration - fixed."""
        with patch('feedparser.parse') as mock_parse:
            parsed = Mock()
            parsed.bozo = False
            
            parsed.feed = Mock()
            parsed.feed.get = Mock(side_effect=lambda key, default=None: {
                'title': 'No Duration Podcast',
                'link': 'https://example.com',
                'description': 'Episodes without duration info'
            }.get(key, default))
            parsed.feed.title = 'No Duration Podcast'
            parsed.feed.link = 'https://example.com'
            parsed.feed.description = 'Episodes without duration info'
            parsed.feed.itunes_author = None
            parsed.feed.itunes_category = None
            parsed.feed.itunes_explicit = None
            parsed.feed.itunes_image = None
            parsed.feed.itunes_owner = None
            parsed.feed.image = None
            
            # Create episode
            ep1 = Mock()
            ep1.get = Mock(side_effect=lambda key, default=None: {
                'title': 'No Duration Episode',
                'id': 'no-duration-001',
                'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                'enclosures': [{
                    'href': 'https://example.com/no-duration.mp3',
                    'type': 'audio/mpeg'
                }]
            }.get(key, default))
            
            parsed.entries = [ep1]
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/no-duration-feed.xml")
            
            assert len(episodes) == 1
            assert episodes[0].duration is None
            assert episodes[0].file_size is None  # No length attribute
    
    def test_parse_feed_with_youtube_links_fixed(self):
        """Test parsing feed with YouTube links in descriptions - fixed."""
        with patch('feedparser.parse') as mock_parse:
            parsed = Mock()
            parsed.bozo = False
            
            parsed.feed = Mock()
            parsed.feed.get = Mock(side_effect=lambda key, default=None: {
                'title': 'YouTube Linked Podcast',
                'link': 'https://example.com',
                'description': 'Podcast with YouTube video links'
            }.get(key, default))
            parsed.feed.title = 'YouTube Linked Podcast'
            parsed.feed.link = 'https://example.com'
            parsed.feed.description = 'Podcast with YouTube video links'
            parsed.feed.itunes_author = None
            parsed.feed.itunes_category = None
            parsed.feed.itunes_explicit = None
            parsed.feed.itunes_image = None
            parsed.feed.itunes_owner = None
            parsed.feed.image = None
            
            # Create episodes
            ep1 = Mock()
            ep1.get = Mock(side_effect=lambda key, default=None: {
                'title': 'Episode with YouTube',
                'id': 'youtube-001',
                'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                'enclosures': [{
                    'href': 'https://example.com/yt-ep1.mp3',
                    'type': 'audio/mpeg'
                }],
                'description': 'Check out the video version on YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\nThis episode discusses various topics...',
                'itunes_duration': '30:00'
            }.get(key, default))
            
            ep2 = Mock()
            ep2.get = Mock(side_effect=lambda key, default=None: {
                'title': 'Episode with short YouTube link',
                'id': 'youtube-002',
                'published': 'Wed, 03 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 3, 10, 0, 0, 2, 154, 0),
                'enclosures': [{
                    'href': 'https://example.com/yt-ep2.mp3',
                    'type': 'audio/mpeg'
                }],
                'description': 'Video: https://youtu.be/dQw4w9WgXcQ | Topics discussed...'
            }.get(key, default))
            
            parsed.entries = [ep1, ep2]
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/youtube-feed.xml")
            
            assert len(episodes) == 2
            # YouTube URL extraction would be done by YouTubeSearcher, not feed parser
            # Just verify descriptions are preserved
            assert "youtube.com/watch?v=dQw4w9WgXcQ" in episodes[1].description
            assert "youtu.be/dQw4w9WgXcQ" in episodes[0].description