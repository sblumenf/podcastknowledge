"""Tests for failure recovery and error handling."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import time

import pytest

from src.core.exceptions import (
    PodcastKGError, ProviderError, ConnectionError, CheckpointError
)
from src.extraction.extraction import KnowledgeExtractor
from src.seeding.batch_processor import BatchProcessor, BatchItem
from src.seeding.checkpoint import ProgressCheckpoint
from src.storage.graph_storage import GraphStorageService


class TestFailureRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.fixture
    def checkpoint_dir(self, tmp_path):
        """Create temporary checkpoint directory."""
        return tmp_path / "checkpoints"
    
    @pytest.fixture
    def batch_processor(self):
        """Create batch processor for testing."""
        return BatchProcessor(
            max_workers=2,
            batch_size=5,
            use_processes=False
        )
    
    @pytest.fixture
    def mock_extractor(self):
        """Create mock knowledge extractor."""
        extractor = Mock()
        extractor.extract_knowledge.return_value = Mock(
            entities=[{"name": "Test", "type": "CONCEPT"}],
            relationships=[],
            quotes=[],
            metadata={}
        )
        return extractor
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock graph storage."""
        storage = Mock(spec=GraphStorageService)
        storage.create_node.return_value = "node-id"
        storage.create_relationship.return_value = "rel-id"
        return storage
    
    def test_recover_from_llm_failure(self, batch_processor, mock_extractor):
        """Test recovery when LLM API fails mid-batch."""
        # Setup: Make LLM fail for specific items
        call_count = 0
        def llm_with_failures(segment):
            nonlocal call_count
            call_count += 1
            if call_count in [2, 4]:  # Fail on 2nd and 4th calls
                raise ProviderError("test_provider", "LLM API rate limit exceeded")
            return Mock(entities=[], relationships=[], quotes=[], metadata={})
        
        mock_extractor.extract_knowledge.side_effect = llm_with_failures
        
        # Create batch items
        items = [
            BatchItem(id=f"episode_{i}", data=f"segment_{i}")
            for i in range(1, 6)
        ]
        
        # Process function that uses extractor
        def process_with_llm(item):
            result = mock_extractor.extract_knowledge(item.data)
            return {"extracted": len(result.entities)}
        
        # Process batch
        results = batch_processor.process_items(
            items=items,
            process_func=process_with_llm
        )
        
        # Verify handling
        assert len(results) == 5
        success_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        assert len(success_results) == 3  # Items 1, 3, 5
        assert len(failed_results) == 2   # Items 2, 4
        
        # Check error messages
        for result in failed_results:
            assert "rate limit" in result.error.lower()
    
    def test_recover_from_neo4j_disconnect(self, batch_processor, mock_storage):
        """Test recovery when database connection is lost."""
        # Setup: Make Neo4j fail intermittently
        call_count = 0
        def neo4j_with_disconnects(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Disconnect on 3rd call
                raise ConnectionError("Lost connection to Neo4j")
            return f"node-{call_count}"
        
        mock_storage.create_node.side_effect = neo4j_with_disconnects
        
        # Process function that uses storage
        def process_with_storage(item):
            node_id = mock_storage.create_node("TestNode", {"id": item.id})
            return {"node_id": node_id}
        
        # Create items
        items = [BatchItem(id=f"item_{i}", data=f"data_{i}") for i in range(1, 5)]
        
        # Process batch
        results = batch_processor.process_items(
            items=items,
            process_func=process_with_storage
        )
        
        # Verify recovery
        assert len(results) == 4
        assert sum(1 for r in results if r.success) == 3
        assert sum(1 for r in results if not r.success) == 1
        
        # Failed item should be item 3
        failed = next(r for r in results if not r.success)
        assert failed.item_id == "item_3"
        assert "connection" in failed.error.lower()
    
    def test_recover_from_corrupt_vtt(self, batch_processor):
        """Test handling of corrupted VTT file in batch."""
        from src.vtt.vtt_parser import VTTParser
        from src.core.exceptions import ValidationError
        
        parser = VTTParser()
        
        # Create mix of valid and corrupt VTT content
        vtt_contents = {
            "valid1.vtt": """WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nValid content 1""",
            "corrupt1.vtt": """NOT_VTT\n\nThis is not valid VTT""",
            "valid2.vtt": """WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nValid content 2""",
            "corrupt2.vtt": """WEBVTT\n\n00:00:00 -> 00:00:05\nBad timestamp format""",
            "valid3.vtt": """WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nValid content 3"""
        }
        
        # Process function that parses VTT
        def process_vtt(item):
            content = vtt_contents[item.id]
            try:
                segments = parser.parse_content(content)
                return {"segments": len(segments)}
            except ValidationError as e:
                raise ValidationError(f"Invalid VTT format: {str(e)}")
        
        # Create items
        items = [BatchItem(id=name, data=name) for name in vtt_contents.keys()]
        
        # Process batch
        results = batch_processor.process_items(
            items=items,
            process_func=process_vtt
        )
        
        # Verify handling
        assert len(results) == 5
        valid_results = [r for r in results if r.success and r.item_id.startswith("valid")]
        corrupt_results = [r for r in results if not r.success and r.item_id.startswith("corrupt")]
        
        assert len(valid_results) == 3
        assert len(corrupt_results) == 2
        
        # All valid files should process successfully
        for result in valid_results:
            assert result.result["segments"] >= 1
    
    def test_checkpoint_integrity(self, checkpoint_dir):
        """Test recovery from corrupted checkpoint file."""
        # Create checkpoint
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        
        # Write some valid data
        checkpoint.mark_episode_complete("ep1", {"entities": 10})
        checkpoint.mark_episode_complete("ep2", {"entities": 15})
        
        # Corrupt the checkpoint file
        checkpoint_file = checkpoint_dir / "progress.json"
        with open(checkpoint_file, 'w') as f:
            f.write("{ corrupted json file")
        
        # Try to load corrupted checkpoint
        with pytest.raises(CheckpointError):
            corrupted_checkpoint = ProgressCheckpoint(checkpoint_dir)
            corrupted_checkpoint.load()
        
        # Recovery: Create new checkpoint with backup
        backup_file = checkpoint_dir / "progress.json.backup"
        if checkpoint_file.exists():
            import shutil
            shutil.copy(checkpoint_file, backup_file)
        
        # Create fresh checkpoint
        new_checkpoint = ProgressCheckpoint(checkpoint_dir)
        new_checkpoint._data = {"episodes": {}, "metadata": {}}  # Reset
        
        # Should be able to continue
        assert new_checkpoint.get_completed_episodes() == []
    
    def test_partial_batch_failure(self, batch_processor):
        """Test handling when part of a batch fails."""
        # Process function that fails for specific patterns
        def selective_failure(item):
            if int(item.id.split('_')[1]) % 3 == 0:  # Fail every 3rd item
                raise RuntimeError(f"Processing failed for {item.id}")
            return {"processed": True, "id": item.id}
        
        # Create larger batch
        items = [BatchItem(id=f"item_{i}", data=f"data_{i}") for i in range(1, 11)]
        
        # Process
        results = batch_processor.process_items(
            items=items,
            process_func=selective_failure
        )
        
        # Verify partial success
        assert len(results) == 10
        
        success_ids = [r.item_id for r in results if r.success]
        failed_ids = [r.item_id for r in results if not r.success]
        
        # Items 3, 6, 9 should fail
        assert "item_3" in failed_ids
        assert "item_6" in failed_ids
        assert "item_9" in failed_ids
        
        # Others should succeed
        assert len(success_ids) == 7
        assert all(f"item_{i}" in success_ids for i in [1, 2, 4, 5, 7, 8, 10])
    
    def test_cascading_failure_prevention(self, batch_processor):
        """Test that one failure doesn't cascade to others."""
        # Shared state that could cause cascading failures
        shared_state = {"connections": 5}
        
        def stateful_process(item):
            # Simulate resource consumption
            if item.id == "bad_item":
                # This failure shouldn't affect others
                shared_state["connections"] = 0
                raise RuntimeError("Resource exhausted")
            
            # Check if resources available
            if shared_state["connections"] <= 0:
                raise RuntimeError("No connections available")
            
            return {"processed": True}
        
        # Process items including bad one
        items = [
            BatchItem(id="good_1", data="data"),
            BatchItem(id="bad_item", data="data"),
            BatchItem(id="good_2", data="data"),
            BatchItem(id="good_3", data="data")
        ]
        
        results = batch_processor.process_items(
            items=items,
            process_func=stateful_process
        )
        
        # Only bad_item should fail
        failed = [r for r in results if not r.success]
        assert len(failed) == 1
        assert failed[0].item_id == "bad_item"
        
        # Others should succeed (isolation working)
        success = [r for r in results if r.success]
        assert len(success) == 3
    
    def test_retry_mechanism(self):
        """Test retry logic for transient failures."""
        from src.utils.retry import retry
        
        # Track attempts
        attempt_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:  # Fail first 2 attempts
                raise ConnectionError("Temporary network error")
            
            return "Success"
        
        # Should succeed on 3rd attempt
        result = flaky_operation()
        assert result == "Success"
        assert attempt_count == 3
    
    def test_graceful_shutdown_during_processing(self, batch_processor):
        """Test graceful shutdown when processing is interrupted."""
        import threading
        
        # Long-running process
        def slow_process(item):
            time.sleep(0.5)  # Simulate slow processing
            return {"processed": True}
        
        # Large batch
        items = [BatchItem(id=f"item_{i}", data=f"data_{i}") for i in range(20)]
        
        # Start processing in thread
        results_container = []
        processing_thread = threading.Thread(
            target=lambda: results_container.extend(
                batch_processor.process_items(items, slow_process)
            )
        )
        processing_thread.start()
        
        # Simulate shutdown after short delay
        time.sleep(0.2)
        batch_processor._shutdown = True  # Signal shutdown
        
        # Wait for graceful completion
        processing_thread.join(timeout=2.0)
        
        # Should have processed some items before shutdown
        assert len(results_container) > 0
        assert len(results_container) < 20  # But not all
    
    def test_checkpoint_recovery_with_schema_evolution(self, checkpoint_dir):
        """Test checkpoint recovery when schema has evolved."""
        # Original checkpoint with old schema
        checkpoint = ProgressCheckpoint(checkpoint_dir)
        checkpoint._data = {
            "episodes": {
                "ep1": {"old_field": "value"},
                "ep2": {"old_field": "value2"}
            },
            "metadata": {"version": "1.0"}
        }
        checkpoint.save()
        
        # Load with new schema expectations
        new_checkpoint = ProgressCheckpoint(checkpoint_dir)
        new_checkpoint.load()
        
        # Should handle missing fields gracefully
        completed = new_checkpoint.get_completed_episodes()
        assert "ep1" in completed
        assert "ep2" in completed
        
        # Add new episode with new schema
        new_checkpoint.mark_episode_complete("ep3", {
            "new_field": "new_value",
            "entities_count": 10
        })
        
        # Should coexist with old data
        assert len(new_checkpoint.get_completed_episodes()) == 3
    
    def test_concurrent_failure_handling(self, batch_processor):
        """Test handling failures in concurrent processing."""
        # Track concurrent failures
        failure_times = []
        lock = threading.Lock()
        
        def concurrent_failing_process(item):
            if "fail" in item.id:
                with lock:
                    failure_times.append(time.time())
                time.sleep(0.1)  # Simulate processing
                raise RuntimeError(f"Concurrent failure: {item.id}")
            
            time.sleep(0.2)  # Successful items take longer
            return {"processed": True}
        
        # Mix of success and failure items
        items = [
            BatchItem(id=f"{'fail' if i % 3 == 0 else 'success'}_{i}", data=f"data_{i}")
            for i in range(9)
        ]
        
        # Process with concurrency
        batch_processor.max_workers = 3
        results = batch_processor.process_items(
            items=items,
            process_func=concurrent_failing_process
        )
        
        # Verify all items processed despite failures
        assert len(results) == 9
        
        # Check failure isolation
        failed = [r for r in results if not r.success]
        assert len(failed) == 3  # Items 0, 3, 6
        
        # Failures shouldn't block successful processing
        success = [r for r in results if r.success]
        assert len(success) == 6