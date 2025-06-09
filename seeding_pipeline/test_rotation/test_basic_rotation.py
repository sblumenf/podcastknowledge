#!/usr/bin/env python3
"""Test basic API key rotation functionality."""

import os
import sys
import json
from pathlib import Path
import tempfile
import shutil

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.key_rotation_manager import KeyRotationManager, KeyStatus, create_key_rotation_manager
from src.utils.rotation_state_manager import RotationStateManager


def test_single_key_functionality():
    """Test backward compatibility with single API key."""
    print("\n=== Testing Single Key Functionality ===")
    
    # Create temporary directory for state
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with single key
        manager = KeyRotationManager(['test_key_123456789'], Path(temp_dir))
        
        # Get the key
        key, index = manager.get_next_key()
        print(f"Got key: {key[:10]}... at index {index}")
        assert key == 'test_key_123456789'
        assert index == 0
        
        # Mark success
        manager.mark_key_success(index)
        
        # Get status
        status = manager.get_status_summary()
        print(f"Status: {json.dumps(status, indent=2)}")
        
        assert status['total_keys'] == 1
        assert status['available_keys'] == 1
        
        print("✓ Single key functionality working correctly")


def test_multi_key_rotation():
    """Test rotation with multiple keys."""
    print("\n=== Testing Multi-Key Rotation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create manager with 3 test keys
        keys = ['key_1_abcdef', 'key_2_ghijkl', 'key_3_mnopqr']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Test round-robin rotation
        seen_indices = []
        for i in range(6):  # Test 2 full rotations
            key, index = manager.get_next_key()
            seen_indices.append(index)
            print(f"Rotation {i}: Got key at index {index}")
            manager.mark_key_success(index)
        
        # Check that we rotated properly
        expected = [0, 1, 2, 0, 1, 2]
        assert seen_indices == expected, f"Expected {expected}, got {seen_indices}"
        
        print("✓ Round-robin rotation working correctly")


def test_key_failure_handling():
    """Test handling of failed keys."""
    print("\n=== Testing Key Failure Handling ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['key_1_fail', 'key_2_good', 'key_3_good']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Mark first key as failed multiple times
        manager.mark_key_failure(0, "Test quota exceeded error")
        manager.mark_key_failure(0, "Test quota exceeded error")
        manager.mark_key_failure(0, "Test quota exceeded error")
        
        # Get next key - should skip the failed one
        key, index = manager.get_next_key()
        print(f"After failures, got key at index {index}")
        assert index == 1, f"Expected index 1, got {index}"
        
        # Check status
        status = manager.get_status_summary()
        print(f"Status after failures: {json.dumps(status, indent=2)}")
        
        assert status['available_keys'] == 2
        assert status['key_states'][0]['status'] == KeyStatus.QUOTA_EXCEEDED.value
        
        print("✓ Key failure handling working correctly")


def test_quota_tracking():
    """Test quota usage tracking."""
    print("\n=== Testing Quota Tracking ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        keys = ['key_1_quota']
        manager = KeyRotationManager(keys, Path(temp_dir))
        
        # Simulate API usage
        key, index = manager.get_next_key(model='gemini-2.5-flash')
        manager.mark_key_success(index)
        manager.update_key_usage(index, tokens_used=1000, model='gemini-2.5-flash')
        
        # Check quota summary
        quota_summary = manager.get_quota_summary()
        print(f"Quota summary: {json.dumps(quota_summary, indent=2)}")
        
        assert quota_summary[0]['tokens_today'] == 1000
        assert quota_summary[0]['requests_today'] == 1
        assert 'gemini-2.5-flash' in quota_summary[0]['model_usage']
        
        print("✓ Quota tracking working correctly")


def test_state_persistence():
    """Test that state persists across manager instances."""
    print("\n=== Testing State Persistence ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_path = Path(temp_dir)
        
        # Create first manager and use some keys
        keys = ['key_1_persist', 'key_2_persist']
        manager1 = KeyRotationManager(keys, state_path)
        
        # Use first key and update quota
        key, index = manager1.get_next_key()
        manager1.mark_key_success(index)
        manager1.update_key_usage(index, tokens_used=5000, model='gemini-2.5-flash')
        
        # Mark second key as failed
        manager1.mark_key_failure(1, "Test error for persistence")
        
        # Create new manager instance
        manager2 = KeyRotationManager(keys, state_path)
        
        # Check that state was loaded
        status = manager2.get_status_summary()
        print(f"Loaded state: {json.dumps(status, indent=2)}")
        
        # Verify state was preserved
        assert manager2.current_index == 1  # Should remember position
        assert manager2.key_states[0].tokens_today == 5000
        assert manager2.key_states[1].consecutive_failures > 0
        
        print("✓ State persistence working correctly")


def test_model_specific_limits():
    """Test model-specific rate limit handling."""
    print("\n=== Testing Model-Specific Rate Limits ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = KeyRotationManager(['key_1_model'], Path(temp_dir))
        
        # Test different models
        models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.5-pro']
        
        for model in models:
            limits = manager.get_rate_limits_for_model(model)
            print(f"{model} limits: {limits}")
            assert 'rpm' in limits
            assert 'tpm' in limits
            assert 'rpd' in limits
            assert 'tpd' in limits
        
        # Check that different models have different limits
        flash_limits = manager.get_rate_limits_for_model('gemini-2.5-flash')
        pro_limits = manager.get_rate_limits_for_model('gemini-2.5-pro')
        assert flash_limits['rpm'] != pro_limits['rpm']
        
        print("✓ Model-specific rate limits working correctly")


def test_rotation_state_manager():
    """Test the RotationStateManager utilities."""
    print("\n=== Testing RotationStateManager ===")
    
    # Test state directory determination
    state_dir = RotationStateManager.get_state_directory()
    print(f"State directory: {state_dir}")
    assert state_dir.exists()
    
    # Test persistence check
    persistence_ok = RotationStateManager.ensure_state_persistence()
    print(f"Persistence check: {persistence_ok}")
    assert persistence_ok
    
    # Test metrics
    metrics = RotationStateManager.get_rotation_metrics()
    print(f"Rotation metrics: {json.dumps(metrics, indent=2)}")
    assert 'state_directory' in metrics
    assert 'directory_writable' in metrics
    
    print("✓ RotationStateManager working correctly")


def test_environment_variable_loading():
    """Test loading keys from environment variables."""
    print("\n=== Testing Environment Variable Loading ===")
    
    # Save current env
    old_env = os.environ.copy()
    
    try:
        # Clear any existing keys
        for key in list(os.environ.keys()):
            if key.startswith('GEMINI_API_KEY') or key == 'GOOGLE_API_KEY':
                del os.environ[key]
        
        # Test with GOOGLE_API_KEY (backward compatibility)
        os.environ['GOOGLE_API_KEY'] = 'google_test_key_123'
        manager = create_key_rotation_manager()
        assert manager is not None
        assert len(manager.api_keys) == 1
        print("✓ GOOGLE_API_KEY loading works")
        
        # Clear and test with GEMINI_API_KEY
        del os.environ['GOOGLE_API_KEY']
        os.environ['GEMINI_API_KEY'] = 'gemini_test_key_456'
        manager = create_key_rotation_manager()
        assert manager is not None
        assert len(manager.api_keys) == 1
        print("✓ GEMINI_API_KEY loading works")
        
        # Test with multiple keys
        os.environ['GEMINI_API_KEY_1'] = 'gemini_key_1'
        os.environ['GEMINI_API_KEY_2'] = 'gemini_key_2'
        os.environ['GEMINI_API_KEY_3'] = 'gemini_key_3'
        manager = create_key_rotation_manager()
        assert manager is not None
        assert len(manager.api_keys) == 3
        print("✓ Multiple GEMINI_API_KEY_N loading works")
        
        # Test no keys scenario
        for key in list(os.environ.keys()):
            if key.startswith('GEMINI_API_KEY') or key == 'GOOGLE_API_KEY':
                del os.environ[key]
        manager = create_key_rotation_manager()
        assert manager is None
        print("✓ No keys scenario handled correctly")
        
    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_env)


def main():
    """Run all tests."""
    print("Starting API Key Rotation Tests")
    print("=" * 50)
    
    try:
        test_single_key_functionality()
        test_multi_key_rotation()
        test_key_failure_handling()
        test_quota_tracking()
        test_state_persistence()
        test_model_specific_limits()
        test_rotation_state_manager()
        test_environment_variable_loading()
        
        print("\n" + "=" * 50)
        print("✅ All basic rotation tests passed!")
        
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