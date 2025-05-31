"""Performance regression test suite.

Monitors key performance metrics to catch regressions early.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import gc
import json
import time

import psutil
import pytest

from src.api.v1 import seed_podcast, PodcastKnowledgePipeline
from src.core.config import Config
class PerformanceMetrics:
    """Track performance metrics during tests."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.peak_memory = None
        self.samples = []
    
    def start(self):
        """Start tracking metrics."""
        gc.collect()
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory = self.start_memory
    
    def sample(self):
        """Take a performance sample."""
        current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        self.peak_memory = max(self.peak_memory, current_memory)
        
        sample = {
            'timestamp': time.time() - self.start_time,
            'memory_mb': current_memory,
            'cpu_percent': psutil.Process().cpu_percent(interval=0.1)
        }
        self.samples.append(sample)
    
    def stop(self):
        """Stop tracking and return results."""
        self.end_time = time.time()
        
        return {
            'duration': self.end_time - self.start_time,
            'memory_used': self.peak_memory - self.start_memory,
            'peak_memory': self.peak_memory,
            'start_memory': self.start_memory,
            'samples': self.samples
        }


class TestPerformanceRegression:
    """Test suite for performance regression detection."""
    
    @pytest.fixture
    def baseline_file(self):
        """Path to performance baseline file."""
        return Path(__file__).parent.parent / 'fixtures' / 'performance_baseline.json'
    
    @pytest.fixture
    def test_config(self):
        """Test configuration optimized for performance testing."""
        config = Config()
        # Use in-memory providers for consistent performance
        config.use_mock_providers = True
        return config
    
    def load_baseline(self, baseline_file: Path) -> Dict[str, Any]:
        """Load performance baseline data."""
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_baseline(self, baseline_file: Path, data: Dict[str, Any]):
        """Save performance baseline data."""
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def update_baseline(self, baseline_file: Path, test_name: str, 
                       metrics: Dict[str, Any], force: bool = False):
        """Update baseline with new metrics.
        
        Args:
            baseline_file: Path to baseline file
            test_name: Name of the test
            metrics: Performance metrics
            force: Force update even if regression detected
        """
        baseline = self.load_baseline(baseline_file)
        
        if test_name not in baseline:
            baseline[test_name] = {
                'history': [],
                'current': None
            }
        
        # Add to history
        entry = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }
        baseline[test_name]['history'].append(entry)
        
        # Keep only last 10 entries
        baseline[test_name]['history'] = baseline[test_name]['history'][-10:]
        
        # Update current if first run or forced
        if baseline[test_name]['current'] is None or force:
            baseline[test_name]['current'] = metrics
        
        self.save_baseline(baseline_file, baseline)
    
    def check_regression(self, current: Dict[str, float], 
                        baseline: Dict[str, float],
                        thresholds: Dict[str, float]) -> List[str]:
        """Check for performance regressions.
        
        Args:
            current: Current metrics
            baseline: Baseline metrics
            thresholds: Acceptable variance thresholds (as ratios)
            
        Returns:
            List of regression descriptions
        """
        regressions = []
        
        for metric, threshold in thresholds.items():
            if metric in current and metric in baseline:
                current_val = current[metric]
                baseline_val = baseline[metric]
                
                # Calculate ratio (higher is worse for time/memory)
                if baseline_val > 0:
                    ratio = current_val / baseline_val
                    
                    if ratio > threshold:
                        regressions.append(
                            f"{metric}: {current_val:.2f} vs baseline {baseline_val:.2f} "
                            f"({ratio:.2f}x, threshold {threshold}x)"
                        )
        
        return regressions
    
    @pytest.mark.performance
    def test_single_episode_performance(self, test_config, baseline_file):
        """Test performance for processing a single episode."""
        # Test data
        podcast = {
            'name': 'Performance Test',
            'rss_url': 'test://performance',
            'category': 'Test'
        }
        
        # Track metrics
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Process episode
        result = seed_podcast(
            podcast,
            max_episodes=1,
            config=test_config
        )
        
        # Stop tracking
        perf_data = metrics.stop()
        
        # Prepare metrics
        current_metrics = {
            'duration': perf_data['duration'],
            'memory_used': perf_data['memory_used'],
            'peak_memory': perf_data['peak_memory']
        }
        
        # Load baseline
        baseline = self.load_baseline(baseline_file)
        test_baseline = baseline.get('single_episode', {}).get('current')
        
        if test_baseline:
            # Check for regressions
            thresholds = {
                'duration': 1.2,      # Allow 20% slower
                'memory_used': 1.3,   # Allow 30% more memory
                'peak_memory': 1.3    # Allow 30% higher peak
            }
            
            regressions = self.check_regression(
                current_metrics,
                test_baseline,
                thresholds
            )
            
            # Fail if regressions detected
            if regressions:
                pytest.fail(
                    "Performance regressions detected:\n" + 
                    "\n".join(regressions)
                )
        
        # Update baseline (only if no regressions or first run)
        self.update_baseline(baseline_file, 'single_episode', current_metrics)
    
    @pytest.mark.performance
    def test_batch_processing_performance(self, test_config, baseline_file):
        """Test performance for batch processing multiple episodes."""
        # Test data
        podcast = {
            'name': 'Batch Performance Test',
            'rss_url': 'test://performance/batch',
            'category': 'Test'
        }
        
        # Track metrics
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Process batch
        result = seed_podcast(
            podcast,
            max_episodes=10,
            config=test_config
        )
        
        # Stop tracking
        perf_data = metrics.stop()
        
        # Calculate per-episode metrics
        episodes_processed = result.get('episodes_processed', 1)
        current_metrics = {
            'total_duration': perf_data['duration'],
            'duration_per_episode': perf_data['duration'] / episodes_processed,
            'memory_used': perf_data['memory_used'],
            'peak_memory': perf_data['peak_memory']
        }
        
        # Load baseline
        baseline = self.load_baseline(baseline_file)
        test_baseline = baseline.get('batch_processing', {}).get('current')
        
        if test_baseline:
            # Check for regressions
            thresholds = {
                'duration_per_episode': 1.15,  # Allow 15% slower per episode
                'memory_used': 1.4,            # Allow 40% more memory
                'peak_memory': 1.4             # Allow 40% higher peak
            }
            
            regressions = self.check_regression(
                current_metrics,
                test_baseline,
                thresholds
            )
            
            if regressions:
                pytest.fail(
                    "Performance regressions detected:\n" + 
                    "\n".join(regressions)
                )
        
        # Update baseline
        self.update_baseline(baseline_file, 'batch_processing', current_metrics)
    
    @pytest.mark.performance
    def test_memory_leak_detection(self, test_config):
        """Test for memory leaks during repeated operations."""
        podcast = {
            'name': 'Memory Leak Test',
            'rss_url': 'test://memory',
            'category': 'Test'
        }
        
        # Track memory over multiple iterations
        memory_samples = []
        
        for i in range(5):
            gc.collect()
            
            # Measure before
            before = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # Process episode
            result = seed_podcast(
                podcast,
                max_episodes=1,
                config=test_config
            )
            
            # Force cleanup
            gc.collect()
            time.sleep(0.5)
            
            # Measure after
            after = psutil.Process().memory_info().rss / (1024 * 1024)
            
            memory_samples.append({
                'iteration': i,
                'before': before,
                'after': after,
                'growth': after - before
            })
        
        # Check for consistent memory growth
        growths = [s['growth'] for s in memory_samples[1:]]  # Skip first
        avg_growth = sum(growths) / len(growths) if growths else 0
        
        # Fail if average growth > 5MB per iteration
        assert avg_growth < 5.0, \
            f"Potential memory leak detected: {avg_growth:.2f} MB growth per iteration"
    
    @pytest.mark.performance
    def test_concurrent_performance(self, test_config, baseline_file):
        """Test performance under concurrent load."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        num_concurrent = 3
        
        def process_podcast(index: int) -> Dict[str, Any]:
            podcast = {
                'name': f'Concurrent Test {index}',
                'rss_url': f'test://concurrent/{index}',
                'category': 'Test'
            }
            
            start_time = time.time()
            result = seed_podcast(
                podcast,
                max_episodes=1,
                config=test_config
            )
            duration = time.time() - start_time
            
            return {
                'index': index,
                'duration': duration,
                'success': result['episodes_processed'] > 0
            }
        
        # Track overall metrics
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [
                executor.submit(process_podcast, i)
                for i in range(num_concurrent)
            ]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        # Stop tracking
        perf_data = metrics.stop()
        
        # Calculate metrics
        total_duration = perf_data['duration']
        individual_durations = [r['duration'] for r in results]
        avg_individual = sum(individual_durations) / len(individual_durations)
        
        current_metrics = {
            'total_duration': total_duration,
            'avg_individual_duration': avg_individual,
            'concurrency_efficiency': avg_individual / total_duration,
            'peak_memory': perf_data['peak_memory']
        }
        
        # Load baseline
        baseline = self.load_baseline(baseline_file)
        test_baseline = baseline.get('concurrent_performance', {}).get('current')
        
        if test_baseline:
            # Check for regressions
            thresholds = {
                'avg_individual_duration': 1.3,  # Allow 30% slower
                'concurrency_efficiency': 0.7,   # Minimum efficiency
                'peak_memory': 1.5              # Allow 50% more memory
            }
            
            # Special check for efficiency
            if current_metrics['concurrency_efficiency'] < thresholds['concurrency_efficiency']:
                pytest.fail(
                    f"Concurrency efficiency too low: "
                    f"{current_metrics['concurrency_efficiency']:.2f} < "
                    f"{thresholds['concurrency_efficiency']}"
                )
            
            regressions = self.check_regression(
                current_metrics,
                test_baseline,
                {'avg_individual_duration': thresholds['avg_individual_duration'],
                 'peak_memory': thresholds['peak_memory']}
            )
            
            if regressions:
                pytest.fail(
                    "Performance regressions detected:\n" + 
                    "\n".join(regressions)
                )
        
        # Update baseline
        self.update_baseline(baseline_file, 'concurrent_performance', current_metrics)
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_scaling_performance(self, test_config, baseline_file):
        """Test how performance scales with input size."""
        sizes = [1, 5, 10, 20]
        results = []
        
        for size in sizes:
            podcast = {
                'name': f'Scaling Test {size}',
                'rss_url': 'test://scaling',
                'category': 'Test'
            }
            
            # Track metrics
            metrics = PerformanceMetrics()
            metrics.start()
            
            # Process episodes
            result = seed_podcast(
                podcast,
                max_episodes=size,
                config=test_config
            )
            
            # Stop tracking
            perf_data = metrics.stop()
            
            results.append({
                'size': size,
                'duration': perf_data['duration'],
                'memory_used': perf_data['memory_used'],
                'duration_per_episode': perf_data['duration'] / size
            })
        
        # Check scaling characteristics
        # Duration should scale roughly linearly
        for i in range(1, len(results)):
            prev = results[i-1]
            curr = results[i]
            
            # Calculate scaling factor
            size_ratio = curr['size'] / prev['size']
            duration_ratio = curr['duration'] / prev['duration']
            
            # Allow sub-linear scaling (good) but flag super-linear (bad)
            # Threshold: no worse than O(n^1.2)
            max_ratio = size_ratio ** 1.2
            
            assert duration_ratio <= max_ratio, \
                f"Poor scaling detected: {prev['size']} -> {curr['size']} episodes " \
                f"increased time by {duration_ratio:.2f}x (max allowed: {max_ratio:.2f}x)"
        
        # Save scaling results
        current_metrics = {
            'scaling_results': results,
            'timestamp': datetime.now().isoformat()
        }
        
        self.update_baseline(baseline_file, 'scaling_performance', current_metrics)
    
    def generate_performance_report(self, baseline_file: Path, output_file: Path):
        """Generate a performance trend report.
        
        This is a utility method for analyzing performance over time.
        """
        baseline = self.load_baseline(baseline_file)
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'tests': {}
        }
        
        for test_name, test_data in baseline.items():
            if 'history' not in test_data:
                continue
            
            history = test_data['history']
            if not history:
                continue
            
            # Analyze trends
            metrics_over_time = {}
            
            for entry in history:
                timestamp = entry['timestamp']
                for metric, value in entry['metrics'].items():
                    if metric not in metrics_over_time:
                        metrics_over_time[metric] = []
                    metrics_over_time[metric].append({
                        'timestamp': timestamp,
                        'value': value
                    })
            
            # Calculate trends
            trends = {}
            for metric, values in metrics_over_time.items():
                if len(values) >= 2:
                    first_val = values[0]['value']
                    last_val = values[-1]['value']
                    
                    if first_val > 0:
                        change_percent = ((last_val - first_val) / first_val) * 100
                        trends[metric] = {
                            'first': first_val,
                            'last': last_val,
                            'change_percent': change_percent,
                            'direction': 'improved' if change_percent < 0 else 'degraded'
                        }
            
            report['tests'][test_name] = {
                'current': test_data.get('current'),
                'trends': trends,
                'history_length': len(history)
            }
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report