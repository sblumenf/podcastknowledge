"""Core tests for batch processing functionality."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import threading
import time

import pytest

from src.seeding.batch_processor import (
    BatchProcessor, BatchItem, BatchResult, create_batch_items
)
from src.seeding.checkpoint import ProgressCheckpoint
from src.core.exceptions import BatchProcessingError


class TestBatchProcessingCore:
    """Test batch processing of multiple VTT files."""
    
    @pytest.fixture
    def batch_processor(self):
        """Create batch processor instance."""
        return BatchProcessor(
            max_workers=2,
            batch_size=5,
            use_processes=False,  # Use threads for testing
            memory_limit_mb=1024
        )
    
    @pytest.fixture
    def sample_vtt_files(self):
        """Create list of sample VTT file paths."""
        return [
            Path(f"test_episode_{i}.vtt")
            for i in range(1, 6)
        ]
    
    @pytest.fixture
    def process_function(self):
        """Mock processing function for VTT files."""
        def mock_process(item: BatchItem) -> dict:
            # Simulate processing time
            time.sleep(0.1)
            
            # Simulate successful processing
            return {
                "file": str(item.data),
                "entities": 10,
                "relationships": 5,
                "processing_time": 0.1
            }
        return mock_process
    
    @pytest.fixture
    def checkpoint_dir(self, tmp_path):
        """Create temporary checkpoint directory."""
        return tmp_path / "checkpoints"
    
    def test_process_multiple_files(self, batch_processor, sample_vtt_files, process_function):
        """Test processing 5 VTT files sequentially."""
        # Create batch items
        items = create_batch_items(
            sample_vtt_files,
            id_func=lambda f: f.stem
        )
        
        # Process batch
        results = batch_processor.process_items(
            items=items,
            process_func=process_function
        )
        
        # Verify all files processed
        assert len(results) == 5
        assert all(r.success for r in results)
        
        # Verify results
        for i, result in enumerate(results):
            assert result.item_id == f"test_episode_{i+1}"
            assert result.result["entities"] == 10
            assert result.result["relationships"] == 5
    
    def test_checkpoint_recovery(self, batch_processor, sample_vtt_files, 
                                process_function, checkpoint_dir):
        """Test recovery from checkpoint after simulated failure."""
        # Create checkpoint
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        checkpoint.mark_episode_complete("0", {})  # First item ID
        checkpoint.mark_episode_complete("1", {})  # Second item ID
        
        # Process with checkpoint - should skip completed
        items = create_batch_items(sample_vtt_files)
        
        processed_count = 0
        def counting_process_func(item):
            nonlocal processed_count
            processed_count += 1
            return process_function(item)
        
        # Filter out completed items
        completed_ids = checkpoint.get_completed_episodes()
        filtered_items = [
            item for item in items 
            if item.id not in completed_ids
        ]
        
        results = batch_processor.process_items(
            items=filtered_items,
            process_func=counting_process_func
        )
        
        # Should only process 3 files (3, 4, 5)
        assert len(results) == 3
        assert processed_count == 3
        assert all(r.item_id in ("2", "3", "4") for r in results)
    
    def test_duplicate_file_handling(self, batch_processor, process_function):
        """Test processing same file twice."""
        # Create duplicate items
        vtt_file = Path("duplicate_episode.vtt")
        items = [
            BatchItem(id="dup1", data=vtt_file),
            BatchItem(id="dup2", data=vtt_file)  # Same file, different ID
        ]
        
        # Track processed files
        processed_files = []
        def tracking_process_func(item):
            processed_files.append(str(item.data))
            return process_function(item)
        
        results = batch_processor.process_items(
            items=items,
            process_func=tracking_process_func
        )
        
        # Both should be processed (different IDs)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert processed_files == [str(vtt_file), str(vtt_file)]
    
    def test_concurrent_processing(self, batch_processor, sample_vtt_files):
        """Test basic concurrent processing."""
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()
        
        def concurrent_process_func(item):
            nonlocal concurrent_count, max_concurrent
            
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            # Simulate work
            time.sleep(0.2)
            
            with lock:
                concurrent_count -= 1
            
            return {"processed": True}
        
        # Process with 2 workers
        items = create_batch_items(sample_vtt_files[:4])  # 4 items
        
        results = batch_processor.process_items(
            items=items,
            process_func=concurrent_process_func
        )
        
        # Verify concurrent execution
        assert len(results) == 4
        assert max_concurrent >= 2  # At least 2 concurrent
        assert max_concurrent <= batch_processor.max_workers
    
    def test_batch_size_handling(self, batch_processor):
        """Test batch size limits."""
        # Create many items
        items = [
            BatchItem(id=f"item_{i}", data=f"file_{i}.vtt")
            for i in range(20)
        ]
        
        batch_sizes = []
        
        def batch_tracking_func(item):
            # Track batch processing
            return {"id": item.id}
        
        # Override batch size
        batch_processor.batch_size = 5
        
        # Process items
        results = batch_processor.process_items(
            items=items,
            process_func=batch_tracking_func
        )
        
        # Should process all items
        assert len(results) == 20
        
        # Check batches were created properly
        # (This would be internal to batch processor)
        assert all(r.success for r in results)
    
    def test_memory_limit_enforcement(self, batch_processor):
        """Test memory limit enforcement."""
        # Set low memory limit
        batch_processor.memory_limit_mb = 100
        
        # Mock memory check to simulate high usage
        with patch.object(batch_processor, '_check_memory_usage') as mock_check:
            # First call returns True (memory OK), then False (limit exceeded)
            mock_check.side_effect = [True, False, True, True]
            
            items = create_batch_items([f"file_{i}.vtt" for i in range(10)])
            
            # Track when processing happens
            process_times = []
            
            def memory_aware_process(item):
                process_times.append(time.time())
                return {"processed": True}
            
            results = batch_processor.process_items(
                items=items,
                process_func=memory_aware_process
            )
            
            # Should still process all items, but with pauses
            assert len(results) == 10
            
            # Memory check should have been called
            assert mock_check.call_count >= 2
    
    def test_progress_callback(self, batch_processor, sample_vtt_files, process_function):
        """Test progress callback functionality."""
        progress_updates = []
        
        def progress_callback(completed, total):
            progress_updates.append((completed, total))
        
        # Set progress callback
        batch_processor.progress_callback = progress_callback
        
        # Process items
        items = create_batch_items(sample_vtt_files)
        results = batch_processor.process_items(
            items=items,
            process_func=process_function
        )
        
        # Verify progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1] == (5, 5)  # Final should be all complete
        
        # Progress should be monotonic
        for i in range(1, len(progress_updates)):
            assert progress_updates[i][0] >= progress_updates[i-1][0]
    
    def test_error_handling_per_item(self, batch_processor):
        """Test handling of individual item failures."""
        def failing_process_func(item):
            if "fail" in item.id:
                raise ValueError(f"Processing failed for {item.id}")
            return {"success": True}
        
        # Mix of success and failure items
        items = [
            BatchItem(id="success_1", data="file1.vtt"),
            BatchItem(id="fail_1", data="file2.vtt"),
            BatchItem(id="success_2", data="file3.vtt"),
            BatchItem(id="fail_2", data="file4.vtt"),
            BatchItem(id="success_3", data="file5.vtt")
        ]
        
        results = batch_processor.process_items(
            items=items,
            process_func=failing_process_func
        )
        
        # Should get results for all items
        assert len(results) == 5
        
        # Check success/failure pattern
        success_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        assert len(success_results) == 3
        assert len(failed_results) == 2
        
        # Verify error messages
        for result in failed_results:
            assert "Processing failed" in result.error
    
    def test_batch_performance_tracking(self, batch_processor, sample_vtt_files, process_function):
        """Test performance metrics collection."""
        # Process items
        items = create_batch_items(sample_vtt_files)
        results = batch_processor.process_items(
            items=items,
            process_func=process_function
        )
        
        # Get statistics
        stats = batch_processor.get_statistics()
        
        # Verify statistics
        assert "total_processed" in stats
        assert "success_count" in stats
        assert "failure_count" in stats
        assert "average_processing_time" in stats
        assert "performance_metrics" in stats
        
        assert stats["total_processed"] == 5
        assert stats["success_count"] == 5
        assert stats["failure_count"] == 0
        assert stats["average_processing_time"] > 0
    
    def test_schema_discovery_tracking(self):
        """Test tracking of discovered entity types during batch processing."""
        # Create a batch processor in schemaless mode
        batch_processor = BatchProcessor(
            max_workers=2,
            batch_size=5,
            use_processes=False,
            memory_limit_mb=1024,
            is_schemaless=True
        )
        def discovery_process_func(item):
            # Simulate discovering new entity types
            # Return results in the format expected by BatchProcessor
            if item.id == "episode_1":
                # Set metadata on the item to be tracked
                item.metadata = {
                    'discovered_types': ["PERSON", "ORGANIZATION"]
                }
                return {
                    "entities": [
                        {"type": "PERSON", "name": "John"},
                        {"type": "ORGANIZATION", "name": "Acme Corp"}
                    ]
                }
            elif item.id == "episode_2":
                item.metadata = {
                    'discovered_types': ["PERSON", "TECHNOLOGY"]
                }
                return {
                    "entities": [
                        {"type": "PERSON", "name": "Jane"},
                        {"type": "TECHNOLOGY", "name": "AI"}  # New type
                    ]
                }
            else:
                return {"entities": []}
        
        items = [
            BatchItem(id=f"episode_{i}", data=f"file_{i}.vtt")
            for i in range(1, 4)
        ]
        
        # Process and track schema
        results = batch_processor.process_items(
            items=items,
            process_func=discovery_process_func
        )
        
        # Track discovered types
        # Note: track_schema_discovery is called automatically in process_items when is_schemaless=True
        
        # Get schema report
        schema_report = batch_processor.get_schema_evolution_report()
        
        # Verify schema tracking
        assert "entity_types" in schema_report
        assert "type_distribution" in schema_report
        assert "most_common_types" in schema_report
        
        discovered = set(schema_report["entity_types"])
        assert "PERSON" in discovered
        assert "ORGANIZATION" in discovered
        assert "TECHNOLOGY" in discovered