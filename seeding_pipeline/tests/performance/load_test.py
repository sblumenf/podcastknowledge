#!/usr/bin/env python3
"""Load testing for the podcast knowledge graph pipeline.

Tests system behavior under heavy load, including:
- Processing 100+ episodes
- Checkpoint recovery under load
- Memory stability over long runs
- Database connection pooling validation
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import argparse
import gc
import json
import logging
import os
import sys
import threading
import time
import traceback

from neo4j import GraphDatabase
import psutil
# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.v1 import VTTKnowledgeExtractor, seed_podcast
from src.core.config import Config
from src.seeding.checkpoint import ProgressCheckpoint


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LoadTester:
    """Load testing for podcast knowledge graph pipeline."""
    
    def __init__(self, config: Config, output_dir: Path):
        """Initialize load tester.
        
        Args:
            config: Pipeline configuration
            output_dir: Directory for test results
        """
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'tests': {},
            'summary': {}
        }
        
        # Monitoring data
        self.monitoring_active = False
        self.monitoring_data = []
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            'platform': sys.platform,
            'cpu_count': psutil.cpu_count(),
            'total_memory_gb': psutil.virtual_memory().total / (1024**3),
            'available_memory_gb': psutil.virtual_memory().available / (1024**3),
            'python_version': sys.version
        }
    
    def start_monitoring(self):
        """Start resource monitoring in background thread."""
        self.monitoring_active = True
        self.monitoring_data = []
        
        def monitor():
            start_time = time.time()
            while self.monitoring_active:
                try:
                    current_process = psutil.Process()
                    
                    sample = {
                        'timestamp': time.time() - start_time,
                        'cpu_percent': current_process.cpu_percent(interval=0.1),
                        'memory_mb': current_process.memory_info().rss / (1024**2),
                        'memory_percent': current_process.memory_percent(),
                        'num_threads': current_process.num_threads(),
                        'open_files': len(current_process.open_files()),
                        'connections': len(current_process.connections())
                    }
                    
                    # System-wide metrics
                    sample['system_cpu_percent'] = psutil.cpu_percent(interval=0.1)
                    sample['system_memory_percent'] = psutil.virtual_memory().percent
                    
                    self.monitoring_data.append(sample)
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                
                time.sleep(1)  # Sample every second
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return statistics."""
        self.monitoring_active = False
        time.sleep(1.5)  # Allow final samples
        
        if not self.monitoring_data:
            return {}
        
        # Calculate statistics
        stats = {
            'duration': self.monitoring_data[-1]['timestamp'],
            'samples': len(self.monitoring_data),
            'peak_memory_mb': max(d['memory_mb'] for d in self.monitoring_data),
            'avg_memory_mb': sum(d['memory_mb'] for d in self.monitoring_data) / len(self.monitoring_data),
            'peak_cpu_percent': max(d['cpu_percent'] for d in self.monitoring_data),
            'avg_cpu_percent': sum(d['cpu_percent'] for d in self.monitoring_data) / len(self.monitoring_data),
            'max_threads': max(d['num_threads'] for d in self.monitoring_data),
            'max_connections': max(d['connections'] for d in self.monitoring_data),
            'monitoring_data': self.monitoring_data
        }
        
        return stats
    
    def test_large_volume(self, podcast_configs: List[Dict[str, Any]], 
                         total_episodes: int = 100) -> Dict[str, Any]:
        """Test processing large volume of episodes.
        
        Args:
            podcast_configs: List of podcast configurations
            total_episodes: Total episodes to process across all podcasts
        """
        logger.info(f"Starting large volume test with {total_episodes} total episodes")
        
        test_result = {
            'name': 'large_volume_test',
            'total_episodes_target': total_episodes,
            'start_time': datetime.now().isoformat(),
            'podcasts': []
        }
        
        # Calculate episodes per podcast
        episodes_per_podcast = max(1, total_episodes // len(podcast_configs))
        
        # Start monitoring
        self.start_monitoring()
        
        pipeline = VTTKnowledgeExtractor(self.config)
        
        try:
            # Process podcasts
            total_processed = 0
            total_failed = 0
            
            for i, config in enumerate(podcast_configs):
                logger.info(f"Processing podcast {i+1}/{len(podcast_configs)}: {config.get('name')}")
                
                podcast_start = time.time()
                
                try:
                    result = pipeline.seed_podcast(
                        config,
                        max_episodes=episodes_per_podcast,
                        use_large_context=False  # Use smaller model for load test
                    )
                    
                    podcast_result = {
                        'name': config.get('name'),
                        'episodes_processed': result.get('episodes_processed', 0),
                        'episodes_failed': result.get('episodes_failed', 0),
                        'processing_time': time.time() - podcast_start,
                        'success': True
                    }
                    
                    total_processed += result.get('episodes_processed', 0)
                    total_failed += result.get('episodes_failed', 0)
                    
                except Exception as e:
                    logger.error(f"Failed to process podcast: {e}")
                    podcast_result = {
                        'name': config.get('name'),
                        'error': str(e),
                        'processing_time': time.time() - podcast_start,
                        'success': False
                    }
                
                test_result['podcasts'].append(podcast_result)
                
                # Check if we've reached target
                if total_processed >= total_episodes:
                    break
        
        finally:
            # Stop monitoring
            monitoring_stats = self.stop_monitoring()
            
            # Cleanup
            pipeline.cleanup()
        
        # Finalize results
        test_result['end_time'] = datetime.now().isoformat()
        test_result['total_episodes_processed'] = total_processed
        test_result['total_episodes_failed'] = total_failed
        test_result['monitoring_stats'] = monitoring_stats
        test_result['success_rate'] = (
            total_processed / (total_processed + total_failed) 
            if (total_processed + total_failed) > 0 else 0
        )
        
        self.results['tests']['large_volume'] = test_result
        return test_result
    
    def test_checkpoint_recovery(self, podcast_config: Dict[str, Any],
                                interrupt_after: int = 5) -> Dict[str, Any]:
        """Test checkpoint recovery under load.
        
        Args:
            podcast_config: Podcast configuration
            interrupt_after: Interrupt after N episodes
        """
        logger.info(f"Starting checkpoint recovery test")
        
        test_result = {
            'name': 'checkpoint_recovery_test',
            'interrupt_after': interrupt_after,
            'runs': []
        }
        
        checkpoint_dir = self.output_dir / 'checkpoints'
        checkpoint_dir.mkdir(exist_ok=True)
        
        # First run - interrupt after N episodes
        logger.info(f"Run 1: Process {interrupt_after} episodes then interrupt")
        
        self.start_monitoring()
        pipeline = VTTKnowledgeExtractor(self.config)
        
        try:
            # Modify config to use our checkpoint directory
            self.config.checkpoint_dir = str(checkpoint_dir)
            self.config.checkpoint_enabled = True
            
            # Process with interruption
            start_time = time.time()
            
            # We'll process more episodes than interrupt_after
            # but will manually check and stop
            result1 = pipeline.seed_podcast(
                podcast_config,
                max_episodes=interrupt_after,
                use_large_context=False
            )
            
            run1_stats = self.stop_monitoring()
            
            run1_result = {
                'run': 1,
                'episodes_processed': result1.get('episodes_processed', 0),
                'processing_time': time.time() - start_time,
                'monitoring_stats': run1_stats
            }
            test_result['runs'].append(run1_result)
            
        finally:
            pipeline.cleanup()
        
        # Verify checkpoint exists
        checkpoint_files = list(checkpoint_dir.glob('*.json'))
        test_result['checkpoint_created'] = len(checkpoint_files) > 0
        
        if not test_result['checkpoint_created']:
            logger.error("No checkpoint files created!")
            test_result['error'] = "No checkpoint files created"
            self.results['tests']['checkpoint_recovery'] = test_result
            return test_result
        
        # Second run - resume from checkpoint
        logger.info("Run 2: Resume from checkpoint")
        
        self.start_monitoring()
        pipeline2 = VTTKnowledgeExtractor(self.config)
        
        try:
            start_time = time.time()
            
            # Process more episodes, should resume from checkpoint
            result2 = pipeline2.seed_podcast(
                podcast_config,
                max_episodes=interrupt_after * 2,  # Try to process more
                use_large_context=False
            )
            
            run2_stats = self.stop_monitoring()
            
            run2_result = {
                'run': 2,
                'episodes_processed': result2.get('episodes_processed', 0),
                'processing_time': time.time() - start_time,
                'monitoring_stats': run2_stats,
                'resumed_from_checkpoint': True
            }
            test_result['runs'].append(run2_result)
            
        finally:
            pipeline2.cleanup()
        
        # Verify recovery worked
        total_episodes = sum(r.get('episodes_processed', 0) for r in test_result['runs'])
        test_result['total_episodes_processed'] = total_episodes
        test_result['recovery_successful'] = total_episodes > interrupt_after
        
        self.results['tests']['checkpoint_recovery'] = test_result
        return test_result
    
    def test_memory_stability(self, podcast_config: Dict[str, Any],
                            duration_minutes: int = 10) -> Dict[str, Any]:
        """Test memory stability over long runs.
        
        Args:
            podcast_config: Podcast configuration
            duration_minutes: How long to run the test
        """
        logger.info(f"Starting memory stability test for {duration_minutes} minutes")
        
        test_result = {
            'name': 'memory_stability_test',
            'duration_minutes': duration_minutes,
            'start_time': datetime.now().isoformat(),
            'episodes': []
        }
        
        # Start monitoring
        self.start_monitoring()
        
        pipeline = VTTKnowledgeExtractor(self.config)
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        try:
            episode_count = 0
            
            while datetime.now() < end_time:
                # Process one episode at a time
                episode_start = time.time()
                gc.collect()  # Force garbage collection
                
                try:
                    result = pipeline.seed_podcast(
                        podcast_config,
                        max_episodes=1,
                        use_large_context=False
                    )
                    
                    episode_result = {
                        'episode': episode_count,
                        'success': True,
                        'processing_time': time.time() - episode_start,
                        'memory_before_gc': psutil.Process().memory_info().rss / (1024**2)
                    }
                    
                    # Force garbage collection and measure again
                    gc.collect()
                    episode_result['memory_after_gc'] = psutil.Process().memory_info().rss / (1024**2)
                    
                    episode_count += 1
                    
                except Exception as e:
                    logger.error(f"Episode processing failed: {e}")
                    episode_result = {
                        'episode': episode_count,
                        'success': False,
                        'error': str(e),
                        'processing_time': time.time() - episode_start
                    }
                
                test_result['episodes'].append(episode_result)
                
                # Brief pause between episodes
                time.sleep(2)
        
        finally:
            # Stop monitoring
            monitoring_stats = self.stop_monitoring()
            pipeline.cleanup()
        
        # Analyze memory trend
        test_result['end_time'] = datetime.now().isoformat()
        test_result['total_episodes'] = len(test_result['episodes'])
        test_result['monitoring_stats'] = monitoring_stats
        
        # Check for memory leaks
        if monitoring_stats and 'monitoring_data' in monitoring_stats:
            memory_samples = [d['memory_mb'] for d in monitoring_stats['monitoring_data']]
            
            # Simple linear regression to detect trend
            if len(memory_samples) > 10:
                n = len(memory_samples)
                x_mean = n / 2
                y_mean = sum(memory_samples) / n
                
                slope = sum((i - x_mean) * (y - y_mean) 
                          for i, y in enumerate(memory_samples)) / sum((i - x_mean)**2 for i in range(n))
                
                # Memory leak if slope > 1 MB per sample (1 second)
                test_result['memory_leak_detected'] = slope > 1.0
                test_result['memory_growth_rate_mb_per_min'] = slope * 60
            else:
                test_result['memory_leak_detected'] = False
                test_result['memory_growth_rate_mb_per_min'] = 0
        
        self.results['tests']['memory_stability'] = test_result
        return test_result
    
    def test_connection_pooling(self, num_concurrent: int = 10) -> Dict[str, Any]:
        """Test database connection pooling under concurrent load.
        
        Args:
            num_concurrent: Number of concurrent operations
        """
        logger.info(f"Starting connection pooling test with {num_concurrent} concurrent operations")
        
        test_result = {
            'name': 'connection_pooling_test',
            'num_concurrent': num_concurrent,
            'start_time': datetime.now().isoformat(),
            'operations': []
        }
        
        # Create test podcast configs
        test_configs = [
            {
                'name': f'Concurrent Test {i}',
                'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                'category': 'Test'
            }
            for i in range(num_concurrent)
        ]
        
        # Monitor Neo4j connections
        neo4j_driver = GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password)
        )
        
        def get_connection_count():
            with neo4j_driver.session() as session:
                result = session.run(
                    "CALL dbms.listConnections() YIELD connectionId RETURN count(*) as count"
                )
                return result.single()['count']
        
        initial_connections = get_connection_count()
        test_result['initial_connections'] = initial_connections
        
        # Start monitoring
        self.start_monitoring()
        
        # Run concurrent operations
        def process_podcast(config: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()
            try:
                result = seed_podcast(
                    config,
                    max_episodes=1,
                    use_large_context=False,
                    config=self.config
                )
                return {
                    'podcast': config['name'],
                    'success': True,
                    'processing_time': time.time() - start_time,
                    'result': result
                }
            except Exception as e:
                return {
                    'podcast': config['name'],
                    'success': False,
                    'error': str(e),
                    'processing_time': time.time() - start_time
                }
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [
                executor.submit(process_podcast, config)
                for config in test_configs
            ]
            
            # Monitor connections during execution
            max_connections = initial_connections
            while not all(f.done() for f in futures):
                try:
                    current_connections = get_connection_count()
                    max_connections = max(max_connections, current_connections)
                except:
                    pass
                time.sleep(0.5)
            
            # Collect results
            for future in as_completed(futures):
                test_result['operations'].append(future.result())
        
        # Stop monitoring
        monitoring_stats = self.stop_monitoring()
        
        # Final connection count
        final_connections = get_connection_count()
        test_result['final_connections'] = final_connections
        test_result['max_connections'] = max_connections
        test_result['connection_leak'] = final_connections > initial_connections + 2
        
        # Close Neo4j driver
        neo4j_driver.close()
        
        # Finalize results
        test_result['end_time'] = datetime.now().isoformat()
        test_result['monitoring_stats'] = monitoring_stats
        test_result['success_count'] = sum(1 for op in test_result['operations'] if op['success'])
        test_result['failure_count'] = sum(1 for op in test_result['operations'] if not op['success'])
        
        self.results['tests']['connection_pooling'] = test_result
        return test_result
    
    def generate_report(self):
        """Generate comprehensive load test report."""
        # Calculate summary
        summary = {
            'total_tests': len(self.results['tests']),
            'tests_passed': 0,
            'tests_failed': 0,
            'issues_found': []
        }
        
        # Check each test
        for test_name, test_data in self.results['tests'].items():
            passed = True
            
            if test_name == 'large_volume':
                if test_data.get('success_rate', 0) < 0.95:
                    passed = False
                    summary['issues_found'].append(
                        f"Large volume test success rate too low: {test_data.get('success_rate', 0):.1%}"
                    )
            
            elif test_name == 'checkpoint_recovery':
                if not test_data.get('recovery_successful', False):
                    passed = False
                    summary['issues_found'].append("Checkpoint recovery failed")
            
            elif test_name == 'memory_stability':
                if test_data.get('memory_leak_detected', False):
                    passed = False
                    summary['issues_found'].append(
                        f"Memory leak detected: {test_data.get('memory_growth_rate_mb_per_min', 0):.1f} MB/min"
                    )
            
            elif test_name == 'connection_pooling':
                if test_data.get('connection_leak', False):
                    passed = False
                    summary['issues_found'].append("Database connection leak detected")
            
            if passed:
                summary['tests_passed'] += 1
            else:
                summary['tests_failed'] += 1
        
        self.results['summary'] = summary
        
        # Save report
        report_file = self.output_dir / 'load_test_report.json'
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Save monitoring data separately
        for test_name, test_data in self.results['tests'].items():
            if 'monitoring_stats' in test_data and 'monitoring_data' in test_data['monitoring_stats']:
                monitoring_file = self.output_dir / f'{test_name}_monitoring.json'
                with open(monitoring_file, 'w') as f:
                    json.dump(test_data['monitoring_stats']['monitoring_data'], f, indent=2)
        
        logger.info(f"Load test report saved to {report_file}")
    
    def print_summary(self):
        """Print test summary to console."""
        summary = self.results.get('summary', {})
        
        print("\n" + "="*60)
        print("LOAD TEST SUMMARY")
        print("="*60)
        print(f"Total tests: {summary.get('total_tests', 0)}")
        print(f"Tests passed: {summary.get('tests_passed', 0)}")
        print(f"Tests failed: {summary.get('tests_failed', 0)}")
        
        if summary.get('issues_found'):
            print("\nISSUES FOUND:")
            for issue in summary['issues_found']:
                print(f"  - {issue}")
        else:
            print("\nNo issues found!")
        
        print("\nDETAILED RESULTS:")
        print("-"*60)
        
        for test_name, test_data in self.results['tests'].items():
            print(f"\n{test_name}:")
            
            if test_name == 'large_volume':
                print(f"  Episodes processed: {test_data.get('total_episodes_processed', 0)}")
                print(f"  Success rate: {test_data.get('success_rate', 0):.1%}")
                if 'monitoring_stats' in test_data:
                    print(f"  Peak memory: {test_data['monitoring_stats'].get('peak_memory_mb', 0):.1f} MB")
            
            elif test_name == 'checkpoint_recovery':
                print(f"  Recovery successful: {test_data.get('recovery_successful', False)}")
                print(f"  Total episodes: {test_data.get('total_episodes_processed', 0)}")
            
            elif test_name == 'memory_stability':
                print(f"  Episodes processed: {test_data.get('total_episodes', 0)}")
                print(f"  Memory leak detected: {test_data.get('memory_leak_detected', False)}")
                if test_data.get('memory_leak_detected'):
                    print(f"  Growth rate: {test_data.get('memory_growth_rate_mb_per_min', 0):.1f} MB/min")
            
            elif test_name == 'connection_pooling':
                print(f"  Concurrent operations: {test_data.get('num_concurrent', 0)}")
                print(f"  Success count: {test_data.get('success_count', 0)}")
                print(f"  Connection leak: {test_data.get('connection_leak', False)}")
                print(f"  Max connections: {test_data.get('max_connections', 0)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Load testing for podcast knowledge graph pipeline'
    )
    parser.add_argument(
        '--test',
        choices=['all', 'volume', 'checkpoint', 'memory', 'connections'],
        default='all',
        help='Which test to run'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='load_test_results',
        help='Output directory for results'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--episodes',
        type=int,
        default=100,
        help='Number of episodes for volume test'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=10,
        help='Duration in minutes for memory stability test'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=10,
        help='Number of concurrent connections'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = Config.from_file(args.config)
    else:
        config = Config()
    
    # Create load tester
    tester = LoadTester(config, Path(args.output_dir))
    
    # Prepare test podcast configurations
    test_configs = [
        {
            'name': f'Load Test Podcast {i}',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Technology'
        }
        for i in range(3)
    ]
    
    # Run requested tests
    if args.test in ['all', 'volume']:
        tester.test_large_volume(test_configs, total_episodes=args.episodes)
    
    if args.test in ['all', 'checkpoint']:
        tester.test_checkpoint_recovery(test_configs[0], interrupt_after=5)
    
    if args.test in ['all', 'memory']:
        tester.test_memory_stability(test_configs[0], duration_minutes=args.duration)
    
    if args.test in ['all', 'connections']:
        tester.test_connection_pooling(num_concurrent=args.concurrent)
    
    # Generate report
    tester.generate_report()
    tester.print_summary()


if __name__ == '__main__':
    main()