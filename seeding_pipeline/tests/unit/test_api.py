"""Comprehensive tests for API module."""

import pytest
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException, status
import json
from datetime import datetime

from src.api.app import create_app
from src.api.health import HealthStatus, ComponentHealth
from src.api.metrics import RequestMetrics, MetricsCollector


class TestAPIApp:
    Test API application.
    
    def test_create_app(self):
        Test app creation.
        app = create_app()
        assert app is not None
        assert app.title == "Podcast Knowledge Pipeline API"
        
    def test_app_routes(self):
        Test app has expected routes.
        app = create_app()
        routes = [route.path for route in app.routes]
        
        # Check core routes exist
        assert "/" in routes
        assert "/health" in routes
        assert "/metrics" in routes
        assert "/api/v1/seed/podcast" in routes
        
    def test_app_middleware(self):
        Test app middleware setup.
        app = create_app()
        
        # Check middleware is configured
        middleware_types = [m.__class__.__name__ for m in app.middleware]
        assert any("CORS" in m for m in middleware_types)
        assert any("Tracing" in m for m in middleware_types)
        

class TestRootEndpoint:
    Test root endpoint.
    
    def test_root_endpoint(self):
        Test root endpoint response.
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Podcast Knowledge Pipeline API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        

class TestHealthEndpoints:
    Test health check endpoints.
    
    @patch('src.api.health.check_component_health')
    def test_health_check_all_healthy(self, mock_check):
        Test health check when all components healthy.
        mock_check.return_value = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Component is healthy"
        )
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["timestamp"] is not None
        
    @patch('src.api.health.check_component_health')
    def test_health_check_degraded(self, mock_check):
        Test health check when components degraded.
        mock_check.side_effect = [
            ComponentHealth(
                name="neo4j",
                status=HealthStatus.HEALTHY,
                message="Connected"
            ),
            ComponentHealth(
                name="llm",
                status=HealthStatus.DEGRADED,
                message="High latency",
                details={"latency_ms": 5000}
            )
        ]
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "degraded"
        
    @patch('src.api.health.check_component_health')
    def test_health_check_unhealthy(self, mock_check):
        Test health check when components unhealthy.
        mock_check.return_value = ComponentHealth(
            name="neo4j",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
            error="Connection refused"
        )
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 503
        
        data = response.json()
        assert data["status"] == "unhealthy"
        

class TestMetricsEndpoint:
    Test metrics endpoint.
    
    @patch('src.api.metrics.MetricsCollector.get_metrics')
    def test_metrics_endpoint(self, mock_get_metrics):
        Test metrics endpoint.
        mock_get_metrics.return_value = {
            "requests": {
                "total": 1000,
                "success": 950,
                "errors": 50
            },
            "latency": {
                "p50": 50,
                "p95": 200,
                "p99": 500
            }
        }
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "requests" in data
        assert "latency" in data
        

class TestSeedingEndpoint:
    Test podcast seeding endpoint.
    
    @patch('src.seeding.PodcastKnowledgePipeline.seed_podcast')
    async def test_seed_podcast_success(self, mock_seed):
        Test successful podcast seeding.
        mock_seed.return_value = {
            "podcast_id": "test-podcast",
            "episodes_processed": 5,
            "status": "completed"
        }
        
        app = create_app()
        client = TestClient(app)
        
        payload = {
            "id": "test-podcast",
            "rss_url": "https://example.com/feed.xml",
            "max_episodes": 5
        }
        
        response = client.post("/api/v1/seed/podcast", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["podcast_id"] == "test-podcast"
        assert data["episodes_processed"] == 5
        
    @patch('src.seeding.PodcastKnowledgePipeline.seed_podcast')
    async def test_seed_podcast_validation_error(self, mock_seed):
        Test podcast seeding with validation error.
        app = create_app()
        client = TestClient(app)
        
        # Missing required fields
        payload = {
            "id": "test-podcast"
            # Missing rss_url
        }
        
        response = client.post("/api/v1/seed/podcast", json=payload)
        assert response.status_code == 422
        
    @patch('src.seeding.PodcastKnowledgePipeline.seed_podcast')
    async def test_seed_podcast_processing_error(self, mock_seed):
        Test podcast seeding with processing error.
        mock_seed.side_effect = Exception("Processing failed")
        
        app = create_app()
        client = TestClient(app)
        
        payload = {
            "id": "test-podcast",
            "rss_url": "https://example.com/feed.xml"
        }
        
        response = client.post("/api/v1/seed/podcast", json=payload)
        assert response.status_code == 500
        
        data = response.json()
        assert "error" in data
        

class TestTracingMiddleware:
    Test distributed tracing middleware.
    
    @patch('src.tracing.create_span')
    def test_tracing_middleware_success(self, mock_create_span):
        Test tracing middleware on successful request.
        mock_span = MagicMock()
        mock_create_span.return_value.__enter__.return_value = mock_span
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/")
        assert response.status_code == 200
        
        # Verify span was created
        mock_create_span.assert_called()
        mock_span.set_attribute.assert_called()
        
    @patch('src.tracing.create_span')
    def test_tracing_middleware_error(self, mock_create_span):
        Test tracing middleware on error.
        mock_span = MagicMock()
        mock_create_span.return_value.__enter__.return_value = mock_span
        
        app = create_app()
        client = TestClient(app)
        
        # Force an error
        with patch('src.api.app.root', side_effect=Exception("Test error")):
            response = client.get("/")
            assert response.status_code == 500
            
        # Verify exception was recorded
        mock_span.record_exception.assert_called()
        

class TestErrorHandling:
    Test API error handling.
    
    def test_404_error(self):
        Test 404 error handling.
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
    def test_method_not_allowed(self):
        Test 405 error handling.
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/")  # Root only accepts GET
        assert response.status_code == 405
        
    @patch('src.api.app.seed_podcast')
    def test_internal_server_error(self, mock_seed):
        Test 500 error handling.
        mock_seed.side_effect = Exception("Unexpected error")
        
        app = create_app()
        client = TestClient(app)
        
        payload = {
            "id": "test",
            "rss_url": "https://example.com/feed.xml"
        }
        
        response = client.post("/api/v1/seed/podcast", json=payload)
        assert response.status_code == 500
        

class TestCORSMiddleware:
    Test CORS middleware configuration.
    
    def test_cors_headers(self):
        Test CORS headers are set.
        app = create_app()
        client = TestClient(app)
        
        response = client.options("/", headers={"Origin": "https://example.com"})
        
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
"""