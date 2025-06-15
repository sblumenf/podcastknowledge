#!/usr/bin/env python3
"""Test core functionality after code duplication refactoring."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_metrics():
    """Test unified metrics system."""
    print("\n=== Testing Metrics System ===")
    try:
        from src.monitoring import (
            Counter, Gauge, Histogram,
            ContentMetricsCalculator,
            get_pipeline_metrics
        )
        
        # Test counter
        counter = Counter("test_counter", "Test counter")
        counter.inc(5)
        assert counter.get() == 5
        print("✅ Counter metrics work")
        
        # Test content metrics
        calc = ContentMetricsCalculator()
        # Test complexity calculation
        complexity = calc.calculate_complexity("This is a test sentence.")
        assert complexity.avg_word_length > 0
        print("✅ Content metrics calculator works")
        
        # Test pipeline metrics
        metrics = get_pipeline_metrics()
        assert metrics is not None
        print("✅ Pipeline metrics accessible")
        
        return True
    except Exception as e:
        print(f"❌ Metrics test failed: {e}")
        return False

def test_dependencies():
    """Test unified dependencies system."""
    print("\n=== Testing Dependencies System ===")
    try:
        from src.core.dependencies import (
            get_dependency,
            is_available,
            get_memory_info,
            get_cpu_info
        )
        
        # Test dependency availability
        psutil_available = is_available('psutil')
        print(f"✅ Psutil available: {psutil_available}")
        
        # Test memory info
        mem = get_memory_info()
        assert 'process_memory_mb' in mem
        print(f"✅ Memory info works: {mem['process_memory_mb']:.1f}MB")
        
        # Test CPU info
        cpu = get_cpu_info()
        assert 'cpu_count' in cpu
        assert 'cpu_percent' in cpu  # This was added in our fix
        print(f"✅ CPU info works: {cpu['cpu_count']} cores")
        
        return True
    except Exception as e:
        print(f"❌ Dependencies test failed: {e}")
        return False

def test_embeddings():
    """Test unified embeddings service."""
    print("\n=== Testing Embeddings Service ===")
    try:
        from src.services.embeddings import (
            GeminiEmbeddingsService,
            create_embeddings_service
        )
        
        # Test service creation (with mock API key)
        service = GeminiEmbeddingsService(api_key="test_key")
        assert service is not None
        print("✅ Embeddings service instantiated")
        
        # Test that service has expected properties
        assert hasattr(service, 'model_name')
        assert hasattr(service, 'dimension')
        assert service.dimension == 768
        print("✅ Embeddings service has correct dimension")
        
        return True
    except Exception as e:
        print(f"❌ Embeddings test failed: {e}")
        return False

def test_storage():
    """Test storage coordination."""
    print("\n=== Testing Storage Coordination ===")
    try:
        from src.storage.base_storage_coordinator import BaseStorageCoordinator
        from src.storage.storage_coordinator import StorageCoordinator
        
        # Test inheritance
        assert issubclass(StorageCoordinator, BaseStorageCoordinator)
        print("✅ Storage inheritance chain works")
        
        return True
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        return False

def test_logging():
    """Test unified logging system."""
    print("\n=== Testing Logging System ===")
    try:
        from src.utils.logging import (
            get_logger,
            setup_logging,
            set_log_level
        )
        
        # Setup logging
        setup_logging()
        
        # Get logger
        logger = get_logger(__name__)
        assert logger is not None
        print("✅ Logger creation works")
        
        # Test log level setting (added in our fix)
        set_log_level("DEBUG")
        print("✅ Log level setting works")
        
        return True
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

def test_resource_monitoring():
    """Test centralized resource monitoring."""
    print("\n=== Testing Resource Monitoring ===")
    try:
        from src.monitoring.resource_monitor import ResourceMonitor
        
        # Test singleton
        monitor1 = ResourceMonitor()
        monitor2 = ResourceMonitor()
        assert monitor1 is monitor2
        print("✅ Resource monitor singleton works")
        
        # Test memory info (added in our fix)
        mem_info = monitor1.get_memory_info()
        assert 'available_memory_mb' in mem_info
        print("✅ Memory info method works")
        
        # Test CPU info (added in our fix)
        cpu_info = monitor1.get_cpu_info()
        assert 'cpu_count' in cpu_info
        print("✅ CPU info method works")
        
        return True
    except Exception as e:
        print(f"❌ Resource monitoring test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("CORE FUNCTIONALITY TEST AFTER REFACTORING")
    print("=" * 60)
    
    tests = [
        test_metrics,
        test_dependencies,
        test_embeddings,
        test_storage,
        test_logging,
        test_resource_monitoring
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL CORE FUNCTIONALITY TESTS PASSED")
        print("The refactoring preserved all core functionality!")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed")
        print("Some functionality may be broken after refactoring.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)