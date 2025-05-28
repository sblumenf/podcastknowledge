#!/usr/bin/env python3
"""
Phase 6 Test Runner - Validates refactored components without pytest.
This script runs tests to ensure all refactored components work correctly.
"""

import sys
import os
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test results
results = {
    'passed': 0,
    'failed': 0,
    'errors': []
}

def test_import(module_path, component_name):
    """Test if a module can be imported successfully."""
    print(f"\n✓ Testing import: {component_name}")
    try:
        __import__(module_path)
        print(f"  ✅ {component_name} imported successfully")
        results['passed'] += 1
        return True
    except Exception as e:
        print(f"  ❌ Failed to import {component_name}: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Import {component_name}: {str(e)}")
        return False

def test_component_initialization():
    """Test initialization of refactored components."""
    print("\n🔍 Testing Component Initialization")
    
    # Test signal manager
    try:
        from src.seeding.components.signal_manager import SignalManager
        sm = SignalManager()
        print("  ✅ SignalManager initialized")
        results['passed'] += 1
    except Exception as e:
        print(f"  ❌ SignalManager failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"SignalManager init: {str(e)}")
    
    # Test checkpoint manager
    try:
        from src.seeding.components.checkpoint_manager import CheckpointManager
        from src.core.config import Config
        config = Config()
        cm = CheckpointManager(config, None)
        print("  ✅ CheckpointManager initialized")
        results['passed'] += 1
    except Exception as e:
        print(f"  ❌ CheckpointManager failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"CheckpointManager init: {str(e)}")
    
    # Test provider coordinator
    try:
        from src.seeding.components.provider_coordinator import ProviderCoordinator
        from src.factories.provider_factory import ProviderFactory
        from src.core.config import Config
        config = Config()
        # We'll test with mock providers
        config.providers = {
            'audio': {'name': 'mock'},
            'llm': {'name': 'mock'},
            'embeddings': {'name': 'mock'},
            'graph': {'name': 'memory'}
        }
        factory = ProviderFactory()
        pc = ProviderCoordinator(factory, config)
        print("  ✅ ProviderCoordinator initialized")
        results['passed'] += 1
    except Exception as e:
        print(f"  ❌ ProviderCoordinator failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"ProviderCoordinator init: {str(e)}")

def test_error_handling_decorators():
    """Test error handling decorators work correctly."""
    print("\n🔍 Testing Error Handling Decorators")
    
    try:
        from src.utils.error_handling import with_error_handling, retry_on_error
        
        # Test basic decorator
        @with_error_handling(retry_count=1, raise_on_failure=False)
        def failing_function():
            raise ValueError("Test error")
        
        result = failing_function()
        assert result is None  # Should return None on failure
        print("  ✅ Error handling decorator works")
        results['passed'] += 1
        
        # Test retry functionality
        counter = {'value': 0}
        
        @retry_on_error(retry_count=2)
        def retry_function():
            counter['value'] += 1
            if counter['value'] < 3:
                raise ValueError("Retry test")
            return "success"
        
        result = retry_function()
        assert result == "success"
        assert counter['value'] == 3
        print("  ✅ Retry decorator works")
        results['passed'] += 1
        
    except Exception as e:
        print(f"  ❌ Error handling test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Error handling: {str(e)}")

def test_enhanced_logging():
    """Test enhanced logging functionality."""
    print("\n🔍 Testing Enhanced Logging")
    
    try:
        from src.utils.logging_enhanced import (
            get_logger, set_correlation_id, get_correlation_id,
            with_correlation_id, StandardizedLogger
        )
        
        # Test correlation ID
        correlation_id = set_correlation_id()
        assert correlation_id is not None
        assert get_correlation_id() == correlation_id
        print("  ✅ Correlation ID functionality works")
        results['passed'] += 1
        
        # Test logger
        logger = get_logger(__name__)
        assert isinstance(logger, StandardizedLogger)
        print("  ✅ StandardizedLogger works")
        results['passed'] += 1
        
        # Test decorator
        @with_correlation_id()
        def test_func():
            return get_correlation_id()
        
        result = test_func()
        assert result is not None
        print("  ✅ Correlation ID decorator works")
        results['passed'] += 1
        
    except Exception as e:
        print(f"  ❌ Enhanced logging test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Enhanced logging: {str(e)}")

def test_exception_hierarchy():
    """Test new exception types."""
    print("\n🔍 Testing Exception Hierarchy")
    
    try:
        from src.core.exceptions import (
            ExtractionError, RateLimitError, TimeoutError,
            ResourceError, DataIntegrityError
        )
        
        # Test each exception type
        exceptions = [
            (ExtractionError, "Extraction failed"),
            (RateLimitError, ("provider", "Rate limit exceeded")),
            (TimeoutError, "Operation timed out"),
            (ResourceError, "Out of memory"),
            (DataIntegrityError, "Data corrupted")
        ]
        
        for exc_class, args in exceptions:
            try:
                if isinstance(args, tuple):
                    raise exc_class(*args)
                else:
                    raise exc_class(args)
            except exc_class as e:
                assert str(e)
                print(f"  ✅ {exc_class.__name__} works correctly")
                results['passed'] += 1
                
    except Exception as e:
        print(f"  ❌ Exception hierarchy test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Exception hierarchy: {str(e)}")

def test_extraction_strategies():
    """Test extraction strategy pattern."""
    print("\n🔍 Testing Extraction Strategies")
    
    try:
        from src.processing.strategies.extraction_factory import ExtractionFactory
        from src.core.config import Config
        
        config = Config()
        config.extraction = {'mode': 'fixed_schema'}
        
        # Test factory creation
        factory = ExtractionFactory(config)
        strategy = factory.create_strategy('fixed_schema')
        assert strategy is not None
        print("  ✅ Fixed schema strategy created")
        results['passed'] += 1
        
        # Test dual mode
        strategy = factory.create_strategy('dual')
        assert strategy is not None
        print("  ✅ Dual mode strategy created")
        results['passed'] += 1
        
    except Exception as e:
        print(f"  ❌ Extraction strategies test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Extraction strategies: {str(e)}")

def test_plugin_discovery():
    """Test plugin discovery system."""
    print("\n🔍 Testing Plugin Discovery")
    
    try:
        from src.core.plugin_discovery import PluginDiscovery, provider_plugin
        
        # Test decorator
        @provider_plugin('test', 'mock', version='1.0.0')
        class TestProvider:
            pass
        
        # Test discovery
        discovery = PluginDiscovery()
        providers = discovery.discover_providers('test')
        print("  ✅ Plugin discovery system works")
        results['passed'] += 1
        
    except Exception as e:
        print(f"  ❌ Plugin discovery test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Plugin discovery: {str(e)}")

def test_refactored_pipeline_executor():
    """Test refactored pipeline executor methods."""
    print("\n🔍 Testing Refactored Pipeline Executor")
    
    try:
        from src.seeding.components.pipeline_executor import PipelineExecutor
        
        # Check method exists and is properly sized
        import inspect
        
        # Get process_episode method
        method = getattr(PipelineExecutor, 'process_episode', None)
        assert method is not None
        
        # Get source lines
        source = inspect.getsource(method)
        lines = source.split('\n')
        
        # Method should be around 30 lines (was 92)
        assert len(lines) < 50, f"process_episode is {len(lines)} lines, should be < 50"
        print(f"  ✅ process_episode refactored to {len(lines)} lines")
        results['passed'] += 1
        
        # Check helper methods exist
        helper_methods = [
            '_is_episode_completed',
            '_download_episode_audio',
            '_add_episode_context',
            '_process_audio_segments',
            '_extract_knowledge',
            '_determine_extraction_mode',
            '_finalize_episode_processing',
            '_cleanup_audio_file'
        ]
        
        for helper in helper_methods:
            assert hasattr(PipelineExecutor, helper), f"Missing helper method: {helper}"
        
        print(f"  ✅ All {len(helper_methods)} helper methods present")
        results['passed'] += 1
        
    except Exception as e:
        print(f"  ❌ Pipeline executor test failed: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Pipeline executor: {str(e)}")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 6: Testing and Validation - Component Tests")
    print("=" * 60)
    
    # Test imports
    print("\n📦 Testing Core Imports")
    modules_to_test = [
        ('src.seeding.components.signal_manager', 'SignalManager'),
        ('src.seeding.components.provider_coordinator', 'ProviderCoordinator'),
        ('src.seeding.components.checkpoint_manager', 'CheckpointManager'),
        ('src.seeding.components.pipeline_executor', 'PipelineExecutor'),
        ('src.seeding.components.storage_coordinator', 'StorageCoordinator'),
        ('src.utils.error_handling', 'Error Handling'),
        ('src.utils.logging_enhanced', 'Enhanced Logging'),
        ('src.core.plugin_discovery', 'Plugin Discovery'),
        ('src.processing.strategies.extraction_factory', 'Extraction Factory'),
    ]
    
    for module, name in modules_to_test:
        test_import(module, name)
    
    # Run component tests
    test_component_initialization()
    test_error_handling_decorators()
    test_enhanced_logging()
    test_exception_hierarchy()
    test_extraction_strategies()
    test_plugin_discovery()
    test_refactored_pipeline_executor()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    
    if results['errors']:
        print("\n🚨 Errors:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print("\n" + "=" * 60)
    
    # Return exit code
    return 0 if results['failed'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())