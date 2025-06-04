"""Integration tests for checkpoint recovery functionality."""

import pytest
import asyncio
import json
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock

from src.checkpoint_recovery import CheckpointManager, EpisodeCheckpoint
from src.orchestrator import TranscriptionOrchestrator
from src.feed_parser import Episode, PodcastMetadata
from src.config import Config


@pytest.mark.integration
@pytest.mark.timeout(90)  # 1.5 minute timeout for checkpoint recovery tests
class TestCheckpointRecoveryIntegration:
    """Test checkpoint recovery in real-world scenarios."""
    
    @pytest.fixture
    def mock_episode(self):
        """Create a mock episode for testing."""
        return Episode(
            title="Test Episode for Checkpoint",
            audio_url="https://example.com/checkpoint-test.mp3",
            guid="checkpoint-test-guid-001",
            description="Testing checkpoint recovery",
            published_date=datetime(2025, 6, 1, 10, 0, 0),
            duration="45:00",
            episode_number=1
        )
    
    @pytest.fixture
    def mock_podcast_metadata(self):
        """Create mock podcast metadata."""
        return PodcastMetadata(
            title="Checkpoint Test Podcast",
            description="Testing checkpoint recovery",
            link="https://example.com/podcast",
            author="Test Author"
        )
    
    @pytest.mark.asyncio
    async def test_checkpoint_recovery_mid_transcription(self, tmp_path, mock_episode, mock_podcast_metadata):
        """Test recovery when interrupted during transcription."""
        # Setup directories
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        checkpoint_dir = data_dir / "checkpoints"
        checkpoint_dir.mkdir()
        
        # Create config
        config_file = tmp_path / "config.yaml"
        config_content = {
            "output": {
                "default_dir": str(data_dir / "transcripts")
            },
            "processing": {
                "checkpoint_enabled": True
            }
        }
        
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_content, f)
        
        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager(data_dir)
        
        # Simulate starting transcription
        episode_data = {
            'guid': mock_episode.guid,
            'title': mock_episode.title,
            'audio_url': mock_episode.audio_url,
            'podcast_name': mock_podcast_metadata.title,
            'author': mock_podcast_metadata.author,
            'duration': mock_episode.duration
        }
        
        checkpoint_manager.start_episode(
            episode_id=mock_episode.guid,
            audio_url=mock_episode.audio_url,
            title=mock_episode.title,
            metadata=episode_data
        )
        
        # Simulate partial transcription
        partial_transcript = """WEBVTT

NOTE
Podcast: Checkpoint Test Podcast
Episode: Test Episode for Checkpoint
Date: 2025-06-01

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Welcome to our test episode.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_1>This transcription will be interrupted..."""
        
        # Save partial transcript
        temp_file = data_dir / ".temp" / "partial_transcript.vtt"
        temp_file.parent.mkdir(exist_ok=True)
        temp_file.write_text(partial_transcript)
        
        checkpoint_manager.update_stage('transcription', str(temp_file))
        # Update metadata in the checkpoint
        checkpoint_manager.current_checkpoint.metadata.update({
            'last_timestamp': '00:00:10.000',
            'segments_processed': 2
        })
        checkpoint_manager._save_checkpoint()
        
        # Verify checkpoint exists
        assert checkpoint_manager.can_resume()
        resume_info = checkpoint_manager.get_resume_info()
        assert resume_info['episode_title'] == mock_episode.title
        assert resume_info['current_stage'] == 'transcription'
        assert 'transcription' in resume_info['temp_files_available']
        
        # Simulate recovery - load existing checkpoint
        new_checkpoint_manager = CheckpointManager(data_dir)
        assert new_checkpoint_manager.can_resume()
        
        # Get saved state
        saved_state = new_checkpoint_manager.current_checkpoint
        assert saved_state.metadata['last_timestamp'] == '00:00:10.000'
        assert saved_state.metadata['segments_processed'] == 2
        
        # Verify partial transcript can be loaded
        partial_file = saved_state.temporary_files['transcription']
        assert Path(partial_file).exists()
        loaded_transcript = Path(partial_file).read_text()
        assert "This transcription will be interrupted" in loaded_transcript
        
        # Continue transcription
        continuation = """
00:00:10.000 --> 00:00:15.000
<v SPEAKER_2>Yes, but we can recover from checkpoints.

00:00:15.000 --> 00:00:20.000
<v SPEAKER_1>That's the beauty of the system."""
        
        # Append to transcript
        full_transcript = loaded_transcript + continuation
        
        # Complete transcription
        new_checkpoint_manager.complete_stage('transcription')
        new_checkpoint_manager.update_stage('speaker_identification')
        
        # Simulate speaker identification
        speaker_mapping = {
            "SPEAKER_1": "Test Host",
            "SPEAKER_2": "Guest Speaker"
        }
        
        new_checkpoint_manager.complete_stage('speaker_identification')
        new_checkpoint_manager.update_stage('vtt_generation')
        
        # Complete process
        output_file = data_dir / "transcripts" / "test_episode.vtt"
        output_file.parent.mkdir(exist_ok=True)
        output_file.write_text(full_transcript.replace("SPEAKER_1", "Test Host").replace("SPEAKER_2", "Guest Speaker"))
        
        new_checkpoint_manager.mark_completed(str(output_file))
        
        # Verify checkpoint is cleaned up
        assert not new_checkpoint_manager.can_resume()
        checkpoint_file = checkpoint_dir / "active_checkpoint.json"
        assert not checkpoint_file.exists()
        
        # Verify output file has complete content
        final_content = output_file.read_text()
        assert "Welcome to our test episode" in final_content
        assert "we can recover from checkpoints" in final_content
        assert "Test Host" in final_content
        assert "Guest Speaker" in final_content
    
    @pytest.mark.asyncio
    async def test_multiple_interruptions_and_recovery(self, tmp_path):
        """Test handling multiple interruptions during processing."""
        data_dir = tmp_path / "data"
        checkpoint_manager = CheckpointManager(data_dir)
        
        # First interruption during transcription
        checkpoint_manager.start_episode(
            episode_id="multi-interrupt-001",
            audio_url="https://example.com/multi.mp3",
            title="Multi Interrupt Test",
            metadata={}
        )
        
        checkpoint_manager.update_stage('transcription')
        checkpoint_manager.current_checkpoint.metadata['progress'] = 0.3
        checkpoint_manager._save_checkpoint()
        
        # Verify state
        assert checkpoint_manager.current_checkpoint.status == 'transcription'
        
        # Second interruption during speaker identification
        checkpoint_manager.complete_stage('transcription')
        checkpoint_manager.update_stage('speaker_identification')
        checkpoint_manager.current_checkpoint.metadata['progress'] = 0.6
        checkpoint_manager._save_checkpoint()
        
        # Simulate crash and recovery
        new_manager = CheckpointManager(data_dir)
        assert new_manager.can_resume()
        assert new_manager.current_checkpoint.status == 'speaker_identification'
        assert new_manager.current_checkpoint.metadata['progress'] == 0.6
        
        # Third interruption during VTT generation
        new_manager.complete_stage('speaker_identification')
        new_manager.update_stage('vtt_generation')
        new_manager.current_checkpoint.metadata['progress'] = 0.9
        new_manager._save_checkpoint()
        
        # Final recovery and completion
        final_manager = CheckpointManager(data_dir)
        assert final_manager.can_resume()
        assert final_manager.current_checkpoint.status == 'vtt_generation'
        
        final_manager.mark_completed("output.vtt")
        assert not final_manager.can_resume()
    
    @pytest.mark.asyncio
    async def test_checkpoint_with_temp_file_cleanup(self, tmp_path):
        """Test that temporary files are properly cleaned up."""
        data_dir = tmp_path / "data"
        
        checkpoint_manager = CheckpointManager(data_dir)
        
        # Create checkpoint with temporary files
        checkpoint_manager.start_episode(
            episode_id="cleanup-test-001",
            audio_url="https://example.com/cleanup.mp3",
            title="Cleanup Test",
            metadata={}
        )
        
        # Use the checkpoint manager's temp directory
        temp_dir = checkpoint_manager.temp_dir
        
        # Create temporary files
        temp_files = {
            'audio': temp_dir / "temp_audio.mp3",
            'transcript': temp_dir / "temp_transcript.txt",
            'metadata': temp_dir / "temp_metadata.json"
        }
        
        for name, path in temp_files.items():
            path.write_text(f"Temporary {name} content")
            checkpoint_manager.current_checkpoint.temporary_files[name] = str(path)
        
        checkpoint_manager._save_checkpoint()
        
        # Verify files exist
        for path in temp_files.values():
            assert path.exists()
        
        # Save checkpoint reference before marking as failed
        checkpoint_ref = checkpoint_manager.current_checkpoint
        
        # Mark as failed (should preserve temp files)
        checkpoint_manager.mark_failed("Test error")
        
        # Files should still exist after failure
        for path in temp_files.values():
            assert path.exists()
        
        # Clean up temp files using the saved checkpoint reference
        checkpoint_manager._cleanup_temp_files(checkpoint_ref)
        
        # Verify checkpoint file is removed (already done by mark_failed)
        checkpoint_file = data_dir / "checkpoints" / "active_checkpoint.json"
        assert not checkpoint_file.exists()
        
        # Verify temp files are cleaned up
        for path in temp_files.values():
            assert not path.exists()
    
    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_protection(self, tmp_path):
        """Test that only one checkpoint can be active at a time."""
        data_dir = tmp_path / "data"
        
        # Create first checkpoint
        manager1 = CheckpointManager(data_dir)
        manager1.start_episode(
            episode_id="concurrent-001",
            audio_url="https://example.com/concurrent1.mp3",
            title="Concurrent Test 1",
            metadata={}
        )
        
        # Try to create second checkpoint
        manager2 = CheckpointManager(data_dir)
        with pytest.raises(Exception) as exc_info:
            manager2.start_episode(
                episode_id="concurrent-002",
                audio_url="https://example.com/concurrent2.mp3",
                title="Concurrent Test 2",
                metadata={}
            )
        
        assert "new episode started before previous completed" in str(exc_info.value).lower()
        
        # Verify first checkpoint is still active
        assert manager1.can_resume()
        assert manager1.current_checkpoint.episode_id == "concurrent-001"
    
    @pytest.mark.asyncio
    async def test_checkpoint_recovery_with_orchestrator(self, tmp_path, mock_episode):
        """Test checkpoint recovery through the orchestrator."""
        # Setup
        data_dir = tmp_path / "data"
        config_file = tmp_path / "config.yaml"
        
        config_content = {
            "output": {
                "default_dir": str(data_dir / "transcripts")
            },
            "processing": {
                "checkpoint_enabled": True
            }
        }
        
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_content, f)
        
        # Create a checkpoint simulating interrupted processing
        checkpoint_dir = data_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        checkpoint_data = {
            'episode_id': mock_episode.guid,
            'audio_url': mock_episode.audio_url,
            'title': mock_episode.title,
            'status': 'transcription',
            'stage_completed': [],
            'temporary_files': {},
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'metadata': {
                'podcast_name': 'Test Podcast',
                'attempt_count': 1
            }
        }
        
        checkpoint_file = checkpoint_dir / "active_checkpoint.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
        
        # Mock dependencies
        with patch.dict(os.environ, {'GEMINI_API_KEY_1': 'test_key'}):
            with patch('src.orchestrator.Config') as mock_config_cls:
                test_config = Config(config_file=str(config_file))
                mock_config_cls.return_value = test_config
                
                orchestrator = TranscriptionOrchestrator(
                    output_dir=Path(test_config.output.default_dir),
                    enable_checkpoint=True,
                    resume=True,
                    data_dir=data_dir
                )
                
                # Verify orchestrator recognizes the checkpoint
                assert orchestrator.checkpoint_manager.can_resume()
                
                # Mock successful completion
                with patch.object(orchestrator, '_process_episode') as mock_process:
                    mock_process.return_value = "success"
                    
                    # Simulate resume
                    resume_info = orchestrator.checkpoint_manager.get_resume_info()
                    assert resume_info['episode_title'] == mock_episode.title
                    
                    # Complete the checkpoint
                    orchestrator.checkpoint_manager.mark_completed("test_output.vtt")
                    
                    # Verify checkpoint is cleaned up
                    assert not checkpoint_file.exists()
    
    def test_checkpoint_file_integrity(self, tmp_path):
        """Test checkpoint file integrity and recovery from corruption."""
        data_dir = tmp_path / "data"
        checkpoint_file = data_dir / "checkpoints" / "active_checkpoint.json"
        checkpoint_file.parent.mkdir(parents=True)
        
        # Write corrupted checkpoint
        checkpoint_file.write_text("{ invalid json }")
        
        # Manager should handle corrupted checkpoint gracefully
        manager = CheckpointManager(data_dir)
        assert not manager.can_resume()
        
        # Write valid checkpoint
        valid_checkpoint = {
            'episode_id': 'integrity-test',
            'audio_url': 'https://example.com/test.mp3',
            'title': 'Test',
            'status': 'transcription',
            'stage_completed': [],
            'temporary_files': {},
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'metadata': {}
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(valid_checkpoint, f)
        
        # Should now be able to resume
        new_manager = CheckpointManager(data_dir)
        assert new_manager.can_resume()
        assert new_manager.current_checkpoint.episode_id == 'integrity-test'
    
    @pytest.mark.asyncio
    async def test_no_duplicate_processing_after_recovery(self, tmp_path):
        """Ensure episodes aren't processed twice after checkpoint recovery."""
        data_dir = tmp_path / "data"
        
        # Create progress tracker file with completed episode
        progress_data = {
            "episodes": {
                "completed-001": {
                    "guid": "completed-001",
                    "status": "completed",
                    "title": "Already Completed Episode",
                    "file_path": "output/completed.vtt",
                    "completed_at": datetime.now().isoformat()
                }
            }
        }
        
        progress_file = data_dir / ".transcription_progress.json"
        progress_file.parent.mkdir(exist_ok=True)
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
        
        # Try to create checkpoint for completed episode
        checkpoint_manager = CheckpointManager(data_dir)
        
        # This should be prevented by the orchestrator logic
        # but checkpoint manager should track it
        checkpoint_manager.start_episode(
            episode_id="completed-001",
            audio_url="https://example.com/completed.mp3",
            title="Already Completed Episode",
            metadata={}
        )
        
        # Add metadata to track this is a retry of completed episode
        checkpoint_manager.current_checkpoint.metadata.update({
            'is_retry_of_completed': True,
            'original_completion_time': progress_data["episodes"]["completed-001"]["completed_at"]
        })
        checkpoint_manager._save_checkpoint()
        
        # Verify metadata is stored
        resume_info = checkpoint_manager.get_resume_info()
        assert resume_info['metadata']['is_retry_of_completed'] is True