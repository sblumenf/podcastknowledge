"""Tests for health check functionality."""

import pytest
from unittest.mock import patch, MagicMock

from src.api.health import (
    HealthChecker, HealthStatus, ComponentHealth,
    health_check, readiness_check, liveness_check
)


class TestHealthChecker:
    """Test the HealthChecker class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.neo4j_uri = "bolt://localhost:7687"
        config.neo4j_user = "neo4j"
        config.neo4j_password = "test"
        config.redis_url = "redis://localhost:6379/0"
        return config
    
    @pytest.fixture
    def health_checker(self, mock_config):
        """Create health checker with mock config."""
        with patch('src.api.health.PipelineConfig.from_env', return_value=mock_config):
            return HealthChecker(mock_config)
    
    def test_neo4j_healthy(self, health_checker):
        """Test Neo4j health check when healthy."""
        with patch('src.api.health.GraphDatabase.driver') as mock_driver:
            mock_session = MagicMock()
            mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
            mock_session.run.return_value.single.return_value = {"health": 1}
            
            result = health_checker._check_neo4j()
            
            assert result.name == "neo4j"
            assert result.status == HealthStatus.HEALTHY
            assert "Neo4j is responsive" in result.message
    
    def test_neo4j_unhealthy(self, health_checker):
        """Test Neo4j health check when unhealthy."""
        from neo4j.exceptions import ServiceUnavailable
        
        with patch('src.api.health.GraphDatabase.driver') as mock_driver:
            mock_driver.side_effect = ServiceUnavailable("Connection failed")
            
            result = health_checker._check_neo4j()
            
            assert result.name == "neo4j"
            assert result.status == HealthStatus.UNHEALTHY
            assert "Neo4j unavailable" in result.message
    
    def test_redis_healthy(self, health_checker):
        """Test Redis health check when healthy."""
        with patch('src.api.health.redis.from_url') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            mock_client.ping.return_value = True
            mock_client.info.return_value = {
                'used_memory': 1024 * 1024 * 100,  # 100MB
                'connected_clients': 5
            }
            
            result = health_checker._check_redis()
            
            assert result.name == "redis"
            assert result.status == HealthStatus.HEALTHY
            assert "Redis is responsive" in result.message
            assert result.details['memory_used_mb'] == 100.0
    
    def test_redis_degraded(self, health_checker):
        """Test Redis health check when connection fails."""
        import redis
        
        with patch('src.api.health.redis.from_url') as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError("Connection refused")
            
            result = health_checker._check_redis()
            
            assert result.name == "redis"
            assert result.status == HealthStatus.DEGRADED
            assert "Redis unavailable" in result.message
    
    def test_system_resources_healthy(self, health_checker):
        """Test system resources check when healthy."""
        with patch('src.api.health.get_system_resources') as mock_resources:
            mock_resources.return_value = {
                'cpu_percent': 50.0,
                'memory_percent': 70.0,
                'disk_percent': 60.0,
                'gpu': {'available': False}
            }
            
            result = health_checker._check_system_resources()
            
            assert result.name == "system_resources"
            assert result.status == HealthStatus.HEALTHY
            assert "System resources healthy" in result.message
    
    def test_system_resources_degraded(self, health_checker):
        """Test system resources check when memory high."""
        with patch('src.api.health.get_system_resources') as mock_resources:
            mock_resources.return_value = {
                'cpu_percent': 50.0,
                'memory_percent': 85.0,  # High memory usage
                'disk_percent': 60.0,
                'gpu': {'available': False}
            }
            
            result = health_checker._check_system_resources()
            
            assert result.name == "system_resources"
            assert result.status == HealthStatus.DEGRADED
            assert "Memory usage high" in result.message
    
    def test_system_resources_unhealthy(self, health_checker):
        """Test system resources check when critical."""
        with patch('src.api.health.get_system_resources') as mock_resources:
            mock_resources.return_value = {
                'cpu_percent': 50.0,
                'memory_percent': 95.0,  # Critical memory usage
                'disk_percent': 96.0,    # Critical disk usage
                'gpu': {'available': False}
            }
            
            result = health_checker._check_system_resources()
            
            assert result.name == "system_resources"
            assert result.status == HealthStatus.UNHEALTHY
            assert "Memory usage critical" in result.message
            assert "Disk space critical" in result.message
    
    def test_check_health_all_healthy(self, health_checker):
        """Test overall health check when all components healthy."""
        with patch.object(health_checker, '_check_neo4j') as mock_neo4j, \
             patch.object(health_checker, '_check_redis') as mock_redis, \
             patch.object(health_checker, '_check_system_resources') as mock_resources, \
             patch.object(health_checker, '_check_providers') as mock_providers:
            
            mock_neo4j.return_value = ComponentHealth("neo4j", HealthStatus.HEALTHY)
            mock_redis.return_value = ComponentHealth("redis", HealthStatus.HEALTHY)
            mock_resources.return_value = ComponentHealth("resources", HealthStatus.HEALTHY)
            mock_providers.return_value = [
                ComponentHealth("provider_audio", HealthStatus.HEALTHY)
            ]
            
            result = health_checker.check_health()
            
            assert result['status'] == 'healthy'
            assert result['healthy'] is True
            assert 'components' in result
            assert len(result['components']) == 4
    
    def test_check_health_degraded(self, health_checker):
        """Test overall health check when some components degraded."""
        with patch.object(health_checker, '_check_neo4j') as mock_neo4j, \
             patch.object(health_checker, '_check_redis') as mock_redis, \
             patch.object(health_checker, '_check_system_resources') as mock_resources, \
             patch.object(health_checker, '_check_providers') as mock_providers:
            
            mock_neo4j.return_value = ComponentHealth("neo4j", HealthStatus.HEALTHY)
            mock_redis.return_value = ComponentHealth("redis", HealthStatus.DEGRADED)
            mock_resources.return_value = ComponentHealth("resources", HealthStatus.HEALTHY)
            mock_providers.return_value = []
            
            result = health_checker.check_health()
            
            assert result['status'] == 'degraded'
            assert result['healthy'] is False
    
    def test_check_readiness(self, health_checker):
        """Test readiness check."""
        with patch.object(health_checker, '_check_neo4j') as mock_neo4j, \
             patch('src.api.health.get_provider_factory') as mock_factory:
            
            mock_neo4j.return_value = ComponentHealth("neo4j", HealthStatus.HEALTHY)
            mock_factory.return_value.get_provider.return_value = MagicMock()
            
            result = health_checker.check_readiness()
            
            assert result['ready'] is True
            assert result['status'] == 'ready'
    
    def test_check_liveness(self, health_checker):
        """Test liveness check."""
        result = health_checker.check_liveness()
        
        assert result['alive'] is True
        assert result['status'] == 'alive'
        assert 'uptime_seconds' in result


class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_health_check(self):
        """Test module-level health_check function."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_health.return_value = {'status': 'healthy'}
            
            result = health_check()
            
            assert result['status'] == 'healthy'
            mock_checker.check_health.assert_called_once()
    
    def test_readiness_check(self):
        """Test module-level readiness_check function."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_readiness.return_value = {'ready': True}
            
            result = readiness_check()
            
            assert result['ready'] is True
            mock_checker.check_readiness.assert_called_once()
    
    def test_liveness_check(self):
        """Test module-level liveness_check function."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_liveness.return_value = {'alive': True}
            
            result = liveness_check()
            
            assert result['alive'] is True
            mock_checker.check_liveness.assert_called_once()