"""Unit tests for API key rotation manager."""

import os
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.utils.key_rotation_manager import (
    KeyRotationManager, APIKeyState, KeyStatus, 
    create_key_rotation_manager, MODEL_RATE_LIMITS
)


class TestAPIKeyState:
    """Test APIKeyState class functionality."""
    
    def test_initial_state(self):
        """Test initial state of API key."""
        state = APIKeyState(index=0, key_name="test_key")
        assert state.status == KeyStatus.AVAILABLE
        assert state.consecutive_failures == 0
        assert state.requests_today == 0
        assert state.tokens_today == 0
    
    def test_mark_success(self):
        """Test marking key as successful."""
        state = APIKeyState(index=0, key_name="test_key")
        state.mark_success()
        assert state.status == KeyStatus.AVAILABLE
        assert state.consecutive_failures == 0
        assert state.last_used is not None
    
    def test_mark_failure(self):
        """Test marking key as failed."""
        state = APIKeyState(index=0, key_name="test_key")
        
        # First failure
        state.mark_failure("rate limit error")
        assert state.status == KeyStatus.RATE_LIMITED
        assert state.consecutive_failures == 1
        
        # Quota error
        state = APIKeyState(index=0, key_name="test_key")
        state.mark_failure("quota exceeded")
        assert state.status == KeyStatus.QUOTA_EXCEEDED
        
        # Generic errors
        state = APIKeyState(index=0, key_name="test_key")
        state.mark_failure("unknown error")
        state.mark_failure("unknown error")
        state.mark_failure("unknown error")
        assert state.status == KeyStatus.ERROR
        assert state.consecutive_failures == 3
    
    def test_update_quota_usage(self):
        """Test quota usage updates."""
        state = APIKeyState(index=0, key_name="test_key")
        
        # Update usage
        state.update_quota_usage(requests=1, tokens=100, model="gemini-2.5-flash")
        assert state.requests_today == 1
        assert state.tokens_today == 100
        assert state.requests_this_minute == 1
        assert state.model_usage["gemini-2.5-flash"]["requests"] == 1
        assert state.model_usage["gemini-2.5-flash"]["tokens"] == 100
    
    def test_is_usable_with_limits(self):
        """Test usability checks with rate limits."""
        state = APIKeyState(index=0, key_name="test_key")
        limits = {"rpm": 5, "tpm": 1000, "rpd": 50, "tpd": 10000}
        
        # Should be usable initially
        assert state.is_usable(limits)
        
        # Exceed daily requests
        state.requests_today = 51
        assert not state.is_usable(limits)
        
        # Reset and exceed tokens
        state.requests_today = 0
        state.tokens_today = 10001
        assert not state.is_usable(limits)
        
        # Test minute limits
        state = APIKeyState(index=0, key_name="test_key")
        state.last_minute_reset = datetime.now(timezone.utc)
        state.requests_this_minute = 6
        assert not state.is_usable(limits)
    
    def test_serialization(self):
        """Test state serialization and deserialization."""
        state = APIKeyState(index=0, key_name="test_key")
        state.update_quota_usage(requests=5, tokens=500)
        state.mark_success()
        
        # Serialize
        data = state.to_dict()
        assert data["index"] == 0
        assert data["key_name"] == "test_key"
        assert data["requests_today"] == 5
        assert data["tokens_today"] == 500
        
        # Deserialize
        restored = APIKeyState.from_dict(data)
        assert restored.index == state.index
        assert restored.key_name == state.key_name
        assert restored.requests_today == state.requests_today
        assert restored.tokens_today == state.tokens_today


class TestKeyRotationManager:
    """Test KeyRotationManager functionality."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for state files."""
        return tmp_path
    
    @pytest.fixture
    def api_keys(self):
        """Sample API keys for testing."""
        return ["key1", "key2", "key3"]
    
    def test_initialization(self, api_keys, temp_dir):
        """Test manager initialization."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        assert len(manager.api_keys) == 3
        assert len(manager.key_states) == 3
        assert manager.current_index == 0
    
    def test_get_next_key_rotation(self, api_keys, temp_dir):
        """Test round-robin key rotation."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # First key
        key, index = manager.get_next_key()
        assert key == "key1"
        assert index == 0
        assert manager.current_index == 1
        
        # Second key
        key, index = manager.get_next_key()
        assert key == "key2"
        assert index == 1
        assert manager.current_index == 2
        
        # Third key
        key, index = manager.get_next_key()
        assert key == "key3"
        assert index == 2
        assert manager.current_index == 0  # Wrapped around
    
    def test_get_next_key_with_model(self, api_keys, temp_dir):
        """Test key selection with model-specific rate limits."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # Get key for specific model
        key, index = manager.get_next_key("gemini-2.5-flash")
        assert key == "key1"
        
        # Mark it as having high usage
        manager.key_states[0].requests_today = 400  # Near limit for flash
        
        # Should still get it if under limit
        key2, index2 = manager.get_next_key("gemini-2.5-flash")
        assert key2 == "key2"  # Rotated to next
    
    def test_all_keys_exhausted(self, api_keys, temp_dir):
        """Test behavior when all keys are exhausted."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # Mark all keys as unavailable
        for state in manager.key_states:
            state.status = KeyStatus.QUOTA_EXCEEDED
        
        # Should raise exception
        with pytest.raises(Exception, match="No API keys available"):
            manager.get_next_key()
    
    def test_mark_key_success_failure(self, api_keys, temp_dir):
        """Test marking keys as successful or failed."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # Get a key and mark success
        key, index = manager.get_next_key()
        manager.mark_key_success(index)
        assert manager.key_states[index].consecutive_failures == 0
        assert manager.key_states[index].status == KeyStatus.AVAILABLE
        
        # Mark failure
        manager.mark_key_failure(index, "rate limit error")
        assert manager.key_states[index].consecutive_failures == 1
        assert manager.key_states[index].status == KeyStatus.RATE_LIMITED
    
    def test_update_key_usage(self, api_keys, temp_dir):
        """Test updating key usage statistics."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # Update usage
        manager.update_key_usage(0, 1000, "gemini-2.5-flash")
        state = manager.key_states[0]
        assert state.tokens_today == 1000
        assert state.requests_today == 1
        assert state.model_usage["gemini-2.5-flash"]["tokens"] == 1000
    
    def test_state_persistence(self, api_keys, temp_dir):
        """Test state saving and loading."""
        # Create manager and update state
        manager1 = KeyRotationManager(api_keys, state_dir=temp_dir)
        manager1.current_index = 2
        manager1.key_states[0].requests_today = 10
        manager1.key_states[1].status = KeyStatus.RATE_LIMITED
        manager1._save_state()
        
        # Create new manager - should load state
        manager2 = KeyRotationManager(api_keys, state_dir=temp_dir)
        assert manager2.current_index == 2
        assert manager2.key_states[0].requests_today == 10
        assert manager2.key_states[1].status == KeyStatus.RATE_LIMITED
    
    def test_daily_reset(self, api_keys, temp_dir):
        """Test daily quota reset."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        
        # Set up state with usage
        for state in manager.key_states:
            state.requests_today = 20
            state.tokens_today = 5000
            state.status = KeyStatus.QUOTA_EXCEEDED
        
        # Perform daily reset
        manager._daily_reset()
        
        # Check reset
        for state in manager.key_states:
            assert state.requests_today == 0
            assert state.tokens_today == 0
            assert state.status == KeyStatus.AVAILABLE
    
    def test_get_status_summary(self, api_keys, temp_dir):
        """Test status summary generation."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        manager.key_states[0].status = KeyStatus.RATE_LIMITED
        
        summary = manager.get_status_summary()
        assert summary["total_keys"] == 3
        assert summary["available_keys"] == 2
        assert len(summary["key_states"]) == 3
    
    def test_get_quota_summary(self, api_keys, temp_dir):
        """Test quota summary generation."""
        manager = KeyRotationManager(api_keys, state_dir=temp_dir)
        manager.key_states[0].requests_today = 10
        manager.key_states[0].tokens_today = 50000
        
        summary = manager.get_quota_summary()
        assert len(summary) == 3
        assert summary[0]["requests_today"] == 10
        assert summary[0]["tokens_today"] == 50000
        assert summary[0]["requests_remaining"] > 0
    
    def test_model_rate_limits(self):
        """Test model-specific rate limit configuration."""
        assert "gemini-2.5-flash" in MODEL_RATE_LIMITS
        assert "gemini-2.0-flash" in MODEL_RATE_LIMITS
        assert "default" in MODEL_RATE_LIMITS
        
        flash_limits = MODEL_RATE_LIMITS["gemini-2.5-flash"]
        assert flash_limits["rpm"] == 10
        assert flash_limits["rpd"] == 500


class TestCreateKeyRotationManager:
    """Test factory function for creating rotation manager."""
    
    def test_create_with_google_api_key(self, temp_dir, monkeypatch):
        """Test creation with GOOGLE_API_KEY."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
        
        manager = create_key_rotation_manager(temp_dir)
        assert manager is not None
        assert len(manager.api_keys) == 1
        assert manager.api_keys[0] == "test_google_key"
    
    def test_create_with_gemini_api_key(self, temp_dir, monkeypatch):
        """Test creation with GEMINI_API_KEY."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
        
        manager = create_key_rotation_manager(temp_dir)
        assert manager is not None
        assert len(manager.api_keys) == 1
        assert manager.api_keys[0] == "test_gemini_key"
    
    def test_create_with_multiple_keys(self, temp_dir, monkeypatch):
        """Test creation with multiple GEMINI_API_KEY_N keys."""
        monkeypatch.setenv("GEMINI_API_KEY_1", "key1")
        monkeypatch.setenv("GEMINI_API_KEY_2", "key2")
        monkeypatch.setenv("GEMINI_API_KEY_3", "key3")
        
        manager = create_key_rotation_manager(temp_dir)
        assert manager is not None
        assert len(manager.api_keys) == 3
        assert manager.api_keys == ["key1", "key2", "key3"]
    
    def test_create_with_mixed_keys(self, temp_dir, monkeypatch):
        """Test creation with both GOOGLE_API_KEY and GEMINI_API_KEY_N."""
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        monkeypatch.setenv("GEMINI_API_KEY_1", "gemini_key1")
        monkeypatch.setenv("GEMINI_API_KEY_2", "gemini_key2")
        
        manager = create_key_rotation_manager(temp_dir)
        assert manager is not None
        assert len(manager.api_keys) == 3
        assert "google_key" in manager.api_keys
        assert "gemini_key1" in manager.api_keys
        assert "gemini_key2" in manager.api_keys
    
    def test_create_no_keys(self, temp_dir, monkeypatch):
        """Test creation with no API keys."""
        # Clear all potential env vars
        for key in ["GOOGLE_API_KEY", "GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(1, 10)]:
            monkeypatch.delenv(key, raising=False)
        
        manager = create_key_rotation_manager(temp_dir)
        assert manager is None