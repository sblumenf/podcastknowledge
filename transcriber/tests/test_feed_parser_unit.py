"""Unit tests for feed parser module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import feedparser

from src.feed_parser import (
    Episode, PodcastMetadata, parse_feed, validate_feed_url,
    _extract_podcast_metadata, _extract_episodes, _parse_episode
)


class TestEpisodeDataclass:
    """Test Episode dataclass functionality."""
    
    def test_episode_init_minimal(self):
        """Test Episode initialization with minimal required fields."""
        episode = Episode(
            title="Test Episode",
            audio_url="https://example.com/audio.mp3",
            guid="test-guid-001"
        )
        
        assert episode.title == "Test Episode"
        assert episode.audio_url == "https://example.com/audio.mp3"
        assert episode.guid == "test-guid-001"
        assert episode.description == ""
        assert episode.published_date is None
        assert episode.duration is None
    
    def test_episode_init_all_fields(self):
        """Test Episode initialization with all fields."""
        pub_date = datetime(2025, 6, 1, 10, 0, 0)
        episode = Episode(
            title="Test Episode",
            audio_url="https://example.com/audio.mp3",
            guid="test-guid-001",
            description="Test description",
            published_date=pub_date,
            duration="45:00",
            episode_number=1,
            season_number=2,
            link="https://example.com/episode",
            author="John Doe",
            keywords=["tech", "ai"],
            youtube_url="https://youtube.com/watch?v=123",
            file_size=12345678,
            mime_type="audio/mpeg"
        )
        
        assert episode.description == "Test description"
        assert episode.published_date == pub_date
        assert episode.duration == "45:00"
        assert episode.episode_number == 1
        assert episode.season_number == 2
        assert episode.keywords == ["tech", "ai"]
    
    def test_episode_validation_missing_title(self):
        """Test Episode validation with missing title."""
        with pytest.raises(ValueError, match="Episode title is required"):
            Episode(
                title="",
                audio_url="https://example.com/audio.mp3",
                guid="test-guid"
            )
    
    def test_episode_validation_missing_audio_url(self):
        """Test Episode validation with missing audio URL."""
        with pytest.raises(ValueError, match="Episode audio URL is required"):
            Episode(
                title="Test",
                audio_url="",
                guid="test-guid"
            )
    
    def test_episode_validation_missing_guid(self):
        """Test Episode validation with missing GUID."""
        with pytest.raises(ValueError, match="Episode GUID is required"):
            Episode(
                title="Test",
                audio_url="https://example.com/audio.mp3",
                guid=""
            )
    
    def test_episode_validation_invalid_url(self):
        """Test Episode validation with invalid URL."""
        with pytest.raises(ValueError, match="Invalid audio URL"):
            Episode(
                title="Test",
                audio_url="not-a-url",
                guid="test-guid"
            )
    
    def test_episode_to_dict(self):
        """Test converting Episode to dictionary."""
        pub_date = datetime(2025, 6, 1, 10, 0, 0)
        episode = Episode(
            title="Test Episode",
            audio_url="https://example.com/audio.mp3",
            guid="test-guid-001",
            published_date=pub_date,
            duration="45:00"
        )
        
        result = episode.to_dict()
        
        assert result['title'] == "Test Episode"
        assert result['audio_url'] == "https://example.com/audio.mp3"
        assert result['guid'] == "test-guid-001"
        assert result['published_date'] == pub_date.isoformat()
        assert result['duration'] == "45:00"
        assert result['description'] == ""
        assert result['episode_number'] is None


class TestPodcastMetadata:
    """Test PodcastMetadata dataclass."""
    
    def test_init_minimal(self):
        """Test PodcastMetadata with minimal fields."""
        metadata = PodcastMetadata(title="Test Podcast")
        
        assert metadata.title == "Test Podcast"
        assert metadata.description == ""
        assert metadata.link is None
        assert metadata.language is None
        assert metadata.explicit is False
    
    def test_init_all_fields(self):
        """Test PodcastMetadata with all fields."""
        metadata = PodcastMetadata(
            title="Test Podcast",
            description="A great podcast",
            link="https://example.com",
            language="en-us",
            author="John Doe",
            owner_name="John Doe",
            owner_email="john@example.com",
            category="Technology",
            explicit=True,
            image_url="https://example.com/logo.jpg"
        )
        
        assert metadata.author == "John Doe"
        assert metadata.owner_email == "john@example.com"
        assert metadata.category == "Technology"
        assert metadata.explicit is True
        assert metadata.image_url == "https://example.com/logo.jpg"


class TestParseFeed:
    """Test parse_feed function."""
    
    @patch('feedparser.parse')
    def test_parse_feed_success(self, mock_parse):
        """Test successful feed parsing."""
        # Setup mock feed
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = Mock()
        mock_feed.feed.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Test Podcast',
            'description': 'Test description',
            'link': 'https://example.com',
            'language': 'en-us'
        }.get(key, default))
        
        # Add required attributes for metadata extraction
        mock_feed.feed.title = 'Test Podcast'
        mock_feed.feed.description = 'Test description'
        mock_feed.feed.link = 'https://example.com'
        mock_feed.feed.language = 'en-us'
        mock_feed.feed.image = None
        
        # Setup mock entry
        mock_entry = Mock()
        mock_entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Episode 1',
            'id': 'episode-1',
            'enclosures': [{
                'href': 'https://example.com/ep1.mp3',
                'type': 'audio/mpeg',
                'length': '12345678'
            }],
            'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0)
        }.get(key, default))
        
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed
        
        # Call function
        podcast_metadata, episodes = parse_feed("https://example.com/feed.xml")
        
        # Verify results
        assert podcast_metadata.title == "Test Podcast"
        assert podcast_metadata.description == "Test description"
        assert len(episodes) == 1
        assert episodes[0].title == "Episode 1"
        assert episodes[0].audio_url == "https://example.com/ep1.mp3"
    
    @patch('feedparser.parse')
    def test_parse_feed_with_bozo_error(self, mock_parse):
        """Test feed parsing with bozo error (continues anyway)."""
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("Parsing error")
        mock_feed.feed = Mock()
        mock_feed.feed.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Test'
        }.get(key, default))
        mock_feed.feed.image = None
        
        # Set required attributes for _extract_podcast_metadata
        for attr in ['itunes_author', 'itunes_owner', 'itunes_category', 'itunes_explicit', 'itunes_image']:
            setattr(mock_feed.feed, attr, None)
        
        mock_feed.entries = []
        
        mock_parse.return_value = mock_feed
        
        # Should not raise, just log warning
        podcast_metadata, episodes = parse_feed("https://example.com/feed.xml")
        
        assert podcast_metadata.title == "Test"
        assert episodes == []
    
    @patch('feedparser.parse')
    def test_parse_feed_no_episodes(self, mock_parse):
        """Test parsing feed with no episodes."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = Mock()
        mock_feed.feed.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Empty Podcast'
        }.get(key, default))
        mock_feed.feed.title = 'Empty Podcast'
        mock_feed.feed.image = None
        mock_feed.entries = []
        
        mock_parse.return_value = mock_feed
        
        podcast_metadata, episodes = parse_feed("https://example.com/feed.xml")
        
        assert podcast_metadata.title == "Empty Podcast"
        assert episodes == []
    
    @patch('feedparser.parse')
    def test_parse_feed_network_error(self, mock_parse):
        """Test handling network errors."""
        mock_parse.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            parse_feed("https://example.com/feed.xml")


class TestExtractPodcastMetadata:
    """Test _extract_podcast_metadata function."""
    
    def test_extract_basic_metadata(self):
        """Test extracting basic podcast metadata."""
        feed = Mock()
        feed.feed = Mock()
        feed.feed.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Test Podcast',
            'description': 'A test podcast',
            'link': 'https://example.com',
            'language': 'en-us'
        }.get(key, default))
        feed.feed.image = None
        
        result = _extract_podcast_metadata(feed)
        
        assert result.title == "Test Podcast"
        assert result.description == "A test podcast"
        assert result.link == "https://example.com"
        assert result.language == "en-us"
    
    def test_extract_itunes_metadata(self):
        """Test extracting iTunes-specific metadata."""
        feed = Mock()
        feed.feed = Mock()
        feed.feed.get = Mock(side_effect=lambda key, default=None: default)
        feed.feed.title = 'iTunes Podcast'
        feed.feed.itunes_author = 'John Doe'
        feed.feed.itunes_owner = {
            'itunes_name': 'John Doe',
            'itunes_email': 'john@example.com'
        }
        feed.feed.itunes_category = 'Technology'
        feed.feed.itunes_explicit = 'yes'
        feed.feed.itunes_image = Mock(href='https://example.com/logo.jpg')
        feed.feed.image = None
        
        result = _extract_podcast_metadata(feed)
        
        assert result.author == "John Doe"
        assert result.owner_name == "John Doe"
        assert result.owner_email == "john@example.com"
        assert result.category == "Technology"
        assert result.explicit is True
        assert result.image_url == "https://example.com/logo.jpg"
    
    def test_extract_standard_image(self):
        """Test extracting standard RSS image."""
        feed = Mock()
        feed.feed = Mock()
        feed.feed.get = Mock(side_effect=lambda key, default=None: default)
        feed.feed.title = 'Test'
        feed.feed.image = {'href': 'https://example.com/standard.jpg'}
        
        result = _extract_podcast_metadata(feed)
        
        assert result.image_url == "https://example.com/standard.jpg"
    
    def test_extract_minimal_metadata(self):
        """Test with minimal/missing metadata."""
        feed = Mock()
        feed.feed = Mock()
        feed.feed.get = Mock(side_effect=lambda key, default=None: default)
        
        result = _extract_podcast_metadata(feed)
        
        assert result.title == "Unknown Podcast"
        assert result.description == ""
        assert result.link is None
        assert result.explicit is False


class TestExtractEpisodes:
    """Test _extract_episodes function."""
    
    def test_extract_multiple_episodes(self):
        """Test extracting multiple episodes."""
        feed = Mock()
        
        # Create mock entries
        entry1 = Mock()
        entry1.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Episode 1',
            'id': 'ep1',
            'enclosures': [{'href': 'https://example.com/ep1.mp3', 'type': 'audio/mpeg'}],
            'published_parsed': (2025, 6, 2, 10, 0, 0, 0, 153, 0)
        }.get(key, default))
        
        entry2 = Mock()
        entry2.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Episode 2',
            'id': 'ep2',
            'enclosures': [{'href': 'https://example.com/ep2.mp3', 'type': 'audio/mpeg'}],
            'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0)
        }.get(key, default))
        
        feed.entries = [entry1, entry2]
        
        podcast_metadata = PodcastMetadata(title="Test")
        episodes = _extract_episodes(feed, podcast_metadata)
        
        assert len(episodes) == 2
        # Should be sorted by date, newest first
        assert episodes[0].title == "Episode 1"
        assert episodes[1].title == "Episode 2"
    
    def test_extract_episodes_with_errors(self):
        """Test extracting episodes with some parsing errors."""
        feed = Mock()
        
        # Good entry
        good_entry = Mock()
        good_entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Good Episode',
            'id': 'good',
            'enclosures': [{'href': 'https://example.com/good.mp3', 'type': 'audio/mpeg'}]
        }.get(key, default))
        
        # Bad entry (no audio)
        bad_entry = Mock()
        bad_entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Bad Episode',
            'id': 'bad',
            'enclosures': []
        }.get(key, default))
        
        feed.entries = [good_entry, bad_entry]
        
        podcast_metadata = PodcastMetadata(title="Test")
        episodes = _extract_episodes(feed, podcast_metadata)
        
        # Only good episode should be extracted
        assert len(episodes) == 1
        assert episodes[0].title == "Good Episode"


class TestParseEpisode:
    """Test _parse_episode function."""
    
    def test_parse_complete_episode(self):
        """Test parsing episode with all fields."""
        entry = Mock()
        entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Complete Episode',
            'id': 'complete-001',
            'guid': 'unique-guid-001',
            'link': 'https://example.com/episode',
            'description': 'Full description',
            'author': 'Guest Author',
            'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
            'enclosures': [{
                'href': 'https://example.com/audio.mp3',
                'type': 'audio/mpeg',
                'length': '12345678'
            }],
            'itunes_duration': '45:32',
            'itunes_episode': '5',
            'itunes_season': '2',
            'itunes_keywords': 'tech, ai, future'
        }.get(key, default))
        
        podcast_metadata = PodcastMetadata(title="Test", author="Host")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode is not None
        assert episode.title == "Complete Episode"
        assert episode.guid == "unique-guid-001"
        assert episode.duration == "45:32"
        assert episode.episode_number == 5
        assert episode.season_number == 2
        assert episode.author == "Guest Author"
        assert episode.keywords == ['tech', 'ai', 'future']
        assert episode.file_size == 12345678
    
    def test_parse_episode_no_audio(self):
        """Test parsing episode without audio enclosure."""
        entry = Mock()
        entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'No Audio Episode',
            'id': 'no-audio',
            'enclosures': []
        }.get(key, default))
        
        podcast_metadata = PodcastMetadata(title="Test")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode is None
    
    def test_parse_episode_fallback_dates(self):
        """Test episode date parsing with fallbacks."""
        entry = Mock()
        entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Test Episode',
            'id': 'test',
            'enclosures': [{'href': 'https://example.com/test.mp3', 'type': 'audio/mpeg'}],
            'updated_parsed': (2025, 6, 2, 10, 0, 0, 0, 153, 0)  # No published_parsed
        }.get(key, default))
        
        podcast_metadata = PodcastMetadata(title="Test")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode is not None
        assert episode.published_date == datetime(2025, 6, 2, 10, 0, 0)
    
    def test_parse_episode_tags_as_keywords(self):
        """Test extracting keywords from tags."""
        entry = Mock()
        entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Tagged Episode',
            'id': 'tagged',
            'enclosures': [{'href': 'https://example.com/tagged.mp3', 'type': 'audio/mpeg'}],
            'tags': [{'term': 'technology'}, {'term': 'podcast'}, {'term': None}]
        }.get(key, default))
        
        podcast_metadata = PodcastMetadata(title="Test")
        episode = _parse_episode(entry, podcast_metadata)
        
        assert episode is not None
        assert episode.keywords == ['technology', 'podcast']
    
    def test_parse_episode_guid_fallbacks(self):
        """Test GUID fallback logic."""
        entry = Mock()
        entry.get = Mock(side_effect=lambda key, default=None: {
            'title': 'Test Episode',
            'link': 'https://example.com/episode',
            'enclosures': [{'href': 'https://example.com/test.mp3', 'type': 'audio/mpeg'}]
        }.get(key, default))
        
        podcast_metadata = PodcastMetadata(title="Test")
        episode = _parse_episode(entry, podcast_metadata)
        
        # Should use link as GUID
        assert episode.guid == 'https://example.com/episode'


class TestValidateFeedUrl:
    """Test validate_feed_url function."""
    
    def test_valid_urls(self):
        """Test valid feed URLs."""
        assert validate_feed_url("https://example.com/feed.xml") is True
        assert validate_feed_url("http://example.com/feed.xml") is True
        assert validate_feed_url("file:///home/user/feed.xml") is True
    
    def test_invalid_urls(self):
        """Test invalid feed URLs."""
        assert validate_feed_url("not-a-url") is False
        assert validate_feed_url("") is False
        assert validate_feed_url("https://") is False
        assert validate_feed_url("file://") is False
    
    def test_exception_handling(self):
        """Test exception handling in URL validation."""
        assert validate_feed_url(None) is False