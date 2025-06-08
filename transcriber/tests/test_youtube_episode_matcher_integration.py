"""Integration tests for YouTube episode matcher."""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.youtube_episode_matcher import YouTubeEpisodeMatcher, NoConfidentMatchError
from src.youtube_api_client import YouTubeAPIError, QuotaExceededError
from src.config import Config


class TestYouTubeEpisodeMatcherIntegration:
    """Integration tests for YouTubeEpisodeMatcher."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        config = Config.create_test_config()
        config.youtube_api.api_key = "test-api-key"
        config.youtube_api.confidence_threshold = 0.90
        config.youtube_api.max_results_per_search = 5
        config.youtube_api.search_quota_per_episode = 500
        config.output.default_dir = str(tmp_path)
        return config
    
    @pytest.fixture
    def matcher(self, config):
        """Create matcher instance with mocked API client."""
        with patch('src.youtube_episode_matcher.YouTubeAPIClient'):
            return YouTubeEpisodeMatcher(config)
    
    @pytest.fixture
    def mock_search_results(self):
        """Create mock search results."""
        return [
            {
                'video_id': 'exact_match_123',
                'title': 'The Podcast Episode 123: Interview with Jane Doe',
                'channel_id': 'channel_official',
                'channel_title': 'The Podcast Official',
                'published_at': datetime.utcnow().isoformat() + 'Z',
                'duration_seconds': 3600,
                'description': 'Great interview about technology',
                'view_count': 10000,
                'like_count': 500
            },
            {
                'video_id': 'partial_match_456',
                'title': 'Episode 123 with Jane',
                'channel_id': 'channel_unofficial',
                'channel_title': 'Random Channel',
                'published_at': (datetime.utcnow() - timedelta(days=5)).isoformat() + 'Z',
                'duration_seconds': 3300,
                'view_count': 1000,
                'like_count': 50
            },
            {
                'video_id': 'poor_match_789',
                'title': 'Different Show Episode 999',
                'channel_id': 'channel_other',
                'channel_title': 'Other Channel',
                'published_at': (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z',
                'duration_seconds': 1800,
                'view_count': 100,
                'like_count': 5
            }
        ]
    
    @pytest.mark.asyncio
    async def test_successful_exact_match(self, matcher, mock_search_results):
        """Test successful exact match scenario."""
        # Mock API client methods
        matcher.api_client.search_videos = Mock(return_value=mock_search_results[:1])
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600,
            'view_count': 10000,
            'like_count': 500,
            'comment_count': 100
        }])
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe",
            episode_duration=3600,
            episode_date=datetime.utcnow()
        )
        
        assert result == "https://www.youtube.com/watch?v=exact_match_123"
        assert matcher.metrics['matches_found'] == 1
        assert matcher.metrics['matches_above_threshold'] == 1
        
    @pytest.mark.asyncio
    async def test_fuzzy_match_acceptance(self, matcher, mock_search_results):
        """Test fuzzy match with high enough confidence."""
        # First search returns partial matches
        matcher.api_client.search_videos = Mock(return_value=mock_search_results[1:2])
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'partial_match_456',
            'duration_seconds': 3300,
            'view_count': 1000,
            'like_count': 50,
            'comment_count': 10
        }])
        
        # Mock known channel to boost confidence
        matcher.channel_associations = {"The Podcast": ["channel_unofficial"]}
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe",
            episode_duration=3600,
            episode_date=datetime.utcnow()
        )
        
        # Should accept the match due to channel association
        assert result is not None
        assert "partial_match_456" in result
        
    @pytest.mark.asyncio
    async def test_no_match_handling(self, matcher):
        """Test handling when no matches found."""
        # Mock empty search results
        matcher.api_client.search_videos = Mock(return_value=[])
        matcher.api_client.get_video_details = Mock(return_value=[])
        
        result = await matcher.match_episode(
            podcast_name="Nonexistent Podcast",
            episode_title="Episode 999: Does Not Exist",
            episode_duration=3600
        )
        
        assert result is None
        assert matcher.metrics['matches_found'] == 0
        
    @pytest.mark.asyncio
    async def test_multiple_candidate_selection(self, matcher, mock_search_results):
        """Test selecting best match from multiple candidates."""
        # Return all mock results
        matcher.api_client.search_videos = Mock(return_value=mock_search_results)
        matcher.api_client.get_video_details = Mock(return_value=[
            {'video_id': r['video_id'], 'duration_seconds': r['duration_seconds']}
            for r in mock_search_results
        ])
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe",
            episode_duration=3600,
            episode_date=datetime.utcnow()
        )
        
        # Should select the best match (exact_match_123)
        assert result == "https://www.youtube.com/watch?v=exact_match_123"
        
    @pytest.mark.asyncio
    async def test_channel_learning_flow(self, matcher, mock_search_results, tmp_path):
        """Test channel learning and persistence."""
        # Start with no known channels
        assert matcher.channel_associations == {}
        
        # Mock successful search
        matcher.api_client.search_videos = Mock(return_value=mock_search_results[:1])
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe"
        )
        
        # Should learn the channel
        assert "The Podcast" in matcher.channel_associations
        assert "channel_official" in matcher.channel_associations["The Podcast"]
        
        # Check persistence
        cache_file = tmp_path / ".channel_associations.json"
        assert cache_file.exists()
        
        with open(cache_file) as f:
            saved_associations = json.load(f)
        assert saved_associations == matcher.channel_associations
        
    @pytest.mark.asyncio
    async def test_quota_exceeded_handling(self, matcher):
        """Test handling of quota exceeded errors."""
        # Mock quota exceeded on first call
        matcher.api_client.search_videos = Mock(
            side_effect=QuotaExceededError("Daily quota exceeded")
        )
        
        with pytest.raises(QuotaExceededError):
            await matcher.match_episode(
                podcast_name="The Podcast",
                episode_title="Episode 123"
            )
            
    @pytest.mark.asyncio
    async def test_api_error_recovery(self, matcher, mock_search_results):
        """Test recovery from API errors."""
        # First query fails, second succeeds
        call_count = 0
        
        def search_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise YouTubeAPIError("Temporary error")
            return mock_search_results[:1]
            
        matcher.api_client.search_videos = Mock(side_effect=search_side_effect)
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe"
        )
        
        # Should recover and find match
        assert result is not None
        assert call_count == 2  # First failed, second succeeded
        
    @pytest.mark.asyncio
    async def test_fallback_guest_search(self, matcher, mock_search_results):
        """Test fallback search with guest name."""
        # First searches return nothing
        call_count = 0
        
        def search_side_effect(query, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return results only for guest name search
            if "Jane Doe" in query and "The Podcast" in query:
                return mock_search_results[:1]
            return []
            
        matcher.api_client.search_videos = Mock(side_effect=search_side_effect)
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe"
        )
        
        # Should find match through fallback
        assert result is not None
        assert call_count > 1  # Multiple searches attempted
        
    @pytest.mark.asyncio
    async def test_channel_uploads_fallback(self, matcher, mock_search_results):
        """Test fallback to channel uploads search."""
        # Set known channel
        matcher.channel_associations = {"The Podcast": ["channel_official"]}
        
        # Regular searches return nothing
        def search_side_effect(query, channel_id=None, *args, **kwargs):
            if channel_id == "channel_official":
                return mock_search_results[:1]
            return []
            
        matcher.api_client.search_videos = Mock(side_effect=search_side_effect)
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        result = await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123: Interview with Jane Doe"
        )
        
        # Should find match through channel search
        assert result is not None
        
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, matcher, mock_search_results):
        """Test metrics are tracked correctly."""
        # Mock successful search
        matcher.api_client.search_videos = Mock(return_value=mock_search_results[:1])
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        # Process multiple episodes
        for i in range(3):
            result = await matcher.match_episode(
                podcast_name="The Podcast",
                episode_title=f"Episode {i}: Test"
            )
            if i < 2:  # Make first 2 succeed
                assert result is not None
            
        metrics = matcher.get_metrics()
        assert metrics['total_episodes'] >= 3
        assert metrics['matches_found'] >= 2
        assert metrics['searches_performed'] >= 3
        assert metrics['success_rate'] > 0
        assert 'quota_status' in metrics
        
    @pytest.mark.asyncio
    async def test_concurrent_episode_handling(self, matcher, mock_search_results):
        """Test handling multiple episodes concurrently."""
        # Mock API to return different results for different queries
        def search_side_effect(query, *args, **kwargs):
            if "Episode 1" in query:
                return [mock_search_results[0]]
            elif "Episode 2" in query:
                return [mock_search_results[1]]
            return []
            
        matcher.api_client.search_videos = Mock(side_effect=search_side_effect)
        matcher.api_client.get_video_details = Mock(side_effect=lambda ids: [
            {'video_id': vid, 'duration_seconds': 3600} for vid in ids
        ])
        
        # Process episodes concurrently
        tasks = [
            matcher.match_episode("Podcast", f"Episode {i}: Test")
            for i in range(1, 3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should handle both without errors
        assert len(results) == 2
        assert all(isinstance(r, str) or r is None for r in results)
        
    @pytest.mark.asyncio
    async def test_cache_hit_optimization(self, matcher, mock_search_results):
        """Test that known channels improve search efficiency."""
        # Pre-populate channel cache
        matcher.channel_associations = {"The Podcast": ["channel_official"]}
        
        # Mock search to track channel_id parameter
        search_calls = []
        
        def track_search(*args, **kwargs):
            search_calls.append(kwargs.get('channel_id'))
            return mock_search_results[:1]
            
        matcher.api_client.search_videos = Mock(side_effect=track_search)
        matcher.api_client.get_video_details = Mock(return_value=[{
            'video_id': 'exact_match_123',
            'duration_seconds': 3600
        }])
        
        await matcher.match_episode(
            podcast_name="The Podcast",
            episode_title="Episode 123"
        )
        
        # Should use known channel in search
        assert any(call == "channel_official" for call in search_calls)
        assert matcher.metrics['cache_hits'] > 0