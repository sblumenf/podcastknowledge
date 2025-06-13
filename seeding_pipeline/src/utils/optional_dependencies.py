"""
Optional dependency management for resource-constrained environments.

This module provides fallbacks for optional dependencies like psutil
to ensure the application can run even when these packages are not available.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import psutil, but provide fallbacks if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - memory monitoring disabled")


class MockProcess:
    """Mock psutil.Process for when psutil is not available."""
    
    def __init__(self, pid=None):
        self.pid = pid or os.getpid()
    
    def memory_info(self):
        """Return mock memory info."""
        class MemInfo:
            rss = 100 * 1024 * 1024  # Mock 100MB
        return MemInfo()
    
    def memory_percent(self):
        """Return mock memory percentage."""
        return 10.0  # Mock 10%
    
    def cpu_percent(self, interval=None):
        """Return mock CPU percentage."""
        return 5.0  # Mock 5%


class MockPsutil:
    """Mock psutil module for when it's not available."""
    
    Process = MockProcess
    
    @staticmethod
    def cpu_count(logical=True):
        """Return CPU count from os module."""
        try:
            return os.cpu_count() or 1
        except:
            return 1
    
    @staticmethod
    def virtual_memory():
        """Return mock memory stats."""
        class VirtMem:
            total = 4 * 1024 * 1024 * 1024  # Mock 4GB
            available = 2 * 1024 * 1024 * 1024  # Mock 2GB
            percent = 50.0
            used = total - available
        return VirtMem()
    
    @staticmethod
    def swap_memory():
        """Return mock swap stats."""
        class SwapMem:
            total = 0
            used = 0
            percent = 0.0
        return SwapMem()


def get_psutil():
    """Get psutil module or mock if not available."""
    if PSUTIL_AVAILABLE:
        return psutil
    else:
        return MockPsutil()


def get_memory_info() -> Dict[str, Any]:
    """Get memory information with fallback for missing psutil."""
    ps = get_psutil()
    
    try:
        process = ps.Process()
        vm = ps.virtual_memory()
        
        return {
            'process_memory_mb': process.memory_info().rss / 1024 / 1024,
            'process_memory_percent': process.memory_percent(),
            'system_memory_total_mb': vm.total / 1024 / 1024,
            'system_memory_available_mb': vm.available / 1024 / 1024,
            'system_memory_percent': vm.percent,
            'available': PSUTIL_AVAILABLE
        }
    except Exception as e:
        logger.debug(f"Error getting memory info: {e}")
        return {
            'process_memory_mb': 0,
            'process_memory_percent': 0,
            'system_memory_total_mb': 0,
            'system_memory_available_mb': 0,
            'system_memory_percent': 0,
            'available': False,
            'error': str(e)
        }


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information with fallback for missing psutil."""
    ps = get_psutil()
    
    try:
        process = ps.Process()
        
        return {
            'cpu_count': ps.cpu_count(logical=True),
            'process_cpu_percent': process.cpu_percent(interval=0.1),
            'available': PSUTIL_AVAILABLE
        }
    except Exception as e:
        logger.debug(f"Error getting CPU info: {e}")
        return {
            'cpu_count': os.cpu_count() or 1,
            'process_cpu_percent': 0,
            'available': False,
            'error': str(e)
        }