"""Unified resource monitoring for CPU, memory, and disk usage.

This module consolidates resource monitoring from both utils/metrics.py
and api/metrics.py into a single, efficient implementation.
"""

import threading
import time
import logging
from typing import Dict, Any, Optional

from .metrics import Gauge
from src.core.dependencies import get_psutil, get_memory_info, get_cpu_info, PSUTIL_AVAILABLE

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Unified resource monitoring with single background thread.
    
    This class consolidates all resource monitoring into one place,
    eliminating duplicate psutil calls and multiple monitoring threads.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Ensure singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize resource monitor (only once due to singleton)."""
        if self._initialized:
            return
            
        # Metrics
        self.memory_usage_mb = Gauge(
            "system_memory_usage_mb",
            "Current memory usage in MB"
        )
        
        self.memory_usage_percent = Gauge(
            "system_memory_usage_percent",
            "Current memory usage percentage"
        )
        
        self.cpu_usage_percent = Gauge(
            "system_cpu_usage_percent",
            "Current CPU usage percentage"
        )
        
        self.cpu_count = Gauge(
            "system_cpu_count",
            "Number of CPU cores"
        )
        
        # Process-specific metrics
        self.process_memory_mb = Gauge(
            "process_memory_usage_mb",
            "Process memory usage in MB"
        )
        
        self.process_cpu_percent = Gauge(
            "process_cpu_usage_percent",
            "Process CPU usage percentage"
        )
        
        # Monitoring state
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        self._monitoring_interval = 10  # seconds
        
        # Cache for latest values
        self._latest_metrics = {
            'memory_mb': 0,
            'memory_percent': 0,
            'cpu_percent': 0,
            'process_memory_mb': 0,
            'process_cpu_percent': 0
        }
        
        self._initialized = True
        logger.info("ResourceMonitor initialized")
    
    def start_monitoring(self, interval: int = 10):
        """Start background monitoring thread.
        
        Args:
            interval: Seconds between metric updates
        """
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.debug("Monitoring already running")
            return
        
        self._monitoring_interval = interval
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitoring_thread.start()
        logger.info(f"Started resource monitoring with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        if self._monitoring_thread:
            logger.info("Stopping resource monitoring")
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5)
            self._monitoring_thread = None
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            # Wait for next interval
            self._stop_monitoring.wait(self._monitoring_interval)
    
    def _collect_metrics(self):
        """Collect all resource metrics."""
        if not PSUTIL_AVAILABLE:
            # Set default values when psutil not available
            self._set_default_metrics()
            return
        
        # Get memory info
        mem_info = get_memory_info()
        self.memory_usage_mb.set(mem_info['system_memory_mb'])
        self.memory_usage_percent.set(mem_info['memory_percent'])
        self.process_memory_mb.set(mem_info['process_memory_mb'])
        
        # Get CPU info
        cpu_info = get_cpu_info()
        self.cpu_usage_percent.set(cpu_info['system_cpu_percent'])
        self.cpu_count.set(cpu_info['cpu_count'])
        self.process_cpu_percent.set(cpu_info['process_cpu_percent'])
        
        # Update cache
        self._latest_metrics.update({
            'memory_mb': mem_info['system_memory_mb'],
            'memory_percent': mem_info['memory_percent'],
            'cpu_percent': cpu_info['system_cpu_percent'],
            'process_memory_mb': mem_info['process_memory_mb'],
            'process_cpu_percent': cpu_info['process_cpu_percent']
        })
        
        logger.debug(f"Collected metrics: Memory={mem_info['process_memory_mb']:.1f}MB, "
                    f"CPU={cpu_info['process_cpu_percent']:.1f}%")
    
    def _set_default_metrics(self):
        """Set default metrics when psutil is not available."""
        self.memory_usage_mb.set(0)
        self.memory_usage_percent.set(0)
        self.cpu_usage_percent.set(0)
        self.cpu_count.set(1)
        self.process_memory_mb.set(0)
        self.process_cpu_percent.set(0)
        
        # Clear cache
        for key in self._latest_metrics:
            self._latest_metrics[key] = 0
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current resource metrics.
        
        Returns:
            Dictionary of current metrics
        """
        # If monitoring not running, collect once
        if not self._monitoring_thread or not self._monitoring_thread.is_alive():
            self._collect_metrics()
        
        return {
            'system': {
                'memory_mb': self.memory_usage_mb.get(),
                'memory_percent': self.memory_usage_percent.get(),
                'cpu_percent': self.cpu_usage_percent.get(),
                'cpu_count': int(self.cpu_count.get())
            },
            'process': {
                'memory_mb': self.process_memory_mb.get(),
                'cpu_percent': self.process_cpu_percent.get()
            },
            'psutil_available': PSUTIL_AVAILABLE
        }
    
    def get_latest_metrics(self) -> Dict[str, float]:
        """Get cached latest metrics (no collection).
        
        Returns:
            Dictionary of cached metrics
        """
        return dict(self._latest_metrics)
    
    def check_memory_threshold(self, threshold_mb: float) -> bool:
        """Check if process memory exceeds threshold.
        
        Args:
            threshold_mb: Memory threshold in MB
            
        Returns:
            True if memory exceeds threshold
        """
        current_mb = self._latest_metrics['process_memory_mb']
        return current_mb > threshold_mb
    
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active.
        
        Returns:
            True if monitoring thread is running
        """
        return (self._monitoring_thread is not None and 
                self._monitoring_thread.is_alive())
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information (compatibility method).
        
        Returns:
            Dictionary with memory metrics
        """
        # Use the existing get_memory_info from dependencies
        mem_info = get_memory_info()
        
        # Add compatibility fields
        return {
            'available_memory_mb': mem_info.get('system_memory_mb', 0),
            'process_memory_mb': mem_info.get('process_memory_mb', 0),
            'memory_percent': mem_info.get('memory_percent', 0),
            **mem_info  # Include all original fields
        }
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information (compatibility method).
        
        Returns:
            Dictionary with CPU metrics
        """
        # Use the existing get_cpu_info from dependencies
        cpu_info_data = get_cpu_info()
        
        # Ensure required fields are present
        return {
            'cpu_count': cpu_info_data.get('cpu_count', 1),
            'cpu_percent': cpu_info_data.get('cpu_percent', 0),
            **cpu_info_data  # Include all original fields
        }


# Global instance getter
def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance.
    
    Returns:
        ResourceMonitor singleton instance
    """
    return ResourceMonitor()