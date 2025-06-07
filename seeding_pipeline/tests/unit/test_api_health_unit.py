"""Comprehensive unit tests for API health module."""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import time

import pytest

from src.api.health import (
    HealthStatus, HealthStatus, HealthChecker,
    get_health_checker, health_check, readiness_check, liveness_check,
    create_health_endpoints
)
from src.core.config import PipelineConfig


class TestHealthStatus:
    """Test HealthStatus enum."""
    
    def test_health_status_values(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthStatus:
    """Test HealthStatus dataclass."""
    
    def test_component_health_creation(self):
        """Test creating component health."""
        health = HealthStatus(
            name="test_component",
            status=HealthStatus.HEALTHY,
            message="All good",
            details={"extra": "info"}
        )
        
        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"
        assert health.details == {"extra": "info"}
    
    def test_component_health_defaults(self):
        """Test component health with defaults."""
        health = HealthStatus(
            name="test",
            status=HealthStatus.UNHEALTHY,
            message="Error"
        )
        
        assert health.details is None


class TestHealthChecker:
    """Test HealthChecker functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock(spec=PipelineConfig)
        config.neo4j_uri = "bolt://localhost:7687"
        config.neo4j_username = "neo4j"
        config.neo4j_password = "password"
        return config
    
    @pytest.fixture
    def health_checker(self, mock_config):
        """Create health checker instance."""
        return HealthChecker(mock_config)
    
    def test_health_checker_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.config is not None
        assert hasattr(health_checker, '_start_time')
        assert isinstance(health_checker._start_time, float)
    
    def test_health_checker_default_config(self):
        """Test health checker with default config."""
        checker = HealthChecker()
        assert isinstance(checker.config, PipelineConfig)
    
    @patch('src.api.health.GraphDatabase')
    def test_check_neo4j_healthy(self, mock_graph_db, health_checker):
        """Test Neo4j health check when healthy."""
        # Mock successful connection
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = {"health": 1}
        
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_session.run.return_value = mock_result
        
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        result = health_checker._check_neo4j()
        
        assert result.name == "neo4j"
        assert result.status == HealthStatus.HEALTHY
        assert "responsive" in result.message
        
        # Verify connection was properly closed
        mock_driver.close.assert_called_once()
    
    @patch('src.api.health.GraphDatabase')
    def test_check_neo4j_unavailable(self, mock_graph_db, health_checker):
        """Test Neo4j health check when service unavailable."""
        from neo4j.exceptions import ServiceUnavailable
        
        mock_graph_db.driver.side_effect = ServiceUnavailable("Connection refused")
        
        result = health_checker._check_neo4j()
        
        assert result.name == "neo4j"
        assert result.status == HealthStatus.UNHEALTHY
        assert "unavailable" in result.message
        assert "Connection refused" in result.message
    
    @patch('src.api.health.GraphDatabase')
    def test_check_neo4j_general_error(self, mock_graph_db, health_checker):
        """Test Neo4j health check with general error."""
        mock_graph_db.driver.side_effect = Exception("Unknown error")
        
        result = health_checker._check_neo4j()
        
        assert result.name == "neo4j"
        assert result.status == HealthStatus.UNHEALTHY
        assert "error" in result.message
        assert "Unknown error" in result.message
    
    @patch('src.api.health.get_system_resources')
    def test_check_system_resources_healthy(self, mock_resources, health_checker):
        """Test system resources check when healthy."""
        mock_resources.return_value = {
            'memory_percent': 60.0,
            'disk_percent': 70.0,
            'cpu_percent': 40.0
        }
        
        result = health_checker._check_system_resources()
        
        assert result["name"] == "system_resources"
        assert result["status"] == "healthy"
        assert result["healthy"] is True
        assert "OK" in result["message"]
        assert result["details"]["memory_percent"] == 60.0
    
    @patch('src.api.health.get_system_resources')
    def test_check_system_resources_high_memory(self, mock_resources, health_checker):
        """Test system resources check with high memory usage."""
        mock_resources.return_value = {
            'memory_percent': 92.0,
            'disk_percent': 70.0,
            'cpu_percent': 40.0
        }
        
        result = health_checker._check_system_resources()
        
        assert result["status"] == "unhealthy"
        assert result["healthy"] is False
        assert "high" in result["message"]
    
    @patch('src.api.health.get_system_resources')
    def test_check_system_resources_high_disk(self, mock_resources, health_checker):
        """Test system resources check with high disk usage."""
        mock_resources.return_value = {
            'memory_percent': 60.0,
            'disk_percent': 96.0,
            'cpu_percent': 40.0
        }
        
        result = health_checker._check_system_resources()
        
        assert result["status"] == "unhealthy"
        assert result["healthy"] is False
    
    @patch('src.api.health.get_system_resources')
    def test_check_system_resources_error(self, mock_resources, health_checker):
        """Test system resources check with error."""
        mock_resources.side_effect = Exception("Resource error")
        
        result = health_checker._check_system_resources()
        
        assert result["status"] == "unhealthy"
        assert result["healthy"] is False
        assert "failed" in result["message"]
        assert "Resource error" in result["message"]
    
    @patch.object(HealthChecker, '_check_neo4j')
    @patch.object(HealthChecker, '_check_system_resources')
    def test_check_health_all_healthy(self, mock_resources, mock_neo4j, health_checker):
        """Test overall health check when all components healthy."""
        mock_neo4j.return_value = HealthStatus(
            name="neo4j",
            status=HealthStatus.HEALTHY,
            message="OK"
        )
        mock_resources.return_value = {
            "name": "system_resources",
            "status": "healthy",
            "healthy": True,
            "message": "OK"
        }
        
        result = health_checker.check_health()
        
        assert result["status"] == "healthy"
        assert result["healthy"] is True
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert result["components"]["neo4j"]["healthy"] is True
        assert result["components"]["system_resources"]["healthy"] is True
    
    @patch.object(HealthChecker, '_check_neo4j')
    @patch.object(HealthChecker, '_check_system_resources')
    def test_check_health_neo4j_unhealthy(self, mock_resources, mock_neo4j, health_checker):
        """Test overall health check when Neo4j unhealthy."""
        mock_neo4j.return_value = HealthStatus(
            name="neo4j",
            status=HealthStatus.UNHEALTHY,
            message="Error"
        )
        mock_resources.return_value = {
            "name": "system_resources",
            "status": "healthy",
            "healthy": True,
            "message": "OK"
        }
        
        result = health_checker.check_health()
        
        assert result["status"] == "unhealthy"
        assert result["healthy"] is False
        assert result["components"]["neo4j"]["healthy"] is False
    
    @patch.object(HealthChecker, '_check_neo4j')
    def test_check_readiness_ready(self, mock_neo4j, health_checker):
        """Test readiness check when ready."""
        mock_neo4j.return_value = HealthStatus(
            name="neo4j",
            status=HealthStatus.HEALTHY,
            message="OK"
        )
        
        result = health_checker.check_readiness()
        
        assert result["ready"] is True
        assert result["status"] == "ready"
        assert result["checks"]["neo4j"] == "healthy"
        assert "timestamp" in result
    
    @patch.object(HealthChecker, '_check_neo4j')
    def test_check_readiness_not_ready(self, mock_neo4j, health_checker):
        """Test readiness check when not ready."""
        mock_neo4j.return_value = HealthStatus(
            name="neo4j",
            status=HealthStatus.UNHEALTHY,
            message="Error"
        )
        
        result = health_checker.check_readiness()
        
        assert result["ready"] is False
        assert result["status"] == "not_ready"
        assert result["checks"]["neo4j"] == "unhealthy"
    
    def test_check_liveness(self, health_checker):
        """Test liveness check."""
        result = health_checker.check_liveness()
        
        assert result["alive"] is True
        assert result["status"] == "alive"
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0
        assert "timestamp" in result
    
    def test_uptime_calculation(self, health_checker):
        """Test uptime calculation."""
        # Set start time to known value
        health_checker._start_time = time.time() - 100  # 100 seconds ago
        
        result = health_checker.check_liveness()
        
        assert result["uptime_seconds"] >= 99  # Allow for small timing differences
        assert result["uptime_seconds"] <= 101


class TestModuleLevelFunctions:
    """Test module-level functions."""
    
    def test_get_health_checker_singleton(self):
        """Test health checker singleton pattern."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        
        assert checker1 is checker2
        assert isinstance(checker1, HealthChecker)
    
    @patch('src.api.health.get_health_checker')
    def test_health_check_function(self, mock_get_checker):
        """Test health_check function."""
        mock_checker = Mock()
        mock_checker.check_health.return_value = {"healthy": True}
        mock_get_checker.return_value = mock_checker
        
        result = health_check()
        
        assert result == {"healthy": True}
        mock_checker.check_health.assert_called_once()
    
    @patch('src.api.health.get_health_checker')
    def test_readiness_check_function(self, mock_get_checker):
        """Test readiness_check function."""
        mock_checker = Mock()
        mock_checker.check_readiness.return_value = {"ready": True}
        mock_get_checker.return_value = mock_checker
        
        result = readiness_check()
        
        assert result == {"ready": True}
        mock_checker.check_readiness.assert_called_once()
    
    @patch('src.api.health.get_health_checker')
    def test_liveness_check_function(self, mock_get_checker):
        """Test liveness_check function."""
        mock_checker = Mock()
        mock_checker.check_liveness.return_value = {"alive": True}
        mock_get_checker.return_value = mock_checker
        
        result = liveness_check()
        
        assert result == {"alive": True}
        mock_checker.check_liveness.assert_called_once()


class TestCreateHealthEndpoints:
    """Test create_health_endpoints function."""
    
    def test_create_health_endpoints_fastapi(self):
        """Test creating health endpoints for FastAPI."""
        from fastapi import FastAPI
        
        app = FastAPI()
        create_health_endpoints(app)
        
        # Check that routes were added
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/ready" in routes
        assert "/live" in routes
    
    @patch('src.api.health.get_health_checker')
    def test_create_health_endpoints_flask(self, mock_get_checker):
        """Test creating health endpoints for Flask."""
        # Mock Flask since it might not be installed
        mock_flask = MagicMock()
        mock_app = MagicMock()
        
        with patch.dict('sys.modules', {'flask': mock_flask}):
            mock_flask.Flask = MagicMock
            mock_flask.jsonify = lambda x: x
            
            # Make isinstance work
            with patch('src.api.health.isinstance') as mock_isinstance:
                mock_isinstance.side_effect = lambda obj, cls: False if "FastAPI" in str(cls) else True
                
                create_health_endpoints(mock_app)
                
                # Check that routes were added
                assert mock_app.route.call_count == 3
                mock_app.route.assert_any_call("/health")
                mock_app.route.assert_any_call("/ready")
                mock_app.route.assert_any_call("/live")
    
    def test_create_health_endpoints_invalid_app(self):
        """Test creating health endpoints with invalid app."""
        with pytest.raises(ValueError, match="App must be either FastAPI or Flask"):
            create_health_endpoints("not_an_app")
    
    def test_create_health_endpoints_no_imports(self):
        """Test creating health endpoints when frameworks not available."""
        with patch.dict('sys.modules', {'fastapi': None, 'flask': None}):
            with pytest.raises(ValueError):
                create_health_endpoints(Mock())