#!/usr/bin/env python3
"""
Performance testing script for clustering system.

Tests clustering performance to ensure it meets requirements:
- Measures total execution time
- Calculates throughput (units per second)
- Monitors cluster quality metrics
- Verifies memory usage stays reasonable

Success criteria:
- Clustering 1000 units completes in under 60 seconds
- Memory usage stays under reasonable limits
- Cluster quality metrics are acceptable
"""

import os
import sys
import time
import psutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.graph_storage import GraphStorageService
from src.services.llm_service import LLMService
from src.clustering.semantic_clustering import SemanticClusteringSystem
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PerformanceMonitor:
    """Monitors system performance during clustering."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.start_time = None
        self.peak_memory = 0
        
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
        
    def update_peak_memory(self):
        """Update peak memory usage."""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
            
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            'execution_time': end_time - self.start_time,
            'start_memory_mb': self.start_memory,
            'end_memory_mb': end_memory,
            'peak_memory_mb': self.peak_memory,
            'memory_increase_mb': end_memory - self.start_memory,
            'cpu_percent': self.process.cpu_percent()
        }


def test_clustering_performance(podcast_db_uri: str, 
                               gemini_api_key: str,
                               test_size_limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Test clustering performance on available data.
    
    Args:
        podcast_db_uri: Neo4j connection URI
        gemini_api_key: API key for LLM service
        test_size_limit: Optional limit on number of units to test
        
    Returns:
        Performance test results
    """
    results = {
        'status': 'success',
        'test_timestamp': datetime.now().isoformat(),
        'performance_metrics': {},
        'clustering_stats': {},
        'quality_assessment': {},
        'errors': []
    }
    
    monitor = PerformanceMonitor()
    
    try:
        logger.info("🚀 Starting clustering performance test")
        monitor.start_monitoring()
        
        # Initialize services
        logger.info("Initializing services...")
        neo4j_service = GraphStorageService(
            uri=podcast_db_uri,
            username='neo4j',
            password='password'
        )
        
        llm_service = LLMService(
            api_key=gemini_api_key,
            model_name="gemini-1.5-flash-002",  # Fast model for testing
            max_tokens=8000,
            temperature=0.3
        )
        
        # Check available data
        logger.info("Checking available data...")
        data_check_query = """
        MATCH (e:Episode)-[:CONTAINS]->(m:MeaningfulUnit)
        WHERE m.embedding IS NOT NULL
        RETURN count(DISTINCT e) as episode_count, 
               count(m) as unit_count
        """
        
        data_result = neo4j_service.query(data_check_query)
        if not data_result:
            raise Exception("Could not query database for available data")
            
        episode_count = data_result[0]['episode_count']
        available_units = data_result[0]['unit_count']
        
        logger.info(f"Found {episode_count} episodes with {available_units} units with embeddings")
        
        if available_units == 0:
            results['status'] = 'skipped'
            results['message'] = 'No MeaningfulUnits with embeddings found for testing'
            return results
        
        # Apply test size limit if specified
        units_to_test = available_units
        if test_size_limit and available_units > test_size_limit:
            units_to_test = test_size_limit
            logger.info(f"Limiting test to {test_size_limit} units for performance testing")
        
        # Initialize clustering system
        logger.info("Initializing clustering system...")
        clustering_config = {
            'clustering': {
                'min_cluster_size_formula': 'sqrt',
                'min_samples': 3,
                'epsilon': 0.3
            }
        }
        
        clustering_system = SemanticClusteringSystem(
            neo4j_service,
            llm_service,
            clustering_config
        )
        
        # Run clustering
        logger.info(f"Running clustering on {units_to_test} units...")
        start_clustering = time.time()
        
        clustering_result = clustering_system.run_clustering()
        
        end_clustering = time.time()
        monitor.update_peak_memory()
        
        # Get performance metrics
        performance_stats = monitor.get_stats()
        clustering_time = end_clustering - start_clustering
        
        # Calculate performance metrics
        if clustering_time > 0:
            throughput = units_to_test / clustering_time
        else:
            throughput = 0
            
        results['performance_metrics'] = {
            'total_execution_time': performance_stats['execution_time'],
            'clustering_time': clustering_time,
            'units_tested': units_to_test,
            'throughput_units_per_second': round(throughput, 1),
            'memory_start_mb': round(performance_stats['start_memory_mb'], 1),
            'memory_end_mb': round(performance_stats['end_memory_mb'], 1),
            'memory_peak_mb': round(performance_stats['peak_memory_mb'], 1),
            'memory_increase_mb': round(performance_stats['memory_increase_mb'], 1),
            'cpu_percent': performance_stats['cpu_percent']
        }
        
        # Store clustering statistics
        if clustering_result['status'] == 'success':
            results['clustering_stats'] = clustering_result['stats']
        else:
            results['errors'].append(f"Clustering failed: {clustering_result.get('message', 'Unknown error')}")
        
        # Assess performance against criteria
        quality_assessment = assess_performance_quality(
            units_to_test,
            clustering_time,
            performance_stats,
            clustering_result
        )
        
        results['quality_assessment'] = quality_assessment
        
        logger.info("✅ Performance test completed successfully")
        
    except Exception as e:
        logger.error(f"Performance test failed: {str(e)}", exc_info=True)
        results['status'] = 'error'
        results['errors'].append(str(e))
        
    finally:
        # Clean up connections
        try:
            neo4j_service.close()
        except:
            pass
    
    return results


def assess_performance_quality(units_tested: int, 
                             clustering_time: float,
                             performance_stats: Dict[str, Any],
                             clustering_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess clustering performance against quality criteria.
    
    Returns:
        Assessment results with pass/fail status
    """
    assessment = {
        'overall_pass': True,
        'criteria_results': {},
        'recommendations': []
    }
    
    # Criterion 1: Execution time (should complete 1000 units in under 60 seconds)
    if units_tested >= 1000:
        time_per_1000 = clustering_time
        time_acceptable = time_per_1000 < 60
    else:
        # Extrapolate to 1000 units
        time_per_1000 = (clustering_time / units_tested) * 1000
        time_acceptable = time_per_1000 < 60
    
    assessment['criteria_results']['execution_time'] = {
        'pass': time_acceptable,
        'actual_time': clustering_time,
        'projected_time_1000_units': round(time_per_1000, 1),
        'threshold': 60
    }
    
    if not time_acceptable:
        assessment['overall_pass'] = False
        assessment['recommendations'].append("Consider optimizing HDBSCAN parameters or using dimensionality reduction")
    
    # Criterion 2: Memory usage (should not exceed 2GB increase)
    memory_increase = performance_stats['memory_increase_mb']
    memory_acceptable = memory_increase < 2048  # 2GB
    
    assessment['criteria_results']['memory_usage'] = {
        'pass': memory_acceptable,
        'memory_increase_mb': memory_increase,
        'peak_memory_mb': performance_stats['peak_memory_mb'],
        'threshold_mb': 2048
    }
    
    if not memory_acceptable:
        assessment['overall_pass'] = False
        assessment['recommendations'].append("Memory usage too high - consider batch processing or dimensionality reduction")
    
    # Criterion 3: Clustering quality (outlier ratio should be < 30%)
    if clustering_result.get('status') == 'success' and 'stats' in clustering_result:
        outlier_ratio = clustering_result['stats'].get('outlier_ratio', 0)
        quality_acceptable = outlier_ratio < 0.3
        
        assessment['criteria_results']['clustering_quality'] = {
            'pass': quality_acceptable,
            'outlier_ratio': outlier_ratio,
            'n_clusters': clustering_result['stats'].get('n_clusters', 0),
            'threshold': 0.3
        }
        
        if not quality_acceptable:
            assessment['recommendations'].append("High outlier ratio - consider adjusting min_cluster_size parameter")
    
    # Criterion 4: Throughput (units per second)
    throughput = units_tested / clustering_time if clustering_time > 0 else 0
    throughput_acceptable = throughput > 10  # Should process at least 10 units/second
    
    assessment['criteria_results']['throughput'] = {
        'pass': throughput_acceptable,
        'units_per_second': round(throughput, 1),
        'threshold': 10
    }
    
    if not throughput_acceptable:
        assessment['overall_pass'] = False
        assessment['recommendations'].append("Low throughput - investigate performance bottlenecks")
    
    return assessment


def print_performance_report(results: Dict[str, Any]):
    """Print formatted performance test report."""
    print("\n" + "=" * 60)
    print("📊 CLUSTERING PERFORMANCE TEST REPORT")
    print("=" * 60)
    
    if results['status'] == 'error':
        print("❌ Test failed with errors:")
        for error in results['errors']:
            print(f"   {error}")
        return
    
    if results['status'] == 'skipped':
        print("⏭️  Test skipped:")
        print(f"   {results.get('message', 'Unknown reason')}")
        return
    
    # Performance metrics
    metrics = results['performance_metrics']
    print(f"\n📈 Performance Metrics:")
    print(f"   Total execution time: {metrics['total_execution_time']:.1f}s")
    print(f"   Clustering time: {metrics['clustering_time']:.1f}s")
    print(f"   Units tested: {metrics['units_tested']}")
    print(f"   Throughput: {metrics['throughput_units_per_second']} units/sec")
    print(f"   Memory usage: {metrics['memory_start_mb']} → {metrics['memory_end_mb']} MB (peak: {metrics['memory_peak_mb']} MB)")
    
    # Clustering results
    if 'clustering_stats' in results:
        stats = results['clustering_stats']
        print(f"\n🔬 Clustering Results:")
        print(f"   Clusters created: {stats.get('n_clusters', 0)}")
        print(f"   Outliers: {stats.get('n_outliers', 0)} ({stats.get('outlier_ratio', 0):.1%})")
        print(f"   Average cluster size: {stats.get('avg_cluster_size', 0):.1f}")
    
    # Quality assessment
    if 'quality_assessment' in results:
        assessment = results['quality_assessment']
        print(f"\n✅ Quality Assessment:")
        
        overall_status = "PASS" if assessment['overall_pass'] else "FAIL"
        print(f"   Overall: {overall_status}")
        
        for criterion, result in assessment['criteria_results'].items():
            status = "✅" if result['pass'] else "❌"
            print(f"   {criterion}: {status}")
        
        if assessment['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in assessment['recommendations']:
                print(f"   - {rec}")
    
    print("\n" + "=" * 60)


def main():
    """Main performance testing function."""
    # Check environment variables
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        return False
    
    # Default to local Neo4j
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    
    # Run performance test
    print("🔧 Starting clustering performance test...")
    
    try:
        # Limit test size for reasonable execution time
        test_results = test_clustering_performance(
            neo4j_uri,
            gemini_api_key,
            test_size_limit=1000  # Limit to 1000 units for testing
        )
        
        # Print report
        print_performance_report(test_results)
        
        # Return success status
        return test_results.get('status') == 'success'
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)