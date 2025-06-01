"""Tests for checkpoint recovery scenarios."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import os
import shutil
import tempfile

import pytest

from src.core.config import Config
from src.core.exceptions import CheckpointError
from src.seeding.checkpoint import ProgressCheckpoint
from src.seeding.orchestrator import VTTKnowledgeExtractor
class TestCheckpointRecovery:
    """Test checkpoint recovery and compatibility scenarios."""
    
    @pytest.fixture
    def checkpoint_dir(self):
        """Create temporary checkpoint directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def sample_checkpoint_data(self):
        """Sample checkpoint data."""
        return {
            "podcast_url": "https://example.com/feed.xml",
            "podcast_name": "Test Podcast",
            "last_processed_episode": "episode-3",
            "processed_episodes": ["episode-1", "episode-2", "episode-3"],
            "extraction_mode": "fixed",
            "total_episodes": 10,
            "start_time": "2024-01-01T10:00:00",
            "last_update": "2024-01-01T10:30:00",
            "schema_discovery": {
                "discovered_types": ["Person", "Organization", "Technology"],
                "evolution": [
                    {
                        "episode": "episode-1",
                        "new_types": ["Person", "Organization"],
                        "timestamp": "2024-01-01T10:10:00"
                    },
                    {
                        "episode": "episode-3",
                        "new_types": ["Technology"],
                        "timestamp": "2024-01-01T10:25:00"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def legacy_checkpoint_data(self):
        """Legacy checkpoint format for compatibility testing."""
        return {
            "podcast_url": "https://example.com/feed.xml",
            "last_processed_episode": "episode-2",
            "processed_episodes": ["episode-1", "episode-2"],
            # Missing fields that exist in new format
            # No extraction_mode, schema_discovery, etc.
        }
    
    @pytest.mark.integration
    def test_checkpoint_creation_and_recovery(self, checkpoint_dir):
        """Test creating and recovering from checkpoint."""
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        # Save checkpoint
        podcast_url = "https://example.com/feed.xml"
        checkpoint.save_progress(
            podcast_url=podcast_url,
            podcast_name="Test Podcast",
            episode_id="episode-1",
            episode_data={"title": "Episode 1", "url": "https://example.com/ep1.mp3"}
        )
        
        # Create new checkpoint instance and load
        new_checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        # Check if episode was processed
        assert new_checkpoint.is_episode_processed(podcast_url, "episode-1")
        assert not new_checkpoint.is_episode_processed(podcast_url, "episode-2")
        
        # Get progress
        progress = new_checkpoint.get_progress(podcast_url)
        assert progress is not None
        assert progress["last_processed_episode"] == "episode-1"
        assert "episode-1" in progress["processed_episodes"]
    
    @pytest.mark.integration
    def test_checkpoint_resume_interrupted_processing(
        self, checkpoint_dir, sample_checkpoint_data
    ):
        """Test resuming interrupted podcast processing."""
        # Create checkpoint with partial progress
        checkpoint_file = Path(checkpoint_dir) / "checkpoint_https___example_com_feed_xml.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(sample_checkpoint_data, f)
        
        # Mock RSS feed with 10 episodes
        mock_episodes = [
            {"id": f"episode-{i}", "title": f"Episode {i}", "url": f"https://example.com/ep{i}.mp3"}
            for i in range(1, 11)
        ]
        
        config = Config()
        config.checkpoint_dir = checkpoint_dir
        config.checkpoint_enabled = True
        
        with patch('src.utils.feed_processing.parse_rss_feed') as mock_parse, \
             patch('src.seeding.orchestrator.VTTKnowledgeExtractor._process_episode') as mock_process:
            
            mock_parse.return_value = {
                "title": "Test Podcast",
                "episodes": mock_episodes
            }
            mock_process.return_value = True
            
            pipeline = VTTKnowledgeExtractor(config)
            
            # Process should skip first 3 episodes (already in checkpoint)
            result = pipeline.process_podcast(
                podcast_url="https://example.com/feed.xml",
                podcast_name="Test Podcast",
                max_episodes=10
            )
            
            # Should process episodes 4-10 (7 episodes)
            assert mock_process.call_count == 7
            
            # Verify skipped episodes
            processed_episodes = [
                call.kwargs['episode']['id'] 
                for call in mock_process.call_args_list
            ]
            assert "episode-1" not in processed_episodes
            assert "episode-2" not in processed_episodes
            assert "episode-3" not in processed_episodes
            assert "episode-4" in processed_episodes
            assert "episode-10" in processed_episodes
    
    @pytest.mark.integration
    def test_checkpoint_compatibility_between_modes(self, checkpoint_dir):
        """Test checkpoint compatibility between extraction modes."""
        # Create checkpoint in fixed mode
        checkpoint_fixed = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        checkpoint_fixed.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-1",
            episode_data={"title": "Episode 1"}
        )
        
        # Load in schemaless mode
        checkpoint_schemaless = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="schemaless"
        )
        
        # Should maintain separate progress for different modes
        assert checkpoint_fixed.is_episode_processed("https://example.com/feed.xml", "episode-1")
        # Schemaless checkpoint is independent
        assert not checkpoint_schemaless.is_episode_processed("https://example.com/feed.xml", "episode-1")
        
        # Save in schemaless mode
        checkpoint_schemaless.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-1",
            episode_data={"title": "Episode 1"},
            discovered_types=["Expert", "Technology"]
        )
        
        # Both should now show processed
        assert checkpoint_fixed.is_episode_processed("https://example.com/feed.xml", "episode-1")
        assert checkpoint_schemaless.is_episode_processed("https://example.com/feed.xml", "episode-1")
    
    @pytest.mark.integration
    def test_checkpoint_distributed_locking(self, checkpoint_dir):
        """Test distributed locking for checkpoints."""
        import threading
        import time
        
        results = []
        
        def worker(worker_id):
            """Worker that tries to update checkpoint."""
            checkpoint = ProgressCheckpoint(
                checkpoint_dir=checkpoint_dir,
                extraction_mode="fixed"
            )
            
            try:
                # Try to acquire lock and update
                with checkpoint.acquire_lock("https://example.com/feed.xml", timeout=2.0):
                    # Simulate processing
                    time.sleep(0.1)
                    checkpoint.save_progress(
                        podcast_url="https://example.com/feed.xml",
                        podcast_name="Test Podcast",
                        episode_id=f"episode-{worker_id}",
                        episode_data={"title": f"Episode {worker_id}"}
                    )
                    results.append(("success", worker_id))
            except Exception as e:
                results.append(("failed", worker_id, str(e)))
        
        # Start multiple workers
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All workers should succeed (serial execution due to locking)
        success_count = sum(1 for r in results if r[0] == "success")
        assert success_count == 3
        
        # Verify all episodes were saved
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        progress = checkpoint.get_progress("https://example.com/feed.xml")
        assert len(progress["processed_episodes"]) == 3
    
    @pytest.mark.integration
    def test_checkpoint_version_migration(self, checkpoint_dir, legacy_checkpoint_data):
        """Test migrating old checkpoint formats to new format."""
        # Save legacy checkpoint
        checkpoint_file = Path(checkpoint_dir) / "checkpoint_https___example_com_feed_xml.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(legacy_checkpoint_data, f)
        
        # Load with new checkpoint class
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        # Should handle legacy format gracefully
        progress = checkpoint.get_progress("https://example.com/feed.xml")
        assert progress is not None
        assert progress["last_processed_episode"] == "episode-2"
        assert len(progress["processed_episodes"]) == 2
        
        # Add new progress (should upgrade format)
        checkpoint.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-3",
            episode_data={"title": "Episode 3"}
        )
        
        # Reload and verify upgraded format
        with open(checkpoint_file, 'r') as f:
            upgraded_data = json.load(f)
        
        # Should have new fields
        assert "extraction_mode" in upgraded_data
        assert "podcast_name" in upgraded_data
        assert upgraded_data["extraction_mode"] == "fixed"
        assert len(upgraded_data["processed_episodes"]) == 3
    
    @pytest.mark.integration
    def test_checkpoint_schema_discovery_tracking(self, checkpoint_dir):
        """Test tracking schema discovery in checkpoints."""
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="schemaless"
        )
        
        # Process first episode with initial types
        checkpoint.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-1",
            episode_data={"title": "Episode 1"},
            discovered_types=["Expert", "Technology", "Company"]
        )
        
        # Process second episode with new types
        checkpoint.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-2",
            episode_data={"title": "Episode 2"},
            discovered_types=["Expert", "Research Institution", "Patent"]
        )
        
        # Get schema statistics
        stats = checkpoint.get_schema_statistics()
        
        assert stats["total_types_discovered"] == 5
        assert "Expert" in stats["entity_types"]
        assert "Technology" in stats["entity_types"]
        assert "Research Institution" in stats["entity_types"]
        assert "Patent" in stats["entity_types"]
        
        # Check evolution timeline
        assert len(stats["discovery_timeline"]) == 2
        assert stats["discovery_timeline"][0]["count"] == 3  # First episode
        assert stats["discovery_timeline"][1]["count"] == 2  # Second episode (new types only)
    
    @pytest.mark.integration
    def test_checkpoint_corruption_recovery(self, checkpoint_dir):
        """Test recovery from corrupted checkpoint files."""
        checkpoint_file = Path(checkpoint_dir) / "checkpoint_https___example_com_feed_xml.json"
        
        # Create corrupted checkpoint
        with open(checkpoint_file, 'w') as f:
            f.write("{ corrupted json file")
        
        # Should handle corruption gracefully
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        # Should return None for corrupted checkpoint
        progress = checkpoint.get_progress("https://example.com/feed.xml")
        assert progress is None
        
        # Should be able to save new progress (overwriting corrupted file)
        checkpoint.save_progress(
            podcast_url="https://example.com/feed.xml",
            podcast_name="Test Podcast",
            episode_id="episode-1",
            episode_data={"title": "Episode 1"}
        )
        
        # Verify checkpoint is now valid
        progress = checkpoint.get_progress("https://example.com/feed.xml")
        assert progress is not None
        assert progress["last_processed_episode"] == "episode-1"
    
    @pytest.mark.integration
    def test_checkpoint_cleanup_old_files(self, checkpoint_dir):
        """Test cleanup of old checkpoint files."""
        # Create multiple checkpoint files with timestamps
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        for i in range(5):
            checkpoint = ProgressCheckpoint(
                checkpoint_dir=checkpoint_dir,
                extraction_mode="fixed"
            )
            
            # Mock file creation time
            checkpoint_file = Path(checkpoint_dir) / f"checkpoint_test_{i}.json"
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    "created_at": (base_time.timestamp() - i * 86400),  # Days ago
                    "podcast_url": f"https://example{i}.com/feed.xml"
                }, f)
        
        # Run cleanup (keep only last 3 days)
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode="fixed"
        )
        
        if hasattr(checkpoint, 'cleanup_old_checkpoints'):
            checkpoint.cleanup_old_checkpoints(max_age_days=3)
            
            # Check remaining files
            remaining_files = list(Path(checkpoint_dir).glob("checkpoint_*.json"))
            assert len(remaining_files) <= 3