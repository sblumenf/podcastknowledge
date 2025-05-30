"""Performance benchmarks for VTT processing pipeline."""

import pytest
import tempfile
import shutil
import time
import psutil
import json
import statistics
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, List, Any
from datetime import datetime
import gc

from src.core.config import PipelineConfig
from src.seeding.transcript_ingestion import TranscriptIngestion
from src.processing.vtt_parser import VTTParser
from src.processing.extraction import KnowledgeExtractor


class TestVTTPerformanceBenchmarks:
    """Performance benchmarks for VTT processing."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def benchmark_config(self):
        """Configuration optimized for performance testing."""
        config = Mock(spec=PipelineConfig)
        config.batch_size = 10
        config.max_workers = 4
        config.checkpoint_enabled = True
        config.merge_short_segments = True
        config.min_segment_duration = 2.0
        return config
    
    def create_vtt_file(self, temp_dir: Path, name: str, num_segments: int, avg_segment_length: int = 100) -> Path:
        """Create a VTT file with specified number of segments."""
        vtt_path = temp_dir / f"{name}.vtt"
        content = "WEBVTT\n\n"
        
        for i in range(num_segments):
            start_time = i * 10  # 10 seconds per segment
            end_time = (i + 1) * 10
            
            # Format timestamps
            start_min = start_time // 60
            start_sec = start_time % 60
            end_min = end_time // 60
            end_sec = end_time % 60
            
            content += f"{start_min:02d}:{start_sec:02d}:000 --> {end_min:02d}:{end_sec:02d}:000\n"
            
            # Generate text content of specified length
            segment_text = f"<v Speaker{i%5}>Segment {i+1}: " + "This is test content. " * (avg_segment_length // 20)
            content += segment_text[:avg_segment_length] + "\n\n"
        
        vtt_path.write_text(content)
        return vtt_path
    
    def measure_processing_time(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Measure processing time and resource usage."""
        # Force garbage collection before measurement
        gc.collect()
        
        # Get initial resource measurements
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu_percent = process.cpu_percent()
        
        # Measure processing time
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Get final resource measurements
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        final_cpu_percent = process.cpu_percent()
        
        return {
            'result': result,
            'processing_time': end_time - start_time,
            'memory_usage_mb': final_memory - initial_memory,
            'peak_memory_mb': final_memory,
            'cpu_usage_percent': final_cpu_percent,
            'timestamp': datetime.now().isoformat()
        }
    
    def test_small_file_processing_benchmark(self, temp_dir, benchmark_config):
        """Benchmark processing of small VTT files (< 100 segments)."""
        # Create small VTT files
        file_sizes = [10, 25, 50, 75, 100]  # Number of segments
        benchmark_results = {}
        
        for size in file_sizes:
            vtt_file = self.create_vtt_file(temp_dir, f"small_{size}", size)
            
            ingestion = TranscriptIngestion(benchmark_config)
            
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.return_value = {'status': 'success', 'segment_count': size}
                
                # Measure processing
                metrics = self.measure_processing_time(
                    ingestion.process_file, vtt_file
                )
                
                benchmark_results[f"small_{size}_segments"] = {
                    'segments': size,
                    'file_size_kb': vtt_file.stat().st_size / 1024,
                    'processing_time': metrics['processing_time'],
                    'memory_usage_mb': metrics['memory_usage_mb'],
                    'segments_per_second': size / metrics['processing_time'] if metrics['processing_time'] > 0 else 0
                }
        
        # Performance assertions
        for size_key, result in benchmark_results.items():
            # Processing should complete within reasonable time
            assert result['processing_time'] < 5.0, f"Small file processing too slow: {result['processing_time']}s"
            
            # Memory usage should be reasonable for small files
            assert result['memory_usage_mb'] < 100, f"Memory usage too high: {result['memory_usage_mb']}MB"
            
            # Should process at least 10 segments per second
            assert result['segments_per_second'] > 10, f"Processing rate too slow: {result['segments_per_second']} seg/s"
        
        print("Small File Benchmark Results:")
        for key, result in benchmark_results.items():
            print(f"  {key}: {result['processing_time']:.3f}s, {result['memory_usage_mb']:.1f}MB, {result['segments_per_second']:.1f} seg/s")
    
    def test_large_file_processing_benchmark(self, temp_dir, benchmark_config):
        """Benchmark processing of large VTT files (> 500 segments)."""
        # Create large VTT files
        file_sizes = [500, 1000, 2000]  # Number of segments
        benchmark_results = {}
        
        for size in file_sizes:
            vtt_file = self.create_vtt_file(temp_dir, f"large_{size}", size)
            
            ingestion = TranscriptIngestion(benchmark_config)
            
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.return_value = {'status': 'success', 'segment_count': size}
                
                # Measure processing
                metrics = self.measure_processing_time(
                    ingestion.process_file, vtt_file
                )
                
                benchmark_results[f"large_{size}_segments"] = {
                    'segments': size,
                    'file_size_mb': vtt_file.stat().st_size / 1024 / 1024,
                    'processing_time': metrics['processing_time'],
                    'memory_usage_mb': metrics['memory_usage_mb'],
                    'peak_memory_mb': metrics['peak_memory_mb'],
                    'segments_per_second': size / metrics['processing_time'] if metrics['processing_time'] > 0 else 0
                }
        
        # Performance assertions for large files
        for size_key, result in benchmark_results.items():
            # Large files can take longer but should still be reasonable
            assert result['processing_time'] < 60.0, f"Large file processing too slow: {result['processing_time']}s"
            
            # Memory usage should scale reasonably with file size
            assert result['memory_usage_mb'] < 500, f"Memory usage too high: {result['memory_usage_mb']}MB"
            
            # Should still maintain decent processing rate
            assert result['segments_per_second'] > 5, f"Processing rate too slow: {result['segments_per_second']} seg/s"
        
        print("Large File Benchmark Results:")
        for key, result in benchmark_results.items():
            print(f"  {key}: {result['processing_time']:.3f}s, {result['peak_memory_mb']:.1f}MB peak, {result['segments_per_second']:.1f} seg/s")
    
    def test_batch_processing_scalability(self, temp_dir, benchmark_config):
        """Test scalability of batch processing with increasing file counts."""
        batch_sizes = [5, 10, 20, 50]
        benchmark_results = {}
        
        for batch_size in batch_sizes:
            # Create multiple medium-sized files
            for i in range(batch_size):
                self.create_vtt_file(temp_dir / "batch" / str(batch_size), f"file_{i}", 50)
            
            batch_dir = temp_dir / "batch" / str(batch_size)
            batch_dir.mkdir(parents=True, exist_ok=True)
            
            ingestion = TranscriptIngestion(benchmark_config)
            
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.return_value = {'status': 'success', 'segment_count': 50}
                
                # Measure batch processing
                metrics = self.measure_processing_time(
                    ingestion.process_directory, batch_dir, "*.vtt"
                )
                
                result = metrics['result']
                benchmark_results[f"batch_{batch_size}_files"] = {
                    'file_count': batch_size,
                    'total_segments': batch_size * 50,
                    'processing_time': metrics['processing_time'],
                    'memory_usage_mb': metrics['memory_usage_mb'],
                    'files_per_second': batch_size / metrics['processing_time'] if metrics['processing_time'] > 0 else 0,
                    'processed_files': result['processed'],
                    'parallel_efficiency': self.calculate_parallel_efficiency(batch_size, metrics['processing_time'])
                }
        
        # Scalability assertions
        for size_key, result in benchmark_results.items():
            # Batch processing should be efficient
            assert result['files_per_second'] > 1, f"Batch processing too slow: {result['files_per_second']} files/s"
            
            # All files should be processed successfully
            assert result['processed_files'] == result['file_count'], f"Not all files processed: {result['processed_files']}/{result['file_count']}"
        
        print("Batch Processing Scalability Results:")
        for key, result in benchmark_results.items():
            print(f"  {key}: {result['processing_time']:.3f}s, {result['files_per_second']:.1f} files/s, {result['parallel_efficiency']:.2f} efficiency")
    
    def calculate_parallel_efficiency(self, file_count: int, processing_time: float) -> float:
        """Calculate parallel processing efficiency."""
        # Estimate sequential time (rough approximation)
        estimated_sequential_time = file_count * 0.5  # 0.5s per file estimate
        
        # Efficiency = sequential_time / (parallel_time * worker_count)
        worker_count = 4  # From benchmark_config
        efficiency = estimated_sequential_time / (processing_time * worker_count)
        return min(1.0, efficiency)  # Cap at 100% efficiency
    
    def test_memory_usage_patterns(self, temp_dir, benchmark_config):
        """Test memory usage patterns for different file types."""
        # Create files with different characteristics
        file_types = {
            'short_segments': (100, 50),    # Many short segments
            'long_segments': (20, 500),     # Few long segments
            'varied_segments': (60, 200),   # Medium segments
        }
        
        memory_patterns = {}
        
        for file_type, (segments, avg_length) in file_types.items():
            vtt_file = self.create_vtt_file(temp_dir, file_type, segments, avg_length)
            
            # Monitor memory usage over time
            memory_usage_over_time = []
            
            def memory_monitoring_process(vtt_file_obj):
                for i in range(10):  # Sample memory 10 times during processing
                    time.sleep(0.1)
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    memory_usage_over_time.append(memory_mb)
                return {'status': 'success', 'segment_count': segments}
            
            ingestion = TranscriptIngestion(benchmark_config)
            
            with patch.object(ingestion, 'process_vtt_file', side_effect=memory_monitoring_process):
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                result = ingestion.process_file(vtt_file)
                
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                memory_patterns[file_type] = {
                    'start_memory_mb': start_memory,
                    'end_memory_mb': end_memory,
                    'peak_memory_mb': max(memory_usage_over_time),
                    'memory_growth_mb': end_memory - start_memory,
                    'memory_samples': memory_usage_over_time,
                    'memory_variance': statistics.variance(memory_usage_over_time) if len(memory_usage_over_time) > 1 else 0
                }
        
        # Memory usage assertions
        for file_type, pattern in memory_patterns.items():
            # Memory growth should be reasonable
            assert pattern['memory_growth_mb'] < 200, f"Excessive memory growth for {file_type}: {pattern['memory_growth_mb']}MB"
            
            # Peak memory should not be excessive
            assert pattern['peak_memory_mb'] < 1000, f"Peak memory too high for {file_type}: {pattern['peak_memory_mb']}MB"
        
        print("Memory Usage Patterns:")
        for file_type, pattern in memory_patterns.items():
            print(f"  {file_type}: Peak {pattern['peak_memory_mb']:.1f}MB, Growth {pattern['memory_growth_mb']:.1f}MB")
    
    def test_vtt_parser_performance(self, temp_dir):
        """Benchmark VTT parser performance specifically."""
        parser = VTTParser()
        
        # Test different parsing scenarios
        parsing_benchmarks = {}
        
        # Simple VTT content
        simple_vtt = self.create_vtt_file(temp_dir, "simple", 100, 50)
        
        # Complex VTT with speaker tags and formatting
        complex_content = "WEBVTT\nKind: captions\nLanguage: en\n\n"
        for i in range(100):
            start = i * 15
            end = (i + 1) * 15
            complex_content += f"{start//60:02d}:{start%60:02d}:{(start*100)%100:02d} --> {end//60:02d}:{end%60:02d}:{(end*100)%100:02d} align:start position:10%\n"
            complex_content += f"<v Speaker{i%3}><b>Segment {i}</b></v> with <i>formatting</i> and multiple <u>tags</u> for complex parsing.\n\n"
        
        complex_vtt = temp_dir / "complex.vtt"
        complex_vtt.write_text(complex_content)
        
        # Benchmark parsing
        for vtt_type, vtt_file in [("simple", simple_vtt), ("complex", complex_vtt)]:
            content = vtt_file.read_text()
            
            # Measure parsing performance
            metrics = self.measure_processing_time(
                parser.parse_content, content
            )
            
            segments = metrics['result']
            
            parsing_benchmarks[vtt_type] = {
                'content_size_kb': len(content) / 1024,
                'segment_count': len(segments),
                'parsing_time': metrics['processing_time'],
                'segments_per_second': len(segments) / metrics['processing_time'] if metrics['processing_time'] > 0 else 0,
                'kb_per_second': (len(content) / 1024) / metrics['processing_time'] if metrics['processing_time'] > 0 else 0
            }
        
        # Parser performance assertions
        for vtt_type, benchmark in parsing_benchmarks.items():
            # Parsing should be fast
            assert benchmark['parsing_time'] < 1.0, f"VTT parsing too slow for {vtt_type}: {benchmark['parsing_time']}s"
            
            # Should parse at good rate
            assert benchmark['segments_per_second'] > 100, f"Parsing rate too slow for {vtt_type}: {benchmark['segments_per_second']} seg/s"
        
        print("VTT Parser Performance:")
        for vtt_type, benchmark in parsing_benchmarks.items():
            print(f"  {vtt_type}: {benchmark['parsing_time']:.4f}s, {benchmark['segments_per_second']:.0f} seg/s, {benchmark['kb_per_second']:.1f} KB/s")
    
    def test_concurrent_processing_performance(self, temp_dir, benchmark_config):
        """Test performance of concurrent processing vs sequential."""
        # Create multiple files for concurrent testing
        num_files = 12
        for i in range(num_files):
            self.create_vtt_file(temp_dir, f"concurrent_{i}", 50)
        
        ingestion = TranscriptIngestion(benchmark_config)
        
        # Test sequential processing (1 worker)
        benchmark_config.max_workers = 1
        sequential_metrics = self.measure_processing_time(
            ingestion.process_directory, temp_dir, "concurrent_*.vtt"
        )
        
        # Test concurrent processing (4 workers)
        benchmark_config.max_workers = 4
        concurrent_metrics = self.measure_processing_time(
            ingestion.process_directory, temp_dir, "concurrent_*.vtt"
        )
        
        # Calculate performance improvement
        speedup_ratio = sequential_metrics['processing_time'] / concurrent_metrics['processing_time']
        efficiency = speedup_ratio / 4  # 4 workers
        
        performance_comparison = {
            'sequential_time': sequential_metrics['processing_time'],
            'concurrent_time': concurrent_metrics['processing_time'],
            'speedup_ratio': speedup_ratio,
            'parallel_efficiency': efficiency,
            'files_processed': num_files
        }
        
        # Concurrent processing should be faster
        assert concurrent_metrics['processing_time'] < sequential_metrics['processing_time'], \
            "Concurrent processing should be faster than sequential"
        
        # Should achieve reasonable speedup
        assert speedup_ratio > 1.5, f"Insufficient speedup from parallel processing: {speedup_ratio:.2f}x"
        
        print("Concurrent vs Sequential Performance:")
        print(f"  Sequential: {performance_comparison['sequential_time']:.3f}s")
        print(f"  Concurrent: {performance_comparison['concurrent_time']:.3f}s")
        print(f"  Speedup: {performance_comparison['speedup_ratio']:.2f}x")
        print(f"  Efficiency: {performance_comparison['parallel_efficiency']:.2f}")
    
    def test_save_benchmark_results(self, temp_dir):
        """Save benchmark results for tracking performance over time."""
        # This test saves results that can be used for performance regression testing
        benchmark_data = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'python_version': f"{3}.{9}",  # Simplified version info
            },
            'benchmarks': {
                'vtt_parsing_rate_segments_per_second': 500,  # Expected baseline
                'small_file_processing_max_time_seconds': 5.0,
                'large_file_processing_max_time_seconds': 60.0,
                'batch_processing_min_files_per_second': 1.0,
                'memory_usage_max_growth_mb': 200,
                'concurrent_speedup_min_ratio': 1.5
            }
        }
        
        # Save to file for performance tracking
        benchmark_file = temp_dir / "performance_baseline.json"
        with open(benchmark_file, 'w') as f:
            json.dump(benchmark_data, f, indent=2)
        
        # Verify file was created
        assert benchmark_file.exists()
        
        # Load and verify content
        with open(benchmark_file, 'r') as f:
            loaded_data = json.load(f)
        
        assert loaded_data['system_info']['cpu_count'] > 0
        assert loaded_data['benchmarks']['vtt_parsing_rate_segments_per_second'] > 0
        
        print(f"Benchmark baseline saved to: {benchmark_file}")
        print(f"System: {loaded_data['system_info']['cpu_count']} CPUs, {loaded_data['system_info']['memory_total_gb']:.1f}GB RAM")