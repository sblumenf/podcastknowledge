"""Tests for VTT batch processing scenarios."""

import pytest
import tempfile
import shutil
import time
import psutil
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import signal
from typing import List, Dict, Any

from src.core.config import PipelineConfig
from src.seeding.transcript_ingestion import TranscriptIngestion
from src.seeding.checkpoint import ProgressCheckpoint
from src.processing.vtt_parser import VTTParser
from src.core.exceptions import ValidationError, PipelineError


class TestVTTBatchProcessing:
    """Test suite for VTT batch processing scenarios."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def mock_config(self):
        """Create mock pipeline configuration for batch processing."""
        config = Mock(spec=PipelineConfig)
        config.batch_size = 5
        config.max_workers = 3
        config.checkpoint_enabled = True
        config.checkpoint_dir = "test_checkpoints"
        config.merge_short_segments = True
        config.min_segment_duration = 2.0
        config.max_memory_usage_mb = 1024
        config.processing_timeout_seconds = 300
        return config
    
    @pytest.fixture
    def mixed_file_directory(self, temp_dir):
        """Create directory with mixed file types for testing."""
        # Valid VTT files
        valid_vtt_files = []
        
        # Small VTT file
        small_vtt = temp_dir / "small_episode.vtt"
        small_vtt.write_text("""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>This is a short test episode.

00:00:05.000 --> 00:00:10.000
<v Speaker>It has just two segments for testing.
""")
        valid_vtt_files.append(small_vtt)
        
        # Medium VTT file
        medium_vtt = temp_dir / "medium_episode.vtt"
        medium_content = "WEBVTT\n\n"
        for i in range(20):
            start_time = i * 10
            end_time = (i + 1) * 10
            medium_content += f"{start_time//60:02d}:{start_time%60:02d}:{(start_time*1000)%1000:03d} --> {end_time//60:02d}:{end_time%60:02d}:{(end_time*1000)%1000:03d}\n"
            medium_content += f"<v Speaker{i%3}>Segment {i+1} with some test content about technology and innovation.\n\n"
        medium_vtt.write_text(medium_content)
        valid_vtt_files.append(medium_vtt)
        
        # Large VTT file (simulated)
        large_vtt = temp_dir / "large_episode.vtt"
        large_content = "WEBVTT\n\n"
        for i in range(100):
            start_time = i * 30
            end_time = (i + 1) * 30
            large_content += f"{start_time//60:02d}:{start_time%60:02d}:{(start_time*1000)%1000:03d} --> {end_time//60:02d}:{end_time%60:02d}:{(end_time*1000)%1000:03d}\n"
            large_content += f"<v Speaker{i%5}>This is segment {i+1} discussing various topics in detail. " \
                           f"We cover technology, science, business, and culture in this comprehensive episode. " \
                           f"Each segment provides valuable insights and information for our listeners.\n\n"
        large_vtt.write_text(large_content)
        valid_vtt_files.append(large_vtt)
        
        # Invalid files
        invalid_files = []
        
        # Not a VTT file
        text_file = temp_dir / "not_vtt.txt"
        text_file.write_text("This is just a text file, not VTT format.")
        invalid_files.append(text_file)
        
        # Corrupted VTT file
        corrupted_vtt = temp_dir / "corrupted.vtt"
        corrupted_vtt.write_text("""WEBVTT

00:00:00.000 --> INVALID_TIMESTAMP
<v Speaker>This has invalid timestamps.

MALFORMED_SEGMENT
No proper format here.
""")
        invalid_files.append(corrupted_vtt)
        
        # Empty VTT file
        empty_vtt = temp_dir / "empty.vtt"
        empty_vtt.write_text("WEBVTT\n\n")
        invalid_files.append(empty_vtt)
        
        # VTT file without WEBVTT header
        no_header_vtt = temp_dir / "no_header.vtt"
        no_header_vtt.write_text("""00:00:00.000 --> 00:00:05.000
<v Speaker>Missing WEBVTT header.
""")
        invalid_files.append(no_header_vtt)
        
        return {
            'valid': valid_vtt_files,
            'invalid': invalid_files,
            'all': valid_vtt_files + invalid_files
        }
    
    def test_mixed_file_type_processing(self, temp_dir, mixed_file_directory, mock_config):
        """Test batch processing with mixed valid and invalid files."""
        ingestion = TranscriptIngestion(mock_config)
        
        # Scan directory for VTT files
        found_files = ingestion.scan_directory(temp_dir, pattern="*.vtt", recursive=False)
        
        # Should find all VTT files (including invalid ones)
        assert len(found_files) == 6  # 3 valid + 3 invalid VTT files
        
        # Process directory and check results
        with patch.object(ingestion, 'process_vtt_file') as mock_process:
            # Mock processing results based on file validity
            def mock_process_side_effect(vtt_file):
                if 'corrupted' in str(vtt_file.path) or 'no_header' in str(vtt_file.path):
                    return {'status': 'error', 'error': 'Invalid VTT format'}
                elif 'empty' in str(vtt_file.path):
                    return {'status': 'skipped', 'reason': 'empty_file'}
                else:
                    return {
                        'status': 'success',
                        'segment_count': 2 if 'small' in str(vtt_file.path) else 
                                       20 if 'medium' in str(vtt_file.path) else 100
                    }
            
            mock_process.side_effect = mock_process_side_effect
            
            results = ingestion.process_directory(temp_dir, pattern="*.vtt")
            
            assert results['total_files'] == 6
            assert results['processed'] == 3  # 3 valid files
            assert results['errors'] == 2     # 2 corrupted files
            assert results['skipped'] == 1    # 1 empty file
    
    def test_parallel_processing_performance(self, temp_dir, mixed_file_directory, mock_config):
        """Test parallel processing with multiple workers."""
        import time
        
        # Create multiple valid VTT files for parallel processing
        for i in range(10):
            vtt_file = temp_dir / f"parallel_test_{i}.vtt"
            vtt_file.write_text(f"""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Parallel test episode {i}.

00:00:05.000 --> 00:00:10.000
<v Speaker>Processing segment {i} for performance testing.
""")
        
        ingestion = TranscriptIngestion(mock_config)
        
        # Test with single worker
        start_time = time.time()
        with patch.object(ingestion, 'process_vtt_file') as mock_process:
            mock_process.return_value = {'status': 'success', 'segment_count': 2}
            # Simulate processing delay
            mock_process.side_effect = lambda x: time.sleep(0.1) or {'status': 'success', 'segment_count': 2}
            
            mock_config.max_workers = 1
            results_sequential = ingestion.process_directory(temp_dir, pattern="parallel_test_*.vtt")
        sequential_time = time.time() - start_time
        
        # Test with multiple workers
        start_time = time.time()
        with patch.object(ingestion, 'process_vtt_file') as mock_process:
            mock_process.side_effect = lambda x: time.sleep(0.1) or {'status': 'success', 'segment_count': 2}
            
            mock_config.max_workers = 3
            results_parallel = ingestion.process_directory(temp_dir, pattern="parallel_test_*.vtt")
        parallel_time = time.time() - start_time
        
        # Parallel processing should be faster
        assert parallel_time < sequential_time
        assert results_sequential['processed'] == results_parallel['processed']
        assert results_sequential['processed'] == 10
    
    def test_interruption_and_resume(self, temp_dir, mixed_file_directory, mock_config):
        """Test processing interruption and checkpoint-based resume."""
        checkpoint_dir = temp_dir / "checkpoints"
        checkpoint_dir.mkdir()
        mock_config.checkpoint_dir = str(checkpoint_dir)
        
        # Create checkpoint manager
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=str(checkpoint_dir),
            extraction_mode='vtt'
        )
        
        ingestion = TranscriptIngestion(mock_config)
        vtt_files = ingestion.scan_directory(temp_dir, pattern="*.vtt")
        
        # Simulate processing first 2 files successfully
        processed_files = []
        for i, vtt_file in enumerate(vtt_files[:2]):
            # Mark as processed in checkpoint
            checkpoint.mark_vtt_processed(
                str(vtt_file.path), 
                vtt_file.file_hash, 
                segments_processed=5
            )
            processed_files.append(vtt_file.file_hash)
        
        # Verify checkpoint state
        assert len(checkpoint.get_processed_vtt_files()) == 2
        
        # Simulate resume - check which files are already processed
        remaining_files = []
        for vtt_file in vtt_files:
            if not checkpoint.is_vtt_processed(str(vtt_file.path), vtt_file.file_hash):
                remaining_files.append(vtt_file)
        
        # Should have remaining files to process
        assert len(remaining_files) == len(vtt_files) - 2
        
        # Verify specific files are marked as processed
        for vtt_file in vtt_files[:2]:
            assert checkpoint.is_vtt_processed(str(vtt_file.path), vtt_file.file_hash)
    
    def test_memory_usage_monitoring(self, temp_dir, mock_config):
        """Test memory usage monitoring during batch processing."""
        # Create several large files to test memory usage
        large_files = []
        for i in range(5):
            large_vtt = temp_dir / f"large_memory_test_{i}.vtt"
            # Create content that would use more memory
            content = "WEBVTT\n\n"
            for j in range(200):  # 200 segments per file
                start = j * 15
                end = (j + 1) * 15
                content += f"00:{start//60:02d}:{start%60:02d}.000 --> 00:{end//60:02d}:{end%60:02d}.000\n"
                content += f"<v Speaker{j%5}>Long segment {j} with extensive content about various topics " \
                          f"including technology, science, research, and innovation. This is designed to " \
                          f"consume more memory during processing and test memory monitoring capabilities.\n\n"
            large_vtt.write_text(content)
            large_files.append(large_vtt)
        
        ingestion = TranscriptIngestion(mock_config)
        
        # Monitor memory usage during processing
        memory_usage = []
        
        def mock_process_with_memory_tracking(vtt_file):
            # Record memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_usage.append(memory_mb)
            
            # Simulate memory-intensive processing
            time.sleep(0.1)
            return {'status': 'success', 'segment_count': 200}
        
        with patch.object(ingestion, 'process_vtt_file', side_effect=mock_process_with_memory_tracking):
            results = ingestion.process_directory(temp_dir, pattern="large_memory_test_*.vtt")
        
        # Verify processing completed
        assert results['processed'] == 5
        assert len(memory_usage) == 5
        
        # Check that memory usage was recorded
        assert all(mem > 0 for mem in memory_usage)
        print(f"Memory usage during processing: {memory_usage} MB")
    
    def test_concurrent_file_access(self, temp_dir, mock_config):
        """Test handling of concurrent access to the same files."""
        # Create test files
        test_files = []
        for i in range(3):
            vtt_file = temp_dir / f"concurrent_test_{i}.vtt"
            vtt_file.write_text(f"""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Concurrent test {i}.
""")
            test_files.append(vtt_file)
        
        ingestion = TranscriptIngestion(mock_config)
        
        results = []
        errors = []
        
        def process_files_concurrently(worker_id):
            try:
                with patch.object(ingestion, 'process_vtt_file') as mock_process:
                    mock_process.return_value = {'status': 'success', 'segment_count': 1}
                    result = ingestion.process_directory(temp_dir, pattern="concurrent_test_*.vtt")
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple workers processing the same directory
        threads = []
        for i in range(3):
            thread = threading.Thread(target=process_files_concurrently, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0  # No errors should occur
        assert len(results) == 3  # All workers should complete
        
        # All workers should find the same files
        for result in results:
            assert result['total_files'] == 3
    
    def test_processing_timeout_handling(self, temp_dir, mock_config):
        """Test timeout handling for long-running processing."""
        # Create test file
        timeout_vtt = temp_dir / "timeout_test.vtt"
        timeout_vtt.write_text("""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>This will timeout during processing.
""")
        
        ingestion = TranscriptIngestion(mock_config)
        mock_config.processing_timeout_seconds = 1  # Short timeout for testing
        
        # Mock a long-running process
        def slow_process(vtt_file):
            time.sleep(2)  # Longer than timeout
            return {'status': 'success', 'segment_count': 1}
        
        with patch.object(ingestion, 'process_vtt_file', side_effect=slow_process):
            start_time = time.time()
            
            # This should timeout and handle gracefully
            try:
                result = ingestion.process_directory(temp_dir, pattern="timeout_test.vtt")
                processing_time = time.time() - start_time
                
                # Should complete quickly due to timeout, not wait full 2 seconds
                assert processing_time < 1.5
                
            except Exception as e:
                # Timeout handling may raise exception - this is acceptable
                assert "timeout" in str(e).lower() or "time" in str(e).lower()
    
    def test_error_recovery_strategies(self, temp_dir, mixed_file_directory, mock_config):
        """Test different error recovery strategies during batch processing."""
        ingestion = TranscriptIngestion(mock_config)
        
        # Create various error scenarios
        error_scenarios = {
            'corrupted_vtt': {'status': 'error', 'error': 'VTT parsing failed'},
            'llm_error': {'status': 'error', 'error': 'LLM processing failed'},
            'memory_error': {'status': 'error', 'error': 'Out of memory'},
            'network_error': {'status': 'error', 'error': 'Network timeout'}
        }
        
        def mock_process_with_errors(vtt_file):
            filename = vtt_file.path.name
            if 'corrupted' in filename:
                return error_scenarios['corrupted_vtt']
            elif 'large' in filename:
                return error_scenarios['memory_error']
            else:
                return {'status': 'success', 'segment_count': 10}
        
        with patch.object(ingestion, 'process_vtt_file', side_effect=mock_process_with_errors):
            results = ingestion.process_directory(temp_dir, pattern="*.vtt")
        
        # Verify error handling
        assert results['errors'] > 0
        assert results['processed'] > 0  # Some files should still process successfully
        
        # Check that processing continued despite errors
        assert results['total_files'] == results['processed'] + results['errors'] + results['skipped']
    
    def test_batch_size_optimization(self, temp_dir, mock_config):
        """Test processing with different batch sizes."""
        # Create many small files
        num_files = 20
        for i in range(num_files):
            vtt_file = temp_dir / f"batch_test_{i:02d}.vtt"
            vtt_file.write_text(f"""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Batch test file {i}.
""")
        
        ingestion = TranscriptIngestion(mock_config)
        
        # Test different batch sizes
        batch_sizes = [1, 5, 10, 20]
        results_by_batch_size = {}
        
        for batch_size in batch_sizes:
            mock_config.batch_size = batch_size
            
            start_time = time.time()
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.return_value = {'status': 'success', 'segment_count': 1}
                result = ingestion.process_directory(temp_dir, pattern="batch_test_*.vtt")
            processing_time = time.time() - start_time
            
            results_by_batch_size[batch_size] = {
                'time': processing_time,
                'processed': result['processed']
            }
        
        # All batch sizes should process the same number of files
        for batch_size, result in results_by_batch_size.items():
            assert result['processed'] == num_files
        
        print(f"Batch processing times: {results_by_batch_size}")
    
    def test_file_change_detection(self, temp_dir, mock_config):
        """Test detection of file changes between processing runs."""
        # Create initial file
        test_vtt = temp_dir / "change_detection.vtt"
        initial_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Initial content.
"""
        test_vtt.write_text(initial_content)
        
        ingestion = TranscriptIngestion(mock_config)
        vtt_file = ingestion._create_vtt_file(test_vtt)
        initial_hash = vtt_file.file_hash
        
        # Modify file content
        modified_content = initial_content + """
00:00:05.000 --> 00:00:10.000
<v Speaker>Added content.
"""
        test_vtt.write_text(modified_content)
        
        # Create new VTTFile object for modified content
        modified_vtt_file = ingestion._create_vtt_file(test_vtt)
        modified_hash = modified_vtt_file.file_hash
        
        # Hashes should be different
        assert initial_hash != modified_hash
        
        # Checkpoint system should detect the change
        checkpoint_dir = temp_dir / "checkpoints"
        checkpoint_dir.mkdir()
        
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=str(checkpoint_dir),
            extraction_mode='vtt'
        )
        
        # Mark initial version as processed
        checkpoint.mark_vtt_processed(str(test_vtt), initial_hash, segments_processed=1)
        
        # Modified version should not be marked as processed
        assert not checkpoint.is_vtt_processed(str(test_vtt), modified_hash)
        assert checkpoint.is_vtt_processed(str(test_vtt), initial_hash)
    
    def test_resource_cleanup(self, temp_dir, mock_config):
        """Test proper cleanup of resources during batch processing."""
        # Create test files
        for i in range(5):
            vtt_file = temp_dir / f"cleanup_test_{i}.vtt"
            vtt_file.write_text(f"""WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Cleanup test {i}.
""")
        
        ingestion = TranscriptIngestion(mock_config)
        
        # Track resource usage
        initial_fd_count = len(os.listdir('/proc/self/fd')) if os.path.exists('/proc/self/fd') else 0
        
        with patch.object(ingestion, 'process_vtt_file') as mock_process:
            mock_process.return_value = {'status': 'success', 'segment_count': 1}
            
            # Process files
            result = ingestion.process_directory(temp_dir, pattern="cleanup_test_*.vtt")
        
        # Check that file descriptors are cleaned up
        final_fd_count = len(os.listdir('/proc/self/fd')) if os.path.exists('/proc/self/fd') else 0
        
        # File descriptor count should not grow significantly
        if initial_fd_count > 0:  # Only check if we can actually measure FDs
            assert final_fd_count <= initial_fd_count + 5  # Allow some growth but not excessive
        
        # Verify processing completed
        assert result['processed'] == 5
        assert result['errors'] == 0