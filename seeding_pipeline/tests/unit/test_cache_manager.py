"""Unit tests for cache manager."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.services.cache_manager import CacheManager, CachedContent


class TestCacheManager:
    """Test suite for CacheManager."""
    
    @pytest.fixture
    def manager(self):
        """Create cache manager instance."""
        return CacheManager(default_ttl=3600)
        
    def test_initialization(self):
        """Test cache manager initialization."""
        manager = CacheManager(default_ttl=7200)
        
        assert manager.default_ttl == 7200
        assert len(manager._episode_caches) == 0
        assert len(manager._prompt_caches) == 0
        assert manager._cache_stats['hits'] == 0
        assert manager._cache_stats['misses'] == 0
        
    def test_content_hash(self, manager):
        """Test content hash generation."""
        hash1 = manager.get_content_hash("test content")
        hash2 = manager.get_content_hash("test content")
        hash3 = manager.get_content_hash("different content")
        
        assert hash1 == hash2  # Same content produces same hash
        assert hash1 != hash3  # Different content produces different hash
        assert len(hash1) == 16  # Hash is truncated to 16 chars
        
    def test_token_estimation(self, manager):
        """Test token count estimation."""
        # Roughly 1 token per 4 characters
        assert manager.estimate_tokens("test") == 1
        assert manager.estimate_tokens("a" * 100) == 25
        assert manager.estimate_tokens("a" * 4000) == 1000
        
    def test_should_cache_transcript_size(self, manager):
        """Test transcript caching decisions based on size."""
        # Too small (< 1024 tokens)
        small_transcript = "a" * 1000  # ~250 tokens
        assert not manager.should_cache_transcript(small_transcript, "ep1")
        
        # Medium size (1024-5000 tokens)
        medium_transcript = "a" * 6000  # ~1500 tokens
        assert manager.should_cache_transcript(medium_transcript, "ep2")
        
        # Large size (> 5000 tokens)
        large_transcript = "a" * 25000  # ~6250 tokens
        assert manager.should_cache_transcript(large_transcript, "ep3")
        
    def test_should_cache_already_cached(self, manager):
        """Test that already cached episodes are not re-cached."""
        transcript = "a" * 10000  # Large enough to cache
        
        # First check - should cache
        assert manager.should_cache_transcript(transcript, "ep1")
        
        # Register the cache
        manager.register_episode_cache("ep1", "cache-123", transcript)
        
        # Second check - should not cache (already cached)
        assert not manager.should_cache_transcript(transcript, "ep1")
        
    def test_register_episode_cache(self, manager):
        """Test registering episode cache."""
        content = "test transcript content"
        cache = manager.register_episode_cache(
            episode_id="ep123",
            cache_name="cache-abc",
            content=content,
            ttl=7200
        )
        
        assert cache.episode_id == "ep123"
        assert cache.cache_name == "cache-abc"
        assert cache.ttl_seconds == 7200
        assert cache.token_count == manager.estimate_tokens(content)
        assert cache.content_hash == manager.get_content_hash(content)
        assert not cache.is_expired
        
        # Check internal state
        assert "ep123" in manager._episode_caches
        assert manager._cache_stats['creates'] == 1
        
    def test_get_episode_cache_hit(self, manager):
        """Test cache hit for episode."""
        # Register cache
        manager.register_episode_cache("ep123", "cache-abc", "content")
        
        # Get cache - should hit
        cache_name = manager.get_episode_cache("ep123")
        
        assert cache_name == "cache-abc"
        assert manager._cache_stats['hits'] == 1
        assert manager._cache_stats['misses'] == 0
        
    def test_get_episode_cache_miss(self, manager):
        """Test cache miss for episode."""
        cache_name = manager.get_episode_cache("nonexistent")
        
        assert cache_name is None
        assert manager._cache_stats['hits'] == 0
        assert manager._cache_stats['misses'] == 1
        
    def test_get_episode_cache_expired(self, manager):
        """Test expired cache handling."""
        # Register cache
        cache = manager.register_episode_cache("ep123", "cache-abc", "content", ttl=1)
        
        # Manually expire the cache
        cache.created_at = datetime.now() - timedelta(seconds=2)
        
        # Get cache - should miss due to expiry
        cache_name = manager.get_episode_cache("ep123")
        
        assert cache_name is None
        assert manager._cache_stats['misses'] == 1
        assert manager._cache_stats['evictions'] == 1
        assert "ep123" not in manager._episode_caches
        
    def test_register_prompt_cache(self, manager):
        """Test registering prompt template cache."""
        content = "prompt template content"
        cache = manager.register_prompt_cache(
            template_name="entity_extraction",
            cache_name="cache-prompt-123",
            content=content,
            version="2.0"
        )
        
        assert cache.cache_name == "cache-prompt-123"
        assert cache.episode_id == "entity_extraction_v2.0"  # Reuses episode_id field
        assert cache.ttl_seconds == 86400  # 24 hours
        assert cache.token_count == manager.estimate_tokens(content)
        
        # Check internal state
        assert "entity_extraction_v2.0" in manager._prompt_caches
        
    def test_get_prompt_cache(self, manager):
        """Test getting prompt cache."""
        # Register cache
        manager.register_prompt_cache(
            "entity_extraction", "cache-prompt-123", "content", "2.0"
        )
        
        # Get with matching version
        cache_name = manager.get_prompt_cache("entity_extraction", "2.0")
        assert cache_name == "cache-prompt-123"
        
        # Get with different version - should miss
        cache_name = manager.get_prompt_cache("entity_extraction", "1.0")
        assert cache_name is None
        
    def test_cache_stats(self, manager):
        """Test cache statistics."""
        # Create some activity
        manager.register_episode_cache("ep1", "cache1", "content1")
        manager.register_episode_cache("ep2", "cache2", "content2")
        manager.get_episode_cache("ep1")  # Hit
        manager.get_episode_cache("ep3")  # Miss
        
        stats = manager.get_cache_stats()
        
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5
        assert stats['creates'] == 2
        assert stats['active_episode_caches'] == 2
        assert stats['total_cached_tokens'] > 0
        
    def test_estimate_cost_savings(self, manager):
        """Test cost savings estimation."""
        # Register some caches
        manager.register_episode_cache("ep1", "cache1", "a" * 10000)  # ~2500 tokens
        manager.register_episode_cache("ep2", "cache2", "a" * 20000)  # ~5000 tokens
        
        # Simulate cache hits
        manager.get_episode_cache("ep1")  # Hit
        manager.get_episode_cache("ep1")  # Hit
        manager.get_episode_cache("ep2")  # Hit
        
        savings = manager.estimate_cost_savings()
        
        assert savings['total_cached_tokens'] == 7500
        assert savings['cache_uses'] == 3
        assert savings['tokens_saved'] > 0
        assert savings['estimated_savings_usd'] > 0
        assert savings['savings_percentage'] == 0.75
        
    def test_cleanup_expired(self, manager):
        """Test cleanup of expired caches."""
        # Create caches with different expiry
        cache1 = manager.register_episode_cache("ep1", "cache1", "content", ttl=1)
        cache2 = manager.register_episode_cache("ep2", "cache2", "content", ttl=3600)
        prompt_cache = manager.register_prompt_cache("prompt1", "cache3", "content")
        
        # Expire some caches
        cache1.created_at = datetime.now() - timedelta(seconds=2)
        prompt_cache.created_at = datetime.now() - timedelta(days=2)
        
        # Run cleanup
        manager.cleanup_expired()
        
        # Check results
        assert "ep1" not in manager._episode_caches  # Expired
        assert "ep2" in manager._episode_caches  # Still valid
        assert "prompt1_v1.0" not in manager._prompt_caches  # Expired
        assert manager._cache_stats['evictions'] == 2
        
    @patch('src.services.cache_manager.logger')
    def test_warm_prompt_caches(self, mock_logger, manager):
        """Test warming prompt caches on startup."""
        # Mock LLM service
        mock_llm = Mock()
        mock_llm.create_cached_content.side_effect = [
            "cache-prompt-1",
            "cache-prompt-2",
            None  # Failure case
        ]
        
        # Prompt templates
        templates = {
            "entity_extraction": "a" * 5000,  # Large enough
            "insight_extraction": "a" * 6000,  # Large enough
            "small_prompt": "a" * 100,  # Too small
            "failed_prompt": "a" * 5000  # Will fail
        }
        
        # Warm caches
        cached = manager.warm_prompt_caches(mock_llm, templates)
        
        # Check results
        assert len(cached) == 2
        assert "entity_extraction" in cached
        assert "insight_extraction" in cached
        assert "small_prompt" not in cached  # Too small
        assert "failed_prompt" not in cached  # Failed
        
        # Verify service was called correctly
        assert mock_llm.create_cached_content.call_count == 3  # Not called for small prompt
        
    def test_cached_content_expiry(self):
        """Test CachedContent expiry check."""
        # Not expired
        cache = CachedContent(
            cache_name="test",
            episode_id="ep1",
            content_hash="hash",
            created_at=datetime.now(),
            ttl_seconds=3600,
            token_count=1000
        )
        assert not cache.is_expired
        
        # Expired
        cache.created_at = datetime.now() - timedelta(seconds=3700)
        assert cache.is_expired