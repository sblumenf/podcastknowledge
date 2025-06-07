"""
Health check endpoints for the Podcast Knowledge Graph Pipeline.

This module provides simple health and readiness checks for monitoring
and orchestration systems (Kubernetes, Docker, etc.).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import time

from ..core.config import PipelineConfig
from ..utils.resources import get_system_resources
from ..utils.health_check import get_health_checker as get_enhanced_health_checker, HealthStatus as EnhancedHealthStatus
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    status: HealthStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """Simple health checker for the application."""
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self._start_time = time.time()
        
    def _check_neo4j(self) -> ComponentHealth:
        """Check Neo4j database health."""
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_username, self.config.neo4j_password),
                max_connection_lifetime=30
            )
            
            with driver.session() as session:
                result = session.run("RETURN 1 as health")
                result.single()
                
            driver.close()
            
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.HEALTHY,
                message="Neo4j is responsive"
            )
        except ServiceUnavailable as e:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j unavailable: {str(e)}"
            )
        except Exception as e:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j error: {str(e)}"
            )
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            resources = get_system_resources()
            
            # Simple health check based on resource usage
            healthy = (
                resources['memory_percent'] < 90 and
                resources['disk_percent'] < 95
            )
            
            return {
                "name": "system_resources",
                "status": HealthStatus.HEALTHY.value if healthy else HealthStatus.UNHEALTHY.value,
                "healthy": healthy,
                "message": "System resources OK" if healthy else "System resources high",
                "details": resources
            }
        except Exception as e:
            return {
                "name": "system_resources",
                "status": HealthStatus.UNHEALTHY.value,
                "healthy": False,
                "message": f"Resource check failed: {str(e)}"
            }
    
    def check_health(self, use_enhanced: bool = True) -> Dict[str, Any]:
        """Perform basic health checks.
        
        Args:
            use_enhanced: Whether to use the enhanced health checker with more components
        """
        if use_enhanced:
            # Use the enhanced health checker for comprehensive checks
            enhanced_checker = get_enhanced_health_checker()
            return enhanced_checker.check_all()
        
        # Original basic health check
        neo4j_health = self._check_neo4j()
        resource_health = self._check_system_resources()
        
        # Overall health is healthy only if all components are healthy
        overall_healthy = neo4j_health.status == HealthStatus.HEALTHY and resource_health["healthy"]
        
        return {
            "status": HealthStatus.HEALTHY.value if overall_healthy else HealthStatus.UNHEALTHY.value,
            "healthy": overall_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self._start_time),
            "components": {
                "neo4j": {
                    "name": neo4j_health.name,
                    "status": neo4j_health.status.value,
                    "healthy": neo4j_health.status == HealthStatus.HEALTHY,
                    "message": neo4j_health.message,
                    "details": neo4j_health.details
                },
                "system_resources": resource_health
            }
        }
    
    def check_readiness(self) -> Dict[str, Any]:
        """Check if the application is ready to serve requests."""
        # For readiness, we only check Neo4j
        neo4j_health = self._check_neo4j()
        
        return {
            "ready": neo4j_health.status == HealthStatus.HEALTHY,
            "status": "ready" if neo4j_health.status == HealthStatus.HEALTHY else "not_ready",
            "checks": {
                "neo4j": neo4j_health.status.value
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def check_liveness(self) -> Dict[str, Any]:
        """Check if the application is alive (not deadlocked)."""
        return {
            "alive": True,
            "status": "alive",
            "uptime_seconds": int(time.time() - self._start_time),
            "timestamp": datetime.utcnow().isoformat()
        }


# Module-level instances for easy access
_health_checker = None


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def health_check() -> Dict[str, Any]:
    """Perform a health check."""
    return get_health_checker().check_health()


def readiness_check() -> Dict[str, Any]:
    """Perform a readiness check."""
    return get_health_checker().check_readiness()


def liveness_check() -> Dict[str, Any]:
    """Perform a liveness check."""
    return get_health_checker().check_liveness()


# FastAPI/Flask integration helpers
def create_health_endpoints(app):
    """
    Add health check endpoints to a FastAPI or Flask app.
    
    Example:
        from fastapi import FastAPI
        from src.api.health import create_health_endpoints
        
        app = FastAPI()
        create_health_endpoints(app)
    """
    try:
        # Try FastAPI
        from fastapi import FastAPI
        if isinstance(app, FastAPI):
            @app.get("/health")
            async def health():
                return get_health_checker().check_health()
                
            @app.get("/ready")
            async def ready():
                return get_health_checker().check_readiness()
                
            @app.get("/live")
            async def live():
                return get_health_checker().check_liveness()
                
            return
    except ImportError:
        pass
        
    try:
        # Try Flask
        from flask import Flask, jsonify
        if isinstance(app, Flask):
            @app.route("/health")
            def health():
                return jsonify(health_check())
                
            @app.route("/ready")
            def ready():
                return jsonify(readiness_check())
                
            @app.route("/live")
            def live():
                return jsonify(liveness_check())
                
            return
    except ImportError:
        pass
        
    raise ValueError("App must be either FastAPI or Flask instance")