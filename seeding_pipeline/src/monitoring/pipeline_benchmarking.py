"""
Comprehensive pipeline performance benchmarking.

This module provides detailed timing measurements throughout the pipeline,
tracking both phase-level and unit-level performance metrics.
"""

import time
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar
from statistics import mean, median
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class UnitMetrics:
    """Metrics for a single meaningful unit processing."""
    unit_id: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    extraction_type: Optional[str] = None  # 'combined' or 'separate'


@dataclass
class PhaseMetrics:
    """Metrics for a pipeline phase."""
    phase_name: str
    episode_id: str
    start_time: float
    end_time: float = 0.0
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    unit_metrics: List[UnitMetrics] = field(default_factory=list)


class PipelineBenchmark:
    """Tracks comprehensive performance metrics for pipeline execution."""
    
    def __init__(self):
        """Initialize pipeline benchmark tracking."""
        self.current_episode_id: Optional[str] = None
        self.phase_metrics: Dict[str, PhaseMetrics] = {}
        self.episode_start_time: Optional[float] = None
        self.episode_end_time: Optional[float] = None
        
    def start_episode(self, episode_id: str):
        """Start tracking a new episode."""
        self.current_episode_id = episode_id
        self.episode_start_time = time.time()
        self.phase_metrics.clear()
        logger.info(f"Started benchmarking episode: {episode_id}")
        
    def end_episode(self):
        """End episode tracking and generate summary."""
        if not self.episode_start_time:
            return
            
        self.episode_end_time = time.time()
        total_duration = self.episode_end_time - self.episode_start_time
        
        # Generate and log summary
        summary = self.generate_summary()
        logger.info(f"Episode {self.current_episode_id} completed in {total_duration:.2f}s")
        logger.info(f"Performance Summary:\n{json.dumps(summary, indent=2)}")
        
        # Save to file
        self._save_summary(summary)
        
    def start_phase(self, phase_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Start tracking a pipeline phase."""
        if not self.current_episode_id:
            return
            
        phase_key = f"{self.current_episode_id}:{phase_name}"
        self.phase_metrics[phase_key] = PhaseMetrics(
            phase_name=phase_name,
            episode_id=self.current_episode_id,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
    def end_phase(self, phase_name: str):
        """End tracking a pipeline phase."""
        if not self.current_episode_id:
            return
            
        phase_key = f"{self.current_episode_id}:{phase_name}"
        if phase_key in self.phase_metrics:
            phase = self.phase_metrics[phase_key]
            phase.end_time = time.time()
            phase.duration = phase.end_time - phase.start_time
            
            logger.info(
                f"Phase '{phase_name}' for episode {self.current_episode_id} "
                f"completed in {phase.duration:.2f}s"
            )
            
    def track_unit_processing(
        self, 
        unit_id: str, 
        start_time: float, 
        end_time: float,
        success: bool,
        error: Optional[str] = None,
        extraction_type: Optional[str] = None
    ):
        """Track metrics for a single unit processing."""
        duration = end_time - start_time
        unit_metrics = UnitMetrics(
            unit_id=unit_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=success,
            error=error,
            extraction_type=extraction_type
        )
        
        # Add to current phase if in knowledge extraction
        phase_key = f"{self.current_episode_id}:knowledge_extraction"
        if phase_key in self.phase_metrics:
            self.phase_metrics[phase_key].unit_metrics.append(unit_metrics)
            
    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive performance summary."""
        if not self.episode_start_time:
            return {}
            
        total_duration = (self.episode_end_time or time.time()) - self.episode_start_time
        
        # Phase summaries
        phase_summaries = {}
        for phase_key, metrics in self.phase_metrics.items():
            phase_name = metrics.phase_name
            
            # Unit processing statistics
            unit_stats = {}
            if metrics.unit_metrics:
                durations = [u.duration for u in metrics.unit_metrics]
                successful = [u for u in metrics.unit_metrics if u.success]
                
                unit_stats = {
                    'total_units': len(metrics.unit_metrics),
                    'successful_units': len(successful),
                    'failed_units': len(metrics.unit_metrics) - len(successful),
                    'average_duration': mean(durations),
                    'median_duration': median(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'total_unit_time': sum(durations),
                    'extraction_types': {
                        'combined': len([u for u in metrics.unit_metrics if u.extraction_type == 'combined']),
                        'separate': len([u for u in metrics.unit_metrics if u.extraction_type == 'separate'])
                    }
                }
            
            phase_summaries[phase_name] = {
                'duration': metrics.duration,
                'percentage_of_total': (metrics.duration / total_duration * 100) if total_duration > 0 else 0,
                'metadata': metrics.metadata,
                'unit_stats': unit_stats
            }
        
        # Overall statistics
        return {
            'episode_id': self.current_episode_id,
            'timestamp': datetime.now().isoformat(),
            'total_duration_seconds': total_duration,
            'total_duration_minutes': total_duration / 60,
            'phases': phase_summaries,
            'performance_indicators': {
                'extraction_parallelization': self._calculate_parallelization_factor(),
                'combined_extraction_usage': self._calculate_combined_extraction_percentage(),
                'average_unit_processing_time': self._calculate_average_unit_time()
            }
        }
        
    def _calculate_parallelization_factor(self) -> float:
        """Calculate how much parallelization improved performance."""
        phase_key = f"{self.current_episode_id}:knowledge_extraction"
        if phase_key not in self.phase_metrics:
            return 1.0
            
        metrics = self.phase_metrics[phase_key]
        if not metrics.unit_metrics:
            return 1.0
            
        # Total time if processed sequentially
        sequential_time = sum(u.duration for u in metrics.unit_metrics)
        
        # Actual parallel time
        parallel_time = metrics.duration
        
        if parallel_time > 0:
            return sequential_time / parallel_time
        return 1.0
        
    def _calculate_combined_extraction_percentage(self) -> float:
        """Calculate percentage of units using combined extraction."""
        phase_key = f"{self.current_episode_id}:knowledge_extraction"
        if phase_key not in self.phase_metrics:
            return 0.0
            
        metrics = self.phase_metrics[phase_key]
        if not metrics.unit_metrics:
            return 0.0
            
        combined_count = len([u for u in metrics.unit_metrics if u.extraction_type == 'combined'])
        total_count = len(metrics.unit_metrics)
        
        return (combined_count / total_count * 100) if total_count > 0 else 0.0
        
    def _calculate_average_unit_time(self) -> float:
        """Calculate average time per meaningful unit."""
        phase_key = f"{self.current_episode_id}:knowledge_extraction"
        if phase_key not in self.phase_metrics:
            return 0.0
            
        metrics = self.phase_metrics[phase_key]
        if not metrics.unit_metrics:
            return 0.0
            
        durations = [u.duration for u in metrics.unit_metrics]
        return mean(durations)
        
    def _save_summary(self, summary: Dict[str, Any]):
        """Save performance summary to file."""
        # Create performance directory if it doesn't exist
        perf_dir = Path("performance_reports")
        perf_dir.mkdir(exist_ok=True)
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = perf_dir / f"performance_{self.current_episode_id}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Performance summary saved to {filename}")


# Global benchmark instance
_benchmark = PipelineBenchmark()


def time_phase(phase_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator to time pipeline phases with comprehensive tracking.
    
    Args:
        phase_name: Name of the phase (defaults to function name)
        metadata: Additional metadata to track
        
    Example:
        @time_phase("vtt_parsing")
        def parse_vtt(file_path):
            # Parse VTT file
            return segments
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            name = phase_name or func.__name__
            
            # Start phase tracking
            _benchmark.start_phase(name, metadata)
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # End phase tracking
                _benchmark.end_phase(name)
                
                return result
                
            except Exception as e:
                # Still end phase tracking on error
                _benchmark.end_phase(name)
                raise
                
        return wrapper
    return decorator


def get_benchmark() -> PipelineBenchmark:
    """Get the global benchmark instance."""
    return _benchmark


def create_performance_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a comprehensive performance report.
    
    Args:
        output_path: Optional path to save the report
        
    Returns:
        Performance report dictionary
    """
    summary = _benchmark.generate_summary()
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
            
    return summary