"""Performance baseline tests for batch processing."""

import pytest
import time
import json
import statistics
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
import psutil
import tempfile

from src.seeding.batch_processor import BatchProcessor, BatchItem
from src.vtt.vtt_parser import VTTParser
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.storage.graph_storage import GraphStorageService


class TestBatchPerformance:
    """Establish performance baselines for batch processing."""
    
    @pytest.fixture
    def performance_config(self):
        """Configuration for performance testing."""
        return {
            "batch_size": 10,
            "max_workers": 4,
            "memory_limit_mb": 2048,
            "test_file_count": 10,
            "warning_threshold": 1.5  # 50% slower triggers warning
        }
    
    @pytest.fixture
    def standard_vtt_files(self, tmp_path):
        """Create standard VTT files for benchmarking."""
        files = []
        for i in range(10):
            vtt_content = f"""WEBVTT

00:00:00.000 --> 00:00:10.000
This is segment 1 of episode {i}. We're discussing important topics.

00:00:10.000 --> 00:00:20.000
Segment 2 contains more detailed information about the subject matter.

00:00:20.000 --> 00:00:30.000
In segment 3, we dive deeper into technical details and examples.

00:00:30.000 --> 00:00:40.000
Segment 4 provides context and background for our discussion.

00:00:40.000 --> 00:00:50.000
Finally, segment 5 wraps up with key takeaways and conclusions.
"""
            file_path = tmp_path / f"episode_{i:03d}.vtt"
            file_path.write_text(vtt_content)
            files.append(file_path)
        return files
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider with consistent performance."""
        provider = Mock()
        
        def generate_response(prompt, **kwargs):
            # Simulate consistent processing time
            time.sleep(0.05)  # 50ms per call
            return {
                "entities": [
                    {"name": f"Entity_{i}", "type": "CONCEPT", "confidence": 0.8}
                    for i in range(5)
                ],
                "relationships": [
                    {"source": "Entity_0", "target": "Entity_1", "type": "RELATES_TO"}
                ],
                "quotes": []
            }
        
        provider.generate.side_effect = generate_response
        return provider
    
    @pytest.fixture
    def mock_neo4j_driver(self):
        """Mock Neo4j driver with consistent performance."""
        driver = Mock()
        session = Mock()
        
        # Track operations for metrics
        operation_times = []
        
        def mock_run(cypher, **params):
            # Simulate database operation time
            start = time.time()
            time.sleep(0.01)  # 10ms per operation
            operation_times.append(time.time() - start)
            
            result = Mock()
            result.single.return_value = {"id": f"node-{len(operation_times)}"}
            return result
        
        session.run.side_effect = mock_run
        driver.session.return_value.__enter__.return_value = session
        driver._operation_times = operation_times
        
        return driver
    
    def test_batch_performance_baseline(self, performance_config, standard_vtt_files, 
                                      mock_llm_provider, mock_neo4j_driver):
        """Establish baseline performance for processing 10 standard VTT files."""
        # Initialize components
        batch_processor = BatchProcessor(
            max_workers=performance_config["max_workers"],
            batch_size=performance_config["batch_size"],
            memory_limit_mb=performance_config["memory_limit_mb"]
        )
        
        parser = VTTParser()
        extractor = KnowledgeExtractor(config=ExtractionConfig())
        extractor.llm_provider = mock_llm_provider
        
        storage = GraphStorageService(
            uri="bolt://localhost:7687",
            username="test",
            password="test"
        )
        storage._driver = mock_neo4j_driver
        
        # Metrics collection
        metrics = {
            "start_time": time.time(),
            "file_times": [],
            "memory_usage": [],
            "segment_counts": [],
            "entity_counts": [],
            "operation_counts": []
        }
        
        # Process function that measures performance
        def process_vtt_file(item: BatchItem):
            file_start = time.time()
            process = psutil.Process()
            
            # Parse VTT
            segments = parser.parse_file(item.data)
            metrics["segment_counts"].append(len(segments))
            
            # Extract knowledge
            total_entities = 0
            for segment in segments:
                result = extractor.extract_knowledge(segment)
                total_entities += len(result.entities)
                
                # Store in Neo4j
                for entity in result.entities:
                    storage.create_node(entity["type"], {
                        "name": entity["name"],
                        "confidence": entity.get("confidence", 1.0)
                    })
            
            metrics["entity_counts"].append(total_entities)
            
            # Record metrics
            file_time = time.time() - file_start
            metrics["file_times"].append(file_time)
            metrics["memory_usage"].append(process.memory_info().rss / 1024 / 1024)  # MB
            
            return {
                "file": str(item.data),
                "segments": len(segments),
                "entities": total_entities,
                "time": file_time
            }
        
        # Create batch items
        items = [
            BatchItem(id=f.stem, data=f)
            for f in standard_vtt_files
        ]
        
        # Process batch
        results = batch_processor.process_items(
            items=items,
            process_func=process_vtt_file
        )
        
        # Calculate final metrics
        metrics["end_time"] = time.time()
        metrics["total_time"] = metrics["end_time"] - metrics["start_time"]
        metrics["operation_counts"] = len(mock_neo4j_driver._operation_times)
        
        # Analyze performance
        performance_report = {
            "total_files": len(results),
            "total_time_seconds": round(metrics["total_time"], 2),
            "average_time_per_file": round(statistics.mean(metrics["file_times"]), 3),
            "median_time_per_file": round(statistics.median(metrics["file_times"]), 3),
            "max_time_per_file": round(max(metrics["file_times"]), 3),
            "min_time_per_file": round(min(metrics["file_times"]), 3),
            "total_segments": sum(metrics["segment_counts"]),
            "total_entities": sum(metrics["entity_counts"]),
            "average_memory_mb": round(statistics.mean(metrics["memory_usage"]), 1),
            "peak_memory_mb": round(max(metrics["memory_usage"]), 1),
            "neo4j_operations": metrics["operation_counts"],
            "files_per_second": round(len(results) / metrics["total_time"], 2),
            "timestamp": datetime.now().isoformat()
        }
        
        # Save baseline
        baseline_file = Path("benchmarks/batch_baseline.json")
        baseline_file.parent.mkdir(exist_ok=True)
        
        # Load existing baseline if exists
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                baseline = json.load(f)
        else:
            baseline = {}
        
        # Update baseline
        baseline["current"] = performance_report
        if "history" not in baseline:
            baseline["history"] = []
        baseline["history"].append(performance_report)
        
        # Keep only last 10 runs
        baseline["history"] = baseline["history"][-10:]
        
        # Save updated baseline
        with open(baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
        
        # Performance assertions
        assert performance_report["total_files"] == 10
        assert performance_report["total_time_seconds"] < 30  # Should complete in 30s
        assert performance_report["average_time_per_file"] < 3  # < 3s per file
        assert performance_report["peak_memory_mb"] < 500  # < 500MB peak
        
        # Check for performance regression
        if len(baseline.get("history", [])) > 1:
            previous = baseline["history"][-2]
            current = performance_report
            
            # Compare with previous run
            time_ratio = current["average_time_per_file"] / previous["average_time_per_file"]
            
            # Warn if performance degraded by threshold
            if time_ratio > performance_config["warning_threshold"]:
                pytest.fail(
                    f"Performance regression detected: {time_ratio:.2f}x slower than baseline"
                )
    
    def test_memory_usage_growth(self, performance_config, standard_vtt_files):
        """Test memory usage doesn't grow excessively during batch processing."""
        batch_processor = BatchProcessor(max_workers=2)
        
        # Track memory over time
        memory_samples = []
        process = psutil.Process()
        
        def memory_tracking_process(item):
            # Record memory before
            mem_before = process.memory_info().rss / 1024 / 1024
            
            # Simulate processing
            time.sleep(0.1)
            data = {"large_data": "x" * 10000}  # Create some data
            
            # Record memory after
            mem_after = process.memory_info().rss / 1024 / 1024
            memory_samples.append((mem_before, mem_after))
            
            return data
        
        # Process files
        items = [BatchItem(id=f"file_{i}", data=f) for f in standard_vtt_files[:5]]
        results = batch_processor.process_items(
            items=items,
            process_func=memory_tracking_process
        )
        
        # Analyze memory growth
        if len(memory_samples) > 2:
            first_sample = memory_samples[0][0]
            last_sample = memory_samples[-1][1]
            growth = last_sample - first_sample
            
            # Memory growth should be reasonable
            assert growth < 100  # Less than 100MB growth
            
            # Check for memory leaks (steady growth)
            differences = [s[1] - s[0] for s in memory_samples]
            avg_growth_per_file = statistics.mean(differences)
            assert avg_growth_per_file < 10  # < 10MB per file on average
    
    def test_concurrent_performance_scaling(self, standard_vtt_files):
        """Test how performance scales with different worker counts."""
        test_files = standard_vtt_files[:8]  # Use 8 files for even distribution
        
        def simple_process(item):
            time.sleep(0.2)  # Simulate work
            return {"processed": True}
        
        scaling_results = {}
        
        for worker_count in [1, 2, 4, 8]:
            processor = BatchProcessor(max_workers=worker_count)
            items = [BatchItem(id=f.stem, data=f) for f in test_files]
            
            start_time = time.time()
            results = processor.process_items(items, simple_process)
            end_time = time.time()
            
            total_time = end_time - start_time
            scaling_results[worker_count] = {
                "total_time": total_time,
                "time_per_file": total_time / len(test_files),
                "speedup": scaling_results.get(1, {}).get("total_time", total_time) / total_time
            }
        
        # Verify scaling improves performance
        assert scaling_results[2]["speedup"] > 1.5  # 2 workers > 1.5x speedup
        assert scaling_results[4]["speedup"] > 2.5  # 4 workers > 2.5x speedup
        
        # But not perfect linear scaling (overhead exists)
        assert scaling_results[4]["speedup"] < 4.0  # Less than perfect 4x
    
    def test_checkpoint_overhead(self, checkpoint_dir, standard_vtt_files):
        """Measure checkpoint operation overhead."""
        from src.seeding.checkpoint import ProgressCheckpoint
        
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        processor = BatchProcessor(max_workers=1)  # Single thread for accurate measurement
        
        # Process without checkpointing
        def process_without_checkpoint(item):
            time.sleep(0.05)
            return {"data": "result"}
        
        items = [BatchItem(id=f"item_{i}", data=f) for i, f in enumerate(standard_vtt_files[:5])]
        
        start = time.time()
        results = processor.process_items(items, process_without_checkpoint)
        time_without_checkpoint = time.time() - start
        
        # Process with checkpointing
        def process_with_checkpoint(item):
            time.sleep(0.05)
            result = {"data": "result"}
            checkpoint.mark_episode_complete(item.id, result)
            return result
        
        checkpoint._data = {"episodes": {}, "metadata": {}}  # Reset
        start = time.time()
        results = processor.process_items(items, process_with_checkpoint)
        time_with_checkpoint = time.time() - start
        
        # Calculate overhead
        overhead = time_with_checkpoint - time_without_checkpoint
        overhead_percent = (overhead / time_without_checkpoint) * 100
        
        # Checkpoint overhead should be reasonable
        assert overhead_percent < 20  # Less than 20% overhead
        
        # Save checkpoint metrics
        checkpoint_metrics = {
            "time_without_checkpoint": round(time_without_checkpoint, 3),
            "time_with_checkpoint": round(time_with_checkpoint, 3),
            "overhead_seconds": round(overhead, 3),
            "overhead_percent": round(overhead_percent, 1),
            "items_processed": len(items)
        }
        
        print(f"Checkpoint overhead: {overhead_percent:.1f}%")
    
    def test_performance_thresholds(self, performance_config):
        """Verify performance stays within acceptable thresholds."""
        # Load current baseline
        baseline_file = Path("benchmarks/batch_baseline.json")
        
        if not baseline_file.exists():
            pytest.skip("No baseline exists yet")
        
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        current = baseline.get("current", {})
        
        # Define thresholds
        thresholds = {
            "max_time_per_file": 5.0,  # 5 seconds max
            "max_memory_mb": 1000,  # 1GB max
            "min_files_per_second": 0.5,  # At least 0.5 files/second
            "max_total_time": 60  # 60 seconds for 10 files
        }
        
        # Check against thresholds
        if current:
            assert current.get("average_time_per_file", 0) < thresholds["max_time_per_file"]
            assert current.get("peak_memory_mb", 0) < thresholds["max_memory_mb"]
            assert current.get("files_per_second", 0) > thresholds["min_files_per_second"]
            assert current.get("total_time_seconds", 0) < thresholds["max_total_time"]
            
            # Check trend over time
            if len(baseline.get("history", [])) >= 3:
                recent = baseline["history"][-3:]
                avg_times = [r["average_time_per_file"] for r in recent]
                
                # Performance shouldn't degrade over time
                if avg_times[-1] > avg_times[0] * 1.2:  # 20% slower
                    pytest.fail("Performance degradation trend detected")