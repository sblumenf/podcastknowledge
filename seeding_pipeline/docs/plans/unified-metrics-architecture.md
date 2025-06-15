# Unified Metrics Architecture Design

## Task 1.2: Design for Consolidated Metrics System

### Design Principles
1. **Simplicity**: Use straightforward inheritance, no complex patterns
2. **Compatibility**: Preserve all existing functionality
3. **Resource Efficiency**: Single monitoring thread, minimal memory usage
4. **Extensibility**: Easy to add new metric types

### Architecture Overview

```
/src/monitoring/
├── __init__.py           # Public API exports
├── metrics.py            # Core metric types (Counter, Gauge, Histogram, Summary)
├── content_metrics.py    # Content analysis metrics (from processing/metrics.py)
├── performance_metrics.py # Pipeline performance tracking
├── api_metrics.py        # API-specific metrics and Prometheus export
└── resource_monitor.py   # Unified resource monitoring (CPU, memory)
```

### Core Components

#### 1. Base Metrics (`metrics.py`)
Adopt the Prometheus-style metric types from `api/metrics.py` as the foundation:

```python
# Base classes
class Metric:
    """Base metric class with labels support"""
    
class Counter(Metric):
    """Monotonic counter"""
    
class Gauge(Metric):
    """Value that can go up and down"""
    
class Histogram(Metric):
    """Distribution of values"""
    
class Summary(Metric):
    """Statistical summary over time window"""
```

#### 2. Content Metrics (`content_metrics.py`)
Preserve the existing content analysis logic:

```python
# Keep existing dataclasses and algorithms
@dataclass
class ComplexityMetrics:
    """Metrics for text complexity analysis"""

@dataclass
class InformationDensityMetrics:
    """Metrics for information density analysis"""

@dataclass
class AccessibilityMetrics:
    """Metrics for content accessibility analysis"""

class ContentMetricsCalculator:
    """Calculator for content metrics (from MetricsCalculator)"""
```

#### 3. Performance Metrics (`performance_metrics.py`)
Consolidate pipeline performance tracking:

```python
class PerformanceMetrics:
    """Pipeline performance tracking with anomaly detection"""
    
    def __init__(self):
        # Use base metric types
        self.file_processing_duration = Histogram(...)
        self.api_calls = Counter(...)
        self.db_latency = Histogram(...)
        
        # Anomaly detection from utils/metrics.py
        self.thresholds = {...}
        self._anomaly_callbacks = []
```

#### 4. API Metrics (`api_metrics.py`)
Prometheus export and HTTP integration:

```python
class MetricsCollector:
    """Central collector with Prometheus export"""
    
    def __init__(self):
        self.content_metrics = ContentMetricsCalculator()
        self.performance_metrics = PerformanceMetrics()
        
    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus format"""
```

#### 5. Resource Monitor (`resource_monitor.py`)
Single implementation for resource monitoring:

```python
class ResourceMonitor:
    """Unified resource monitoring (singleton)"""
    
    def __init__(self):
        self.memory_gauge = Gauge("memory_usage_mb")
        self.cpu_gauge = Gauge("cpu_usage_percent")
        self._monitoring_thread = None
        
    def start_monitoring(self):
        """Start single background thread"""
```

### Migration Path

1. **Phase 1**: Create new structure without removing old code
2. **Phase 2**: Update imports one module at a time
3. **Phase 3**: Verify functionality with tests
4. **Phase 4**: Remove old implementations

### Key Consolidations

1. **Single Resource Monitor**
   - One background thread instead of multiple
   - Shared psutil integration
   - Consistent sampling intervals

2. **Unified Metric Types**
   - Use Prometheus-style base classes
   - All metrics support labels
   - Consistent API across all metrics

3. **Centralized Export**
   - Single point for Prometheus export
   - Optional JSON export for debugging
   - Extensible for other formats

4. **Preserved Functionality**
   - Content analysis algorithms unchanged
   - Anomaly detection maintained
   - Neo4j integration preserved
   - All decorators still work

### Benefits

1. **Code Reduction**: ~40% less code in metrics modules
2. **Clarity**: Clear separation of concerns
3. **Performance**: Single monitoring thread reduces overhead
4. **Maintainability**: One place to fix bugs or add features
5. **Consistency**: Same metric API everywhere

### Backward Compatibility

To ensure smooth migration:
1. Keep same function signatures
2. Maintain decorator compatibility
3. Support existing metric names
4. Preserve threshold configurations