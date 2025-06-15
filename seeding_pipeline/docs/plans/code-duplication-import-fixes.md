# Code Duplication Import Fixes - Corrective Plan

## Issue Summary
During the objective review of the code duplication resolution, 3 minor import issues were identified that need correction.

## Tasks

### Task 1: Fix api/app.py Import
**File**: `/src/api/app.py`
**Line**: 12
**Current**: `from .metrics import setup_metrics`
**Fix**: `from ..monitoring import setup_metrics`

### Task 2: Fix api/metrics_integration.py Import
**File**: `/src/api/metrics_integration.py`
**Line**: 10
**Current**: `from .metrics import get_metrics_collector, track_duration, track_provider_call`
**Fix**: `from ..monitoring import get_metrics_collector, track_duration, track_api_call`

Note: `track_provider_call` should be `track_api_call` based on the monitoring module exports.

### Task 3: Fix test patch path
**File**: `/tests/unit/test_api.py`
**Line**: 135
**Current**: `@patch('src.api.metrics.MetricsCollector.get_metrics')`
**Fix**: `@patch('src.monitoring.api_metrics.MetricsCollector.get_metrics')`

### Task 4: Add missing method or update test
The test expects a `get_metrics()` method on `MetricsCollector` class, but this method doesn't exist. Either:
- Add a `get_metrics()` method to `MetricsCollector` that returns metrics in dictionary format, or
- Update the test to use the existing `export_prometheus()` method

## Success Criteria
- All imports resolve correctly
- No import errors when running the application
- API tests pass with correct metric collection