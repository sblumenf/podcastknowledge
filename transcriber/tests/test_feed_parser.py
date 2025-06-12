"""Unit tests for the RSS feed parser module."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import feedparser

from src.feed_parser import (
    Episode, PodcastMetadata, parse_feed, validate_feed_url,
    _extract_podcast_metadata, _extract_episodes, _parse_episode
)


@pytest.mark.unit
class TestEpisode:
    """Test Episode dataclass."""
    
    def test_valid_episode_creation(self):
        """Test creating a valid episode."""
        episode = Episode(
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            guid="unique-guid-123"
        )
        
        assert episode.title == "Test Episode"
        assert episode.audio_url == "https://example.com/episode.mp3"
        assert episode.guid == "unique-guid-123"
        assert episode.description == ""
        assert episode.published_date is None
        assert episode.duration is None
    
    def test_episode_with_all_fields(self):
        """Test episode with all optional fields."""
        pub_date = datetime(2024, 1, 15, 10, 0, 0)
        episode = Episode(
            title="Full Episode",
            audio_url="https://example.com/episode.mp3",
            guid="guid-456",
            description="Test description",
            published_date=pub_date,
            duration="1:23:45",
            episode_number=10,
            season_number=2,
            link="https://example.com/episodes/10",
            author="John Doe",
            keywords=["tech", "python"],
            file_size=50000000,
            mime_type="audio/mpeg"
        )
        
        assert episode.episode_number == 10
        assert episode.season_number == 2
        assert episode.keywords == ["tech", "python"]
        assert episode.file_size == 50000000
    
    def test_episode_missing_title(self):
        """Test episode creation fails without title."""
        with pytest.raises(ValueError, match="Episode title is required"):
            Episode(title="", audio_url="https://example.com/episode.mp3", guid="guid")
    
    def test_episode_missing_audio_url(self):
        """Test episode creation fails without audio URL."""
        with pytest.raises(ValueError, match="Episode audio URL is required"):
            Episode(title="Test", audio_url="", guid="guid")
    
    def test_episode_missing_guid(self):
        """Test episode creation fails without GUID."""
        with pytest.raises(ValueError, match="Episode GUID is required"):
            Episode(title="Test", audio_url="https://example.com/episode.mp3", guid="")
    
    def test_episode_invalid_audio_url(self):
        """Test episode creation fails with invalid audio URL."""
        with pytest.raises(ValueError, match="Invalid audio URL"):
            Episode(title="Test", audio_url="not-a-url", guid="guid")
    
    def test_episode_to_dict(self):
        """Test converting episode to dictionary."""
        pub_date = datetime(2024, 1, 15, 10, 0, 0)
        episode = Episode(
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            guid="guid-123",
            published_date=pub_date,
            keywords=["test", "podcast"]
        )
        
        data = episode.to_dict()
        
        assert data['title'] == "Test Episode"
        assert data['audio_url'] == "https://example.com/episode.mp3"
        assert data['guid'] == "guid-123"
        assert data['published_date'] == pub_date.isoformat()
        assert data['keywords'] == ["test", "podcast"]
        assert data['duration'] is None


@pytest.mark.unit
class TestPodcastMetadata:
    """Test PodcastMetadata dataclass."""
    
    def test_podcast_metadata_creation(self):
        """Test creating podcast metadata."""
        metadata = PodcastMetadata(
            title="Test Podcast",
            description="A test podcast",
            link="https://example.com/podcast",
            language="en",
            author="Jane Doe",
            category="Technology",
            explicit=True,
            image_url="https://example.com/logo.jpg"
        )
        
        assert metadata.title == "Test Podcast"
        assert metadata.description == "A test podcast"
        assert metadata.explicit is True
        assert metadata.image_url == "https://example.com/logo.jpg"
    
    def test_podcast_metadata_defaults(self):
        """Test podcast metadata with default values."""
        metadata = PodcastMetadata(title="Minimal Podcast")
        
        assert metadata.title == "Minimal Podcast"
        assert metadata.description == ""
        assert metadata.link is None
        assert metadata.explicit is False


@pytest.mark.unit
class TestParseFeed:
    """Test parse_feed function."""
    
    @patch('src.feed_parser.feedparser.parse')
    def test_parse_feed_success(self, mock_parse, mock_logger):
        """Test successfully parsing a feed."""
        # Mock feed data
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {
            'title': 'Test Podcast',
            'description': 'Test Description',
            'link': 'https://example.com'
        }
        mock_feed.entries = [
            {
                'title': 'Episode 1',
                'id': 'ep1',
                'enclosures': [{'href': 'https://example.com/ep1.mp3', 'type': 'audio/mpeg'}]
            }
        ]
        mock_parse.return_value = mock_feed
        
        metadata, episodes = parse_feed('https://example.com/feed.xml')
        
        assert metadata.title == 'Test Podcast'
        assert len(episodes) == 1
        assert episodes[0].title == 'Episode 1'
    
    @patch('src.feed_parser.feedparser.parse')
    def test_parse_feed_with_bozo_error(self, mock_parse, mock_logger):
        """Test parsing feed with bozo error (malformed but parseable)."""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("XML parsing error")
        mock_feed.feed = {'title': 'Test Podcast'}
        mock_feed.entries = []
        mock_parse.return_value = mock_feed
        
        # Should still parse despite bozo error
        metadata, episodes = parse_feed('https://example.com/feed.xml')
        assert metadata.title == 'Test Podcast'
    
    @patch('src.feed_parser.feedparser.parse')
    def test_parse_feed_network_error(self, mock_parse, mock_logger):
        """Test handling network error during feed parsing."""
        mock_parse.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            parse_feed('https://example.com/feed.xml')
    
    @patch('src.feed_parser.feedparser.parse')
    def test_parse_feed_no_episodes(self, mock_parse, mock_logger):
        """Test parsing feed with no episodes."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Empty Podcast'}
        mock_feed.entries = []
        mock_parse.return_value = mock_feed
        
        metadata, episodes = parse_feed('https://example.com/feed.xml')
        
        assert metadata.title == 'Empty Podcast'
        assert len(episodes) == 0


@pytest.mark.unit
class TestExtractPodcastMetadata:
    """Test _extract_podcast_metadata function."""
    
    def test_extract_basic_metadata(self):
        """Test extracting basic podcast metadata."""
        feed = MagicMock()
        feed.feed = {
            'title': 'Basic Podcast',
            'description': 'Basic description',
            'link': 'https://example.com',
            'language': 'en',
            'author': 'Author Name'
        }
        
        metadata = _extract_podcast_metadata(feed)
        
        assert metadata.title == 'Basic Podcast'
        assert metadata.description == 'Basic description'
        assert metadata.link == 'https://example.com'
        assert metadata.language == 'en'
        assert metadata.author == 'Author Name'
    
    def test_extract_itunes_metadata(self):
        """Test extracting iTunes-specific metadata."""
        feed = MagicMock()
        feed.feed = MagicMock(spec=['get', 'itunes_author', 'itunes_owner', 'itunes_category', 'itunes_explicit', 'itunes_image'])
        feed.feed.get = lambda k, d=None: d
        feed.feed.itunes_author = 'iTunes Author'
        feed.feed.itunes_owner = {
            'itunes_name': 'Owner Name',
            'itunes_email': 'owner@example.com'
        }
        feed.feed.itunes_category = 'Technology'
        feed.feed.itunes_explicit = 'yes'
        feed.feed.itunes_image = MagicMock()
        feed.feed.itunes_image.href = 'https://example.com/itunes.jpg'
        
        metadata = _extract_podcast_metadata(feed)
        
        assert metadata.author == 'iTunes Author'
        assert metadata.owner_name == 'Owner Name'
        assert metadata.owner_email == 'owner@example.com'
        assert metadata.category == 'Technology'
        assert metadata.explicit is True
        assert metadata.image_url == 'https://example.com/itunes.jpg'
    
    def test_extract_standard_image(self):
        """Test extracting standard RSS image."""
        feed = MagicMock()
        feed.feed = MagicMock()
        feed.feed.get = lambda k, d=None: d
        feed.feed.image = {'href': 'https://example.com/image.jpg'}
        
        metadata = _extract_podcast_metadata(feed)
        assert metadata.image_url == 'https://example.com/image.jpg'
    
    def test_extract_minimal_metadata(self):
        """Test extracting metadata with minimal fields."""
        feed = MagicMock()
        feed.feed = {}
        
        metadata = _extract_podcast_metadata(feed)
        
        assert metadata.title == 'Unknown Podcast'
        assert metadata.description == ''
        assert metadata.link is None
        assert metadata.explicit is False


@pytest.mark.unit
class TestExtractEpisodes:
    """Test _extract_episodes function."""
    
    def test_extract_multiple_episodes(self):
        """Test extracting multiple episodes."""
        feed = MagicMock()
        feed.entries = [
            {
                'title': 'Episode 1',
                'id': 'ep1',
                'enclosures': [{'href': 'https://example.com/ep1.mp3', 'type': 'audio/mpeg'}],
                'published_parsed': (2024, 1, 15, 10, 0, 0, 0, 0, 0)
            },
            {
                'title': 'Episode 2',
                'id': 'ep2',
                'enclosures': [{'href': 'https://example.com/ep2.mp3', 'type': 'audio/mpeg'}],
                'published_parsed': (2024, 1, 22, 10, 0, 0, 0, 0, 0)
            }
        ]
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episodes = _extract_episodes(feed, podcast_metadata)
        
        assert len(episodes) == 2
        # Should be sorted by date, newest first
        assert episodes[0].title == 'Episode 2'
        assert episodes[1].title == 'Episode 1'
    
    def test_extract_episodes_with_failures(self, mock_logger):
        """Test extracting episodes when some fail to parse."""
        feed = MagicMock()
        feed.entries = [
            {
                'title': 'Good Episode',
                'id': 'good',
                'enclosures': [{'href': 'https://example.com/good.mp3', 'type': 'audio/mpeg'}]
            },
            {
                'title': 'Bad Episode',
                # No enclosures - will fail
            },
            {
                'title': 'Another Good Episode',
                'id': 'good2',
                'enclosures': [{'href': 'https://example.com/good2.mp3', 'type': 'audio/mpeg'}]
            }
        ]
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episodes = _extract_episodes(feed, podcast_metadata)
        
        # Should parse 2 good episodes, skip the bad one
        assert len(episodes) == 2
        assert episodes[0].title == 'Good Episode'
        assert episodes[1].title == 'Another Good Episode'


@pytest.mark.unit
class TestParseEpisode:
    """Test _parse_episode function."""
    
    def test_parse_basic_episode(self):
        """Test parsing basic episode."""
        entry = {
            'title': 'Basic Episode',
            'id': 'basic-id',
            'description': 'Basic description',
            'link': 'https://example.com/episodes/1',
            'enclosures': [{
                'href': 'https://example.com/episode.mp3',
                'type': 'audio/mpeg',
                'length': '25000000'
            }]
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", author="Podcast Author")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode.title == 'Basic Episode'
        assert episode.audio_url == 'https://example.com/episode.mp3'
        assert episode.guid == 'basic-id'
        assert episode.description == 'Basic description'
        assert episode.file_size == 25000000
        assert episode.mime_type == 'audio/mpeg'
        assert episode.author == 'Podcast Author'  # Inherited from podcast
    
    def test_parse_episode_with_itunes_metadata(self):
        """Test parsing episode with iTunes metadata."""
        entry = {
            'title': 'iTunes Episode',
            'id': 'itunes-id',
            'enclosures': [{'href': 'https://example.com/itunes.mp3', 'type': 'audio/mpeg'}],
            'itunes_duration': '01:23:45',
            'itunes_episode': '10',
            'itunes_season': '2',
            'itunes_keywords': 'tech, podcast, python',
            'published_parsed': (2024, 1, 15, 10, 0, 0, 0, 0, 0)
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode.duration == '01:23:45'
        assert episode.episode_number == 10
        assert episode.season_number == 2
        assert episode.keywords == ['tech', 'podcast', 'python']
        assert episode.published_date == datetime(2024, 1, 15, 10, 0, 0)
    
    def test_parse_episode_no_audio(self):
        """Test parsing episode without audio returns None."""
        entry = {
            'title': 'No Audio Episode',
            'id': 'no-audio',
            'enclosures': [{'href': 'https://example.com/image.jpg', 'type': 'image/jpeg'}]
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode is None
    
    def test_parse_episode_multiple_enclosures(self):
        """Test parsing episode with multiple enclosures."""
        entry = {
            'title': 'Multi Enclosure Episode',
            'id': 'multi',
            'enclosures': [
                {'href': 'https://example.com/image.jpg', 'type': 'image/jpeg'},
                {'href': 'https://example.com/episode.mp3', 'type': 'audio/mpeg', 'length': '30000000'},
                {'href': 'https://example.com/episode.m4a', 'type': 'audio/mp4'}
            ]
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episode = _parse_episode(entry, podcast_metadata)
        
        # Should pick the first audio enclosure
        assert episode.audio_url == 'https://example.com/episode.mp3'
        assert episode.mime_type == 'audio/mpeg'
        assert episode.file_size == 30000000
    
    def test_parse_episode_fallback_guid(self):
        """Test GUID fallback when id is not available."""
        entry = {
            'title': 'Fallback GUID Episode',
            'guid': 'guid-fallback',
            'enclosures': [{'href': 'https://example.com/episode.mp3', 'type': 'audio/mpeg'}]
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode.guid == 'guid-fallback'
    
    def test_parse_episode_audio_url_as_guid(self):
        """Test using audio URL as GUID when nothing else available."""
        entry = {
            'title': 'URL GUID Episode',
            'enclosures': [{'href': 'https://example.com/unique-episode.mp3', 'type': 'audio/mpeg'}]
        }
        
        podcast_metadata = PodcastMetadata(title="Test Podcast")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode.guid == 'https://example.com/unique-episode.mp3'


@pytest.mark.unit
class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_validate_feed_url_valid(self):
        """Test validating valid feed URLs."""
        assert validate_feed_url('https://example.com/feed.xml') is True
        assert validate_feed_url('http://example.com/feed.xml') is True
        assert validate_feed_url('https://subdomain.example.com/path/to/feed.xml') is True
    
    def test_validate_feed_url_invalid(self):
        """Test validating invalid feed URLs."""
        assert validate_feed_url('not-a-url') is False
        assert validate_feed_url('example.com/feed.xml') is False  # No scheme
        assert validate_feed_url('https://') is False  # No netloc
        assert validate_feed_url('') is False
        assert validate_feed_url('file:///local/path') is True  # File URLs are valid