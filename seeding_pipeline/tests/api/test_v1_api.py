"""Tests for API v1 functionality and versioning."""

from unittest.mock import Mock, patch, MagicMock
import warnings

import pytest

from src.api.v1 import (
    seed_podcast,
    seed_podcasts,
    VTTKnowledgeExtractor,
    get_api_version,
    check_api_compatibility,
    deprecated,
    api_version_check,
)
from src.core.config import Config


class TestAPIVersioning:
    """Test API versioning functionality."""
    
    def test_get_api_version(self):
        """Test getting API version."""
        version = get_api_version()
        assert version == "1.0.0"
        assert isinstance(version, str)
        assert len(version.split('.')) == 3
    
    def test_check_api_compatibility_exact(self):
        """Test API compatibility with exact version."""
        assert check_api_compatibility("1.0.0") is True
        assert check_api_compatibility("1.0") is True
    
    def test_check_api_compatibility_minor(self):
        """Test API compatibility with minor version differences."""
        # Should be compatible with lower minor/patch versions
        assert check_api_compatibility("1.0.0") is True
        # Should not be compatible with different major version
        assert check_api_compatibility("2.0.0") is False
        assert check_api_compatibility("0.9.0") is False
    
    def test_deprecated_decorator(self):
        """Test deprecation decorator."""
        @deprecated("2.0", "new_function")
        def old_function():
            return "result"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_function()
            
            assert result == "result"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message)
            assert "2.0" in str(w[0].message)
            assert "new_function" in str(w[0].message)
    
    def test_api_version_check_decorator(self):
        """Test API version check decorator."""
        @api_version_check("1.0")
        def versioned_function():
            return "success"
        
        # Should work with current version
        assert versioned_function() == "success"
        
        # Test with incompatible version
        @api_version_check("2.0")
        def future_function():
            return "future"
        
        with pytest.raises(RuntimeError, match="API version .* required"):
            future_function()


class TestAPIPipeline:
    """Test API v1 VTTKnowledgeExtractor."""
    
    @patch('src.api.v1.seeding._PipelineImpl')
    def test_pipeline_initialization(self, mock_pipeline_class):
        """Test pipeline initialization with API version."""
        config = Mock(spec=Config)
        pipeline = VTTKnowledgeExtractor(config, api_version="1.0")
        
        assert pipeline._api_version == "1.0"
        assert pipeline._created_at is not None
    
    @patch('src.api.v1.seeding._PipelineImpl.seed_podcast')
    def test_seed_podcast_v1_response(self, mock_seed):
        """Test seed_podcast ensures v1 response schema."""
        # Mock internal response
        mock_seed.return_value = {
            'start_time': '2024-01-01T00:00:00',
            'end_time': '2024-01-01T01:00:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'processing_time_seconds': 3600.0,
            'extra_field': 'extra_value'  # Additional field
        }
        
        pipeline = VTTKnowledgeExtractor()
        result = pipeline.seed_podcast({'rss_url': 'test.xml'})
        
        # Check v1 schema fields are present
        assert 'api_version' in result
        assert result['api_version'] == '1.0'
        assert 'start_time' in result
        assert 'end_time' in result
        assert 'podcasts_processed' in result
        assert 'episodes_processed' in result
        assert 'episodes_failed' in result
        assert 'processing_time_seconds' in result
        # Additional fields should be preserved
        assert result['extra_field'] == 'extra_value'
    
    @patch('src.api.v1.seeding._PipelineImpl.seed_podcasts')
    def test_seed_podcasts_v1_response(self, mock_seed):
        """Test seed_podcasts ensures v1 response schema."""
        # Mock internal response
        mock_seed.return_value = {
            'start_time': '2024-01-01T00:00:00',
            'end_time': '2024-01-01T02:00:00',
            'podcasts_processed': 2,
            'episodes_processed': 10,
            'episodes_failed': 1,
            'processing_time_seconds': 7200.0,
        }
        
        pipeline = VTTKnowledgeExtractor()
        result = pipeline.seed_podcasts([
            {'rss_url': 'test1.xml'},
            {'rss_url': 'test2.xml'}
        ])
        
        # Check v1 schema
        assert result['api_version'] == '1.0'
        assert result['podcasts_processed'] == 2
        assert result['episodes_processed'] == 10
    
    def test_deprecated_method(self):
        """Test deprecated method shows warning."""
        pipeline = VTTKnowledgeExtractor()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.object(pipeline, 'seed_podcast', return_value={}):
                pipeline.process_podcast({'rss_url': 'test.xml'})
            
            assert len(w) == 1
            assert "deprecated" in str(w[0].message)
            assert "seed_podcast" in str(w[0].message)


class TestAPIFunctions:
    """Test module-level API functions."""
    
    @patch('src.api.v1.seeding.VTTKnowledgeExtractor')
    def test_seed_podcast_function(self, mock_pipeline_class):
        """Test module-level seed_podcast function."""
        # Setup mock
        mock_pipeline = Mock()
        mock_pipeline.seed_podcast.return_value = {
            'podcasts_processed': 1,
            'api_version': '1.0'
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Call function
        result = seed_podcast(
            {'rss_url': 'test.xml'},
            max_episodes=5
        )
        
        # Verify
        assert result['podcasts_processed'] == 1
        mock_pipeline.seed_podcast.assert_called_once()
        mock_pipeline.cleanup.assert_called_once()
    
    @patch('src.api.v1.seeding.VTTKnowledgeExtractor')
    def test_seed_podcasts_function(self, mock_pipeline_class):
        """Test module-level seed_podcasts function."""
        # Setup mock
        mock_pipeline = Mock()
        mock_pipeline.seed_podcasts.return_value = {
            'podcasts_processed': 2,
            'api_version': '1.0'
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Call function
        configs = [
            {'rss_url': 'test1.xml'},
            {'rss_url': 'test2.xml'}
        ]
        result = seed_podcasts(configs, max_episodes_per_podcast=10)
        
        # Verify
        assert result['podcasts_processed'] == 2
        mock_pipeline.seed_podcasts.assert_called_once()
        mock_pipeline.cleanup.assert_called_once()
    
    @patch('src.api.v1.seeding.VTTKnowledgeExtractor')
    def test_function_with_custom_config(self, mock_pipeline_class):
        """Test API function with custom config."""
        # Setup
        custom_config = Mock(spec=Config)
        mock_pipeline = Mock()
        mock_pipeline.seed_podcast.return_value = {'api_version': '1.0'}
        mock_pipeline_class.return_value = mock_pipeline
        
        # Call with custom config
        seed_podcast({'rss_url': 'test.xml'}, config=custom_config)
        
        # Verify config was passed
        mock_pipeline_class.assert_called_once_with(custom_config)
    
    @patch('src.api.v1.seeding.VTTKnowledgeExtractor')
    def test_function_cleanup_on_error(self, mock_pipeline_class):
        """Test cleanup is called even on error."""
        # Setup mock to raise error
        mock_pipeline = Mock()
        mock_pipeline.seed_podcast.side_effect = Exception("Test error")
        mock_pipeline_class.return_value = mock_pipeline
        
        # Call should raise but still cleanup
        with pytest.raises(Exception, match="Test error"):
            seed_podcast({'rss_url': 'test.xml'})
        
        # Cleanup should still be called
        mock_pipeline.cleanup.assert_called_once()
    
    def test_forward_compatibility_kwargs(self):
        """Test that functions accept **kwargs for forward compatibility."""
        with patch('src.api.v1.seeding.VTTKnowledgeExtractor') as mock_class:
            mock_pipeline = Mock()
            mock_pipeline.seed_podcast.return_value = {'api_version': '1.0'}
            mock_class.return_value = mock_pipeline
            
            # Should not raise with unknown kwargs
            result = seed_podcast(
                {'rss_url': 'test.xml'},
                future_param='future_value',
                another_param=123
            )
            
            assert result is not None