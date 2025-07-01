#!/usr/bin/env python3
"""
Simulated performance test for clustering system.

Tests clustering performance with synthetic data to validate:
- HDBSCAN algorithm performance with different data sizes
- Memory usage patterns
- Execution time scaling
- Quality metrics under various conditions

This allows performance validation without requiring external services.
"""

import time
import psutil
import numpy as np
from typing import Dict, Any, List
from collections import defaultdict
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    print("⚠️  HDBSCAN not available - simulating clustering behavior")


class SimulatedClusteringPerformanceTest:
    """Simulates clustering performance testing with synthetic data."""
    
    def __init__(self):
        self.process = psutil.Process()
        
    def generate_synthetic_embeddings(self, n_units: int, n_dimensions: int = 768) -> np.ndarray:
        """Generate synthetic embeddings that simulate real podcast data."""
        np.random.seed(42)  # Reproducible results
        
        # Create clusters of related content
        n_clusters = max(3, n_units // 50)  # Reasonable cluster count
        embeddings = []
        
        # Generate cluster centers
        centers = np.random.randn(n_clusters, n_dimensions)
        
        units_per_cluster = n_units // n_clusters
        
        for i in range(n_clusters):
            # Generate units around each center with some spread
            cluster_embeddings = np.random.randn(units_per_cluster, n_dimensions) * 0.3
            cluster_embeddings += centers[i]
            embeddings.extend(cluster_embeddings)
        
        # Add some random outliers
        remaining_units = n_units - len(embeddings)
        if remaining_units > 0:
            outliers = np.random.randn(remaining_units, n_dimensions) * 2
            embeddings.extend(outliers)
        
        # Normalize embeddings (simulate cosine similarity space)
        embeddings = np.array(embeddings)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.maximum(norms, 1e-8)
        
        return embeddings[:n_units]  # Ensure exact count
    
    def simulate_hdbscan_clustering(self, embeddings: np.ndarray, 
                                   min_cluster_size: int = None) -> Dict[str, Any]:
        """Simulate HDBSCAN clustering behavior."""
        n_samples = len(embeddings)
        
        if min_cluster_size is None:
            min_cluster_size = max(5, int(np.sqrt(n_samples) / 2))
        
        if HDBSCAN_AVAILABLE:
            # Use real HDBSCAN for accurate performance testing
            clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=3,
                metric='euclidean',  # Use euclidean instead of cosine
                cluster_selection_epsilon=0.3,
                core_dist_n_jobs=1  # Single thread for consistent timing
            )
            
            labels = clusterer.fit_predict(embeddings)
            
            # Build cluster assignments
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                if label >= 0:  # Not an outlier
                    clusters[label].append(i)
            
            n_clusters = len(clusters)
            n_outliers = np.sum(labels == -1)
            
        else:
            # Simulate clustering behavior
            # Simple k-means-like assignment for testing
            n_clusters = max(3, n_samples // min_cluster_size)
            
            # Random cluster assignment with some outliers
            labels = np.random.randint(0, n_clusters, n_samples)
            
            # Make 10-20% outliers
            outlier_count = int(n_samples * 0.15)
            outlier_indices = np.random.choice(n_samples, outlier_count, replace=False)
            labels[outlier_indices] = -1
            
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                if label >= 0:
                    clusters[label].append(i)
            
            n_outliers = outlier_count
        
        # Calculate statistics
        if clusters:
            cluster_sizes = [len(units) for units in clusters.values()]
            avg_cluster_size = np.mean(cluster_sizes)
            min_cluster_size = np.min(cluster_sizes)
            max_cluster_size = np.max(cluster_sizes)
        else:
            avg_cluster_size = min_cluster_size = max_cluster_size = 0
        
        outlier_ratio = n_outliers / n_samples if n_samples > 0 else 0
        
        return {
            'clusters': dict(clusters),
            'n_clusters': n_clusters,
            'n_outliers': n_outliers,
            'total_units': n_samples,
            'outlier_ratio': outlier_ratio,
            'avg_cluster_size': avg_cluster_size,
            'min_cluster_size': min_cluster_size,
            'max_cluster_size': max_cluster_size
        }
    
    def run_performance_test(self, test_sizes: List[int]) -> Dict[str, Any]:
        """Run performance tests with different data sizes."""
        results = {
            'test_results': [],
            'summary': {},
            'recommendations': []
        }
        
        print("🧪 Running clustering performance tests...")
        
        for n_units in test_sizes:
            print(f"\n📊 Testing with {n_units} units...")
            
            # Track memory before test
            start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            
            # Generate synthetic data
            print(f"   Generating {n_units} synthetic embeddings...")
            embeddings = self.generate_synthetic_embeddings(n_units)
            
            data_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            
            # Run clustering
            print(f"   Running clustering...")
            start_time = time.time()
            
            cluster_results = self.simulate_hdbscan_clustering(embeddings)
            
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            
            execution_time = end_time - start_time
            throughput = n_units / execution_time if execution_time > 0 else 0
            
            test_result = {
                'n_units': n_units,
                'execution_time': round(execution_time, 3),
                'throughput_units_per_sec': round(throughput, 1),
                'memory_start_mb': round(start_memory, 1),
                'memory_data_mb': round(data_memory, 1),
                'memory_end_mb': round(end_memory, 1),
                'memory_increase_mb': round(end_memory - start_memory, 1),
                'clustering_stats': cluster_results
            }
            
            results['test_results'].append(test_result)
            
            print(f"   ✅ Time: {execution_time:.2f}s, Throughput: {throughput:.1f} units/sec")
            print(f"   📊 Clusters: {cluster_results['n_clusters']}, Outliers: {cluster_results['outlier_ratio']:.1%}")
            print(f"   💾 Memory: {end_memory - start_memory:.1f} MB increase")
            
            # Clean up for next test
            del embeddings
        
        # Generate summary
        results['summary'] = self._generate_summary(results['test_results'])
        results['recommendations'] = self._generate_recommendations(results['test_results'])
        
        return results
    
    def _generate_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate performance summary."""
        if not test_results:
            return {}
        
        # Find 1000-unit test or closest
        target_test = None
        for result in test_results:
            if result['n_units'] == 1000:
                target_test = result
                break
        
        if not target_test:
            # Find closest to 1000
            target_test = min(test_results, key=lambda x: abs(x['n_units'] - 1000))
        
        # Extrapolate to 1000 units if needed
        if target_test['n_units'] != 1000:
            scale_factor = 1000 / target_test['n_units']
            # Assume O(n log n) complexity for HDBSCAN
            time_scaling = scale_factor * np.log(scale_factor)
            projected_time = target_test['execution_time'] * time_scaling
            projected_throughput = 1000 / projected_time
            projected_memory = target_test['memory_increase_mb'] * scale_factor
        else:
            projected_time = target_test['execution_time']
            projected_throughput = target_test['throughput_units_per_sec']
            projected_memory = target_test['memory_increase_mb']
        
        # Performance assessment
        time_acceptable = projected_time < 60  # 60 second target
        memory_acceptable = projected_memory < 2048  # 2GB target
        throughput_acceptable = projected_throughput > 10  # 10 units/sec target
        
        return {
            'target_test_size': target_test['n_units'],
            'projected_time_1000_units': round(projected_time, 1),
            'projected_throughput_1000_units': round(projected_throughput, 1),
            'projected_memory_1000_units': round(projected_memory, 1),
            'performance_assessment': {
                'time_acceptable': time_acceptable,
                'memory_acceptable': memory_acceptable,
                'throughput_acceptable': throughput_acceptable,
                'overall_pass': time_acceptable and memory_acceptable and throughput_acceptable
            }
        }
    
    def _generate_recommendations(self, test_results: List[Dict[str, Any]]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        if not test_results:
            return recommendations
        
        # Check for performance issues
        latest_result = test_results[-1]
        
        if latest_result['throughput_units_per_sec'] < 10:
            recommendations.append("Low throughput detected - consider using dimensionality reduction (PCA/UMAP)")
        
        if latest_result['memory_increase_mb'] > 1000:
            recommendations.append("High memory usage - consider batch processing for large datasets")
        
        # Check clustering quality
        stats = latest_result['clustering_stats']
        if stats['outlier_ratio'] > 0.3:
            recommendations.append("High outlier ratio - consider reducing min_cluster_size parameter")
        
        if stats['n_clusters'] < 3:
            recommendations.append("Very few clusters - consider reducing cluster_selection_epsilon")
        
        if stats['max_cluster_size'] > 100:
            recommendations.append("Very large clusters - may need parameter tuning for better granularity")
        
        if not recommendations:
            recommendations.append("Performance looks good - no optimizations needed")
        
        return recommendations


def print_performance_report(results: Dict[str, Any]):
    """Print formatted performance report."""
    print("\n" + "=" * 60)
    print("📊 CLUSTERING PERFORMANCE TEST REPORT")
    print("=" * 60)
    
    # Test results
    print("\n📈 Test Results:")
    for result in results['test_results']:
        print(f"   {result['n_units']} units: {result['execution_time']}s "
              f"({result['throughput_units_per_sec']} units/sec, "
              f"{result['memory_increase_mb']} MB)")
    
    # Summary
    if 'summary' in results and results['summary']:
        summary = results['summary']
        assessment = summary['performance_assessment']
        
        print(f"\n🎯 Performance Assessment (1000 units):")
        print(f"   Projected time: {summary['projected_time_1000_units']}s")
        print(f"   Projected throughput: {summary['projected_throughput_1000_units']} units/sec")
        print(f"   Projected memory: {summary['projected_memory_1000_units']} MB")
        
        print(f"\n✅ Quality Checks:")
        time_status = "✅" if assessment['time_acceptable'] else "❌"
        memory_status = "✅" if assessment['memory_acceptable'] else "❌"
        throughput_status = "✅" if assessment['throughput_acceptable'] else "❌"
        
        print(f"   Time < 60s: {time_status}")
        print(f"   Memory < 2GB: {memory_status}")
        print(f"   Throughput > 10 units/sec: {throughput_status}")
        
        overall_status = "PASS" if assessment['overall_pass'] else "FAIL"
        print(f"   Overall: {overall_status}")
    
    # Recommendations
    if 'recommendations' in results:
        print(f"\n💡 Recommendations:")
        for rec in results['recommendations']:
            print(f"   - {rec}")
    
    print("\n" + "=" * 60)


def main():
    """Main performance testing function."""
    print("🔧 Starting simulated clustering performance test...")
    
    # Test with different sizes
    test_sizes = [100, 500, 1000]
    
    # Add larger test if system has enough memory
    memory_gb = psutil.virtual_memory().total / (1024**3)
    if memory_gb > 8:
        test_sizes.append(2000)
    
    try:
        tester = SimulatedClusteringPerformanceTest()
        results = tester.run_performance_test(test_sizes)
        
        print_performance_report(results)
        
        # Check if performance is acceptable
        if 'summary' in results and results['summary']:
            assessment = results['summary']['performance_assessment']
            return assessment['overall_pass']
        else:
            return True  # Default to pass if no assessment
            
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    print(f"\n🏁 Performance test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)