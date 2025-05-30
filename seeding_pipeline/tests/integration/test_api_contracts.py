"""Comprehensive API contract tests for v1 API endpoints."""

import json
import pytest
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from src.api.v1.seeding import (
    PodcastKnowledgePipeline, 
    seed_podcast, 
    seed_podcasts,
    deprecated, 
    api_version_check
)
from src.api.health import HealthChecker, HealthStatus, ComponentHealth
from src.core.config import Config
from src.core.exceptions import PodcastKGError


class TestAPIv1Contracts:
    """Test API v1 contracts and response formats."""
    
    @pytest.fixture
    def test_config(self, monkeypatch):
        """Test configuration."""
        # Set required environment variables
        monkeypatch.setenv('NEO4J_PASSWORD', 'testpass')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test-api-key')
        
        config = Config()
        config.neo4j_uri = 'bolt://localhost:7687'
        config.neo4j_user = 'neo4j'
        config.neo4j_password = 'testpass'
        config.checkpoint_enabled = True
        config.checkpoint_dir = 'test_checkpoints'
        return config
    
    @pytest.fixture
    def sample_podcast_config(self):
        """Sample podcast configuration."""
        return {
            'name': 'Test Podcast',
            'rss_url': 'https://example.com/feed.xml',
            'category': 'Technology'
        }
    
    @pytest.fixture
    def mock_pipeline_result(self):
        """Mock pipeline processing result."""
        return {
            'start_time': '2024-01-01T10:00:00',
            'end_time': '2024-01-01T10:05:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'extraction_mode': 'fixed',
            'processing_time_seconds': 300.0
        }
    
    @pytest.mark.integration
    def test_seed_podcast_fixed_schema_response_format(
        self, test_config, sample_podcast_config, mock_pipeline_result
    ):
        """Test seed_podcast API response format for fixed schema."""
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast',
                  return_value=mock_pipeline_result):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            result = pipeline.seed_podcast(
                podcast_config=sample_podcast_config,
                max_episodes=5,
                extraction_mode='fixed'
            )
            
            # Verify v1 response schema
            assert 'api_version' in result
            assert result['api_version'] == '1.0'
            assert 'start_time' in result
            assert 'end_time' in result
            assert 'podcasts_processed' in result
            assert result['podcasts_processed'] == 1
            assert 'episodes_processed' in result
            assert result['episodes_processed'] == 5
            assert 'episodes_failed' in result
            assert result['episodes_failed'] == 0
            assert 'processing_time_seconds' in result
            assert result['processing_time_seconds'] == 300.0
            assert 'extraction_mode' in result
            assert result['extraction_mode'] == 'fixed'
            
            # Fixed schema should not have schemaless fields
            assert 'discovered_types' not in result or result['discovered_types'] == []
    
    @pytest.mark.integration
    def test_seed_podcast_schemaless_response_format(
        self, test_config, sample_podcast_config
    ):
        """Test seed_podcast API response format for schemaless extraction."""
        mock_result = {
            'start_time': '2024-01-01T10:00:00',
            'end_time': '2024-01-01T10:05:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'extraction_mode': 'schemaless',
            'total_entities': 25,
            'total_relationships': 15,
            'discovered_types': ['Expert', 'Technology', 'Concept', 'Event'],
            'processing_time_seconds': 350.0
        }
        
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast',
                  return_value=mock_result):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            result = pipeline.seed_podcast(
                podcast_config=sample_podcast_config,
                max_episodes=5,
                extraction_mode='schemaless'
            )
            
            # Verify v1 response schema
            assert result['api_version'] == '1.0'
            assert result['extraction_mode'] == 'schemaless'
            
            # Schemaless-specific fields
            assert 'total_entities' in result
            assert result['total_entities'] == 25
            assert 'total_relationships' in result
            assert result['total_relationships'] == 15
            assert 'discovered_types' in result
            assert isinstance(result['discovered_types'], list)
            assert len(result['discovered_types']) == 4
            assert 'Expert' in result['discovered_types']
    
    @pytest.mark.integration
    def test_seed_podcasts_batch_response_format(
        self, test_config, sample_podcast_config
    ):
        """Test seed_podcasts batch API response format."""
        podcast_configs = [
            sample_podcast_config,
            {
                'name': 'Test Podcast 2',
                'rss_url': 'https://example.com/feed2.xml',
                'category': 'Science'
            }
        ]
        
        mock_result = {
            'start_time': '2024-01-01T10:00:00',
            'end_time': '2024-01-01T10:15:00',
            'podcasts_processed': 2,
            'episodes_processed': 10,
            'episodes_failed': 1,
            'extraction_mode': 'fixed',
            'processing_time_seconds': 900.0
        }
        
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcasts',
                  return_value=mock_result):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            result = pipeline.seed_podcasts(
                podcast_configs=podcast_configs,
                max_episodes_each=5,
                extraction_mode='fixed'
            )
            
            # Verify batch response format
            assert result['api_version'] == '1.0'
            assert result['podcasts_processed'] == 2
            assert result['episodes_processed'] == 10
            assert result['episodes_failed'] == 1
            assert result['processing_time_seconds'] == 900.0
    
    @pytest.mark.integration
    def test_get_schema_evolution_response_format(self, test_config):
        """Test get_schema_evolution API response format."""
        mock_stats = {
            'total_types_discovered': 15,
            'evolution_entries': 5,
            'first_discovery': '2024-01-01',
            'latest_discovery': '2024-01-15',
            'entity_types': ['Expert', 'Technology', 'Concept'],
            'discovery_timeline': [
                {
                    'date': '2024-01-01',
                    'episode': 'Episode 1',
                    'count': 3,
                    'new_types': ['Expert', 'Technology', 'Concept']
                }
            ]
        }
        
        with patch('src.seeding.checkpoint.ProgressCheckpoint.get_schema_statistics',
                  return_value=mock_stats):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            result = pipeline.get_schema_evolution()
            
            # Verify response format
            assert 'api_version' in result
            assert result['api_version'] == '1.0'
            assert 'checkpoint_dir' in result
            assert 'schema_stats' in result
            assert 'timestamp' in result
            
            # Verify ISO timestamp format
            datetime.fromisoformat(result['timestamp'])
            
            # Verify schema stats structure
            stats = result['schema_stats']
            assert stats['total_types_discovered'] == 15
            assert stats['evolution_entries'] == 5
            assert isinstance(stats['entity_types'], list)
    
    @pytest.mark.integration
    def test_module_level_seed_podcast_function(
        self, test_config, sample_podcast_config, mock_pipeline_result
    ):
        """Test module-level seed_podcast convenience function."""
        with patch('src.api.v1.seeding.PodcastKnowledgePipeline') as mock_pipeline_class:
            mock_instance = Mock()
            mock_instance.seed_podcast.return_value = mock_pipeline_result
            mock_instance.cleanup.return_value = None
            mock_pipeline_class.return_value = mock_instance
            
            # Call module-level function
            result = seed_podcast(
                podcast_config=sample_podcast_config,
                max_episodes=5,
                config=test_config
            )
            
            # Verify pipeline was created and cleaned up
            mock_pipeline_class.assert_called_once_with(test_config)
            mock_instance.seed_podcast.assert_called_once()
            mock_instance.cleanup.assert_called_once()
            
            # Verify result
            assert result['episodes_processed'] == 5
    
    @pytest.mark.integration
    def test_deprecated_method_warning(self, test_config, sample_podcast_config):
        """Test deprecated method shows warning."""
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast',
                  return_value={'episodes_processed': 1}):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            with pytest.warns(DeprecationWarning) as warning_info:
                result = pipeline.process_podcast(sample_podcast_config)
            
            assert len(warning_info) == 1
            assert "process_podcast is deprecated" in str(warning_info[0].message)
            assert "Use seed_podcast instead" in str(warning_info[0].message)
    
    @pytest.mark.integration
    def test_api_version_check_decorator(self, test_config):
        """Test API version checking decorator."""
        # Test function with version check
        @api_version_check("1.0", "2.0")
        def test_func():
            return "success"
        
        # Should work with current version
        assert test_func() == "success"
        
        # Test with future version warning
        with patch('src.api.v1.seeding.__api_version__', '3.0'):
            with pytest.warns(FutureWarning) as warning_info:
                result = test_func()
            
            assert "newer than tested version" in str(warning_info[0].message)
    
    @pytest.mark.integration
    def test_error_response_format(self, test_config, sample_podcast_config):
        """Test error response maintains consistent format."""
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast',
                  side_effect=PodcastKGError("Test error")):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            with pytest.raises(PodcastKGError) as exc_info:
                pipeline.seed_podcast(sample_podcast_config)
            
            assert str(exc_info.value) == "[WARNING] Test error"
    
    @pytest.mark.integration
    def test_extraction_mode_configuration(self, test_config, sample_podcast_config):
        """Test that extraction mode properly configures the pipeline."""
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast') as mock_seed:
            mock_seed.return_value = {'episodes_processed': 1}
            
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Test fixed mode
            pipeline.seed_podcast(
                sample_podcast_config,
                extraction_mode='fixed'
            )
            assert pipeline.config.use_schemaless_extraction is False
            
            # Test schemaless mode
            pipeline.seed_podcast(
                sample_podcast_config,
                extraction_mode='schemaless'
            )
            assert pipeline.config.use_schemaless_extraction is True
    
    @pytest.mark.integration
    def test_backward_compatibility_fields(self, test_config, sample_podcast_config):
        """Test that additional fields are preserved for backward compatibility."""
        mock_result = {
            'start_time': '2024-01-01T10:00:00',
            'end_time': '2024-01-01T10:05:00',
            'podcasts_processed': 1,
            'episodes_processed': 5,
            'episodes_failed': 0,
            'extraction_mode': 'fixed',
            # Additional custom fields
            'custom_field': 'custom_value',
            'metrics': {'custom_metric': 42}
        }
        
        with patch('src.seeding.orchestrator.PodcastKnowledgePipeline.seed_podcast',
                  return_value=mock_result):
            
            pipeline = PodcastKnowledgePipeline(test_config)
            result = pipeline.seed_podcast(sample_podcast_config)
            
            # Verify custom fields are preserved
            assert result['custom_field'] == 'custom_value'
            assert result['metrics']['custom_metric'] == 42


class TestHealthAPIContracts:
    """Test health check API contracts."""
    
    @pytest.fixture
    def health_checker(self):
        """Create health checker instance."""
        config = Mock()
        config.neo4j_uri = 'bolt://localhost:7687'
        config.neo4j_user = 'neo4j'
        config.neo4j_password = 'testpass'
        return HealthChecker(config)
    
    @pytest.mark.integration
    def test_component_health_format(self):
        """Test ComponentHealth response format."""
        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            message="Component is healthy",
            details={'version': '1.0'}
        )
        
        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "Component is healthy"
        assert health.details == {'version': '1.0'}
        assert 'checked_at' in health.__dict__
        
        # Verify ISO timestamp format
        datetime.fromisoformat(health.checked_at)
    
    @pytest.mark.integration
    def test_neo4j_health_check_healthy(self, health_checker):
        """Test Neo4j health check response when healthy."""
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = Mock()
            mock_result = Mock()
            mock_result.single.return_value = {'health': 1}
            mock_session.run.return_value = mock_result
            mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
            
            result = health_checker._check_neo4j()
            
            assert result.name == "neo4j"
            assert result.status == HealthStatus.HEALTHY
            assert result.message == "Neo4j is responsive"
            assert result.details['connected'] is True
            assert 'uri' in result.details
    
    @pytest.mark.integration
    def test_neo4j_health_check_unhealthy(self, health_checker):
        """Test Neo4j health check response when unhealthy."""
        from neo4j.exceptions import ServiceUnavailable
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver.side_effect = ServiceUnavailable("Connection refused")
            
            result = health_checker._check_neo4j()
            
            assert result.name == "neo4j"
            assert result.status == HealthStatus.UNHEALTHY
            assert "Neo4j unavailable" in result.message
            assert 'error' in result.details
            assert "Connection refused" in result.details['error']