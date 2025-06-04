"""Integration tests for batch processing functionality.

This module tests the complete batch processing pipeline including:
- Multiple episode processing
- Progress monitoring
- Quota handling and recovery
- Failure and retry scenarios
- Resume capabilities
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
from typing import List, Dict, Any

from src.orchestrator import TranscriptionOrchestrator
from src.feed_parser import Episode, PodcastMetadata
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.utils.batch_progress import BatchProgressTracker
from src.retry_wrapper import QuotaExceededException, CircuitBreakerOpenException
from src.utils.state_management import reset_state, get_state_directory


@pytest.mark.integration
@pytest.mark.timeout(120)  # 2 minute timeout for integration tests
class TestBatchProcessingIntegration:
    """Test complete batch processing functionality."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_podcast_metadata(self):
        """Create mock podcast metadata."""
        return PodcastMetadata(
            title="Batch Test Podcast",
            description="A podcast for batch processing testing",
            link="https://example.com/podcast",
            language="en",
            author="Test Host"
        )
    
    @pytest.fixture
    def mock_episodes_20(self):
        """Create a list of 20 mock episodes for batch testing."""
        episodes = []
        for i in range(1, 21):
            episode = Episode(
                guid=f"ep{i}-guid",
                title=f"Episode {i}: Test Episode",
                audio_url=f"https://example.com/audio/episode{i}.mp3",
                published_date=datetime(2024, 1, i),
                description=f"Test episode {i} description",
                duration="30:00",
                author="Test Host"
            )
            episodes.append(episode)
        return episodes
    
    @pytest.fixture
    def mock_transcription_response(self):
        """Create a mock VTT transcription response."""
        return """WEBVTT

NOTE
Podcast: Batch Test Podcast
Episode: Test Episode
Date: 2024-01-01

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello and welcome to the test episode.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>This is a mock transcription for testing.

00:00:10.000 --> 00:00:15.000
<v SPEAKER_2>Thanks for listening.

00:00:15.000 --> 00:00:20.000
<v SPEAKER_1>We'll see you next time."""
    
    @pytest.fixture
    def mock_speaker_mapping(self):
        """Create mock speaker identification response."""
        return {
            "SPEAKER_1": "Test Host",
            "SPEAKER_2": "Test Guest"
        }
    
    @pytest.fixture 
    def orchestrator(self, temp_data_dir):
        """Create orchestrator instance with temp directory."""
        output_dir = temp_data_dir / "transcripts"
        output_dir.mkdir()
        
        # Mock environment for isolated testing
        with patch.dict('os.environ', {'STATE_DIR': str(temp_data_dir)}):
            orchestrator = TranscriptionOrchestrator(
                output_dir=output_dir,
                enable_checkpoint=True,
                resume=False,
                data_dir=temp_data_dir
            )
            yield orchestrator
    
    @pytest.mark.asyncio
    async def test_successful_batch_processing(self, orchestrator, mock_podcast_metadata, 
                                             mock_episodes_20, mock_transcription_response, 
                                             mock_speaker_mapping):
        """Test successful processing of a batch of episodes."""
        
        # Mock the feed parsing
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:5])  # Process 5 episodes
            
            # Mock the Gemini API calls
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    
                    # Set up successful responses
                    mock_transcribe.return_value = mock_transcription_response
                    mock_identify.return_value = mock_speaker_mapping
                    
                    # Mock YouTube searcher
                    with patch.object(orchestrator.youtube_searcher, 'search_youtube_url') as mock_youtube:
                        mock_youtube.return_value = None  # No YouTube URL found
                        
                        # Process the feed
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=5
                        )
                        
                        # Verify results
                        assert results['status'] == 'completed'
                        assert results['processed'] == 5
                        assert results['failed'] == 0
                        assert results['skipped'] == 0
                        assert len(results['episodes']) == 5
                        
                        # Verify all episodes were processed successfully
                        for episode_result in results['episodes']:
                            assert episode_result['status'] == 'completed'
                            assert 'output_file' in episode_result
                            assert 'duration' in episode_result
                        
                        # Verify API calls were made
                        assert mock_transcribe.call_count == 5
                        assert mock_identify.call_count == 5
    
    @pytest.mark.asyncio
    async def test_quota_exhaustion_and_recovery(self, orchestrator, mock_podcast_metadata,
                                                mock_episodes_20, mock_transcription_response):
        """Test quota exhaustion handling and recovery."""
        
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:10])
            
            # Mock quota exhaustion after 3 episodes
            call_count = 0
            
            async def mock_transcribe_with_quota_error(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    return mock_transcription_response
                else:
                    raise QuotaExceededException("Daily quota exceeded")
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    with patch.object(orchestrator.key_manager, 'get_available_key_for_quota') as mock_quota_key:
                        
                        mock_transcribe.side_effect = mock_transcribe_with_quota_error
                        mock_identify.return_value = {"SPEAKER_1": "Host"}
                        mock_quota_key.return_value = None  # No keys with quota available
                        
                        # Disable quota wait for testing
                        orchestrator.config.processing.quota_wait_enabled = False
                        
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=10
                        )
                        
                        # Should process 3 episodes then stop due to quota
                        assert results['status'] == 'quota_reached'
                        assert results['processed'] == 3
                        assert results['skipped'] == 7
                        
                        # Verify quota handling was attempted
                        assert mock_quota_key.called
    
    @pytest.mark.asyncio
    async def test_failure_and_retry_scenarios(self, orchestrator, mock_podcast_metadata,
                                              mock_episodes_20, mock_transcription_response):
        """Test episode failure handling and retry capabilities."""
        
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:5])
            
            # Mock failures for episodes 2 and 4
            call_count = 0
            
            async def mock_transcribe_with_failures(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count in [2, 4]:  # Fail episodes 2 and 4
                    raise Exception("Transcription failed for testing")
                return mock_transcription_response
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    
                    mock_transcribe.side_effect = mock_transcribe_with_failures
                    mock_identify.return_value = {"SPEAKER_1": "Host"}
                    
                    results = await orchestrator.process_feed(
                        "https://example.com/feed.xml",
                        max_episodes=5
                    )
                    
                    # Should have 3 successful, 2 failed
                    assert results['processed'] == 3
                    assert results['failed'] == 2
                    
                    # Check that failed episodes are marked correctly
                    failed_episodes = [ep for ep in results['episodes'] if ep['status'] == 'failed']
                    assert len(failed_episodes) == 2
                    
                    # Verify failed episodes can be retrieved for retry
                    failed_from_tracker = orchestrator.progress_tracker.get_failed()
                    assert len(failed_from_tracker) == 2
    
    @pytest.mark.asyncio
    async def test_progress_monitoring_integration(self, orchestrator, mock_podcast_metadata,
                                                  mock_episodes_20, mock_transcription_response):
        """Test progress monitoring during batch processing."""
        
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:3])
            
            # Track progress updates
            progress_updates = []
            
            def capture_progress_update(*args, **kwargs):
                progress_updates.append(args)
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    # Mock progress bar update method
                    with patch('src.utils.batch_progress.ProgressBar.update', side_effect=capture_progress_update):
                        
                        mock_transcribe.return_value = mock_transcription_response
                        mock_identify.return_value = {"SPEAKER_1": "Host"}
                        
                        results = await orchestrator.process_feed(
                            "https://example.com/feed.xml",
                            max_episodes=3
                        )
                        
                        # Verify processing completed successfully
                        assert results['status'] == 'completed'
                        assert results['processed'] == 3
                        
                        # Verify progress updates were captured
                        assert len(progress_updates) > 0
    
    @pytest.mark.asyncio
    async def test_batch_resume_capability(self, orchestrator, mock_podcast_metadata,
                                          mock_episodes_20, mock_transcription_response):
        """Test resuming interrupted batch processing."""
        
        # First, process some episodes
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:5])
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    
                    mock_transcribe.return_value = mock_transcription_response
                    mock_identify.return_value = {"SPEAKER_1": "Host"}
                    
                    # Process first 3 episodes
                    results = await orchestrator.process_feed(
                        "https://example.com/feed.xml",
                        max_episodes=3
                    )
                    
                    assert results['processed'] == 3
            
            # Now simulate resume with the same feed (should skip completed episodes)
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:5])
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                with patch.object(orchestrator.gemini_client, 'identify_speakers') as mock_identify:
                    
                    mock_transcribe.return_value = mock_transcription_response
                    mock_identify.return_value = {"SPEAKER_1": "Host"}
                    
                    # Process the feed again (should only process remaining 2 episodes)
                    results = await orchestrator.process_feed(
                        "https://example.com/feed.xml",
                        max_episodes=5
                    )
                    
                    # Should only process the 2 remaining episodes
                    assert results['processed'] == 2
                    
                    # Verify that transcribe was only called for the 2 new episodes
                    assert mock_transcribe.call_count == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, orchestrator, mock_podcast_metadata,
                                             mock_episodes_20):
        """Test circuit breaker behavior during batch processing."""
        
        with patch('src.orchestrator.parse_feed') as mock_parse_feed:
            mock_parse_feed.return_value = (mock_podcast_metadata, mock_episodes_20[:3])
            
            with patch.object(orchestrator.gemini_client, 'transcribe_audio') as mock_transcribe:
                
                # Simulate circuit breaker open exception
                mock_transcribe.side_effect = CircuitBreakerOpenException("Circuit breaker is open")
                
                results = await orchestrator.process_feed(
                    "https://example.com/feed.xml",
                    max_episodes=3
                )
                
                # All episodes should be skipped due to circuit breaker
                assert results['skipped'] >= 1  # At least one should be skipped due to circuit breaker
                
                # Check that episodes were marked as skipped with circuit breaker error
                skipped_episodes = [ep for ep in results['episodes'] if ep['status'] == 'skipped']
                assert len(skipped_episodes) >= 1
                
                # Verify the reason is circuit breaker
                circuit_breaker_episodes = [ep for ep in results['episodes'] 
                                           if ep.get('reason') == 'circuit_breaker_open']
                assert len(circuit_breaker_episodes) >= 1
    
    def test_batch_progress_tracker_functionality(self, temp_data_dir):
        """Test BatchProgressTracker functionality independently."""
        
        # Create progress tracker
        progress_file = temp_data_dir / ".progress.json"
        progress_tracker = ProgressTracker(progress_file)
        
        # Create batch progress tracker
        batch_tracker = BatchProgressTracker(progress_tracker, total_episodes=10)
        
        # Test initialization
        assert batch_tracker.stats.total_episodes == 10
        assert batch_tracker.stats.completed == 0
        assert batch_tracker.stats.failed == 0
        
        # Test starting batch
        batch_tracker.start_batch()
        assert batch_tracker.stats.start_time is not None
        
        # Test episode updates
        batch_tracker.update_current_episode("Test Episode 1")
        assert batch_tracker.current_episode_title == "Test Episode 1"
        
        # Test completion tracking
        batch_tracker.episode_completed(processing_time=120.0)
        assert 120.0 in batch_tracker.stats.processing_times
        
        # Test failure tracking
        batch_tracker.episode_failed("Test error")
        
        # Test skipped tracking
        batch_tracker.episode_skipped("Test reason")
        
        # Test finish
        batch_tracker.finish_batch("Test completed")
        
        # Verify status summary
        status = batch_tracker.get_status_summary()
        assert 'total_episodes' in status
        assert 'completed' in status
        assert 'failed' in status
    
    @pytest.mark.asyncio
    async def test_state_isolation_during_batch(self, temp_data_dir):
        """Test that batch processing properly isolates state files."""
        
        # Set up isolated state directory
        with patch.dict('os.environ', {'STATE_DIR': str(temp_data_dir)}):
            
            # Create orchestrator
            orchestrator = TranscriptionOrchestrator(
                output_dir=temp_data_dir / "transcripts",
                enable_checkpoint=True,
                data_dir=temp_data_dir
            )
            
            # Verify state files are created in temp directory
            assert orchestrator.progress_tracker.progress_file.parent == temp_data_dir
            
            # Add some test data
            test_episode_data = {
                'guid': 'test-episode',
                'title': 'Test Episode',
                'audio_url': 'https://example.com/test.mp3',
                'podcast_name': 'Test Podcast'
            }
            
            orchestrator.progress_tracker.add_episode(test_episode_data)
            
            # Verify state file exists in temp directory
            assert orchestrator.progress_tracker.progress_file.exists()
            
            # Verify state can be loaded
            with open(orchestrator.progress_tracker.progress_file, 'r') as f:
                state_data = json.load(f)
            
            assert 'test-episode' in state_data['episodes']


@pytest.mark.integration 
@pytest.mark.timeout(300)  # 5 minute timeout for integration tests
class TestBatchProcessingPerformance:
    """Performance tests for batch processing."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_large_batch_memory_usage(self, temp_data_dir):
        """Test memory usage with large batch processing."""
        
        # Create a large number of mock episodes
        episodes = []
        for i in range(100):
            episode = Episode(
                guid=f"perf-ep{i}-guid",
                title=f"Performance Episode {i}",
                audio_url=f"https://example.com/audio/perf{i}.mp3",
                published_date=datetime(2024, 1, 1),
                description=f"Performance test episode {i}",
                duration="15:00",
                author="Perf Host"
            )
            episodes.append(episode)
        
        with patch.dict('os.environ', {'STATE_DIR': str(temp_data_dir)}):
            orchestrator = TranscriptionOrchestrator(
                output_dir=temp_data_dir / "transcripts",
                data_dir=temp_data_dir
            )
            
            # Add all episodes to progress tracker
            for episode in episodes:
                episode_data = episode.to_dict()
                episode_data['podcast_name'] = 'Performance Test'
                orchestrator.progress_tracker.add_episode(episode_data)
            
            # Verify all episodes were added
            assert len(orchestrator.progress_tracker.state.episodes) == 100
            
            # Test getting pending episodes
            pending = orchestrator._get_pending_episodes(episodes, max_episodes=50)
            assert len(pending) == 50
            
            # Test progress tracker performance
            start_time = datetime.now()
            for i, episode in enumerate(episodes[:10]):
                orchestrator.progress_tracker.mark_started(episode.to_dict())
                orchestrator.progress_tracker.mark_completed(
                    episode.guid, 
                    f"output_{i}.vtt", 
                    processing_time=60.0
                )
            end_time = datetime.now()
            
            # Should complete within reasonable time
            processing_time = (end_time - start_time).total_seconds()
            assert processing_time < 5.0  # Should take less than 5 seconds