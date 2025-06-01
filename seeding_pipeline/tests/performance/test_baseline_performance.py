"""Baseline performance tests for the pipeline."""

import pytest
import time
from statistics import mean, stdev
from pathlib import Path
from src.seeding.orchestrator import VTTKnowledgeExtractor
from src.core.config import SeedingConfig
from src.storage.graph_storage import GraphStorageService


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.requires_docker
class TestBaselinePerformance:
    """Establish performance baselines for the pipeline."""
    
    def test_single_file_performance(self, test_data_dir, neo4j_driver, temp_dir):
        """Establish single file processing baseline."""
        config = SeedingConfig()
        config.neo4j_uri = neo4j_driver._uri
        config.neo4j_username = neo4j_driver._auth[0]
        config.neo4j_password = neo4j_driver._auth[1]
        config.checkpoint_dir = str(temp_dir / "checkpoints")
        config.use_schemaless_extraction = True
        
        orchestrator = VTTKnowledgeExtractor(config=config)
        orchestrator.storage_service = GraphStorageService(
            uri=config.neo4j_uri,
            username=config.neo4j_username,
            password=config.neo4j_password
        )
        orchestrator.storage_service._driver = neo4j_driver
        
        vtt_file = test_data_dir / "standard.vtt"
        
        class MockVTTFile:
            def __init__(self, path):
                self.path = Path(path)
                self.podcast_name = "Performance Test"
                self.episode_title = "Performance Episode"
        
        times = []
        
        for i in range(5):
            # Clear database between runs
            with neo4j_driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            
            start = time.time()
            result = orchestrator.process_vtt_files([MockVTTFile(vtt_file)])
            elapsed = time.time() - start
            
            if result["files_processed"] > 0:
                times.append(elapsed)
        
        if times:
            avg_time = mean(times)
            std_dev = stdev(times) if len(times) > 1 else 0.0
            
            # Performance assertion
            assert avg_time < 5.0  # Should process in < 5 seconds
            
            # Save baseline
            baseline_file = temp_dir / "performance_baseline.txt"
            with open(baseline_file, "w") as f:
                f.write(f"Single File Performance Baseline\n")
                f.write(f"================================\n")
                f.write(f"Average: {avg_time:.2f}s\n")
                f.write(f"StdDev: {std_dev:.2f}s\n")
                f.write(f"Min: {min(times):.2f}s\n")
                f.write(f"Max: {max(times):.2f}s\n")
                f.write(f"Runs: {len(times)}\n")
                
    def test_batch_performance(self, test_data_dir, neo4j_driver, temp_dir):
        """Test batch processing performance (files/second)."""
        config = SeedingConfig()
        config.neo4j_uri = neo4j_driver._uri
        config.neo4j_username = neo4j_driver._auth[0]
        config.neo4j_password = neo4j_driver._auth[1]
        config.checkpoint_dir = str(temp_dir / "checkpoints")
        config.batch_size = 10
        config.use_schemaless_extraction = True
        
        orchestrator = VTTKnowledgeExtractor(config=config)
        orchestrator.storage_service = GraphStorageService(
            uri=config.neo4j_uri,
            username=config.neo4j_username,
            password=config.neo4j_password
        )
        orchestrator.storage_service._driver = neo4j_driver
        
        vtt_file = test_data_dir / "minimal.vtt"
        
        class MockVTTFile:
            def __init__(self, path, index):
                self.path = Path(path)
                self.podcast_name = f"Batch Test {index}"
                self.episode_title = f"Episode {index}"
        
        # Test with different batch sizes
        batch_sizes = [1, 5, 10]
        results = {}
        
        for size in batch_sizes:
            # Clear database
            with neo4j_driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            
            batch = [MockVTTFile(vtt_file, i) for i in range(size)]
            
            start = time.time()
            result = orchestrator.process_vtt_files(batch)
            elapsed = time.time() - start
            
            files_processed = result["files_processed"]
            if files_processed > 0:
                files_per_second = files_processed / elapsed
                results[size] = {
                    'files_processed': files_processed,
                    'time': elapsed,
                    'files_per_second': files_per_second
                }
        
        # Save batch performance results
        if results:
            baseline_file = temp_dir / "batch_performance_baseline.txt"
            with open(baseline_file, "w") as f:
                f.write(f"Batch Performance Baseline\n")
                f.write(f"=========================\n")
                for size, metrics in results.items():
                    f.write(f"\nBatch Size: {size}\n")
                    f.write(f"Files Processed: {metrics['files_processed']}\n")
                    f.write(f"Total Time: {metrics['time']:.2f}s\n")
                    f.write(f"Files/Second: {metrics['files_per_second']:.2f}\n")
                    
    def test_memory_usage_growth(self, test_data_dir, neo4j_driver, temp_dir):
        """Test memory usage growth with increasing batch sizes."""
        import psutil
        import os
        
        config = SeedingConfig()
        config.neo4j_uri = neo4j_driver._uri
        config.neo4j_username = neo4j_driver._auth[0]
        config.neo4j_password = neo4j_driver._auth[1]
        config.checkpoint_dir = str(temp_dir / "checkpoints")
        config.use_schemaless_extraction = True
        
        orchestrator = VTTKnowledgeExtractor(config=config)
        orchestrator.storage_service = GraphStorageService(
            uri=config.neo4j_uri,
            username=config.neo4j_username,
            password=config.neo4j_password
        )
        orchestrator.storage_service._driver = neo4j_driver
        
        vtt_file = test_data_dir / "minimal.vtt"
        process = psutil.Process(os.getpid())
        
        class MockVTTFile:
            def __init__(self, path, index):
                self.path = Path(path)
                self.podcast_name = f"Memory Test {index}"
                self.episode_title = f"Episode {index}"
        
        memory_results = []
        
        for batch_size in [1, 5, 10]:
            # Get initial memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            batch = [MockVTTFile(vtt_file, i) for i in range(batch_size)]
            orchestrator.process_vtt_files(batch)
            
            # Get final memory
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = final_memory - initial_memory
            
            memory_results.append({
                'batch_size': batch_size,
                'initial_mb': initial_memory,
                'final_mb': final_memory,
                'growth_mb': memory_growth
            })
        
        # Save memory usage results
        baseline_file = temp_dir / "memory_usage_baseline.txt"
        with open(baseline_file, "w") as f:
            f.write(f"Memory Usage Baseline\n")
            f.write(f"====================\n")
            for result in memory_results:
                f.write(f"\nBatch Size: {result['batch_size']}\n")
                f.write(f"Initial Memory: {result['initial_mb']:.2f} MB\n")
                f.write(f"Final Memory: {result['final_mb']:.2f} MB\n")
                f.write(f"Growth: {result['growth_mb']:.2f} MB\n")
        
        # Assert reasonable memory growth
        if memory_results:
            max_growth = max(r['growth_mb'] for r in memory_results)
            assert max_growth < 500  # Should not grow more than 500MB for small batches