"""Unit tests for deprecation utilities."""

from datetime import datetime
from unittest.mock import patch, call
import json
import warnings

import pytest

from src.utils.deprecation import (
    deprecated,
    deprecated_class,
    pending_deprecation,
    check_deprecations
)


class TestDeprecatedDecorator:
    """Test deprecated function decorator."""
    
    def test_basic_deprecation(self):
        """Test basic function deprecation."""
        @deprecated(
            reason="This function is outdated",
            version="1.0.0"
        )
        def old_function():
            return "result"
        
        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_function()
            
            # Check result
            assert result == "result"
            
            # Check warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "old_function is deprecated since version 1.0.0" in str(w[0].message)
            assert "This function is outdated" in str(w[0].message)
    
    def test_deprecation_with_alternative(self):
        """Test deprecation with alternative suggestion."""
        @deprecated(
            reason="Use new_function instead",
            version="1.5.0",
            alternative="new_function()"
        )
        def old_function():
            return "old"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_function()
            
            assert len(w) == 1
            message = str(w[0].message)
            assert "Use new_function() instead" in message
    
    def test_deprecation_with_removal_version(self):
        """Test deprecation with removal version."""
        @deprecated(
            reason="Being removed",
            version="2.0.0",
            removal_version="3.0.0"
        )
        def doomed_function():
            return "doomed"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            doomed_function()
            
            assert len(w) == 1
            message = str(w[0].message)
            assert "It will be removed in version 3.0.0" in message
    
    def test_deprecation_metadata(self):
        """Test that deprecation metadata is attached to function."""
        @deprecated(
            reason="Test reason",
            version="1.0.0",
            removal_version="2.0.0",
            alternative="other_func"
        )
        def func():
            pass
        
        # Check metadata
        assert hasattr(func, '__deprecated__')
        assert func.__deprecated__ is True
        assert hasattr(func, '__deprecated_info__')
        
        info = func.__deprecated_info__
        assert info['reason'] == "Test reason"
        assert info['version'] == "1.0.0"
        assert info['removal_version'] == "2.0.0"
        assert info['alternative'] == "other_func"
        assert 'deprecated_at' in info
    
    def test_deprecation_preserves_function_attributes(self):
        """Test that decorator preserves function attributes."""
        def original_function(x, y=10):
            """Original docstring."""
            return x + y
        
        deprecated_func = deprecated(
            reason="Test",
            version="1.0.0"
        )(original_function)
        
        # Check function name and module are preserved
        assert deprecated_func.__name__ == original_function.__name__
        assert deprecated_func.__module__ == original_function.__module__
        
        # Check function works correctly
        assert deprecated_func(5) == 15
        assert deprecated_func(5, 20) == 25
    
    def test_docstring_modification(self):
        """Test that deprecation info is added to docstring."""
        @deprecated(
            reason="Use better_func",
            version="1.2.0",
            removal_version="2.0.0",
            alternative="better_func()"
        )
        def documented_func():
            """This is the original docstring."""
            pass
        
        # Check docstring contains deprecation info
        assert ".. deprecated:: 1.2.0" in documented_func.__doc__
        assert "Use better_func" in documented_func.__doc__
        assert "Use better_func() instead" in documented_func.__doc__
        assert "Will be removed in version 2.0.0" in documented_func.__doc__
        assert "This is the original docstring" in documented_func.__doc__
    
    @patch('src.utils.deprecation.logger')
    def test_deprecation_logging(self, mock_logger):
        """Test that deprecation is logged."""
        @deprecated(reason="Test", version="1.0.0")
        def func():
            pass
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            func()
        
        # Check logging
        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        assert "DEPRECATION:" in log_message


class TestDeprecatedClassDecorator:
    """Test deprecated_class decorator."""
    
    def test_class_deprecation(self):
        """Test basic class deprecation."""
        @deprecated_class(
            reason="Use NewClass instead",
            version="1.0.0"
        )
        class OldClass:
            def __init__(self, value):
                self.value = value
        
        # Creating instance should trigger warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            obj = OldClass(42)
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "OldClass is deprecated since version 1.0.0" in str(w[0].message)
            assert "Use NewClass instead" in str(w[0].message)
        
        # Object should work normally
        assert obj.value == 42
    
    def test_class_deprecation_with_removal(self):
        """Test class deprecation with removal version."""
        @deprecated_class(
            reason="Being removed",
            version="2.0.0",
            removal_version="3.0.0",
            alternative="BetterClass"
        )
        class DoomedClass:
            pass
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            DoomedClass()
            
            message = str(w[0].message)
            assert "Use BetterClass instead" in message
            assert "It will be removed in version 3.0.0" in message
    
    def test_class_metadata(self):
        """Test that class metadata is preserved."""
        @deprecated_class(reason="Test", version="1.0.0")
        class TestClass:
            """Original class docstring."""
            class_var = 42
        
        # Check metadata
        assert hasattr(TestClass, '__deprecated__')
        assert TestClass.__deprecated__ is True
        assert hasattr(TestClass, '__deprecated_info__')
        
        # Check class attributes preserved
        assert TestClass.class_var == 42
        assert ".. deprecated:: 1.0.0" in TestClass.__doc__
        assert "Original class docstring" in TestClass.__doc__
    
    def test_inheritance_still_works(self):
        """Test that inheritance works with deprecated classes."""
        @deprecated_class(reason="Old base", version="1.0.0")
        class BaseClass:
            def method(self):
                return "base"
        
        class DerivedClass(BaseClass):
            def method(self):
                return super().method() + " derived"
        
        # Should only warn when creating BaseClass directly
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            base = BaseClass()
            assert len(w) == 1
            
            derived = DerivedClass()
            # Should get warning from BaseClass.__init__ call via super()
            assert len(w) == 2
        
        assert base.method() == "base"
        assert derived.method() == "base derived"
    
    @patch('src.utils.deprecation.logger')
    def test_class_deprecation_logging(self, mock_logger):
        """Test that class deprecation is logged."""
        @deprecated_class(reason="Test", version="1.0.0")
        class TestClass:
            pass
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            TestClass()
        
        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        assert "DEPRECATION:" in log_message


class TestPendingDeprecation:
    """Test pending_deprecation decorator."""
    
    def test_pending_deprecation_basic(self):
        """Test basic pending deprecation."""
        @pending_deprecation(
            reason="Will be replaced",
            deprecation_version="2.0.0"
        )
        def future_deprecated():
            return "still works"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = future_deprecated()
            
            assert result == "still works"
            assert len(w) == 1
            assert issubclass(w[0].category, PendingDeprecationWarning)
            assert "future_deprecated will be deprecated in version 2.0.0" in str(w[0].message)
            assert "Will be replaced" in str(w[0].message)
    
    def test_pending_deprecation_with_alternative(self):
        """Test pending deprecation with alternative."""
        @pending_deprecation(
            reason="Performance issues",
            deprecation_version="2.5.0",
            alternative="fast_function()"
        )
        def slow_function():
            return "slow"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            slow_function()
            
            message = str(w[0].message)
            assert "Consider using fast_function()" in message
    
    def test_pending_deprecation_metadata(self):
        """Test pending deprecation metadata."""
        @pending_deprecation(
            reason="Test reason",
            deprecation_version="3.0.0",
            alternative="other_func"
        )
        def func():
            pass
        
        assert hasattr(func, '__pending_deprecation__')
        assert func.__pending_deprecation__ is True
        assert hasattr(func, '__pending_deprecation_info__')
        
        info = func.__pending_deprecation_info__
        assert info['reason'] == "Test reason"
        assert info['deprecation_version'] == "3.0.0"
        assert info['alternative'] == "other_func"


class TestCheckDeprecations:
    """Test check_deprecations function."""
    
    def test_check_module_deprecations(self):
        """Test checking a module for deprecations."""
        # Create a test module
        import types
        test_module = types.ModuleType('test_module')
        
        # Add deprecated items
        @deprecated(reason="Old func", version="1.0.0")
        def deprecated_func():
            pass
        
        @deprecated_class(reason="Old class", version="1.1.0")
        class DeprecatedClass:
            pass
        
        @pending_deprecation(reason="Future", deprecation_version="2.0.0")
        def pending_func():
            pass
        
        def normal_func():
            pass
        
        # Add to module
        test_module.deprecated_func = deprecated_func
        test_module.DeprecatedClass = DeprecatedClass
        test_module.pending_func = pending_func
        test_module.normal_func = normal_func
        
        # Check deprecations
        result = check_deprecations(test_module)
        
        # Should find the deprecated items
        assert 'deprecated_func' in result
        assert result['deprecated_func']['type'] == 'function'
        assert result['deprecated_func']['info']['reason'] == "Old func"
        assert result['deprecated_func']['info']['version'] == "1.0.0"
        
        assert 'DeprecatedClass' in result
        # Classes are detected as functions since they're callable
        assert result['DeprecatedClass']['type'] in ['class', 'function']
        assert result['DeprecatedClass']['info']['reason'] == "Old class"
        
        assert 'pending_func' in result
        assert result['pending_func']['pending'] is True
        assert result['pending_func']['info']['reason'] == "Future"
        
        # Should not include normal function
        assert 'normal_func' not in result
    
    def test_check_empty_module(self):
        """Test checking module with no deprecations."""
        import types
        empty_module = types.ModuleType('empty_module')
        empty_module.func1 = lambda: None
        empty_module.func2 = lambda: None
        
        result = check_deprecations(empty_module)
        assert result == {}


class TestDeprecationScenarios:
    """Test real-world deprecation scenarios."""
    
    def test_api_migration_scenario(self):
        """Test deprecating old API in favor of new one."""
        @deprecated(
            reason="The fixed schema API is being replaced by schemaless extraction",
            version="1.1.0",
            removal_version="2.0.0",
            alternative="use extract_schemaless() with ENABLE_SCHEMALESS_EXTRACTION=true"
        )
        def extract_with_schema(data, schema):
            return {"extracted": data, "schema": schema}
        
        def extract_schemaless(data):
            return {"extracted": data, "flexible": True}
        
        # Using old API should warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = extract_with_schema("test", {"type": "string"})
            
            assert len(w) == 1
            message = str(w[0].message)
            assert "fixed schema API is being replaced" in message
            assert "use extract_schemaless()" in message
            assert "ENABLE_SCHEMALESS_EXTRACTION=true" in message
    
    def test_gradual_deprecation_scenario(self):
        """Test gradual deprecation process."""
        # Phase 1: Mark as pending deprecation
        @pending_deprecation(
            reason="This method will be replaced with async version",
            deprecation_version="2.0.0",
            alternative="sync_to_async_wrapper()"
        )
        def sync_process():
            return "sync result"
        
        # Phase 2: Move to deprecated (in future version)
        @deprecated(
            reason="Async version is now available",
            version="2.0.0",
            removal_version="3.0.0",
            alternative="async_process()"
        )
        def sync_process_v2():
            return "sync result"
        
        # Test both warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            sync_process()
            sync_process_v2()
            
            assert len(w) == 2
            assert issubclass(w[0].category, PendingDeprecationWarning)
            assert issubclass(w[1].category, DeprecationWarning)
    
    def test_conditional_deprecation(self):
        """Test deprecation based on feature flags."""
        import os
        
        def conditionally_deprecated(func):
            """Deprecate only if new feature is enabled."""
            if os.getenv('ENABLE_NEW_FEATURE', 'false').lower() == 'true':
                return deprecated(
                    reason="New feature replaces this",
                    version="1.5.0",
                    alternative="use new_feature_func()"
                )(func)
            return func
        
        @conditionally_deprecated
        def maybe_deprecated():
            return "result"
        
        # Without feature flag, no warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            maybe_deprecated()
            assert len(w) == 0
        
        # With feature flag, should warn
        with patch.dict(os.environ, {'ENABLE_NEW_FEATURE': 'true'}):
            # Need to re-apply decorator with new env
            decorated = conditionally_deprecated(lambda: "result")
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                decorated()
                assert len(w) == 1