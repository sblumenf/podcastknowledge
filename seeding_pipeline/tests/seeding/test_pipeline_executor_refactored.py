"""
Unit tests for refactored PipelineExecutor helper methods.

This module tests the new helper methods added during refactoring
to ensure they maintain the same behavior as the original code.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import os

from src.seeding.components.pipeline_executor import PipelineExecutor
from src.core.exceptions import PipelineError


class TestPipelineExecutorHelperMethods:
    """Test the newly extracted helper methods."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for PipelineExecutor."""
        mock_provider_coordinator = Mock()
        mock_checkpoint_manager = Mock()
        mock_storage_coordinator = Mock()
        mock_config = Mock()
        
        # Set up provider mocks
        mock_provider_coordinator.segmenter = Mock()
        mock_provider_coordinator.knowledge_extractor = Mock()
        mock_provider_coordinator.entity_resolver = Mock()
        mock_provider_coordinator.graph_analyzer = Mock()
        mock_provider_coordinator.emergent_theme_detector = Mock()
        mock_provider_coordinator.episode_flow_analyzer = Mock()
        mock_provider_coordinator.graph_provider = Mock()
        mock_provider_coordinator.llm_provider = Mock()
        mock_provider_coordinator.embedding_provider = Mock()
        
        return {
            'provider_coordinator': mock_provider_coordinator,
            'checkpoint_manager': mock_checkpoint_manager,
            'storage_coordinator': mock_storage_coordinator,
            'config': mock_config
        }
    
    @pytest.fixture
    def pipeline_executor(self, mock_dependencies):
        """Create PipelineExecutor instance with mocks."""
        return PipelineExecutor(
            mock_dependencies['provider_coordinator'],
            mock_dependencies['checkpoint_manager'],
            mock_dependencies['storage_coordinator'],
            mock_dependencies['config']
        )
    
    def test_is_episode_completed_true(self, pipeline_executor):
        """Test _is_episode_completed when episode is completed."""
        # Setup
        episode_id = "ep123"
        pipeline_executor.checkpoint_manager.is_completed.return_value = True
        
        # Execute
        result = pipeline_executor._is_episode_completed(episode_id)
        
        # Assert
        assert result is True
        pipeline_executor.checkpoint_manager.is_completed.assert_called_once_with(episode_id)
    
    def test_is_episode_completed_false(self, pipeline_executor):
        """Test _is_episode_completed when episode is not completed."""
        # Setup
        episode_id = "ep123"
        pipeline_executor.checkpoint_manager.is_completed.return_value = False
        
        # Execute
        result = pipeline_executor._is_episode_completed(episode_id)
        
        # Assert
        assert result is False
        pipeline_executor.checkpoint_manager.is_completed.assert_called_once_with(episode_id)
    
    @patch('src.seeding.components.pipeline_executor.download_episode_audio')
    def test_download_episode_audio_success(self, mock_download, pipeline_executor):
        """Test _download_episode_audio successful download."""
        # Setup
        episode = {'id': 'ep123', 'title': 'Test Episode'}
        podcast_id = 'pod456'
        expected_path = '/tmp/audio/ep123.mp3'
        mock_download.return_value = expected_path
        pipeline_executor.config.audio_dir = '/tmp/audio'
        
        # Execute
        result = pipeline_executor._download_episode_audio(episode, podcast_id)
        
        # Assert
        assert result == expected_path
        mock_download.assert_called_once_with(
            episode,
            podcast_id,
            output_dir='/tmp/audio'
        )
    
    @patch('src.seeding.components.pipeline_executor.download_episode_audio')
    def test_download_episode_audio_failure(self, mock_download, pipeline_executor):
        """Test _download_episode_audio when download fails."""
        # Setup
        episode = {'id': 'ep123', 'title': 'Test Episode'}
        podcast_id = 'pod456'
        mock_download.return_value = None
        
        # Execute & Assert
        with pytest.raises(PipelineError) as exc_info:
            pipeline_executor._download_episode_audio(episode, podcast_id)
        
        assert "Failed to download audio for episode ep123" in str(exc_info.value)
    
    @patch('src.seeding.components.pipeline_executor.add_span_attributes')
    def test_add_episode_context(self, mock_add_span, pipeline_executor):
        """Test _add_episode_context adds correct attributes."""
        # Setup
        episode = {'id': 'ep123', 'title': 'Test Episode'}
        podcast_config = {'id': 'pod456', 'name': 'Test Podcast'}
        
        # Execute
        pipeline_executor._add_episode_context(episode, podcast_config)
        
        # Assert
        mock_add_span.assert_called_once_with({
            "episode.id": "ep123",
            "episode.title": "Test Episode",
            "podcast.id": "pod456",
            "podcast.name": "Test Podcast",
        })
    
    @patch('src.seeding.components.pipeline_executor.create_span')
    @patch('src.seeding.components.pipeline_executor.add_span_attributes')
    def test_process_audio_segments(self, mock_add_span, mock_create_span, pipeline_executor):
        """Test _process_audio_segments processing and checkpointing."""
        # Setup
        audio_path = '/tmp/audio/ep123.mp3'
        episode_id = 'ep123'
        mock_segments = [
            {'text': 'Segment 1', 'start': 0, 'end': 30},
            {'text': 'Segment 2', 'start': 30, 'end': 60}
        ]
        pipeline_executor._prepare_segments = Mock(return_value=mock_segments)
        
        # Execute
        with patch('src.seeding.components.pipeline_executor.create_span'):
            result = pipeline_executor._process_audio_segments(audio_path, episode_id)
        
        # Assert
        assert result == mock_segments
        pipeline_executor._prepare_segments.assert_called_once_with(audio_path)
        pipeline_executor.checkpoint_manager.save_progress.assert_called_once_with(
            episode_id, "segments", mock_segments
        )
    
    def test_determine_extraction_mode_fixed(self, pipeline_executor):
        """Test _determine_extraction_mode returns 'fixed' by default."""
        # Setup
        pipeline_executor.config.use_schemaless_extraction = False
        pipeline_executor.config.migration_mode = False
        
        # Execute
        result = pipeline_executor._determine_extraction_mode()
        
        # Assert
        assert result == 'fixed'
    
    def test_determine_extraction_mode_schemaless(self, pipeline_executor):
        """Test _determine_extraction_mode returns 'schemaless' when enabled."""
        # Setup
        pipeline_executor.config.use_schemaless_extraction = True
        pipeline_executor.config.migration_mode = False
        
        # Execute
        result = pipeline_executor._determine_extraction_mode()
        
        # Assert
        assert result == 'schemaless'
    
    def test_determine_extraction_mode_migration(self, pipeline_executor):
        """Test _determine_extraction_mode returns 'migration' when enabled."""
        # Setup
        pipeline_executor.config.use_schemaless_extraction = True
        pipeline_executor.config.migration_mode = True
        
        # Execute
        result = pipeline_executor._determine_extraction_mode()
        
        # Assert
        assert result == 'migration'
    
    @patch('src.seeding.components.pipeline_executor.cleanup_memory')
    @patch('src.seeding.components.pipeline_executor.add_span_attributes')
    def test_finalize_episode_processing(self, mock_add_span, mock_cleanup, pipeline_executor):
        """Test _finalize_episode_processing completes all steps."""
        # Setup
        episode_id = 'ep123'
        result = {
            'segments': 5,
            'insights': 10,
            'entities': 15,
            'mode': 'fixed'
        }
        
        # Execute
        pipeline_executor._finalize_episode_processing(episode_id, result)
        
        # Assert
        pipeline_executor.checkpoint_manager.mark_completed.assert_called_once_with(
            episode_id, result
        )
        mock_cleanup.assert_called_once()
        mock_add_span.assert_called_once_with({
            "result.segments": 5,
            "result.insights": 10,
            "result.entities": 15,
            "result.mode": "fixed"
        })
    
    @patch('os.remove')
    def test_cleanup_audio_file_enabled(self, mock_remove, pipeline_executor):
        """Test _cleanup_audio_file when cleanup is enabled."""
        # Setup
        audio_path = '/tmp/audio/ep123.mp3'
        pipeline_executor.config.delete_audio_after_processing = True
        
        # Execute
        pipeline_executor._cleanup_audio_file(audio_path)
        
        # Assert
        mock_remove.assert_called_once_with(audio_path)
    
    @patch('os.remove')
    def test_cleanup_audio_file_disabled(self, mock_remove, pipeline_executor):
        """Test _cleanup_audio_file when cleanup is disabled."""
        # Setup
        audio_path = '/tmp/audio/ep123.mp3'
        pipeline_executor.config.delete_audio_after_processing = False
        
        # Execute
        pipeline_executor._cleanup_audio_file(audio_path)
        
        # Assert
        mock_remove.assert_not_called()
    
    @patch('os.remove')
    def test_cleanup_audio_file_error_ignored(self, mock_remove, pipeline_executor):
        """Test _cleanup_audio_file ignores errors."""
        # Setup
        audio_path = '/tmp/audio/ep123.mp3'
        pipeline_executor.config.delete_audio_after_processing = True
        mock_remove.side_effect = OSError("File not found")
        
        # Execute (should not raise)
        pipeline_executor._cleanup_audio_file(audio_path)
        
        # Assert
        mock_remove.assert_called_once_with(audio_path)