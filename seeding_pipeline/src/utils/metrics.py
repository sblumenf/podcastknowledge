"""Comprehensive metrics collection and analysis for the VTT pipeline."""

import json
import time
import psutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict, deque

from src.utils.logging import get_logger
from src.utils.logging_enhanced import get_metrics_collector


class PipelineMetrics:
    """Comprehensive metrics tracking for the VTT pipeline."""
    
    def __init__(self, export_interval: int = 60):
        """Initialize pipeline metrics.
        
        Args:
            export_interval: Seconds between automatic metric exports
        """
        self.logger = get_logger(__name__)
        self.collector = get_metrics_collector()
        self.export_interval = export_interval
        
        # Metric tracking
        self._start_time = time.time()
        self._file_metrics = defaultdict(dict)
        self._api_calls = defaultdict(lambda: {'success': 0, 'failure': 0})
        self._memory_samples = deque(maxlen=1000)  # Keep last 1000 samples
        self._db_latencies = deque(maxlen=1000)
        
        # Rate tracking
        self._entity_counts = deque(maxlen=60)  # Last 60 seconds
        self._entity_timestamps = deque(maxlen=60)
        
        # Thresholds for anomaly detection
        self.thresholds = {
            'memory_usage_mb': 2048,  # 2GB
            'db_latency_ms': 1000,    # 1 second
            'api_failure_rate': 0.1,   # 10% failure rate
            'processing_time_s': 600   # 10 minutes per file
        }
        
        # Anomaly callbacks
        self._anomaly_callbacks = []
        
        # Background monitoring
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitoring_thread is None:
            self._stop_monitoring.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitor_system,
                daemon=True
            )
            self._monitoring_thread.start()
            self.logger.info("Started metrics monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        if self._monitoring_thread:
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5)
            self._monitoring_thread = None
            self.logger.info("Stopped metrics monitoring")
    
    def _monitor_system(self):
        """Background thread to collect system metrics."""
        while not self._stop_monitoring.is_set():
            try:
                # Sample memory usage
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self._memory_samples.append({
                    'timestamp': time.time(),
                    'memory_mb': memory_mb,
                    'cpu_percent': process.cpu_percent(interval=0.1)
                })
                
                # Check for anomalies
                if memory_mb > self.thresholds['memory_usage_mb']:
                    self._trigger_anomaly('high_memory', {
                        'current_mb': memory_mb,
                        'threshold_mb': self.thresholds['memory_usage_mb']
                    })
                
                # Record memory metric
                self.collector.record_metric(
                    'system.memory_usage',
                    memory_mb,
                    unit='MB',
                    tags={'type': 'rss'}
                )
                
            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
            
            # Sleep until next sample (1 second intervals)
            self._stop_monitoring.wait(1)
    
    def record_file_processing(self, file_path: str, start_time: float, 
                             end_time: float, segments: int, success: bool):
        """Record metrics for file processing.
        
        Args:
            file_path: Path to the processed file
            start_time: Processing start timestamp
            end_time: Processing end timestamp
            segments: Number of segments processed
            success: Whether processing succeeded
        """
        duration = end_time - start_time
        file_name = Path(file_path).name
        
        self._file_metrics[file_name] = {
            'duration_s': duration,
            'segments': segments,
            'success': success,
            'timestamp': end_time
        }
        
        # Record in metrics collector
        self.collector.record_metric(
            'file_processing.duration',
            duration,
            unit='seconds',
            tags={
                'file': file_name,
                'success': str(success),
                'segments': str(segments)
            }
        )
        
        # Check for anomaly
        if duration > self.thresholds['processing_time_s']:
            self._trigger_anomaly('slow_processing', {
                'file': file_name,
                'duration_s': duration,
                'threshold_s': self.thresholds['processing_time_s']
            })
    
    def record_entity_extraction(self, count: int):
        """Record entity extraction count for rate calculation.
        
        Args:
            count: Number of entities extracted
        """
        current_time = time.time()
        self._entity_counts.append(count)
        self._entity_timestamps.append(current_time)
        
        # Calculate rate over last minute
        if len(self._entity_timestamps) > 1:
            time_span = self._entity_timestamps[-1] - self._entity_timestamps[0]
            if time_span > 0:
                total_entities = sum(self._entity_counts)
                rate_per_minute = (total_entities / time_span) * 60
                
                self.collector.record_metric(
                    'extraction.entities_per_minute',
                    rate_per_minute,
                    unit='entities/minute'
                )
    
    def record_api_call(self, provider: str, success: bool, latency: float):
        """Record API call metrics.
        
        Args:
            provider: API provider name (e.g., 'gemini', 'openai')
            success: Whether the call succeeded
            latency: Call latency in seconds
        """
        if success:
            self._api_calls[provider]['success'] += 1
        else:
            self._api_calls[provider]['failure'] += 1
        
        # Calculate success rate
        total = self._api_calls[provider]['success'] + self._api_calls[provider]['failure']
        if total > 0:
            success_rate = self._api_calls[provider]['success'] / total
            
            self.collector.record_metric(
                f'api.{provider}.success_rate',
                success_rate,
                unit='ratio',
                tags={'provider': provider}
            )
            
            # Check for anomaly
            failure_rate = 1 - success_rate
            if failure_rate > self.thresholds['api_failure_rate']:
                self._trigger_anomaly('high_api_failure_rate', {
                    'provider': provider,
                    'failure_rate': failure_rate,
                    'threshold': self.thresholds['api_failure_rate']
                })
        
        # Record latency
        self.collector.record_metric(
            f'api.{provider}.latency',
            latency,
            unit='seconds',
            tags={'success': str(success)}
        )
    
    def record_db_operation(self, operation: str, latency: float, success: bool):
        """Record database operation metrics.
        
        Args:
            operation: Operation type (e.g., 'create_node', 'query')
            latency: Operation latency in seconds
            success: Whether the operation succeeded
        """
        self._db_latencies.append(latency)
        
        # Record in collector
        self.collector.record_metric(
            f'db.{operation}.latency',
            latency,
            unit='seconds',
            tags={'success': str(success)}
        )
        
        # Check for anomaly
        latency_ms = latency * 1000
        if latency_ms > self.thresholds['db_latency_ms']:
            self._trigger_anomaly('high_db_latency', {
                'operation': operation,
                'latency_ms': latency_ms,
                'threshold_ms': self.thresholds['db_latency_ms']
            })
    
    def add_anomaly_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a callback for anomaly detection.
        
        Args:
            callback: Function to call when anomaly detected
        """
        self._anomaly_callbacks.append(callback)
    
    def _trigger_anomaly(self, anomaly_type: str, details: Dict[str, Any]):
        """Trigger anomaly callbacks.
        
        Args:
            anomaly_type: Type of anomaly detected
            details: Anomaly details
        """
        self.logger.warning(f"Anomaly detected: {anomaly_type}", extra={
            'anomaly_type': anomaly_type,
            'details': details
        })
        
        # Call registered callbacks
        for callback in self._anomaly_callbacks:
            try:
                callback(anomaly_type, details)
            except Exception as e:
                self.logger.error(f"Error in anomaly callback: {e}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot.
        
        Returns:
            Dictionary of current metrics
        """
        # Calculate aggregates
        total_files = len(self._file_metrics)
        successful_files = sum(1 for f in self._file_metrics.values() if f['success'])
        
        # Memory stats
        if self._memory_samples:
            current_memory = self._memory_samples[-1]['memory_mb']
            avg_memory = sum(s['memory_mb'] for s in self._memory_samples) / len(self._memory_samples)
            max_memory = max(s['memory_mb'] for s in self._memory_samples)
        else:
            current_memory = avg_memory = max_memory = 0
        
        # DB latency stats
        if self._db_latencies:
            avg_db_latency = sum(self._db_latencies) / len(self._db_latencies)
            max_db_latency = max(self._db_latencies)
        else:
            avg_db_latency = max_db_latency = 0
        
        # API stats
        api_stats = {}
        for provider, counts in self._api_calls.items():
            total = counts['success'] + counts['failure']
            if total > 0:
                api_stats[provider] = {
                    'total_calls': total,
                    'success_rate': counts['success'] / total,
                    'failures': counts['failure']
                }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': time.time() - self._start_time,
            'files': {
                'total_processed': total_files,
                'successful': successful_files,
                'failed': total_files - successful_files,
                'average_duration': sum(f['duration_s'] for f in self._file_metrics.values()) / total_files if total_files > 0 else 0
            },
            'memory': {
                'current_mb': current_memory,
                'average_mb': avg_memory,
                'max_mb': max_memory
            },
            'database': {
                'average_latency_ms': avg_db_latency * 1000,
                'max_latency_ms': max_db_latency * 1000,
                'operations_tracked': len(self._db_latencies)
            },
            'api': api_stats,
            'extraction': {
                'entities_per_minute': self._calculate_entity_rate()
            }
        }
    
    def _calculate_entity_rate(self) -> float:
        """Calculate current entity extraction rate."""
        if len(self._entity_timestamps) < 2:
            return 0.0
        
        time_span = self._entity_timestamps[-1] - self._entity_timestamps[0]
        if time_span <= 0:
            return 0.0
        
        total_entities = sum(self._entity_counts)
        return (total_entities / time_span) * 60
    
    def export_metrics(self, output_path: Optional[str] = None) -> str:
        """Export metrics to JSON file.
        
        Args:
            output_path: Optional output path (auto-generated if not provided)
            
        Returns:
            Path to exported file
        """
        if output_path is None:
            output_dir = Path("metrics")
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"pipeline_metrics_{timestamp}.json"
        
        metrics = {
            'current_snapshot': self.get_current_metrics(),
            'detailed_metrics': self.collector.get_metrics(),
            'file_details': dict(self._file_metrics),
            'thresholds': self.thresholds
        }
        
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        self.logger.info(f"Exported metrics to {output_path}")
        return str(output_path)


# Global metrics instance
_pipeline_metrics = None


def get_pipeline_metrics() -> PipelineMetrics:
    """Get the global pipeline metrics instance."""
    global _pipeline_metrics
    if _pipeline_metrics is None:
        _pipeline_metrics = PipelineMetrics()
        _pipeline_metrics.start_monitoring()
    return _pipeline_metrics


def cleanup_metrics():
    """Clean up metrics monitoring."""
    global _pipeline_metrics
    if _pipeline_metrics:
        _pipeline_metrics.stop_monitoring()
        _pipeline_metrics = None