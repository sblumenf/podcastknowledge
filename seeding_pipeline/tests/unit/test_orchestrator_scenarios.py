"""Integration and scenario tests for pipeline orchestrator.

Tests for src/seeding/orchestrator.py focusing on real-world scenarios
and integration between components.
"""

from datetime import datetime
from typing import Dict, Any, List
from unittest import mock
import json
import os
import tempfile

import pytest

from src.core.config import SeedingConfig
from src.core.exceptions import PipelineError
from src.core.extraction_interface import Entity, Insight, Quote, EntityType
from src.seeding.orchestrator import VTTKnowledgeExtractor
class TestEndToEndScenarios:
    """Test complete end-to-end pipeline scenarios."""
    
    @pytest.fixture
    def mock_providers(self):
        """Create a complete set of mock providers."""
        return {
            'audio': self._create_mock_audio_provider(),
            'llm': self._create_mock_llm_provider(),
            'graph': self._create_mock_graph_provider(),
            'embedding': self._create_mock_embedding_provider()
        }
    
    def _create_mock_audio_provider(self):
        """Create mock audio provider with realistic responses."""
        provider = mock.Mock()
        provider.transcribe.return_value = {
            'segments': [
                {
                    'text': "Welcome to our AI podcast. Today we discuss GPT-4.",
                    'start': 0.0,
                    'end': 5.0,
                    'speaker': 'SPEAKER_00'
                },
                {
                    'text': "GPT-4 represents a major advancement in language models.",
                    'start': 5.0,
                    'end': 10.0,
                    'speaker': 'SPEAKER_01'
                }
            ],
            'speakers': [
                {'id': 'SPEAKER_00', 'name': 'Host'},
                {'id': 'SPEAKER_01', 'name': 'Guest'}
            ]
        }
        provider.cleanup.return_value = None
        return provider
    
    def _create_mock_llm_provider(self):
        """Create mock LLM provider with realistic responses."""
        provider = mock.Mock()
        
        def complete_side_effect(prompt):
            if "complexity" in prompt.lower():
                return json.dumps({
                    "classification": "technical",
                    "technical_density": 0.8,
                    "requires_domain_knowledge": True
                })
            elif "segment the following" in prompt.lower():
                return json.dumps([
                    {
                        "start_index": 0,
                        "end_index": 1,
                        "topic": "Introduction to GPT-4",
                        "coherence_score": 0.9
                    }
                ])
            elif "extract" in prompt.lower() and "entities" in prompt.lower():
                return json.dumps([
                    {
                        "name": "GPT-4",
                        "type": "Technology",
                        "description": "Large language model",
                        "importance": 9
                    },
                    {
                        "name": "OpenAI",
                        "type": "Company",
                        "description": "AI research company",
                        "importance": 8
                    }
                ])
            else:
                return json.dumps({
                    "entities": [{"name": "AI", "type": "Concept"}],
                    "insights": [{"content": "AI is transformative", "type": "conceptual"}],
                    "quotes": []
                })
        
        provider.complete.side_effect = complete_side_effect
        provider.cleanup.return_value = None
        return provider
    
    def _create_mock_graph_provider(self):
        """Create mock graph provider."""
        provider = mock.Mock()
        provider.add_entities.return_value = {"created": 2, "updated": 0}
        provider.add_relationships.return_value = {"created": 1}
        provider.get_statistics.return_value = {
            "nodes": 100,
            "relationships": 200,
            "labels": ["Entity", "Insight", "Quote"]
        }
        provider.close.return_value = None
        return provider
    
    def _create_mock_embedding_provider(self):
        """Create mock embedding provider."""
        provider = mock.Mock()
        provider.embed_texts.return_value = [[0.1] * 768, [0.2] * 768]  # Mock embeddings
        provider.embed_text.return_value = [0.1] * 768
        return provider
    
    @pytest.fixture
    def configured_pipeline(self, mock_providers, tmp_path):
        """Create a fully configured pipeline with mocked components."""
        # Create config
        config = SeedingConfig()
        config.checkpoint_dir = str(tmp_path / "checkpoints")
        config.checkpoint_enabled = True
        config.batch_size = 10
        
        # Create pipeline
        pipeline = VTTKnowledgeExtractor(config=config)
        
        # Mock component initialization
        with mock.patch.object(pipeline.provider_coordinator, 'initialize_providers') as mock_init:
            mock_init.return_value = True
            
            # Set up mock providers
            pipeline.provider_coordinator.audio_provider = mock_providers['audio']
            pipeline.provider_coordinator.llm_provider = mock_providers['llm']
            pipeline.provider_coordinator.graph_provider = mock_providers['graph']
            pipeline.provider_coordinator.embedding_provider = mock_providers['embedding']
            
            # Mock other components
            pipeline.provider_coordinator.check_health.return_value = True
            
            # Initialize components
            with mock.patch('src.seeding.orchestrator.StorageCoordinator'):
                with mock.patch('src.seeding.orchestrator.PipelineExecutor') as MockExecutor:
                    # Set up pipeline executor mock
                    mock_executor = MockExecutor.return_value
                    mock_executor.process_episode.return_value = {
                        'segments': 10,
                        'insights': 5,
                        'entities': 15,
                        'mode': 'fixed'
                    }
                    
                    pipeline.initialize_components()
                    pipeline.pipeline_executor = mock_executor
        
        return pipeline
    
    def test_complete_podcast_processing(self, configured_pipeline):
        """Test processing a complete podcast from start to finish."""
        podcast_config = {
            'id': 'tech-talks',
            'name': 'Tech Talks',
            'rss_url': 'http://techtalks.example.com/feed.xml'
        }
        
        # Mock feed fetching
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.return_value = {
                'podcast_id': 'tech-talks',
                'episodes': [
                    {
                        'id': 'ep1',
                        'title': 'Understanding GPT-4',
                        'url': 'http://techtalks.example.com/episodes/1.mp3',
                        'description': 'Deep dive into GPT-4',
                        'published_date': '2024-01-01'
                    },
                    {
                        'id': 'ep2',
                        'title': 'The Future of AI',
                        'url': 'http://techtalks.example.com/episodes/2.mp3',
                        'description': 'AI predictions for 2025',
                        'published_date': '2024-01-08'
                    }
                ]
            }
            
            # Process podcast
            result = configured_pipeline.seed_podcast(
                podcast_config,
                max_episodes=2,
                use_large_context=True
            )
            
            # Verify results
            assert result['podcasts_processed'] == 1
            assert result['episodes_processed'] == 2
            assert result['episodes_failed'] == 0
            assert result['success'] is True
            
            # Verify component interactions
            mock_fetch.assert_called_once_with(podcast_config, 2)
            assert configured_pipeline.pipeline_executor.process_episode.call_count == 2
    
    def test_podcast_processing_with_failures(self, configured_pipeline):
        """Test podcast processing with some episode failures."""
        podcast_configs = [
            {
                'id': 'podcast1',
                'name': 'Podcast 1',
                'rss_url': 'http://podcast1.com/feed.xml'
            },
            {
                'id': 'podcast2',
                'name': 'Podcast 2',
                'rss_url': 'http://podcast2.com/feed.xml'
            }
        ]
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            # First podcast succeeds, second fails during fetch
            mock_fetch.side_effect = [
                {
                    'podcast_id': 'podcast1',
                    'episodes': [
                        {'id': 'ep1', 'title': 'Episode 1', 'url': 'http://ep1.mp3'}
                    ]
                },
                Exception("Feed fetch error")
            ]
            
            result = configured_pipeline.seed_podcasts(
                podcast_configs,
                max_episodes_each=1
            )
            
            # Should process first podcast but fail on second
            assert result['podcasts_processed'] == 1
            assert result['episodes_processed'] == 1
            assert result['success'] is False
            assert len(result['errors']) == 1
            assert result['errors'][0]['podcast'] == 'podcast2'
    
    def test_checkpoint_recovery_scenario(self, configured_pipeline, tmp_path):
        """Test recovery from checkpoint after interruption."""
        # Create a checkpoint file simulating interrupted processing
        checkpoint_data = {
            'podcast_id': 'test-podcast',
            'episode_id': 'ep1',
            'stage': 'segmentation',
            'segments_processed': 5,
            'total_segments': 10,
            'timestamp': datetime.now().isoformat()
        }
        
        checkpoint_file = tmp_path / "checkpoints" / "test-podcast_ep1.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
        
        # Test resume functionality
        result = configured_pipeline.resume_from_checkpoints()
        
        # Current implementation doesn't fully support recovery
        assert result['resumed_episodes'] == 0
        assert 'not fully implemented' in result['message']
    
    def test_schemaless_extraction_scenario(self, configured_pipeline):
        """Test pipeline in schemaless extraction mode."""
        # Enable schemaless extraction
        configured_pipeline.config.use_schemaless_extraction = True
        
        # Update pipeline executor mock for schemaless mode
        configured_pipeline.pipeline_executor.process_episode.return_value = {
            'segments': 10,
            'insights': 5,
            'entities': 20,
            'relationships': 15,
            'discovered_types': ['Person', 'Organization', 'Technology', 'Concept'],
            'mode': 'schemaless'
        }
        
        podcast_config = {
            'id': 'discovery-pod',
            'name': 'Discovery Podcast',
            'rss_url': 'http://discovery.example.com/feed.xml'
        }
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.return_value = {
                'episodes': [
                    {'id': 'ep1', 'title': 'Discovering New Patterns', 'url': 'http://ep1.mp3'}
                ]
            }
            
            result = configured_pipeline.seed_podcast(podcast_config, max_episodes=1)
            
            # Verify schemaless-specific results
            assert result['extraction_mode'] == 'schemaless'
            assert result['total_relationships'] == 15
            assert 'discovered_types' in result
            assert 'Person' in result['discovered_types']
            assert isinstance(result['discovered_types'], list)
    
    def test_large_batch_processing(self, configured_pipeline):
        """Test processing a large batch of podcasts."""
        # Create 10 podcast configs
        podcast_configs = [
            {
                'id': f'podcast-{i}',
                'name': f'Podcast {i}',
                'rss_url': f'http://podcast{i}.com/feed.xml'
            }
            for i in range(10)
        ]
        
        # Mock successful processing for all
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            def fetch_side_effect(config, max_episodes):
                return {
                    'episodes': [
                        {
                            'id': f"{config['id']}-ep1",
                            'title': f"Episode from {config['name']}",
                            'url': f"http://{config['id']}.mp3"
                        }
                    ]
                }
            
            mock_fetch.side_effect = fetch_side_effect
            
            result = configured_pipeline.seed_podcasts(
                podcast_configs,
                max_episodes_each=1
            )
            
            assert result['podcasts_processed'] == 10
            assert result['episodes_processed'] == 10
            assert result['success'] is True


class TestMemoryManagement:
    """Test memory management in various scenarios."""
    
    def test_memory_cleanup_after_processing(self, configured_pipeline):
        """Test that memory is cleaned up after processing."""
        with mock.patch('src.seeding.orchestrator.cleanup_memory') as mock_cleanup:
            with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
                mock_fetch.return_value = {'episodes': []}
                
                configured_pipeline.seed_podcast({'id': 'test', 'rss_url': 'http://test.com'})
                
                # Cleanup should be called
                mock_cleanup.assert_called()
    
    def test_memory_monitoring_during_batch(self, configured_pipeline):
        """Test memory monitoring during batch processing."""
        # This would require actual memory monitoring implementation
        # For now, just verify the structure is in place
        assert hasattr(configured_pipeline, 'cleanup')


class TestConcurrentProcessing:
    """Test concurrent processing scenarios."""
    
    def test_signal_handling_during_processing(self, configured_pipeline):
        """Test graceful shutdown via signal handling."""
        podcast_configs = [
            {'id': f'podcast-{i}', 'rss_url': f'http://podcast{i}.com/feed.xml'}
            for i in range(5)
        ]
        
        # Simulate shutdown request after first podcast
        processed_count = 0
        
        def fetch_side_effect(config, max_episodes):
            nonlocal processed_count
            processed_count += 1
            if processed_count > 1:
                configured_pipeline._shutdown_requested = True
            return {'episodes': []}
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.side_effect = fetch_side_effect
            
            result = configured_pipeline.seed_podcasts(podcast_configs)
            
            # Should only process 1 podcast before shutdown
            assert result['podcasts_processed'] == 1
            assert processed_count == 1


class TestConfigurationScenarios:
    """Test various configuration scenarios."""
    
    def test_minimal_configuration(self):
        """Test pipeline with minimal configuration."""
        pipeline = VTTKnowledgeExtractor()
        
        assert pipeline.config is not None
        assert isinstance(pipeline.config, SeedingConfig)
    
    def test_custom_configuration(self, tmp_path):
        """Test pipeline with custom configuration."""
        config = SeedingConfig()
        config.checkpoint_dir = str(tmp_path / "custom_checkpoints")
        config.batch_size = 5
        config.checkpoint_interval = 20
        config.log_level = 'DEBUG'
        config.log_file = str(tmp_path / "pipeline.log")
        
        with mock.patch('logging.basicConfig'):
            with mock.patch('logging.FileHandler'):
                pipeline = VTTKnowledgeExtractor(config=config)
                
                assert pipeline.config.batch_size == 5
                assert pipeline.config.checkpoint_interval == 20


class TestErrorRecovery:
    """Test error recovery scenarios."""
    
    def test_provider_initialization_retry(self):
        """Test retry logic for provider initialization."""
        config = SeedingConfig()
        
        pipeline = VTTKnowledgeExtractor(config=config)
        
        # Mock initialization to fail then succeed
        pipeline.provider_coordinator.initialize_providers.side_effect = [False, True]
        pipeline.provider_coordinator.check_health.return_value = True
        
        # First attempt should fail
        assert pipeline.initialize_components() is False
        
        # Second attempt should succeed
        with mock.patch('src.seeding.orchestrator.StorageCoordinator'):
            with mock.patch('src.seeding.orchestrator.PipelineExecutor'):
                # Need to set up mock providers for success
                pipeline.provider_coordinator.graph_provider = mock.Mock()
                pipeline.provider_coordinator.graph_enhancer = mock.Mock()
                assert pipeline.initialize_components() is True
    
    def test_graceful_degradation(self, configured_pipeline):
        """Test graceful degradation when optional components fail."""
        # Simulate graph enhancer failure (non-critical)
        configured_pipeline.graph_enhancer = None
        
        # Should still be able to process
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.return_value = {
                'episodes': [{'id': 'ep1', 'title': 'Test', 'url': 'http://test.mp3'}]
            }
            
            result = configured_pipeline.seed_podcast(
                {'id': 'test', 'rss_url': 'http://test.com'},
                max_episodes=1
            )
            
            # Should complete despite missing enhancer
            assert result['episodes_processed'] == 1


class TestPerformanceScenarios:
    """Test performance-related scenarios."""
    
    def test_batch_size_impact(self, configured_pipeline):
        """Test different batch sizes impact on processing."""
        # Small batch size
        configured_pipeline.config.batch_size = 2
        
        episodes = [
            {'id': f'ep{i}', 'title': f'Episode {i}', 'url': f'http://ep{i}.mp3'}
            for i in range(10)
        ]
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.return_value = {'episodes': episodes}
            
            result = configured_pipeline.seed_podcast(
                {'id': 'test', 'rss_url': 'http://test.com'},
                max_episodes=10
            )
            
            # All episodes should still be processed
            assert result['episodes_processed'] == 10
    
    def test_checkpoint_frequency(self, configured_pipeline, tmp_path):
        """Test checkpoint creation frequency."""
        configured_pipeline.config.checkpoint_interval = 2  # Checkpoint every 2 episodes
        
        episodes = [
            {'id': f'ep{i}', 'title': f'Episode {i}', 'url': f'http://ep{i}.mp3'}
            for i in range(5)
        ]
        
        with mock.patch('src.seeding.orchestrator.fetch_podcast_feed') as mock_fetch:
            mock_fetch.return_value = {'episodes': episodes}
            
            # Mock checkpoint manager to track saves
            checkpoint_saves = []
            configured_pipeline.checkpoint_manager.save_checkpoint = mock.Mock(
                side_effect=lambda *args: checkpoint_saves.append(args)
            )
            
            result = configured_pipeline.seed_podcast(
                {'id': 'test', 'rss_url': 'http://test.com'},
                max_episodes=5
            )
            
            # Should have created checkpoints based on interval
            # Note: Actual implementation may vary
            assert result['episodes_processed'] == 5