"""Unit tests for YouTube searcher module."""

import pytest
from unittest.mock import patch, Mock
import re

from src.youtube_searcher import YouTubeSearcher
from src.config import Config


@pytest.mark.unit
class TestYouTubeSearcher:
    """Test YouTube searcher functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        config = Mock(spec=Config)
        config.youtube_search = Mock()
        config.youtube_search.enabled = True
        config.youtube_search.extract_from_rss = True
        config.youtube_search.use_yt_dlp = False
        config.youtube_search.fuzzy_match_threshold = 0.8
        config.youtube_search.cache_results = True
        config.youtube_search.search_limit = 5
        return config
    
    @pytest.fixture
    def searcher(self, config):
        """Create YouTube searcher instance."""
        return YouTubeSearcher(config)
    
    def test_init(self, config):
        """Test YouTubeSearcher initialization."""
        searcher = YouTubeSearcher(config)
        assert searcher.config == config
        assert searcher.search_enabled is True
        assert searcher.cache_file.name == ".youtube_cache.json"
        assert searcher.cache == {}
    
    def test_init_disabled(self, config):
        """Test YouTubeSearcher when search is disabled."""
        config.youtube_search.enabled = False
        searcher = YouTubeSearcher(config)
        assert searcher.search_enabled is False
    
    def test_load_cache_no_file(self, searcher, tmp_path):
        """Test loading cache when file doesn't exist."""
        searcher.cache_file = tmp_path / "nonexistent_cache.json"
        cache = searcher._load_cache()
        assert cache == {}
    
    def test_load_cache_with_data(self, searcher, tmp_path):
        """Test loading cache with existing data."""
        cache_file = tmp_path / "cache.json"
        cache_data = {"episode1": "https://youtube.com/watch?v=123"}
        cache_file.write_text('{"episode1": "https://youtube.com/watch?v=123"}')
        
        searcher.cache_file = cache_file
        cache = searcher._load_cache()
        assert cache == cache_data
    
    def test_load_cache_corrupted(self, searcher, tmp_path):
        """Test loading corrupted cache file."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("invalid json{")
        
        searcher.cache_file = cache_file
        cache = searcher._load_cache()
        assert cache == {}
    
    def test_save_cache(self, searcher, tmp_path):
        """Test saving cache."""
        searcher.cache_file = tmp_path / "cache.json"
        searcher.cache = {"episode1": "https://youtube.com/watch?v=123"}
        
        searcher._save_cache()
        
        # Verify file was written
        assert searcher.cache_file.exists()
        import json
        with open(searcher.cache_file) as f:
            saved_data = json.load(f)
        assert saved_data == searcher.cache
    
    def test_extract_youtube_url_from_text_full_url(self, searcher):
        """Test extracting full YouTube URL from text."""
        text = "Check out the video: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url = searcher._extract_youtube_url_from_text(text)
        assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_extract_youtube_url_from_text_short_url(self, searcher):
        """Test extracting short YouTube URL from text."""
        text = "Video here: https://youtu.be/dQw4w9WgXcQ"
        url = searcher._extract_youtube_url_from_text(text)
        assert url == "https://youtu.be/dQw4w9WgXcQ"
    
    def test_extract_youtube_url_from_text_no_url(self, searcher):
        """Test extracting URL when none present."""
        text = "This is a podcast episode with no YouTube link"
        url = searcher._extract_youtube_url_from_text(text)
        assert url is None
    
    def test_extract_youtube_url_from_text_multiple_urls(self, searcher):
        """Test extracting URL when multiple present (returns first)."""
        text = "Video 1: https://youtube.com/watch?v=abc123 Video 2: https://youtu.be/xyz789"
        url = searcher._extract_youtube_url_from_text(text)
        assert url == "https://youtube.com/watch?v=abc123"
    
    @pytest.mark.asyncio
    async def test_search_youtube_url_disabled(self, searcher):
        """Test search when YouTube search is disabled."""
        searcher.search_enabled = False
        result = await searcher.search_youtube_url("Test Episode", "Test description")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_search_youtube_url_cached(self, searcher):
        """Test search returns cached result."""
        episode_id = "Test Episode_test-guid"
        searcher.cache = {episode_id: "https://youtube.com/watch?v=cached"}
        searcher._cache_loaded = True  # Mark cache as loaded
        
        result = await searcher.search_youtube_url(
            "Test Episode", "Test description", episode_guid="test-guid"
        )
        assert result == "https://youtube.com/watch?v=cached"
    
    @pytest.mark.asyncio
    async def test_search_youtube_url_from_rss(self, searcher):
        """Test search extracts URL from RSS description."""
        description = "Episode description with https://www.youtube.com/watch?v=rss123"
        searcher._cache_loaded = True  # Mark cache as loaded
        
        result = await searcher.search_youtube_url("Test Episode", description)
        assert result == "https://www.youtube.com/watch?v=rss123"
        
        # Check it was cached
        assert "Test Episode_" in searcher.cache
        assert searcher.cache[list(searcher.cache.keys())[0]] == "https://www.youtube.com/watch?v=rss123"
    
    @pytest.mark.asyncio
    async def test_search_youtube_url_no_result(self, searcher):
        """Test search with no YouTube URL found."""
        searcher._cache_loaded = True  # Mark cache as loaded
        result = await searcher.search_youtube_url(
            "Test Episode", "No YouTube link in this description"
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_search_with_yt_dlp_disabled(self, searcher):
        """Test search doesn't use yt-dlp when disabled."""
        searcher.config.youtube_search.use_yt_dlp = False
        searcher._cache_loaded = True  # Mark cache as loaded
        
        with patch('subprocess.run') as mock_run:
            result = await searcher.search_youtube_url(
                "Test Episode", "No YouTube link here"
            )
            
            # Should not call subprocess
            mock_run.assert_not_called()
            assert result is None
    
    def test_fuzzy_match_exact(self, searcher):
        """Test fuzzy match with exact match."""
        score = searcher._fuzzy_match("Test Episode", "Test Episode")
        assert score == 1.0
    
    def test_fuzzy_match_partial(self, searcher):
        """Test fuzzy match with partial match."""
        score = searcher._fuzzy_match("Test Episode 123", "Test Episode")
        assert score > 0.8
        assert score < 1.0
    
    def test_fuzzy_match_no_match(self, searcher):
        """Test fuzzy match with no match."""
        score = searcher._fuzzy_match("Test Episode", "Completely Different")
        assert score < 0.5
    
    def test_youtube_url_patterns(self, searcher):
        """Test various YouTube URL patterns are recognized."""
        patterns = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be",
        ]
        
        for pattern in patterns:
            text = f"Check out the video: {pattern}"
            url = searcher._extract_youtube_url_from_text(text)
            assert url is not None
            assert "youtube.com" in url or "youtu.be" in url