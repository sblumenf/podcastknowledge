#!/usr/bin/env python3
"""Continuous benchmarking script for CI/CD integration.

This script runs performance benchmarks and tracks metrics over time,
suitable for integration with CI/CD pipelines.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psutil
import matplotlib.pyplot as plt
import pandas as pd

from src.api.v1 import seed_podcast
from src.core.config import Config


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousBenchmark:
    """Continuous benchmarking system."""
    
    def __init__(self, results_dir: Path, history_file: Path):
        """Initialize benchmarking system.
        
        Args:
            results_dir: Directory to store results
            history_file: File to track historical metrics
        """
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.history_file = history_file
        self.history = self.load_history()
        
        # Git info if available
        self.git_info = self._get_git_info()
    
    def _get_git_info(self) -> Dict[str, str]:
        """Get current git information."""
        try:
            import subprocess
            
            def run_git(cmd):
                result = subprocess.run(
                    ['git'] + cmd.split(),
                    capture_output=True,
                    text=True
                )
                return result.stdout.strip() if result.returncode == 0 else None
            
            return {
                'commit': run_git('rev-parse HEAD'),
                'branch': run_git('rev-parse --abbrev-ref HEAD'),
                'author': run_git('log -1 --format=%an'),
                'date': run_git('log -1 --format=%ai'),
                'message': run_git('log -1 --format=%s')
            }
        except Exception:
            return {}
    
    def load_history(self) -> List[Dict[str, Any]]:
        """Load benchmark history."""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_history(self):
        """Save benchmark history."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def run_benchmark_suite(self, config: Config) -> Dict[str, Any]:
        """Run complete benchmark suite.
        
        Args:
            config: Pipeline configuration
            
        Returns:
            Benchmark results
        """
        logger.info("Starting benchmark suite...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'git': self.git_info,
            'system': self._get_system_info(),
            'benchmarks': {}
        }
        
        # Benchmark 1: Single episode processing
        logger.info("Running single episode benchmark...")
        results['benchmarks']['single_episode'] = self._benchmark_single_episode(config)
        
        # Benchmark 2: Batch processing
        logger.info("Running batch processing benchmark...")
        results['benchmarks']['batch_processing'] = self._benchmark_batch_processing(config)
        
        # Benchmark 3: Memory efficiency
        logger.info("Running memory efficiency benchmark...")
        results['benchmarks']['memory_efficiency'] = self._benchmark_memory_efficiency(config)
        
        # Benchmark 4: Concurrent processing
        logger.info("Running concurrent processing benchmark...")
        results['benchmarks']['concurrent'] = self._benchmark_concurrent_processing(config)
        
        # Calculate aggregate metrics
        results['summary'] = self._calculate_summary(results['benchmarks'])
        
        return results
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            'platform': sys.platform,
            'python_version': sys.version.split()[0],
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else None,
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'memory_available_gb': psutil.virtual_memory().available / (1024**3)
        }
    
    def _benchmark_single_episode(self, config: Config) -> Dict[str, Any]:
        """Benchmark single episode processing."""
        podcast = {
            'name': 'Benchmark Single',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Benchmark'
        }
        
        # Warm-up run
        seed_podcast(podcast, max_episodes=1, config=config)
        
        # Actual benchmark
        times = []
        memory_used = []
        
        for i in range(3):
            import gc
            gc.collect()
            
            start_mem = psutil.Process().memory_info().rss / (1024**2)
            start_time = time.time()
            
            result = seed_podcast(podcast, max_episodes=1, config=config)
            
            duration = time.time() - start_time
            end_mem = psutil.Process().memory_info().rss / (1024**2)
            
            times.append(duration)
            memory_used.append(end_mem - start_mem)
        
        return {
            'times': times,
            'avg_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'avg_memory_mb': sum(memory_used) / len(memory_used),
            'success': True
        }
    
    def _benchmark_batch_processing(self, config: Config) -> Dict[str, Any]:
        """Benchmark batch processing."""
        podcast = {
            'name': 'Benchmark Batch',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Benchmark'
        }
        
        batch_sizes = [1, 5, 10]
        results = []
        
        for size in batch_sizes:
            start_time = time.time()
            start_mem = psutil.Process().memory_info().rss / (1024**2)
            
            result = seed_podcast(podcast, max_episodes=size, config=config)
            
            duration = time.time() - start_time
            end_mem = psutil.Process().memory_info().rss / (1024**2)
            
            results.append({
                'batch_size': size,
                'total_time': duration,
                'time_per_episode': duration / size,
                'memory_used_mb': end_mem - start_mem,
                'episodes_processed': result['episodes_processed']
            })
        
        return {
            'batch_results': results,
            'scaling_efficiency': self._calculate_scaling_efficiency(results)
        }
    
    def _calculate_scaling_efficiency(self, results: List[Dict]) -> float:
        """Calculate how well processing scales with batch size."""
        if len(results) < 2:
            return 1.0
        
        # Compare time per episode for different batch sizes
        single = next((r for r in results if r['batch_size'] == 1), None)
        largest = max(results, key=lambda r: r['batch_size'])
        
        if single and largest and single['time_per_episode'] > 0:
            # Efficiency = single episode time / batch episode time
            # Values > 1 mean batch processing is more efficient
            return single['time_per_episode'] / largest['time_per_episode']
        
        return 1.0
    
    def _benchmark_memory_efficiency(self, config: Config) -> Dict[str, Any]:
        """Benchmark memory efficiency."""
        import gc
        
        podcast = {
            'name': 'Benchmark Memory',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Benchmark'
        }
        
        # Process multiple episodes and track memory
        memory_samples = []
        
        for i in range(5):
            gc.collect()
            before = psutil.Process().memory_info().rss / (1024**2)
            
            result = seed_podcast(podcast, max_episodes=1, config=config)
            
            gc.collect()
            after = psutil.Process().memory_info().rss / (1024**2)
            
            memory_samples.append({
                'iteration': i,
                'before_mb': before,
                'after_mb': after,
                'growth_mb': after - before
            })
        
        # Calculate memory leak indicator
        growths = [s['growth_mb'] for s in memory_samples[1:]]  # Skip first
        avg_growth = sum(growths) / len(growths) if growths else 0
        
        return {
            'samples': memory_samples,
            'avg_growth_mb': avg_growth,
            'potential_leak': avg_growth > 5.0,  # Flag if > 5MB growth per iteration
            'final_memory_mb': memory_samples[-1]['after_mb']
        }
    
    def _benchmark_concurrent_processing(self, config: Config) -> Dict[str, Any]:
        """Benchmark concurrent processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def process_single(index: int) -> Dict[str, Any]:
            podcast = {
                'name': f'Concurrent {index}',
                'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                'category': 'Benchmark'
            }
            
            start = time.time()
            result = seed_podcast(podcast, max_episodes=1, config=config)
            duration = time.time() - start
            
            return {
                'index': index,
                'duration': duration,
                'success': result['episodes_processed'] > 0
            }
        
        concurrent_levels = [1, 3, 5]
        results = []
        
        for num_concurrent in concurrent_levels:
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [
                    executor.submit(process_single, i)
                    for i in range(num_concurrent)
                ]
                
                individual_results = []
                for future in as_completed(futures):
                    individual_results.append(future.result())
            
            total_duration = time.time() - start_time
            avg_individual = sum(r['duration'] for r in individual_results) / len(individual_results)
            
            results.append({
                'concurrent_count': num_concurrent,
                'total_duration': total_duration,
                'avg_individual_duration': avg_individual,
                'efficiency': avg_individual / total_duration if total_duration > 0 else 0,
                'all_successful': all(r['success'] for r in individual_results)
            })
        
        return {
            'concurrency_results': results,
            'optimal_concurrency': max(results, key=lambda r: r['efficiency'])['concurrent_count']
        }
    
    def _calculate_summary(self, benchmarks: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary metrics."""
        summary = {
            'single_episode_time': benchmarks['single_episode']['avg_time'],
            'batch_scaling_efficiency': benchmarks['batch_processing']['scaling_efficiency'],
            'memory_leak_detected': benchmarks['memory_efficiency']['potential_leak'],
            'optimal_concurrency': benchmarks['concurrent']['optimal_concurrency']
        }
        
        # Calculate overall score (0-100)
        score = 100
        
        # Deduct for slow processing (baseline: 10s per episode)
        if summary['single_episode_time'] > 10:
            score -= min(20, (summary['single_episode_time'] - 10) * 2)
        
        # Deduct for poor scaling
        if summary['batch_scaling_efficiency'] < 1.2:
            score -= 10
        
        # Deduct for memory leak
        if summary['memory_leak_detected']:
            score -= 20
        
        # Deduct for poor concurrency
        if summary['optimal_concurrency'] < 3:
            score -= 10
        
        summary['overall_score'] = max(0, score)
        
        return summary
    
    def update_history(self, results: Dict[str, Any]):
        """Update benchmark history with new results."""
        # Extract key metrics for history
        history_entry = {
            'timestamp': results['timestamp'],
            'commit': results['git'].get('commit', 'unknown')[:8],
            'branch': results['git'].get('branch', 'unknown'),
            'single_episode_time': results['summary']['single_episode_time'],
            'batch_efficiency': results['summary']['batch_scaling_efficiency'],
            'memory_leak': results['summary']['memory_leak_detected'],
            'overall_score': results['summary']['overall_score']
        }
        
        self.history.append(history_entry)
        
        # Keep only last 100 entries
        self.history = self.history[-100:]
        
        self.save_history()
    
    def generate_report(self, results: Dict[str, Any]) -> Path:
        """Generate benchmark report.
        
        Args:
            results: Benchmark results
            
        Returns:
            Path to report file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.results_dir / f'benchmark_report_{timestamp}.json'
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Generate summary text
        summary_file = self.results_dir / f'benchmark_summary_{timestamp}.txt'
        with open(summary_file, 'w') as f:
            f.write("BENCHMARK SUMMARY\n")
            f.write("="*60 + "\n\n")
            f.write(f"Timestamp: {results['timestamp']}\n")
            f.write(f"Git Commit: {results['git'].get('commit', 'N/A')[:8]}\n")
            f.write(f"Branch: {results['git'].get('branch', 'N/A')}\n\n")
            
            f.write("KEY METRICS:\n")
            f.write("-"*40 + "\n")
            summary = results['summary']
            f.write(f"Single Episode Time: {summary['single_episode_time']:.2f}s\n")
            f.write(f"Batch Scaling Efficiency: {summary['batch_scaling_efficiency']:.2f}x\n")
            f.write(f"Memory Leak Detected: {'Yes' if summary['memory_leak_detected'] else 'No'}\n")
            f.write(f"Optimal Concurrency: {summary['optimal_concurrency']}\n")
            f.write(f"Overall Score: {summary['overall_score']}/100\n")
        
        logger.info(f"Report saved to {report_file}")
        return report_file
    
    def plot_trends(self, output_file: Optional[Path] = None):
        """Plot performance trends over time.
        
        Args:
            output_file: Path to save plot (shows if not provided)
        """
        if len(self.history) < 2:
            logger.warning("Not enough history to plot trends")
            return
        
        # Convert to DataFrame for easier plotting
        df = pd.DataFrame(self.history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle('Performance Trends', fontsize=16)
        
        # Plot 1: Single episode time
        ax1 = axes[0, 0]
        ax1.plot(df['timestamp'], df['single_episode_time'], 'b-o')
        ax1.set_title('Single Episode Processing Time')
        ax1.set_ylabel('Time (seconds)')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Batch efficiency
        ax2 = axes[0, 1]
        ax2.plot(df['timestamp'], df['batch_efficiency'], 'g-o')
        ax2.set_title('Batch Processing Efficiency')
        ax2.set_ylabel('Efficiency Ratio')
        ax2.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Memory leaks
        ax3 = axes[1, 0]
        memory_leak_points = df[df['memory_leak']]
        ax3.scatter(memory_leak_points['timestamp'], 
                   [1] * len(memory_leak_points), 
                   color='red', s=100, label='Memory Leak')
        ax3.set_title('Memory Leak Detection')
        ax3.set_ylim(0, 2)
        ax3.set_yticks([])
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Overall score
        ax4 = axes[1, 1]
        ax4.plot(df['timestamp'], df['overall_score'], 'purple', linewidth=2)
        ax4.fill_between(df['timestamp'], df['overall_score'], alpha=0.3)
        ax4.set_title('Overall Performance Score')
        ax4.set_ylabel('Score (0-100)')
        ax4.set_ylim(0, 100)
        ax4.grid(True, alpha=0.3)
        
        # Format x-axis
        for ax in axes.flat:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            logger.info(f"Trend plot saved to {output_file}")
        else:
            plt.show()
    
    def check_regressions(self, results: Dict[str, Any]) -> List[str]:
        """Check for performance regressions.
        
        Args:
            results: Current benchmark results
            
        Returns:
            List of regression warnings
        """
        if len(self.history) < 5:
            return []  # Not enough history
        
        # Get recent history (last 5 runs)
        recent = self.history[-5:]
        
        # Calculate baselines (average of recent runs)
        baseline_time = sum(h['single_episode_time'] for h in recent) / len(recent)
        baseline_efficiency = sum(h['batch_efficiency'] for h in recent) / len(recent)
        baseline_score = sum(h['overall_score'] for h in recent) / len(recent)
        
        current = results['summary']
        regressions = []
        
        # Check single episode time (20% threshold)
        if current['single_episode_time'] > baseline_time * 1.2:
            regressions.append(
                f"Single episode time regression: "
                f"{current['single_episode_time']:.2f}s vs baseline {baseline_time:.2f}s"
            )
        
        # Check batch efficiency (15% threshold)
        if current['batch_scaling_efficiency'] < baseline_efficiency * 0.85:
            regressions.append(
                f"Batch efficiency regression: "
                f"{current['batch_scaling_efficiency']:.2f} vs baseline {baseline_efficiency:.2f}"
            )
        
        # Check overall score (10 point threshold)
        if current['overall_score'] < baseline_score - 10:
            regressions.append(
                f"Overall score regression: "
                f"{current['overall_score']} vs baseline {baseline_score:.1f}"
            )
        
        # Check for new memory leak
        recent_leaks = sum(1 for h in recent if h['memory_leak'])
        if current['memory_leak_detected'] and recent_leaks == 0:
            regressions.append("New memory leak detected!")
        
        return regressions


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Continuous benchmarking for podcast knowledge graph pipeline'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--results-dir',
        type=str,
        default='benchmark_results',
        help='Directory to store results'
    )
    parser.add_argument(
        '--history-file',
        type=str,
        default='benchmark_history.json',
        help='File to track historical metrics'
    )
    parser.add_argument(
        '--plot-trends',
        action='store_true',
        help='Generate trend plots'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check for regressions (CI mode)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = Config.from_file(args.config)
    else:
        config = Config()
        # Use mock providers for consistent benchmarking
        config.use_mock_providers = True
    
    # Initialize benchmark system
    benchmark = ContinuousBenchmark(
        results_dir=Path(args.results_dir),
        history_file=Path(args.history_file)
    )
    
    if args.plot_trends:
        # Just plot trends and exit
        benchmark.plot_trends()
        return
    
    # Run benchmarks
    logger.info("Running continuous benchmark suite...")
    results = benchmark.run_benchmark_suite(config)
    
    # Check for regressions
    regressions = benchmark.check_regressions(results)
    
    if args.check_only:
        # CI mode - just check for regressions
        if regressions:
            logger.error("Performance regressions detected:")
            for regression in regressions:
                logger.error(f"  - {regression}")
            sys.exit(1)
        else:
            logger.info("No performance regressions detected")
            sys.exit(0)
    
    # Update history
    benchmark.update_history(results)
    
    # Generate report
    report_file = benchmark.generate_report(results)
    
    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)
    print(f"Overall Score: {results['summary']['overall_score']}/100")
    
    if regressions:
        print("\nWARNING - Regressions detected:")
        for regression in regressions:
            print(f"  - {regression}")
    else:
        print("\nNo regressions detected")
    
    print(f"\nFull report: {report_file}")
    
    # Exit with error if score is too low
    if results['summary']['overall_score'] < 70:
        logger.error("Performance score below threshold (70)")
        sys.exit(1)


if __name__ == '__main__':
    main()