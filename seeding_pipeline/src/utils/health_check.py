"""System health monitoring for VTT pipeline."""

import os
import time
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import shutil

from src.utils.logging import get_logger
from src.utils.metrics import get_pipeline_metrics


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Health status for a single component."""
    
    def __init__(self, name: str, status: str, message: str, 
                 details: Optional[Dict[str, Any]] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.checked_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'checked_at': self.checked_at
        }


class HealthChecker:
    """System health checker for VTT pipeline."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize health checker.
        
        Args:
            config: Optional configuration overrides
        """
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Default thresholds
        self.thresholds = {
            'memory_percent': self.config.get('memory_threshold', 80),
            'disk_percent': self.config.get('disk_threshold', 90),
            'disk_min_gb': self.config.get('disk_min_gb', 1.0),
            'api_timeout': self.config.get('api_timeout', 5.0),
            'db_timeout': self.config.get('db_timeout', 5.0),
        }
        
        # Component check functions
        self._component_checks = {
            'system': self.check_system_resources,
            'neo4j': self.check_neo4j,
            'llm_api': self.check_llm_api,
            'checkpoints': self.check_checkpoint_storage,
            'metrics': self.check_metrics_system,
        }
    
    def check_all(self) -> Dict[str, Any]:
        """Run all health checks.
        
        Returns:
            Dictionary with overall status and component details
        """
        start_time = time.time()
        component_results = []
        
        # Run each component check
        for component_name, check_func in self._component_checks.items():
            try:
                result = check_func()
                component_results.append(result)
            except Exception as e:
                self.logger.error(f"Error checking {component_name}: {e}")
                component_results.append(
                    ComponentHealth(
                        name=component_name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Check failed: {str(e)}"
                    )
                )
        
        # Determine overall status
        statuses = [r.status for r in component_results]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        check_duration = time.time() - start_time
        
        return {
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': check_duration,
            'components': [r.to_dict() for r in component_results],
            'summary': self._generate_summary(overall_status, component_results)
        }
    
    def check_system_resources(self) -> ComponentHealth:
        """Check system memory and CPU resources."""
        try:
            # Memory check
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024 ** 3)
            
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            
            details = {
                'memory_percent_used': memory_percent,
                'memory_available_gb': round(memory_available_gb, 2),
                'cpu_percent': cpu_percent,
                'process_count': len(psutil.pids())
            }
            
            # Determine status
            if memory_percent > self.thresholds['memory_percent']:
                return ComponentHealth(
                    name='system',
                    status=HealthStatus.DEGRADED,
                    message=f"High memory usage: {memory_percent:.1f}%",
                    details=details
                )
            
            return ComponentHealth(
                name='system',
                status=HealthStatus.HEALTHY,
                message="System resources are healthy",
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                name='system',
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check system resources: {str(e)}"
            )
    
    def check_neo4j(self) -> ComponentHealth:
        """Check Neo4j database connectivity."""
        try:
            from src.storage import GraphStorageService
            
            # Get connection details from environment
            uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            username = os.getenv('NEO4J_USER', 'neo4j')
            password = os.getenv('NEO4J_PASSWORD', '')
            
            if not password:
                return ComponentHealth(
                    name='neo4j',
                    status=HealthStatus.UNHEALTHY,
                    message="Neo4j password not configured"
                )
            
            # Try to connect and run simple query
            start_time = time.time()
            storage = GraphStorageService(uri, username, password)
            
            # Run health check query
            result = storage.query("RETURN 1 as health_check LIMIT 1")
            query_time = time.time() - start_time
            
            if result and result[0].get('health_check') == 1:
                return ComponentHealth(
                    name='neo4j',
                    status=HealthStatus.HEALTHY,
                    message="Neo4j is accessible",
                    details={
                        'uri': uri,
                        'response_time_ms': round(query_time * 1000, 2),
                        'connected': True
                    }
                )
            else:
                return ComponentHealth(
                    name='neo4j',
                    status=HealthStatus.UNHEALTHY,
                    message="Neo4j query failed",
                    details={'uri': uri}
                )
                
        except Exception as e:
            return ComponentHealth(
                name='neo4j',
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j connection failed: {str(e)}",
                details={
                    'error_type': type(e).__name__,
                    'configured': bool(os.getenv('NEO4J_PASSWORD'))
                }
            )
    
    def check_llm_api(self) -> ComponentHealth:
        """Check LLM API availability."""
        try:
            # Check for API key
            api_key = os.getenv('GOOGLE_API_KEY', '')
            if not api_key:
                return ComponentHealth(
                    name='llm_api',
                    status=HealthStatus.UNHEALTHY,
                    message="Google API key not configured"
                )
            
            # Try to initialize service (doesn't make actual call)
            from src.services import LLMService
            service = LLMService(provider="google", model="gemini-pro")
            
            # Check rate limit status
            rate_status = service.get_rate_limit_status()
            
            return ComponentHealth(
                name='llm_api',
                status=HealthStatus.HEALTHY,
                message="LLM API is configured",
                details={
                    'provider': 'google',
                    'model': 'gemini-pro',
                    'api_key_configured': True,
                    'rate_limit_status': rate_status
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name='llm_api',
                status=HealthStatus.DEGRADED,
                message=f"LLM API check partial: {str(e)}",
                details={
                    'api_key_configured': bool(os.getenv('GOOGLE_API_KEY')),
                    'error_type': type(e).__name__
                }
            )
    
    def check_checkpoint_storage(self) -> ComponentHealth:
        """Check checkpoint directory storage."""
        try:
            checkpoint_dir = Path(self.config.get('checkpoint_dir', 'checkpoints'))
            
            # Create directory if it doesn't exist
            checkpoint_dir.mkdir(exist_ok=True, parents=True)
            
            # Check disk space
            stat = shutil.disk_usage(checkpoint_dir)
            disk_free_gb = stat.free / (1024 ** 3)
            disk_percent_used = (stat.used / stat.total) * 100
            
            # Count checkpoint files
            checkpoint_files = list(checkpoint_dir.glob('*.ckpt*'))
            checkpoint_size_mb = sum(f.stat().st_size for f in checkpoint_files) / (1024 ** 2)
            
            details = {
                'checkpoint_dir': str(checkpoint_dir),
                'disk_free_gb': round(disk_free_gb, 2),
                'disk_percent_used': round(disk_percent_used, 1),
                'checkpoint_count': len(checkpoint_files),
                'checkpoint_size_mb': round(checkpoint_size_mb, 2)
            }
            
            # Check thresholds
            if disk_free_gb < self.thresholds['disk_min_gb']:
                return ComponentHealth(
                    name='checkpoints',
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low disk space: {disk_free_gb:.1f}GB free",
                    details=details
                )
            elif disk_percent_used > self.thresholds['disk_percent']:
                return ComponentHealth(
                    name='checkpoints',
                    status=HealthStatus.DEGRADED,
                    message=f"High disk usage: {disk_percent_used:.1f}%",
                    details=details
                )
            
            return ComponentHealth(
                name='checkpoints',
                status=HealthStatus.HEALTHY,
                message="Checkpoint storage is healthy",
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                name='checkpoints',
                status=HealthStatus.UNHEALTHY,
                message=f"Checkpoint storage check failed: {str(e)}"
            )
    
    def check_metrics_system(self) -> ComponentHealth:
        """Check metrics collection system."""
        try:
            metrics = get_pipeline_metrics()
            current_metrics = metrics.get_current_metrics()
            
            details = {
                'uptime_seconds': round(current_metrics['uptime_seconds'], 1),
                'metrics_collected': len(current_metrics.get('detailed_metrics', {}).get('metrics', {})),
                'monitoring_active': metrics._monitoring_thread is not None and metrics._monitoring_thread.is_alive()
            }
            
            if details['monitoring_active']:
                return ComponentHealth(
                    name='metrics',
                    status=HealthStatus.HEALTHY,
                    message="Metrics system is active",
                    details=details
                )
            else:
                return ComponentHealth(
                    name='metrics',
                    status=HealthStatus.DEGRADED,
                    message="Metrics monitoring thread not active",
                    details=details
                )
                
        except Exception as e:
            return ComponentHealth(
                name='metrics',
                status=HealthStatus.UNHEALTHY,
                message=f"Metrics system check failed: {str(e)}"
            )
    
    def _generate_summary(self, overall_status: str, 
                         components: List[ComponentHealth]) -> str:
        """Generate summary message based on component statuses."""
        unhealthy = [c.name for c in components if c.status == HealthStatus.UNHEALTHY]
        degraded = [c.name for c in components if c.status == HealthStatus.DEGRADED]
        
        if overall_status == HealthStatus.HEALTHY:
            return "All systems operational"
        elif unhealthy:
            return f"Critical issues with: {', '.join(unhealthy)}"
        elif degraded:
            return f"Degraded performance in: {', '.join(degraded)}"
        else:
            return "System status unknown"
    
    def get_cli_summary(self) -> str:
        """Get formatted summary for CLI output."""
        health_data = self.check_all()
        
        # Status indicators
        status_icons = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.DEGRADED: "⚠️",
            HealthStatus.UNHEALTHY: "❌"
        }
        
        lines = [
            "=" * 50,
            "VTT Pipeline Health Check",
            "=" * 50,
            f"Overall Status: {status_icons.get(health_data['status'], '❓')} {health_data['status'].upper()}",
            f"Checked at: {health_data['timestamp']}",
            "",
            "Component Status:",
            "-" * 40
        ]
        
        for component in health_data['components']:
            icon = status_icons.get(component['status'], '❓')
            lines.append(f"{icon} {component['name']:<15} - {component['message']}")
            
            # Add key details for some components
            if component['details']:
                if component['name'] == 'system':
                    lines.append(f"   Memory: {component['details']['memory_percent_used']:.1f}% used")
                    lines.append(f"   CPU: {component['details']['cpu_percent']:.1f}%")
                elif component['name'] == 'neo4j' and component['status'] == HealthStatus.HEALTHY:
                    lines.append(f"   Response time: {component['details']['response_time_ms']:.1f}ms")
                elif component['name'] == 'checkpoints':
                    lines.append(f"   Free space: {component['details']['disk_free_gb']:.1f}GB")
                    lines.append(f"   Checkpoints: {component['details']['checkpoint_count']} files")
        
        lines.extend([
            "",
            "-" * 40,
            f"Summary: {health_data['summary']}",
            f"Check duration: {health_data['duration_seconds']:.2f}s"
        ])
        
        return "\n".join(lines)


# Global health checker instance
_health_checker = None


def get_health_checker(config: Optional[Dict[str, Any]] = None) -> HealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(config)
    return _health_checker