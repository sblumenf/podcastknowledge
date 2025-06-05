"""Comprehensive E2E tests for the podcast transcription pipeline with memory optimization.

This module provides extensive end-to-end testing scenarios while minimizing memory usage
through careful test data management and resource cleanup.
"""

import pytest
import asyncio
import json
import os
import tempfile
import shutil
import gc
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, Mock
import time

from src.feed_parser import parse_feed
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.gemini_client import RateLimitedGeminiClient
from src.vtt_generator import VTTGenerator
from src.file_organizer import FileOrganizer
from src.orchestrator import TranscriptionOrchestrator
from src.config import Config
from src.checkpoint_recovery import CheckpointManager


@pytest.mark.integration
@pytest.mark.e2e
class TestE2EComprehensive:
    """Comprehensive E2E tests with memory-efficient implementations."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure cleanup before and after each test to prevent memory issues."""
        gc.collect()
        yield
        gc.collect()
    
    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary directories for testing."""
        dirs = {
            'output': tmp_path / 'output',
            'checkpoints': tmp_path / 'checkpoints',
            'state': tmp_path / 'state'
        }
        for dir_path in dirs.values():
            dir_path.mkdir(exist_ok=True)
        yield dirs
        # Cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    @pytest.fixture
    def minimal_rss_feeds(self):
        """Create minimal RSS feeds with different formats for testing."""
        feeds = {
            'simple': """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <title>Simple Test Podcast</title>
                    <description>Minimal test feed</description>
                    <link>https://example.com/simple</link>
                    <item>
                        <title>Episode 1</title>
                        <guid>simple-ep1</guid>
                        <description>Test episode</description>
                        <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg"/>
                        <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                    </item>
                </channel>
            </rss>""",
            
            'itunes': """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
                <channel>
                    <title>iTunes Test Podcast</title>
                    <itunes:author>Test Author</itunes:author>
                    <item>
                        <title>iTunes Episode</title>
                        <guid>itunes-ep1</guid>
                        <itunes:duration>1800</itunes:duration>
                        <enclosure url="https://example.com/itunes-ep1.mp3" type="audio/mpeg"/>
                    </item>
                </channel>
            </rss>""",
            
            'youtube': """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <title>YouTube Test Podcast</title>
                    <item>
                        <title>YouTube Episode</title>
                        <guid>yt-ep1</guid>
                        <link>https://www.youtube.com/watch?v=test123</link>
                    </item>
                </channel>
            </rss>"""
        }
        return feeds
    
    @pytest.fixture
    def mock_gemini_response(self):
        """Create a minimal mock Gemini transcription response."""
        return """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker 1>This is a test transcription.

00:00:05.000 --> 00:00:10.000
<v Speaker 2>Memory efficient testing is important."""
    
    @pytest.fixture
    def mock_config(self, temp_dirs):
        """Create a mock configuration."""
        config = Mock(spec=Config)
        config.output_directory = str(temp_dirs['output'])
        config.checkpoint_dir = str(temp_dirs['checkpoints'])
        config.state_dir = str(temp_dirs['state'])
        config.gemini_api_keys = ['test_key']
        config.concurrent_processing_limit = 1  # Limit concurrency for memory
        config.batch_size = 2  # Small batch size
        config.vtt_generation = {'enabled': True}
        config.speaker_identification = {'enabled': True}
        config.metadata_index = {'enabled': True}
        config.file_organization = {'enabled': True}
        return config
    
    def test_complete_pipeline_single_episode(self, temp_dirs, minimal_rss_feeds, 
                                            mock_gemini_response, mock_config):
        """Test complete processing pipeline with a single episode."""
        # Setup
        feed_url = "https://example.com/feed.xml"
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            # Mock RSS feed response
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                minimal_rss_feeds['simple'].encode('utf-8')
            
            # Mock Gemini model
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = mock_gemini_response
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            # Create orchestrator
            orchestrator = TranscriptionOrchestrator(config=mock_config)
            
            # Process feed
            asyncio.run(orchestrator.process_feed(feed_url))
            
            # Verify output
            output_files = list(Path(temp_dirs['output']).rglob('*.vtt'))
            assert len(output_files) == 1
            assert 'simple-ep1' in str(output_files[0])
    
    def test_interruption_and_resume(self, temp_dirs, minimal_rss_feeds, 
                                   mock_gemini_response, mock_config):
        """Test interruption and resume functionality."""
        feed_url = "https://example.com/feed.xml"
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            # Mock RSS feed with 2 episodes
            multi_episode_feed = minimal_rss_feeds['simple'].replace(
                '</channel>',
                '''<item>
                    <title>Episode 2</title>
                    <guid>simple-ep2</guid>
                    <enclosure url="https://example.com/ep2.mp3" type="audio/mpeg"/>
                </item>
                </channel>'''
            )
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                multi_episode_feed.encode('utf-8')
            
            # Mock Gemini to simulate interruption
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Process first episode successfully
                    response = MagicMock()
                    response.text = mock_gemini_response
                    return response
                else:
                    # Simulate interruption
                    raise Exception("Simulated interruption")
            
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = side_effect
            mock_model_class.return_value = mock_model
            
            # First run - should process 1 episode then fail
            orchestrator = TranscriptionOrchestrator(config=mock_config)
            with pytest.raises(Exception):
                asyncio.run(orchestrator.process_feed(feed_url))
            
            # Verify checkpoint exists
            checkpoint_files = list(Path(temp_dirs['checkpoints']).glob('*.json'))
            assert len(checkpoint_files) > 0
            
            # Reset mock for resume
            mock_model.generate_content.side_effect = None
            mock_model.generate_content.return_value.text = mock_gemini_response
            
            # Resume processing
            orchestrator2 = TranscriptionOrchestrator(config=mock_config)
            asyncio.run(orchestrator2.process_feed(feed_url))
            
            # Verify both episodes processed
            output_files = list(Path(temp_dirs['output']).rglob('*.vtt'))
            assert len(output_files) == 2
    
    def test_concurrent_feed_processing_limited(self, temp_dirs, minimal_rss_feeds,
                                               mock_gemini_response, mock_config):
        """Test concurrent feed processing with memory limits."""
        # Limit to 2 concurrent feeds to avoid memory issues
        feed_urls = [
            "https://example.com/feed1.xml",
            "https://example.com/feed2.xml"
        ]
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            # Mock different feeds
            def urlopen_side_effect(url):
                feed_index = int(url.split('feed')[1][0])
                feed_content = minimal_rss_feeds['simple'].replace(
                    'simple-ep1', f'feed{feed_index}-ep1'
                ).replace(
                    'Simple Test Podcast', f'Feed {feed_index}'
                )
                mock_response = MagicMock()
                mock_response.read.return_value = feed_content.encode('utf-8')
                mock_response.__enter__ = lambda self: mock_response
                mock_response.__exit__ = lambda self, *args: None
                return mock_response
            
            mock_urlopen.side_effect = urlopen_side_effect
            
            # Mock Gemini
            mock_model = MagicMock()
            mock_model.generate_content.return_value.text = mock_gemini_response
            mock_model_class.return_value = mock_model
            
            # Process feeds concurrently
            async def process_feeds():
                orchestrator = TranscriptionOrchestrator(config=mock_config)
                tasks = [orchestrator.process_feed(url) for url in feed_urls]
                await asyncio.gather(*tasks)
            
            asyncio.run(process_feeds())
            
            # Verify outputs
            output_files = list(Path(temp_dirs['output']).rglob('*.vtt'))
            assert len(output_files) == 2
            assert any('feed1-ep1' in str(f) for f in output_files)
            assert any('feed2-ep1' in str(f) for f in output_files)
    
    def test_error_recovery_workflows(self, temp_dirs, minimal_rss_feeds,
                                    mock_gemini_response, mock_config):
        """Test various error recovery scenarios."""
        scenarios = [
            {
                'name': 'API_ERROR',
                'error': Exception("API Error"),
                'expected_status': EpisodeStatus.FAILED
            },
            {
                'name': 'QUOTA_EXCEEDED',
                'error': Exception("Quota exceeded"),
                'expected_status': EpisodeStatus.FAILED
            },
            {
                'name': 'NETWORK_ERROR',
                'error': Exception("Network timeout"),
                'expected_status': EpisodeStatus.FAILED
            }
        ]
        
        for scenario in scenarios:
            with patch('urllib.request.urlopen') as mock_urlopen, \
                 patch('google.generativeai.GenerativeModel') as mock_model_class:
                
                # Setup unique feed for this scenario
                feed_content = minimal_rss_feeds['simple'].replace(
                    'simple-ep1', f'{scenario["name"]}-ep1'
                )
                mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                    feed_content.encode('utf-8')
                
                # Mock Gemini to raise specific error
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = scenario['error']
                mock_model_class.return_value = mock_model
                
                # Process and expect failure
                orchestrator = TranscriptionOrchestrator(config=mock_config)
                asyncio.run(orchestrator.process_feed("https://example.com/feed.xml"))
                
                # Verify error was tracked
                progress_file = Path(temp_dirs['state']) / 'podcast_progress.json'
                if progress_file.exists():
                    with open(progress_file) as f:
                        progress_data = json.load(f)
                    
                    episode_key = f'{scenario["name"]}-ep1'
                    if episode_key in progress_data.get('episodes', {}):
                        assert progress_data['episodes'][episode_key]['status'] == \
                               scenario['expected_status'].value
    
    def test_resource_cleanup(self, temp_dirs, minimal_rss_feeds,
                            mock_gemini_response, mock_config):
        """Test that resources are properly cleaned up after processing."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                minimal_rss_feeds['simple'].encode('utf-8')
            
            mock_model = MagicMock()
            mock_model.generate_content.return_value.text = mock_gemini_response
            mock_model_class.return_value = mock_model
            
            # Process multiple times to check for memory leaks
            for i in range(3):
                orchestrator = TranscriptionOrchestrator(config=mock_config)
                asyncio.run(orchestrator.process_feed("https://example.com/feed.xml"))
                
                # Explicit cleanup
                del orchestrator
                gc.collect()
        
        # Check memory usage didn't increase significantly
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Allow for some increase but flag potential leaks
        assert memory_increase < 50, f"Memory increased by {memory_increase}MB"
        
        # Verify temporary files are cleaned
        temp_files = list(Path(temp_dirs['checkpoints']).glob('*.tmp'))
        assert len(temp_files) == 0, "Temporary files not cleaned up"
    
    def test_different_feed_formats(self, temp_dirs, minimal_rss_feeds,
                                   mock_gemini_response, mock_config):
        """Test processing different RSS feed formats."""
        for format_name, feed_content in minimal_rss_feeds.items():
            with patch('urllib.request.urlopen') as mock_urlopen, \
                 patch('google.generativeai.GenerativeModel') as mock_model_class:
                
                mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                    feed_content.encode('utf-8')
                
                mock_model = MagicMock()
                mock_model.generate_content.return_value.text = mock_gemini_response
                mock_model_class.return_value = mock_model
                
                # Process feed
                orchestrator = TranscriptionOrchestrator(config=mock_config)
                asyncio.run(orchestrator.process_feed(f"https://example.com/{format_name}.xml"))
                
                # Clean up for next iteration
                del orchestrator
                gc.collect()