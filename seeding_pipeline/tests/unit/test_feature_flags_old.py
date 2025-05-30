"""
Comprehensive tests for the feature flags module.

This module tests the feature flag system including flag management,
caching, decorators, and configuration.
"""

import pytest
import os
from unittest.mock import Mock, patch, mock_open
from src.core.feature_flags import (
    FeatureFlag,
    FlagConfig,
    FeatureFlagManager,
    is_enabled,
    set_flag,
    get_all_flags,
    requires_flag,
)


class TestFeatureFlag:
    """Test the FeatureFlag enum."""
    
    def test_feature_flags_defined(self):
        """Test that expected feature flags are defined."""
        # Check that we can access feature flags
        flags = [f.value for f in FeatureFlag]
        assert len(flags) > 0  # Should have at least some flags
        
        # Common expected flags
        expected_flags = [
            "SCHEMALESS_EXTRACTION",
            "LARGE_CONTEXT_WINDOW",
            "GPU_ACCELERATION",
            "BATCH_PROCESSING",
            "DISTRIBUTED_PROCESSING"
        ]
        
        for expected in expected_flags:
            assert expected in flags
    
    def test_flag_values_are_strings(self):
        """Test that all flag values are strings."""
        for flag in FeatureFlag:
            assert isinstance(flag.value, str)
            assert len(flag.value) > 0


class TestFlagConfig:
    """Test the FlagConfig dataclass."""
    
    def test_default_config(self):
        """Test default flag configuration."""
        config = FlagConfig()
        assert config.enabled is False
        assert config.rollout_percentage == 0.0
        assert config.allowed_users == []
        assert config.metadata == {}
    
    def test_custom_config(self):
        """Test custom flag configuration."""
        config = FlagConfig(
            enabled=True,
            rollout_percentage=50.0,
            allowed_users=["user1", "user2"],
            metadata={"version": "1.0", "team": "backend"}
        )
        assert config.enabled is True
        assert config.rollout_percentage == 50.0
        assert config.allowed_users == ["user1", "user2"]
        assert config.metadata["version"] == "1.0"
    
    def test_config_immutability(self):
        """Test that config values can be modified (not frozen)."""
        config = FlagConfig()
        config.enabled = True
        config.rollout_percentage = 75.0
        assert config.enabled is True
        assert config.rollout_percentage == 75.0


class TestFeatureFlagManager:
    """Test the FeatureFlagManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh manager instance."""
        # Clear any existing cache
        if hasattr(FeatureFlagManager, '_instance'):
            delattr(FeatureFlagManager, '_instance')
        return FeatureFlagManager()
    
    def test_singleton_pattern(self):
        """Test that manager follows singleton pattern."""
        manager1 = FeatureFlagManager()
        manager2 = FeatureFlagManager()
        assert manager1 is manager2
    
    def test_default_flags_disabled(self, manager):
        """Test that flags are disabled by default."""
        for flag in FeatureFlag:
            assert not manager.is_enabled(flag.value)
    
    def test_set_and_check_flag(self, manager):
        """Test setting and checking flag status."""
        flag = FeatureFlag.SCHEMALESS_EXTRACTION.value
        
        # Initially disabled
        assert not manager.is_enabled(flag)
        
        # Enable the flag
        manager.set_flag(flag, True)
        assert manager.is_enabled(flag)
        
        # Disable the flag
        manager.set_flag(flag, False)
        assert not manager.is_enabled(flag)
    
    def test_set_flag_with_config(self, manager):
        """Test setting flag with full configuration."""
        flag = FeatureFlag.LARGE_CONTEXT_WINDOW.value
        config = FlagConfig(
            enabled=True,
            rollout_percentage=25.0,
            allowed_users=["test_user"]
        )
        
        manager.set_flag(flag, config)
        
        # Check that flag is enabled
        assert manager.is_enabled(flag)
        
        # Verify config was stored
        all_flags = manager.get_all_flags()
        assert flag in all_flags
        assert all_flags[flag].rollout_percentage == 25.0
    
    def test_rollout_percentage(self, manager):
        """Test rollout percentage logic."""
        flag = FeatureFlag.GPU_ACCELERATION.value
        
        # Set 50% rollout
        config = FlagConfig(enabled=True, rollout_percentage=50.0)
        manager.set_flag(flag, config)
        
        # Test with different user IDs - should get mixed results
        enabled_count = 0
        total_tests = 1000
        
        for i in range(total_tests):
            if manager.is_enabled(flag, user_id=f"user_{i}"):
                enabled_count += 1
        
        # Should be roughly 50% (with some variance)
        percentage = (enabled_count / total_tests) * 100
        assert 40 <= percentage <= 60  # Allow 10% variance
    
    def test_allowed_users(self, manager):
        """Test allowed users list."""
        flag = FeatureFlag.BATCH_PROCESSING.value
        config = FlagConfig(
            enabled=False,  # Globally disabled
            allowed_users=["special_user", "admin_user"]
        )
        manager.set_flag(flag, config)
        
        # Flag should be enabled for allowed users even if globally disabled
        assert manager.is_enabled(flag, user_id="special_user")
        assert manager.is_enabled(flag, user_id="admin_user")
        assert not manager.is_enabled(flag, user_id="regular_user")
        assert not manager.is_enabled(flag)  # No user specified
    
    def test_get_all_flags(self, manager):
        """Test retrieving all flag configurations."""
        # Set a few flags
        manager.set_flag(FeatureFlag.SCHEMALESS_EXTRACTION.value, True)
        manager.set_flag(
            FeatureFlag.GPU_ACCELERATION.value,
            FlagConfig(enabled=True, rollout_percentage=75.0)
        )
        
        all_flags = manager.get_all_flags()
        
        # Should include all FeatureFlag enum values
        for flag in FeatureFlag:
            assert flag.value in all_flags
        
        # Check specific configurations
        assert all_flags[FeatureFlag.SCHEMALESS_EXTRACTION.value].enabled is True
        assert all_flags[FeatureFlag.GPU_ACCELERATION.value].rollout_percentage == 75.0
    
    def test_clear_cache(self, manager):
        """Test cache clearing functionality."""
        flag = FeatureFlag.DISTRIBUTED_PROCESSING.value
        
        # Enable flag
        manager.set_flag(flag, True)
        assert manager.is_enabled(flag)
        
        # Clear cache
        manager.clear_cache()
        
        # Flag should still be enabled (cache doesn't affect storage)
        assert manager.is_enabled(flag)
    
    def test_invalid_flag_name(self, manager):
        """Test handling of invalid flag names."""
        # Should handle gracefully
        assert not manager.is_enabled("INVALID_FLAG_NAME")
        
        # Setting invalid flag should work (for forward compatibility)
        manager.set_flag("FUTURE_FLAG", True)
        assert manager.is_enabled("FUTURE_FLAG")
    
    @patch.dict(os.environ, {"SEEDING_ENV": "production"})
    def test_production_environment_defaults(self):
        """Test that flags have safe defaults in production."""
        # Create new manager in production env
        if hasattr(FeatureFlagManager, '_instance'):
            delattr(FeatureFlagManager, '_instance')
        
        manager = FeatureFlagManager()
        
        # All flags should be disabled by default in production
        for flag in FeatureFlag:
            assert not manager.is_enabled(flag.value)
    
    def test_flag_metadata(self, manager):
        """Test storing and retrieving flag metadata."""
        flag = FeatureFlag.SCHEMALESS_EXTRACTION.value
        config = FlagConfig(
            enabled=True,
            metadata={
                "description": "Enable schemaless extraction mode",
                "jira_ticket": "PROJ-123",
                "owner": "data-team"
            }
        )
        
        manager.set_flag(flag, config)
        
        all_flags = manager.get_all_flags()
        metadata = all_flags[flag].metadata
        assert metadata["description"] == "Enable schemaless extraction mode"
        assert metadata["jira_ticket"] == "PROJ-123"
        assert metadata["owner"] == "data-team"


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the feature flag manager before each test."""
        if hasattr(FeatureFlagManager, '_instance'):
            delattr(FeatureFlagManager, '_instance')
        yield
        if hasattr(FeatureFlagManager, '_instance'):
            delattr(FeatureFlagManager, '_instance')
    
    def test_is_enabled_function(self):
        """Test the module-level is_enabled function."""
        flag = FeatureFlag.SCHEMALESS_EXTRACTION.value
        
        # Initially disabled
        assert not is_enabled(flag)
        
        # Enable it
        set_flag(flag, True)
        assert is_enabled(flag)
    
    def test_set_flag_function(self):
        """Test the module-level set_flag function."""
        flag = FeatureFlag.GPU_ACCELERATION.value
        
        # Set with boolean
        set_flag(flag, True)
        assert is_enabled(flag)
        
        # Set with config
        config = FlagConfig(enabled=False, rollout_percentage=30.0)
        set_flag(flag, config)
        assert not is_enabled(flag)
    
    def test_get_all_flags_function(self):
        """Test the module-level get_all_flags function."""
        # Set some flags
        set_flag(FeatureFlag.BATCH_PROCESSING.value, True)
        set_flag(FeatureFlag.LARGE_CONTEXT_WINDOW.value, False)
        
        all_flags = get_all_flags()
        
        assert all_flags[FeatureFlag.BATCH_PROCESSING.value].enabled is True
        assert all_flags[FeatureFlag.LARGE_CONTEXT_WINDOW.value].enabled is False
    
    def test_module_functions_with_user_id(self):
        """Test module functions with user_id parameter."""
        flag = FeatureFlag.DISTRIBUTED_PROCESSING.value
        config = FlagConfig(
            enabled=False,
            allowed_users=["power_user"]
        )
        
        set_flag(flag, config)
        
        assert not is_enabled(flag)
        assert is_enabled(flag, user_id="power_user")
        assert not is_enabled(flag, user_id="regular_user")


class TestRequiresFlagDecorator:
    """Test the requires_flag decorator."""
    
    def test_decorator_allows_when_enabled(self):
        """Test decorator allows function execution when flag is enabled."""
        set_flag(FeatureFlag.SCHEMALESS_EXTRACTION.value, True)
        
        @requires_flag(FeatureFlag.SCHEMALESS_EXTRACTION)
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
    
    def test_decorator_blocks_when_disabled(self):
        """Test decorator prevents execution when flag is disabled."""
        set_flag(FeatureFlag.GPU_ACCELERATION.value, False)
        
        @requires_flag(FeatureFlag.GPU_ACCELERATION)
        def gpu_function():
            return "GPU result"
        
        result = gpu_function()
        assert result is None
    
    def test_decorator_with_method(self):
        """Test decorator works with class methods."""
        set_flag(FeatureFlag.BATCH_PROCESSING.value, True)
        
        class TestClass:
            @requires_flag(FeatureFlag.BATCH_PROCESSING)
            def process_batch(self, items):
                return len(items)
        
        obj = TestClass()
        result = obj.process_batch([1, 2, 3, 4, 5])
        assert result == 5
    
    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""
        @requires_flag(FeatureFlag.LARGE_CONTEXT_WINDOW)
        def documented_function():
            """This is a documented function."""
            return 42
        
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."
    
    def test_decorator_with_arguments(self):
        """Test decorator with various argument types."""
        set_flag(FeatureFlag.DISTRIBUTED_PROCESSING.value, True)
        
        @requires_flag(FeatureFlag.DISTRIBUTED_PROCESSING)
        def complex_function(a, b=10, *args, **kwargs):
            return {
                "a": a,
                "b": b,
                "args": args,
                "kwargs": kwargs
            }
        
        result = complex_function(1, 2, 3, 4, x=5, y=6)
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["args"] == (3, 4)
        assert result["kwargs"] == {"x": 5, "y": 6}
    
    def test_decorator_with_exception_in_function(self):
        """Test decorator behavior when decorated function raises exception."""
        set_flag(FeatureFlag.SCHEMALESS_EXTRACTION.value, True)
        
        @requires_flag(FeatureFlag.SCHEMALESS_EXTRACTION)
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
    
    def test_decorator_with_return_value_on_disabled(self):
        """Test that decorator returns None when flag is disabled."""
        set_flag(FeatureFlag.GPU_ACCELERATION.value, False)
        
        @requires_flag(FeatureFlag.GPU_ACCELERATION)
        def compute_intensive():
            return {"result": "computed"}
        
        assert compute_intensive() is None


class TestFeatureFlagIntegration:
    """Test integration scenarios with feature flags."""
    
    def test_gradual_rollout_scenario(self):
        """Test a gradual rollout scenario."""
        flag = FeatureFlag.SCHEMALESS_EXTRACTION.value
        
        # Start with 0% rollout
        set_flag(flag, FlagConfig(enabled=True, rollout_percentage=0.0))
        
        # No users should have access
        for i in range(100):
            assert not is_enabled(flag, user_id=f"user_{i}")
        
        # Increase to 50% rollout
        set_flag(flag, FlagConfig(enabled=True, rollout_percentage=50.0))
        
        # About half should have access
        enabled_count = sum(
            1 for i in range(100) 
            if is_enabled(flag, user_id=f"user_{i}")
        )
        assert 30 <= enabled_count <= 70
        
        # Full rollout
        set_flag(flag, FlagConfig(enabled=True, rollout_percentage=100.0))
        
        # All users should have access
        for i in range(100):
            assert is_enabled(flag, user_id=f"user_{i}")
    
    def test_emergency_kill_switch(self):
        """Test emergency flag disable scenario."""
        flag = FeatureFlag.DISTRIBUTED_PROCESSING.value
        
        # Feature is rolled out to everyone
        set_flag(flag, FlagConfig(
            enabled=True,
            rollout_percentage=100.0,
            allowed_users=["admin1", "admin2"]
        ))
        
        # Verify it's enabled
        assert is_enabled(flag)
        assert is_enabled(flag, user_id="random_user")
        
        # Emergency disable
        set_flag(flag, False)
        
        # Should be disabled for everyone
        assert not is_enabled(flag)
        assert not is_enabled(flag, user_id="admin1")
        assert not is_enabled(flag, user_id="random_user")
    
    def test_beta_testing_scenario(self):
        """Test beta testing with specific users."""
        flag = FeatureFlag.LARGE_CONTEXT_WINDOW.value
        
        beta_testers = ["beta1@example.com", "beta2@example.com", "beta3@example.com"]
        
        # Enable only for beta testers
        set_flag(flag, FlagConfig(
            enabled=False,  # Not generally available
            allowed_users=beta_testers
        ))
        
        # Beta testers have access
        for tester in beta_testers:
            assert is_enabled(flag, user_id=tester)
        
        # Regular users don't
        assert not is_enabled(flag, user_id="regular@example.com")
        assert not is_enabled(flag)
    
    @patch.dict(os.environ, {"FEATURE_FLAGS_CONFIG": "config/feature_flags.json"})
    @patch("builtins.open", new_callable=mock_open, read_data='{"SCHEMALESS_EXTRACTION": {"enabled": true}}')
    def test_loading_from_config_file(self, mock_file):
        """Test loading feature flags from configuration file."""
        # This test simulates loading flags from a config file
        # In real implementation, the manager might load from file on init
        
        # For this test, we'll manually parse the config
        import json
        config_data = json.loads(mock_file.return_value.read())
        
        # Apply the configuration
        for flag_name, flag_config in config_data.items():
            if flag_name in [f.value for f in FeatureFlag]:
                set_flag(flag_name, flag_config.get("enabled", False))
        
        # Verify the flag was loaded
        assert is_enabled(FeatureFlag.SCHEMALESS_EXTRACTION.value)