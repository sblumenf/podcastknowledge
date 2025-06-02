"""
Performance profiling decorator for component analysis.

This module provides decorators to track performance metrics for individual components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional
import functools
import time

from ..api.metrics import get_metrics_collector
from ..utils.component_tracker import get_component_tracker
from ..utils.logging import get_logger
try:
    import psutil
except ImportError:
    # Use mock psutil if real one not available
    from tests.utils import mock_psutil as psutil
import tracemalloc
logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    component_name: str
    execution_time: float
    memory_used: int
    memory_peak: int
    cpu_percent: float
    tokens_used: Optional[int] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class PerformanceTracker:
    """Tracks performance metrics for components."""
    
    def __init__(self):
        self.metrics_collector = get_metrics_collector()
        self.component_tracker = get_component_tracker()
        self.process = psutil.Process()
        
    def track_performance(self, component_name: str, func: Callable, 
                         *args, **kwargs) -> tuple[Any, PerformanceMetrics]:
        """
        Track performance of a function execution.
        
        Returns:
            Tuple of (function result, performance metrics)
        """
        # Start tracking
        tracemalloc.start()
        start_time = time.time()
        start_memory = self.process.memory_info().rss
        cpu_before = self.process.cpu_percent(interval=0.1)
        
        try:
            # Execute function
            result = func(*args, **kwargs)
            
            # Capture metrics
            end_time = time.time()
            execution_time = end_time - start_time
            
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            end_memory = self.process.memory_info().rss
            memory_used = end_memory - start_memory
            cpu_after = self.process.cpu_percent(interval=0.1)
            cpu_percent = (cpu_after + cpu_before) / 2
            
            # Extract token usage if available
            tokens_used = None
            if hasattr(result, '__token_usage__'):
                tokens_used = result.__token_usage__
            
            # Create metrics
            metrics = PerformanceMetrics(
                component_name=component_name,
                execution_time=execution_time,
                memory_used=memory_used,
                memory_peak=peak,
                cpu_percent=cpu_percent,
                tokens_used=tokens_used
            )
            
            # Record metrics
            self._record_metrics(metrics)
            
            return result, metrics
            
        except Exception as e:
            tracemalloc.stop()
            logger.error(f"Error tracking performance for {component_name}: {e}")
            raise
    
    def _record_metrics(self, metrics: PerformanceMetrics) -> None:
        """Record metrics to various collectors."""
        # Update Prometheus metrics
        self.metrics_collector.processing_duration.observe(
            metrics.execution_time,
            labels={"stage": f"component_{metrics.component_name}"}
        )
        
        self.metrics_collector.memory_usage.set(metrics.memory_used)
        self.metrics_collector.cpu_usage.set(metrics.cpu_percent)
        
        # Track with component tracker
        with self.component_tracker.track_impact(metrics.component_name) as impact:
            impact.add_metadata("execution_time", metrics.execution_time)
            impact.add_metadata("memory_used", metrics.memory_used)
            impact.add_metadata("cpu_percent", metrics.cpu_percent)
            if metrics.tokens_used:
                impact.add_metadata("tokens_used", metrics.tokens_used)


def profile_performance(component_name: Optional[str] = None,
                       track_memory: bool = True,
                       track_tokens: bool = False):
    """
    Decorator to profile component performance.
    
    Args:
        component_name: Name of the component (defaults to function name)
        track_memory: Whether to track memory usage
        track_tokens: Whether to track LLM token usage
        
    Example:
        @profile_performance(component_name="entity_extraction")
        def extract_entities(text):
            # Process text
            return entities
    """
    def decorator(func: Callable) -> Callable:
        name = component_name or func.__name__
        tracker = PerformanceTracker()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if profiling is enabled
            from ..core.feature_flags import FeatureFlag, is_enabled
            if not is_enabled(FeatureFlag.LOG_SCHEMA_DISCOVERY):
                return func(*args, **kwargs)
            
            # Track performance
            result, metrics = tracker.track_performance(name, func, *args, **kwargs)
            
            # Log summary
            logger.info(
                f"Component '{name}' completed in {metrics.execution_time:.3f}s, "
                f"Memory: {metrics.memory_used / 1024 / 1024:.1f}MB"
            )
            
            return result
        
        # Mark as profiled
        wrapper.__profiled__ = True
        wrapper.__component_name__ = name
        
        return wrapper
    return decorator


def track_llm_tokens(func: Callable) -> Callable:
    """
    Decorator to track LLM token usage.
    
    This decorator should be used on functions that call LLM providers.
    It extracts token usage from the LLM response.
    
    Example:
        @track_llm_tokens
        def generate_insights(text, llm_provider):
            response = llm_provider.generate(prompt)
            return response
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # Try to extract token usage from result
        token_usage = None
        
        # Check if result has token usage info
        if hasattr(result, 'usage'):
            token_usage = {
                'prompt_tokens': getattr(result.usage, 'prompt_tokens', 0),
                'completion_tokens': getattr(result.usage, 'completion_tokens', 0),
                'total_tokens': getattr(result.usage, 'total_tokens', 0)
            }
        elif isinstance(result, dict) and 'usage' in result:
            token_usage = result['usage']
        
        # Attach token usage to result
        if token_usage:
            if hasattr(result, '__dict__'):
                result.__token_usage__ = token_usage
            elif isinstance(result, dict):
                result['__token_usage__'] = token_usage
        
        # Log token usage
        if token_usage:
            logger.debug(f"LLM tokens used: {token_usage}")
        
        return result
    
    return wrapper


def create_performance_dashboard(output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a performance dashboard from collected metrics.
    
    Args:
        output_path: Path to save dashboard data (optional)
        
    Returns:
        Dashboard data dictionary
    """
    tracker = get_component_tracker()
    metrics_collector = get_metrics_collector()
    
    # Generate impact report
    impact_report = tracker.generate_impact_report()
    
    # Get metrics summary
    metrics_summary = metrics_collector.get_summary()
    
    # Create dashboard data
    dashboard = {
        "generated_at": datetime.utcnow().isoformat(),
        "component_impacts": impact_report,
        "performance_metrics": metrics_summary,
        "recommendations": _generate_performance_recommendations(impact_report, metrics_summary)
    }
    
    # Save if path provided
    if output_path:
        import json
        with open(output_path, 'w') as f:
            json.dump(dashboard, f, indent=2)
        logger.info(f"Performance dashboard saved to {output_path}")
    
    return dashboard


def _generate_performance_recommendations(impact_report: Dict[str, Any], 
                                        metrics_summary: Dict[str, Any]) -> List[str]:
    """Generate performance recommendations based on collected data."""
    recommendations = []
    
    # Check for slow components
    for component, stats in impact_report.get("components", {}).items():
        if stats.get("avg_time", 0) > 1.0:
            recommendations.append(
                f"Optimize {component}: average execution time is {stats['avg_time']:.1f}s"
            )
    
    # Check memory usage
    if metrics_summary.get("resources", {}).get("memory_mb", 0) > 1000:
        recommendations.append(
            "High memory usage detected. Consider implementing streaming or chunking."
        )
    
    # Check for redundant components
    redundant = impact_report.get("recommendations", [])
    for rec in redundant:
        if rec.get("type") == "no_additions":
            recommendations.append(
                f"Component '{rec['component']}' adds no value - consider removing"
            )
    
    return recommendations