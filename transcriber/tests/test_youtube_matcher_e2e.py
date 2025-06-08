"""End-to-end tests for YouTube episode matcher."""

import pytest
import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.youtube_episode_matcher import YouTubeEpisodeMatcher
from src.config import Config
from tests.fixtures.youtube_api_responses import MockResponses, YouTubeAPIResponseFactory


class TestYouTubeMatcherE2E:
    """End-to-end tests for complete YouTube matching scenarios."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        config = Config.create_test_config()
        config.youtube_api.api_key = "test-api-key"
        config.youtube_api.confidence_threshold = 0.90
        config.output.default_dir = str(tmp_path)
        return config
    
    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client."""
        client = MagicMock()
        client.SEARCH_COST = 100
        client.get_quota_status = Mock(return_value={
            'used': 0,
            'limit': 10000,
            'remaining': 10000,
            'reset_time': datetime.utcnow().isoformat(),
            'hours_until_reset': 12
        })
        return client
    
    @pytest.mark.asyncio
    async def test_popular_podcast_episode_matching(self, config, mock_api_client):
        """Test matching a popular podcast episode."""
        factory = YouTubeAPIResponseFactory()
        
        # Mock Tim Ferriss Show search results
        def search_side_effect(query, **kwargs):
            if "Tim Ferriss" in query and "123" in query:
                return [
                    factory.create_search_item(
                        video_id="tim_123_official",
                        title="The Tim Ferriss Show #123: Dr. Jane Smith - The Science of Longevity",
                        channel_id="tim_ferriss_channel",
                        channel_title="Tim Ferriss",
                        description="Dr. Jane Smith discusses breakthrough research on longevity",
                        published_at=datetime.utcnow() - timedelta(days=2)
                    ),
                    factory.create_search_item(
                        video_id="tim_123_clips",
                        title="Best Moments - Tim Ferriss & Dr. Jane Smith on Longevity",
                        channel_id="tim_clips_channel",
                        channel_title="Tim Ferriss Clips",
                        published_at=datetime.utcnow() - timedelta(days=1)
                    )
                ]
            return []
            
        mock_api_client.search_videos = Mock(side_effect=search_side_effect)
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'tim_123_official', 'duration_seconds': 7200},  # 2 hours
            {'video_id': 'tim_123_clips', 'duration_seconds': 900}  # 15 minutes
        ])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            result = await matcher.match_episode(
                podcast_name="The Tim Ferriss Show",
                episode_title="Episode 123: Dr. Jane Smith - The Science of Longevity",
                episode_duration=7200,  # 2 hours
                episode_date=datetime.utcnow() - timedelta(days=3)
            )
            
        # Should find the official full episode
        assert result == "https://www.youtube.com/watch?v=tim_123_official"
        
        # Should learn channel association
        assert "The Tim Ferriss Show" in matcher.channel_associations
        assert "tim_ferriss_channel" in matcher.channel_associations["The Tim Ferriss Show"]
        
    @pytest.mark.asyncio
    async def test_podcast_with_numbered_episodes(self, config, mock_api_client):
        """Test matching podcast with clear episode numbers."""
        factory = YouTubeAPIResponseFactory()
        
        # Mock search for numbered episode
        def search_side_effect(query, **kwargs):
            if "Daily Tech" in query and ("456" in query or "episode 456" in query.lower()):
                return [
                    factory.create_search_item(
                        video_id="daily_tech_456",
                        title="Daily Tech News Show - Episode 456",
                        channel_id="dtns_channel",
                        channel_title="Daily Tech News Show",
                        published_at=datetime.utcnow()
                    )
                ]
            return []
            
        mock_api_client.search_videos = Mock(side_effect=search_side_effect)
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'daily_tech_456', 'duration_seconds': 1800}  # 30 minutes
        ])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            result = await matcher.match_episode(
                podcast_name="Daily Tech News Show",
                episode_title="Episode 456: AI Breakthrough Announced",
                episode_number=456,
                episode_duration=1800
            )
            
        assert result == "https://www.youtube.com/watch?v=daily_tech_456"
        
    @pytest.mark.asyncio
    async def test_interview_style_podcast_matching(self, config, mock_api_client):
        """Test matching interview-style podcast."""
        factory = YouTubeAPIResponseFactory()
        
        # Mock search results
        def search_side_effect(query, **kwargs):
            # Check for guest name search
            if "Conversations" in query and "Elon Musk" in query:
                return [
                    factory.create_search_item(
                        video_id="conv_elon_2024",
                        title="Deep Conversations: Elon Musk on the Future of AI and Space",
                        channel_id="deep_conv_channel",
                        channel_title="Deep Conversations Podcast",
                        published_at=datetime.utcnow() - timedelta(days=1)
                    )
                ]
            return []
            
        mock_api_client.search_videos = Mock(side_effect=search_side_effect)
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'conv_elon_2024', 'duration_seconds': 5400}  # 1.5 hours
        ])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            result = await matcher.match_episode(
                podcast_name="Deep Conversations",
                episode_title="Interview with Elon Musk on the Future of AI and Space",
                episode_duration=5400
            )
            
        assert result == "https://www.youtube.com/watch?v=conv_elon_2024"
        
    @pytest.mark.asyncio
    async def test_non_youtube_podcast_handling(self, config, mock_api_client):
        """Test handling podcast not available on YouTube."""
        # Mock empty search results
        mock_api_client.search_videos = Mock(return_value=[])
        mock_api_client.get_video_details = Mock(return_value=[])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            result = await matcher.match_episode(
                podcast_name="Private Podcast",
                episode_title="Episode 10: Members Only Content",
                episode_duration=2400
            )
            
        # Should gracefully handle no matches
        assert result is None
        assert matcher.metrics['matches_found'] == 0
        
    @pytest.mark.asyncio
    async def test_multi_part_episode_handling(self, config, mock_api_client):
        """Test handling multi-part episodes."""
        factory = YouTubeAPIResponseFactory()
        
        # Mock search returning multiple parts
        def search_side_effect(query, **kwargs):
            if "Long Form" in query and "50" in query:
                return [
                    factory.create_search_item(
                        video_id="long_50_part1",
                        title="Long Form Podcast #50: Epic Discussion (Part 1 of 2)",
                        channel_id="long_form_channel",
                        channel_title="Long Form Podcast",
                        published_at=datetime.utcnow()
                    ),
                    factory.create_search_item(
                        video_id="long_50_part2",
                        title="Long Form Podcast #50: Epic Discussion (Part 2 of 2)",
                        channel_id="long_form_channel",
                        channel_title="Long Form Podcast",
                        published_at=datetime.utcnow()
                    )
                ]
            return []
            
        mock_api_client.search_videos = Mock(side_effect=search_side_effect)
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'long_50_part1', 'duration_seconds': 5400},  # 1.5 hours each
            {'video_id': 'long_50_part2', 'duration_seconds': 5400}
        ])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            # Search for full episode (3 hours)
            result = await matcher.match_episode(
                podcast_name="Long Form Podcast",
                episode_title="Episode 50: Epic Discussion with Multiple Guests",
                episode_duration=10800  # 3 hours total
            )
            
        # Should find part 1 (better title match)
        assert result is not None
        assert "long_50_part" in result
        
    @pytest.mark.asyncio
    async def test_channel_learning_persistence(self, config, mock_api_client, tmp_path):
        """Test channel associations persist across instances."""
        factory = YouTubeAPIResponseFactory()
        
        # First search - new podcast
        mock_api_client.search_videos = Mock(return_value=[
            factory.create_search_item(
                video_id="test_ep1",
                title="Test Podcast Episode 1",
                channel_id="test_channel",
                channel_title="Test Podcast Official"
            )
        ])
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'test_ep1', 'duration_seconds': 3600}
        ])
        
        # First matcher instance
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher1 = YouTubeEpisodeMatcher(config)
            
            result1 = await matcher1.match_episode(
                podcast_name="Test Podcast",
                episode_title="Episode 1: Introduction"
            )
            
        assert result1 is not None
        assert "Test Podcast" in matcher1.channel_associations
        
        # Create new matcher instance - should load associations
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher2 = YouTubeEpisodeMatcher(config)
            
        # Should have loaded associations
        assert "Test Podcast" in matcher2.channel_associations
        assert "test_channel" in matcher2.channel_associations["Test Podcast"]
        
    @pytest.mark.asyncio
    async def test_various_podcast_formats(self, config, mock_api_client):
        """Test matching various podcast naming formats."""
        factory = YouTubeAPIResponseFactory()
        
        test_cases = [
            # (podcast_name, episode_title, expected_video_id)
            ("The Daily", "Thursday, January 4: News Roundup", "daily_20240104"),
            ("Serial", "S04E03: The Courthouse", "serial_s04e03"),
            ("Reply All", "#186 SIM Swap", "replyall_186"),
            ("99% Invisible", "500- The Miracle Plant", "99pi_500"),
        ]
        
        def search_side_effect(query, **kwargs):
            # Return appropriate result based on query
            for podcast, title, video_id in test_cases:
                if podcast in query:
                    return [factory.create_search_item(
                        video_id=video_id,
                        title=f"{podcast}: {title}",
                        channel_id=f"{podcast.lower().replace(' ', '_')}_channel",
                        channel_title=podcast
                    )]
            return []
            
        mock_api_client.search_videos = Mock(side_effect=search_side_effect)
        mock_api_client.get_video_details = Mock(
            side_effect=lambda ids: [{'video_id': vid, 'duration_seconds': 1800} for vid in ids]
        )
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            results = []
            for podcast_name, episode_title, expected_id in test_cases:
                result = await matcher.match_episode(
                    podcast_name=podcast_name,
                    episode_title=episode_title
                )
                results.append((result, expected_id))
                
        # All should find matches
        for result, expected_id in results:
            assert result is not None
            assert expected_id in result
            
    @pytest.mark.asyncio
    async def test_quota_management_across_episodes(self, config, mock_api_client):
        """Test quota management across multiple episodes."""
        factory = YouTubeAPIResponseFactory()
        
        # Track quota usage
        quota_used = 0
        
        def update_quota(*args, **kwargs):
            nonlocal quota_used
            quota_used += 100
            mock_api_client.get_quota_status.return_value['used'] = quota_used
            return [factory.create_search_item(
                video_id=f"video_{quota_used}",
                title="Test Episode",
                channel_id="test_channel",
                channel_title="Test"
            )]
            
        mock_api_client.search_videos = Mock(side_effect=update_quota)
        mock_api_client.get_video_details = Mock(return_value=[])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            # Process episodes until quota limit approached
            for i in range(10):
                result = await matcher.match_episode(
                    podcast_name="Test",
                    episode_title=f"Episode {i}"
                )
                
                # Check quota tracking
                assert matcher.metrics['quota_used'] == (i + 1) * 100
                
        # Should have tracked quota correctly
        assert matcher.metrics['quota_used'] >= 1000
        
    @pytest.mark.asyncio
    async def test_real_world_edge_cases(self, config, mock_api_client):
        """Test real-world edge cases."""
        factory = YouTubeAPIResponseFactory()
        
        # Case 1: Podcast with special characters
        mock_api_client.search_videos = Mock(return_value=[
            factory.create_search_item(
                video_id="special_chars",
                title="Podcast & Co. | Episode #1: Q&A!",
                channel_id="special_channel",
                channel_title="Podcast & Co."
            )
        ])
        mock_api_client.get_video_details = Mock(return_value=[
            {'video_id': 'special_chars', 'duration_seconds': 2400}
        ])
        
        with patch('src.youtube_episode_matcher.YouTubeAPIClient', return_value=mock_api_client):
            matcher = YouTubeEpisodeMatcher(config)
            
            result = await matcher.match_episode(
                podcast_name="Podcast & Co.",
                episode_title="Episode #1: Q&A!"
            )
            
        assert result == "https://www.youtube.com/watch?v=special_chars"
        
        # Case 2: Very long episode title
        long_title = "Episode 100: " + "Very Long Title " * 20
        mock_api_client.search_videos = Mock(return_value=[
            factory.create_search_item(
                video_id="long_title",
                title=long_title[:100] + "...",  # YouTube truncates
                channel_id="test_channel",
                channel_title="Test"
            )
        ])
        
        result = await matcher.match_episode(
            podcast_name="Test",
            episode_title=long_title
        )
        
        assert result == "https://www.youtube.com/watch?v=long_title"