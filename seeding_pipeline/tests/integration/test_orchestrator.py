"""Integration tests for the pipeline orchestrator."""

from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

import pytest

from src.core.config import SeedingConfig
from src.core.exceptions import PipelineError
from src.seeding.orchestrator import VTTKnowledgeExtractor
@pytest.fixture
def mock_providers():
    """Create mock providers for testing."""
    audio_provider = Mock()
    audio_provider.health_check.return_value = {'status': 'healthy'}
    audio_provider.transcribe.return_value = "Test transcript"
    audio_provider.diarize.return_value = []
    
    llm_provider = Mock()
    llm_provider.health_check.return_value = {'status': 'healthy'}
    llm_provider.generate.return_value = '{"insights": [], "entities": []}'
    
    graph_provider = Mock()
    graph_provider.health_check.return_value = {'status': 'healthy'}
    graph_provider.create_node.return_value = True
    graph_provider.create_relationship.return_value = True
    
    embedding_provider = Mock()
    embedding_provider.health_check.return_value = {'status': 'healthy'}
    embedding_provider.embed.return_value = [0.1] * 384
    
    return {
        'audio': audio_provider,
        'llm': llm_provider,
        'graph': graph_provider,
        'embedding': embedding_provider
    }


@pytest.fixture
def test_config(monkeypatch):
    """Create test configuration."""
    # Set required environment variables
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "test_password")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_api_key")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SeedingConfig()
        config.checkpoint_dir = tmpdir
        config.audio_dir = tmpdir
        config.log_file = os.path.join(tmpdir, 'test.log')
        config.delete_audio_after_processing = True
        yield config


@pytest.fixture
def mock_podcast_feed():
    """Create mock podcast feed data."""
    return {
        'id': 'test-podcast',
        'title': 'Test Podcast',
        'description': 'A test podcast',
        'episodes': [
            {
                'id': 'ep1',
                'title': 'Episode 1',
                'description': 'First episode',
                'audio_url': 'https://example.com/ep1.mp3',
                'published_date': '2023-01-01'
            }
        ]
    }


@pytest.fixture
def mock_segments():
    """Create mock segment data."""
    return [
        {
            'text': 'This is segment one.',
            'start': 0.0,
            'end': 10.0,
            'speaker': 'Speaker 1'
        },
        {
            'text': 'This is segment two.',
            'start': 10.0,
            'end': 20.0,
            'speaker': 'Speaker 2'
        }
    ]


class TestPodcastKnowledgePipeline:
    """Integration tests for VTTKnowledgeExtractor."""
    
    def test_pipeline_initialization(self, test_config):
        """Test pipeline initialization."""
        pipeline = VTTKnowledgeExtractor(test_config)
        assert pipeline.config == test_config
        assert pipeline.factory is not None
        assert pipeline._shutdown_requested is False
    
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_initialize_components(self, mock_factory, test_config, mock_providers):
        """Test component initialization."""
        # Configure factory mock
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        pipeline = VTTKnowledgeExtractor(test_config)
        result = pipeline.initialize_components()
        
        assert result is True
        assert pipeline.audio_provider is not None
        assert pipeline.llm_provider is not None
        assert pipeline.graph_provider is not None
        assert pipeline.embedding_provider is not None
        assert pipeline.segmenter is not None
        assert pipeline.knowledge_extractor is not None
    
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_component_health_check_failure(self, mock_factory, test_config, mock_providers):
        """Test handling of unhealthy components."""
        # Make one provider unhealthy
        mock_providers['llm'].health_check.return_value = {'status': 'unhealthy', 'error': 'Connection failed'}
        
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        pipeline = VTTKnowledgeExtractor(test_config)
        result = pipeline.initialize_components()
        
        assert result is False
    
    @patch('src.seeding.components.pipeline_executor.download_episode_audio')
    @patch('src.seeding.orchestrator.fetch_podcast_feed')
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_seed_single_podcast(self, mock_factory, mock_fetch_feed, mock_download, 
                                test_config, mock_providers, mock_podcast_feed,
                                mock_segments):
        """Test seeding a single podcast."""
        # Configure mocks
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        mock_fetch_feed.return_value = mock_podcast_feed
        mock_download.return_value = '/tmp/test_audio.mp3'
        
        # Configure segmenter mock
        mock_segmenter = Mock()
        mock_segmenter.process_audio.return_value = mock_segments
        
        # Configure extractor mock
        mock_extractor = Mock()
        mock_extractor.extract_from_segments.return_value = {
            'insights': [{'id': 'i1', 'title': 'Test Insight', 'description': 'Test'}],
            'entities': [{'id': 'e1', 'name': 'Test Entity', 'type': 'PERSON'}],
            'quotes': []
        }
        
        # Configure resolver mock
        mock_resolver = Mock()
        mock_resolver.resolve_entities.return_value = [
            {'id': 'e1', 'name': 'Test Entity', 'type': 'PERSON'}
        ]
        
        pipeline = VTTKnowledgeExtractor(test_config)
        pipeline.initialize_components()
        
        # Inject mocked components
        with patch.object(pipeline, 'segmenter', mock_segmenter), \
             patch.object(pipeline, 'knowledge_extractor', mock_extractor), \
             patch.object(pipeline, 'entity_resolver', mock_resolver):
            
            podcast_config = {
                'id': 'test-podcast',
                'name': 'Test Podcast',
                'rss_url': 'https://example.com/feed.rss'
            }
            
            result = pipeline.seed_podcast(podcast_config, max_episodes=1)
            
            assert result['podcasts_processed'] == 1
            assert result['episodes_processed'] == 1
            assert result['episodes_failed'] == 0
            assert result['total_segments'] == 2
            assert result['total_insights'] == 1
            assert result['total_entities'] == 1
            assert result['success'] is True
    
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_cleanup(self, mock_factory, test_config, mock_providers):
        """Test cleanup functionality."""
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        pipeline = VTTKnowledgeExtractor(test_config)
        pipeline.initialize_components()
        
        # Call cleanup
        pipeline.cleanup()
        
        # Verify all providers were closed
        for provider in mock_providers.values():
            provider.close.assert_called_once()
    
    def test_graceful_shutdown(self, test_config):
        """Test graceful shutdown handling."""
        pipeline = VTTKnowledgeExtractor(test_config)
        
        # Simulate shutdown request
        pipeline._shutdown_requested = True
        
        # Try to process podcasts
        result = pipeline.seed_podcasts([], max_episodes_each=10)
        
        # Should return immediately without processing
        assert result['podcasts_processed'] == 0
        assert result['episodes_processed'] == 0
    
    @patch('src.seeding.components.pipeline_executor.download_episode_audio')
    @patch('src.seeding.orchestrator.fetch_podcast_feed')
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_error_handling(self, mock_factory, mock_fetch_feed, mock_download,
                          test_config, mock_providers):
        """Test error handling during processing."""
        # Configure mocks
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        # Make fetch_feed raise an error
        mock_fetch_feed.side_effect = Exception("Feed parsing error")
        
        pipeline = VTTKnowledgeExtractor(test_config)
        
        podcast_config = {
            'id': 'test-podcast',
            'rss_url': 'https://example.com/feed.rss'
        }
        
        result = pipeline.seed_podcasts([podcast_config], max_episodes_each=1)
        
        assert result['podcasts_processed'] == 0
        assert len(result['errors']) == 1
        assert 'Feed parsing error' in result['errors'][0]['error']
        assert result['success'] is False
    
    @patch('src.seeding.orchestrator.ProviderFactory')
    def test_checkpoint_recovery(self, mock_factory, test_config, mock_providers):
        """Test checkpoint recovery functionality."""
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        mock_factory_instance.create_provider.side_effect = lambda ptype, *args, **kwargs: mock_providers[ptype]
        
        pipeline = VTTKnowledgeExtractor(test_config)
        
        # Mock checkpoint with completed episode
        with patch.object(pipeline.checkpoint, 'get_completed_episodes', return_value=['ep1']):
            # This episode should be skipped
            result = pipeline._process_episode(
                {'id': 'test-podcast'},
                {'id': 'ep1', 'title': 'Completed Episode'},
                use_large_context=True
            )
            
            assert result['segments'] == 0
            assert result['insights'] == 0
            assert result['entities'] == 0
    
    def test_logging_configuration(self, test_config):
        """Test logging configuration."""
        import logging
        
        # Set custom log level
        test_config.log_level = 'DEBUG'
        
        pipeline = VTTKnowledgeExtractor(test_config)
        
        # Check that logging was configured
        assert logging.getLogger().level == logging.DEBUG
        
        # Check file handler was added if log_file specified
        handlers = logging.getLogger().handlers
        file_handlers = [h for h in handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0


class TestPipelineIntegration:
    """End-to-end integration tests."""
    
    @pytest.mark.integration
    def test_full_pipeline_with_mock_data(self, test_config):
        """Test full pipeline execution with all mocked components."""
        # This test would require more setup but demonstrates the pattern
        # for full integration testing
        pass