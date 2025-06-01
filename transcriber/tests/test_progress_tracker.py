"""Unit tests for the progress tracker module."""

import pytest
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

from src.progress_tracker import (
    EpisodeStatus, EpisodeProgress, ProgressState, ProgressTracker
)


class TestEpisodeStatus:
    """Test EpisodeStatus enum."""
    
    def test_episode_status_values(self):
        """Test episode status enum values."""
        assert EpisodeStatus.PENDING.value == "pending"
        assert EpisodeStatus.IN_PROGRESS.value == "in_progress"
        assert EpisodeStatus.COMPLETED.value == "completed"
        assert EpisodeStatus.FAILED.value == "failed"


class TestEpisodeProgress:
    """Test EpisodeProgress dataclass."""
    
    def test_episode_progress_creation(self):
        """Test creating episode progress."""
        episode = EpisodeProgress(
            guid="test-guid",
            status=EpisodeStatus.PENDING,
            podcast_name="Test Podcast",
            title="Test Episode"
        )
        
        assert episode.guid == "test-guid"
        assert episode.status == EpisodeStatus.PENDING
        assert episode.podcast_name == "Test Podcast"
        assert episode.title == "Test Episode"
        assert episode.attempt_count == 0
        assert episode.last_attempt is None
    
    def test_episode_progress_to_dict(self):
        """Test converting episode progress to dictionary."""
        now = datetime.now(timezone.utc)
        episode = EpisodeProgress(
            guid="test-guid",
            status=EpisodeStatus.COMPLETED,
            podcast_name="Test Podcast",
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            publication_date="2024-01-15",
            attempt_count=1,
            last_attempt=now,
            completed_at=now + timedelta(minutes=5),
            processing_time_seconds=300.5,
            output_file="/path/to/output.vtt",
            api_key_used="key_1"
        )
        
        data = episode.to_dict()
        
        assert data['guid'] == "test-guid"
        assert data['status'] == "completed"
        assert data['podcast_name'] == "Test Podcast"
        assert data['attempt_count'] == 1
        assert data['last_attempt'] == now.isoformat()
        assert data['processing_time_seconds'] == 300.5
        assert data['api_key_used'] == "key_1"
    
    def test_episode_progress_from_dict(self):
        """Test creating episode progress from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            'guid': 'test-guid',
            'status': 'in_progress',
            'podcast_name': 'Test Podcast',
            'title': 'Test Episode',
            'audio_url': 'https://example.com/episode.mp3',
            'publication_date': '2024-01-15',
            'attempt_count': 2,
            'last_attempt': now.isoformat(),
            'error': 'Test error',
            'error_type': 'network_error'
        }
        
        episode = EpisodeProgress.from_dict(data)
        
        assert episode.guid == 'test-guid'
        assert episode.status == EpisodeStatus.IN_PROGRESS
        assert episode.attempt_count == 2
        assert episode.last_attempt.isoformat() == now.isoformat()
        assert episode.error == 'Test error'
        assert episode.error_type == 'network_error'
    
    def test_episode_progress_from_dict_minimal(self):
        """Test creating episode progress from minimal dictionary."""
        data = {'guid': 'minimal-guid'}
        
        episode = EpisodeProgress.from_dict(data)
        
        assert episode.guid == 'minimal-guid'
        assert episode.status == EpisodeStatus.PENDING
        assert episode.podcast_name == ''
        assert episode.attempt_count == 0


class TestProgressState:
    """Test ProgressState dataclass."""
    
    def test_progress_state_creation(self):
        """Test creating progress state."""
        state = ProgressState()
        
        assert state.total_processed == 0
        assert state.daily_quota_used == 0
        assert state.quota_reset_time is None
        assert len(state.episodes) == 0
        assert state.next_key_index == 0
    
    def test_progress_state_to_dict(self):
        """Test converting progress state to dictionary."""
        now = datetime.now(timezone.utc)
        state = ProgressState(
            last_updated=now,
            total_processed=10,
            daily_quota_used=20,
            quota_reset_time=now - timedelta(hours=1),
            next_key_index=1
        )
        
        # Add an episode
        episode = EpisodeProgress(guid="ep1", status=EpisodeStatus.COMPLETED)
        state.episodes["ep1"] = episode
        
        data = state.to_dict()
        
        assert data['meta']['last_updated'] == now.isoformat()
        assert data['meta']['total_processed'] == 10
        assert data['meta']['daily_quota_used'] == 20
        assert data['meta']['quota_reset_time'] == (now - timedelta(hours=1)).isoformat()
        assert data['meta']['next_key_index'] == 1
        assert 'ep1' in data['episodes']
        assert data['episodes']['ep1']['status'] == 'completed'
    
    def test_progress_state_from_dict(self):
        """Test creating progress state from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            'meta': {
                'last_updated': now.isoformat(),
                'total_processed': 5,
                'daily_quota_used': 10,
                'quota_reset_time': now.isoformat(),
                'next_key_index': 2
            },
            'episodes': {
                'ep1': {
                    'guid': 'ep1',
                    'status': 'completed',
                    'title': 'Episode 1'
                },
                'ep2': {
                    'guid': 'ep2',
                    'status': 'failed',
                    'title': 'Episode 2',
                    'error': 'Test error'
                }
            }
        }
        
        state = ProgressState.from_dict(data)
        
        assert state.total_processed == 5
        assert state.daily_quota_used == 10
        assert state.next_key_index == 2
        assert len(state.episodes) == 2
        assert state.episodes['ep1'].status == EpisodeStatus.COMPLETED
        assert state.episodes['ep2'].status == EpisodeStatus.FAILED
        assert state.episodes['ep2'].error == 'Test error'


class TestProgressTracker:
    """Test ProgressTracker class."""
    
    @pytest.fixture
    def tracker_file(self, tmp_path):
        """Create a temporary tracker file path."""
        return tmp_path / '.progress.json'
    
    def test_init_new_tracker(self, tracker_file, mock_logger):
        """Test initializing a new progress tracker."""
        tracker = ProgressTracker(tracker_file)
        
        assert tracker.progress_file == tracker_file
        assert len(tracker.state.episodes) == 0
        assert tracker.state.total_processed == 0
    
    def test_init_existing_tracker(self, tracker_file, mock_logger):
        """Test initializing tracker with existing file."""
        # Create existing progress file
        state_data = {
            'meta': {'total_processed': 3},
            'episodes': {
                'ep1': {'guid': 'ep1', 'status': 'completed', 'title': 'Episode 1'}
            }
        }
        with open(tracker_file, 'w') as f:
            json.dump(state_data, f)
        
        tracker = ProgressTracker(tracker_file)
        
        assert tracker.state.total_processed == 3
        assert len(tracker.state.episodes) == 1
        assert 'ep1' in tracker.state.episodes
    
    def test_init_corrupted_file(self, tracker_file, mock_logger):
        """Test initializing tracker with corrupted file."""
        # Create corrupted file
        with open(tracker_file, 'w') as f:
            f.write("invalid json content {[}")
        
        tracker = ProgressTracker(tracker_file)
        
        # Should start with empty state
        assert len(tracker.state.episodes) == 0
        assert tracker.state.total_processed == 0
    
    def test_save_state(self, tracker_file, mock_logger):
        """Test saving state atomically."""
        tracker = ProgressTracker(tracker_file)
        
        # Add some data
        episode = EpisodeProgress(guid="test", status=EpisodeStatus.PENDING)
        tracker.state.episodes["test"] = episode
        tracker.state.total_processed = 5
        
        # Save state
        tracker._save_state()
        
        # Verify file exists and contains correct data
        assert tracker_file.exists()
        with open(tracker_file, 'r') as f:
            data = json.load(f)
        
        assert data['meta']['total_processed'] == 5
        assert 'test' in data['episodes']
    
    def test_save_state_atomic_write(self, tracker_file, mock_logger):
        """Test atomic write prevents corruption."""
        tracker = ProgressTracker(tracker_file)
        
        # Mock os.replace to simulate failure
        with patch('os.replace', side_effect=Exception("Write failed")):
            with pytest.raises(Exception):
                tracker._save_state()
        
        # Original file should not exist (new tracker)
        assert not tracker_file.exists()
    
    def test_mark_started(self, tracker_file, mock_logger):
        """Test marking episode as started."""
        tracker = ProgressTracker(tracker_file)
        
        episode_data = {
            'guid': 'ep1',
            'podcast_name': 'Test Podcast',
            'title': 'Episode 1',
            'audio_url': 'https://example.com/ep1.mp3',
            'publication_date': '2024-01-15'
        }
        
        tracker.mark_started(episode_data, api_key_index=0)
        
        assert 'ep1' in tracker.state.episodes
        episode = tracker.state.episodes['ep1']
        assert episode.status == EpisodeStatus.IN_PROGRESS
        assert episode.podcast_name == 'Test Podcast'
        assert episode.attempt_count == 1
        assert episode.last_attempt is not None
        assert episode.api_key_used == 'key_1'
    
    def test_mark_started_existing_episode(self, tracker_file, mock_logger):
        """Test marking existing episode as started (retry)."""
        tracker = ProgressTracker(tracker_file)
        
        # Add failed episode
        episode = EpisodeProgress(
            guid='ep1',
            status=EpisodeStatus.FAILED,
            attempt_count=1,
            error='Previous error'
        )
        tracker.state.episodes['ep1'] = episode
        
        # Mark as started again
        episode_data = {'guid': 'ep1', 'title': 'Episode 1'}
        tracker.mark_started(episode_data, api_key_index=1)
        
        episode = tracker.state.episodes['ep1']
        assert episode.status == EpisodeStatus.IN_PROGRESS
        assert episode.attempt_count == 2
        assert episode.error is None  # Error cleared
        assert episode.api_key_used == 'key_2'
    
    def test_mark_completed(self, tracker_file, mock_logger):
        """Test marking episode as completed."""
        tracker = ProgressTracker(tracker_file)
        
        # Add in-progress episode
        episode = EpisodeProgress(
            guid='ep1',
            status=EpisodeStatus.IN_PROGRESS,
            title='Episode 1'
        )
        tracker.state.episodes['ep1'] = episode
        initial_total = tracker.state.total_processed
        initial_quota = tracker.state.daily_quota_used
        
        tracker.mark_completed('ep1', '/output/ep1.vtt', 123.45)
        
        episode = tracker.state.episodes['ep1']
        assert episode.status == EpisodeStatus.COMPLETED
        assert episode.output_file == '/output/ep1.vtt'
        assert episode.processing_time_seconds == 123.45
        assert episode.completed_at is not None
        assert tracker.state.total_processed == initial_total + 1
        assert tracker.state.daily_quota_used == initial_quota + 2
    
    def test_mark_completed_missing_episode(self, tracker_file, mock_logger):
        """Test marking non-existent episode as completed."""
        tracker = ProgressTracker(tracker_file)
        
        # Should not raise error
        tracker.mark_completed('non-existent', '/output/file.vtt', 100.0)
        
        assert 'non-existent' not in tracker.state.episodes
    
    def test_mark_failed(self, tracker_file, mock_logger):
        """Test marking episode as failed."""
        tracker = ProgressTracker(tracker_file)
        
        # Add in-progress episode
        episode = EpisodeProgress(
            guid='ep1',
            status=EpisodeStatus.IN_PROGRESS,
            title='Episode 1'
        )
        tracker.state.episodes['ep1'] = episode
        
        tracker.mark_failed('ep1', 'Network timeout', 'network_error')
        
        episode = tracker.state.episodes['ep1']
        assert episode.status == EpisodeStatus.FAILED
        assert episode.error == 'Network timeout'
        assert episode.error_type == 'network_error'
    
    def test_get_pending(self, tracker_file, mock_logger):
        """Test getting pending episodes."""
        tracker = ProgressTracker(tracker_file)
        
        # Add episodes with different statuses
        tracker.state.episodes['ep1'] = EpisodeProgress(
            guid='ep1', status=EpisodeStatus.PENDING
        )
        tracker.state.episodes['ep2'] = EpisodeProgress(
            guid='ep2', status=EpisodeStatus.COMPLETED
        )
        tracker.state.episodes['ep3'] = EpisodeProgress(
            guid='ep3', status=EpisodeStatus.PENDING
        )
        
        pending = tracker.get_pending()
        
        assert len(pending) == 2
        assert all(ep.status == EpisodeStatus.PENDING for ep in pending)
        guids = [ep.guid for ep in pending]
        assert 'ep1' in guids
        assert 'ep3' in guids
    
    def test_get_failed(self, tracker_file, mock_logger):
        """Test getting failed episodes eligible for retry."""
        tracker = ProgressTracker(tracker_file)
        
        # Add failed episodes with different attempt counts
        tracker.state.episodes['ep1'] = EpisodeProgress(
            guid='ep1', status=EpisodeStatus.FAILED, attempt_count=1
        )
        tracker.state.episodes['ep2'] = EpisodeProgress(
            guid='ep2', status=EpisodeStatus.FAILED, attempt_count=2
        )
        tracker.state.episodes['ep3'] = EpisodeProgress(
            guid='ep3', status=EpisodeStatus.FAILED, attempt_count=3
        )
        
        # Default max_attempts=2
        failed = tracker.get_failed()
        
        assert len(failed) == 1
        assert failed[0].guid == 'ep1'
        
        # With higher max_attempts
        failed = tracker.get_failed(max_attempts=4)
        assert len(failed) == 3
    
    def test_get_in_progress(self, tracker_file, mock_logger):
        """Test getting in-progress episodes."""
        tracker = ProgressTracker(tracker_file)
        
        # Add episodes with different statuses
        tracker.state.episodes['ep1'] = EpisodeProgress(
            guid='ep1', status=EpisodeStatus.IN_PROGRESS
        )
        tracker.state.episodes['ep2'] = EpisodeProgress(
            guid='ep2', status=EpisodeStatus.COMPLETED
        )
        
        in_progress = tracker.get_in_progress()
        
        assert len(in_progress) == 1
        assert in_progress[0].guid == 'ep1'
    
    def test_add_episode(self, tracker_file, mock_logger):
        """Test adding new episode."""
        tracker = ProgressTracker(tracker_file)
        
        episode_data = {
            'guid': 'new-ep',
            'podcast_name': 'Test Podcast',
            'title': 'New Episode',
            'audio_url': 'https://example.com/new.mp3',
            'publication_date': '2024-01-20'
        }
        
        tracker.add_episode(episode_data)
        
        assert 'new-ep' in tracker.state.episodes
        episode = tracker.state.episodes['new-ep']
        assert episode.status == EpisodeStatus.PENDING
        assert episode.podcast_name == 'Test Podcast'
        assert episode.title == 'New Episode'
    
    def test_add_existing_episode(self, tracker_file, mock_logger):
        """Test adding episode that already exists."""
        tracker = ProgressTracker(tracker_file)
        
        # Add episode
        tracker.state.episodes['ep1'] = EpisodeProgress(
            guid='ep1', status=EpisodeStatus.COMPLETED
        )
        
        # Try to add again
        episode_data = {'guid': 'ep1', 'title': 'Duplicate'}
        tracker.add_episode(episode_data)
        
        # Should not overwrite
        assert tracker.state.episodes['ep1'].status == EpisodeStatus.COMPLETED
    
    def test_key_rotation_tracking(self, tracker_file, mock_logger):
        """Test API key rotation tracking."""
        tracker = ProgressTracker(tracker_file)
        
        assert tracker.get_next_key_index() == 0
        
        tracker.update_key_index(1)
        assert tracker.get_next_key_index() == 1
        
        tracker.update_key_index(0)
        assert tracker.get_next_key_index() == 0
    
    def test_reset_daily_quota(self, tracker_file, mock_logger):
        """Test resetting daily quota."""
        tracker = ProgressTracker(tracker_file)
        
        # Set some quota usage
        tracker.state.daily_quota_used = 20
        
        tracker.reset_daily_quota()
        
        assert tracker.state.daily_quota_used == 0
        assert tracker.state.quota_reset_time is not None
    
    def test_cleanup_interrupted(self, tracker_file, mock_logger):
        """Test cleaning up interrupted episodes."""
        tracker = ProgressTracker(tracker_file)
        
        # Add interrupted episodes
        tracker.state.episodes['ep1'] = EpisodeProgress(
            guid='ep1', status=EpisodeStatus.IN_PROGRESS, title='Episode 1'
        )
        tracker.state.episodes['ep2'] = EpisodeProgress(
            guid='ep2', status=EpisodeStatus.IN_PROGRESS, title='Episode 2'
        )
        tracker.state.episodes['ep3'] = EpisodeProgress(
            guid='ep3', status=EpisodeStatus.COMPLETED, title='Episode 3'
        )
        
        tracker.cleanup_interrupted()
        
        # In-progress should be marked as failed
        assert tracker.state.episodes['ep1'].status == EpisodeStatus.FAILED
        assert tracker.state.episodes['ep1'].error == "Processing interrupted - marked for retry"
        assert tracker.state.episodes['ep1'].error_type == "interrupted"
        assert tracker.state.episodes['ep2'].status == EpisodeStatus.FAILED
        
        # Completed should remain unchanged
        assert tracker.state.episodes['ep3'].status == EpisodeStatus.COMPLETED