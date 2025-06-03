"""Unit tests for pipeline orchestrator module.

Tests for src/seeding/orchestrator.py focusing on unit-level testing
with mocked dependencies.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest import mock
import logging

import pytest

from src.core.config import PipelineConfig, SeedingConfig
from src.core.exceptions import PipelineError, ConfigurationError
from src.extraction.extraction import KnowledgeExtractor
from src.processing.segmentation import VTTSegmenter
from src.services.embeddings import EmbeddingsService
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.seeding.components.signal_manager import SignalManager
from src.seeding.components.provider_coordinator import ProviderCoordinator
from src.seeding.components.checkpoint_manager import CheckpointManager
from src.seeding.components.pipeline_executor import PipelineExecutor
from src.storage.storage_coordinator import StorageCoordinator
from src.seeding.orchestrator import VTTKnowledgeExtractor


class TestPodcastKnowledgePipeline:
    """Test VTTKnowledgeExtractor class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = mock.Mock(spec=SeedingConfig)
        config.log_level = 'INFO'
        config.log_file = None
        config.use_schemaless_extraction = False
        config.checkpoint_enabled = True
        config.checkpoint_interval = 10
        return config
    
    @pytest.fixture
    def mock_factory(self):
        """Create mock provider factory."""
        return mock.Mock(spec=ProviderFactory)
    
    @pytest.fixture
    def mock_components(self):
        """Create mocked pipeline components."""
        return {
            'signal_manager': mock.Mock(spec=SignalManager),
            'provider_coordinator': mock.Mock(spec=ProviderCoordinator),
            'checkpoint_manager': mock.Mock(spec=CheckpointManager),
            'pipeline_executor': mock.Mock(spec=PipelineExecutor),
            'storage_coordinator': mock.Mock(spec=StorageCoordinator)
        }
    
    @pytest.fixture
    def pipeline(self, mock_config, monkeypatch):
        """Create pipeline instance with mocked dependencies."""
        # Mock component initialization
        with mock.patch('src.seeding.orchestrator.SignalManager'):
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator'):
                with mock.patch('src.seeding.orchestrator.CheckpointManager'):
                    with mock.patch('src.seeding.orchestrator.ProviderFactory'):
                        with mock.patch('src.seeding.orchestrator.init_tracing'):
                            pipeline = VTTKnowledgeExtractor(config=mock_config)
                            return pipeline
    
    def test_pipeline_initialization(self, mock_config):
        """Test pipeline initialization."""
        with mock.patch('src.seeding.orchestrator.SignalManager') as MockSignal:
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator') as MockProvider:
                with mock.patch('src.seeding.orchestrator.CheckpointManager') as MockCheckpoint:
                    with mock.patch('src.seeding.orchestrator.ProviderFactory') as MockFactory:
                        with mock.patch('src.seeding.orchestrator.init_tracing'):
                            pipeline = VTTKnowledgeExtractor(config=mock_config)
                            
                            # Verify component creation
                            MockSignal.assert_called_once()
                            MockProvider.assert_called_once()
                            MockCheckpoint.assert_called_once_with(mock_config)
                            MockFactory.assert_called_once()
                            
                            # Verify attributes
                            assert pipeline.config == mock_config
                            assert pipeline._shutdown_requested is False
                            assert pipeline.audio_provider is None
                            assert pipeline.pipeline_executor is None
    
    def test_pipeline_default_config(self, monkeypatch):
        """Test pipeline with default configuration."""
        # Set required environment variables
        monkeypatch.setenv('NEO4J_PASSWORD', 'test')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test')
        
        with mock.patch('src.seeding.orchestrator.SignalManager'):
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator'):
                with mock.patch('src.seeding.orchestrator.CheckpointManager'):
                    with mock.patch('src.seeding.orchestrator.ProviderFactory'):
                        with mock.patch('src.seeding.orchestrator.init_tracing'):
                            pipeline = VTTKnowledgeExtractor()
                            assert isinstance(pipeline.config, SeedingConfig)
    
    def test_setup_logging(self, pipeline, mock_config):
        """Test logging setup."""
        # Test basic logging setup
        with mock.patch('logging.basicConfig') as mock_basic_config:
            pipeline._setup_logging()
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs['level'] == logging.INFO
    
    def test_setup_logging_with_file(self, pipeline, mock_config):
        """Test logging setup with file handler."""
        mock_config.log_file = '/tmp/test.log'
        
        with mock.patch('logging.basicConfig'):
            with mock.patch('logging.FileHandler') as MockFileHandler:
                with mock.patch('logging.getLogger') as mock_get_logger:
                    mock_logger = mock.Mock()
                    mock_get_logger.return_value = mock_logger
                    
                    pipeline._setup_logging()
                    
                    MockFileHandler.assert_called_once_with('/tmp/test.log')
                    mock_logger.addHandler.assert_called_once()
    
    def test_setup_tracing(self, pipeline):
        """Test tracing setup."""
        with mock.patch('src.seeding.orchestrator.TracingConfig') as MockTracingConfig:
            with mock.patch('src.seeding.orchestrator.init_tracing') as mock_init:
                # Mock tracing config
                mock_tracing_config = mock.Mock()
                mock_tracing_config.service_name = 'test-service'
                mock_tracing_config.jaeger_host = 'localhost'
                mock_tracing_config.jaeger_port = 6831
                mock_tracing_config.console_export = False
                mock_tracing_config.instrument_neo4j = False
                mock_tracing_config.instrument_redis = False
                mock_tracing_config.instrument_requests = False
                mock_tracing_config.instrument_langchain = False
                mock_tracing_config.instrument_whisper = False
                MockTracingConfig.from_env.return_value = mock_tracing_config
                
                pipeline._setup_tracing()
                
                mock_init.assert_called_once_with(
                    service_name='test-service',
                    jaeger_host='localhost',
                    jaeger_port=6831,
                    config=pipeline.config,
                    enable_console=False
                )
    
    def test_initialize_components_success(self, pipeline):
        """Test successful component initialization."""
        # Mock provider coordinator
        pipeline.provider_coordinator.initialize_providers.return_value = True
        pipeline.provider_coordinator.check_health.return_value = True
        
        # Mock providers
        mock_audio = mock.Mock(spec=AudioProvider)
        mock_llm = mock.Mock(spec=LLMProvider)
        mock_graph = mock.Mock(spec=GraphProvider)
        mock_embedding = mock.Mock(spec=EmbeddingProvider)
        
        pipeline.provider_coordinator.audio_provider = mock_audio
        pipeline.provider_coordinator.llm_provider = mock_llm
        pipeline.provider_coordinator.graph_provider = mock_graph
        pipeline.provider_coordinator.embedding_provider = mock_embedding
        
        # Mock processing components
        pipeline.provider_coordinator.segmenter = mock.Mock()
        pipeline.provider_coordinator.knowledge_extractor = mock.Mock()
        pipeline.provider_coordinator.entity_resolver = mock.Mock()
        pipeline.provider_coordinator.graph_analyzer = mock.Mock()
        pipeline.provider_coordinator.graph_enhancer = mock.Mock()
        pipeline.provider_coordinator.discourse_flow_tracker = mock.Mock()
        pipeline.provider_coordinator.emergent_theme_detector = mock.Mock()
        pipeline.provider_coordinator.episode_flow_analyzer = mock.Mock()
        
        # Mock checkpoint
        pipeline.checkpoint_manager.checkpoint = mock.Mock()
        
        with mock.patch('src.seeding.orchestrator.StorageCoordinator') as MockStorage:
            with mock.patch('src.seeding.orchestrator.PipelineExecutor') as MockExecutor:
                result = pipeline.initialize_components(use_large_context=True)
                
                assert result is True
                
                # Verify provider coordinator was called
                pipeline.provider_coordinator.initialize_providers.assert_called_once_with(True)
                
                # Verify backward compatibility references
                assert pipeline.audio_provider == mock_audio
                assert pipeline.llm_provider == mock_llm
                assert pipeline.graph_provider == mock_graph
                assert pipeline.embedding_provider == mock_embedding
                
                # Verify storage and executor creation
                MockStorage.assert_called_once()
                MockExecutor.assert_called_once()
    
    def test_initialize_components_provider_failure(self, pipeline):
        """Test component initialization when provider init fails."""
        pipeline.provider_coordinator.initialize_providers.return_value = False
        
        result = pipeline.initialize_components()
        
        assert result is False
        assert pipeline.audio_provider is None
        assert pipeline.pipeline_executor is None
    
    def test_initialize_components_health_check_failure(self, pipeline):
        """Test component initialization when health check fails."""
        pipeline.provider_coordinator.initialize_providers.return_value = True
        pipeline.provider_coordinator.check_health.return_value = False
        
        # Set up mock providers so storage coordinator can be created
        pipeline.provider_coordinator.graph_provider = mock.Mock()
        pipeline.provider_coordinator.graph_enhancer = mock.Mock()
        
        with mock.patch('src.seeding.orchestrator.StorageCoordinator'):
            with mock.patch('src.seeding.orchestrator.PipelineExecutor'):
                result = pipeline.initialize_components()
                
                assert result is False
    
    def test_verify_components_health(self, pipeline):
        """Test component health verification."""
        pipeline.provider_coordinator.check_health.return_value = True
        assert pipeline._verify_components_health() is True
        
        pipeline.provider_coordinator.check_health.return_value = False
        assert pipeline._verify_components_health() is False
    
    def test_cleanup(self, pipeline):
        """Test resource cleanup."""
        with mock.patch('src.seeding.orchestrator.cleanup_memory') as mock_cleanup_memory:
            pipeline.cleanup()
            
            pipeline.provider_coordinator.cleanup.assert_called_once()
            mock_cleanup_memory.assert_called_once()
    
    def test_seed_podcast(self, pipeline):
        """Test single podcast seeding."""
        podcast_config = {'id': 'test', 'rss_url': 'http://test.com/feed'}
        
        with mock.patch.object(pipeline, 'seed_podcasts') as mock_seed_podcasts:
            mock_seed_podcasts.return_value = {'success': True}
            
            result = pipeline.seed_podcast(
                podcast_config,
                max_episodes=5
            )
            
            mock_seed_podcasts.assert_called_once_with(
                [podcast_config],
                max_episodes_per_podcast=5,
                use_large_context=True
            )
            assert result == {'success': True}
    
    def test_seed_podcasts_single_config(self, pipeline):
        """Test seed_podcasts with single config dict."""
        podcast_config = {'id': 'test', 'rss_url': 'http://test.com/feed'}
        
        # Mock component initialization
        pipeline.audio_provider = mock.Mock()  # Already initialized
        
        with mock.patch.object(pipeline, '_process_podcast') as mock_process:
            with mock.patch.object(pipeline, 'cleanup') as mock_cleanup:
                mock_process.return_value = {
                    'episodes_processed': 1,
                    'episodes_failed': 0,
                    'total_segments': 10,
                    'total_insights': 5,
                    'total_entities': 20,
                    'extraction_mode': 'fixed'
                }
                
                result = pipeline.seed_podcasts(podcast_config, max_episodes_per_podcast=1)
                
                # Should convert to list
                mock_process.assert_called_once_with(podcast_config, 1, True)
                mock_cleanup.assert_called_once()
                
                assert result['podcasts_processed'] == 1
                assert result['episodes_processed'] == 1
                assert result['success'] is True
    
    def test_seed_podcasts_initialization_required(self, pipeline):
        """Test seed_podcasts when initialization is required."""
        podcast_configs = [{'id': 'test', 'rss_url': 'http://test.com/feed'}]
        
        # No providers initialized yet
        assert pipeline.audio_provider is None
        
        with mock.patch.object(pipeline, 'initialize_components') as mock_init:
            with mock.patch.object(pipeline, '_process_podcast') as mock_process:
                with mock.patch.object(pipeline, 'cleanup'):
                    mock_init.return_value = True
                    mock_process.return_value = {
                        'episodes_processed': 1,
                        'episodes_failed': 0,
                        'total_segments': 10,
                        'total_insights': 5,
                        'total_entities': 20,
                        'extraction_mode': 'fixed'
                    }
                    
                    result = pipeline.seed_podcasts(podcast_configs)
                    
                    mock_init.assert_called_once_with(True)
                    assert result['success'] is True
    
    def test_seed_podcasts_initialization_failure(self, pipeline):
        """Test seed_podcasts when initialization fails."""
        podcast_configs = [{'id': 'test', 'rss_url': 'http://test.com/feed'}]
        
        with mock.patch.object(pipeline, 'initialize_components') as mock_init:
            mock_init.return_value = False
            
            with pytest.raises(PipelineError, match="Failed to initialize"):
                pipeline.seed_podcasts(podcast_configs)
    
    def test_seed_podcasts_with_shutdown(self, pipeline):
        """Test seed_podcasts with shutdown request."""
        podcast_configs = [
            {'id': 'test1', 'rss_url': 'http://test1.com/feed'},
            {'id': 'test2', 'rss_url': 'http://test2.com/feed'}
        ]
        
        pipeline.audio_provider = mock.Mock()  # Already initialized
        pipeline._shutdown_requested = True
        
        with mock.patch.object(pipeline, '_process_podcast') as mock_process:
            with mock.patch.object(pipeline, 'cleanup'):
                result = pipeline.seed_podcasts(podcast_configs)
                
                # Should not process any podcasts
                mock_process.assert_not_called()
                assert result['podcasts_processed'] == 0
    
    def test_seed_podcasts_with_errors(self, pipeline):
        """Test seed_podcasts with processing errors."""
        podcast_configs = [
            {'id': 'test1', 'rss_url': 'http://test1.com/feed'},
            {'id': 'test2', 'rss_url': 'http://test2.com/feed'}
        ]
        
        pipeline.audio_provider = mock.Mock()
        
        with mock.patch.object(pipeline, '_process_podcast') as mock_process:
            with mock.patch.object(pipeline, 'cleanup'):
                # First succeeds, second fails
                mock_process.side_effect = [
                    {
                        'episodes_processed': 1,
                        'episodes_failed': 0,
                        'total_segments': 10,
                        'total_insights': 5,
                        'total_entities': 20,
                        'extraction_mode': 'fixed'
                    },
                    Exception("Processing error")
                ]
                
                result = pipeline.seed_podcasts(podcast_configs)
                
                assert result['podcasts_processed'] == 1
                assert result['success'] is False
                assert len(result['errors']) == 1
                assert result['errors'][0]['podcast'] == 'test2'
    
    def test_seed_podcasts_schemaless_mode(self, pipeline):
        """Test seed_podcasts in schemaless extraction mode."""
        pipeline.config.use_schemaless_extraction = True
        pipeline.audio_provider = mock.Mock()
        
        podcast_config = {'id': 'test', 'rss_url': 'http://test.com/feed'}
        
        with mock.patch.object(pipeline, '_process_podcast') as mock_process:
            with mock.patch.object(pipeline, 'cleanup'):
                mock_process.return_value = {
                    'episodes_processed': 1,
                    'episodes_failed': 0,
                    'total_segments': 10,
                    'total_insights': 5,
                    'total_entities': 20,
                    'total_relationships': 15,
                    'discovered_types': ['Person', 'Organization', 'Technology'],
                    'extraction_mode': 'schemaless'
                }
                
                result = pipeline.seed_podcasts(podcast_config)
                
                assert result['extraction_mode'] == 'schemaless'
                assert result['total_relationships'] == 15
                assert 'Person' in result['discovered_types']
                assert isinstance(result['discovered_types'], list)  # Converted from set
    
    def test_process_podcast(self, pipeline):
        """Test processing a single podcast."""
        podcast_config = {'id': 'test', 'name': 'Test Podcast', 'rss_url': 'http://test.com/feed'}
        
        mock_podcast_info = {
            'episodes': [
                {'title': 'Episode 1', 'url': 'http://test.com/ep1.mp3'},
                {'title': 'Episode 2', 'url': 'http://test.com/ep2.mp3'}
            ]
        }
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            with mock.patch.object(pipeline, '_process_episode') as mock_process_episode:
                mock_fetch.return_value = mock_podcast_info
                mock_process_episode.return_value = {
                    'segments': 10,
                    'insights': 5,
                    'entities': 20,
                    'mode': 'fixed'
                }
                
                result = pipeline._process_podcast(podcast_config, max_episodes=2, use_large_context=True)
                
                mock_fetch.assert_called_once_with(podcast_config, 2)
                assert mock_process_episode.call_count == 2
                assert result['episodes_processed'] == 2
                assert result['total_segments'] == 20
                assert result['total_insights'] == 10
                assert result['total_entities'] == 40
    
    def test_process_podcast_with_episode_failure(self, pipeline):
        """Test podcast processing when some episodes fail."""
        podcast_config = {'id': 'test', 'name': 'Test Podcast'}
        
        mock_podcast_info = {
            'episodes': [
                {'title': 'Episode 1', 'url': 'http://test.com/ep1.mp3'},
                {'title': 'Episode 2', 'url': 'http://test.com/ep2.mp3'}
            ]
        }
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            with mock.patch.object(pipeline, '_process_episode') as mock_process_episode:
                mock_fetch.return_value = mock_podcast_info
                
                # First episode succeeds, second fails
                mock_process_episode.side_effect = [
                    {'segments': 10, 'insights': 5, 'entities': 20, 'mode': 'fixed'},
                    Exception("Episode processing error")
                ]
                
                result = pipeline._process_podcast(podcast_config, max_episodes=2, use_large_context=True)
                
                assert result['episodes_processed'] == 1
                assert result['episodes_failed'] == 1
                assert result['total_segments'] == 10
    
    def test_process_podcast_schemaless_metrics(self, pipeline):
        """Test podcast processing with schemaless metrics."""
        pipeline.config.use_schemaless_extraction = True
        podcast_config = {'id': 'test', 'name': 'Test Podcast'}
        
        mock_podcast_info = {
            'episodes': [{'title': 'Episode 1', 'url': 'http://test.com/ep1.mp3'}]
        }
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            with mock.patch.object(pipeline, '_process_episode') as mock_process_episode:
                mock_fetch.return_value = mock_podcast_info
                mock_process_episode.return_value = {
                    'segments': 10,
                    'insights': 5,
                    'entities': 20,
                    'relationships': 15,
                    'discovered_types': {'Person', 'Organization'},
                    'mode': 'schemaless'
                }
                
                result = pipeline._process_podcast(podcast_config, max_episodes=1, use_large_context=True)
                
                assert result['extraction_mode'] == 'schemaless'
                assert result['total_relationships'] == 15
                assert 'Person' in result['discovered_types']
                assert isinstance(result['discovered_types'], list)  # Converted from set
    
    def test_process_episode(self, pipeline):
        """Test episode processing delegation."""
        podcast_config = {'id': 'test'}
        episode = {'title': 'Test Episode', 'url': 'http://test.com/ep.mp3'}
        
        # Mock pipeline executor
        pipeline.pipeline_executor = mock.Mock()
        pipeline.pipeline_executor.process_episode.return_value = {
            'segments': 10,
            'insights': 5,
            'entities': 20
        }
        
        result = pipeline._process_episode(podcast_config, episode, use_large_context=True)
        
        pipeline.pipeline_executor.process_episode.assert_called_once_with(
            podcast_config,
            episode,
            True
        )
        assert result['segments'] == 10
    
    def test_resume_from_checkpoints(self, pipeline):
        """Test checkpoint resumption."""
        result = pipeline.resume_from_checkpoints()
        
        assert result['resumed_episodes'] == 0
        assert 'not fully implemented' in result['message']


class TestSignalHandling:
    """Test signal handling integration."""
    
    def test_signal_manager_setup(self, monkeypatch):
        """Test signal manager is set up correctly."""
        # Set required environment variables
        monkeypatch.setenv('NEO4J_PASSWORD', 'test')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test')
        
        with mock.patch('src.seeding.orchestrator.SignalManager') as MockSignal:
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator'):
                with mock.patch('src.seeding.orchestrator.CheckpointManager'):
                    with mock.patch('src.seeding.orchestrator.init_tracing'):
                        mock_signal_instance = MockSignal.return_value
                        
                        pipeline = VTTKnowledgeExtractor()
                        
                        mock_signal_instance.setup.assert_called_once()
                        # Check cleanup callback was provided
                        call_kwargs = mock_signal_instance.setup.call_args[1]
                        assert 'cleanup_callback' in call_kwargs
                        assert callable(call_kwargs['cleanup_callback'])


class TestBackwardCompatibility:
    """Test backward compatibility features."""
    
    def test_backward_compatible_attributes(self, monkeypatch):
        """Test that old attribute references still work."""
        # Set required environment variables
        monkeypatch.setenv('NEO4J_PASSWORD', 'test')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test')
        
        with mock.patch('src.seeding.orchestrator.SignalManager'):
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator') as MockProvider:
                with mock.patch('src.seeding.orchestrator.CheckpointManager') as MockCheckpoint:
                    with mock.patch('src.seeding.orchestrator.init_tracing'):
                        pipeline = VTTKnowledgeExtractor()
                        
                        # Set up mocks
                        mock_provider_coord = MockProvider.return_value
                        mock_checkpoint_mgr = MockCheckpoint.return_value
                        
                        # Mock providers
                        mock_provider_coord.audio_provider = mock.Mock()
                        mock_provider_coord.llm_provider = mock.Mock()
                        mock_provider_coord.graph_provider = mock.Mock()
                        mock_provider_coord.embedding_provider = mock.Mock()
                        mock_provider_coord.segmenter = mock.Mock()
                        mock_provider_coord.knowledge_extractor = mock.Mock()
                        mock_provider_coord.check_health.return_value = True
                        mock_provider_coord.initialize_providers.return_value = True
                        
                        mock_checkpoint_mgr.checkpoint = mock.Mock()
                        
                        with mock.patch('src.seeding.orchestrator.StorageCoordinator'):
                            with mock.patch('src.seeding.orchestrator.PipelineExecutor'):
                                pipeline.initialize_components()
                                
                                # Verify backward compatible attributes are set
                                assert pipeline.audio_provider is not None
                                assert pipeline.llm_provider is not None
                                assert pipeline.graph_provider is not None
                                assert pipeline.embedding_provider is not None
                                assert pipeline.segmenter is not None
                                assert pipeline.knowledge_extractor is not None
                                assert pipeline.checkpoint is not None


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_podcast_list(self, monkeypatch):
        """Test processing empty podcast list."""
        # Set required environment variables
        monkeypatch.setenv('NEO4J_PASSWORD', 'test')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test')
        
        with mock.patch('src.seeding.orchestrator.SignalManager'):
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator'):
                with mock.patch('src.seeding.orchestrator.CheckpointManager'):
                    with mock.patch('src.seeding.orchestrator.init_tracing'):
                        pipeline = VTTKnowledgeExtractor()
                        pipeline.audio_provider = mock.Mock()  # Already initialized
                        
                        with mock.patch.object(pipeline, 'cleanup'):
                            result = pipeline.seed_podcasts([])
                            
                            assert result['podcasts_processed'] == 0
                            assert result['success'] is True
    
    def test_invalid_config_type(self):
        """Test initialization with invalid config type."""
        with mock.patch('src.seeding.orchestrator.SignalManager'):
            with mock.patch('src.seeding.orchestrator.ProviderCoordinator'):
                with mock.patch('src.seeding.orchestrator.CheckpointManager'):
                    with mock.patch('src.seeding.orchestrator.init_tracing'):
                        # Should handle dict config gracefully
                        pipeline = VTTKnowledgeExtractor(config={'key': 'value'})
                        assert pipeline.config == {'key': 'value'}