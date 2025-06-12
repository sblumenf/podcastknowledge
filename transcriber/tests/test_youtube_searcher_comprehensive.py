"""Comprehensive tests for YouTube Searcher module to improve coverage."""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.youtube_searcher import YouTubeSearcher
from src.config import Config


class TestYouTubeSearcherBasicFunctionality:
    """Test basic YouTube searcher functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config.create_test_config()
        config.youtube_search.enabled = True
        config.youtube_search.method = 'rss_only'
        config.youtube_search.cache_results = True
        config.youtube_search.fuzzy_match_threshold = 0.85
        config.youtube_search.duration_tolerance = 0.1
        config.youtube_search.max_search_results = 5
        return config
    
    @pytest.fixture
    def searcher(self, config, tmp_path):
        """Create searcher instance."""
        config.output.base_dir = str(tmp_path)
        return YouTubeSearcher(config)
    
    def test_initialization(self, searcher, config):
        """Test searcher initialization."""
        assert searcher.search_enabled == True
        assert searcher.method == 'rss_only'
        assert searcher.cache_results == True
        assert searcher.fuzzy_match_threshold == 0.85
        assert searcher.duration_tolerance == 0.1
        assert searcher.max_search_results == 5
        assert searcher.cache_file.name == ".youtube_cache.json"
    
    @pytest.mark.asyncio
    async def test_search_disabled(self, searcher):
        """Test search when disabled."""
        searcher.search_enabled = False
        
        result = await searcher.search_youtube_url(
            episode_title="Test Episode",
            podcast_name="Test Podcast"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_extract_youtube_url_from_description(self, searcher):
        """Test extracting YouTube URL from episode description."""
        # Test various YouTube URL formats
        descriptions = [
            "Check out the video at https://www.youtube.com/watch?v=abc123",
            "Video: https://youtu.be/xyz789",
            "Watch on YouTube: youtube.com/watch?v=test456",
            "Available at https://m.youtube.com/watch?v=mobile123",
            "No URL here"
        ]
        
        expected_results = [
            "https://www.youtube.com/watch?v=abc123",
            "https://www.youtube.com/watch?v=xyz789",
            "https://www.youtube.com/watch?v=test456",
            "https://www.youtube.com/watch?v=mobile123",
            None
        ]
        
        for desc, expected in zip(descriptions, expected_results):
            result = await searcher.search_youtube_url(
                episode_title="Test",
                episode_description=desc
            )
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, searcher, tmp_path):
        """Test cache loading and saving."""
        # Test cache loading with no file
        searcher._load_cache()
        assert searcher.cache == {}
        
        # Add to cache and save
        searcher.cache["episode_123"] = "https://youtube.com/watch?v=123"
        searcher._save_cache()
        
        # Verify file was created
        assert searcher.cache_file.exists()
        
        # Create new searcher and load cache
        new_searcher = YouTubeSearcher(searcher.config)
        new_searcher._load_cache()
        assert new_searcher.cache["episode_123"] == "https://youtube.com/watch?v=123"
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, searcher):
        """Test cache hit scenario."""
        # Pre-populate cache
        episode_guid = "test-guid-123"
        cached_url = "https://youtube.com/watch?v=cached123"
        searcher.cache[episode_guid] = cached_url
        searcher._cache_loaded = True
        
        result = await searcher.search_youtube_url(
            episode_title="Test Episode",
            episode_guid=episode_guid
        )
        
        assert result == cached_url
    
    def test_normalize_youtube_url(self, searcher):
        """Test YouTube URL normalization."""
        test_cases = [
            ("https://youtu.be/abc123", "https://www.youtube.com/watch?v=abc123"),
            ("youtube.com/watch?v=xyz789", "https://www.youtube.com/watch?v=xyz789"),
            ("https://m.youtube.com/watch?v=mobile", "https://www.youtube.com/watch?v=mobile"),
            ("https://www.youtube.com/watch?v=test&t=123s", "https://www.youtube.com/watch?v=test"),
            ("invalid-url", None)
        ]
        
        for input_url, expected in test_cases:
            result = searcher._normalize_youtube_url(input_url)
            assert result == expected


class TestYouTubeSearcherExternalSearch:
    """Test external search functionality."""
    
    @pytest.fixture
    def searcher_with_external(self, tmp_path):
        """Create searcher with external search enabled."""
        config = Config.create_test_config()
        config.output.base_dir = str(tmp_path)
        config.youtube_search.enabled = True
        config.youtube_search.method = 'external'
        return YouTubeSearcher(config)
    
    @pytest.mark.asyncio
    @patch('src.youtube_searcher.YouTubeEpisodeMatcher')
    async def test_external_search_success(self, mock_matcher_class, searcher_with_external):
        """Test successful external search."""
        # Mock the matcher
        mock_matcher = Mock()
        mock_matcher_class.return_value = mock_matcher
        mock_matcher.match_episode = Mock(
            return_value="https://www.youtube.com/watch?v=external123"
        )
        
        result = await searcher_with_external.search_youtube_url(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            episode_number=123,
            duration_seconds=3600
        )
        
        assert result == "https://www.youtube.com/watch?v=external123"
        mock_matcher.match_episode.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.youtube_searcher.YouTubeEpisodeMatcher')
    async def test_external_search_no_match(self, mock_matcher_class, searcher_with_external):
        """Test external search with no match."""
        mock_matcher = Mock()
        mock_matcher_class.return_value = mock_matcher
        mock_matcher.match_episode = Mock(return_value=None)
        
        result = await searcher_with_external.search_youtube_url(
            episode_title="No Match Episode",
            podcast_name="Test Podcast"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    @patch('src.youtube_searcher.YouTubeEpisodeMatcher')
    async def test_external_search_error_handling(self, mock_matcher_class, searcher_with_external):
        """Test external search error handling."""
        mock_matcher = Mock()
        mock_matcher_class.return_value = mock_matcher
        mock_matcher.match_episode = Mock(side_effect=Exception("API Error"))
        
        result = await searcher_with_external.search_youtube_url(
            episode_title="Error Episode",
            podcast_name="Test Podcast"
        )
        
        # Should return None on error
        assert result is None


class TestYouTubeSearcherEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def searcher(self, tmp_path):
        """Create searcher instance."""
        config = Config.create_test_config()
        config.output.base_dir = str(tmp_path)
        return YouTubeSearcher(config)
    
    @pytest.mark.asyncio
    async def test_empty_inputs(self, searcher):
        """Test with empty inputs."""
        result = await searcher.search_youtube_url(
            episode_title="",
            episode_description=None
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_multiple_urls_in_description(self, searcher):
        """Test handling multiple YouTube URLs in description."""
        description = """
        Check out these videos:
        1. https://youtube.com/watch?v=first123
        2. https://youtu.be/second456
        3. https://youtube.com/watch?v=third789
        """
        
        result = await searcher.search_youtube_url(
            episode_title="Multi URL Episode",
            episode_description=description
        )
        
        # Should return the first valid URL
        assert result == "https://www.youtube.com/watch?v=first123"
    
    def test_cache_corruption_handling(self, searcher, tmp_path):
        """Test handling of corrupted cache file."""
        # Write corrupted cache
        cache_file = tmp_path / ".youtube_cache.json"
        cache_file.write_text("{corrupted json")
        
        # Should handle gracefully
        searcher._load_cache()
        assert searcher.cache == {}
    
    def test_cache_save_error_handling(self, searcher):
        """Test cache save error handling."""
        # Make cache file unwritable
        searcher.cache_file = Path("/invalid/path/.youtube_cache.json")
        searcher.cache["test"] = "value"
        
        # Should not raise exception
        searcher._save_cache()
    
    @pytest.mark.asyncio
    async def test_combined_search_method(self, searcher):
        """Test combined search method (RSS + external)."""
        searcher.method = 'combined'
        
        # Test with URL in description (should use RSS)
        result = await searcher.search_youtube_url(
            episode_title="Test",
            episode_description="Watch at https://youtube.com/watch?v=rss123"
        )
        assert result == "https://www.youtube.com/watch?v=rss123"
    
    @pytest.mark.asyncio
    async def test_invalid_youtube_urls(self, searcher):
        """Test handling of invalid YouTube URLs."""
        invalid_urls = [
            "https://youtube.com/",  # No video ID
            "https://youtube.com/channel/123",  # Channel URL
            "https://youtube.com/playlist?list=123",  # Playlist URL
            "https://vimeo.com/123456",  # Non-YouTube URL
        ]
        
        for url in invalid_urls:
            result = await searcher.search_youtube_url(
                episode_title="Test",
                episode_description=f"Video at {url}"
            )
            # Should not extract non-video URLs
            assert result is None or "watch?v=" in result


class TestYouTubeSearcherIntegration:
    """Integration tests for YouTube searcher."""
    
    @pytest.fixture
    def full_config(self, tmp_path):
        """Create full configuration with all options."""
        config = Config.create_test_config()
        config.output.base_dir = str(tmp_path)
        config.youtube_search.enabled = True
        config.youtube_search.method = 'combined'
        config.youtube_search.cache_results = True
        config.youtube_api.api_key = "test-key"
        return config
    
    @pytest.mark.asyncio
    async def test_full_search_flow_with_caching(self, full_config):
        """Test complete search flow with caching."""
        searcher = YouTubeSearcher(full_config)
        
        # First search - no cache
        episode_guid = "test-episode-guid"
        url = "https://youtube.com/watch?v=test123"
        
        result = await searcher.search_youtube_url(
            episode_title="Test Episode",
            episode_description=f"Video: {url}",
            episode_guid=episode_guid
        )
        
        assert result == "https://www.youtube.com/watch?v=test123"
        
        # Second search - should hit cache
        searcher2 = YouTubeSearcher(full_config)
        result2 = await searcher2.search_youtube_url(
            episode_title="Different Title",  # Different title
            episode_description="No URL here",  # No URL
            episode_guid=episode_guid  # Same GUID
        )
        
        assert result2 == "https://www.youtube.com/watch?v=test123"  # From cache
    
    @pytest.mark.asyncio
    async def test_search_priority_order(self, full_config):
        """Test search method priority order."""
        searcher = YouTubeSearcher(full_config)
        
        # Cache has highest priority
        searcher.cache["guid-123"] = "https://youtube.com/watch?v=cached"
        searcher._cache_loaded = True
        
        result = await searcher.search_youtube_url(
            episode_title="Test",
            episode_description="https://youtube.com/watch?v=description",
            episode_guid="guid-123"
        )
        
        assert result == "https://youtube.com/watch?v=cached"
        
        # Description URL has priority over external search
        result2 = await searcher.search_youtube_url(
            episode_title="Test",
            episode_description="https://youtube.com/watch?v=description",
            episode_guid="new-guid"
        )
        
        assert result2 == "https://www.youtube.com/watch?v=description"
    
    @pytest.mark.asyncio
    async def test_batch_search_performance(self, full_config):
        """Test performance with multiple searches."""
        searcher = YouTubeSearcher(full_config)
        
        # Simulate batch of episodes
        episodes = [
            {
                "title": f"Episode {i}",
                "description": f"Watch at https://youtube.com/watch?v=ep{i}",
                "guid": f"guid-{i}"
            }
            for i in range(10)
        ]
        
        # Search all episodes
        results = []
        for ep in episodes:
            result = await searcher.search_youtube_url(
                episode_title=ep["title"],
                episode_description=ep["description"],
                episode_guid=ep["guid"]
            )
            results.append(result)
        
        # All should be found
        assert len(results) == 10
        assert all(r is not None for r in results)
        
        # Cache should have all entries
        assert len(searcher.cache) == 10