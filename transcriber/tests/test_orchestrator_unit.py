"""Comprehensive unit tests for TranscriptionOrchestrator class.

This module contains comprehensive unit tests for the TranscriptionOrchestrator,
covering initialization, episode processing, state management, error handling,
and quota management scenarios.
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call

from src.orchestrator import TranscriptionOrchestrator
from src.feed_parser import Episode, PodcastMetadata
from src.progress_tracker import EpisodeStatus
from src.retry_wrapper import QuotaExceededException, CircuitBreakerOpenException


class TestTranscriptionOrchestratorInit:
    """Test TranscriptionOrchestrator initialization."""
    
    def test_init_default_configuration(self, tmp_path):
        """Test initialization with default configuration."""
        output_dir = tmp_path / "transcripts"
        with patch('src.orchestrator.Config') as mock_config:
            with patch('src.orchestrator.ProgressTracker') as mock_progress:
                with patch('src.orchestrator.create_key_rotation_manager') as mock_key_manager:
                    with patch('src.orchestrator.create_gemini_client') as mock_gemini:
                        with patch('src.orchestrator.CheckpointManager') as mock_checkpoint:
                            orchestrator = TranscriptionOrchestrator(output_dir=output_dir)
                            
                            # Verify output directory created
                            assert output_dir.exists()
                            
                            # Verify components initialized
                            assert orchestrator.output_dir == output_dir
                            assert orchestrator.config is not None
                            assert orchestrator.progress_tracker is not None
                            assert orchestrator.key_manager is not None
                            assert orchestrator.gemini_client is not None
                            assert orchestrator.checkpoint_manager is not None
                            assert orchestrator.resume_mode is False
    
    def test_init_with_resume_mode(self, tmp_path):
        """Test initialization with resume mode enabled."""
        output_dir = tmp_path / "transcripts"
        with patch('src.orchestrator.Config'):
            with patch('src.orchestrator.ProgressTracker'):
                with patch('src.orchestrator.create_key_rotation_manager'):
                    with patch('src.orchestrator.create_gemini_client'):
                        with patch('src.orchestrator.CheckpointManager') as mock_checkpoint:
                            # Mock checkpoint manager to indicate resumable state
                            mock_checkpoint_instance = Mock()
                            mock_checkpoint_instance.can_resume.return_value = True
                            mock_checkpoint_instance.get_resume_info.return_value = {
                                'episode_title': 'Test Episode',
                                'hours_since_update': 2.5
                            }
                            mock_checkpoint.return_value = mock_checkpoint_instance
                            
                            orchestrator = TranscriptionOrchestrator(
                                output_dir=output_dir,
                                enable_checkpoint=True,
                                resume=True
                            )
                            
                            assert orchestrator.resume_mode is True
                            mock_checkpoint_instance.can_resume.assert_called_once()
                            mock_checkpoint_instance.get_resume_info.assert_called_once()
    
    def test_init_without_checkpoint(self, tmp_path):
        """Test initialization without checkpoint support."""
        output_dir = tmp_path / "transcripts"
        with patch('src.orchestrator.Config'):
            with patch('src.orchestrator.ProgressTracker'):
                with patch('src.orchestrator.create_key_rotation_manager'):
                    with patch('src.orchestrator.create_gemini_client'):
                        orchestrator = TranscriptionOrchestrator(
                            output_dir=output_dir,
                            enable_checkpoint=False
                        )
                        
                        assert orchestrator.checkpoint_manager is None
    
    def test_init_with_custom_data_dir(self, tmp_path):
        """Test initialization with custom data directory."""
        output_dir = tmp_path / "transcripts"
        data_dir = tmp_path / "custom_data"
        
        with patch('src.orchestrator.Config'):
            with patch('src.orchestrator.ProgressTracker') as mock_progress:
                with patch('src.orchestrator.create_key_rotation_manager'):
                    with patch('src.orchestrator.create_gemini_client'):
                        with patch('src.orchestrator.CheckpointManager'):
                            orchestrator = TranscriptionOrchestrator(
                                output_dir=output_dir,
                                data_dir=data_dir
                            )
                            
                            # Verify data directory created
                            assert data_dir.exists()
                            
                            # Verify progress tracker initialized with correct path
                            mock_progress.assert_called_with(data_dir / ".progress.json")


class TestGetPendingEpisodes:
    """Test _get_pending_episodes method."""
    
    def test_get_pending_episodes_all_new(self):
        """Test getting pending episodes when all are new."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Mock progress tracker state
        orchestrator.progress_tracker.state.episodes = {}
        
        # Create test episodes
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(5)
        ]
        
        pending = orchestrator._get_pending_episodes(episodes, max_episodes=3)
        
        assert len(pending) == 3
        assert all(ep.guid in ["ep0", "ep1", "ep2"] for ep in pending)
    
    def test_get_pending_episodes_mixed_status(self):
        """Test getting pending episodes with mixed statuses."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Mock progress tracker state with various statuses
        mock_state = Mock()
        mock_state.episodes = {
            "ep0": Mock(status=EpisodeStatus.COMPLETED),
            "ep1": Mock(status=EpisodeStatus.FAILED),
            "ep2": Mock(status=EpisodeStatus.IN_PROGRESS),
            "ep3": Mock(status=EpisodeStatus.PENDING),
        }
        orchestrator.progress_tracker.state = mock_state
        
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(6)
        ]
        
        pending = orchestrator._get_pending_episodes(episodes, max_episodes=10)
        
        # Should include: ep1 (failed), ep3 (pending), ep4 (new), ep5 (new)
        assert len(pending) == 4
        assert set(ep.guid for ep in pending) == {"ep1", "ep3", "ep4", "ep5"}
    
    def test_get_pending_episodes_respects_max_limit(self):
        """Test that max_episodes limit is respected."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        orchestrator.progress_tracker.state.episodes = {}
        
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(10)
        ]
        
        pending = orchestrator._get_pending_episodes(episodes, max_episodes=2)
        
        assert len(pending) == 2


class TestProcessSingleEpisode:
    """Test _process_single_episode and related methods."""
    
    @pytest.mark.asyncio
    async def test_process_episode_success(self):
        """Test successful episode processing."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Mock all processors
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            return_value="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello world"
        )
        orchestrator.speaker_identifier.identify_speakers = AsyncMock(
            return_value={"Speaker1": "John Doe"}
        )
        orchestrator.speaker_identifier.apply_speaker_mapping = Mock(
            return_value="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v John Doe>Hello world"
        )
        orchestrator.vtt_generator.create_metadata_from_episode = Mock()
        orchestrator.vtt_generator.generate_output_path = Mock(
            return_value=Path("output.vtt")
        )
        orchestrator.vtt_generator.generate_vtt = Mock()
        orchestrator.youtube_searcher.search_enabled = False
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        result = await orchestrator._process_episode(episode, podcast_metadata)
        
        assert result['status'] == 'completed'
        assert result['episode_id'] == "test-ep1"
        assert result['title'] == "Test Episode"
        assert 'output_file' in result
        assert 'speakers' in result
        assert 'duration' in result
    
    @pytest.mark.asyncio
    async def test_process_episode_with_youtube_search(self):
        """Test episode processing with YouTube search enabled."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Enable YouTube search
        orchestrator.youtube_searcher.search_enabled = True
        orchestrator.youtube_searcher.search_youtube_url = AsyncMock(
            return_value="https://youtube.com/watch?v=test123"
        )
        
        # Mock other processors
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            return_value="WEBVTT\n\nTest transcript"
        )
        orchestrator.speaker_identifier.identify_speakers = AsyncMock(return_value={})
        orchestrator.vtt_generator.create_metadata_from_episode = Mock()
        orchestrator.vtt_generator.generate_output_path = Mock(return_value=Path("output.vtt"))
        orchestrator.vtt_generator.generate_vtt = Mock()
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3",
            duration="45:30"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        result = await orchestrator._process_episode(episode, podcast_metadata)
        
        # Verify YouTube search was called
        orchestrator.youtube_searcher.search_youtube_url.assert_called_once()
        call_args = orchestrator.youtube_searcher.search_youtube_url.call_args
        assert call_args[1]['podcast_name'] == "Test Podcast"
        assert call_args[1]['episode_title'] == "Test Episode"
        assert call_args[1]['duration_seconds'] == 2730  # 45:30
    
    @pytest.mark.asyncio
    async def test_process_episode_transcription_failure(self):
        """Test episode processing when transcription fails."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            return_value=None
        )
        orchestrator.youtube_searcher.search_enabled = False
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        result = await orchestrator._process_episode(episode, podcast_metadata)
        
        assert result['status'] == 'failed'
        assert result['episode_id'] == "test-ep1"
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_process_episode_speaker_id_failure(self):
        """Test episode processing when speaker identification fails."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            return_value="WEBVTT\n\nTest transcript"
        )
        orchestrator.speaker_identifier.identify_speakers = AsyncMock(
            side_effect=Exception("Speaker ID failed")
        )
        orchestrator.vtt_generator.create_metadata_from_episode = Mock()
        orchestrator.vtt_generator.generate_output_path = Mock(return_value=Path("output.vtt"))
        orchestrator.vtt_generator.generate_vtt = Mock()
        orchestrator.youtube_searcher.search_enabled = False
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        result = await orchestrator._process_episode(episode, podcast_metadata)
        
        # Should still complete but without speaker mapping
        assert result['status'] == 'completed'
        assert result['speakers'] == []
    
    @pytest.mark.asyncio
    async def test_process_episode_quota_exceeded(self):
        """Test episode processing when quota is exceeded."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            side_effect=QuotaExceededException("Quota exceeded")
        )
        orchestrator.youtube_searcher.search_enabled = False
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        with pytest.raises(QuotaExceededException):
            await orchestrator._process_episode(episode, podcast_metadata)
    
    @pytest.mark.asyncio
    async def test_process_episode_circuit_breaker_open(self):
        """Test episode processing when circuit breaker is open."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        orchestrator.transcription_processor.transcribe_episode = AsyncMock(
            side_effect=CircuitBreakerOpenException("Circuit breaker open")
        )
        orchestrator.youtube_searcher.search_enabled = False
        orchestrator.progress_tracker.update_episode_state = Mock()
        
        episode = Episode(
            guid="test-ep1",
            title="Test Episode",
            audio_url="http://test.com/audio.mp3"
        )
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        
        result = await orchestrator._process_episode(episode, podcast_metadata)
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'circuit_breaker_open'


class TestProcessFeed:
    """Test process_feed method with various scenarios."""
    
    @pytest.mark.asyncio
    async def test_process_feed_success(self):
        """Test successful feed processing."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Mock feed parser
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(3)
        ]
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            # Mock episode processing
            orchestrator._process_episode = AsyncMock(
                side_effect=[
                    {'status': 'completed', 'episode_id': 'ep0', 'title': 'Episode 0'},
                    {'status': 'completed', 'episode_id': 'ep1', 'title': 'Episode 1'},
                    {'status': 'failed', 'episode_id': 'ep2', 'title': 'Episode 2', 'error': 'Test error'}
                ]
            )
            
            # Mock progress tracker
            orchestrator.progress_tracker.state.episodes = {}
            orchestrator.gemini_client.get_usage_summary = Mock(return_value={})
            orchestrator._generate_summary_report = Mock()
            
            result = await orchestrator.process_feed("http://test.com/feed.xml", max_episodes=3)
            
            assert result['status'] == 'completed'
            assert result['processed'] == 2
            assert result['failed'] == 1
            assert result['skipped'] == 0
            assert len(result['episodes']) == 3
    
    @pytest.mark.asyncio
    async def test_process_feed_parse_failure(self):
        """Test feed processing when RSS parsing fails."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.side_effect = Exception("Parse error")
            
            result = await orchestrator.process_feed("http://test.com/feed.xml")
            
            assert result['status'] == 'failed'
            assert 'error' in result
            assert "Parse error" in result['error']
    
    @pytest.mark.asyncio
    async def test_process_feed_no_pending_episodes(self):
        """Test feed processing when all episodes are already processed."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = [
            Episode(guid="ep0", title="Episode 0", audio_url="http://test.com/ep0.mp3")
        ]
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            # Mock all episodes as completed
            mock_state = Mock()
            mock_state.episodes = {
                "ep0": Mock(status=EpisodeStatus.COMPLETED)
            }
            orchestrator.progress_tracker.state = mock_state
            orchestrator._generate_summary_report = Mock()
            
            result = await orchestrator.process_feed("http://test.com/feed.xml")
            
            assert result['status'] == 'completed'
            assert result['processed'] == 0
            assert result['message'] == 'All episodes already processed'
    
    @pytest.mark.asyncio
    async def test_process_feed_quota_limit_reached(self):
        """Test feed processing when quota limit is reached."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(5)
        ]
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            # Mock high usage to trigger quota limit
            orchestrator.gemini_client.get_usage_summary = Mock(
                return_value={
                    'key1': {'requests_today': 25},
                    'key2': {'requests_today': 25}
                }
            )
            orchestrator.gemini_client.api_keys = ['key1', 'key2']
            orchestrator.progress_tracker.state.episodes = {}
            orchestrator._generate_summary_report = Mock()
            
            result = await orchestrator.process_feed("http://test.com/feed.xml")
            
            assert result['status'] == 'quota_reached'
            assert result['skipped'] == 5
    
    @pytest.mark.asyncio
    async def test_process_feed_with_resume(self):
        """Test feed processing with checkpoint resume."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        # Mock checkpoint manager
        orchestrator.checkpoint_manager.can_resume = Mock(return_value=True)
        orchestrator._resume_processing = AsyncMock(
            return_value={
                'status': 'resumed',
                'processed': 1,
                'failed': 0,
                'skipped': 0,
                'episodes': [{'status': 'completed'}]
            }
        )
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = []
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            result = await orchestrator.process_feed("http://test.com/feed.xml")
            
            assert result['status'] == 'resumed'
            assert result['processed'] == 1
            orchestrator._resume_processing.assert_called_once()


class TestQuotaManagement:
    """Test quota management and waiting functionality."""
    
    @pytest.mark.asyncio
    async def test_wait_for_quota_reset_success(self):
        """Test successful quota reset waiting."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        orchestrator.config.processing.max_quota_wait_hours = 24
        orchestrator.config.processing.quota_check_interval_minutes = 1
        
        # Mock datetime to control wait time
        with patch('src.orchestrator.datetime') as mock_datetime:
            # Set current time to 11 PM Pacific
            mock_now = datetime(2024, 1, 1, 23, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            with patch('src.orchestrator.asyncio.sleep') as mock_sleep:
                result = await orchestrator._wait_for_quota_reset()
                
                assert result is True
                # Should wait approximately 1 hour + 5 minute buffer
                mock_sleep.assert_called()
    
    @pytest.mark.asyncio
    async def test_wait_for_quota_reset_exceeds_max(self):
        """Test quota reset wait when wait time exceeds maximum."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        orchestrator.config.processing.max_quota_wait_hours = 2
        
        # Mock datetime to require long wait
        with patch('src.orchestrator.datetime') as mock_datetime:
            # Set current time to 8 AM Pacific (16 hours until midnight)
            mock_now = datetime(2024, 1, 1, 8, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = await orchestrator._wait_for_quota_reset()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_wait_for_quota_reset_interrupted(self):
        """Test quota reset wait when interrupted."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        orchestrator.config.processing.max_quota_wait_hours = 24
        
        with patch('src.orchestrator.asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError()
            
            result = await orchestrator._wait_for_quota_reset()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_process_feed_quota_exceeded_with_key_rotation(self):
        """Test handling quota exceeded with key rotation."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = [
            Episode(guid="ep0", title="Episode 0", audio_url="http://test.com/ep0.mp3", duration="30:00")
        ]
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            # Track process_episode calls
            process_episode_calls = []
            async def mock_process_episode(episode, metadata):
                process_episode_calls.append(episode.guid)
                if len(process_episode_calls) == 1:
                    # First call raises quota exceeded
                    raise QuotaExceededException("Quota exceeded")
                else:
                    # Second call succeeds
                    return {'status': 'completed', 'episode_id': 'ep0', 'title': 'Episode 0'}
            
            orchestrator._process_episode = mock_process_episode
            
            # Mock key rotation - return key once, then None
            key_rotation_calls = []
            def mock_get_available_key(tokens):
                key_rotation_calls.append(tokens)
                if len(key_rotation_calls) == 1:
                    return "new-api-key"
                return None
            
            orchestrator.key_manager.get_available_key_for_quota = mock_get_available_key
            
            orchestrator.progress_tracker.state.episodes = {}
            orchestrator.gemini_client.get_usage_summary = Mock(return_value={})
            orchestrator._generate_summary_report = Mock()
            
            result = await orchestrator.process_feed("http://test.com/feed.xml")
            
            assert result['status'] == 'completed'
            assert result['processed'] == 1
            
            # Verify key rotation was attempted
            assert len(key_rotation_calls) == 1
            assert len(process_episode_calls) == 2  # Two attempts


class TestCheckpointRecovery:
    """Test checkpoint recovery functionality."""
    
    @pytest.mark.asyncio
    async def test_resume_from_transcription_stage(self):
        """Test resuming from transcription stage."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        # Mock checkpoint data with all required attributes
        mock_checkpoint = Mock()
        mock_checkpoint.episode_id = 'ep1'
        mock_checkpoint.title = 'Test Episode'
        mock_checkpoint.audio_url = 'http://test.com/audio.mp3'
        mock_checkpoint.metadata = {
            'podcast_name': 'Test Podcast',
            'publication_date': '2024-01-01',
            'description': 'Test description',
            'duration': '30:00',
            'author': 'Test Author'
        }
        
        checkpoint_data = {
            'checkpoint': mock_checkpoint,
            'temp_data': {}
        }
        
        orchestrator.checkpoint_manager.resume_processing = Mock(
            return_value=('transcription', checkpoint_data)
        )
        
        orchestrator._process_episode_full = AsyncMock(
            return_value={'status': 'completed', 'episode_id': 'ep1'}
        )
        
        result = await orchestrator._resume_processing()
        
        assert result is not None
        assert result['status'] == 'resumed'
        assert result['processed'] == 1
        orchestrator._process_episode_full.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resume_from_speaker_id_stage(self):
        """Test resuming from speaker identification stage."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        mock_checkpoint = Mock()
        mock_checkpoint.episode_id = 'ep1'
        mock_checkpoint.title = 'Test Episode'
        mock_checkpoint.audio_url = 'http://test.com/audio.mp3'
        mock_checkpoint.metadata = {
            'podcast_name': 'Test Podcast',
            'publication_date': '2024-01-01',
            'description': 'Test description',
            'duration': '30:00',
            'author': 'Test Author'
        }
        
        checkpoint_data = {
            'checkpoint': mock_checkpoint,
            'temp_data': {
                'transcription': 'WEBVTT\n\nTest transcript'
            }
        }
        
        orchestrator.checkpoint_manager.resume_processing = Mock(
            return_value=('speaker_identification', checkpoint_data)
        )
        
        orchestrator._process_from_speaker_id = AsyncMock(
            return_value={'status': 'completed', 'episode_id': 'ep1'}
        )
        
        result = await orchestrator._resume_processing()
        
        assert result is not None
        assert result['status'] == 'resumed'
        orchestrator._process_from_speaker_id.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resume_from_vtt_generation_stage(self):
        """Test resuming from VTT generation stage."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        mock_checkpoint = Mock()
        mock_checkpoint.episode_id = 'ep1'
        mock_checkpoint.title = 'Test Episode'
        mock_checkpoint.audio_url = 'http://test.com/audio.mp3'
        mock_checkpoint.metadata = {
            'podcast_name': 'Test Podcast',
            'publication_date': '2024-01-01',
            'description': 'Test description',
            'duration': '30:00',
            'author': 'Test Author'
        }
        
        checkpoint_data = {
            'checkpoint': mock_checkpoint,
            'temp_data': {
                'transcription': 'WEBVTT\n\nTest transcript',
                'speaker_mapping': '{"Speaker1": "John Doe"}'
            }
        }
        
        orchestrator.checkpoint_manager.resume_processing = Mock(
            return_value=('vtt_generation', checkpoint_data)
        )
        
        orchestrator._process_from_vtt_gen = AsyncMock(
            return_value={'status': 'completed', 'episode_id': 'ep1'}
        )
        
        result = await orchestrator._resume_processing()
        
        assert result is not None
        assert result['status'] == 'resumed'
        orchestrator._process_from_vtt_gen.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resume_with_missing_data(self):
        """Test resume when required data is missing."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        mock_checkpoint = Mock()
        mock_checkpoint.episode_id = 'ep1'
        mock_checkpoint.title = 'Test Episode'
        mock_checkpoint.audio_url = 'http://test.com/audio.mp3'
        mock_checkpoint.metadata = {
            'podcast_name': 'Test Podcast',
            'publication_date': '2024-01-01',
            'description': 'Test description',
            'duration': '30:00',
            'author': 'Test Author'
        }
        
        checkpoint_data = {
            'checkpoint': mock_checkpoint,
            'temp_data': {}  # Missing transcription
        }
        
        orchestrator.checkpoint_manager.resume_processing = Mock(
            return_value=('speaker_identification', checkpoint_data)
        )
        
        orchestrator._process_episode_full = AsyncMock(
            return_value={'status': 'completed', 'episode_id': 'ep1'}
        )
        
        result = await orchestrator._resume_processing()
        
        # Should fall back to full processing
        orchestrator._process_episode_full.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resume_failure(self):
        """Test handling of resume failure."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True, resume=True)
        
        orchestrator.checkpoint_manager.resume_processing = Mock(
            return_value=None  # Return None to indicate no checkpoint to resume
        )
        
        result = await orchestrator._resume_processing()
        
        assert result is None


class TestConcurrentProcessing:
    """Test concurrent processing limits and behavior."""
    
    @pytest.mark.asyncio
    async def test_sequential_processing(self):
        """Test that episodes are processed sequentially, not concurrently."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        episodes = [
            Episode(guid=f"ep{i}", title=f"Episode {i}", audio_url=f"http://test.com/ep{i}.mp3")
            for i in range(3)
        ]
        
        with patch('src.orchestrator.parse_feed') as mock_parse:
            mock_parse.return_value = (podcast_metadata, episodes)
            
            # Track call order
            call_order = []
            
            async def mock_process_episode(episode, metadata):
                call_order.append(episode.guid)
                await asyncio.sleep(0.1)  # Simulate processing time
                return {'status': 'completed', 'episode_id': episode.guid, 'title': episode.title}
            
            orchestrator._process_episode = mock_process_episode
            orchestrator.progress_tracker.state.episodes = {}
            orchestrator.gemini_client.get_usage_summary = Mock(return_value={})
            orchestrator._generate_summary_report = Mock()
            
            await orchestrator.process_feed("http://test.com/feed.xml")
            
            # Verify sequential processing
            assert call_order == ['ep0', 'ep1', 'ep2']


class TestSummaryReport:
    """Test summary report generation."""
    
    def test_generate_summary_report(self, tmp_path):
        """Test summary report generation."""
        output_dir = tmp_path / "transcripts"
        orchestrator = TranscriptionOrchestrator(output_dir=output_dir, enable_checkpoint=False)
        
        podcast_metadata = PodcastMetadata(title="Test Podcast", description="Test")
        results = {
            'processed': 2,
            'failed': 1,
            'skipped': 0,
            'episodes': [
                {'status': 'completed', 'episode_id': 'ep1'},
                {'status': 'completed', 'episode_id': 'ep2'},
                {'status': 'failed', 'episode_id': 'ep3', 'error': 'Test error'}
            ]
        }
        
        orchestrator.gemini_client.get_usage_summary = Mock(
            return_value={'key1': {'requests_today': 10}}
        )
        
        orchestrator._generate_summary_report(results, podcast_metadata)
        
        report_file = output_dir / "Test Podcast_report.json"
        assert report_file.exists()
        
        with open(report_file) as f:
            report = json.load(f)
        
        assert report['podcast'] == "Test Podcast"
        assert report['summary']['total_processed'] == 2
        assert report['summary']['failed'] == 1
        assert len(report['episodes']) == 3
        assert 'api_usage' in report


class TestCleanup:
    """Test cleanup functionality."""
    
    def test_cleanup_old_data(self):
        """Test cleanup of old checkpoint and progress data."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=True)
        
        orchestrator.checkpoint_manager.cleanup_old_checkpoints = Mock()
        
        orchestrator.cleanup_old_data(days=7)
        
        orchestrator.checkpoint_manager.cleanup_old_checkpoints.assert_called_once_with(7)
    
    def test_cleanup_without_checkpoint_manager(self):
        """Test cleanup when checkpoint manager is disabled."""
        orchestrator = TranscriptionOrchestrator(enable_checkpoint=False)
        
        # Should not raise exception
        orchestrator.cleanup_old_data(days=7)