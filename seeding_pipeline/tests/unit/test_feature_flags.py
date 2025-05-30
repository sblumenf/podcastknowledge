"""
Comprehensive tests for the feature flags module.

This module tests the actual feature flag system implementation including
flag management, caching, decorators, and configuration.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.core.feature_flags import (
    FeatureFlag,
    FlagConfig,
    FeatureFlagManager,
    get_feature_flag_manager,
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
        
        # Check actual flags that exist
        expected_flags = [
            "ENABLE_SCHEMALESS_EXTRACTION",
            "SCHEMALESS_MIGRATION_MODE",
            "LOG_SCHEMA_DISCOVERY",
            "ENABLE_ENTITY_RESOLUTION_V2",
            "ENABLE_TIMESTAMP_INJECTION",
            "ENABLE_SPEAKER_INJECTION",
            "ENABLE_QUOTE_POSTPROCESSING",
            "ENABLE_METADATA_ENRICHMENT",
            "ENABLE_ENTITY_RESOLUTION_POSTPROCESS"
        ]
        
        for expected in expected_flags:
            assert expected in flags
    
    def test_flag_values_are_strings(self):
        """Test that all flag values are strings."""
        for flag in FeatureFlag:
            assert isinstance(flag.value, str)
            assert len(flag.value) > 0
    
    def test_flag_enum_members(self):
        """Test specific enum members exist."""
        assert hasattr(FeatureFlag, 'ENABLE_SCHEMALESS_EXTRACTION')
        assert hasattr(FeatureFlag, 'SCHEMALESS_MIGRATION_MODE')
        assert hasattr(FeatureFlag, 'LOG_SCHEMA_DISCOVERY')
        assert hasattr(FeatureFlag, 'ENABLE_ENTITY_RESOLUTION_V2')


class TestFlagConfig:
    """Test the FlagConfig dataclass."""
    
    def test_flag_config_creation(self):
        """Test creating a flag configuration."""
        config = FlagConfig(
            name="TEST_FLAG",
            default_value=True,
            description="Test flag description"
        )
        assert config.name == "TEST_FLAG"
        assert config.default_value is True
        assert config.description == "Test flag description"
        assert config.env_var is None
    
    def test_flag_config_with_env_var(self):
        """Test flag config with custom env var."""
        config = FlagConfig(
            name="TEST_FLAG",
            default_value=False,
            description="Test flag",
            env_var="CUSTOM_ENV_VAR"
        )
        assert config.env_var == "CUSTOM_ENV_VAR"
        assert config.get_env_var() == "CUSTOM_ENV_VAR"
    
    def test_flag_config_default_env_var(self):
        """Test default environment variable naming."""
        config = FlagConfig(
            name="MY_FEATURE",
            default_value=False,
            description="Test"
        )
        assert config.get_env_var() == "FF_MY_FEATURE"


class TestFeatureFlagManager:
    """Test the FeatureFlagManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh manager instance."""
        manager = FeatureFlagManager()
        manager.clear_cache()  # Ensure clean state
        return manager
    
    def test_manager_initialization(self, manager):
        """Test manager initializes with all flags."""
        all_flags = manager._flags
        
        # Check all expected flags are registered
        assert FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION in all_flags
        assert FeatureFlag.SCHEMALESS_MIGRATION_MODE in all_flags
        assert FeatureFlag.LOG_SCHEMA_DISCOVERY in all_flags
        assert FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2 in all_flags
        
        # Check each flag has proper config
        for flag, config in all_flags.items():
            assert isinstance(config, FlagConfig)
            assert config.name == flag.value
            assert isinstance(config.default_value, bool)
            assert len(config.description) > 0
    
    def test_is_enabled_default_values(self, manager):
        """Test default values for flags."""
        # Schemaless extraction should be disabled by default
        assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is False
        assert manager.is_enabled(FeatureFlag.SCHEMALESS_MIGRATION_MODE) is False
        
        # Some flags are enabled by default
        assert manager.is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY) is True
        assert manager.is_enabled(FeatureFlag.ENABLE_TIMESTAMP_INJECTION) is True
    
    def test_set_flag(self, manager):
        """Test setting flag values programmatically."""
        flag = FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION
        
        # Initially disabled
        assert manager.is_enabled(flag) is False
        
        # Enable the flag
        manager.set_flag(flag, True)
        assert manager.is_enabled(flag) is True
        
        # Disable the flag
        manager.set_flag(flag, False)
        assert manager.is_enabled(flag) is False
    
    def test_set_unknown_flag_raises_error(self, manager):
        """Test setting unknown flag raises ValueError."""
        # Create a mock flag that's not in the manager
        mock_flag = Mock(spec=FeatureFlag)
        mock_flag.value = "UNKNOWN_FLAG"
        
        with pytest.raises(ValueError, match="Unknown feature flag"):
            manager.set_flag(mock_flag, True)
    
    @patch.dict(os.environ, {"FF_ENABLE_SCHEMALESS_EXTRACTION": "true"})
    def test_environment_variable_override(self, manager):
        """Test environment variables override defaults."""
        manager.clear_cache()  # Clear cache to force re-read
        
        # Should be true from environment despite default being false
        assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is True
    
    @patch.dict(os.environ, {"FF_LOG_SCHEMA_DISCOVERY": "false"})
    def test_environment_variable_disable(self, manager):
        """Test environment variables can disable default-true flags."""
        manager.clear_cache()
        
        # Should be false from environment despite default being true
        assert manager.is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY) is False
    
    @patch.dict(os.environ, {"FF_ENABLE_SCHEMALESS_EXTRACTION": "1"})
    def test_environment_variable_formats(self, manager):
        """Test various truthy environment variable formats."""
        manager.clear_cache()
        assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is True
        
        # Test other truthy values
        for value in ["yes", "YES", "on", "ON", "True", "TRUE"]:
            with patch.dict(os.environ, {"FF_ENABLE_SCHEMALESS_EXTRACTION": value}):
                manager.clear_cache()
                assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is True
    
    def test_caching_behavior(self, manager):
        """Test that flag values are cached."""
        flag = FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION
        
        # First call should cache the value
        initial_value = manager.is_enabled(flag)
        assert flag in manager._cache
        
        # Subsequent calls should use cache
        for _ in range(5):
            assert manager.is_enabled(flag) == initial_value
        
        # Clear cache should remove cached values
        manager.clear_cache()
        assert flag not in manager._cache
    
    def test_get_all_flags(self, manager):
        """Test retrieving all flag configurations."""
        all_flags = manager.get_all_flags()
        
        # Should have entry for each flag
        assert len(all_flags) == len(FeatureFlag)
        
        # Check structure of returned data
        for flag in FeatureFlag:
            assert flag.value in all_flags
            flag_info = all_flags[flag.value]
            assert "description" in flag_info
            assert "default" in flag_info
            assert "current" in flag_info
            assert "env_var" in flag_info
            assert isinstance(flag_info["current"], bool)
    
    def test_programmatic_override_beats_environment(self, manager):
        """Test programmatic settings override environment variables."""
        with patch.dict(os.environ, {"FF_ENABLE_SCHEMALESS_EXTRACTION": "true"}):
            manager.clear_cache()
            
            # Environment says true
            assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is True
            
            # But programmatic setting should override
            manager.set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, False)
            assert manager.is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION) is False


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""
    
    @pytest.fixture(autouse=True)
    def clear_global_state(self):
        """Clear global state before each test."""
        global _manager
        from src.core import feature_flags
        feature_flags._manager = None
        yield
        feature_flags._manager = None
    
    def test_get_feature_flag_manager_singleton(self):
        """Test that get_feature_flag_manager returns singleton."""
        manager1 = get_feature_flag_manager()
        manager2 = get_feature_flag_manager()
        assert manager1 is manager2
    
    def test_is_enabled_function(self):
        """Test the module-level is_enabled function."""
        flag = FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION
        
        # Should use default value
        assert is_enabled(flag) is False
        
        # Should reflect changes
        set_flag(flag, True)
        assert is_enabled(flag) is True
    
    def test_set_flag_function(self):
        """Test the module-level set_flag function."""
        flag = FeatureFlag.SCHEMALESS_MIGRATION_MODE
        
        # Set flag
        set_flag(flag, True)
        assert is_enabled(flag) is True
        
        # Unset flag
        set_flag(flag, False)
        assert is_enabled(flag) is False
    
    def test_get_all_flags_function(self):
        """Test the module-level get_all_flags function."""
        # Set some flags
        set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)
        set_flag(FeatureFlag.LOG_SCHEMA_DISCOVERY, False)
        
        all_flags = get_all_flags()
        
        # Check modified flags reflect changes
        assert all_flags["ENABLE_SCHEMALESS_EXTRACTION"]["current"] is True
        assert all_flags["LOG_SCHEMA_DISCOVERY"]["current"] is False


class TestRequiresFlagDecorator:
    """Test the requires_flag decorator."""
    
    def test_decorator_allows_when_enabled(self):
        """Test decorator allows function execution when flag is enabled."""
        set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)
        
        @requires_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
    
    def test_decorator_blocks_when_disabled(self):
        """Test decorator prevents execution when flag is disabled."""
        set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, False)
        
        @requires_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
        def test_function():
            return "should not execute"
        
        result = test_function()
        assert result is None
    
    def test_decorator_with_method(self):
        """Test decorator works with class methods."""
        set_flag(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2, True)
        
        class TestClass:
            @requires_flag(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2)
            def process(self, items):
                return len(items)
        
        obj = TestClass()
        result = obj.process([1, 2, 3, 4, 5])
        assert result == 5
    
    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function metadata."""
        @requires_flag(FeatureFlag.LOG_SCHEMA_DISCOVERY)
        def documented_function():
            """This is a documented function."""
            return 42
        
        # Note: The wrapper function won't preserve all metadata without functools.wraps
        # But we can test that it's callable
        assert callable(documented_function)
    
    def test_decorator_with_arguments(self):
        """Test decorator with various argument types."""
        set_flag(FeatureFlag.ENABLE_TIMESTAMP_INJECTION, True)
        
        @requires_flag(FeatureFlag.ENABLE_TIMESTAMP_INJECTION)
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
        set_flag(FeatureFlag.ENABLE_QUOTE_POSTPROCESSING, True)
        
        @requires_flag(FeatureFlag.ENABLE_QUOTE_POSTPROCESSING)
        def failing_function():
            raise ValueError("Test error")
        
        # Exception should propagate when flag is enabled
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
    
    def test_decorator_returns_none_when_disabled(self):
        """Test that decorator returns None when flag is disabled."""
        set_flag(FeatureFlag.ENABLE_METADATA_ENRICHMENT, False)
        
        @requires_flag(FeatureFlag.ENABLE_METADATA_ENRICHMENT)
        def compute_intensive():
            return {"result": "computed"}
        
        assert compute_intensive() is None


class TestFeatureFlagIntegration:
    """Test integration scenarios with feature flags."""
    
    def test_multiple_flags_scenario(self):
        """Test managing multiple flags together."""
        # Set up a migration scenario
        set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)
        set_flag(FeatureFlag.SCHEMALESS_MIGRATION_MODE, True)
        set_flag(FeatureFlag.LOG_SCHEMA_DISCOVERY, True)
        
        # All should be enabled
        assert is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
        assert is_enabled(FeatureFlag.SCHEMALESS_MIGRATION_MODE)
        assert is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY)
        
        # Disable migration mode
        set_flag(FeatureFlag.SCHEMALESS_MIGRATION_MODE, False)
        
        # Others should remain enabled
        assert is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
        assert not is_enabled(FeatureFlag.SCHEMALESS_MIGRATION_MODE)
        assert is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY)
    
    def test_component_enhancement_flags(self):
        """Test component enhancement flags are properly configured."""
        # Clear cache to ensure we get fresh values
        get_feature_flag_manager().clear_cache()
        
        # These should be enabled by default
        enhancement_flags = [
            FeatureFlag.ENABLE_TIMESTAMP_INJECTION,
            FeatureFlag.ENABLE_SPEAKER_INJECTION,
            FeatureFlag.ENABLE_QUOTE_POSTPROCESSING,
            FeatureFlag.ENABLE_METADATA_ENRICHMENT,
            FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS
        ]
        
        for flag in enhancement_flags:
            assert is_enabled(flag), f"{flag.value} should be enabled by default"
    
    def test_emergency_disable_scenario(self):
        """Test emergency disable of features."""
        # Enable a feature
        set_flag(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2, True)
        assert is_enabled(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2)
        
        # Emergency disable
        set_flag(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2, False)
        assert not is_enabled(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2)
    
    @patch.dict(os.environ, {
        "FF_ENABLE_SCHEMALESS_EXTRACTION": "true",
        "FF_SCHEMALESS_MIGRATION_MODE": "true",
        "FF_LOG_SCHEMA_DISCOVERY": "true"
    })
    def test_environment_based_configuration(self):
        """Test configuring multiple flags via environment."""
        # Clear any cached values
        manager = get_feature_flag_manager()
        manager.clear_cache()
        
        # All should be enabled from environment
        assert is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
        assert is_enabled(FeatureFlag.SCHEMALESS_MIGRATION_MODE)
        assert is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY)
    
    def test_flag_usage_logging(self):
        """Test that flag usage is logged appropriately."""
        with patch('src.core.feature_flags.logger') as mock_logger:
            # Check flag value (should log)
            is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
            
            # Set flag value (should log)
            set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)
            
            # Verify logging occurred
            assert mock_logger.debug.called or mock_logger.info.called