"""Performance metrics for pipeline execution monitoring.

This module consolidates pipeline performance tracking from utils/metrics.py,
including anomaly detection, file processing metrics, and API tracking.
"""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import threading
import logging

from .metrics import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Comprehensive performance tracking for the VTT pipeline.
    
    Consolidates functionality from utils/metrics.py with improvements
    for reduced memory usage and cleaner API.
    """
    
    def __init__(self):
        """Initialize performance metrics."""
        # Core metrics using base types
        self.file_processing_duration = Histogram(
            "pipeline_file_processing_duration_seconds",
            "Time spent processing files",
            labels=["file", "success"]
        )
        
        self.api_calls = Counter(
            "pipeline_api_calls_total",
            "Total API calls",
            labels=["provider", "method", "success"]
        )
        
        self.api_latency = Histogram(
            "pipeline_api_latency_seconds",
            "API call latency",
            labels=["provider", "method"]
        )
        
        self.db_operations = Counter(
            "pipeline_db_operations_total",
            "Total database operations",
            labels=["operation", "success"]
        )
        
        self.db_latency = Histogram(
            "pipeline_db_latency_seconds",
            "Database operation latency",
            labels=["operation"]
        )
        
        self.entities_extracted = Counter(
            "pipeline_entities_extracted_total",
            "Total entities extracted"
        )
        
        self.entity_extraction_rate = Gauge(
            "pipeline_entity_extraction_rate_per_minute",
            "Current entity extraction rate"
        )
        
        # File processing tracking
        self._file_metrics = {}
        self._file_lock = threading.Lock()
        
        # Rate calculation
        self._entity_counts = deque(maxlen=60)  # Last 60 seconds
        self._entity_timestamps = deque(maxlen=60)
        
        # Anomaly detection
        self.thresholds = {
            'memory_usage_mb': 2048,  # 2GB
            'db_latency_ms': 1000,    # 1 second
            'api_failure_rate': 0.1,   # 10% failure rate
            'processing_time_s': 600   # 10 minutes per file
        }
        
        self._anomaly_callbacks = []
        self._anomaly_lock = threading.Lock()
        
        # Track API success rates
        self._api_success_counts = defaultdict(lambda: {'success': 0, 'total': 0})
        
        # Start time for uptime tracking
        self._start_time = time.time()
    
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
        
        # Record in histogram
        self.file_processing_duration.observe(
            duration,
            labels={
                "file": file_path.split('/')[-1],  # Just filename
                "success": str(success)
            }
        )
        
        # Store detailed metrics
        with self._file_lock:
            self._file_metrics[file_path] = {
                'duration_s': duration,
                'segments': segments,
                'success': success,
                'timestamp': end_time
            }
        
        # Check for anomaly
        if duration > self.thresholds['processing_time_s']:
            self._trigger_anomaly('slow_processing', {
                'file': file_path,
                'duration_s': duration,
                'threshold_s': self.thresholds['processing_time_s']
            })
    
    def record_entity_extraction(self, count: int):
        """Record entity extraction count for rate calculation.
        
        Args:
            count: Number of entities extracted
        """
        current_time = time.time()
        
        # Update counter
        self.entities_extracted.inc(count)
        
        # Track for rate calculation
        self._entity_counts.append(count)
        self._entity_timestamps.append(current_time)
        
        # Calculate and update rate
        rate = self._calculate_entity_rate()
        if rate > 0:
            self.entity_extraction_rate.set(rate)
    
    def record_api_call(self, provider: str, method: str, success: bool, latency: float):
        """Record API call metrics.
        
        Args:
            provider: API provider name (e.g., 'gemini', 'openai')
            method: API method called
            success: Whether the call succeeded
            latency: Call latency in seconds
        """
        # Record counter
        self.api_calls.inc(labels={
            "provider": provider,
            "method": method,
            "success": str(success)
        })
        
        # Record latency
        self.api_latency.observe(latency, labels={
            "provider": provider,
            "method": method
        })
        
        # Track success rate
        key = f"{provider}:{method}"
        self._api_success_counts[key]['total'] += 1
        if success:
            self._api_success_counts[key]['success'] += 1
        
        # Check failure rate
        stats = self._api_success_counts[key]
        if stats['total'] >= 10:  # Need at least 10 calls
            failure_rate = 1 - (stats['success'] / stats['total'])
            if failure_rate > self.thresholds['api_failure_rate']:
                self._trigger_anomaly('high_api_failure_rate', {
                    'provider': provider,
                    'method': method,
                    'failure_rate': failure_rate,
                    'threshold': self.thresholds['api_failure_rate']
                })
    
    def record_db_operation(self, operation: str, latency: float, success: bool):
        """Record database operation metrics.
        
        Args:
            operation: Operation type (e.g., 'create_node', 'query')
            latency: Operation latency in seconds
            success: Whether the operation succeeded
        """
        # Record counter
        self.db_operations.inc(labels={
            "operation": operation,
            "success": str(success)
        })
        
        # Record latency
        self.db_latency.observe(latency, labels={
            "operation": operation
        })
        
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
        with self._anomaly_lock:
            self._anomaly_callbacks.append(callback)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current metrics summary.
        
        Returns:
            Dictionary of current metrics
        """
        # File processing stats
        with self._file_lock:
            total_files = len(self._file_metrics)
            successful_files = sum(1 for f in self._file_metrics.values() if f['success'])
            avg_duration = (
                sum(f['duration_s'] for f in self._file_metrics.values()) / total_files
                if total_files > 0 else 0
            )
        
        # API success rates
        api_stats = {}
        for key, counts in self._api_success_counts.items():
            provider, method = key.split(':', 1)
            if provider not in api_stats:
                api_stats[provider] = {}
            
            total = counts['total']
            if total > 0:
                api_stats[provider][method] = {
                    'total_calls': total,
                    'success_rate': counts['success'] / total
                }
        
        # Get histogram stats
        file_processing_stats = self.file_processing_duration.get_stats()
        db_latency_stats = self.db_latency.get_stats()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': time.time() - self._start_time,
            'files': {
                'total_processed': total_files,
                'successful': successful_files,
                'failed': total_files - successful_files,
                'average_duration_s': avg_duration,
                'p95_duration_s': file_processing_stats.get('p95', 0),
                'p99_duration_s': file_processing_stats.get('p99', 0)
            },
            'entities': {
                'total_extracted': self.entities_extracted.get(),
                'extraction_rate_per_minute': self.entity_extraction_rate.get()
            },
            'database': {
                'total_operations': self.db_operations.get(),
                'average_latency_ms': db_latency_stats.get('mean', 0) * 1000,
                'p95_latency_ms': db_latency_stats.get('p95', 0) * 1000,
                'p99_latency_ms': db_latency_stats.get('p99', 0) * 1000
            },
            'api': api_stats
        }
    
    def _calculate_entity_rate(self) -> float:
        """Calculate current entity extraction rate."""
        if len(self._entity_timestamps) < 2:
            return 0.0
        
        # Remove old entries
        current_time = time.time()
        cutoff = current_time - 60  # Keep last minute
        
        while self._entity_timestamps and self._entity_timestamps[0] < cutoff:
            self._entity_timestamps.popleft()
            self._entity_counts.popleft()
        
        if len(self._entity_timestamps) < 2:
            return 0.0
        
        time_span = self._entity_timestamps[-1] - self._entity_timestamps[0]
        if time_span <= 0:
            return 0.0
        
        total_entities = sum(self._entity_counts)
        return (total_entities / time_span) * 60  # Per minute
    
    def _trigger_anomaly(self, anomaly_type: str, details: Dict[str, Any]):
        """Trigger anomaly callbacks.
        
        Args:
            anomaly_type: Type of anomaly detected
            details: Anomaly details
        """
        logger.warning(f"Anomaly detected: {anomaly_type}", extra={
            'anomaly_type': anomaly_type,
            'details': details
        })
        
        # Call registered callbacks
        with self._anomaly_lock:
            for callback in self._anomaly_callbacks:
                try:
                    callback(anomaly_type, details)
                except Exception as e:
                    logger.error(f"Error in anomaly callback: {e}")
    
    def update_threshold(self, threshold_name: str, value: float):
        """Update an anomaly detection threshold.
        
        Args:
            threshold_name: Name of the threshold
            value: New threshold value
        """
        if threshold_name in self.thresholds:
            self.thresholds[threshold_name] = value
            logger.info(f"Updated threshold {threshold_name} to {value}")
        else:
            raise ValueError(f"Unknown threshold: {threshold_name}")
    
    def get_file_metrics(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed file processing metrics.
        
        Args:
            file_path: Specific file to get metrics for (or None for all)
            
        Returns:
            File metrics dictionary
        """
        with self._file_lock:
            if file_path:
                return self._file_metrics.get(file_path, {})
            else:
                return dict(self._file_metrics)