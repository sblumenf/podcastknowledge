"""Simple tests for health check functionality that match actual implementation."""

from unittest.mock import patch, MagicMock

import pytest

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
        config.neo4j_username = "neo4j"
        config.neo4j_password = "test"
        return config
    
    @pytest.fixture
    def health_checker(self, mock_config):
        """Create health checker with mock config."""
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
            
            assert result['name'] == "system_resources"
            assert result['status'] == HealthStatus.HEALTHY.value
            assert "System resources OK" in result['message']
    
    def test_system_resources_unhealthy(self, health_checker):
        """Test system resources check when unhealthy."""
        with patch('src.api.health.get_system_resources') as mock_resources:
            mock_resources.return_value = {
                'cpu_percent': 99.0,
                'memory_percent': 95.0,
                'disk_percent': 98.0,
                'gpu': {'available': False}
            }
            
            result = health_checker._check_system_resources()
            
            assert result['name'] == "system_resources"
            assert result['status'] == HealthStatus.UNHEALTHY.value
            assert "System resources high" in result['message']
    
    def test_check_health_all_healthy(self, health_checker):
        """Test overall health check when all components healthy."""
        with patch.object(health_checker, '_check_neo4j') as mock_neo4j, \
             patch.object(health_checker, '_check_system_resources') as mock_resources:
            
            mock_neo4j.return_value = ComponentHealth(
                name='neo4j',
                status=HealthStatus.HEALTHY,
                message='OK'
            )
            mock_resources.return_value = {
                'name': 'system_resources',
                'status': HealthStatus.HEALTHY.value,
                'healthy': True,
                'message': 'OK'
            }
            
            result = health_checker.check_health(use_enhanced=False)
            
            assert result['status'] == 'healthy'
            assert result['healthy'] is True
            assert 'components' in result
    
    def test_check_readiness(self, health_checker):
        """Test readiness check."""
        with patch.object(health_checker, '_check_neo4j') as mock_neo4j:
            mock_neo4j.return_value = ComponentHealth(
                name='neo4j',
                status=HealthStatus.HEALTHY,
                message='OK'
            )
            
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
    """Test module-level health check functions."""
    
    def test_health_check(self):
        """Test module-level health check."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_health.return_value = {
                'status': 'healthy',
                'healthy': True
            }
            
            result = health_check()
            
            assert result['status'] == 'healthy'
            mock_checker.check_health.assert_called_once()
    
    def test_readiness_check(self):
        """Test module-level readiness check."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_readiness.return_value = {
                'ready': True,
                'status': 'ready'
            }
            
            result = readiness_check()
            
            assert result['ready'] is True
            mock_checker.check_readiness.assert_called_once()
    
    def test_liveness_check(self):
        """Test module-level liveness check."""
        with patch('src.api.health.get_health_checker') as mock_get_checker:
            mock_checker = MagicMock()
            mock_get_checker.return_value = mock_checker
            mock_checker.check_liveness.return_value = {
                'alive': True,
                'status': 'alive'
            }
            
            result = liveness_check()
            
            assert result['alive'] is True
            mock_checker.check_liveness.assert_called_once()