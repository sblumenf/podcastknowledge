#!/usr/bin/env python3
"""Pre-merge validation script for production readiness.

This script performs final validation before merging to production:
- Processes a complete real podcast
- Verifies Neo4j contains expected node types
- Checks resource cleanup
- Generates validation report
"""

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
from neo4j import GraphDatabase

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.v1 import seed_podcast, PodcastKnowledgePipeline
from src.core.config import Config


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PreMergeValidator:
    """Validates system readiness for production."""
    
    def __init__(self, config: Config, output_dir: Path):
        """Initialize validator.
        
        Args:
            config: Pipeline configuration
            output_dir: Directory for validation results
        """
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'validation_checks': {},
            'issues': [],
            'warnings': [],
            'recommendation': None
        }
    
    def run_validation(self, podcast_url: str) -> bool:
        """Run complete validation suite.
        
        Args:
            podcast_url: RSS URL of podcast to process
            
        Returns:
            True if validation passed, False otherwise
        """
        logger.info("Starting pre-merge validation...")
        
        # Check 1: Environment validation
        self._validate_environment()
        
        # Check 2: Process real podcast
        podcast_result = self._validate_podcast_processing(podcast_url)
        
        if podcast_result:
            # Check 3: Verify graph structure
            self._validate_graph_structure()
            
            # Check 4: Resource cleanup
            self._validate_resource_cleanup()
            
            # Check 5: Performance characteristics
            self._validate_performance()
        
        # Generate final recommendation
        self._generate_recommendation()
        
        # Save report
        self._save_report()
        
        return self.results['recommendation'] == 'READY_FOR_PRODUCTION'
    
    def _validate_environment(self):
        """Validate environment setup."""
        logger.info("Validating environment...")
        
        checks = {
            'python_version': sys.version_info >= (3, 9),
            'memory_available': psutil.virtual_memory().available > (2 * 1024**3),  # 2GB
            'disk_space': psutil.disk_usage('/').free > (5 * 1024**3),  # 5GB
            'neo4j_connection': self._check_neo4j_connection(),
            'required_env_vars': self._check_env_vars()
        }
        
        self.results['validation_checks']['environment'] = checks
        
        # Log issues
        if not checks['python_version']:
            self.results['issues'].append(
                f"Python version too old: {sys.version}, requires >= 3.9"
            )
        
        if not checks['memory_available']:
            self.results['warnings'].append(
                f"Low memory: {psutil.virtual_memory().available / (1024**3):.1f} GB available"
            )
        
        if not checks['neo4j_connection']:
            self.results['issues'].append("Cannot connect to Neo4j database")
    
    def _check_neo4j_connection(self) -> bool:
        """Check Neo4j connection."""
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            return True
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False
    
    def _check_env_vars(self) -> bool:
        """Check required environment variables."""
        required = ['NEO4J_PASSWORD', 'GOOGLE_API_KEY']
        missing = [var for var in required if not os.environ.get(var)]
        
        if missing:
            self.results['warnings'].append(
                f"Missing environment variables: {', '.join(missing)}"
            )
        
        return len(missing) == 0
    
    def _validate_podcast_processing(self, podcast_url: str) -> bool:
        """Validate processing of a real podcast.
        
        Args:
            podcast_url: RSS URL to process
            
        Returns:
            True if processing succeeded
        """
        logger.info(f"Processing podcast: {podcast_url}")
        
        validation = {
            'podcast_url': podcast_url,
            'start_time': datetime.now().isoformat(),
            'success': False,
            'episodes_target': 3,
            'episodes_processed': 0,
            'processing_time': 0,
            'errors': []
        }
        
        # Clear database first
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            driver.close()
        except Exception as e:
            validation['errors'].append(f"Failed to clear database: {e}")
        
        # Monitor resources during processing
        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024**2)  # MB
        start_time = time.time()
        
        try:
            # Process podcast
            podcast = {
                'name': 'Validation Test Podcast',
                'rss_url': podcast_url,
                'category': 'Validation'
            }
            
            result = seed_podcast(
                podcast,
                max_episodes=validation['episodes_target'],
                config=self.config
            )
            
            validation['episodes_processed'] = result.get('episodes_processed', 0)
            validation['episodes_failed'] = result.get('episodes_failed', 0)
            validation['success'] = validation['episodes_processed'] > 0
            
            if not validation['success']:
                validation['errors'].append("No episodes were processed successfully")
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            validation['errors'].append(str(e))
            validation['success'] = False
            traceback.print_exc()
        
        # Record metrics
        validation['processing_time'] = time.time() - start_time
        validation['peak_memory_mb'] = (
            process.memory_info().rss / (1024**2) - start_memory
        )
        validation['end_time'] = datetime.now().isoformat()
        
        self.results['validation_checks']['podcast_processing'] = validation
        
        # Check performance
        if validation['processing_time'] > 300:  # 5 minutes
            self.results['warnings'].append(
                f"Processing took too long: {validation['processing_time']:.1f}s"
            )
        
        if validation['peak_memory_mb'] > 1024:  # 1GB
            self.results['warnings'].append(
                f"High memory usage: {validation['peak_memory_mb']:.1f} MB"
            )
        
        return validation['success']
    
    def _validate_graph_structure(self):
        """Validate Neo4j graph structure."""
        logger.info("Validating graph structure...")
        
        validation = {
            'node_types': {},
            'relationships': {},
            'data_integrity': [],
            'success': True
        }
        
        driver = GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password)
        )
        
        try:
            with driver.session() as session:
                # Check expected node types
                expected_labels = [
                    'Podcast', 'Episode', 'Segment', 'Insight',
                    'Entity', 'Quote', 'Topic', 'Speaker'
                ]
                
                for label in expected_labels:
                    count_result = session.run(
                        f"MATCH (n:{label}) RETURN count(n) as count"
                    ).single()
                    count = count_result['count'] if count_result else 0
                    validation['node_types'][label] = count
                
                # Check required nodes exist
                if validation['node_types']['Podcast'] == 0:
                    validation['data_integrity'].append("No Podcast nodes found")
                    validation['success'] = False
                
                if validation['node_types']['Episode'] == 0:
                    validation['data_integrity'].append("No Episode nodes found")
                    validation['success'] = False
                
                if validation['node_types']['Insight'] == 0:
                    validation['data_integrity'].append("No Insight nodes found")
                    self.results['warnings'].append("No insights extracted")
                
                # Check relationships
                expected_relationships = [
                    'HAS_EPISODE', 'HAS_SEGMENT', 'HAS_INSIGHT',
                    'MENTIONS_ENTITY', 'HAS_QUOTE', 'SPOKEN_BY'
                ]
                
                for rel_type in expected_relationships:
                    count_result = session.run(
                        f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                    ).single()
                    count = count_result['count'] if count_result else 0
                    validation['relationships'][rel_type] = count
                
                # Verify podcast-episode connection
                connected = session.run(
                    """
                    MATCH (p:Podcast)-[:HAS_EPISODE]->(e:Episode)
                    RETURN count(e) as count
                    """
                ).single()
                
                if connected['count'] == 0:
                    validation['data_integrity'].append(
                        "Episodes not connected to Podcast"
                    )
                    validation['success'] = False
                
                # Check for orphaned nodes
                orphaned = session.run(
                    """
                    MATCH (n)
                    WHERE NOT (n)--()
                    RETURN count(n) as count, labels(n) as labels
                    """
                )
                
                orphan_count = 0
                for record in orphaned:
                    if record['count'] > 0:
                        orphan_count += record['count']
                        validation['data_integrity'].append(
                            f"{record['count']} orphaned {record['labels']} nodes"
                        )
                
                if orphan_count > 10:
                    self.results['warnings'].append(
                        f"High number of orphaned nodes: {orphan_count}"
                    )
                
        except Exception as e:
            logger.error(f"Graph validation failed: {e}")
            validation['success'] = False
            validation['data_integrity'].append(f"Validation error: {e}")
        
        finally:
            driver.close()
        
        self.results['validation_checks']['graph_structure'] = validation
        
        if not validation['success']:
            self.results['issues'].append("Graph structure validation failed")
    
    def _validate_resource_cleanup(self):
        """Validate resource cleanup."""
        logger.info("Validating resource cleanup...")
        
        validation = {
            'memory_leaks': False,
            'file_handles': True,
            'database_connections': True,
            'temp_files': True,
            'checks': {}
        }
        
        # Check for memory leaks by processing multiple times
        memory_samples = []
        
        for i in range(3):
            import gc
            gc.collect()
            
            before = psutil.Process().memory_info().rss / (1024**2)
            
            # Process small podcast
            try:
                test_podcast = {
                    'name': f'Cleanup Test {i}',
                    'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                    'category': 'Test'
                }
                
                seed_podcast(
                    test_podcast,
                    max_episodes=1,
                    config=self.config
                )
            except Exception:
                pass  # Ignore processing errors here
            
            gc.collect()
            after = psutil.Process().memory_info().rss / (1024**2)
            
            memory_samples.append({
                'iteration': i,
                'before': before,
                'after': after,
                'growth': after - before
            })
        
        # Check for consistent growth
        if len(memory_samples) > 1:
            avg_growth = sum(s['growth'] for s in memory_samples[1:]) / (len(memory_samples) - 1)
            validation['checks']['avg_memory_growth_mb'] = avg_growth
            
            if avg_growth > 10:  # 10MB growth per iteration
                validation['memory_leaks'] = True
                self.results['issues'].append(
                    f"Potential memory leak: {avg_growth:.1f} MB growth per iteration"
                )
        
        # Check file handles
        process = psutil.Process()
        open_files = len(process.open_files())
        validation['checks']['open_files'] = open_files
        
        if open_files > 100:
            validation['file_handles'] = False
            self.results['warnings'].append(
                f"High number of open files: {open_files}"
            )
        
        # Check database connections
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )
            
            with driver.session() as session:
                # Try to get connection count (may not work on all Neo4j versions)
                try:
                    connections = session.run(
                        "CALL dbms.listConnections() YIELD connectionId "
                        "RETURN count(*) as count"
                    ).single()
                    
                    conn_count = connections['count']
                    validation['checks']['db_connections'] = conn_count
                    
                    if conn_count > 50:
                        validation['database_connections'] = False
                        self.results['warnings'].append(
                            f"High database connection count: {conn_count}"
                        )
                except:
                    # Query not available, skip check
                    pass
            
            driver.close()
            
        except Exception as e:
            logger.warning(f"Could not check database connections: {e}")
        
        # Check for temp files
        temp_dirs = ['/tmp', Path.home() / 'tmp', Path('./temp')]
        temp_file_count = 0
        
        for temp_dir in temp_dirs:
            if temp_dir.exists():
                # Look for files created in last hour
                one_hour_ago = time.time() - 3600
                for file in temp_dir.glob('*'):
                    if file.is_file() and file.stat().st_mtime > one_hour_ago:
                        if 'podcast' in str(file).lower():
                            temp_file_count += 1
        
        validation['checks']['temp_files'] = temp_file_count
        
        if temp_file_count > 10:
            validation['temp_files'] = False
            self.results['warnings'].append(
                f"Found {temp_file_count} recent temporary files"
            )
        
        self.results['validation_checks']['resource_cleanup'] = validation
    
    def _validate_performance(self):
        """Validate performance characteristics."""
        logger.info("Validating performance...")
        
        validation = {
            'single_episode_benchmark': {},
            'memory_efficiency': {},
            'concurrent_safety': {},
            'meets_requirements': True
        }
        
        # Benchmark single episode
        test_podcast = {
            'name': 'Performance Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Benchmark'
        }
        
        times = []
        for i in range(3):
            start = time.time()
            try:
                result = seed_podcast(
                    test_podcast,
                    max_episodes=1,
                    config=self.config
                )
                if result['episodes_processed'] > 0:
                    times.append(time.time() - start)
            except Exception:
                pass
        
        if times:
            avg_time = sum(times) / len(times)
            validation['single_episode_benchmark'] = {
                'avg_time': avg_time,
                'min_time': min(times),
                'max_time': max(times),
                'meets_target': avg_time < 60  # 1 minute target
            }
            
            if not validation['single_episode_benchmark']['meets_target']:
                validation['meets_requirements'] = False
                self.results['issues'].append(
                    f"Performance too slow: {avg_time:.1f}s per episode"
                )
        
        # Test concurrent processing
        from concurrent.futures import ThreadPoolExecutor
        
        def process_concurrent(index):
            try:
                seed_podcast(
                    {
                        'name': f'Concurrent {index}',
                        'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                        'category': 'Test'
                    },
                    max_episodes=1,
                    config=self.config
                )
                return True
            except Exception:
                return False
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_concurrent, i) for i in range(3)]
            results = [f.result() for f in futures]
        
        validation['concurrent_safety'] = {
            'success_count': sum(results),
            'total': len(results),
            'thread_safe': sum(results) == len(results)
        }
        
        if not validation['concurrent_safety']['thread_safe']:
            self.results['warnings'].append(
                "Concurrent processing showed failures"
            )
        
        self.results['validation_checks']['performance'] = validation
    
    def _generate_recommendation(self):
        """Generate final recommendation."""
        # Count issues and warnings
        critical_issues = len(self.results['issues'])
        warnings = len(self.results['warnings'])
        
        # Check all validations passed
        all_passed = all(
            check.get('success', True) 
            for check in self.results['validation_checks'].values()
            if isinstance(check, dict)
        )
        
        if critical_issues == 0 and all_passed:
            if warnings == 0:
                self.results['recommendation'] = 'READY_FOR_PRODUCTION'
                self.results['recommendation_details'] = (
                    "All validation checks passed. System is ready for production."
                )
            elif warnings < 3:
                self.results['recommendation'] = 'READY_WITH_WARNINGS'
                self.results['recommendation_details'] = (
                    f"System is ready but has {warnings} warnings that should be addressed."
                )
            else:
                self.results['recommendation'] = 'NEEDS_ATTENTION'
                self.results['recommendation_details'] = (
                    f"System has {warnings} warnings. Review and address before production."
                )
        else:
            self.results['recommendation'] = 'NOT_READY'
            self.results['recommendation_details'] = (
                f"System has {critical_issues} critical issues that must be fixed."
            )
    
    def _save_report(self):
        """Save validation report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f'pre_merge_validation_{timestamp}.json'
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Also save summary
        summary_file = self.output_dir / f'validation_summary_{timestamp}.txt'
        with open(summary_file, 'w') as f:
            f.write("PRE-MERGE VALIDATION SUMMARY\n")
            f.write("="*60 + "\n\n")
            f.write(f"Timestamp: {self.results['timestamp']}\n")
            f.write(f"Recommendation: {self.results['recommendation']}\n")
            f.write(f"Details: {self.results['recommendation_details']}\n\n")
            
            if self.results['issues']:
                f.write("CRITICAL ISSUES:\n")
                for issue in self.results['issues']:
                    f.write(f"  ❌ {issue}\n")
                f.write("\n")
            
            if self.results['warnings']:
                f.write("WARNINGS:\n")
                for warning in self.results['warnings']:
                    f.write(f"  ⚠️  {warning}\n")
                f.write("\n")
            
            f.write("VALIDATION RESULTS:\n")
            for check_name, check_data in self.results['validation_checks'].items():
                if isinstance(check_data, dict):
                    success = check_data.get('success', True)
                    status = "✅ PASSED" if success else "❌ FAILED"
                    f.write(f"  {check_name}: {status}\n")
        
        logger.info(f"Validation report saved to {report_file}")
        logger.info(f"Summary saved to {summary_file}")
    
    def print_summary(self):
        """Print validation summary to console."""
        print("\n" + "="*60)
        print("PRE-MERGE VALIDATION COMPLETE")
        print("="*60)
        print(f"Recommendation: {self.results['recommendation']}")
        print(f"Details: {self.results['recommendation_details']}")
        
        if self.results['issues']:
            print("\nCRITICAL ISSUES:")
            for issue in self.results['issues']:
                print(f"  ❌ {issue}")
        
        if self.results['warnings']:
            print("\nWARNINGS:")
            for warning in self.results['warnings']:
                print(f"  ⚠️  {warning}")
        
        print("\nVALIDATION CHECKS:")
        for check_name, check_data in self.results['validation_checks'].items():
            if isinstance(check_data, dict):
                success = check_data.get('success', True)
                status = "✅" if success else "❌"
                print(f"  {status} {check_name}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Pre-merge validation for production readiness'
    )
    parser.add_argument(
        '--podcast-url',
        type=str,
        default='https://feeds.simplecast.com/54nAGcIl',
        help='RSS URL of podcast to process for validation'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='validation_results',
        help='Directory for validation results'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick validation (skip some checks)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = Config.from_file(args.config)
    else:
        config = Config()
    
    # Create validator
    validator = PreMergeValidator(config, Path(args.output_dir))
    
    # Run validation
    success = validator.run_validation(args.podcast_url)
    
    # Print summary
    validator.print_summary()
    
    # Exit with appropriate code
    if success:
        logger.info("✅ System is ready for production!")
        sys.exit(0)
    else:
        logger.error("❌ System is not ready for production")
        sys.exit(1)


if __name__ == '__main__':
    main()