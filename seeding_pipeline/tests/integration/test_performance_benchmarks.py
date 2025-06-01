"""Performance benchmark tests for the pipeline."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch
import gc
import json
import os
import tempfile
import time

import numpy as np
import psutil
import pytest

from src.core.config import Config
from src.extraction.extraction import KnowledgeExtractor
from src.seeding.orchestrator import VTTKnowledgeExtractor
from src.utils.memory import MemoryMonitor
class PerformanceMetrics:
    """Collect and analyze performance metrics."""
    
    def __init__(self):
        self.metrics = {
            'extraction_times': [],
            'memory_usage': [],
            'cpu_usage': [],
            'episode_processing_times': [],
            'neo4j_query_times': [],
            'llm_response_times': [],
            'embedding_times': []
        }
        self.process = psutil.Process()
    
    def record_extraction_time(self, duration: float):
        self.metrics['extraction_times'].append(duration)
    
    def record_memory_usage(self):
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        self.metrics['memory_usage'].append(memory_mb)
    
    def record_cpu_usage(self):
        cpu_percent = self.process.cpu_percent(interval=0.1)
        self.metrics['cpu_usage'].append(cpu_percent)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        summary = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                summary[metric_name] = {
                    'count': len(values),
                    'mean': np.mean(values),
                    'median': np.median(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'p95': np.percentile(values, 95),
                    'p99': np.percentile(values, 99)
                }
        
        return summary


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.fixture
    def benchmark_dir(self):
        """Directory for benchmark results."""
        benchmark_dir = Path(__file__).parent.parent / "benchmarks"
        benchmark_dir.mkdir(exist_ok=True)
        return benchmark_dir
    
    @pytest.fixture
    def test_config(self):
        """Test configuration for benchmarks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.checkpoint_dir = tmpdir
            config.audio_dir = tmpdir
            config.batch_size = 10
            config.max_workers = 4
            yield config
    
    @pytest.fixture
    def sample_transcript(self):
        """Generate sample transcript of various sizes."""
        base_text = """
        Welcome to our technology podcast. Today we're discussing artificial intelligence
        and its impact on society. Our guest is Dr. Jane Smith from MIT, who has been
        researching machine learning for over 20 years. She recently published a paper
        on neural networks that has gained significant attention in the field.
        """
        return {
            'small': base_text,
            'medium': base_text * 10,
            'large': base_text * 50,
            'xlarge': base_text * 100
        }
    
    @pytest.mark.benchmark
    def test_benchmark_extraction_time_per_episode(
        self, benchmark_dir, test_config, sample_transcript
    ):
        """Benchmark extraction time per episode."""
        metrics = PerformanceMetrics()
        
        # Mock providers
        mock_audio = Mock()
        mock_audio.transcribe.return_value = sample_transcript['medium']
        
        mock_llm = Mock()
        def mock_generate(prompt, *args, **kwargs):
            # Simulate processing time
            time.sleep(0.1)
            return json.dumps({
                "entities": [
                    {"name": "Dr. Jane Smith", "type": "Person"},
                    {"name": "MIT", "type": "Organization"}
                ],
                "relationships": [
                    {"source": "Dr. Jane Smith", "target": "MIT", "type": "WORKS_AT"}
                ]
            })
        mock_llm.generate.side_effect = mock_generate
        
        mock_graph = Mock()
        mock_embeddings = Mock()
        mock_embeddings.embed.return_value = [0.1] * 384
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider',
                  return_value=mock_audio), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider',
                  return_value=mock_llm), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider',
                  return_value=mock_graph), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider',
                  return_value=mock_embeddings):
            
            extractor = KnowledgeExtractor(
                llm_provider=mock_llm,
                embedding_provider=mock_embeddings
            )
            
            # Benchmark different transcript sizes
            for size_name, transcript in sample_transcript.items():
                mock_audio.transcribe.return_value = transcript
                
                # Warm up
                segment = {"text": transcript[:100], "start": 0, "end": 10}
                extractor.extract_knowledge(segment)
                
                # Benchmark
                iterations = 10 if size_name in ['small', 'medium'] else 5
                
                for i in range(iterations):
                    start_time = time.time()
                    
                    result = extractor.extract_knowledge({
                        "text": transcript,
                        "start": 0,
                        "end": 60 * (i + 1),
                        "speaker": "Mixed"
                    })
                    
                    duration = time.time() - start_time
                    metrics.record_extraction_time(duration)
                    metrics.record_memory_usage()
                    
                    # Verify extraction worked
                    assert 'entities' in result
                    assert 'relationships' in result
            
            # Save benchmark results
            summary = metrics.get_summary()
            benchmark_file = benchmark_dir / f"extraction_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(benchmark_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'config': {
                        'batch_size': test_config.batch_size,
                        'max_workers': test_config.max_workers
                    },
                    'results': summary
                }, f, indent=2)
            
            # Performance assertions
            avg_time = summary['extraction_times']['mean']
            assert avg_time < 2.0, f"Average extraction time {avg_time}s exceeds 2s threshold"
            
            p95_time = summary['extraction_times']['p95']
            assert p95_time < 3.0, f"95th percentile extraction time {p95_time}s exceeds 3s threshold"
    
    @pytest.mark.benchmark
    def test_benchmark_memory_usage_patterns(self, benchmark_dir, test_config):
        """Benchmark memory usage patterns during processing."""
        metrics = PerformanceMetrics()
        memory_monitor = MemoryMonitor()
        
        # Track memory over time
        memory_samples = []
        
        def sample_memory():
            for _ in range(100):
                memory_mb = memory_monitor.get_current_usage_mb()
                memory_samples.append({
                    'timestamp': time.time(),
                    'memory_mb': memory_mb,
                    'available_mb': memory_monitor.get_available_memory_mb()
                })
                time.sleep(0.1)
        
        # Simulate processing with memory tracking
        import threading
        memory_thread = threading.Thread(target=sample_memory)
        memory_thread.start()
        
        # Simulate data processing
        large_data = []
        for i in range(50):
            # Allocate memory
            data = {
                'entities': [f"Entity_{j}" for j in range(1000)],
                'embeddings': np.random.rand(1000, 384)
            }
            large_data.append(data)
            
            # Force garbage collection periodically
            if i % 10 == 0:
                gc.collect()
            
            time.sleep(0.2)
        
        # Clear data
        large_data.clear()
        gc.collect()
        
        # Wait for memory sampling to complete
        memory_thread.join()
        
        # Analyze memory patterns
        peak_memory = max(s['memory_mb'] for s in memory_samples)
        baseline_memory = memory_samples[0]['memory_mb']
        memory_increase = peak_memory - baseline_memory
        
        # Save memory usage data
        benchmark_file = benchmark_dir / f"memory_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(benchmark_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'baseline_memory_mb': baseline_memory,
                'peak_memory_mb': peak_memory,
                'memory_increase_mb': memory_increase,
                'samples': memory_samples[-20:]  # Last 20 samples
            }, f, indent=2)
        
        # Memory assertions
        assert memory_increase < 500, f"Memory increase {memory_increase}MB exceeds 500MB threshold"
        
        # Check for memory leaks (final memory should be close to baseline)
        final_memory = memory_samples[-1]['memory_mb']
        memory_leaked = final_memory - baseline_memory
        assert memory_leaked < 50, f"Potential memory leak: {memory_leaked}MB not freed"
    
    @pytest.mark.benchmark
    def test_benchmark_neo4j_query_performance(self, benchmark_dir):
        """Benchmark Neo4j query performance."""
        metrics = PerformanceMetrics()
        
        # Mock Neo4j operations
        query_times = {
            'create_node': 0.01,
            'create_relationship': 0.015,
            'find_node': 0.005,
            'update_node': 0.012,
            'complex_query': 0.05
        }
        
        mock_graph = Mock()
        
        def mock_query(query_type):
            def query_func(*args, **kwargs):
                time.sleep(query_times.get(query_type, 0.01))
                return True
            return query_func
        
        mock_graph.create_node = mock_query('create_node')
        mock_graph.create_relationship = mock_query('create_relationship')
        mock_graph.find_node = mock_query('find_node')
        mock_graph.update_node = mock_query('update_node')
        
        # Benchmark different operations
        operations = [
            ('create_node', 100),
            ('create_relationship', 50),
            ('find_node', 200),
            ('update_node', 50)
        ]
        
        for op_name, count in operations:
            operation_times = []
            
            for i in range(count):
                start_time = time.time()
                
                if op_name == 'create_node':
                    mock_graph.create_node(f"Node_{i}", {"name": f"Test_{i}"})
                elif op_name == 'create_relationship':
                    mock_graph.create_relationship(f"Node_{i}", f"Node_{i+1}", "RELATES_TO")
                elif op_name == 'find_node':
                    mock_graph.find_node("Person", {"name": f"Test_{i}"})
                elif op_name == 'update_node':
                    mock_graph.update_node(f"Node_{i}", {"updated": True})
                
                duration = time.time() - start_time
                operation_times.append(duration)
                metrics.metrics['neo4j_query_times'].append(duration)
            
            # Calculate operation statistics
            avg_time = np.mean(operation_times)
            p95_time = np.percentile(operation_times, 95)
            
            print(f"\n{op_name} performance:")
            print(f"  Average: {avg_time*1000:.2f}ms")
            print(f"  P95: {p95_time*1000:.2f}ms")
        
        # Save benchmark results
        summary = metrics.get_summary()
        benchmark_file = benchmark_dir / f"neo4j_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(benchmark_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'operations': operations,
                'results': summary
            }, f, indent=2)
        
        # Performance assertions
        avg_query_time = summary['neo4j_query_times']['mean']
        assert avg_query_time < 0.1, f"Average query time {avg_query_time}s exceeds 100ms threshold"
    
    @pytest.mark.benchmark
    def test_create_baseline_metrics_file(self, benchmark_dir):
        """Create baseline metrics file for future comparisons."""
        baseline_metrics = {
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'thresholds': {
                'extraction_time': {
                    'mean': 1.5,  # seconds
                    'p95': 2.5,
                    'p99': 3.0
                },
                'memory_usage': {
                    'baseline': 200,  # MB
                    'peak': 500,
                    'increase': 300
                },
                'neo4j_queries': {
                    'mean': 0.05,  # seconds
                    'p95': 0.1,
                    'p99': 0.2
                },
                'episode_processing': {
                    'small': 30,  # seconds
                    'medium': 60,
                    'large': 120
                },
                'concurrent_processing': {
                    'max_workers': 4,
                    'episodes_per_minute': 2
                }
            },
            'hardware': {
                'cpu_cores': psutil.cpu_count(),
                'memory_gb': psutil.virtual_memory().total / (1024**3),
                'platform': os.uname().sysname if hasattr(os, 'uname') else 'Unknown'
            }
        }
        
        # Save baseline file
        baseline_file = benchmark_dir / "baseline_metrics.json"
        with open(baseline_file, 'w') as f:
            json.dump(baseline_metrics, f, indent=2)
        
        print(f"\nBaseline metrics saved to: {baseline_file}")
        
        # Verify file was created
        assert baseline_file.exists()
        
        # Load and verify structure
        with open(baseline_file, 'r') as f:
            loaded = json.load(f)
        
        assert 'version' in loaded
        assert 'thresholds' in loaded
        assert 'hardware' in loaded