"""Unit tests for episode flow processing."""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

from src.processing.episode_flow import (
    EpisodeProcessor,
    ProcessingStage,
    ProcessingMetrics,
    ProcessingResult,
    EpisodeState,
    create_episode_flow,
    process_episode_batch
)


class TestProcessingStage:
    """Test ProcessingStage enum."""
    
    def test_processing_stage_values(self):
        """Test ProcessingStage values."""
        assert ProcessingStage.INITIALIZATION == "initialization"
        assert ProcessingStage.SEGMENTATION == "segmentation"
        assert ProcessingStage.EXTRACTION == "extraction"
        assert ProcessingStage.ENRICHMENT == "enrichment"
        assert ProcessingStage.STORAGE == "storage"
        assert ProcessingStage.COMPLETION == "completion"


class TestProcessingMetrics:
    """Test ProcessingMetrics dataclass."""
    
    def test_processing_metrics_creation(self):
        """Test creating ProcessingMetrics."""
        metrics = ProcessingMetrics(
            stage=ProcessingStage.EXTRACTION,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=5.5,
            success=True,
            error=None,
            items_processed=10
        )
        
        assert metrics.stage == ProcessingStage.EXTRACTION
        assert metrics.duration == 5.5
        assert metrics.success is True
        assert metrics.error is None
        assert metrics.items_processed == 10
    
    def test_processing_metrics_with_error(self):
        """Test ProcessingMetrics with error."""
        metrics = ProcessingMetrics(
            stage=ProcessingStage.STORAGE,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=1.2,
            success=False,
            error="Database connection failed"
        )
        
        assert metrics.success is False
        assert metrics.error == "Database connection failed"
        assert metrics.items_processed == 0


class TestProcessingResult:
    """Test ProcessingResult dataclass."""
    
    def test_processing_result_success(self):
        """Test successful ProcessingResult."""
        result = ProcessingResult(
            episode_id="ep123",
            success=True,
            metrics=[],
            error=None,
            data={"entities": [], "insights": []}
        )
        
        assert result.episode_id == "ep123"
        assert result.success is True
        assert result.error is None
        assert "entities" in result.data
    
    def test_processing_result_failure(self):
        """Test failed ProcessingResult."""
        result = ProcessingResult(
            episode_id="ep456",
            success=False,
            metrics=[],
            error="Processing failed",
            data=None
        )
        
        assert result.episode_id == "ep456"
        assert result.success is False
        assert result.error == "Processing failed"
        assert result.data is None


class TestEpisodeState:
    """Test EpisodeState class."""
    
    def test_episode_state_initialization(self):
        """Test EpisodeState initialization."""
        state = EpisodeState(episode_id="ep789")
        
        assert state.episode_id == "ep789"
        assert state.current_stage == ProcessingStage.INITIALIZATION
        assert state.completed_stages == []
        assert state.metrics == []
        assert state.errors == []
        assert state.data == {}
    
    def test_episode_state_update_stage(self):
        """Test updating episode state stage."""
        state = EpisodeState(episode_id="ep123")
        
        state.update_stage(ProcessingStage.SEGMENTATION)
        assert state.current_stage == ProcessingStage.SEGMENTATION
        assert ProcessingStage.INITIALIZATION in state.completed_stages
        
        state.update_stage(ProcessingStage.EXTRACTION)
        assert state.current_stage == ProcessingStage.EXTRACTION
        assert ProcessingStage.SEGMENTATION in state.completed_stages
    
    def test_episode_state_add_metric(self):
        """Test adding metrics to episode state."""
        state = EpisodeState(episode_id="ep123")
        
        metric = ProcessingMetrics(
            stage=ProcessingStage.EXTRACTION,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=2.5,
            success=True
        )
        
        state.add_metric(metric)
        assert len(state.metrics) == 1
        assert state.metrics[0] == metric
    
    def test_episode_state_add_error(self):
        """Test adding errors to episode state."""
        state = EpisodeState(episode_id="ep123")
        
        state.add_error("Test error", ProcessingStage.STORAGE)
        assert len(state.errors) == 1
        assert state.errors[0]["error"] == "Test error"
        assert state.errors[0]["stage"] == ProcessingStage.STORAGE
    
    def test_episode_state_to_dict(self):
        """Test converting episode state to dictionary."""
        state = EpisodeState(episode_id="ep123")
        state.update_stage(ProcessingStage.EXTRACTION)
        state.data["test"] = "value"
        
        result = state.to_dict()
        
        assert result["episode_id"] == "ep123"
        assert result["current_stage"] == ProcessingStage.EXTRACTION
        assert len(result["completed_stages"]) == 1
        assert result["data"]["test"] == "value"


class TestEpisodeProcessor:
    """Test EpisodeProcessor class."""
    
    @patch('src.processing.episode_flow.get_logger')
    def test_episode_processor_initialization(self, mock_get_logger):
        """Test EpisodeProcessor initialization."""
        mock_config = Mock()
        mock_extractor = Mock()
        mock_storage = Mock()
        
        processor = EpisodeProcessor(
            config=mock_config,
            extractor=mock_extractor,
            storage=mock_storage
        )
        
        assert processor.config == mock_config
        assert processor.extractor == mock_extractor
        assert processor.storage == mock_storage
        assert processor.metrics_collector is not None
    
    @patch('src.processing.episode_flow.get_logger')
    @patch('src.processing.episode_flow.get_metrics_collector')
    def test_process_episode_success(self, mock_get_metrics, mock_get_logger):
        """Test successful episode processing."""
        # Setup mocks
        mock_config = Mock()
        mock_extractor = Mock()
        mock_storage = Mock()
        mock_metrics = Mock()
        mock_get_metrics.return_value = mock_metrics
        
        # Mock extraction results
        mock_extractor.extract.return_value = {
            "entities": [{"name": "Test", "type": "THING"}],
            "insights": []
        }
        
        processor = EpisodeProcessor(
            config=mock_config,
            extractor=mock_extractor,
            storage=mock_storage
        )
        
        # Process episode
        episode_data = {
            "id": "ep123",
            "title": "Test Episode",
            "transcript": "Test transcript content"
        }
        
        with patch.object(processor, '_segment_transcript', return_value=["Segment 1"]):
            with patch.object(processor, '_enrich_data', return_value={"enriched": True}):
                result = processor.process_episode(episode_data)
        
        assert result.success is True
        assert result.episode_id == "ep123"
        assert len(result.metrics) > 0
        
        # Verify extraction was called
        mock_extractor.extract.assert_called()
        
        # Verify storage was called
        mock_storage.store_episode.assert_called()
    
    @patch('src.processing.episode_flow.get_logger')
    def test_process_episode_extraction_error(self, mock_get_logger):
        """Test episode processing with extraction error."""
        mock_config = Mock()
        mock_extractor = Mock()
        mock_extractor.extract.side_effect = Exception("Extraction failed")
        mock_storage = Mock()
        
        processor = EpisodeProcessor(
            config=mock_config,
            extractor=mock_extractor,
            storage=mock_storage
        )
        
        episode_data = {
            "id": "ep123",
            "title": "Test Episode",
            "transcript": "Test transcript"
        }
        
        with patch.object(processor, '_segment_transcript', return_value=["Segment 1"]):
            result = processor.process_episode(episode_data)
        
        assert result.success is False
        assert result.error is not None
        assert "Extraction failed" in result.error
    
    def test_segment_transcript(self):
        """Test transcript segmentation."""
        processor = EpisodeProcessor(Mock(), Mock(), Mock())
        
        transcript = "Sentence one. Sentence two. Sentence three. Sentence four."
        
        with patch('src.processing.episode_flow.segment_transcript') as mock_segment:
            mock_segment.return_value = ["Segment 1", "Segment 2"]
            
            segments = processor._segment_transcript(transcript)
            
            assert len(segments) == 2
            mock_segment.assert_called_once_with(transcript)
    
    def test_extract_from_segments(self):
        """Test extraction from segments."""
        mock_extractor = Mock()
        mock_extractor.extract.side_effect = [
            {"entities": [{"name": "Entity1"}], "insights": []},
            {"entities": [{"name": "Entity2"}], "insights": [{"title": "Insight1"}]}
        ]
        
        processor = EpisodeProcessor(Mock(), mock_extractor, Mock())
        
        segments = ["Segment 1", "Segment 2"]
        result = processor._extract_from_segments(segments)
        
        assert len(result["entities"]) == 2
        assert len(result["insights"]) == 1
        assert mock_extractor.extract.call_count == 2
    
    def test_enrich_data(self):
        """Test data enrichment."""
        processor = EpisodeProcessor(Mock(), Mock(), Mock())
        
        data = {
            "entities": [{"name": "Test Entity", "type": "PERSON"}],
            "insights": [{"title": "Test Insight"}]
        }
        
        with patch('src.processing.episode_flow.enrich_entities') as mock_enrich:
            mock_enrich.return_value = [{"name": "Test Entity", "enriched": True}]
            
            enriched = processor._enrich_data(data)
            
            assert enriched["entities"][0]["enriched"] is True
            mock_enrich.assert_called_once()
    
    def test_calculate_processing_metrics(self):
        """Test calculating processing metrics."""
        processor = EpisodeProcessor(Mock(), Mock(), Mock())
        
        state = EpisodeState(episode_id="ep123")
        state.add_metric(ProcessingMetrics(
            stage=ProcessingStage.EXTRACTION,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=2.5,
            success=True,
            items_processed=10
        ))
        state.add_metric(ProcessingMetrics(
            stage=ProcessingStage.STORAGE,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=1.5,
            success=True,
            items_processed=10
        ))
        
        summary = processor._calculate_processing_metrics(state)
        
        assert summary["total_duration"] == 4.0
        assert summary["stages_completed"] == 2
        assert summary["items_processed"] == 20


class TestCreateEpisodeFlow:
    """Test create_episode_flow function."""
    
    @patch('src.processing.episode_flow.Config')
    @patch('src.processing.episode_flow.create_extractor')
    @patch('src.processing.episode_flow.create_storage')
    def test_create_episode_flow(self, mock_create_storage, mock_create_extractor, mock_config_class):
        """Test creating episode flow."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        mock_extractor = Mock()
        mock_create_extractor.return_value = mock_extractor
        
        mock_storage = Mock()
        mock_create_storage.return_value = mock_storage
        
        processor = create_episode_flow()
        
        assert isinstance(processor, EpisodeProcessor)
        mock_create_extractor.assert_called_once_with(mock_config)
        mock_create_storage.assert_called_once_with(mock_config)


class TestProcessEpisodeBatch:
    """Test process_episode_batch function."""
    
    @patch('src.processing.episode_flow.create_episode_flow')
    def test_process_episode_batch_success(self, mock_create_flow):
        """Test processing episode batch successfully."""
        mock_processor = Mock()
        mock_create_flow.return_value = mock_processor
        
        # Mock successful processing
        mock_processor.process_episode.side_effect = [
            ProcessingResult(episode_id="ep1", success=True, metrics=[], error=None),
            ProcessingResult(episode_id="ep2", success=True, metrics=[], error=None)
        ]
        
        episodes = [
            {"id": "ep1", "title": "Episode 1"},
            {"id": "ep2", "title": "Episode 2"}
        ]
        
        results = process_episode_batch(episodes)
        
        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_processor.process_episode.call_count == 2
    
    @patch('src.processing.episode_flow.create_episode_flow')
    def test_process_episode_batch_with_failures(self, mock_create_flow):
        """Test processing episode batch with some failures."""
        mock_processor = Mock()
        mock_create_flow.return_value = mock_processor
        
        # Mock mixed results
        mock_processor.process_episode.side_effect = [
            ProcessingResult(episode_id="ep1", success=True, metrics=[], error=None),
            ProcessingResult(episode_id="ep2", success=False, metrics=[], error="Failed"),
            ProcessingResult(episode_id="ep3", success=True, metrics=[], error=None)
        ]
        
        episodes = [
            {"id": "ep1", "title": "Episode 1"},
            {"id": "ep2", "title": "Episode 2"},
            {"id": "ep3", "title": "Episode 3"}
        ]
        
        results = process_episode_batch(episodes, stop_on_error=False)
        
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
    
    @patch('src.processing.episode_flow.create_episode_flow')
    def test_process_episode_batch_stop_on_error(self, mock_create_flow):
        """Test processing episode batch with stop_on_error."""
        mock_processor = Mock()
        mock_create_flow.return_value = mock_processor
        
        # Mock failure on second episode
        mock_processor.process_episode.side_effect = [
            ProcessingResult(episode_id="ep1", success=True, metrics=[], error=None),
            ProcessingResult(episode_id="ep2", success=False, metrics=[], error="Failed")
        ]
        
        episodes = [
            {"id": "ep1", "title": "Episode 1"},
            {"id": "ep2", "title": "Episode 2"},
            {"id": "ep3", "title": "Episode 3"}  # Should not be processed
        ]
        
        results = process_episode_batch(episodes, stop_on_error=True)
        
        assert len(results) == 2  # Only processed first two
        assert results[0].success is True
        assert results[1].success is False
        assert mock_processor.process_episode.call_count == 2