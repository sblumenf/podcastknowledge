#!/usr/bin/env python3
"""Performance benchmarking for migration validation.

Compares memory usage, processing speed, and resource utilization
between monolithic and modular implementations.
"""

import argparse
import gc
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Performance monitoring tools
import psutil
import memory_profiler
import cProfile
import pstats
from io import StringIO

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import both versions
from src.api.v1 import seed_podcast as modular_seed_podcast
from src.api.v1 import PodcastKnowledgePipeline as ModularPipeline
from src.core.config import Config


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Benchmark performance between monolithic and modular versions."""
    
    def __init__(self, output_dir: Path):
        """Initialize benchmark suite.
        
        Args:
            output_dir: Directory for benchmark results
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'benchmarks': [],
            'summary': {}
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for benchmark context."""
        return {
            'platform': sys.platform,
            'python_version': sys.version,
            'cpu_count': psutil.cpu_count(),
            'total_memory': psutil.virtual_memory().total / (1024**3),  # GB
            'available_memory': psutil.virtual_memory().available / (1024**3),  # GB
        }
    
    def profile_function(self, func, *args, **kwargs) -> Tuple[Any, Dict[str, Any]]:
        """Profile a function's performance.
        
        Returns:
            Tuple of (result, profile_data)
        """
        # Memory profiling
        gc.collect()
        start_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
        
        # CPU profiling
        profiler = cProfile.Profile()
        
        # Time tracking
        start_time = time.time()
        
        # Execute function
        try:
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()
            success = True
            error = None
        except Exception as e:
            profiler.disable()
            result = None
            success = False
            error = str(e)
            logger.error(f"Function execution failed: {e}")
            traceback.print_exc()
        
        # Collect metrics
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
        
        # Get CPU profile stats
        stats_stream = StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        
        profile_data = {
            'success': success,
            'error': error,
            'execution_time': end_time - start_time,
            'start_memory': start_memory,
            'end_memory': end_memory,
            'memory_used': end_memory - start_memory,
            'peak_memory': max(start_memory, end_memory),
            'cpu_profile': stats_stream.getvalue()
        }
        
        return result, profile_data
    
    def benchmark_memory_usage(self, func, args_list: List[Tuple],
                             name: str) -> Dict[str, Any]:
        """Benchmark memory usage across different input sizes.
        
        Args:
            func: Function to benchmark
            args_list: List of argument tuples for different sizes
            name: Name of the benchmark
        """
        logger.info(f"Running memory benchmark: {name}")
        
        memory_results = {
            'name': name,
            'type': 'memory',
            'measurements': []
        }
        
        for i, args in enumerate(args_list):
            logger.info(f"  Test case {i+1}/{len(args_list)}")
            gc.collect()
            
            # Measure memory usage
            result, profile = self.profile_function(func, *args)
            
            measurement = {
                'test_case': i,
                'args_description': str(args)[:100],
                'memory_used': profile['memory_used'],
                'peak_memory': profile['peak_memory'],
                'execution_time': profile['execution_time'],
                'success': profile['success']
            }
            
            memory_results['measurements'].append(measurement)
            
            # Force garbage collection between tests
            gc.collect()
            time.sleep(0.5)  # Brief pause for system
        
        return memory_results
    
    def benchmark_processing_speed(self, func, args: Tuple,
                                 iterations: int = 5,
                                 name: str = "") -> Dict[str, Any]:
        """Benchmark processing speed with multiple iterations.
        
        Args:
            func: Function to benchmark
            args: Arguments for the function
            iterations: Number of iterations
            name: Name of the benchmark
        """
        logger.info(f"Running speed benchmark: {name}")
        
        speed_results = {
            'name': name,
            'type': 'speed',
            'iterations': iterations,
            'times': [],
            'measurements': []
        }
        
        # Warm-up run
        logger.info("  Warm-up run...")
        self.profile_function(func, *args)
        
        # Actual benchmark runs
        for i in range(iterations):
            logger.info(f"  Iteration {i+1}/{iterations}")
            gc.collect()
            
            result, profile = self.profile_function(func, *args)
            
            speed_results['times'].append(profile['execution_time'])
            speed_results['measurements'].append({
                'iteration': i,
                'execution_time': profile['execution_time'],
                'memory_used': profile['memory_used'],
                'success': profile['success']
            })
            
            time.sleep(0.5)  # Brief pause between iterations
        
        # Calculate statistics
        times = speed_results['times']
        speed_results['statistics'] = {
            'mean': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'std_dev': self._calculate_std_dev(times)
        }
        
        return speed_results
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def benchmark_resource_utilization(self, func, args: Tuple,
                                     name: str = "") -> Dict[str, Any]:
        """Monitor resource utilization during execution.
        
        Args:
            func: Function to benchmark
            args: Arguments for the function
            name: Name of the benchmark
        """
        logger.info(f"Running resource utilization benchmark: {name}")
        
        resource_results = {
            'name': name,
            'type': 'resources',
            'samples': []
        }
        
        # Start monitoring in background
        monitoring = True
        start_time = time.time()
        
        def monitor_resources():
            while monitoring:
                sample = {
                    'time': time.time() - start_time,
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'memory_mb': psutil.Process().memory_info().rss / (1024**2)
                }
                resource_results['samples'].append(sample)
                time.sleep(0.5)
        
        # Run monitoring in thread
        import threading
        monitor_thread = threading.Thread(target=monitor_resources)
        monitor_thread.start()
        
        # Execute function
        result, profile = self.profile_function(func, *args)
        
        # Stop monitoring
        monitoring = False
        monitor_thread.join()
        
        # Add execution info
        resource_results['execution_time'] = profile['execution_time']
        resource_results['success'] = profile['success']
        
        # Calculate peak values
        if resource_results['samples']:
            resource_results['peak_cpu'] = max(
                s['cpu_percent'] for s in resource_results['samples']
            )
            resource_results['peak_memory'] = max(
                s['memory_mb'] for s in resource_results['samples']
            )
        
        return resource_results
    
    def compare_implementations(self, test_configs: List[Dict[str, Any]]):
        """Compare monolithic and modular implementations.
        
        Args:
            test_configs: List of test configurations
        """
        logger.info("Starting implementation comparison...")
        
        comparison_results = []
        
        for config in test_configs:
            logger.info(f"\nTesting: {config.get('name', 'Unknown')}")
            
            comparison = {
                'test_name': config.get('name'),
                'config': config,
                'monolithic': {},
                'modular': {},
                'comparison': {}
            }
            
            # Prepare test functions
            max_episodes = config.get('max_episodes', 1)
            
            # Test monolithic version
            try:
                import podcast_knowledge_system_enhanced as monolith
                
                def run_monolithic():
                    pipeline = monolith.PodcastKnowledgePipeline()
                    return pipeline.seed_podcasts(
                        [config],
                        max_episodes_each=max_episodes
                    )
                
                # Speed benchmark
                mono_speed = self.benchmark_processing_speed(
                    run_monolithic, (),
                    iterations=3,
                    name="Monolithic Speed"
                )
                comparison['monolithic']['speed'] = mono_speed
                
                # Resource benchmark
                mono_resources = self.benchmark_resource_utilization(
                    run_monolithic, (),
                    name="Monolithic Resources"
                )
                comparison['monolithic']['resources'] = mono_resources
                
            except Exception as e:
                logger.error(f"Failed to benchmark monolithic: {e}")
                comparison['monolithic']['error'] = str(e)
            
            # Test modular version
            try:
                def run_modular():
                    return modular_seed_podcast(
                        config,
                        max_episodes=max_episodes
                    )
                
                # Speed benchmark
                mod_speed = self.benchmark_processing_speed(
                    run_modular, (),
                    iterations=3,
                    name="Modular Speed"
                )
                comparison['modular']['speed'] = mod_speed
                
                # Resource benchmark
                mod_resources = self.benchmark_resource_utilization(
                    run_modular, (),
                    name="Modular Resources"
                )
                comparison['modular']['resources'] = mod_resources
                
            except Exception as e:
                logger.error(f"Failed to benchmark modular: {e}")
                comparison['modular']['error'] = str(e)
            
            # Calculate comparison metrics
            if ('speed' in comparison['monolithic'] and 
                'speed' in comparison['modular']):
                
                mono_mean = comparison['monolithic']['speed']['statistics']['mean']
                mod_mean = comparison['modular']['speed']['statistics']['mean']
                
                comparison['comparison'] = {
                    'speedup': mono_mean / mod_mean if mod_mean > 0 else 0,
                    'time_difference': mod_mean - mono_mean,
                    'time_difference_percent': (
                        (mod_mean - mono_mean) / mono_mean * 100
                        if mono_mean > 0 else 0
                    )
                }
                
                if ('resources' in comparison['monolithic'] and 
                    'resources' in comparison['modular']):
                    
                    comparison['comparison']['peak_memory_diff'] = (
                        comparison['modular']['resources'].get('peak_memory', 0) -
                        comparison['monolithic']['resources'].get('peak_memory', 0)
                    )
            
            comparison_results.append(comparison)
        
        self.results['benchmarks'] = comparison_results
        self._generate_summary()
    
    def profile_bottlenecks(self, func, args: Tuple, name: str = ""):
        """Profile to identify performance bottlenecks.
        
        Args:
            func: Function to profile
            args: Arguments for the function
            name: Name of the profile
        """
        logger.info(f"Profiling bottlenecks: {name}")
        
        # Detailed CPU profiling
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = func(*args)
        except Exception as e:
            logger.error(f"Profiling failed: {e}")
            result = None
        finally:
            profiler.disable()
        
        # Save detailed profile
        profile_file = self.output_dir / f"{name.replace(' ', '_')}_profile.prof"
        profiler.dump_stats(str(profile_file))
        
        # Generate readable report
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        
        report_file = self.output_dir / f"{name.replace(' ', '_')}_profile.txt"
        with open(report_file, 'w') as f:
            stats = pstats.Stats(profiler, stream=f)
            stats.sort_stats('cumulative')
            f.write(f"Profile: {name}\n")
            f.write("="*60 + "\n\n")
            stats.print_stats(50)  # Top 50 functions
            
            f.write("\n\nCallers:\n")
            f.write("="*60 + "\n")
            stats.print_callers(20)  # Top 20 callers
        
        logger.info(f"Profile saved to {report_file}")
    
    def _generate_summary(self):
        """Generate summary of benchmark results."""
        summary = {
            'total_benchmarks': len(self.results['benchmarks']),
            'average_speedup': 0,
            'average_memory_difference': 0,
            'modular_faster_count': 0,
            'modular_slower_count': 0
        }
        
        speedups = []
        memory_diffs = []
        
        for benchmark in self.results['benchmarks']:
            if 'comparison' in benchmark and 'speedup' in benchmark['comparison']:
                speedup = benchmark['comparison']['speedup']
                speedups.append(speedup)
                
                if speedup > 1:
                    summary['modular_faster_count'] += 1
                else:
                    summary['modular_slower_count'] += 1
                
                if 'peak_memory_diff' in benchmark['comparison']:
                    memory_diffs.append(benchmark['comparison']['peak_memory_diff'])
        
        if speedups:
            summary['average_speedup'] = sum(speedups) / len(speedups)
        
        if memory_diffs:
            summary['average_memory_difference'] = sum(memory_diffs) / len(memory_diffs)
        
        self.results['summary'] = summary
    
    def save_results(self):
        """Save benchmark results to files."""
        # Save JSON report
        report_file = self.output_dir / 'benchmark_report.json'
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"Report saved to {report_file}")
        
        # Save human-readable summary
        summary_file = self.output_dir / 'benchmark_summary.txt'
        with open(summary_file, 'w') as f:
            f.write("PERFORMANCE BENCHMARK SUMMARY\n")
            f.write("="*60 + "\n\n")
            f.write(f"Timestamp: {self.results['timestamp']}\n")
            f.write(f"System: {self.results['system_info']['platform']}\n")
            f.write(f"CPUs: {self.results['system_info']['cpu_count']}\n")
            f.write(f"Memory: {self.results['system_info']['total_memory']:.1f} GB\n\n")
            
            summary = self.results['summary']
            f.write(f"Total benchmarks: {summary['total_benchmarks']}\n")
            f.write(f"Average speedup: {summary['average_speedup']:.2f}x\n")
            f.write(f"Average memory difference: {summary['average_memory_difference']:.1f} MB\n")
            f.write(f"Modular faster: {summary['modular_faster_count']}\n")
            f.write(f"Modular slower: {summary['modular_slower_count']}\n\n")
            
            # Detailed results
            f.write("DETAILED RESULTS\n")
            f.write("-"*60 + "\n")
            
            for benchmark in self.results['benchmarks']:
                f.write(f"\nTest: {benchmark['test_name']}\n")
                
                if 'comparison' in benchmark:
                    comp = benchmark['comparison']
                    f.write(f"  Speedup: {comp.get('speedup', 'N/A'):.2f}x\n")
                    f.write(f"  Time difference: {comp.get('time_difference', 'N/A'):.2f}s\n")
                    f.write(f"  Memory difference: {comp.get('peak_memory_diff', 'N/A'):.1f} MB\n")
        
        logger.info(f"Summary saved to {summary_file}")
    
    def print_summary(self):
        """Print summary to console."""
        summary = self.results['summary']
        
        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)
        print(f"Total benchmarks: {summary['total_benchmarks']}")
        print(f"Average speedup: {summary['average_speedup']:.2f}x")
        print(f"Average memory difference: {summary['average_memory_difference']:.1f} MB")
        print(f"Modular faster: {summary['modular_faster_count']}")
        print(f"Modular slower: {summary['modular_slower_count']}")
        
        print("\nDETAILED RESULTS:")
        for benchmark in self.results['benchmarks']:
            print(f"\n{benchmark['test_name']}:")
            if 'comparison' in benchmark:
                comp = benchmark['comparison']
                print(f"  Speedup: {comp.get('speedup', 'N/A'):.2f}x")
                print(f"  Time difference: {comp.get('time_difference', 'N/A'):.2f}s "
                      f"({comp.get('time_difference_percent', 0):.1f}%)")


def create_test_configurations(size: str = "small") -> List[Dict[str, Any]]:
    """Create test configurations of different sizes.
    
    Args:
        size: Test size - "small", "medium", or "large"
    """
    base_config = {
        'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
        'category': 'Technology'
    }
    
    if size == "small":
        return [
            {'name': 'Small Test 1', 'max_episodes': 1, **base_config}
        ]
    elif size == "medium":
        return [
            {'name': 'Medium Test 1', 'max_episodes': 3, **base_config},
            {'name': 'Medium Test 2', 'max_episodes': 5, **base_config}
        ]
    else:  # large
        return [
            {'name': 'Large Test 1', 'max_episodes': 10, **base_config},
            {'name': 'Large Test 2', 'max_episodes': 20, **base_config}
        ]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Performance benchmarking for migration validation'
    )
    parser.add_argument(
        '--size',
        choices=['small', 'medium', 'large'],
        default='small',
        help='Test size'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmark_results',
        help='Output directory for results'
    )
    parser.add_argument(
        '--profile-bottlenecks',
        action='store_true',
        help='Run detailed profiling to identify bottlenecks'
    )
    
    args = parser.parse_args()
    
    # Create test configurations
    test_configs = create_test_configurations(args.size)
    
    # Run benchmarks
    benchmark = PerformanceBenchmark(Path(args.output_dir))
    benchmark.compare_implementations(test_configs)
    
    # Profile bottlenecks if requested
    if args.profile_bottlenecks:
        config = test_configs[0]
        
        # Profile modular version
        def run_modular():
            return modular_seed_podcast(config, max_episodes=1)
        
        benchmark.profile_bottlenecks(
            run_modular, (),
            name="Modular_Bottlenecks"
        )
    
    # Save and display results
    benchmark.save_results()
    benchmark.print_summary()


if __name__ == '__main__':
    main()