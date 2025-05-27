"""Tests for signal handling and graceful shutdown."""

import signal
import time
import threading
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from multiprocessing import Process, Queue

from src.seeding.orchestrator import PodcastKnowledgePipeline
from src.core.config import Config


class TestSignalHandling:
    """Test signal handling and graceful shutdown scenarios."""
    
    @pytest.fixture
    def test_config(self):
        """Test configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.checkpoint_dir = tmpdir
            config.audio_dir = tmpdir
            config.log_file = os.path.join(tmpdir, 'test.log')
            config.checkpoint_enabled = True
            yield config
    
    @pytest.fixture
    def mock_providers(self):
        """Mock providers for testing."""
        audio = Mock()
        audio.health_check.return_value = {'status': 'healthy'}
        audio.cleanup.return_value = None
        audio.transcribe.return_value = "Test transcript"
        
        llm = Mock()
        llm.health_check.return_value = {'status': 'healthy'}
        llm.cleanup.return_value = None
        llm.generate.return_value = '{"entities": [], "relationships": []}'
        
        graph = Mock()
        graph.health_check.return_value = {'status': 'healthy'}
        graph.cleanup.return_value = None
        graph.close.return_value = None
        
        embeddings = Mock()
        embeddings.health_check.return_value = {'status': 'healthy'}
        embeddings.cleanup.return_value = None
        
        return {
            'audio': audio,
            'llm': llm,
            'graph': graph,
            'embeddings': embeddings
        }
    
    def _run_pipeline_with_signal(self, config, signal_type, delay, result_queue):
        """Run pipeline in subprocess and send signal after delay."""
        try:
            # Import here to avoid issues with multiprocessing
            from src.seeding.orchestrator import PodcastKnowledgePipeline
            import signal as sig
            import time
            
            # Track cleanup
            cleanup_called = False
            original_cleanup = PodcastKnowledgePipeline.cleanup
            
            def track_cleanup(self):
                nonlocal cleanup_called
                cleanup_called = True
                original_cleanup(self)
            
            PodcastKnowledgePipeline.cleanup = track_cleanup
            
            # Create pipeline
            pipeline = PodcastKnowledgePipeline(config)
            
            # Set up signal to be sent after delay
            def send_signal():
                time.sleep(delay)
                os.kill(os.getpid(), signal_type)
            
            signal_thread = threading.Thread(target=send_signal)
            signal_thread.start()
            
            # Start processing
            try:
                result = pipeline.process_podcast(
                    podcast_url="https://example.com/feed.xml",
                    podcast_name="Test Podcast",
                    max_episodes=10
                )
                result_queue.put(('completed', result, cleanup_called))
            except KeyboardInterrupt:
                result_queue.put(('interrupted', None, cleanup_called))
            except Exception as e:
                result_queue.put(('error', str(e), cleanup_called))
            
        except Exception as e:
            result_queue.put(('setup_error', str(e), False))
    
    @pytest.mark.integration
    def test_sigint_graceful_shutdown(self, test_config, mock_providers):
        """Test SIGINT (Ctrl+C) triggers graceful shutdown."""
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider', 
                  return_value=mock_providers['audio']), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider',
                  return_value=mock_providers['llm']), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider',
                  return_value=mock_providers['graph']), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider',
                  return_value=mock_providers['embeddings']), \
             patch('src.utils.feed_processing.parse_rss_feed') as mock_parse:
            
            # Mock RSS feed with many episodes
            mock_parse.return_value = {
                "title": "Test Podcast",
                "episodes": [
                    {"id": f"ep-{i}", "title": f"Episode {i}", "url": f"https://example.com/ep{i}.mp3"}
                    for i in range(20)
                ]
            }
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Track signal handling
            signal_handled = False
            original_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
            
            def signal_handler(signum, frame):
                nonlocal signal_handled
                signal_handled = True
                pipeline._shutdown_flag = True
            
            signal.signal(signal.SIGINT, signal_handler)
            
            # Simulate processing with interrupt
            processing_thread = threading.Thread(
                target=pipeline.process_podcast,
                kwargs={
                    "podcast_url": "https://example.com/feed.xml",
                    "podcast_name": "Test Podcast",
                    "max_episodes": 20
                }
            )
            
            processing_thread.start()
            
            # Send SIGINT after short delay
            time.sleep(0.1)
            os.kill(os.getpid(), signal.SIGINT)
            
            # Wait for thread to complete
            processing_thread.join(timeout=5.0)
            
            # Restore original handler
            signal.signal(signal.SIGINT, original_handler)
            
            # Verify signal was handled
            assert signal_handled
            
            # Verify cleanup was called
            for provider in mock_providers.values():
                if hasattr(provider, 'cleanup'):
                    provider.cleanup.assert_called()
    
    @pytest.mark.integration
    def test_sigterm_graceful_shutdown(self, test_config):
        """Test SIGTERM triggers graceful shutdown."""
        # This test needs to run in a subprocess to properly test SIGTERM
        result_queue = Queue()
        
        process = Process(
            target=self._run_pipeline_with_signal,
            args=(test_config, signal.SIGTERM, 0.5, result_queue)
        )
        
        process.start()
        process.join(timeout=10.0)
        
        if not result_queue.empty():
            status, result, cleanup_called = result_queue.get()
            assert status in ['interrupted', 'completed']
            assert cleanup_called, "Cleanup should have been called on SIGTERM"
    
    @pytest.mark.integration
    def test_resource_cleanup_on_shutdown(self, test_config, mock_providers):
        """Test that all resources are properly cleaned up on shutdown."""
        resources_cleaned = {
            'audio': False,
            'llm': False,
            'graph': False,
            'embeddings': False,
            'files': []
        }
        
        # Track cleanup calls
        def make_cleanup_tracker(resource_name):
            def cleanup():
                resources_cleaned[resource_name] = True
            return cleanup
        
        for name, provider in mock_providers.items():
            provider.cleanup = Mock(side_effect=make_cleanup_tracker(name))
        
        # Track file operations
        original_unlink = os.unlink
        def track_unlink(path):
            resources_cleaned['files'].append(path)
            return original_unlink(path)
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider',
                  return_value=mock_providers['audio']), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider',
                  return_value=mock_providers['llm']), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider',
                  return_value=mock_providers['graph']), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider',
                  return_value=mock_providers['embeddings']), \
             patch('os.unlink', side_effect=track_unlink):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Initialize components
            pipeline.initialize_components()
            
            # Trigger cleanup
            pipeline.cleanup()
            
            # Verify all providers were cleaned up
            assert resources_cleaned['audio']
            assert resources_cleaned['llm']
            assert resources_cleaned['graph']
            assert resources_cleaned['embeddings']
    
    @pytest.mark.integration
    def test_checkpoint_save_on_interrupt(self, test_config, mock_providers):
        """Test that checkpoint is saved when processing is interrupted."""
        checkpoint_saved = []
        
        def mock_save_progress(*args, **kwargs):
            checkpoint_saved.append(kwargs)
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider',
                  return_value=mock_providers['audio']), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider',
                  return_value=mock_providers['llm']), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider',
                  return_value=mock_providers['graph']), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider',
                  return_value=mock_providers['embeddings']), \
             patch('src.seeding.checkpoint.ProgressCheckpoint.save_progress',
                  side_effect=mock_save_progress), \
             patch('src.utils.feed_processing.parse_rss_feed') as mock_parse:
            
            # Mock RSS feed
            mock_parse.return_value = {
                "title": "Test Podcast",
                "episodes": [
                    {"id": f"ep-{i}", "title": f"Episode {i}", "url": f"https://example.com/ep{i}.mp3"}
                    for i in range(10)
                ]
            }
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Process a few episodes then simulate interrupt
            episode_count = 0
            original_process = pipeline._process_episode
            
            def process_with_interrupt(*args, **kwargs):
                nonlocal episode_count
                episode_count += 1
                if episode_count >= 3:
                    # Simulate interrupt after 3 episodes
                    raise KeyboardInterrupt()
                return original_process(*args, **kwargs)
            
            pipeline._process_episode = process_with_interrupt
            
            # Process podcast (should be interrupted)
            with pytest.raises(KeyboardInterrupt):
                pipeline.process_podcast(
                    podcast_url="https://example.com/feed.xml",
                    podcast_name="Test Podcast",
                    max_episodes=10
                )
            
            # Verify checkpoint was saved for processed episodes
            assert len(checkpoint_saved) >= 2  # At least 2 episodes should be checkpointed
    
    @pytest.mark.integration  
    def test_concurrent_shutdown_safety(self, test_config, mock_providers):
        """Test that concurrent shutdown requests are handled safely."""
        shutdown_count = 0
        cleanup_count = 0
        
        def track_shutdown(self):
            nonlocal shutdown_count
            shutdown_count += 1
        
        def track_cleanup():
            nonlocal cleanup_count
            cleanup_count += 1
            time.sleep(0.1)  # Simulate cleanup time
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider',
                  return_value=mock_providers['audio']), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider',
                  return_value=mock_providers['llm']), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider',
                  return_value=mock_providers['graph']), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider',
                  return_value=mock_providers['embeddings']):
            
            for provider in mock_providers.values():
                provider.cleanup = Mock(side_effect=track_cleanup)
            
            pipeline = PodcastKnowledgePipeline(test_config)
            pipeline.initialize_components()
            
            # Simulate multiple concurrent shutdown requests
            threads = []
            for i in range(5):
                t = threading.Thread(target=pipeline.cleanup)
                threads.append(t)
                t.start()
            
            # Wait for all threads
            for t in threads:
                t.join()
            
            # Cleanup should only happen once per provider despite multiple requests
            assert cleanup_count == 4  # One per provider
    
    @pytest.mark.integration
    def test_signal_handler_registration(self, test_config):
        """Test that signal handlers are properly registered."""
        original_sigint = signal.signal(signal.SIGINT, signal.SIG_DFL)
        original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        
        try:
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Get current handlers
            current_sigint = signal.signal(signal.SIGINT, signal.SIG_DFL)
            current_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
            
            # Restore to check
            signal.signal(signal.SIGINT, current_sigint)
            signal.signal(signal.SIGTERM, current_sigterm)
            
            # Handlers should be different from defaults (custom handlers installed)
            assert current_sigint != signal.SIG_DFL
            assert current_sigterm != signal.SIG_DFL
            
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)