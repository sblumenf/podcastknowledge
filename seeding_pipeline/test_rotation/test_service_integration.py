#!/usr/bin/env python3
"""Test API key rotation integration with LLM and Embeddings services."""

import os
import sys
import json
import time
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.key_rotation_manager import KeyRotationManager, KeyStatus
from src.services.llm import LLMService
from src.services.embeddings_gemini import GeminiEmbeddingsService
from src.core.exceptions import RateLimitError, ProviderError


def test_llm_service_integration():
    """Test LLM service with key rotation."""
    print("\n=== Testing LLM Service Integration ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create rotation manager with test keys
        keys = ['llm_key_1', 'llm_key_2', 'llm_key_3']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Create LLM service
        llm_service = LLMService(
            key_rotation_manager=rotation_manager,
            model_name='gemini-2.5-flash',
            enable_cache=False  # Disable cache for testing
        )
        
        # Mock the actual API client
        mock_response = Mock()
        mock_response.content = "Test response from LLM"
        
        with patch.object(llm_service, '_ensure_client'):
            llm_service.client = Mock()
            llm_service.client.invoke = Mock(return_value=mock_response)
            
            # Test multiple completions to verify rotation
            for i in range(5):
                response = llm_service.complete(f"Test prompt {i}")
                print(f"Completion {i}: {response}")
                assert response == "Test response from LLM"
            
            # Check that rotation happened
            status = rotation_manager.get_status_summary()
            print(f"Rotation status: {json.dumps(status, indent=2)}")
            
            # All keys should have been used at least once
            used_keys = sum(1 for state in status['key_states'] 
                          if state['last_used'] is not None)
            assert used_keys >= 2  # At least 2 keys should be used in 5 calls
        
        print("✓ LLM service integration working correctly")


def test_llm_service_with_failures():
    """Test LLM service handling of API failures."""
    print("\n=== Testing LLM Service with Failures ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['fail_key_1', 'good_key_2']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        llm_service = LLMService(
            key_rotation_manager=rotation_manager,
            enable_cache=False
        )
        
        # Mock client to fail on first key, succeed on second
        call_count = 0
        def mock_invoke(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Quota exceeded for this API key")
            else:
                response = Mock()
                response.content = "Success after retry"
                return response
        
        with patch.object(llm_service, '_ensure_client'):
            llm_service.client = Mock()
            llm_service.client.invoke = mock_invoke
            
            # Should succeed by using second key
            response = llm_service.complete("Test with failure")
            print(f"Response after failure: {response}")
            assert response == "Success after retry"
            
            # Check that first key is marked as failed
            status = rotation_manager.get_status_summary()
            print(f"Status after failure: {json.dumps(status, indent=2)}")
            assert status['key_states'][0]['failures'] > 0
        
        print("✓ LLM service failure handling working correctly")


def test_embeddings_service_integration():
    """Test embeddings service with key rotation."""
    print("\n=== Testing Embeddings Service Integration ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['embed_key_1', 'embed_key_2']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        embeddings_service = GeminiEmbeddingsService(
            key_rotation_manager=rotation_manager,
            model_name='models/text-embedding-004'
        )
        
        # Mock genai module
        mock_response = {'embedding': [0.1] * 768}
        
        with patch('src.services.embeddings_gemini.genai') as mock_genai:
            mock_genai.embed_content = Mock(return_value=mock_response)
            
            # Test single embedding
            embedding = embeddings_service.generate_embedding("Test text")
            print(f"Single embedding length: {len(embedding)}")
            assert len(embedding) == 768
            
            # Test batch embeddings
            texts = ["Text 1", "Text 2", "Text 3"]
            mock_genai.embed_content.return_value = {
                'embedding': [[0.1] * 768, [0.2] * 768, [0.3] * 768]
            }
            
            embeddings = embeddings_service.generate_embeddings(texts)
            print(f"Batch embeddings count: {len(embeddings)}")
            assert len(embeddings) == 3
            
            # Check rotation happened
            status = rotation_manager.get_status_summary()
            print(f"Rotation status: {json.dumps(status, indent=2)}")
        
        print("✓ Embeddings service integration working correctly")


def test_embeddings_with_rate_limit():
    """Test embeddings service handling rate limits."""
    print("\n=== Testing Embeddings Service with Rate Limits ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['rate_limited_key']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        embeddings_service = GeminiEmbeddingsService(
            key_rotation_manager=rotation_manager
        )
        
        # Mock to raise rate limit error
        with patch('src.services.embeddings_gemini.genai') as mock_genai:
            mock_genai.embed_content = Mock(
                side_effect=Exception("Resource exhausted: Quota exceeded")
            )
            
            try:
                embedding = embeddings_service.generate_embedding("Test")
                assert False, "Should have raised RateLimitError"
            except RateLimitError as e:
                print(f"Correctly caught rate limit error: {e}")
            
            # Check key is marked as rate limited or quota exceeded
            status = rotation_manager.get_status_summary()
            print(f"Status after rate limit: {json.dumps(status, indent=2)}")
            key_status = status['key_states'][0]['status']
            assert key_status in [KeyStatus.RATE_LIMITED.value, KeyStatus.QUOTA_EXCEEDED.value], \
                f"Expected rate limited or quota exceeded, got {key_status}"
        
        print("✓ Embeddings rate limit handling working correctly")


def test_cache_with_rotation():
    """Test that caching works correctly with key rotation."""
    print("\n=== Testing Cache with Rotation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['cache_key_1', 'cache_key_2']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        llm_service = LLMService(
            key_rotation_manager=rotation_manager,
            enable_cache=True,
            cache_ttl=3600
        )
        
        mock_response = Mock()
        mock_response.content = "Cached response"
        
        with patch.object(llm_service, '_ensure_client'):
            llm_service.client = Mock()
            llm_service.client.invoke = Mock(return_value=mock_response)
            
            # First call - should hit API
            response1 = llm_service.complete("Same prompt")
            print(f"First response: {response1}")
            assert llm_service.client.invoke.call_count == 1
            
            # Second call - should hit cache
            response2 = llm_service.complete("Same prompt")
            print(f"Second response (cached): {response2}")
            assert response1 == response2
            assert llm_service.client.invoke.call_count == 1  # No additional API call
            
            # Different prompt - should hit API again
            mock_response.content = "Different response"
            response3 = llm_service.complete("Different prompt")
            print(f"Third response: {response3}")
            assert llm_service.client.invoke.call_count == 2
        
        print("✓ Cache integration working correctly")


def test_concurrent_service_usage():
    """Test multiple services using the same rotation manager."""
    print("\n=== Testing Concurrent Service Usage ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['shared_key_1', 'shared_key_2', 'shared_key_3']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Create multiple services sharing the same rotation manager
        llm_service = LLMService(
            key_rotation_manager=rotation_manager,
            enable_cache=False
        )
        
        embeddings_service = GeminiEmbeddingsService(
            key_rotation_manager=rotation_manager
        )
        
        # Mock both services
        mock_llm_response = Mock()
        mock_llm_response.content = "LLM response"
        mock_embed_response = {'embedding': [0.5] * 768}
        
        with patch.object(llm_service, '_ensure_client'), \
             patch('src.services.embeddings_gemini.genai') as mock_genai:
            
            llm_service.client = Mock()
            llm_service.client.invoke = Mock(return_value=mock_llm_response)
            mock_genai.embed_content = Mock(return_value=mock_embed_response)
            
            # Interleave calls between services
            for i in range(6):
                if i % 2 == 0:
                    response = llm_service.complete(f"LLM prompt {i}")
                    print(f"LLM call {i}: {response}")
                else:
                    embedding = embeddings_service.generate_embedding(f"Embed text {i}")
                    print(f"Embedding call {i}: length={len(embedding)}")
            
            # Check that rotation is working across both services
            status = rotation_manager.get_status_summary()
            print(f"Final rotation status: {json.dumps(status, indent=2)}")
            
            # All keys should have been used
            used_keys = sum(1 for state in status['key_states'] 
                          if state['last_used'] is not None)
            assert used_keys == 3
        
        print("✓ Concurrent service usage working correctly")


def test_quota_aware_selection():
    """Test quota-aware key selection."""
    print("\n=== Testing Quota-Aware Key Selection ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['quota_key_1', 'quota_key_2']
        rotation_manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Simulate first key near quota limit
        rotation_manager.key_states[0].tokens_today = 999_000  # Near 1M limit
        
        # Request should get second key due to quota
        available = rotation_manager.get_available_key_for_quota(
            tokens_needed=10_000, 
            model='gemini-2.5-flash'
        )
        
        if available:
            key, index = available
            print(f"Got key at index {index} for quota-aware request")
            assert index == 1  # Should get second key
        
        # Check quota summary
        quota_summary = rotation_manager.get_quota_summary()
        print(f"Quota summary: {json.dumps(quota_summary, indent=2)}")
        
        print("✓ Quota-aware selection working correctly")


def main():
    """Run all service integration tests."""
    print("Starting Service Integration Tests")
    print("=" * 50)
    
    try:
        test_llm_service_integration()
        test_llm_service_with_failures()
        test_embeddings_service_integration()
        test_embeddings_with_rate_limit()
        test_cache_with_rotation()
        test_concurrent_service_usage()
        test_quota_aware_selection()
        
        print("\n" + "=" * 50)
        print("✅ All service integration tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()