#!/usr/bin/env python3
"""Stress test the API key rotation system."""

import os
import sys
import json
import time
import threading
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import random

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.key_rotation_manager import KeyRotationManager, KeyStatus
from src.utils.rotation_state_manager import RotationStateManager


def simulate_api_call(manager: KeyRotationManager, call_id: int, 
                     fail_probability: float = 0.1) -> dict:
    """Simulate an API call with possible failure."""
    try:
        # Random model selection
        models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.5-pro']
        model = random.choice(models)
        
        # Get API key
        api_key, key_index = manager.get_next_key(model)
        
        # Simulate processing time
        time.sleep(random.uniform(0.01, 0.05))
        
        # Simulate possible failure
        if random.random() < fail_probability:
            error_messages = [
                "Quota exceeded for this API key",
                "Rate limit reached",
                "Internal server error",
                "Resource exhausted"
            ]
            error = random.choice(error_messages)
            manager.mark_key_failure(key_index, error)
            return {
                'call_id': call_id,
                'success': False,
                'key_index': key_index,
                'error': error,
                'model': model
            }
        else:
            # Success
            tokens_used = random.randint(100, 5000)
            manager.mark_key_success(key_index)
            manager.update_key_usage(key_index, tokens_used, model)
            return {
                'call_id': call_id,
                'success': True,
                'key_index': key_index,
                'tokens_used': tokens_used,
                'model': model
            }
    except Exception as e:
        return {
            'call_id': call_id,
            'success': False,
            'error': str(e),
            'model': model if 'model' in locals() else 'unknown'
        }


def test_concurrent_rotation():
    """Test concurrent access to rotation manager."""
    print("\n=== Testing Concurrent Rotation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create manager with 5 keys
        keys = [f'concurrent_key_{i}' for i in range(5)]
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Run concurrent API calls
        num_calls = 100
        num_threads = 10
        results = []
        
        print(f"Running {num_calls} concurrent calls with {num_threads} threads...")
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_calls):
                future = executor.submit(simulate_api_call, manager, i, 0.2)
                futures.append(future)
            
            for future in as_completed(futures):
                results.append(future.result())
        
        elapsed = time.time() - start_time
        
        # Analyze results
        successful = sum(1 for r in results if r['success'])
        failed = sum(1 for r in results if not r['success'])
        
        print(f"\nCompleted in {elapsed:.2f} seconds")
        print(f"Successful calls: {successful}")
        print(f"Failed calls: {failed}")
        
        # Check rotation distribution
        key_usage = {}
        for result in results:
            if 'key_index' in result:
                key_index = result['key_index']
                key_usage[key_index] = key_usage.get(key_index, 0) + 1
        
        print("\nKey usage distribution:")
        for key_index, count in sorted(key_usage.items()):
            print(f"  Key {key_index}: {count} calls")
        
        # Verify relatively even distribution (within reasonable bounds)
        # With failures, distribution may be less even
        avg_usage = num_calls / len(keys)
        min_usage = min(key_usage.values()) if key_usage else 0
        max_usage = max(key_usage.values()) if key_usage else 0
        
        # Allow more variance due to failures
        assert min_usage >= avg_usage * 0.2, \
            f"Too low usage: {min_usage} vs avg {avg_usage}"
        assert max_usage <= avg_usage * 2.5, \
            f"Too high usage: {max_usage} vs avg {avg_usage}"
        
        # Check final status
        status = manager.get_status_summary()
        print(f"\nFinal status: {json.dumps(status, indent=2)}")
        
        print("✓ Concurrent rotation test passed")


def test_quota_exhaustion():
    """Test behavior when quotas are exhausted."""
    print("\n=== Testing Quota Exhaustion ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create manager with 2 keys
        keys = ['quota_test_1', 'quota_test_2']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Get rate limits for testing
        limits = manager.get_rate_limits_for_model('gemini-2.5-flash')
        
        # Simulate exhausting daily token quota on first key
        manager.key_states[0].tokens_today = limits['tpd'] - 100
        manager.key_states[0].requests_today = limits['rpd'] - 1
        
        print(f"Set key 0 near limits: {manager.key_states[0].tokens_today} tokens")
        
        # Try to get key with high token requirement
        available = manager.get_available_key_for_quota(
            tokens_needed=1000, 
            model='gemini-2.5-flash'
        )
        
        if available:
            key, index = available
            print(f"Got key {index} for high-token request")
            assert index == 1, "Should have selected second key"
        
        # Exhaust both keys
        for i in range(2):
            manager.key_states[i].requests_today = limits['rpd'] + 1
        
        # Try to get any key - should fail
        try:
            key, index = manager.get_next_key('gemini-2.5-flash')
            assert False, "Should have raised exception"
        except Exception as e:
            print(f"Correctly raised exception: {e}")
            assert "No API keys available" in str(e)
        
        print("✓ Quota exhaustion test passed")


def test_minute_rate_limits():
    """Test per-minute rate limit tracking."""
    print("\n=== Testing Minute Rate Limits ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['minute_test_key']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Get rate limits
        limits = manager.get_rate_limits_for_model('gemini-2.5-flash')
        rpm_limit = limits['rpm']
        
        print(f"RPM limit for gemini-2.5-flash: {rpm_limit}")
        
        # Simulate reaching minute limit
        state = manager.key_states[0]
        state.last_minute_reset = datetime.now(timezone.utc)
        state.requests_this_minute = rpm_limit
        
        # Key should not be usable
        assert not state.is_usable(limits), "Key should not be usable at RPM limit"
        
        # Simulate time passing (61 seconds)
        from datetime import timedelta
        state.last_minute_reset = datetime.now(timezone.utc) - timedelta(seconds=61)
        
        # Key should be usable again
        assert state.is_usable(limits), "Key should be usable after minute reset"
        
        print("✓ Minute rate limit test passed")


def test_daily_reset():
    """Test daily quota reset functionality."""
    print("\n=== Testing Daily Reset ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['daily_reset_key']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Set high usage
        state = manager.key_states[0]
        state.requests_today = 100
        state.tokens_today = 500000
        state.status = KeyStatus.QUOTA_EXCEEDED
        state.last_daily_reset = datetime.now(timezone.utc) - timedelta(days=1)
        
        print(f"Before reset: {state.requests_today} requests, status={state.status.value}")
        
        # Trigger daily reset
        manager._daily_reset()
        
        print(f"After reset: {state.requests_today} requests, status={state.status.value}")
        
        # Verify reset
        assert state.requests_today == 0
        assert state.tokens_today == 0
        assert state.status == KeyStatus.AVAILABLE
        assert state.model_usage == {}
        
        print("✓ Daily reset test passed")


def test_stress_with_failures():
    """Stress test with high failure rate."""
    print("\n=== Testing Stress with High Failures ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create manager with 10 keys
        keys = [f'stress_key_{i}' for i in range(10)]
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Run with 50% failure rate
        num_calls = 200
        results = []
        
        print(f"Running {num_calls} calls with 50% failure rate...")
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(num_calls):
                future = executor.submit(simulate_api_call, manager, i, 0.5)
                futures.append(future)
            
            for future in as_completed(futures):
                results.append(future.result())
        
        elapsed = time.time() - start_time
        
        # Analyze results
        successful = sum(1 for r in results if r['success'])
        failed = sum(1 for r in results if not r['success'])
        no_keys_errors = sum(1 for r in results 
                           if not r['success'] and 'No API keys available' in r.get('error', ''))
        
        print(f"\nCompleted in {elapsed:.2f} seconds")
        print(f"Successful calls: {successful}")
        print(f"Failed calls: {failed}")
        print(f"No keys available errors: {no_keys_errors}")
        
        # Check how many keys are still available
        status = manager.get_status_summary()
        available_keys = status['available_keys']
        print(f"Keys still available: {available_keys}/{len(keys)}")
        
        # Some keys should have failed
        failed_keys = sum(1 for state in status['key_states'] 
                         if state['status'] != KeyStatus.AVAILABLE.value)
        assert failed_keys > 0, "Some keys should have failed with 50% failure rate"
        
        print("✓ High failure stress test passed")


def test_model_specific_tracking():
    """Test model-specific usage tracking."""
    print("\n=== Testing Model-Specific Tracking ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['model_track_key']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Simulate usage with different models
        models_and_tokens = [
            ('gemini-2.5-flash', 1000),
            ('gemini-2.5-flash', 2000),
            ('gemini-2.0-flash', 3000),
            ('gemini-2.5-pro', 500),
            ('gemini-2.5-pro', 750)
        ]
        
        for model, tokens in models_and_tokens:
            key, index = manager.get_next_key(model)
            manager.mark_key_success(index)
            manager.update_key_usage(index, tokens, model)
        
        # Check model-specific usage
        state = manager.key_states[0]
        print(f"Model usage: {json.dumps(state.model_usage, indent=2)}")
        
        # Verify tracking
        assert state.model_usage['gemini-2.5-flash']['tokens'] == 3000
        assert state.model_usage['gemini-2.5-flash']['requests'] == 2
        assert state.model_usage['gemini-2.0-flash']['tokens'] == 3000
        assert state.model_usage['gemini-2.5-pro']['tokens'] == 1250
        
        print("✓ Model-specific tracking test passed")


def test_state_persistence_under_load():
    """Test state persistence under concurrent load."""
    print("\n=== Testing State Persistence Under Load ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_path = Path(temp_dir)
        keys = [f'persist_key_{i}' for i in range(5)]
        
        # Create first manager and generate load
        manager1 = KeyRotationManager(keys, state_path)
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(50):
                future = executor.submit(simulate_api_call, manager1, i, 0.3)
                futures.append(future)
            
            for future in as_completed(futures):
                _ = future.result()
        
        # Get state before creating new manager
        status1 = manager1.get_status_summary()
        quota1 = manager1.get_quota_summary()
        
        # Create new manager - should load state
        manager2 = KeyRotationManager(keys, state_path)
        status2 = manager2.get_status_summary()
        quota2 = manager2.get_quota_summary()
        
        # Compare states
        print("\nComparing persisted state...")
        print(f"Keys used in manager1: {status1['available_keys']}")
        print(f"Keys loaded in manager2: {status2['available_keys']}")
        
        # Verify quota was preserved
        for i in range(len(keys)):
            tokens1 = quota1[i]['tokens_today']
            tokens2 = quota2[i]['tokens_today']
            print(f"Key {i}: {tokens1} tokens -> {tokens2} tokens")
            assert tokens1 == tokens2, f"Token count mismatch for key {i}"
        
        print("✓ State persistence under load test passed")


def main():
    """Run all stress tests."""
    print("Starting Stress Tests")
    print("=" * 50)
    
    try:
        test_concurrent_rotation()
        test_quota_exhaustion()
        test_minute_rate_limits()
        test_daily_reset()
        test_stress_with_failures()
        test_model_specific_tracking()
        test_state_persistence_under_load()
        
        print("\n" + "=" * 50)
        print("✅ All stress tests passed!")
        
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