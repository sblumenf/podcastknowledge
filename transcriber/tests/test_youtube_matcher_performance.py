"""Performance tests for YouTube episode matcher."""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import psutil
import os

from src.youtube_episode_matcher import YouTubeEpisodeMatcher
from src.youtube_api_client import YouTubeAPIClient, QuotaExceededError
from src.config import Config
from tests.fixtures.youtube_api_responses import MockResponses, YouTubeAPIResponseFactory


class TestYouTubeMatcherPerformance:
    """Performance tests for YouTube matcher components."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        config = Config.create_test_config()
        config.youtube_api.api_key = "test-api-key"
        config.youtube_api.max_results_per_search = 10
        config.output.default_dir = str(tmp_path)
        return config
    
    @pytest.fixture
    def matcher(self, config):
        """Create matcher with mocked API."""
        with patch('src.youtube_episode_matcher.YouTubeAPIClient'):
            matcher = YouTubeEpisodeMatcher(config)
            # Mock API responses to be fast
            matcher.api_client.search_videos = Mock(return_value=[])
            matcher.api_client.get_video_details = Mock(return_value=[])
            return matcher
    
    def test_search_timeout_handling(self, matcher):
        """Test handling of search timeouts."""
        # Mock slow API response
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(2)  # Simulate slow response
            return []
            
        matcher.api_client.search_videos = Mock(side_effect=slow_search)
        
        # Test with timeout
        start_time = time.time()
        
        async def run_with_timeout():
            try:
                return await asyncio.wait_for(
                    matcher.match_episode("Podcast", "Episode 1"),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                return None
                
        result = asyncio.run(run_with_timeout())
        elapsed = time.time() - start_time
        
        assert result is None
        assert elapsed < 1.5  # Should timeout quickly
        
    def test_cache_performance(self, matcher, tmp_path):
        """Test channel cache performance."""
        # Pre-populate large cache
        large_cache = {}
        for i in range(1000):
            large_cache[f"Podcast_{i}"] = [f"channel_{i}"]
            
        matcher.channel_associations = large_cache
        
        # Test cache lookup performance
        start_time = time.time()
        
        # Perform many lookups
        for i in range(10000):
            channels = matcher.channel_associations.get(f"Podcast_{i % 1000}", [])
            
        elapsed = time.time() - start_time
        
        # Should be very fast (< 10ms for 10k lookups)
        assert elapsed < 0.01
        
        # Test cache save performance
        start_time = time.time()
        matcher._save_channel_cache()
        save_elapsed = time.time() - start_time
        
        # Should complete quickly even with 1000 entries
        assert save_elapsed < 0.5
        
    @pytest.mark.asyncio
    async def test_concurrent_episode_handling(self, matcher):
        """Test performance with concurrent episodes."""
        # Mock fast API responses
        factory = YouTubeAPIResponseFactory()
        
        def create_mock_results(episode_num):
            return [factory.create_search_item(
                video_id=f"video_{episode_num}",
                title=f"Episode {episode_num}",
                channel_id="channel_1",
                channel_title="Test Channel"
            )]
            
        matcher.api_client.search_videos = Mock(
            side_effect=lambda query, **kwargs: create_mock_results(
                int(query.split()[-1]) if query.split()[-1].isdigit() else 1
            )
        )
        matcher.api_client.get_video_details = Mock(
            side_effect=lambda ids: [{'video_id': vid, 'duration_seconds': 3600} for vid in ids]
        )
        
        # Process multiple episodes concurrently
        start_time = time.time()
        
        tasks = []
        for i in range(20):
            task = matcher.match_episode(
                podcast_name="Test Podcast",
                episode_title=f"Episode {i}"
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        # All should complete
        assert len(results) == 20
        assert all(r is not None for r in results)
        
        # Should process 20 episodes quickly (< 2 seconds)
        assert elapsed < 2.0
        
    def test_memory_usage(self, matcher):
        """Test memory usage stays reasonable."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create many search results
        factory = YouTubeAPIResponseFactory()
        large_results = []
        
        for i in range(100):
            large_results.append(factory.create_search_item(
                video_id=f"video_{i}",
                title=f"Episode {i}: " + "x" * 1000,  # Long title
                channel_id=f"channel_{i}",
                channel_title=f"Channel {i}",
                description="y" * 5000  # Long description
            ))
            
        # Process with scorer
        matcher.match_scorer.score_results(
            large_results,
            episode_title="Test Episode",
            podcast_name="Test Podcast"
        )
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB)
        assert memory_increase < 50
        
    @pytest.mark.asyncio
    async def test_rate_limiting_performance(self, matcher):
        """Test performance under rate limiting."""
        call_times = []
        
        def track_calls(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) > 5:
                # Simulate rate limit after 5 calls
                raise QuotaExceededError("Rate limited")
            return []
            
        matcher.api_client.search_videos = Mock(side_effect=track_calls)
        
        # Try to process multiple episodes
        tasks = []
        for i in range(10):
            task = matcher.match_episode(
                podcast_name="Test",
                episode_title=f"Episode {i}"
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # First 5 should succeed, rest should fail with quota error
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, QuotaExceededError)]
        
        assert len(successful) <= 5
        assert len(failed) >= 5
        
    def test_query_builder_performance(self):
        """Test query builder performance."""
        from src.youtube_query_builder import QueryBuilder
        
        builder = QueryBuilder()
        
        # Test with many episodes
        start_time = time.time()
        
        for i in range(1000):
            queries = builder.build_queries(
                podcast_name="The Long Podcast Name Show",
                episode_title=f"Episode {i}: Very Long Title with Many Words and Guest Names like Dr. Jane Smith PhD",
                episode_number=i
            )
            
        elapsed = time.time() - start_time
        
        # Should process 1000 episodes quickly (< 1 second)
        assert elapsed < 1.0
        
    def test_scorer_performance(self):
        """Test match scorer performance."""
        from src.youtube_match_scorer import MatchScorer
        
        scorer = MatchScorer()
        factory = YouTubeAPIResponseFactory()
        
        # Create many results to score
        results = []
        for i in range(100):
            results.append({
                'video_id': f'video_{i}',
                'title': f'Episode {i}: Test Title with Various Words',
                'channel_id': f'channel_{i % 10}',
                'channel_title': f'Channel {i % 10}',
                'published_at': (datetime.utcnow() - timedelta(days=i)).isoformat() + 'Z',
                'duration_seconds': 3600 + (i * 10)
            })
            
        # Test scoring performance
        start_time = time.time()
        
        scored = scorer.score_results(
            results,
            episode_title="Episode 50: Test Title with Various Words",
            podcast_name="Test Podcast",
            episode_duration=3600,
            episode_date=datetime.utcnow() - timedelta(days=50)
        )
        
        elapsed = time.time() - start_time
        
        # Should score 100 results quickly (< 100ms)
        assert elapsed < 0.1
        assert len(scored) == 100
        
    @pytest.mark.asyncio
    async def test_api_retry_performance(self, matcher):
        """Test performance of API retry logic."""
        retry_count = 0
        
        def flaky_search(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            if retry_count < 3:
                raise Exception("Temporary failure")
            return []
            
        # Patch the retry decorator to use shorter delays
        with patch('src.youtube_api_client.wait_exponential',
                   return_value=lambda retry_state: 0.01):  # 10ms delays
            matcher.api_client.search_videos = Mock(side_effect=flaky_search)
            
            start_time = time.time()
            result = await matcher.match_episode("Test", "Episode 1")
            elapsed = time.time() - start_time
            
            # Should retry quickly
            assert retry_count >= 3
            assert elapsed < 0.5  # Should complete quickly with short delays
            
    def test_channel_learning_performance(self, matcher):
        """Test performance of channel learning with many podcasts."""
        # Learn many channel associations
        start_time = time.time()
        
        for i in range(100):
            matcher._learn_channel_association(
                podcast_name=f"Podcast_{i}",
                channel_id=f"channel_{i}",
                channel_title=f"Channel {i}"
            )
            
        learn_elapsed = time.time() - start_time
        
        # Should learn 100 associations quickly
        assert learn_elapsed < 1.0
        assert len(matcher.channel_associations) == 100
        
        # Test lookup performance
        start_time = time.time()
        
        for i in range(1000):
            channels = matcher.channel_associations.get(f"Podcast_{i % 100}")
            
        lookup_elapsed = time.time() - start_time
        
        # Lookups should be very fast
        assert lookup_elapsed < 0.01