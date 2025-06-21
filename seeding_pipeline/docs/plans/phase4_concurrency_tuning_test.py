#!/usr/bin/env python3
"""
Phase 4 Task 4.1: Test script for tuning concurrent processing limits.

This script tests different MAX_CONCURRENT_UNITS values (3, 5, 8, 10)
to determine optimal concurrency for the pipeline.
"""

import sys
import os
import time
import statistics
import json
from datetime import datetime
import threading
import psutil

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Set specific concurrency values for testing
test_values = [3, 5, 8, 10]

# Global variables for resource monitoring
resource_monitor_stop = threading.Event()
resource_stats = {}


def monitor_resources(interval=1.0):
    """Monitor CPU and memory usage in a separate thread."""
    process = psutil.Process()
    cpu_samples = []
    memory_samples = []
    
    while not resource_monitor_stop.is_set():
        try:
            # Get current resource usage
            cpu_percent = process.cpu_percent(interval=None)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
            
            cpu_samples.append(cpu_percent)
            memory_samples.append(memory_mb)
            
            time.sleep(interval)
        except Exception as e:
            print(f"Resource monitoring error: {e}")
            break
    
    # Calculate statistics
    if cpu_samples and memory_samples:
        resource_stats['cpu'] = {
            'avg': statistics.mean(cpu_samples),
            'max': max(cpu_samples),
            'min': min(cpu_samples),
            'samples': len(cpu_samples)
        }
        resource_stats['memory'] = {
            'avg_mb': statistics.mean(memory_samples),
            'max_mb': max(memory_samples),
            'min_mb': min(memory_samples),
            'peak_mb': max(memory_samples)
        }


def detect_rate_limit_error(error_msg):
    """Check if error indicates API rate limiting."""
    rate_limit_indicators = [
        'rate limit',
        'too many requests',
        '429',
        'quota exceeded',
        'throttled'
    ]
    return any(indicator in str(error_msg).lower() for indicator in rate_limit_indicators)


def run_single_test(concurrency_value, episode_path):
    """Run a single test with specified concurrency value."""
    # Set environment variable before importing pipeline
    os.environ['MAX_CONCURRENT_UNITS'] = str(concurrency_value)
    
    # Import after setting env var to ensure it takes effect
    from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
    from src.storage.graph_storage import GraphStorageService
    from src.services.llm import LLMService
    from src.services.embeddings import EmbeddingsService
    
    print(f"\n{'='*60}")
    print(f"Testing with MAX_CONCURRENT_UNITS = {concurrency_value}")
    print(f"{'='*60}")
    
    # Initialize services
    graph_storage = GraphStorageService()
    llm_service = LLMService()
    embeddings_service = EmbeddingsService()
    
    # Create pipeline
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=graph_storage,
        llm_service=llm_service,
        embeddings_service=embeddings_service
    )
    
    # Reset resource stats
    global resource_stats, resource_monitor_stop
    resource_stats = {}
    resource_monitor_stop = threading.Event()
    
    # Start resource monitoring thread
    monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
    monitor_thread.start()
    
    # Record start time
    start_time = time.time()
    
    try:
        # Process episode
        result = pipeline.process_episode(episode_path)
        
        # Record end time
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Stop resource monitoring
        resource_monitor_stop.set()
        monitor_thread.join(timeout=2.0)
        
        # Extract unit processing times from logs if available
        unit_times = []
        if 'extraction_metadata' in result and 'unit_processing_times' in result['extraction_metadata']:
            unit_times = result['extraction_metadata']['unit_processing_times']
        
        return {
            'success': True,
            'concurrency': concurrency_value,
            'total_time': processing_time,
            'unit_count': result.get('meaningful_units_count', 0),
            'unit_times': unit_times,
            'cpu_stats': resource_stats.get('cpu', {}),
            'memory_stats': resource_stats.get('memory', {}),
            'errors': []
        }
        
    except Exception as e:
        # Stop resource monitoring
        resource_monitor_stop.set()
        monitor_thread.join(timeout=2.0)
        
        return {
            'success': False,
            'concurrency': concurrency_value,
            'total_time': time.time() - start_time,
            'error': str(e),
            'cpu_stats': resource_stats.get('cpu', {}),
            'memory_stats': resource_stats.get('memory', {}),
            'errors': [str(e)]
        }


def run_concurrency_tests(episode_path, runs_per_value=3):
    """Run tests for all concurrency values with multiple runs each."""
    all_results = {}
    
    for concurrency in test_values:
        print(f"\n\nStarting {runs_per_value} test runs for concurrency={concurrency}")
        run_results = []
        
        for run_num in range(runs_per_value):
            print(f"\nRun {run_num + 1}/{runs_per_value}")
            result = run_single_test(concurrency, episode_path)
            run_results.append(result)
            
            # Brief pause between runs to let system settle
            time.sleep(5)
        
        # Calculate statistics for this concurrency value
        successful_runs = [r for r in run_results if r['success']]
        
        if successful_runs:
            times = [r['total_time'] for r in successful_runs]
            cpu_avgs = [r['cpu_stats'].get('avg', 0) for r in successful_runs if r['cpu_stats']]
            cpu_maxs = [r['cpu_stats'].get('max', 0) for r in successful_runs if r['cpu_stats']]
            mem_avgs = [r['memory_stats'].get('avg_mb', 0) for r in successful_runs if r['memory_stats']]
            mem_peaks = [r['memory_stats'].get('peak_mb', 0) for r in successful_runs if r['memory_stats']]
            
            # Check for rate limit errors
            errors = [r['error'] for r in run_results if not r['success']]
            rate_limit_errors = [e for e in errors if detect_rate_limit_error(e)]
            
            all_results[concurrency] = {
                'runs': len(successful_runs),
                'failures': len(run_results) - len(successful_runs),
                'avg_time': statistics.mean(times),
                'min_time': min(times),
                'max_time': max(times),
                'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
                'avg_units': statistics.mean([r['unit_count'] for r in successful_runs]),
                'avg_cpu': statistics.mean(cpu_avgs) if cpu_avgs else 0,
                'max_cpu': max(cpu_maxs) if cpu_maxs else 0,
                'avg_memory_mb': statistics.mean(mem_avgs) if mem_avgs else 0,
                'peak_memory_mb': max(mem_peaks) if mem_peaks else 0,
                'errors': errors,
                'rate_limit_errors': len(rate_limit_errors)
            }
        else:
            all_results[concurrency] = {
                'runs': 0,
                'failures': len(run_results),
                'errors': [r['error'] for r in run_results]
            }
    
    return all_results


def print_results_summary(results):
    """Print a formatted summary of test results."""
    print("\n\n" + "="*80)
    print("CONCURRENCY TUNING TEST RESULTS SUMMARY")
    print("="*80)
    
    # Performance table header
    print(f"\n{'Concurrency':>12} | {'Runs':>5} | {'Avg Time':>10} | {'Min Time':>10} | {'Max Time':>10} | {'Std Dev':>8} | {'Status':>10}")
    print("-" * 85)
    
    best_concurrency = None
    best_time = float('inf')
    
    for concurrency in sorted(results.keys()):
        data = results[concurrency]
        
        if data['runs'] > 0:
            status = "OK" if data['failures'] == 0 else f"{data['failures']} fails"
            print(f"{concurrency:>12} | {data['runs']:>5} | {data['avg_time']:>10.2f} | {data['min_time']:>10.2f} | {data['max_time']:>10.2f} | {data['std_dev']:>8.2f} | {status:>10}")
            
            if data['avg_time'] < best_time:
                best_time = data['avg_time']
                best_concurrency = concurrency
        else:
            print(f"{concurrency:>12} | {0:>5} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>8} | {'All failed':>10}")
    
    print("\n" + "="*85)
    
    # Resource usage table
    print("\nRESOURCE USAGE SUMMARY")
    print(f"\n{'Concurrency':>12} | {'Avg CPU %':>10} | {'Max CPU %':>10} | {'Avg Mem MB':>12} | {'Peak Mem MB':>12}")
    print("-" * 70)
    
    for concurrency in sorted(results.keys()):
        data = results[concurrency]
        if data['runs'] > 0:
            print(f"{concurrency:>12} | {data.get('avg_cpu', 0):>10.1f} | {data.get('max_cpu', 0):>10.1f} | {data.get('avg_memory_mb', 0):>12.1f} | {data.get('peak_memory_mb', 0):>12.1f}")
    
    print("\n" + "="*85)
    
    if best_concurrency:
        print(f"\nRECOMMENDED SETTING: MAX_CONCURRENT_UNITS = {best_concurrency}")
        print(f"Average processing time: {best_time:.2f} seconds")
        
        # Calculate speedup compared to lowest concurrency
        if 3 in results and results[3]['runs'] > 0:
            speedup = results[3]['avg_time'] / best_time
            print(f"Speedup vs concurrency=3: {speedup:.2fx")
    
    # Print any errors encountered
    print("\n\nERRORS ENCOUNTERED:")
    for concurrency, data in results.items():
        if data.get('errors'):
            print(f"\nConcurrency {concurrency}:")
            for error in data['errors']:
                print(f"  - {error}")
            if data.get('rate_limit_errors', 0) > 0:
                print(f"  ⚠️  {data['rate_limit_errors']} errors were rate limit related")


def save_results(results, output_file):
    """Save detailed results to JSON file."""
    output_data = {
        'test_date': datetime.now().isoformat(),
        'test_values': test_values,
        'results': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")


def main():
    """Main test execution."""
    if len(sys.argv) < 2:
        print("Usage: python phase4_concurrency_tuning_test.py <episode_vtt_path>")
        sys.exit(1)
    
    episode_path = sys.argv[1]
    
    if not os.path.exists(episode_path):
        print(f"Error: Episode file not found: {episode_path}")
        sys.exit(1)
    
    print("Starting Concurrent Processing Tuning Tests")
    print(f"Testing episode: {episode_path}")
    print(f"Concurrency values to test: {test_values}")
    print(f"Runs per value: 3")
    
    # Run tests
    results = run_concurrency_tests(episode_path, runs_per_value=3)
    
    # Print summary
    print_results_summary(results)
    
    # Save detailed results
    output_file = os.path.join(
        os.path.dirname(__file__), 
        f"concurrency_tuning_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    save_results(results, output_file)


if __name__ == "__main__":
    main()