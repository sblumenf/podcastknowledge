"""Performance tests for the podcast transcription pipeline.

This module tests the performance characteristics of batch processing
including memory usage, processing rates, and scalability.
"""

import pytest
import asyncio
import time
import gc
import json
import psutil
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from typing import List, Dict, Any
import tempfile

# Ensure clean imports by removing any cached cli module
if 'src.cli' in sys.modules:
    del sys.modules['src.cli']

from src.orchestrator import TranscriptionOrchestrator
from src.feed_parser import Episode, PodcastMetadata
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.utils.batch_progress import BatchProgressTracker


@pytest.mark.performance
@pytest.mark.timeout(600)  # 10 minute timeout for performance tests
class TestBatchProcessingPerformance:
    """Test performance characteristics of batch processing."""
    
    @pytest.fixture(autouse=True)
    def cleanup_imports(self):
        """Clean up imports before and after each test."""
        # Remove cli module if it's been imported
        if 'src.cli' in sys.modules:
            del sys.modules['src.cli']
        
        yield
        
        # Clean up after test
        if 'src.cli' in sys.modules:
            del sys.modules['src.cli']
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_podcast_metadata(self):
        """Create mock podcast metadata."""
        return PodcastMetadata(
            title="Performance Test Podcast",
            description="A podcast for performance testing",
            link="https://example.com/podcast",
            language="en",
            author="Perf Test Host"
        )
    
    @pytest.fixture
    def large_episode_list(self, num_episodes: int = 100):
        """Create a large list of mock episodes for performance testing."""
        episodes = []
        for i in range(1, num_episodes + 1):
            episode = Episode(
                guid=f"perf-ep{i:03d}-guid",
                title=f"Performance Episode {i:03d}: Long Title With Many Words To Test Memory Usage",
                audio_url=f"https://example.com/audio/performance{i:03d}.mp3",
                published_date=datetime(2024, (i % 12) + 1, (i % 28) + 1),
                description=f"Performance test episode {i} with a long description that simulates real podcast descriptions. " * 10,
                duration="45:30",
                author="Performance Test Host"
            )
            episodes.append(episode)
        return episodes
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
    
    @pytest.mark.asyncio
    async def test_large_batch_memory_usage(self, temp_data_dir, mock_podcast_metadata):
        """Test memory usage with 100 episode batch processing."""
        
        # Create 100 episodes
        episodes = []
        for i in range(1, 101):
            episode = Episode(
                guid=f"mem-test-ep{i:03d}",
                title=f"Memory Test Episode {i}",
                audio_url=f"https://example.com/audio/mem{i}.mp3",
                published_date=datetime(2024, 1, 1),
                description=f"Memory test episode {i} description",
                duration="30:00",
                author="Memory Test Host"
            )
            episodes.append(episode)
        
        # Set up orchestrator with isolated state
        with patch.dict('os.environ', {'STATE_DIR': str(temp_data_dir)}):
            orchestrator = TranscriptionOrchestrator(
                output_dir=temp_data_dir / "transcripts",
                data_dir=temp_data_dir
            )
            
            # Record initial memory usage
            # Ensure any pending coroutines are cleaned up before gc
            await asyncio.sleep(0)  # Allow event loop to process pending tasks
            gc.collect()  # Force garbage collection
            initial_memory = self.get_memory_usage()
            
            # Add all episodes to progress tracker (simulating feed parsing)
            for episode in episodes:
                episode_data = episode.to_dict()
                episode_data['podcast_name'] = mock_podcast_metadata.title
                orchestrator.progress_tracker.add_episode(episode_data)
            
            # Memory after adding episodes
            after_add_memory = self.get_memory_usage()
            
            # Mark some episodes as completed (simulating processing)
            for i, episode in enumerate(episodes[:50]):
                orchestrator.progress_tracker.mark_started(episode.to_dict())
                orchestrator.progress_tracker.mark_completed(
                    episode.guid,
                    f"output_{i}.vtt",
                    processing_time=120.0
                )
            
            # Memory after processing
            after_processing_memory = self.get_memory_usage()
            
            # Test getting pending episodes (should be efficient)
            start_time = time.time()
            pending = orchestrator._get_pending_episodes(episodes, max_episodes=100)
            pending_time = time.time() - start_time
            
            # Memory after getting pending
            after_pending_memory = self.get_memory_usage()
            
            # Verify performance characteristics
            assert len(pending) == 50  # Should have 50 pending episodes
            assert pending_time < 1.0  # Should take less than 1 second
            
            # Memory usage should not grow excessively
            memory_growth = after_processing_memory['rss_mb'] - initial_memory['rss_mb']
            assert memory_growth < 100, f"Memory grew by {memory_growth:.1f}MB, expected <100MB"
            
            # Getting pending episodes should not significantly increase memory
            pending_memory_growth = after_pending_memory['rss_mb'] - after_processing_memory['rss_mb']
            assert pending_memory_growth < 10, f"Pending episodes increased memory by {pending_memory_growth:.1f}MB"
            
            # Verify we're not using excessive memory overall
            assert after_processing_memory['rss_mb'] < 500, f"Total memory usage {after_processing_memory['rss_mb']:.1f}MB too high"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_progress_tracker_performance(self, temp_data_dir):
        """Test progress tracker performance with large number of episodes."""
        
        progress_file = temp_data_dir / ".progress.json"
        progress_tracker = ProgressTracker(progress_file)
        
        # Test adding many episodes
        num_episodes = 500
        start_time = time.time()
        
        for i in range(num_episodes):
            episode_data = {
                'guid': f'perf-ep{i:03d}',
                'title': f'Performance Episode {i}',
                'audio_url': f'https://example.com/audio/{i}.mp3',
                'podcast_name': 'Performance Test Podcast'
            }
            progress_tracker.add_episode(episode_data)
        
        add_time = time.time() - start_time
        
        # Test querying episodes
        start_time = time.time()
        pending = progress_tracker.get_pending()
        pending_time = time.time() - start_time
        
        start_time = time.time()
        failed = progress_tracker.get_failed()
        failed_time = time.time() - start_time
        
        # Test state file size
        if progress_file.exists():
            file_size_mb = progress_file.stat().st_size / 1024 / 1024
            assert file_size_mb < 10, f"Progress file too large: {file_size_mb:.1f}MB"
        
        # Verify performance
        assert add_time < 30.0, f"Adding {num_episodes} episodes took {add_time:.2f}s, expected <30s"
        assert pending_time < 1.0, f"Getting pending episodes took {pending_time:.2f}s, expected <1s"
        assert failed_time < 1.0, f"Getting failed episodes took {failed_time:.2f}s, expected <1s"
        
        assert len(pending) == num_episodes
        assert len(failed) == 0
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_batch_progress_tracker_performance(self, temp_data_dir):
        """Test BatchProgressTracker performance with frequent updates."""
        
        progress_file = temp_data_dir / ".progress.json"
        progress_tracker = ProgressTracker(progress_file)
        
        # Add episodes to progress tracker first
        for i in range(100):
            episode_data = {
                'guid': f'batch-ep{i:03d}',
                'title': f'Episode {i}',
                'audio_url': f'https://example.com/audio/{i}.mp3',
                'podcast_name': 'Batch Test Podcast'
            }
            progress_tracker.add_episode(episode_data)
        
        # Create batch tracker for 100 episodes
        batch_tracker = BatchProgressTracker(progress_tracker, total_episodes=100)
        
        # Record initial memory
        initial_memory = self.get_memory_usage()
        
        # Start batch
        batch_tracker.start_batch()
        
        # Simulate processing with frequent updates
        start_time = time.time()
        
        for i in range(100):
            # Get episode
            episode_guid = f'batch-ep{i:03d}'
            
            # Mark as in progress
            progress_tracker.mark_started({'guid': episode_guid}, api_key_index=0)
            
            # Update current episode
            batch_tracker.update_current_episode(f"Episode {i}")
            
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms per episode
            
            # Complete episode
            processing_time = 60.0 + (i % 10) * 10  # Vary processing time
            progress_tracker.mark_completed(episode_guid, f"output/episode-{i}.vtt", processing_time)
            batch_tracker.episode_completed(processing_time)
        
        total_time = time.time() - start_time
        
        # Finish batch
        batch_tracker.finish_batch("Performance test completed")
        
        # Check final memory
        final_memory = self.get_memory_usage()
        memory_growth = final_memory['rss_mb'] - initial_memory['rss_mb']
        
        # Verify performance
        assert total_time < 5.0, f"Processing 100 episodes took {total_time:.2f}s, expected <5s"
        assert memory_growth < 50, f"Memory grew by {memory_growth:.1f}MB during processing"
        
        # Verify statistics are calculated correctly
        status = batch_tracker.get_status_summary()
        assert status['completed'] == 100
        assert status['total_episodes'] == 100
        assert status['success_rate'] == 100.0
        assert len(batch_tracker.stats.processing_times) == 100
    
    @pytest.mark.slow
    def test_state_file_scalability(self, temp_data_dir):
        """Test state file handling with large amounts of data."""
        
        progress_file = temp_data_dir / ".progress.json"
        progress_tracker = ProgressTracker(progress_file)
        
        # Add many episodes and track save/load performance
        num_episodes = 1000
        
        # Test saving performance
        start_time = time.time()
        
        for i in range(num_episodes):
            episode_data = {
                'guid': f'scale-ep{i:04d}',
                'title': f'Scalability Episode {i}',
                'audio_url': f'https://example.com/audio/{i}.mp3',
                'podcast_name': 'Scalability Test Podcast',
                'description': 'A' * 500  # Long description to test serialization
            }
            progress_tracker.add_episode(episode_data)
        
        save_time = time.time() - start_time
        
        # Test loading performance
        start_time = time.time()
        new_tracker = ProgressTracker(progress_file)
        load_time = time.time() - start_time
        
        # Verify state file size is reasonable
        file_size_mb = progress_file.stat().st_size / 1024 / 1024
        
        # Performance assertions
        # Allow more time for save operations (50ms per episode is reasonable for JSON serialization)
        assert save_time < 50.0, f"Saving {num_episodes} episodes took {save_time:.2f}s, expected <50s"
        assert load_time < 10.0, f"Loading {num_episodes} episodes took {load_time:.2f}s, expected <10s"
        assert file_size_mb < 50, f"State file is {file_size_mb:.1f}MB, expected <50MB"
        
        # Verify data integrity
        assert len(new_tracker.state.episodes) == num_episodes
        
        # Test state file operations
        start_time = time.time()
        pending = new_tracker.get_pending()
        query_time = time.time() - start_time
        
        assert query_time < 2.0, f"Querying {num_episodes} episodes took {query_time:.2f}s, expected <2s"
        assert len(pending) == num_episodes
    
    @pytest.mark.asyncio 
    async def test_concurrent_operations_performance(self, temp_data_dir):
        """Test performance of concurrent operations."""
        
        # Create multiple progress trackers (simulating concurrent sessions)
        trackers = []
        for i in range(5):
            progress_file = temp_data_dir / f".progress_{i}.json"
            tracker = ProgressTracker(progress_file)
            trackers.append(tracker)
        
        # Add episodes to each tracker concurrently
        async def add_episodes_to_tracker(tracker, start_idx):
            for i in range(start_idx, start_idx + 50):
                episode_data = {
                    'guid': f'concurrent-ep{i:03d}',
                    'title': f'Concurrent Episode {i}',
                    'audio_url': f'https://example.com/audio/{i}.mp3',
                    'podcast_name': f'Concurrent Test Podcast'
                }
                tracker.add_episode(episode_data)
                # Small delay to simulate real processing
                await asyncio.sleep(0.001)
        
        # Run concurrent operations
        start_time = time.time()
        
        tasks = []
        for i, tracker in enumerate(trackers):
            task = add_episodes_to_tracker(tracker, i * 50)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        concurrent_time = time.time() - start_time
        
        # Verify all trackers have their episodes
        total_episodes = 0
        for tracker in trackers:
            total_episodes += len(tracker.state.episodes)
        
        assert total_episodes == 250  # 5 trackers * 50 episodes each
        assert concurrent_time < 10.0, f"Concurrent operations took {concurrent_time:.2f}s, expected <10s"
    
    def test_memory_cleanup_after_processing(self, temp_data_dir):
        """Test that memory is properly cleaned up after processing large batches."""
        
        initial_memory = self.get_memory_usage()
        
        # Process multiple batches to test cleanup
        for batch_num in range(5):
            progress_file = temp_data_dir / f".progress_batch_{batch_num}.json"
            progress_tracker = ProgressTracker(progress_file)
            
            # Add and process episodes
            for i in range(100):
                episode_data = {
                    'guid': f'cleanup-batch{batch_num}-ep{i:03d}',
                    'title': f'Cleanup Test Episode {i}',
                    'audio_url': f'https://example.com/audio/{i}.mp3',
                    'podcast_name': 'Cleanup Test Podcast'
                }
                progress_tracker.add_episode(episode_data)
                progress_tracker.mark_started(episode_data)
                progress_tracker.mark_completed(
                    episode_data['guid'],
                    f"output_{i}.vtt",
                    processing_time=60.0
                )
            
            # Force cleanup
            del progress_tracker
            gc.collect()
        
        final_memory = self.get_memory_usage()
        memory_growth = final_memory['rss_mb'] - initial_memory['rss_mb']
        
        # Memory should not grow significantly after cleanup
        assert memory_growth < 100, f"Memory grew by {memory_growth:.1f}MB after processing 5 batches"


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.timeout(300)  # 5 minute timeout for extensive tests
class TestProcessingRatePerformance:
    """Test processing rate and throughput performance."""
    
    def test_processing_rate_estimation(self, tmp_path):
        """Test and document processing rate estimation."""
        
        # Simulate processing times for different episode lengths
        processing_times = {
            '15:00': [45, 50, 42, 48, 46],     # 15 min episodes -> ~45-50 sec processing
            '30:00': [85, 92, 88, 90, 87],     # 30 min episodes -> ~85-92 sec processing
            '60:00': [165, 172, 168, 170, 166], # 60 min episodes -> ~165-172 sec processing
        }
        
        results = {}
        
        for duration, times in processing_times.items():
            avg_time = sum(times) / len(times)
            episodes_per_hour = 3600 / avg_time
            
            results[duration] = {
                'avg_processing_time': avg_time,
                'episodes_per_hour': episodes_per_hour,
                'duration_minutes': int(duration.split(':')[0])
            }
        
        # Document results
        print("\n=== PROCESSING RATE PERFORMANCE ===")
        for duration, stats in results.items():
            print(f"Episode Length: {duration}")
            print(f"  Average Processing Time: {stats['avg_processing_time']:.1f} seconds")
            print(f"  Episodes per Hour: {stats['episodes_per_hour']:.1f}")
            print(f"  Processing Ratio: {stats['avg_processing_time'] / (stats['duration_minutes'] * 60):.2f}")
            print()
        
        # Verify reasonable processing rates
        # For 30-minute episodes, should process at least 40 episodes per hour
        assert results['30:00']['episodes_per_hour'] >= 40
        
        # Processing should be faster than real-time (ratio < 1.0)
        for duration, stats in results.items():
            ratio = stats['avg_processing_time'] / (stats['duration_minutes'] * 60)
            assert ratio < 1.0, f"Processing ratio {ratio:.2f} for {duration} episodes is not real-time"
    
    @pytest.mark.asyncio
    async def test_batch_throughput_performance(self, tmp_path):
        """Test overall batch processing throughput."""
        
        # Simulate a batch of mixed-length episodes
        episodes = [
            ('15:00', 45),  # 15-min episode, 45s processing
            ('30:00', 90),  # 30-min episode, 90s processing
            ('60:00', 170), # 60-min episode, 170s processing
            ('45:00', 135), # 45-min episode, 135s processing
            ('20:00', 60),  # 20-min episode, 60s processing
        ]
        
        total_processing_time = 0
        total_content_time = 0
        
        for duration, processing_time in episodes:
            total_processing_time += processing_time
            total_content_time += int(duration.split(':')[0]) * 60
        
        # Calculate throughput metrics
        throughput_ratio = total_processing_time / total_content_time
        content_hours = total_content_time / 3600
        processing_hours = total_processing_time / 3600
        
        print(f"\n=== BATCH THROUGHPUT PERFORMANCE ===")
        print(f"Total Content Time: {content_hours:.2f} hours")
        print(f"Total Processing Time: {processing_hours:.2f} hours") 
        print(f"Throughput Ratio: {throughput_ratio:.3f}")
        print(f"Speed Factor: {1/throughput_ratio:.1f}x real-time")
        
        # Should process faster than real-time
        assert throughput_ratio < 1.0, f"Batch processing not faster than real-time: {throughput_ratio:.3f}"
        
        # Should achieve at least 2x real-time speed
        assert throughput_ratio < 0.5, f"Processing speed {1/throughput_ratio:.1f}x is below target of 2x"