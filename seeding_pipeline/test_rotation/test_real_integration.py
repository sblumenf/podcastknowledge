#!/usr/bin/env python3
"""Test real integration with actual API calls (requires valid API keys)."""

import os
import sys
import json
import time
from pathlib import Path
import tempfile

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.key_rotation_manager import KeyRotationManager, create_key_rotation_manager
from src.services.llm import LLMService
from src.services.embeddings_gemini import GeminiEmbeddingsService
from src.core.exceptions import RateLimitError, ProviderError


def test_real_llm_calls():
    """Test real LLM API calls with rotation."""
    print("\n=== Testing Real LLM API Calls ===")
    
    # Create rotation manager from environment
    rotation_manager = create_key_rotation_manager()
    if not rotation_manager:
        print("⚠️  No API keys found in environment, skipping real API tests")
        return
    
    print(f"Found {len(rotation_manager.api_keys)} API key(s)")
    
    # Create LLM service
    llm_service = LLMService(
        key_rotation_manager=rotation_manager,
        model_name='gemini-2.5-flash',
        temperature=0.7,
        enable_cache=True
    )
    
    # Test prompts
    test_prompts = [
        "What is 2+2? Answer in one word.",
        "Name the capital of France in one word.",
        "What color is the sky? One word answer."
    ]
    
    try:
        for i, prompt in enumerate(test_prompts):
            print(f"\nTest {i+1}: {prompt}")
            start_time = time.time()
            
            response = llm_service.complete(prompt)
            elapsed = time.time() - start_time
            
            print(f"Response: {response}")
            print(f"Time: {elapsed:.2f}s")
            
            # Small delay to avoid hitting rate limits
            time.sleep(1)
        
        # Test cache hit
        print("\nTesting cache...")
        start_time = time.time()
        cached_response = llm_service.complete(test_prompts[0])
        elapsed = time.time() - start_time
        print(f"Cached response: {cached_response}")
        print(f"Cache time: {elapsed:.2f}s (should be near 0)")
        
        # Check status
        status = rotation_manager.get_status_summary()
        print(f"\nRotation status: {json.dumps(status, indent=2)}")
        
        print("✓ Real LLM calls successful")
        
    except RateLimitError as e:
        print(f"⚠️  Rate limit hit (expected with free tier): {e}")
    except Exception as e:
        print(f"❌ Error during real LLM calls: {e}")
        import traceback
        traceback.print_exc()


def test_real_embeddings():
    """Test real embeddings API calls with rotation."""
    print("\n=== Testing Real Embeddings API Calls ===")
    
    # Create rotation manager from environment
    rotation_manager = create_key_rotation_manager()
    if not rotation_manager:
        print("⚠️  No API keys found in environment, skipping real API tests")
        return
    
    # Create embeddings service
    embeddings_service = GeminiEmbeddingsService(
        key_rotation_manager=rotation_manager,
        model_name='models/text-embedding-004'
    )
    
    # Test texts
    test_texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language."
    ]
    
    try:
        # Test single embeddings
        print("\nTesting single embeddings...")
        for i, text in enumerate(test_texts[:2]):
            print(f"\nEmbedding {i+1}: {text[:50]}...")
            start_time = time.time()
            
            embedding = embeddings_service.generate_embedding(text)
            elapsed = time.time() - start_time
            
            print(f"Embedding dimension: {len(embedding)}")
            print(f"First 5 values: {embedding[:5]}")
            print(f"Time: {elapsed:.2f}s")
            
            # Small delay
            time.sleep(0.5)
        
        # Test batch embeddings
        print("\nTesting batch embeddings...")
        start_time = time.time()
        
        batch_embeddings = embeddings_service.generate_embeddings(test_texts)
        elapsed = time.time() - start_time
        
        print(f"Batch size: {len(batch_embeddings)}")
        print(f"Batch time: {elapsed:.2f}s")
        
        for i, emb in enumerate(batch_embeddings):
            print(f"  Text {i+1}: dimension={len(emb)}, first value={emb[0]:.4f}")
        
        # Check quota usage
        quota_summary = rotation_manager.get_quota_summary()
        print(f"\nQuota usage: {json.dumps(quota_summary, indent=2)}")
        
        print("✓ Real embeddings calls successful")
        
    except RateLimitError as e:
        print(f"⚠️  Rate limit hit: {e}")
    except Exception as e:
        print(f"❌ Error during real embeddings calls: {e}")
        import traceback
        traceback.print_exc()


def test_rate_limit_handling():
    """Test handling of real rate limits."""
    print("\n=== Testing Rate Limit Handling ===")
    
    rotation_manager = create_key_rotation_manager()
    if not rotation_manager:
        print("⚠️  No API keys found in environment, skipping test")
        return
    
    if len(rotation_manager.api_keys) < 2:
        print("⚠️  Need at least 2 API keys for rate limit testing")
        return
    
    llm_service = LLMService(
        key_rotation_manager=rotation_manager,
        model_name='gemini-2.5-flash',
        enable_cache=False  # Disable cache for this test
    )
    
    print(f"Testing with {len(rotation_manager.api_keys)} keys...")
    
    # Try to hit rate limits with rapid requests
    rate_limit_hit = False
    successful_after_limit = False
    
    try:
        for i in range(20):  # Try 20 rapid requests
            prompt = f"Count to {i}. Answer with just the number."
            
            try:
                response = llm_service.complete(prompt)
                print(f"Request {i+1}: Success - {response.strip()}")
                
                if rate_limit_hit:
                    successful_after_limit = True
                    print("✓ Successfully recovered after rate limit!")
                    break
                    
            except RateLimitError as e:
                print(f"Request {i+1}: Rate limit hit - {e}")
                rate_limit_hit = True
                
                # Check if all keys are exhausted
                status = rotation_manager.get_status_summary()
                if status['available_keys'] == 0:
                    print("All keys exhausted")
                    break
            
            # No delay - trying to hit rate limits
        
        if rate_limit_hit and successful_after_limit:
            print("✓ Rate limit handling working correctly")
        elif not rate_limit_hit:
            print("⚠️  Rate limits not hit (keys have high quota)")
        else:
            print("⚠️  Could not recover after rate limit")
            
    except Exception as e:
        print(f"❌ Error during rate limit test: {e}")


def test_model_switching():
    """Test switching between different models."""
    print("\n=== Testing Model Switching ===")
    
    rotation_manager = create_key_rotation_manager()
    if not rotation_manager:
        print("⚠️  No API keys found in environment, skipping test")
        return
    
    # Test different models
    models = ['gemini-2.5-flash', 'gemini-2.0-flash']
    
    for model in models:
        print(f"\nTesting model: {model}")
        
        try:
            llm_service = LLMService(
                key_rotation_manager=rotation_manager,
                model_name=model,
                enable_cache=False
            )
            
            response = llm_service.complete("Say 'hello' in one word.")
            print(f"Response from {model}: {response.strip()}")
            
            # Check model-specific usage
            status = rotation_manager.get_status_summary()
            for key_state in status['key_states']:
                if key_state['model_usage'] and model in key_state['model_usage']:
                    usage = key_state['model_usage'][model]
                    print(f"  {key_state['name']}: {usage['requests']} requests")
            
            time.sleep(1)  # Small delay between models
            
        except Exception as e:
            print(f"  Error with {model}: {e}")


def test_checkpoint_integration():
    """Test integration with checkpoint system."""
    print("\n=== Testing Checkpoint Integration ===")
    
    rotation_manager = create_key_rotation_manager()
    if not rotation_manager:
        print("⚠️  No API keys found in environment, skipping test")
        return
    
    # Check state persistence location
    from src.utils.rotation_state_manager import RotationStateManager
    
    state_dir = RotationStateManager.get_state_directory()
    print(f"State directory: {state_dir}")
    
    # Ensure persistence is ready
    if RotationStateManager.ensure_state_persistence():
        print("✓ State persistence configured")
    else:
        print("❌ State persistence configuration failed")
        return
    
    # Get metrics
    metrics = RotationStateManager.get_rotation_metrics()
    print(f"Rotation metrics: {json.dumps(metrics, indent=2)}")
    
    # Test cleanup of old states
    cleaned = RotationStateManager.cleanup_old_states(days=30)
    print(f"Cleaned up {cleaned} old state files")
    
    print("✓ Checkpoint integration working")


def main():
    """Run all real integration tests."""
    print("Starting Real Integration Tests")
    print("=" * 50)
    print("Note: These tests require valid API keys in environment variables")
    print("Set GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc. or GOOGLE_API_KEY")
    
    try:
        test_real_llm_calls()
        test_real_embeddings()
        test_rate_limit_handling()
        test_model_switching()
        test_checkpoint_integration()
        
        print("\n" + "=" * 50)
        print("✅ Real integration tests completed!")
        print("\nNote: Some tests may skip or show warnings if:")
        print("- No API keys are configured")
        print("- Rate limits are hit (normal for free tier)")
        print("- Only one API key is available")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()