"""Unit tests for the key rotation manager module."""

import pytest
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.key_rotation_manager import (
    KeyStatus, APIKeyState, KeyRotationManager, create_key_rotation_manager
)


class TestKeyStatus:
    """Test KeyStatus enum."""
    
    def test_key_status_values(self):
        """Test key status enum values."""
        assert KeyStatus.AVAILABLE.value == "available"
        assert KeyStatus.RATE_LIMITED.value == "rate_limited"
        assert KeyStatus.QUOTA_EXCEEDED.value == "quota_exceeded"
        assert KeyStatus.ERROR.value == "error"


class TestAPIKeyState:
    """Test APIKeyState dataclass."""
    
    def test_api_key_state_creation(self):
        """Test creating API key state."""
        state = APIKeyState(index=0, key_name="key_1 (test1234...)")
        
        assert state.index == 0
        assert state.key_name == "key_1 (test1234...)"
        assert state.status == KeyStatus.AVAILABLE
        assert state.last_used is None
        assert state.consecutive_failures == 0
        assert state.error_message is None
    
    def test_is_usable(self):
        """Test checking if key is usable."""
        state = APIKeyState(index=0, key_name="test_key")
        
        # Available key is usable
        assert state.is_usable() is True
        
        # Rate limited key is not usable
        state.status = KeyStatus.RATE_LIMITED
        assert state.is_usable() is False
        
        # Quota exceeded key is not usable
        state.status = KeyStatus.QUOTA_EXCEEDED
        assert state.is_usable() is False
        
        # Error key is not usable
        state.status = KeyStatus.ERROR
        assert state.is_usable() is False
    
    def test_mark_success(self):
        """Test marking key use as successful."""
        state = APIKeyState(
            index=0,
            key_name="test_key",
            status=KeyStatus.RATE_LIMITED,
            consecutive_failures=3,
            error_message="Previous error"
        )
        
        before_time = datetime.now(timezone.utc)
        state.mark_success()
        after_time = datetime.now(timezone.utc)
        
        assert state.status == KeyStatus.AVAILABLE
        assert state.consecutive_failures == 0
        assert state.error_message is None
        assert state.last_used is not None
        assert before_time <= state.last_used <= after_time
    
    def test_mark_failure_quota(self):
        """Test marking failure with quota exceeded error."""
        state = APIKeyState(index=0, key_name="test_key")
        
        state.mark_failure("Resource has been exhausted (e.g. check quota)")
        
        assert state.consecutive_failures == 1
        assert state.status == KeyStatus.QUOTA_EXCEEDED
        assert state.error_message == "Resource has been exhausted (e.g. check quota)"
        assert state.last_used is not None
    
    def test_mark_failure_rate_limit(self):
        """Test marking failure with rate limit error."""
        state = APIKeyState(index=0, key_name="test_key")
        
        state.mark_failure("Rate limit exceeded")
        
        assert state.consecutive_failures == 1
        assert state.status == KeyStatus.RATE_LIMITED
        assert state.error_message == "Rate limit exceeded"
    
    def test_mark_failure_consecutive(self):
        """Test marking consecutive failures."""
        state = APIKeyState(index=0, key_name="test_key")
        
        # First two failures keep status as available
        state.mark_failure("Generic error 1")
        assert state.status == KeyStatus.AVAILABLE
        assert state.consecutive_failures == 1
        
        state.mark_failure("Generic error 2")
        assert state.status == KeyStatus.AVAILABLE
        assert state.consecutive_failures == 2
        
        # Third failure marks as error
        state.mark_failure("Generic error 3")
        assert state.status == KeyStatus.ERROR
        assert state.consecutive_failures == 3
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        now = datetime.now(timezone.utc)
        state = APIKeyState(
            index=1,
            key_name="test_key",
            status=KeyStatus.RATE_LIMITED,
            last_used=now,
            consecutive_failures=2,
            error_message="Test error"
        )
        
        data = state.to_dict()
        
        assert data['index'] == 1
        assert data['key_name'] == "test_key"
        assert data['status'] == "rate_limited"
        assert data['last_used'] == now.isoformat()
        assert data['consecutive_failures'] == 2
        assert data['error_message'] == "Test error"
    
    def test_from_dict(self):
        """Test creating from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            'index': 2,
            'key_name': 'key_3',
            'status': 'quota_exceeded',
            'last_used': now.isoformat(),
            'consecutive_failures': 5,
            'error_message': 'Quota error'
        }
        
        state = APIKeyState.from_dict(data)
        
        assert state.index == 2
        assert state.key_name == 'key_3'
        assert state.status == KeyStatus.QUOTA_EXCEEDED
        assert state.last_used.isoformat() == now.isoformat()
        assert state.consecutive_failures == 5
        assert state.error_message == 'Quota error'


class TestKeyRotationManager:
    """Test KeyRotationManager class."""
    
    @pytest.fixture
    def test_keys(self):
        """Provide test API keys."""
        return ['test_key_1', 'test_key_2', 'test_key_3']
    
    @pytest.fixture
    def manager(self, test_keys, temp_dir):
        """Create a key rotation manager for testing."""
        # Use temp directory for state file
        with patch('src.key_rotation_manager.Path') as mock_path:
            mock_path.return_value = Path(temp_dir) / ".key_rotation_state.json"
            return KeyRotationManager(test_keys)
    
    def test_init_with_keys(self, test_keys, mock_logger):
        """Test initializing with API keys."""
        manager = KeyRotationManager(test_keys)
        
        assert len(manager.api_keys) == 3
        assert len(manager.key_states) == 3
        assert manager.current_index == 0
        
        # Check key names are masked
        assert "key_1 (test_key" in manager.key_states[0].key_name
        assert "...)" in manager.key_states[0].key_name
    
    def test_init_no_keys(self):
        """Test initializing without keys raises error."""
        with pytest.raises(ValueError, match="At least one API key"):
            KeyRotationManager([])
    
    def test_get_next_key_round_robin(self, manager):
        """Test round-robin key rotation."""
        # First call returns key 0
        key, index = manager.get_next_key()
        assert key == 'test_key_1'
        assert index == 0
        assert manager.current_index == 1
        
        # Second call returns key 1
        key, index = manager.get_next_key()
        assert key == 'test_key_2'
        assert index == 1
        assert manager.current_index == 2
        
        # Third call returns key 2
        key, index = manager.get_next_key()
        assert key == 'test_key_3'
        assert index == 2
        assert manager.current_index == 0  # Wrapped around
        
        # Fourth call returns key 0 again
        key, index = manager.get_next_key()
        assert key == 'test_key_1'
        assert index == 0
    
    def test_get_next_key_skip_unavailable(self, manager):
        """Test skipping unavailable keys."""
        # Mark key 0 as rate limited
        manager.key_states[0].status = KeyStatus.RATE_LIMITED
        
        # Should skip to key 1
        key, index = manager.get_next_key()
        assert key == 'test_key_2'
        assert index == 1
        
        # Mark key 2 as error
        manager.key_states[2].status = KeyStatus.ERROR
        
        # Should return key 1 again (only available)
        key, index = manager.get_next_key()
        assert key == 'test_key_2'
        assert index == 1
    
    def test_get_next_key_all_unavailable(self, manager):
        """Test when all keys are unavailable."""
        # Mark all keys as unavailable
        for state in manager.key_states:
            state.status = KeyStatus.QUOTA_EXCEEDED
        
        with pytest.raises(Exception, match="No API keys available"):
            manager.get_next_key()
    
    def test_mark_key_success(self, manager):
        """Test marking key as successful."""
        # Mark key 1 as failed first
        manager.key_states[1].consecutive_failures = 2
        manager.key_states[1].status = KeyStatus.ERROR
        
        manager.mark_key_success(1)
        
        assert manager.key_states[1].status == KeyStatus.AVAILABLE
        assert manager.key_states[1].consecutive_failures == 0
        assert manager.key_states[1].last_used is not None
    
    def test_mark_key_failure(self, manager):
        """Test marking key as failed."""
        manager.mark_key_failure(0, "Rate limit exceeded")
        
        assert manager.key_states[0].status == KeyStatus.RATE_LIMITED
        assert manager.key_states[0].consecutive_failures == 1
        assert manager.key_states[0].error_message == "Rate limit exceeded"
    
    def test_get_key_by_index(self, manager):
        """Test getting specific key by index."""
        assert manager.get_key_by_index(0) == 'test_key_1'
        assert manager.get_key_by_index(1) == 'test_key_2'
        assert manager.get_key_by_index(2) == 'test_key_3'
        assert manager.get_key_by_index(3) is None  # Out of range
        assert manager.get_key_by_index(-1) is None  # Negative index
    
    def test_get_status_summary(self, manager):
        """Test getting status summary."""
        # Set up some states
        manager.key_states[0].mark_success()
        manager.key_states[1].mark_failure("Quota exceeded")
        manager.key_states[1].status = KeyStatus.QUOTA_EXCEEDED
        
        summary = manager.get_status_summary()
        
        assert summary['total_keys'] == 3
        assert summary['current_index'] == 0
        assert summary['available_keys'] == 2
        assert len(summary['key_states']) == 3
        
        # Check individual key states
        assert summary['key_states'][0]['status'] == 'available'
        assert summary['key_states'][1]['status'] == 'quota_exceeded'
        assert summary['key_states'][1]['error'] == 'Quota exceeded'
    
    def test_force_reset_key(self, manager):
        """Test force resetting a key."""
        # Set key as failed
        manager.key_states[1].status = KeyStatus.ERROR
        manager.key_states[1].consecutive_failures = 5
        manager.key_states[1].error_message = "Multiple errors"
        
        manager.force_reset_key(1)
        
        assert manager.key_states[1].status == KeyStatus.AVAILABLE
        assert manager.key_states[1].consecutive_failures == 0
        assert manager.key_states[1].error_message is None
    
    def test_daily_reset(self, manager):
        """Test daily reset of key states."""
        # Set some keys as rate limited/quota exceeded
        manager.key_states[0].status = KeyStatus.RATE_LIMITED
        manager.key_states[1].status = KeyStatus.QUOTA_EXCEEDED
        manager.key_states[2].status = KeyStatus.ERROR  # Should not reset
        
        manager._daily_reset()
        
        assert manager.key_states[0].status == KeyStatus.AVAILABLE
        assert manager.key_states[1].status == KeyStatus.AVAILABLE
        assert manager.key_states[2].status == KeyStatus.ERROR  # Not reset
    
    def test_save_and_load_state(self, temp_dir, test_keys, mock_logger):
        """Test saving and loading state."""
        state_file = Path(temp_dir) / ".key_rotation_state.json"
        
        # Create first manager and modify state
        with patch('src.key_rotation_manager.Path') as mock_path:
            mock_path.return_value = state_file
            manager1 = KeyRotationManager(test_keys)
            
            manager1.current_index = 2
            manager1.key_states[0].mark_failure("Test error")
            manager1.key_states[1].mark_success()
            manager1._save_state()
        
        # Create second manager and verify state is loaded
        with patch('src.key_rotation_manager.Path') as mock_path:
            mock_path.return_value = state_file
            manager2 = KeyRotationManager(test_keys)
            
            assert manager2.current_index == 2
            assert manager2.key_states[0].consecutive_failures == 1
            assert manager2.key_states[0].error_message == "Test error"
            assert manager2.key_states[1].last_used is not None
    
    def test_load_state_with_daily_reset(self, temp_dir, test_keys, mock_logger):
        """Test loading state triggers daily reset if needed."""
        state_file = Path(temp_dir) / ".key_rotation_state.json"
        
        # Create state from yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        state_data = {
            'current_index': 1,
            'last_reset': yesterday.date().isoformat(),
            'key_states': [
                {
                    'index': 0,
                    'key_name': 'key_1',
                    'status': 'quota_exceeded',
                    'consecutive_failures': 1
                }
            ]
        }
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Create manager - should trigger daily reset
        with patch('src.key_rotation_manager.Path') as mock_path:
            mock_path.return_value = state_file
            manager = KeyRotationManager(test_keys)
            
            # Quota exceeded should be reset to available
            assert manager.key_states[0].status == KeyStatus.AVAILABLE


class TestCreateKeyRotationManager:
    """Test create_key_rotation_manager factory function."""
    
    def test_create_with_multiple_keys(self, mock_logger):
        """Test creating manager with multiple numbered keys."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'key1',
            'GEMINI_API_KEY_2': 'key2',
            'GEMINI_API_KEY_3': 'key3'
        }):
            manager = create_key_rotation_manager()
            
            assert manager is not None
            assert len(manager.api_keys) == 3
            assert manager.api_keys == ['key1', 'key2', 'key3']
    
    def test_create_with_gap_in_keys(self, mock_logger):
        """Test creating manager stops at first missing key."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY_1': 'key1',
            'GEMINI_API_KEY_2': 'key2',
            # No KEY_3
            'GEMINI_API_KEY_4': 'key4'  # Should not be included
        }):
            manager = create_key_rotation_manager()
            
            assert manager is not None
            assert len(manager.api_keys) == 2
            assert manager.api_keys == ['key1', 'key2']
    
    def test_create_with_single_key_fallback(self, mock_logger):
        """Test creating manager with single key fallback."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'single_key'
            # No numbered keys
        }, clear=True):
            manager = create_key_rotation_manager()
            
            assert manager is not None
            assert len(manager.api_keys) == 1
            assert manager.api_keys == ['single_key']
    
    def test_create_no_keys(self, mock_logger):
        """Test creating manager with no keys returns None."""
        with patch.dict(os.environ, {}, clear=True):
            manager = create_key_rotation_manager()
            
            assert manager is None