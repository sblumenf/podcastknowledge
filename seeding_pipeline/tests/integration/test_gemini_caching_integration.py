"""Integration tests for Gemini caching implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

from src.services import LLMServiceFactory, LLMServiceType, CacheManager
from src.services.llm_gemini_direct import GeminiDirectService
from src.services.cached_prompt_service import CachedPromptService
from src.extraction.cached_extraction import CachedExtractionService, CachedExtractionConfig
from src.core.interfaces import TranscriptSegment
from src.utils.key_rotation_manager import KeyRotationManager


class TestGeminiCachingIntegration:
    """Integration tests for the complete caching pipeline."""
    
    @pytest.fixture
    def mock_key_manager(self):
        """Mock key rotation manager."""
        manager = Mock(spec=KeyRotationManager)
        manager.get_next_key.return_value = ("test-api-key", 0)
        manager.mark_key_success = Mock()
        manager.mark_key_failure = Mock()
        manager.update_key_usage = Mock()
        manager.get_status_summary.return_value = {'total_keys': 1}
        return manager
        
    @pytest.fixture
    def test_transcript(self):
        """Generate test transcript data."""
        transcript = "This is a test podcast transcript. " * 500  # ~10K chars
        segments = []
        
        for i in range(10):
            segments.append(TranscriptSegment(
                text=f"Segment {i}: This is test content with entities like AI and machine learning.",
                start_time=i * 30.0,
                end_time=(i + 1) * 30.0,
                speaker='Host',
                word_count=15
            ))
            
        return transcript, segments
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_service_factory_creates_all_types(self, mock_genai, mock_key_manager):
        """Test that factory can create all service types."""
        # Mock client
        mock_client = Mock()
        mock_genai.Client.return_value = mock_client
        
        # Test Gemini Direct service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_DIRECT
        )
        assert isinstance(service, GeminiDirectService)
        
        # Test Gemini Cached service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        assert isinstance(service, GeminiDirectService)
        assert hasattr(service, '_cache_manager')
        assert hasattr(service, '_cached_prompt_service')
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_episode_caching_flow(self, mock_genai, mock_key_manager, test_transcript):
        """Test complete episode caching flow."""
        transcript, segments = test_transcript
        
        # Mock Gemini client
        mock_cached_content = Mock()
        mock_cached_content.name = "cache-episode-123"
        
        mock_client = Mock()
        mock_client.caches.create.return_value = mock_cached_content
        mock_client.models.generate_content.return_value = Mock(
            text='[{"name": "AI", "type": "technology"}]'
        )
        mock_genai.Client.return_value = mock_client
        
        # Create cached service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        
        # Create extraction service
        extraction_service = CachedExtractionService(
            llm_service=service,
            cache_manager=service._cache_manager,
            config=CachedExtractionConfig()
        )
        
        # Extract from episode
        results = extraction_service.extract_from_episode(
            episode_id="test-123",
            transcript=transcript,
            segments=segments
        )
        
        # Verify caching was attempted
        assert mock_client.caches.create.called
        
        # Verify results
        assert 'entities' in results
        assert 'metadata' in results
        assert results['metadata']['episode_id'] == "test-123"
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_prompt_template_caching(self, mock_genai, mock_key_manager):
        """Test prompt template caching functionality."""
        # Mock client
        mock_client = Mock()
        mock_cached_prompt = Mock()
        mock_cached_prompt.name = "cache-prompt-entity"
        mock_client.caches.create.return_value = mock_cached_prompt
        mock_genai.Client.return_value = mock_client
        
        # Create service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        
        # Verify prompt caches were warmed
        cached_prompt_service = service._cached_prompt_service
        assert cached_prompt_service is not None
        
        # Check that caching was attempted
        assert mock_client.caches.create.call_count > 0
        
    def test_cache_manager_integration(self, mock_key_manager):
        """Test cache manager tracks caches correctly."""
        cache_manager = CacheManager(default_ttl=3600)
        
        # Register episode cache
        cache_info = cache_manager.register_episode_cache(
            episode_id="ep-123",
            cache_name="cache-123",
            content="Test transcript content",
            ttl=3600
        )
        
        assert cache_info.episode_id == "ep-123"
        assert cache_info.cache_name == "cache-123"
        
        # Retrieve cache
        cache_name = cache_manager.get_episode_cache("ep-123")
        assert cache_name == "cache-123"
        
        # Check stats
        stats = cache_manager.get_cache_stats()
        assert stats['hits'] == 1
        assert stats['active_episode_caches'] == 1
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_cost_savings_calculation(self, mock_genai, mock_key_manager, test_transcript):
        """Test that cost savings are calculated correctly."""
        transcript, segments = test_transcript
        
        # Mock responses
        mock_client = Mock()
        mock_client.caches.create.return_value = Mock(name="cache-123")
        mock_client.models.generate_content.return_value = Mock(text="[]")
        mock_genai.Client.return_value = mock_client
        
        # Create service with caching
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        
        cache_manager = service._cache_manager
        
        # Register cache and simulate usage
        cache_manager.register_episode_cache("ep-123", "cache-123", transcript)
        
        # Simulate cache hits
        for _ in range(5):
            cache_manager.get_episode_cache("ep-123")
            
        # Calculate savings
        savings = cache_manager.estimate_cost_savings()
        
        assert savings['cache_uses'] == 5
        assert savings['total_cached_tokens'] > 0
        assert savings['estimated_savings_usd'] > 0
        assert savings['savings_percentage'] == 0.75
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_fallback_to_non_cached(self, mock_genai, mock_key_manager):
        """Test fallback when caching fails."""
        # Mock client that fails cache creation
        mock_client = Mock()
        mock_client.caches.create.side_effect = Exception("Cache creation failed")
        mock_client.models.generate_content.return_value = Mock(
            text='[{"name": "Fallback", "type": "test"}]'
        )
        mock_genai.Client.return_value = mock_client
        
        # Create service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        
        # Should still work without caching
        response = service.complete("Test prompt")
        assert "Fallback" in response
        
    def test_service_info(self):
        """Test service information retrieval."""
        # Get info for each service type
        direct_info = LLMServiceFactory.get_service_info(LLMServiceType.GEMINI_DIRECT)
        assert direct_info['name'] == 'Gemini Direct Service'
        assert 'Context caching' in direct_info['features']
        
        cached_info = LLMServiceFactory.get_service_info(LLMServiceType.GEMINI_CACHED)
        assert cached_info['name'] == 'Gemini Cached Service'
        assert 'Cost optimization' in cached_info['features']
        
    @patch('src.services.llm_gemini_direct.genai')
    def test_batch_extraction_with_caching(self, mock_genai, mock_key_manager, test_transcript):
        """Test batch extraction leverages caching effectively."""
        transcript, segments = test_transcript
        
        # Mock responses
        mock_client = Mock()
        mock_client.caches.create.return_value = Mock(name="cache-batch-123")
        
        # Mock different responses for entities and insights
        response_count = 0
        def mock_generate(*args, **kwargs):
            nonlocal response_count
            response_count += 1
            if response_count == 1:
                return Mock(text='[{"name": "AI", "type": "technology"}]')
            else:
                return Mock(text='[{"content": "AI is transformative", "type": "key_point"}]')
                
        mock_client.models.generate_content.side_effect = mock_generate
        mock_genai.Client.return_value = mock_client
        
        # Create service
        service = LLMServiceFactory.create_service(
            key_rotation_manager=mock_key_manager,
            service_type=LLMServiceType.GEMINI_CACHED
        )
        
        extraction_service = CachedExtractionService(
            llm_service=service,
            cache_manager=service._cache_manager,
            config=CachedExtractionConfig(batch_size=5)
        )
        
        # Process episode
        results = extraction_service.extract_from_episode(
            episode_id="batch-test",
            transcript=transcript,
            segments=segments
        )
        
        # Verify batching worked
        assert len(results['entities']) > 0
        assert results['metadata']['segment_count'] == len(segments)
        
        # Verify caching stats show improvement
        stats = extraction_service.get_extraction_stats()
        assert 'cache_stats' in stats
        assert stats['cache_stats']['creates'] > 0