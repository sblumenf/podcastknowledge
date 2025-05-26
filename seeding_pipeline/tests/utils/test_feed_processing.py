"""Tests for podcast feed processing utilities."""

import pytest
import os
import tempfile
import urllib.error
from unittest.mock import Mock, patch, MagicMock
from src.utils.feed_processing import (
    fetch_podcast_feed,
    download_episode_audio,
    validate_podcast_config,
    parse_duration,
    FeedParsingError,
    AudioDownloadError,
    _extract_feed_image,
    _extract_categories,
    _find_audio_url,
    _generate_episode_id,
    _parse_date,
    _extract_keywords
)


@pytest.fixture
def mock_feed():
    """Create a mock feed object."""
    feed = Mock()
    feed.bozo = False
    feed.feed = Mock()
    feed.feed.title = "Test Podcast"
    feed.feed.subtitle = "A test podcast description"
    feed.feed.link = "https://example.com/podcast"
    feed.feed.language = "en"
    feed.feed.author = "Test Author"
    
    # Mock entries
    entry1 = Mock()
    entry1.title = "Episode 1"
    entry1.summary = "First episode"
    entry1.published = "2023-01-01T00:00:00Z"
    entry1.id = "ep1"
    entry1.links = [Mock(href="https://example.com/ep1.mp3", type="audio/mpeg")]
    
    entry2 = Mock()
    entry2.title = "Episode 2"
    entry2.description = "Second episode"
    entry2.updated = "2023-01-02T00:00:00Z"
    entry2.guid = "ep2"
    entry2.enclosures = [Mock(href="https://example.com/ep2.mp3", type="audio/mpeg")]
    
    feed.entries = [entry1, entry2]
    return feed


@pytest.fixture
def podcast_config():
    """Create a test podcast configuration."""
    return {
        'id': 'test-podcast',
        'name': 'Test Podcast',
        'rss_url': 'https://example.com/feed.rss',
        'description': 'Test description'
    }


class TestFetchPodcastFeed:
    """Tests for fetch_podcast_feed function."""
    
    @patch('src.utils.feed_processing.HAS_FEEDPARSER', False)
    def test_no_feedparser(self, podcast_config):
        """Test error when feedparser not available."""
        with pytest.raises(ImportError, match="feedparser is required"):
            fetch_podcast_feed(podcast_config)
    
    def test_missing_rss_url(self):
        """Test error when RSS URL missing."""
        config = {'id': 'test'}
        with pytest.raises(ValueError, match="RSS URL is required"):
            fetch_podcast_feed(config)
    
    @patch('src.utils.feed_processing.feedparser')
    def test_successful_feed_fetch(self, mock_feedparser, mock_feed, podcast_config):
        """Test successful feed fetching."""
        mock_feedparser.parse.return_value = mock_feed
        
        result = fetch_podcast_feed(podcast_config, max_episodes=2)
        
        assert result['id'] == 'test-podcast'
        assert result['title'] == 'Test Podcast'
        assert result['description'] == 'A test podcast description'
        assert len(result['episodes']) == 2
        assert result['episodes'][0]['title'] == 'Episode 1'
        assert result['episodes'][1]['title'] == 'Episode 2'
    
    @patch('src.utils.feed_processing.feedparser')
    def test_malformed_feed(self, mock_feedparser, mock_feed, podcast_config):
        """Test handling of malformed feed."""
        mock_feed.bozo = True
        mock_feed.bozo_exception = "Parse error"
        mock_feedparser.parse.return_value = mock_feed
        
        # Should still work but log warning
        result = fetch_podcast_feed(podcast_config)
        assert result['title'] == 'Test Podcast'
    
    @patch('src.utils.feed_processing.feedparser')
    def test_feed_parse_error(self, mock_feedparser, podcast_config):
        """Test handling of feed parse error."""
        mock_feedparser.parse.side_effect = Exception("Network error")
        
        with pytest.raises(FeedParsingError, match="Failed to parse RSS feed"):
            fetch_podcast_feed(podcast_config)
    
    @patch('src.utils.feed_processing.feedparser')
    def test_max_episodes_limit(self, mock_feedparser, mock_feed, podcast_config):
        """Test max episodes limit."""
        mock_feedparser.parse.return_value = mock_feed
        
        result = fetch_podcast_feed(podcast_config, max_episodes=1)
        assert len(result['episodes']) == 1


class TestFeedExtraction:
    """Tests for feed extraction helper functions."""
    
    def test_extract_feed_image(self):
        """Test feed image extraction."""
        # Test with image.href
        feed = Mock()
        feed.feed = Mock()
        feed.feed.image = Mock(href="https://example.com/image.jpg")
        assert _extract_feed_image(feed) == "https://example.com/image.jpg"
        
        # Test with image.url
        feed.feed.image = Mock(url="https://example.com/image2.jpg")
        del feed.feed.image.href
        assert _extract_feed_image(feed) == "https://example.com/image2.jpg"
        
        # Test with iTunes image
        feed.feed = Mock(itunes_image="https://example.com/itunes.jpg")
        assert _extract_feed_image(feed) == "https://example.com/itunes.jpg"
    
    def test_extract_categories(self):
        """Test category extraction."""
        feed = Mock()
        feed.feed = Mock()
        
        # iTunes category
        feed.feed.itunes_category = "Technology"
        categories = _extract_categories(feed)
        assert "Technology" in categories
        
        # Regular categories
        feed.feed.categories = [("Business",), "Education"]
        categories = _extract_categories(feed)
        assert "Business" in categories
        assert "Education" in categories
    
    def test_find_audio_url(self):
        """Test audio URL finding."""
        # Test with links
        entry = Mock()
        entry.links = [
            Mock(href="https://example.com/page", type="text/html"),
            Mock(href="https://example.com/audio.mp3", type="audio/mpeg")
        ]
        assert _find_audio_url(entry) == "https://example.com/audio.mp3"
        
        # Test with enclosures
        entry = Mock()
        entry.enclosures = [Mock(href="https://example.com/ep.m4a", type="audio/mp4")]
        assert _find_audio_url(entry) == "https://example.com/ep.m4a"
        
        # Test by extension
        entry = Mock()
        entry.links = [Mock(href="https://example.com/file.mp3")]
        entry.enclosures = []
        assert _find_audio_url(entry) == "https://example.com/file.mp3"
    
    def test_generate_episode_id(self):
        """Test episode ID generation."""
        # With existing ID
        entry = Mock(id="existing-id")
        episode_id = _generate_episode_id(entry, "https://audio.url")
        assert len(episode_id) == 32  # SHA256 truncated
        
        # With GUID
        entry = Mock(guid="guid-123")
        del entry.id
        episode_id = _generate_episode_id(entry, "https://audio.url")
        assert len(episode_id) == 32
        
        # Generated from title and URL
        entry = Mock(title="Episode Title")
        entry.link = "https://episode.link"
        episode_id = _generate_episode_id(entry, "https://audio.url")
        assert len(episode_id) == 32
    
    def test_parse_date(self):
        """Test date parsing."""
        # Valid ISO date
        assert "2023-01-01" in _parse_date("2023-01-01T00:00:00Z")
        
        # Empty date
        result = _parse_date("")
        assert len(result) > 0  # Should return current date
        
        # Invalid date (no dateutil)
        with patch('src.utils.feed_processing.date_parse', side_effect=ImportError):
            result = _parse_date("invalid date")
            assert result == "invalid date"  # Returns as-is
    
    def test_extract_keywords(self):
        """Test keyword extraction."""
        entry = Mock()
        
        # iTunes keywords
        entry.itunes_keywords = "tech, podcast, audio"
        keywords = _extract_keywords(entry)
        assert "tech" in keywords
        assert "podcast" in keywords
        assert "audio" in keywords
        
        # Regular tags
        entry.tags = [Mock(term="news"), Mock(term="technology")]
        keywords = _extract_keywords(entry)
        assert "news" in keywords
        assert "technology" in keywords


class TestDownloadEpisodeAudio:
    """Tests for download_episode_audio function."""
    
    @pytest.fixture
    def episode(self):
        """Create test episode."""
        return {
            'id': 'test-episode',
            'title': 'Test Episode',
            'audio_url': 'https://example.com/audio.mp3'
        }
    
    def test_file_already_exists(self, episode):
        """Test when file already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing file
            expected_path = os.path.join(tmpdir, "test-podcast_test-episode.mp3")
            with open(expected_path, 'wb') as f:
                f.write(b'x' * 2048)  # Non-empty file
            
            result = download_episode_audio(episode, 'test-podcast', tmpdir)
            assert result == expected_path
    
    @patch('urllib.request.urlopen')
    def test_successful_download(self, mock_urlopen, episode):
        """Test successful audio download."""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b'audio data'
        mock_response.headers.get.return_value = 'audio/mpeg'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_episode_audio(episode, 'test-podcast', tmpdir)
            
            assert result is not None
            assert os.path.exists(result)
            with open(result, 'rb') as f:
                assert f.read() == b'audio data'
    
    @patch('urllib.request.urlopen')
    def test_download_with_retry(self, mock_urlopen, episode):
        """Test download with retry on failure."""
        # First attempt fails, second succeeds
        mock_response = MagicMock()
        mock_response.read.return_value = b'audio data'
        mock_response.__enter__.return_value = mock_response
        
        mock_urlopen.side_effect = [
            urllib.error.HTTPError(None, 500, "Server Error", {}, None),
            mock_response
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_episode_audio(episode, 'test-podcast', tmpdir, max_retries=2)
            
            assert result is not None
            assert mock_urlopen.call_count == 2
    
    @patch('urllib.request.urlopen')
    def test_download_404_no_retry(self, mock_urlopen, episode):
        """Test that 404 errors don't retry."""
        mock_urlopen.side_effect = urllib.error.HTTPError(None, 404, "Not Found", {}, None)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_episode_audio(episode, 'test-podcast', tmpdir, max_retries=3)
            
            assert result is None
            assert mock_urlopen.call_count == 1  # No retries on 404
    
    @patch('urllib.request.urlopen')
    def test_empty_file_error(self, mock_urlopen, episode):
        """Test error when downloaded file is empty."""
        mock_response = MagicMock()
        mock_response.read.return_value = b''  # Empty response
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_episode_audio(episode, 'test-podcast', tmpdir)
            assert result is None


class TestValidatePodcastConfig:
    """Tests for validate_podcast_config function."""
    
    def test_valid_config(self):
        """Test validation of valid config."""
        config = {
            'id': 'test-podcast',
            'rss_url': 'https://example.com/feed.rss'
        }
        is_valid, errors = validate_podcast_config(config)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_missing_required_fields(self):
        """Test validation with missing fields."""
        config = {}
        is_valid, errors = validate_podcast_config(config)
        assert is_valid is False
        assert "Missing required field: id" in errors
        assert "Missing required field: rss_url" in errors
    
    def test_invalid_rss_url(self):
        """Test validation with invalid RSS URL."""
        config = {
            'id': 'test',
            'rss_url': 'not-a-url'
        }
        is_valid, errors = validate_podcast_config(config)
        assert is_valid is False
        assert any("must start with http://" in e for e in errors)
    
    def test_invalid_id_format(self):
        """Test validation with invalid ID format."""
        config = {
            'id': 'test podcast!',  # Contains invalid characters
            'rss_url': 'https://example.com/feed.rss'
        }
        is_valid, errors = validate_podcast_config(config)
        assert is_valid is False
        assert any("letters, numbers, hyphens, and underscores" in e for e in errors)


class TestParseDuration:
    """Tests for parse_duration function."""
    
    def test_parse_hhmmss(self):
        """Test parsing HH:MM:SS format."""
        assert parse_duration("01:23:45") == 5025  # 1h 23m 45s
        assert parse_duration("10:00:00") == 36000  # 10 hours
    
    def test_parse_mmss(self):
        """Test parsing MM:SS format."""
        assert parse_duration("23:45") == 1425  # 23m 45s
        assert parse_duration("05:30") == 330  # 5m 30s
    
    def test_parse_seconds(self):
        """Test parsing seconds only."""
        assert parse_duration("3600") == 3600
        assert parse_duration("120") == 120
    
    def test_parse_invalid(self):
        """Test parsing invalid formats."""
        assert parse_duration("") is None
        assert parse_duration("invalid") is None
        assert parse_duration("1:2:3:4") is None