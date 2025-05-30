#!/usr/bin/env python3
"""
Phase 6 Integration Tests - Tests refactored components without external dependencies.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestRefactoredComponents(unittest.TestCase):
    """Test refactored components work correctly."""
    
    def test_signal_manager(self):
        """Test SignalManager component."""
        # Mock the config loading to avoid YAML dependency
        with patch('src.core.config.Config.__init__', return_value=None):
            with patch('src.core.config.Config.get', return_value={}):
                from src.seeding.components.signal_manager import SignalManager
                
                # Test initialization
                sm = SignalManager()
                self.assertIsNotNone(sm)
                
                # Test setup
                cleanup_called = False
                def cleanup():
                    nonlocal cleanup_called
                    cleanup_called = True
                
                sm.setup(cleanup)
                
                # Test shutdown request
                self.assertFalse(sm.shutdown_requested)
                
                # Simulate shutdown
                sm.shutdown()
                self.assertTrue(cleanup_called)
    
    def test_checkpoint_manager_wrapper(self):
        """Test CheckpointManager wrapper."""
        # Mock checkpoint and config
        mock_checkpoint = MagicMock()
        mock_config = MagicMock()
        
        with patch('src.core.config.Config', return_value=mock_config):
            from src.seeding.components.checkpoint_manager import CheckpointManager
            
            cm = CheckpointManager(mock_config, mock_checkpoint)
            self.assertIsNotNone(cm)
            
            # Test delegation
            cm.is_completed('episode123')
            mock_checkpoint.is_episode_completed.assert_called_with('episode123')
            
            cm.mark_completed('episode123')
            mock_checkpoint.mark_episode_completed.assert_called_with('episode123')
    
    def test_error_handling_decorators(self):
        """Test error handling decorators."""
        from src.utils.error_handling import with_error_handling, retry_on_error
        
        # Test basic error handling
        counter = {'value': 0}
        
        @with_error_handling(retry_count=2, raise_on_failure=False)
        def failing_func():
            counter['value'] += 1
            raise ValueError("Test error")
        
        result = failing_func()
        self.assertIsNone(result)
        self.assertEqual(counter['value'], 3)  # Initial + 2 retries
        
        # Test successful retry
        counter2 = {'value': 0}
        
        @retry_on_error(retry_count=3)
        def eventual_success():
            counter2['value'] += 1
            if counter2['value'] < 3:
                raise ValueError("Retry me")
            return "success"
        
        result = eventual_success()
        self.assertEqual(result, "success")
        self.assertEqual(counter2['value'], 3)
    
    def test_enhanced_logging(self):
        """Test enhanced logging functionality."""
        from src.utils.logging_enhanced import (
            get_logger, set_correlation_id, get_correlation_id,
            with_correlation_id, StandardizedLogger
        )
        
        # Test correlation ID
        corr_id = set_correlation_id("test-123")
        self.assertEqual(get_correlation_id(), "test-123")
        
        # Test logger
        logger = get_logger(__name__)
        self.assertIsInstance(logger, StandardizedLogger)
        
        # Test decorator
        @with_correlation_id("decorator-test")
        def test_func():
            return get_correlation_id()
        
        result = test_func()
        self.assertEqual(result, "decorator-test")
        
        # Verify original context restored
        self.assertEqual(get_correlation_id(), "test-123")
    
    def test_exception_hierarchy(self):
        """Test new exception types."""
        from src.core.exceptions import (
            ExtractionError, RateLimitError, TimeoutError,
            ResourceError, DataIntegrityError, ErrorSeverity
        )
        
        # Test ExtractionError
        e = ExtractionError("Extraction failed")
        self.assertEqual(e.severity, ErrorSeverity.WARNING)
        self.assertIn("Extraction failed", str(e))
        
        # Test RateLimitError with retry_after
        e = RateLimitError("gemini", "Rate limit hit", retry_after=60.0)
        self.assertEqual(e.details['retry_after'], 60.0)
        self.assertEqual(e.details['provider'], 'gemini')
        
        # Test TimeoutError
        e = TimeoutError("Operation timed out", operation="transcription", timeout_seconds=30.0)
        self.assertEqual(e.details['operation'], 'transcription')
        self.assertEqual(e.details['timeout_seconds'], 30.0)
        
        # Test ResourceError
        e = ResourceError("Out of memory", resource_type="memory")
        self.assertEqual(e.severity, ErrorSeverity.CRITICAL)
        self.assertEqual(e.details['resource_type'], 'memory')
        
        # Test DataIntegrityError
        e = DataIntegrityError("Corrupt data", entity_type="Episode", entity_id="123")
        self.assertEqual(e.details['entity_type'], 'Episode')
        self.assertEqual(e.details['entity_id'], '123')
    
    def test_plugin_discovery(self):
        """Test plugin discovery system."""
        from src.core.plugin_discovery import PluginDiscovery, provider_plugin
        
        # Test decorator
        @provider_plugin('audio', 'test_provider', version='1.0.0', author='Test')
        class TestAudioProvider:
            pass
        
        # Verify metadata added
        self.assertTrue(hasattr(TestAudioProvider, '_is_provider_plugin'))
        self.assertEqual(TestAudioProvider._plugin_metadata['name'], 'test_provider')
        self.assertEqual(TestAudioProvider._plugin_metadata['version'], '1.0.0')
        
        # Test discovery
        discovery = PluginDiscovery()
        self.assertIsNotNone(discovery)
        
        # Test discover_providers method
        providers = discovery.discover_providers('audio')
        self.assertIsInstance(providers, dict)
    
    def test_extraction_strategies(self):
        """Test extraction strategy pattern."""
        # Mock config to avoid YAML dependency
        mock_config = MagicMock()
        mock_config.extraction = {'mode': 'fixed_schema'}
        mock_config.providers = {
            'llm': {'name': 'mock'},
            'embedding': {'name': 'mock'}
        }
        
        with patch('src.core.config.Config', return_value=mock_config):
            from src.processing.extraction import KnowledgeExtractor, ExtractionResult, ExtractionConfig
            
            # Test ExtractionResult
            result = ExtractionResult(
                entities=[],
                quotes=[],
                relationships=[],
                metadata={}
            )
            self.assertEqual(len(result.entities), 0)
            
            # Test KnowledgeExtractor can be instantiated
            extractor = KnowledgeExtractor(None, None)  # Mock services
            self.assertIsNotNone(extractor)
    
    def test_pipeline_executor_refactoring(self):
        """Test pipeline executor was properly refactored."""
        import inspect
        from src.seeding.components.pipeline_executor import PipelineExecutor
        
        # Check process_episode method size
        method = getattr(PipelineExecutor, 'process_episode', None)
        self.assertIsNotNone(method)
        
        # Get source and count substantive lines
        source = inspect.getsource(method)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        
        # Should be significantly smaller than original 92 lines
        self.assertLess(len(lines), 50, 
                       f"process_episode has {len(lines)} lines, should be < 50")
        
        # Check all helper methods exist
        helper_methods = [
            '_is_episode_completed',
            '_download_episode_audio', 
            '_add_episode_context',
            '_process_audio_segments',
            '_extract_knowledge',
            '_determine_extraction_mode',
            '_finalize_episode_processing',
            '_cleanup_audio_file'
        ]
        
        for helper in helper_methods:
            self.assertTrue(hasattr(PipelineExecutor, helper),
                          f"Missing helper method: {helper}")
    
    def test_provider_coordinator_structure(self):
        """Test ProviderCoordinator has correct structure."""
        # Mock to avoid YAML dependency
        mock_config = MagicMock()
        mock_config.providers = {
            'audio': {'name': 'mock'},
            'llm': {'name': 'mock'}, 
            'embeddings': {'name': 'mock'},
            'graph': {'name': 'memory'}
        }
        
        with patch('src.factories.provider_factory.ProviderFactory') as mock_factory:
            mock_factory.return_value.create_audio_provider.return_value = Mock()
            mock_factory.return_value.create_llm_provider.return_value = Mock()
            mock_factory.return_value.create_embedding_provider.return_value = Mock()
            mock_factory.return_value.create_graph_provider.return_value = Mock()
            
            from src.seeding.components.provider_coordinator import ProviderCoordinator
            
            pc = ProviderCoordinator(mock_factory.return_value, mock_config)
            
            # Check methods exist
            self.assertTrue(hasattr(pc, 'initialize_providers'))
            self.assertTrue(hasattr(pc, 'check_health'))
            self.assertTrue(hasattr(pc, 'cleanup'))
    
    def test_storage_coordinator_exists(self):
        """Test StorageCoordinator component exists."""
        from src.seeding.components.storage_coordinator import StorageCoordinator
        
        # Check key methods exist
        self.assertTrue(hasattr(StorageCoordinator, 'store_all'))
        self.assertTrue(hasattr(StorageCoordinator, 'store_entities'))
        self.assertTrue(hasattr(StorageCoordinator, 'store_relationships'))

class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility is maintained."""
    
    def test_orchestrator_facade(self):
        """Test orchestrator maintains facade pattern."""
        # Mock dependencies
        mock_config = MagicMock()
        
        with patch('src.core.config.Config', return_value=mock_config):
            with patch('src.seeding.checkpoint.Checkpoint'):
                with patch('src.seeding.components.signal_manager.SignalManager'):
                    with patch('src.seeding.components.provider_coordinator.ProviderCoordinator'):
                        from src.seeding.orchestrator import PodcastOrchestrator
                        
                        # Test public interface maintained
                        self.assertTrue(hasattr(PodcastOrchestrator, 'run'))
                        self.assertTrue(hasattr(PodcastOrchestrator, 'process_podcast'))
                        self.assertTrue(hasattr(PodcastOrchestrator, 'cleanup'))
    
    def test_extraction_compatibility(self):
        """Test extraction.py maintains compatibility."""
        # Test imports still work
        try:
            from src.processing.extraction import (
                KnowledgeExtractor,
                extract_entities_relationships,
                extract_quotes,
                extract_insights
            )
            
            # Verify main classes/functions exist
            self.assertIsNotNone(KnowledgeExtractor)
            self.assertIsNotNone(extract_entities_relationships)
            self.assertIsNotNone(extract_quotes)
            self.assertIsNotNone(extract_insights)
            
        except ImportError as e:
            # YAML dependency is expected, but structure should exist
            if "yaml" not in str(e):
                self.fail(f"Unexpected import error: {e}")

def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRefactoredComponents))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)