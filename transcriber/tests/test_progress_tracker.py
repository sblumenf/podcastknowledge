"""Comprehensive tests for ProgressTracker."""

import os
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import pytest

from src.progress_tracker import ProgressTracker, EpisodeStatus


class TestProgressTracker:
    """Test suite for ProgressTracker class."""
    
    @pytest.fixture
    def temp_tracking_file(self, tmp_path):
        """Create a temporary tracking file path."""
        return str(tmp_path / "test_progress.json")
    
    @pytest.fixture
    def tracker(self, temp_tracking_file):
        """Create a ProgressTracker instance with temporary file."""
        return ProgressTracker(temp_tracking_file)
    
    def test_init_creates_data_directory(self, tmp_path):
        """Test that initialization creates the data directory if it doesn't exist."""
        tracking_path = str(tmp_path / "new_dir" / "progress.json")
        tracker = ProgressTracker(tracking_path)
        
        assert Path(tracking_path).parent.exists()
    
    def test_load_progress_nonexistent_file(self, tracker):
        """Test loading progress when file doesn't exist creates empty dict."""
        progress = tracker.load_progress()
        
        assert progress == {}
        assert tracker._progress_data == {}
    
    def test_load_progress_existing_file(self, temp_tracking_file):
        """Test loading progress from existing file."""
        # Create test data
        test_data = {
            "Test Podcast": ["Episode 1", "Episode 2"],
            "Another Podcast": ["First Episode"]
        }
        
        with open(temp_tracking_file, 'w') as f:
            json.dump(test_data, f)
        
        tracker = ProgressTracker(temp_tracking_file)
        progress = tracker.load_progress()
        
        assert progress == test_data
        assert tracker._progress_data == test_data
    
    def test_load_progress_corrupted_file(self, temp_tracking_file):
        """Test loading progress from corrupted JSON file."""
        # Write invalid JSON
        with open(temp_tracking_file, 'w') as f:
            f.write("{ invalid json")
        
        tracker = ProgressTracker(temp_tracking_file)
        progress = tracker.load_progress()
        
        assert progress == {}
        assert tracker._progress_data == {}
    
    def test_save_progress(self, tracker, temp_tracking_file):
        """Test saving progress data to file."""
        test_data = {
            "My Podcast": ["Episode A", "Episode B"]
        }
        
        tracker.save_progress(test_data)
        
        # Verify file contents
        with open(temp_tracking_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data == test_data
        assert tracker._progress_data == test_data
    
    def test_save_progress_atomic_operation(self, tracker, temp_tracking_file):
        """Test that save uses atomic file operations."""
        test_data = {"Podcast": ["Episode"]}
        
        with patch('os.replace') as mock_replace:
            tracker.save_progress(test_data)
            
            # Verify atomic operation was used
            mock_replace.assert_called_once()
            temp_file = mock_replace.call_args[0][0]
            assert temp_file == f"{temp_tracking_file}.tmp"
            assert mock_replace.call_args[0][1] == temp_tracking_file
    
    def test_save_progress_io_error(self, tracker, temp_tracking_file):
        """Test save handles IO errors gracefully."""
        test_data = {"Podcast": ["Episode"]}
        
        with patch('builtins.open', side_effect=IOError("Disk full")):
            # Should not raise exception
            tracker.save_progress(test_data)
    
    def test_is_episode_transcribed(self, tracker):
        """Test checking if episode is transcribed."""
        # Set up test data
        tracker._progress_data = {
            "My Podcast": ["Episode 1", "Episode 2"],
            "Other Podcast": []
        }
        
        assert tracker.is_episode_transcribed("My Podcast", "Episode 1") is True
        assert tracker.is_episode_transcribed("My Podcast", "Episode 3") is False
        assert tracker.is_episode_transcribed("Other Podcast", "Episode 1") is False
        assert tracker.is_episode_transcribed("Unknown Podcast", "Episode 1") is False
    
    def test_mark_episode_transcribed(self, tracker, temp_tracking_file):
        """Test marking an episode as transcribed."""
        # Mark first episode
        tracker.mark_episode_transcribed("Test Podcast", "Episode 1", "2024-01-01")
        
        assert tracker.is_episode_transcribed("Test Podcast", "Episode 1") is True
        
        # Verify it was saved to file
        with open(temp_tracking_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == {"Test Podcast": ["Episode 1"]}
        
        # Mark another episode
        tracker.mark_episode_transcribed("Test Podcast", "Episode 2", "2024-01-02")
        
        assert tracker.is_episode_transcribed("Test Podcast", "Episode 2") is True
        assert len(tracker._progress_data["Test Podcast"]) == 2
    
    def test_mark_episode_transcribed_no_duplicates(self, tracker):
        """Test that marking same episode twice doesn't create duplicates."""
        tracker.mark_episode_transcribed("Podcast", "Episode", "2024-01-01")
        tracker.mark_episode_transcribed("Podcast", "Episode", "2024-01-01")
        
        assert len(tracker._progress_data["Podcast"]) == 1
    
    def test_get_transcribed_episodes(self, tracker):
        """Test getting list of transcribed episodes."""
        test_episodes = ["Episode 1", "Episode 2", "Episode 3"]
        tracker._progress_data = {"My Podcast": test_episodes}
        
        episodes = tracker.get_transcribed_episodes("My Podcast")
        
        assert episodes == test_episodes
        assert episodes is not tracker._progress_data["My Podcast"]  # Should be a copy
        
        # Test non-existent podcast
        assert tracker.get_transcribed_episodes("Unknown") == []
    
    def test_get_all_podcasts(self, tracker):
        """Test getting list of all podcasts."""
        tracker._progress_data = {
            "Podcast A": ["Episode 1"],
            "Podcast B": ["Episode 1", "Episode 2"],
            "Podcast C": []
        }
        
        podcasts = tracker.get_all_podcasts()
        
        assert set(podcasts) == {"Podcast A", "Podcast B", "Podcast C"}
    
    def test_get_total_transcribed_count(self, tracker):
        """Test getting total count of transcribed episodes."""
        tracker._progress_data = {
            "Podcast A": ["Ep1", "Ep2", "Ep3"],
            "Podcast B": ["Episode 1", "Episode 2"],
            "Podcast C": []
        }
        
        assert tracker.get_total_transcribed_count() == 5
    
    def test_remove_episode(self, tracker, temp_tracking_file):
        """Test removing an episode from transcribed list."""
        tracker._progress_data = {
            "My Podcast": ["Episode 1", "Episode 2"],
            "Other Podcast": ["Only Episode"]
        }
        
        # Remove existing episode
        assert tracker.remove_episode("My Podcast", "Episode 1") is True
        assert "Episode 1" not in tracker._progress_data["My Podcast"]
        assert len(tracker._progress_data["My Podcast"]) == 1
        
        # Remove non-existent episode
        assert tracker.remove_episode("My Podcast", "Episode 99") is False
        
        # Remove last episode should remove podcast
        assert tracker.remove_episode("Other Podcast", "Only Episode") is True
        assert "Other Podcast" not in tracker._progress_data
    
    def test_clear_podcast(self, tracker, temp_tracking_file):
        """Test clearing all episodes for a podcast."""
        tracker._progress_data = {
            "My Podcast": ["Episode 1", "Episode 2", "Episode 3"],
            "Other Podcast": ["Episode A"]
        }
        
        # Clear existing podcast
        assert tracker.clear_podcast("My Podcast") is True
        assert "My Podcast" not in tracker._progress_data
        assert "Other Podcast" in tracker._progress_data
        
        # Clear non-existent podcast
        assert tracker.clear_podcast("Unknown Podcast") is False
    
    def test_thread_safety(self, tracker):
        """Test that operations are thread-safe."""
        episodes_to_add = 100
        threads = []
        
        def add_episodes(start, end):
            for i in range(start, end):
                tracker.mark_episode_transcribed("Podcast", f"Episode {i}", "2024-01-01")
        
        # Create multiple threads adding episodes
        for i in range(0, episodes_to_add, 20):
            thread = threading.Thread(target=add_episodes, args=(i, i + 20))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all episodes were added without corruption
        episodes = tracker.get_transcribed_episodes("Podcast")
        assert len(episodes) == episodes_to_add
        assert len(set(episodes)) == episodes_to_add  # No duplicates
    
    def test_concurrent_save_operations(self, tracker, temp_tracking_file):
        """Test concurrent save operations don't corrupt file."""
        def save_operation(podcast_name):
            for i in range(10):
                tracker.mark_episode_transcribed(podcast_name, f"Episode {i}", "2024-01-01")
                time.sleep(0.001)  # Small delay to increase chance of conflict
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=save_operation, args=(f"Podcast {i}",))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Reload from file to verify integrity
        new_tracker = ProgressTracker(temp_tracking_file)
        progress = new_tracker.load_progress()
        
        # Verify all podcasts and episodes are present
        assert len(progress) == 5
        for i in range(5):
            assert f"Podcast {i}" in progress
            assert len(progress[f"Podcast {i}"]) == 10
    
    def test_unicode_handling(self, tracker, temp_tracking_file):
        """Test handling of unicode characters in podcast/episode names."""
        unicode_podcast = "Podcast with émojis 🎙️"
        unicode_episode = "Episode über Python 🐍"
        
        tracker.mark_episode_transcribed(unicode_podcast, unicode_episode, "2024-01-01")
        
        # Verify it works
        assert tracker.is_episode_transcribed(unicode_podcast, unicode_episode) is True
        
        # Verify file is readable
        new_tracker = ProgressTracker(temp_tracking_file)
        assert new_tracker.is_episode_transcribed(unicode_podcast, unicode_episode) is True
    
    def test_large_dataset_performance(self, tracker):
        """Test performance with large number of episodes."""
        import time
        
        # Add many episodes
        start_time = time.time()
        for i in range(100):
            podcast_name = f"Podcast {i % 10}"
            episode_name = f"Episode {i}"
            tracker.mark_episode_transcribed(podcast_name, episode_name, "2024-01-01")
        
        add_time = time.time() - start_time
        
        # Check lookup performance
        start_time = time.time()
        for i in range(100):
            podcast_name = f"Podcast {i % 10}"
            episode_name = f"Episode {i}"
            assert tracker.is_episode_transcribed(podcast_name, episode_name) is True
        
        lookup_time = time.time() - start_time
        
        # Performance should be reasonable
        assert add_time < 5.0  # Adding 100 episodes should take less than 5 seconds
        assert lookup_time < 0.1  # Lookups should be very fast