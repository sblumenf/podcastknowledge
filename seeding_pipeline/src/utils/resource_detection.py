"""
Automatic resource detection and configuration.

This module detects available system resources and provides
recommendations for optimal configuration based on the system's capabilities.
"""

import os
import multiprocessing
from typing import Dict, Any, Tuple

from src.core.dependencies import get_psutil, PSUTIL_AVAILABLE, get_memory_info


def get_available_memory_mb() -> int:
    """Get available system memory in MB."""
    if PSUTIL_AVAILABLE:
        psutil = get_psutil()
        memory = psutil.virtual_memory()
        # Use available memory (not total) to be conservative
        return int(memory.available / (1024 * 1024))
    else:
        # Fallback: try to read from /proc/meminfo on Linux
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        # MemAvailable is in kB
                        kb = int(line.split()[1])
                        return int(kb / 1024)
        except:
            pass
        
        # Conservative default if we can't detect
        return 2048  # 2GB


def get_cpu_count() -> int:
    """Get number of CPU cores."""
    try:
        # Use os.cpu_count() which is available in Python 3.4+
        count = os.cpu_count()
        return count if count else 2
    except:
        # Fallback to multiprocessing
        try:
            return multiprocessing.cpu_count()
        except:
            return 2  # Conservative default


def detect_system_resources() -> Dict[str, Any]:
    """Detect system resources and return configuration."""
    resources = {
        'memory_mb': get_available_memory_mb(),
        'cpu_count': get_cpu_count(),
        'is_low_resource': False,
        'recommendations': {}
    }
    
    # Determine if this is a low-resource system
    # Consider systems with < 4GB available memory as low-resource
    if resources['memory_mb'] < 4096:
        resources['is_low_resource'] = True
    
    # Make recommendations based on resources
    resources['recommendations'] = calculate_recommendations(
        resources['memory_mb'],
        resources['cpu_count'],
        resources['is_low_resource']
    )
    
    return resources


def calculate_recommendations(memory_mb: int, cpu_count: int, is_low_resource: bool) -> Dict[str, Any]:
    """Calculate recommended settings based on available resources."""
    recommendations = {}
    
    if is_low_resource:
        # Low resource settings (< 4GB RAM)
        recommendations['MAX_MEMORY_MB'] = min(memory_mb // 2, 1024)  # Use max 50% of available, cap at 1GB
        recommendations['MAX_CONCURRENT_FILES'] = 1  # Process files sequentially
        recommendations['BATCH_SIZE'] = 5  # Small batches
        recommendations['MAX_WORKERS'] = min(cpu_count, 2)  # Limit workers
        recommendations['ENABLE_ENHANCED_LOGGING'] = False  # Disable to save memory
        recommendations['ENABLE_METRICS'] = False  # Disable to save memory
    else:
        # Normal resource settings (>= 4GB RAM)
        recommendations['MAX_MEMORY_MB'] = min(memory_mb // 3, 4096)  # Use max 33% of available, cap at 4GB
        recommendations['MAX_CONCURRENT_FILES'] = min(cpu_count // 2, 4)  # Half CPU cores, max 4
        recommendations['BATCH_SIZE'] = 10  # Default batch size
        recommendations['MAX_WORKERS'] = min(cpu_count, 8)  # All cores, max 8
        recommendations['ENABLE_ENHANCED_LOGGING'] = True  # Enable features
        recommendations['ENABLE_METRICS'] = True  # Enable features
    
    return recommendations


def apply_low_resource_mode() -> None:
    """Apply low-resource mode settings to environment if not already set."""
    # Get current resource detection
    resources = detect_system_resources()
    recommendations = resources['recommendations']
    
    # Apply recommendations as environment variables if not already set
    for key, value in recommendations.items():
        if not os.getenv(key):
            os.environ[key] = str(value)
    
    # Set a flag indicating low-resource mode
    if resources['is_low_resource']:
        os.environ['LOW_RESOURCE_MODE'] = 'true'


def get_resource_summary() -> str:
    """Get a human-readable summary of detected resources and recommendations."""
    resources = detect_system_resources()
    
    lines = [
        "System Resource Detection:",
        f"  Available Memory: {resources['memory_mb']} MB",
        f"  CPU Cores: {resources['cpu_count']}",
        f"  Mode: {'Low Resource' if resources['is_low_resource'] else 'Normal'}",
        "",
        "Recommended Settings:"
    ]
    
    for key, value in resources['recommendations'].items():
        lines.append(f"  {key}: {value}")
    
    if resources['is_low_resource']:
        lines.extend([
            "",
            "💡 Low Resource Mode Tips:",
            "  - Process files one at a time",
            "  - Use smaller batch sizes",
            "  - Consider using Docker with memory limits",
            "  - Close other applications while processing"
        ])
    
    return "\n".join(lines)


def check_resource_requirements(required_mb: int = 1024) -> Tuple[bool, str]:
    """Check if system meets minimum resource requirements."""
    available_mb = get_available_memory_mb()
    
    if available_mb < required_mb:
        return False, f"Insufficient memory: {available_mb}MB available, {required_mb}MB required"
    
    return True, f"Memory check passed: {available_mb}MB available"


# Module initialization - detect resources on import
if __name__ == "__main__":
    # If run directly, print resource summary
    print(get_resource_summary())