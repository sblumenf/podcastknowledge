"""
Health check endpoints for the Podcast Knowledge Graph Pipeline.

This module provides health and readiness checks for monitoring
and orchestration systems (Kubernetes, Docker, etc.).
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import redis

from ..core.config import PipelineConfig
from ..providers.health import ProviderHealthChecker
from ..utils.resources import get_system_resources
from ..factories.provider_factory import get_provider_factory


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Health status for a single component."""
    
    def __init__(self, name: str, status: HealthStatus, 
                 message: str = "", details: Optional[Dict[str, Any]] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.checked_at = datetime.utcnow().isoformat()


class HealthChecker:
    """Main health checker for the application."""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self._start_time = time.time()
        self._provider_checker = ProviderHealthChecker()
        
    def _check_neo4j(self) -> ComponentHealth:
        """Check Neo4j database health."""
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password),
                max_connection_lifetime=30
            )
            
            with driver.session() as session:
                result = session.run("RETURN 1 as health")
                result.single()
                
            driver.close()
            
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.HEALTHY,
                message="Neo4j is responsive",
                details={
                    "uri": self.config.neo4j_uri,
                    "connected": True
                }
            )
        except ServiceUnavailable as e:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j unavailable: {str(e)}",
                details={
                    "uri": self.config.neo4j_uri,
                    "error": str(e)
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j error: {str(e)}",
                details={
                    "error": str(e)
                }
            )
    
    def _check_redis(self) -> ComponentHealth:
        """Check Redis cache health."""
        if not hasattr(self.config, 'redis_url'):
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis not configured (optional)",
                details={"configured": False}
            )
            
        try:
            r = redis.from_url(self.config.redis_url)
            r.ping()
            
            info = r.info()
            memory_used_mb = info.get('used_memory', 0) / 1024 / 1024
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis is responsive",
                details={
                    "connected": True,
                    "memory_used_mb": round(memory_used_mb, 2),
                    "connected_clients": info.get('connected_clients', 0)
                }
            )
        except redis.ConnectionError as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                message=f"Redis unavailable: {str(e)}",
                details={
                    "error": str(e),
                    "impact": "Caching disabled, performance may be degraded"
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                message=f"Redis error: {str(e)}",
                details={"error": str(e)}
            )
    
    def _check_providers(self) -> List[ComponentHealth]:
        """Check all provider health."""
        results = []
        factory = get_provider_factory()
        
        # Check each provider type
        for provider_type in ['audio', 'llm', 'graph', 'embeddings']:
            try:
                provider = factory.get_provider(provider_type)
                health_result = self._provider_checker.check_provider(provider)
                
                status = HealthStatus.HEALTHY if health_result['healthy'] else HealthStatus.UNHEALTHY
                results.append(ComponentHealth(
                    name=f"provider_{provider_type}",
                    status=status,
                    message=health_result.get('message', ''),
                    details=health_result
                ))
            except Exception as e:
                results.append(ComponentHealth(
                    name=f"provider_{provider_type}",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Provider check failed: {str(e)}",
                    details={"error": str(e)}
                ))
                
        return results
    
    def _check_schemaless_extraction(self) -> ComponentHealth:
        """Check schemaless extraction availability."""
        try:
            # Check if schemaless extraction is enabled
            schemaless_enabled = getattr(self.config, 'use_schemaless_extraction', False)
            
            if not schemaless_enabled:
                return ComponentHealth(
                    name="schemaless_extraction",
                    status=HealthStatus.HEALTHY,
                    message="Schemaless extraction not enabled",
                    details={
                        "enabled": False,
                        "mode": "fixed"
                    }
                )
            
            # Check SimpleKGPipeline connectivity
            try:
                from neo4j_graphrag import SimpleKGPipeline
                # Just verify the import works
                return ComponentHealth(
                    name="schemaless_extraction",
                    status=HealthStatus.HEALTHY,
                    message="Schemaless extraction available",
                    details={
                        "enabled": True,
                        "mode": "schemaless",
                        "simple_kg_pipeline": "available"
                    }
                )
            except ImportError:
                return ComponentHealth(
                    name="schemaless_extraction",
                    status=HealthStatus.DEGRADED,
                    message="SimpleKGPipeline not available",
                    details={
                        "enabled": True,
                        "mode": "schemaless",
                        "simple_kg_pipeline": "not_installed",
                        "impact": "Schemaless extraction will fail"
                    }
                )
                
        except Exception as e:
            return ComponentHealth(
                name="schemaless_extraction",
                status=HealthStatus.DEGRADED,
                message=f"Schemaless check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def _check_system_resources(self) -> ComponentHealth:
        """Check system resource usage."""
        try:
            resources = get_system_resources()
            
            # Determine health based on resource usage
            status = HealthStatus.HEALTHY
            warnings = []
            
            if resources['memory_percent'] > 90:
                status = HealthStatus.UNHEALTHY
                warnings.append("Memory usage critical")
            elif resources['memory_percent'] > 80:
                status = HealthStatus.DEGRADED
                warnings.append("Memory usage high")
                
            if resources['disk_percent'] > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append("Disk space critical")
            elif resources['disk_percent'] > 85:
                status = HealthStatus.DEGRADED
                warnings.append("Disk space low")
                
            message = "; ".join(warnings) if warnings else "System resources healthy"
            
            return ComponentHealth(
                name="system_resources",
                status=status,
                message=message,
                details=resources
            )
        except Exception as e:
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.DEGRADED,
                message=f"Resource check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def check_health_async(self) -> Dict[str, Any]:
        """Perform all health checks asynchronously."""
        loop = asyncio.get_event_loop()
        
        # Run checks in parallel
        tasks = [
            loop.run_in_executor(None, self._check_neo4j),
            loop.run_in_executor(None, self._check_redis),
            loop.run_in_executor(None, self._check_system_resources),
            loop.run_in_executor(None, self._check_schemaless_extraction),
        ]
        
        # Add provider checks
        provider_task = loop.run_in_executor(None, self._check_providers)
        tasks.append(provider_task)
        
        results = await asyncio.gather(*tasks)
        
        # Flatten provider results
        components = []
        for result in results:
            if isinstance(result, list):
                components.extend(result)
            else:
                components.append(result)
        
        # Determine overall status
        statuses = [c.status for c in components]
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
            
        return self._format_response(overall_status, components)
    
    def check_health(self) -> Dict[str, Any]:
        """Perform all health checks synchronously."""
        components = []
        
        # Check core components
        components.append(self._check_neo4j())
        components.append(self._check_redis())
        components.append(self._check_system_resources())
        components.append(self._check_schemaless_extraction())
        
        # Check providers
        components.extend(self._check_providers())
        
        # Determine overall status
        statuses = [c.status for c in components]
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
            
        return self._format_response(overall_status, components)
    
    def check_readiness(self) -> Dict[str, Any]:
        """Check if the application is ready to serve requests."""
        # For readiness, we only check critical components
        neo4j_health = self._check_neo4j()
        
        # Check if critical providers are available
        factory = get_provider_factory()
        try:
            audio_provider = factory.get_provider('audio')
            llm_provider = factory.get_provider('llm')
            ready = neo4j_health.status != HealthStatus.UNHEALTHY
        except Exception:
            ready = False
            
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "checks": {
                "neo4j": neo4j_health.status.value,
                "providers": "available" if ready else "unavailable"
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
    
    def _format_response(self, overall_status: HealthStatus, 
                        components: List[ComponentHealth]) -> Dict[str, Any]:
        """Format health check response."""
        return {
            "status": overall_status.value,
            "healthy": overall_status == HealthStatus.HEALTHY,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self._start_time),
            "components": {
                c.name: {
                    "status": c.status.value,
                    "healthy": c.status == HealthStatus.HEALTHY,
                    "message": c.message,
                    "details": c.details,
                    "checked_at": c.checked_at
                }
                for c in components
            }
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
                checker = get_health_checker()
                return await checker.check_health_async()
                
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