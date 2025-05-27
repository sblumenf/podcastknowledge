#!/usr/bin/env python3
"""
Phase 6 Performance Benchmarks - Compare refactored code performance with baseline.
"""

import sys
import os
import time
import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class PerformanceBenchmark:
    """Run performance benchmarks on refactored components."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'benchmarks': {},
            'summary': {}
        }
        self.baseline_path = Path(__file__).parent.parent / 'tests/benchmarks/baseline_20250526_224713.json'
    
    def load_baseline(self) -> Dict[str, Any]:
        """Load baseline performance metrics."""
        if self.baseline_path.exists():
            with open(self.baseline_path, 'r') as f:
                return json.load(f)
        return {}
    
    def benchmark_function(self, func, name: str, iterations: int = 100) -> Dict[str, float]:
        """Benchmark a function's performance."""
        times = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append(end - start)
        
        return {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
            'min': min(times),
            'max': max(times),
            'iterations': iterations
        }
    
    def test_error_handling_performance(self):
        """Benchmark error handling decorators."""
        print("\n📊 Benchmarking Error Handling Decorators")
        
        from src.utils.error_handling import with_error_handling, retry_on_error
        
        # Test decorator overhead
        def simple_function():
            return sum(range(100))
        
        @with_error_handling(retry_count=0, log_errors=False)
        def decorated_function():
            return sum(range(100))
        
        # Benchmark both
        baseline = self.benchmark_function(simple_function, "simple_function", 1000)
        decorated = self.benchmark_function(decorated_function, "decorated_function", 1000)
        
        overhead_percent = ((decorated['mean'] - baseline['mean']) / baseline['mean']) * 100
        
        self.results['benchmarks']['error_handling_overhead'] = {
            'baseline_mean': baseline['mean'],
            'decorated_mean': decorated['mean'],
            'overhead_percent': overhead_percent
        }
        
        print(f"  Base function: {baseline['mean']*1000:.3f}ms")
        print(f"  With decorator: {decorated['mean']*1000:.3f}ms")
        print(f"  Overhead: {overhead_percent:.1f}%")
    
    def test_logging_performance(self):
        """Benchmark enhanced logging."""
        print("\n📊 Benchmarking Enhanced Logging")
        
        from src.utils.logging_enhanced import get_logger, with_correlation_id, set_correlation_id
        import logging
        
        # Disable actual logging to measure pure overhead
        logging.disable(logging.CRITICAL)
        
        logger = get_logger(__name__)
        
        def standard_logging():
            for i in range(100):
                logger.info(f"Test message {i}")
        
        @with_correlation_id()
        def enhanced_logging():
            for i in range(100):
                logger.info(f"Test message {i}")
        
        # Benchmark
        standard = self.benchmark_function(standard_logging, "standard_logging", 100)
        enhanced = self.benchmark_function(enhanced_logging, "enhanced_logging", 100)
        
        overhead_percent = ((enhanced['mean'] - standard['mean']) / standard['mean']) * 100
        
        self.results['benchmarks']['logging_overhead'] = {
            'standard_mean': standard['mean'],
            'enhanced_mean': enhanced['mean'],
            'overhead_percent': overhead_percent
        }
        
        print(f"  Standard logging: {standard['mean']*1000:.3f}ms")
        print(f"  Enhanced logging: {enhanced['mean']*1000:.3f}ms")
        print(f"  Overhead: {overhead_percent:.1f}%")
        
        # Re-enable logging
        logging.disable(logging.NOTSET)
    
    def test_exception_creation_performance(self):
        """Benchmark new exception types."""
        print("\n📊 Benchmarking Exception Creation")
        
        from src.core.exceptions import (
            ExtractionError, RateLimitError, TimeoutError,
            ResourceError, DataIntegrityError
        )
        
        def create_standard_exception():
            for _ in range(100):
                e = Exception("Test error")
        
        def create_custom_exceptions():
            for _ in range(20):
                e1 = ExtractionError("Extraction failed")
                e2 = RateLimitError("provider", "Rate limited", retry_after=60)
                e3 = TimeoutError("Timeout", operation="test", timeout_seconds=30)
                e4 = ResourceError("Out of memory", resource_type="memory")
                e5 = DataIntegrityError("Corrupt", entity_type="Test", entity_id="123")
        
        # Benchmark
        standard = self.benchmark_function(create_standard_exception, "standard_exception", 100)
        custom = self.benchmark_function(create_custom_exceptions, "custom_exceptions", 100)
        
        self.results['benchmarks']['exception_creation'] = {
            'standard_mean': standard['mean'],
            'custom_mean': custom['mean'],
            'ratio': custom['mean'] / standard['mean']
        }
        
        print(f"  Standard exceptions: {standard['mean']*1000:.3f}ms")
        print(f"  Custom exceptions: {custom['mean']*1000:.3f}ms")
        print(f"  Ratio: {custom['mean']/standard['mean']:.2f}x")
    
    def test_method_refactoring_impact(self):
        """Test impact of method refactoring on import time."""
        print("\n📊 Benchmarking Import Performance")
        
        import importlib
        import sys
        
        def import_component(module_name):
            # Clear from cache if exists
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            start = time.perf_counter()
            importlib.import_module(module_name)
            end = time.perf_counter()
            
            return end - start
        
        # Test components that don't require YAML
        components = [
            'src.utils.error_handling',
            'src.utils.logging_enhanced',
            'src.core.exceptions',
            'src.utils.retry'
        ]
        
        import_times = {}
        for component in components:
            try:
                times = []
                for _ in range(5):
                    times.append(import_component(component))
                import_times[component] = statistics.mean(times)
                print(f"  {component}: {statistics.mean(times)*1000:.2f}ms")
            except Exception as e:
                print(f"  {component}: Failed - {str(e)}")
        
        self.results['benchmarks']['import_times'] = import_times
    
    def test_memory_usage(self):
        """Test memory usage of refactored components."""
        print("\n📊 Testing Memory Usage")
        
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Import and create instances
        from src.utils.error_handling import with_error_handling
        from src.utils.logging_enhanced import get_logger, StandardizedLogger
        from src.core.exceptions import (
            ExtractionError, RateLimitError, TimeoutError,
            ResourceError, DataIntegrityError
        )
        
        # Create many instances
        loggers = [get_logger(f"test.logger.{i}") for i in range(100)]
        exceptions = []
        for i in range(100):
            exceptions.extend([
                ExtractionError(f"Error {i}"),
                RateLimitError("provider", f"Error {i}"),
                TimeoutError(f"Error {i}"),
                ResourceError(f"Error {i}"),
                DataIntegrityError(f"Error {i}")
            ])
        
        # Measure after creation
        after_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = after_memory - baseline_memory
        
        self.results['benchmarks']['memory_usage'] = {
            'baseline_mb': baseline_memory,
            'after_mb': after_memory,
            'increase_mb': memory_increase,
            'objects_created': len(loggers) + len(exceptions)
        }
        
        print(f"  Baseline memory: {baseline_memory:.2f}MB")
        print(f"  After creation: {after_memory:.2f}MB")
        print(f"  Memory increase: {memory_increase:.2f}MB")
        print(f"  Objects created: {len(loggers) + len(exceptions)}")
    
    def compare_with_baseline(self):
        """Compare current results with baseline."""
        print("\n📊 Comparing with Baseline")
        
        baseline = self.load_baseline()
        if not baseline:
            print("  ⚠️  No baseline found for comparison")
            return
        
        # Compare specific metrics if available
        comparisons = {}
        
        # Example comparison (adapt based on actual baseline structure)
        if 'memory_usage' in baseline:
            current_mem = self.results['benchmarks'].get('memory_usage', {}).get('increase_mb', 0)
            baseline_mem = baseline.get('memory_usage', {}).get('total_mb', 0)
            
            if baseline_mem > 0:
                mem_ratio = current_mem / baseline_mem
                comparisons['memory_ratio'] = mem_ratio
                print(f"  Memory usage ratio: {mem_ratio:.2f}x")
        
        self.results['comparisons'] = comparisons
    
    def generate_summary(self):
        """Generate performance summary."""
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        
        # Error handling overhead
        if 'error_handling_overhead' in self.results['benchmarks']:
            overhead = self.results['benchmarks']['error_handling_overhead']['overhead_percent']
            status = "✅" if overhead < 10 else "⚠️" if overhead < 25 else "❌"
            print(f"{status} Error handling overhead: {overhead:.1f}%")
        
        # Logging overhead
        if 'logging_overhead' in self.results['benchmarks']:
            overhead = self.results['benchmarks']['logging_overhead']['overhead_percent']
            status = "✅" if overhead < 20 else "⚠️" if overhead < 50 else "❌"
            print(f"{status} Logging enhancement overhead: {overhead:.1f}%")
        
        # Memory usage
        if 'memory_usage' in self.results['benchmarks']:
            mem_increase = self.results['benchmarks']['memory_usage']['increase_mb']
            status = "✅" if mem_increase < 10 else "⚠️" if mem_increase < 50 else "❌"
            print(f"{status} Memory increase: {mem_increase:.2f}MB")
        
        # Overall assessment
        print("\nOverall Performance Assessment:")
        all_good = all(
            self.results['benchmarks'].get('error_handling_overhead', {}).get('overhead_percent', 100) < 10,
            self.results['benchmarks'].get('logging_overhead', {}).get('overhead_percent', 100) < 20,
            self.results['benchmarks'].get('memory_usage', {}).get('increase_mb', 100) < 10
        )
        
        if all_good:
            print("✅ All performance metrics within acceptable ranges")
            self.results['summary']['status'] = 'PASS'
        else:
            print("⚠️  Some performance metrics need attention")
            self.results['summary']['status'] = 'WARNING'
    
    def save_results(self):
        """Save benchmark results."""
        output_path = Path(__file__).parent / f"phase6_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to: {output_path}")
        return output_path
    
    def run(self):
        """Run all benchmarks."""
        print("="*60)
        print("Phase 6: Performance Benchmarks")
        print("="*60)
        
        try:
            self.test_error_handling_performance()
            self.test_logging_performance()
            self.test_exception_creation_performance()
            self.test_method_refactoring_impact()
            self.test_memory_usage()
            self.compare_with_baseline()
            self.generate_summary()
            return self.save_results()
        except Exception as e:
            print(f"\n❌ Benchmark failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    result_path = benchmark.run()
    sys.exit(0 if result_path else 1)