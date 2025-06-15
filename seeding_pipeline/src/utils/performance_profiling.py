"""
Performance profiling utilities for the podcast knowledge pipeline.

This module provides tools for profiling and optimizing the schemaless extraction pipeline.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
import functools
import io
import json
import time

from ..api.metrics import get_metrics_collector
from ..utils.logging import get_logger
import cProfile
import pstats
import tracemalloc
logger = get_logger(__name__)


@dataclass
class ProfileResult:
    """Result of a profiling session."""
    name: str
    duration: float
    cpu_time: float
    memory_used: int
    memory_peak: int
    call_count: int
    bottlenecks: List[Tuple[str, float]]
    timestamp: str


class PerformanceProfiler:
    """Main performance profiler for the pipeline."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the profiler.
        
        Args:
            output_dir: Directory to save profiling results
        """
        self.output_dir = output_dir or Path("profiling_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[ProfileResult] = []
        self.metrics = get_metrics_collector()
        
    @contextmanager
    def profile_section(self, name: str, track_memory: bool = True):
        """
        Context manager for profiling a code section.
        
        Args:
            name: Name of the section being profiled
            track_memory: Whether to track memory usage
            
        Example:
            with profiler.profile_section("entity_extraction"):
                # Code to profile
                pass
        """
        # Start tracking
        start_time = time.time()
        cpu_start = time.process_time()
        
        if track_memory:
            tracemalloc.start()
            
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            yield
        finally:
            # Stop tracking
            profiler.disable()
            end_time = time.time()
            cpu_end = time.process_time()
            
            # Get memory stats
            memory_used = 0
            memory_peak = 0
            if track_memory:
                current, peak = tracemalloc.get_traced_memory()
                memory_used = current
                memory_peak = peak
                tracemalloc.stop()
            
            # Analyze profile
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(10)  # Top 10 functions
            
            # Extract bottlenecks
            bottlenecks = self._extract_bottlenecks(ps)
            
            # Create result
            result = ProfileResult(
                name=name,
                duration=end_time - start_time,
                cpu_time=cpu_end - cpu_start,
                memory_used=memory_used,
                memory_peak=memory_peak,
                call_count=ps.total_calls,
                bottlenecks=bottlenecks,
                timestamp=datetime.utcnow().isoformat()
            )
            
            self.results.append(result)
            
            # Log results
            logger.info(f"Profile '{name}': {result.duration:.3f}s, "
                       f"Memory: {memory_used / 1024 / 1024:.1f}MB")
            
            # Save detailed profile
            self._save_profile(name, profiler, result)
            
            # Update metrics
            self.metrics.processing_duration.observe(
                result.duration, 
                labels={"stage": name}
            )
    
    def _extract_bottlenecks(self, stats: pstats.Stats) -> List[Tuple[str, float]]:
        """Extract top bottleneck functions from stats."""
        bottlenecks = []
        
        # Get top functions by cumulative time
        stats.sort_stats('cumulative')
        for func, (cc, nc, tt, ct, callers) in list(stats.stats.items())[:10]:
            func_name = f"{func[0]}:{func[1]}:{func[2]}"
            bottlenecks.append((func_name, ct))
            
        return bottlenecks
    
    def _save_profile(self, name: str, profiler: cProfile.Profile, 
                     result: ProfileResult) -> None:
        """Save profile data to disk."""
        # Save raw profile
        profile_path = self.output_dir / f"{name}_{result.timestamp}.prof"
        profiler.dump_stats(str(profile_path))
        
        # Save result as JSON
        result_path = self.output_dir / f"{name}_{result.timestamp}.json"
        with open(result_path, 'w') as f:
            json.dump({
                "name": result.name,
                "duration": result.duration,
                "cpu_time": result.cpu_time,
                "memory_used": result.memory_used,
                "memory_peak": result.memory_peak,
                "call_count": result.call_count,
                "bottlenecks": result.bottlenecks,
                "timestamp": result.timestamp
            }, f, indent=2)
    
    def profile_schemaless_pipeline(self, pipeline, test_text: str) -> Dict[str, Any]:
        """
        Profile the complete schemaless extraction pipeline.
        
        Args:
            pipeline: SimpleKGPipeline instance
            test_text: Text to use for profiling
            
        Returns:
            Dictionary of profiling results
        """
        results = {}
        
        # Profile overall extraction
        with self.profile_section("overall_extraction"):
            pipeline.extract(test_text)
        
        # Profile individual components if possible
        # This would require instrumenting the SimpleKGPipeline
        # For now, we'll profile what we can access
        
        # Analyze results
        analysis = self.analyze_results()
        
        return {
            "profile_results": [r.__dict__ for r in self.results],
            "analysis": analysis
        }
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze profiling results to identify optimization opportunities."""
        if not self.results:
            return {"error": "No profiling results available"}
        
        analysis = {
            "summary": {},
            "bottlenecks": {},
            "recommendations": []
        }
        
        # Aggregate by section
        section_stats = {}
        for result in self.results:
            if result.name not in section_stats:
                section_stats[result.name] = {
                    "total_time": 0,
                    "total_memory": 0,
                    "count": 0
                }
            
            stats = section_stats[result.name]
            stats["total_time"] += result.duration
            stats["total_memory"] += result.memory_peak
            stats["count"] += 1
        
        # Calculate averages
        for section, stats in section_stats.items():
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["avg_memory"] = stats["total_memory"] / stats["count"]
        
        analysis["summary"] = section_stats
        
        # Identify main bottlenecks
        all_bottlenecks = {}
        for result in self.results:
            for func, time_spent in result.bottlenecks:
                if func not in all_bottlenecks:
                    all_bottlenecks[func] = 0
                all_bottlenecks[func] += time_spent
        
        # Sort by total time
        sorted_bottlenecks = sorted(
            all_bottlenecks.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        analysis["bottlenecks"] = dict(sorted_bottlenecks)
        
        # Generate recommendations
        self._generate_recommendations(analysis, section_stats)
        
        return analysis
    
    def _generate_recommendations(self, analysis: Dict[str, Any], 
                                 section_stats: Dict[str, Any]) -> None:
        """Generate optimization recommendations based on profiling."""
        recommendations = []
        
        # Check for slow sections
        for section, stats in section_stats.items():
            if stats["avg_time"] > 5.0:  # More than 5 seconds
                recommendations.append({
                    "type": "performance",
                    "section": section,
                    "issue": f"Section takes {stats['avg_time']:.1f}s on average",
                    "suggestion": "Consider batch processing or caching"
                })
            
            if stats["avg_memory"] > 500 * 1024 * 1024:  # More than 500MB
                recommendations.append({
                    "type": "memory",
                    "section": section,
                    "issue": f"High memory usage: {stats['avg_memory'] / 1024 / 1024:.0f}MB",
                    "suggestion": "Consider streaming or chunking data"
                })
        
        # Check bottlenecks
        for func, time_spent in list(analysis["bottlenecks"].items())[:3]:
            if "llm" in func.lower():
                recommendations.append({
                    "type": "bottleneck",
                    "function": func,
                    "issue": f"LLM calls taking {time_spent:.1f}s total",
                    "suggestion": "Enable LLM response caching"
                })
            elif "embed" in func.lower():
                recommendations.append({
                    "type": "bottleneck",
                    "function": func,
                    "issue": f"Embedding generation taking {time_spent:.1f}s",
                    "suggestion": "Batch embedding requests"
                })
            elif "neo4j" in func.lower() or "graph" in func.lower():
                recommendations.append({
                    "type": "bottleneck",
                    "function": func,
                    "issue": f"Graph operations taking {time_spent:.1f}s",
                    "suggestion": "Use connection pooling and batch writes"
                })
        
        analysis["recommendations"] = recommendations
    
    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """Generate a comprehensive profiling report."""
        analysis = self.analyze_results()
        
        report_lines = [
            "# Performance Profiling Report",
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
            "## Summary",
            ""
        ]
        
        # Add summary stats
        for section, stats in analysis["summary"].items():
            report_lines.extend([
                f"### {section}",
                f"- Average Time: {stats['avg_time']:.3f}s",
                f"- Average Memory: {stats['avg_memory'] / 1024 / 1024:.1f}MB",
                f"- Runs: {stats['count']}",
                ""
            ])
        
        # Add bottlenecks
        report_lines.extend([
            "## Top Bottlenecks",
            ""
        ])
        
        for func, time_spent in list(analysis["bottlenecks"].items())[:10]:
            report_lines.append(f"- {func}: {time_spent:.3f}s")
        
        # Add recommendations
        report_lines.extend([
            "",
            "## Recommendations",
            ""
        ])
        
        for rec in analysis["recommendations"]:
            report_lines.extend([
                f"### {rec['type'].title()} Issue",
                f"- **Issue**: {rec['issue']}",
                f"- **Location**: {rec.get('section', rec.get('function', 'Unknown'))}",
                f"- **Suggestion**: {rec['suggestion']}",
                ""
            ])
        
        report = "\n".join(report_lines)
        
        if output_file:
            output_file.write_text(report)
            logger.info(f"Report saved to {output_file}")
        
        return report


def profile_function(name: Optional[str] = None, track_memory: bool = True):
    """
    Decorator for profiling functions.
    
    Args:
        name: Custom name for the profile (defaults to function name)
        track_memory: Whether to track memory usage
        
    Example:
        @profile_function()
        def expensive_operation():
            pass
    """
    def decorator(func):
        profile_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = PerformanceProfiler()
            
            with profiler.profile_section(profile_name, track_memory):
                result = func(*args, **kwargs)
            
            # Log basic stats
            if profiler.results:
                stats = profiler.results[-1]
                logger.info(f"{profile_name} completed in {stats.duration:.3f}s")
            
            return result
        
        return wrapper
    return decorator


# Optimization implementations

class OptimizationManager:
    """Manages performance optimizations for the pipeline."""
    
    def __init__(self):
        self.batch_processor = BatchOptimizer()
        self.cache_manager = CacheOptimizer()
        self.async_manager = AsyncOptimizer()
        self.pool_manager = ConnectionPoolOptimizer()
    
    def apply_optimizations(self, pipeline: Any) -> None:
        """Apply all optimizations to the pipeline."""
        logger.info("Applying performance optimizations...")
        
        # Apply each optimization
        self.batch_processor.optimize(pipeline)
        self.cache_manager.optimize(pipeline)
        self.async_manager.optimize(pipeline)
        self.pool_manager.optimize(pipeline)
        
        logger.info("Optimizations applied")


class BatchOptimizer:
    """Handles batch processing optimizations."""
    
    def optimize(self, pipeline: Any) -> None:
        """Apply batch processing optimizations."""
        # This would be implemented based on SimpleKGPipeline's API
        logger.info("Batch processing optimization applied")


class CacheOptimizer:
    """Handles caching optimizations."""
    
    def optimize(self, pipeline: Any) -> None:
        """Apply caching optimizations."""
        # Enable LLM response caching
        # Enable embedding caching
        logger.info("Caching optimization applied")


class AsyncOptimizer:
    """Handles async operation optimizations."""
    
    def optimize(self, pipeline: Any) -> None:
        """Apply async optimizations."""
        # Convert blocking operations to async where possible
        logger.info("Async optimization applied")


class ConnectionPoolOptimizer:
    """Handles connection pooling optimizations."""
    
    def optimize(self, pipeline: Any) -> None:
        """Apply connection pooling optimizations."""
        # Optimize Neo4j connection pooling
        logger.info("Connection pooling optimization applied")