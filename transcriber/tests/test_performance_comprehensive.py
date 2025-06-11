"""Comprehensive performance tests for the podcast transcription pipeline.

This module tests performance characteristics with a focus on memory efficiency,
avoiding large datasets that could cause out-of-memory issues.
"""

import pytest
import asyncio
import time
import gc
import json
import psutil
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from typing import List, Dict, Any
import threading
import resource

from src.orchestrator import TranscriptionOrchestrator
from src.feed_parser import Episode, PodcastMetadata
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.gemini_client import RateLimitedGeminiClient
from src.retry_wrapper import RetryManager
from src.config import Config


@pytest.mark.performance
class TestPerformanceComprehensive:
    """Comprehensive performance tests with memory optimization."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Aggressive cleanup to prevent memory issues."""
        gc.collect()
        yield
        gc.collect()
    
    @pytest.fixture
    def temp_performance_dirs(self, tmp_path):
        """Create temporary directories for performance testing."""
        dirs = {
            'output': tmp_path / 'perf_output',
            'checkpoints': tmp_path / 'perf_checkpoints',
            'state': tmp_path / 'perf_state'
        }
        for dir_path in dirs.values():
            dir_path.mkdir(exist_ok=True)
        yield dirs
        # Aggressive cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    @pytest.fixture
    def performance_config(self, temp_performance_dirs):
        """Create performance test configuration."""
        config = Mock(spec=Config)
        config.output_directory = str(temp_performance_dirs['output'])
        config.checkpoint_dir = str(temp_performance_dirs['checkpoints'])
        config.state_dir = str(temp_performance_dirs['state'])
        config.gemini_api_keys = ['test_key1', 'test_key2']  # Multiple keys for rate limit testing
        config.concurrent_processing_limit = 2  # Limited for memory
        config.batch_size = 5  # Small batch
        config.vtt_generation = {'enabled': True}
        config.speaker_identification = {'enabled': False}  # Disable to save memory
        config.metadata_index = {'enabled': False}  # Disable to save memory
        config.file_organization = {'enabled': True}
        return config
    
    def test_small_feed_processing_performance(self, temp_performance_dirs, performance_config):
        """Test performance with small episode feeds (memory-limited)."""
        # Create a small feed with 5 episodes
        feed_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Performance Test Podcast</title>
                <description>Testing performance metrics</description>"""
        
        for i in range(1, 6):  # Only 5 episodes to avoid memory issues
            feed_content += f"""
                <item>
                    <title>Episode {i}</title>
                    <guid>perf-ep{i}</guid>
                    <enclosure url="https://example.com/ep{i}.mp3" type="audio/mpeg"/>
                    <pubDate>Mon, {i:02d} Jan 2024 00:00:00 GMT</pubDate>
                </item>"""
        
        feed_content += """
            </channel>
        </rss>"""
        
        # Mock transcription response
        mock_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker>Performance test transcription."""
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                feed_content.encode('utf-8')
            
            # Mock Gemini with controlled response time
            def generate_content_with_delay(*args, **kwargs):
                time.sleep(0.1)  # Simulate API delay
                response = MagicMock()
                response.text = mock_vtt
                return response
            
            mock_model = MagicMock()
            mock_model.generate_content = generate_content_with_delay
            mock_model_class.return_value = mock_model
            
            # Measure performance
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(performance_config.output.default_dir),
                config=performance_config
            )
            asyncio.run(orchestrator.process_feed("https://example.com/feed.xml"))
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            # Performance assertions
            processing_time = end_time - start_time
            memory_used = end_memory - start_memory
            episodes_per_second = 5 / processing_time
            
            # Log performance metrics
            print(f"\nPerformance Metrics:")
            print(f"  Total time: {processing_time:.2f}s")
            print(f"  Episodes/second: {episodes_per_second:.2f}")
            print(f"  Memory used: {memory_used:.2f}MB")
            
            # Basic performance requirements
            assert processing_time < 10, "Processing took too long"
            assert memory_used < 100, "Used too much memory"
            assert episodes_per_second > 0.5, "Processing too slow"
    
    def test_memory_usage_under_controlled_load(self, temp_performance_dirs, performance_config):
        """Test memory usage patterns under controlled load."""
        memory_samples = []
        
        def monitor_memory():
            """Monitor memory usage during processing."""
            process = psutil.Process()
            while getattr(monitor_memory, 'running', True):
                memory_mb = process.memory_info().rss / 1024 / 1024
                memory_samples.append(memory_mb)
                time.sleep(0.1)
        
        # Start memory monitoring
        monitor_memory.running = True
        monitor_thread = threading.Thread(target=monitor_memory)
        monitor_thread.start()
        
        try:
            # Create controlled load - process 3 small feeds sequentially
            for i in range(3):
                feed_content = f"""<?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0">
                    <channel>
                        <title>Memory Test Feed {i}</title>
                        <item>
                            <title>Episode {i}</title>
                            <guid>mem-test-{i}</guid>
                            <enclosure url="https://example.com/mem{i}.mp3" type="audio/mpeg"/>
                        </item>
                    </channel>
                </rss>"""
                
                with patch('urllib.request.urlopen') as mock_urlopen, \
                     patch('google.generativeai.GenerativeModel') as mock_model_class:
                    
                    mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                        feed_content.encode('utf-8')
                    
                    mock_model = MagicMock()
                    mock_model.generate_content.return_value.text = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest"
                    mock_model_class.return_value = mock_model
                    
                    orchestrator = TranscriptionOrchestrator(
                output_dir=Path(performance_config.output.default_dir),
                config=performance_config
            )
                    asyncio.run(orchestrator.process_feed(f"https://example.com/feed{i}.xml"))
                    
                    # Force cleanup between iterations
                    del orchestrator
                    gc.collect()
                    time.sleep(0.5)
        
        finally:
            # Stop monitoring
            monitor_memory.running = False
            monitor_thread.join()
        
        # Analyze memory usage
        if memory_samples:
            avg_memory = sum(memory_samples) / len(memory_samples)
            max_memory = max(memory_samples)
            min_memory = min(memory_samples)
            memory_variance = max_memory - min_memory
            
            print(f"\nMemory Usage Analysis:")
            print(f"  Average: {avg_memory:.2f}MB")
            print(f"  Maximum: {max_memory:.2f}MB")
            print(f"  Minimum: {min_memory:.2f}MB")
            print(f"  Variance: {memory_variance:.2f}MB")
            
            # Memory should stay relatively stable
            assert memory_variance < 50, f"Memory variance too high: {memory_variance}MB"
            assert max_memory < 500, f"Peak memory too high: {max_memory}MB"
    
    def test_api_rate_limit_handling_performance(self, temp_performance_dirs, performance_config):
        """Test performance of API rate limit handling."""
        # Track API call timing
        api_call_times = []
        
        def mock_generate_content(*args, **kwargs):
            api_call_times.append(time.time())
            
            # Simulate rate limit on 3rd call
            if len(api_call_times) == 3:
                raise Exception("Resource exhausted: Quota exceeded")
            
            response = MagicMock()
            response.text = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nRate limit test"
            return response
        
        # Create feed with 5 episodes
        feed_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Rate Limit Test</title>"""
        
        for i in range(1, 6):
            feed_content += f"""
                <item>
                    <title>Episode {i}</title>
                    <guid>rate-limit-ep{i}</guid>
                    <enclosure url="https://example.com/rl{i}.mp3" type="audio/mpeg"/>
                </item>"""
        
        feed_content += """
            </channel>
        </rss>"""
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class, \
             patch('src.retry_wrapper.RetryManager') as mock_retry_manager:
            
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                feed_content.encode('utf-8')
            
            mock_model = MagicMock()
            mock_model.generate_content = mock_generate_content
            mock_model_class.return_value = mock_model
            
            # Setup retry manager to handle rate limits
            retry_instance = Mock()
            mock_retry_manager.return_value = retry_instance
            
            start_time = time.time()
            
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(performance_config.output.default_dir),
                config=performance_config
            )
            asyncio.run(orchestrator.process_feed("https://example.com/feed.xml"))
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Analyze rate limit handling
            if len(api_call_times) > 1:
                # Calculate time between API calls
                call_intervals = [api_call_times[i] - api_call_times[i-1] 
                                for i in range(1, len(api_call_times))]
                avg_interval = sum(call_intervals) / len(call_intervals) if call_intervals else 0
                
                print(f"\nRate Limit Performance:")
                print(f"  Total API calls: {len(api_call_times)}")
                print(f"  Average interval: {avg_interval:.2f}s")
                print(f"  Total processing time: {total_time:.2f}s")
    
    def test_concurrent_processing_limits(self, temp_performance_dirs, performance_config):
        """Test concurrent processing performance and limits."""
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()
        
        def track_concurrency():
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
        
        def release_concurrency():
            nonlocal concurrent_count
            with lock:
                concurrent_count -= 1
        
        # Create multiple small feeds
        feeds = []
        for i in range(4):  # Test with 4 feeds
            feed = f"""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <title>Concurrent Test {i}</title>
                    <item>
                        <title>Episode {i}</title>
                        <guid>concurrent-ep{i}</guid>
                        <enclosure url="https://example.com/c{i}.mp3" type="audio/mpeg"/>
                    </item>
                </channel>
            </rss>"""
            feeds.append(feed)
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            def urlopen_side_effect(url):
                feed_index = int(url[-5])  # Extract index from URL
                mock_response = MagicMock()
                mock_response.read.return_value = feeds[feed_index].encode('utf-8')
                mock_response.__enter__ = lambda self: mock_response
                mock_response.__exit__ = lambda self, *args: None
                return mock_response
            
            mock_urlopen.side_effect = urlopen_side_effect
            
            # Mock Gemini with concurrency tracking
            def generate_with_tracking(*args, **kwargs):
                track_concurrency()
                time.sleep(0.2)  # Simulate processing
                release_concurrency()
                response = MagicMock()
                response.text = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nConcurrent test"
                return response
            
            mock_model = MagicMock()
            mock_model.generate_content = generate_with_tracking
            mock_model_class.return_value = mock_model
            
            # Process feeds concurrently
            async def process_all_feeds():
                orchestrator = TranscriptionOrchestrator(
                output_dir=Path(performance_config.output.default_dir),
                config=performance_config
            )
                tasks = [
                    orchestrator.process_feed(f"https://example.com/feed{i}.xml")
                    for i in range(4)
                ]
                await asyncio.gather(*tasks)
            
            start_time = time.time()
            asyncio.run(process_all_feeds())
            end_time = time.time()
            
            total_time = end_time - start_time
            
            print(f"\nConcurrency Performance:")
            print(f"  Max concurrent: {max_concurrent}")
            print(f"  Configured limit: {performance_config.concurrent_processing_limit}")
            print(f"  Total time: {total_time:.2f}s")
            
            # Verify concurrency was limited
            assert max_concurrent <= performance_config.concurrent_processing_limit, \
                f"Exceeded concurrency limit: {max_concurrent} > {performance_config.concurrent_processing_limit}"
    
    def test_performance_benchmarks(self, temp_performance_dirs, performance_config):
        """Create and verify performance benchmarks."""
        benchmarks = {
            'single_episode_time': None,
            'memory_per_episode': None,
            'api_calls_per_episode': None,
            'disk_io_per_episode': None
        }
        
        # Single episode benchmark
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            feed_content = """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <title>Benchmark Test</title>
                    <item>
                        <title>Benchmark Episode</title>
                        <guid>benchmark-ep1</guid>
                        <enclosure url="https://example.com/benchmark.mp3" type="audio/mpeg"/>
                    </item>
                </channel>
            </rss>"""
            
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                feed_content.encode('utf-8')
            
            api_call_count = 0
            def count_api_calls(*args, **kwargs):
                nonlocal api_call_count
                api_call_count += 1
                response = MagicMock()
                response.text = "WEBVTT\n\n00:00:00.000 --> 00:00:10.000\nBenchmark content"
                return response
            
            mock_model = MagicMock()
            mock_model.generate_content = count_api_calls
            mock_model_class.return_value = mock_model
            
            # Measure single episode performance
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            orchestrator = TranscriptionOrchestrator(
                output_dir=Path(performance_config.output.default_dir),
                config=performance_config
            )
            asyncio.run(orchestrator.process_feed("https://example.com/benchmark.xml"))
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Calculate benchmarks
            benchmarks['single_episode_time'] = end_time - start_time
            benchmarks['memory_per_episode'] = end_memory - start_memory
            benchmarks['api_calls_per_episode'] = api_call_count
            
            # Count output files for disk I/O benchmark
            output_files = list(Path(temp_performance_dirs['output']).rglob('*'))
            benchmarks['disk_io_per_episode'] = len(output_files)
            
            # Save benchmarks
            benchmark_file = temp_performance_dirs['output'] / 'performance_benchmarks.json'
            with open(benchmark_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'benchmarks': benchmarks,
                    'config': {
                        'concurrent_limit': performance_config.concurrent_processing_limit,
                        'batch_size': performance_config.batch_size
                    }
                }, f, indent=2)
            
            print(f"\nPerformance Benchmarks:")
            print(f"  Single episode time: {benchmarks['single_episode_time']:.2f}s")
            print(f"  Memory per episode: {benchmarks['memory_per_episode']:.2f}MB")
            print(f"  API calls per episode: {benchmarks['api_calls_per_episode']}")
            print(f"  Files created per episode: {benchmarks['disk_io_per_episode']}")
            
            # Verify benchmarks are reasonable
            assert benchmarks['single_episode_time'] < 5, "Single episode too slow"
            assert benchmarks['memory_per_episode'] < 50, "Too much memory per episode"
            assert benchmarks['api_calls_per_episode'] >= 1, "No API calls made"
            assert benchmarks['disk_io_per_episode'] >= 1, "No output files created"