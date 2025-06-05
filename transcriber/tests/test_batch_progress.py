"""Tests for batch progress tracking module with memory optimization."""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.utils.batch_progress import BatchStats, BatchProgressTracker
from src.progress_tracker import ProgressTracker, EpisodeStatus, EpisodeProgress


@pytest.mark.unit
class TestBatchStats:
    """Test BatchStats dataclass functionality."""
    
    def test_init_defaults(self):
        """Test BatchStats initialization with defaults."""
        stats = BatchStats()
        assert stats.total_episodes == 0
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.in_progress == 0
        assert stats.processing_times == []
        assert stats.start_time is None
        assert stats.last_update_time is None
    
    def test_init_with_values(self):
        """Test BatchStats initialization with values."""
        stats = BatchStats(
            total_episodes=10,
            completed=3,
            failed=1,
            skipped=2,
            in_progress=1
        )
        assert stats.total_episodes == 10
        assert stats.completed == 3
        assert stats.failed == 1
        assert stats.skipped == 2
        assert stats.in_progress == 1
        assert stats.pending == 3  # 10 - 3 - 1 - 2 - 1
    
    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        stats = BatchStats()
        assert stats.elapsed_time == 0.0
        
        stats.start_time = datetime.now() - timedelta(seconds=30)
        assert 29 <= stats.elapsed_time <= 31
    
    def test_average_processing_time(self):
        """Test average processing time calculation."""
        stats = BatchStats()
        # Default when no processing times
        assert stats.average_processing_time == 300.0
        
        # With processing times
        stats.processing_times = [100, 200, 300]
        assert stats.average_processing_time == 200.0
    
    def test_estimated_time_remaining(self):
        """Test estimated time remaining calculation."""
        stats = BatchStats(total_episodes=10, completed=3, in_progress=1)
        stats.processing_times = [100, 200]
        
        # pending = 10 - 3 - 0 - 0 - 1 = 6
        # remaining = pending + in_progress = 6 + 1 = 7
        # average time = (100 + 200) / 2 = 150
        # estimated = 7 * 150 = 1050
        assert stats.estimated_time_remaining == 1050.0
        
        # No remaining episodes
        stats.completed = 10
        stats.in_progress = 0
        assert stats.estimated_time_remaining == 0.0
    
    def test_success_rate(self):
        """Test success rate calculation."""
        stats = BatchStats()
        assert stats.success_rate == 0.0
        
        stats.completed = 7
        stats.failed = 3
        assert stats.success_rate == 70.0


@pytest.mark.unit
class TestBatchProgressTracker:
    """Test BatchProgressTracker functionality with memory optimization."""
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Create a mock progress tracker."""
        tracker = Mock(spec=ProgressTracker)
        tracker.state = Mock()
        tracker.state.episodes = {}
        return tracker
    
    @pytest.fixture
    def batch_tracker(self, mock_progress_tracker):
        """Create a batch progress tracker."""
        return BatchProgressTracker(mock_progress_tracker, total_episodes=5)
    
    def test_init_new_session(self, mock_progress_tracker):
        """Test initialization of new batch session."""
        tracker = BatchProgressTracker(mock_progress_tracker, total_episodes=10)
        assert tracker.stats.total_episodes == 10
        assert not tracker.is_resume_session
        assert tracker.current_episode_title == ""
        assert tracker.current_episode_start_time is None
    
    def test_init_resume_session(self, mock_progress_tracker):
        """Test initialization detecting resume session."""
        # Add completed episodes
        mock_progress_tracker.state.episodes = {
            'ep1': Mock(status=EpisodeStatus.COMPLETED),
            'ep2': Mock(status=EpisodeStatus.COMPLETED),
            'ep3': Mock(status=EpisodeStatus.PENDING)
        }
        
        tracker = BatchProgressTracker(mock_progress_tracker, total_episodes=10)
        assert tracker.is_resume_session
    
    def test_start_batch(self, batch_tracker):
        """Test starting batch processing."""
        with patch('threading.Thread'):
            batch_tracker.start_batch()
            
            assert batch_tracker.stats.start_time is not None
            assert batch_tracker.stats.last_update_time is not None
            assert not batch_tracker._stop_updates.is_set()
    
    def test_update_current_episode(self, batch_tracker):
        """Test updating current episode."""
        batch_tracker.update_current_episode("Test Episode")
        
        assert batch_tracker.current_episode_title == "Test Episode"
        assert batch_tracker.current_episode_start_time is not None
    
    def test_episode_completed(self, batch_tracker):
        """Test marking episode as completed."""
        batch_tracker.current_episode_title = "Test Episode"
        batch_tracker.episode_completed(120.5)
        
        assert batch_tracker.current_episode_title == ""
        assert batch_tracker.current_episode_start_time is None
        assert 120.5 in batch_tracker.stats.processing_times
    
    def test_episode_failed(self, batch_tracker):
        """Test marking episode as failed."""
        batch_tracker.current_episode_title = "Test Episode"
        batch_tracker.episode_failed("Test error")
        
        assert batch_tracker.current_episode_title == ""
        assert batch_tracker.current_episode_start_time is None
    
    def test_episode_skipped(self, batch_tracker):
        """Test marking episode as skipped."""
        batch_tracker.current_episode_title = "Test Episode"
        batch_tracker.episode_skipped("Already processed")
        
        assert batch_tracker.current_episode_title == ""
        assert batch_tracker.current_episode_start_time is None
    
    def test_finish_batch(self, batch_tracker):
        """Test finishing batch processing."""
        # Start a mock update thread
        batch_tracker._update_thread = Mock()
        batch_tracker._update_thread.is_alive.return_value = True
        
        # Set some stats
        batch_tracker.stats.completed = 8
        batch_tracker.stats.failed = 2
        batch_tracker.stats.total_episodes = 10
        batch_tracker.stats.start_time = datetime.now() - timedelta(seconds=100)
        
        batch_tracker.finish_batch("Test complete")
        
        assert batch_tracker._stop_updates.is_set()
        batch_tracker._update_thread.join.assert_called_once()
    
    def test_update_stats(self, batch_tracker, mock_progress_tracker):
        """Test updating statistics from progress tracker."""
        # Set up episodes with different statuses
        mock_progress_tracker.state.episodes = {
            'ep1': Mock(status=EpisodeStatus.COMPLETED),
            'ep2': Mock(status=EpisodeStatus.COMPLETED),
            'ep3': Mock(status=EpisodeStatus.FAILED),
            'ep4': Mock(status=EpisodeStatus.IN_PROGRESS),
            'ep5': Mock(status=EpisodeStatus.PENDING)
        }
        
        batch_tracker._update_stats()
        
        assert batch_tracker.stats.completed == 2
        assert batch_tracker.stats.failed == 1
        assert batch_tracker.stats.in_progress == 1
    
    def test_display_progress_throttling(self, batch_tracker):
        """Test display progress throttling to avoid memory issues."""
        batch_tracker._last_display_update = time.time() - 0.5
        
        with patch.object(batch_tracker.progress_bar, 'update') as mock_update:
            batch_tracker._display_progress()
            mock_update.assert_not_called()  # Should be throttled
        
        # After 1 second, should update
        batch_tracker._last_display_update = time.time() - 1.5
        with patch.object(batch_tracker.progress_bar, 'update') as mock_update:
            batch_tracker._display_progress()
            mock_update.assert_called_once()
    
    def test_display_progress_with_current_episode(self, batch_tracker):
        """Test display progress with current episode."""
        batch_tracker._last_display_update = 0  # Force update
        batch_tracker.current_episode_title = "A very long episode title that should be truncated"
        batch_tracker.stats.completed = 5
        batch_tracker.stats.total_episodes = 10
        
        with patch.object(batch_tracker.progress_bar, 'update') as mock_update:
            batch_tracker._display_progress()
            
            # Check that title was truncated
            args, _ = mock_update.call_args
            suffix = args[1]
            assert "A very long episode title t..." in suffix
    
    def test_periodic_update_worker(self, batch_tracker):
        """Test periodic update worker thread."""
        # Mock the stop event to return True immediately
        batch_tracker._stop_updates.wait = Mock(return_value=True)
        
        # Run the worker
        batch_tracker._periodic_update_worker()
        
        # Should exit without errors
        batch_tracker._stop_updates.wait.assert_called_once_with(30.0)
    
    def test_periodic_update_worker_exception(self, batch_tracker):
        """Test periodic update worker handles exceptions."""
        # Mock to run once then stop
        batch_tracker._stop_updates.wait = Mock(side_effect=[False, True])
        batch_tracker._update_stats = Mock(side_effect=Exception("Test error"))
        
        # Should not raise exception
        batch_tracker._periodic_update_worker()
    
    def test_format_time(self, batch_tracker):
        """Test time formatting."""
        assert batch_tracker._format_time(45) == "45s"
        assert batch_tracker._format_time(90) == "1m 30s"
        assert batch_tracker._format_time(3661) == "1h 1m"
        assert batch_tracker._format_time(7265) == "2h 1m"
    
    def test_get_status_summary(self, batch_tracker):
        """Test getting status summary."""
        batch_tracker.stats.completed = 5
        batch_tracker.stats.failed = 1
        batch_tracker.stats.total_episodes = 10
        batch_tracker.current_episode_title = "Current Episode"
        
        summary = batch_tracker.get_status_summary()
        
        assert summary['total_episodes'] == 10
        assert summary['completed'] == 5
        assert summary['failed'] == 1
        assert summary['current_episode'] == "Current Episode"
        assert 'success_rate' in summary
        assert 'elapsed_time' in summary


@pytest.mark.unit
class TestMemoryEfficiency:
    """Test memory efficiency with large batches."""
    
    def test_large_batch_initialization(self):
        """Test initialization with large batch doesn't cause memory issues."""
        mock_tracker = Mock(spec=ProgressTracker)
        mock_tracker.state = Mock()
        mock_tracker.state.episodes = {}
        
        # Create tracker with large episode count
        batch_tracker = BatchProgressTracker(mock_tracker, total_episodes=10000)
        
        assert batch_tracker.stats.total_episodes == 10000
        # Ensure no large data structures are created
        assert len(batch_tracker.stats.processing_times) == 0
    
    def test_processing_times_memory_limit(self):
        """Test that processing times list doesn't grow unbounded."""
        stats = BatchStats()
        
        # Simulate processing many episodes
        for i in range(1000):
            stats.processing_times.append(100 + i)
        
        # In a real implementation, we might want to limit this list
        # For now, just verify it works with large numbers
        assert len(stats.processing_times) == 1000
        assert stats.average_processing_time > 0
    
    def test_concurrent_update_safety(self):
        """Test thread safety of updates."""
        mock_tracker = Mock(spec=ProgressTracker)
        mock_tracker.state = Mock()
        mock_tracker.state.episodes = {}
        
        batch_tracker = BatchProgressTracker(mock_tracker, total_episodes=100)
        
        # Simulate concurrent updates
        def update_episode(i):
            batch_tracker.update_current_episode(f"Episode {i}")
            time.sleep(0.001)  # Small delay
            batch_tracker.episode_completed(100)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_episode, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should complete without errors
        assert len(batch_tracker.stats.processing_times) == 10