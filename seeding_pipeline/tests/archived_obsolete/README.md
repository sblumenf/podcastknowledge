# Archived Obsolete Tests

This directory was created to archive obsolete tests, but during the import resolution process, we discovered that all the tests identified as obsolete had already been removed from the codebase.

## Summary of Obsolete Tests

The following tests were identified in `import_errors.txt` but no longer exist in the codebase:

### API Tests
- `tests/api/test_v1_api.py` - API v1 functionality moved or removed
- `tests/unit/test_metrics.py` - Metrics testing consolidated elsewhere

### E2E/Performance Tests  
- `tests/e2e/test_e2e_scenarios.py` - E2E scenarios consolidated
- `tests/performance/load_test.py` - Performance testing approach changed
- `tests/performance/test_performance_regression.py` - Performance regression testing approach changed

### Utility Tests
- `tests/unit/test_retry_comprehensive.py` - Consolidated into test_retry.py
- `tests/unit/test_retry_utils.py` - Consolidated into test_retry.py
- `tests/unit/test_rate_limiting_utils.py` - Rate limiting tests consolidated
- `tests/unit/test_segmentation.py` - Moved to processing folder
- `tests/unit/test_validation_comprehensive.py` - Validation tests consolidated
- `tests/utils/test_validation.py` - Moved to unit folder
- `tests/utils/test_text_processing.py` - Had syntax errors, removed
- `tests/unit/test_text_processing_comprehensive.py` - Had syntax errors, removed

### Other Tests with Syntax Errors
- `tests/seeding/test_concurrency.py` - Concurrency testing moved or removed
- `tests/unit/test_error_handling_utils.py` - Had syntax errors
- `tests/unit/test_logging.py` - Had syntax errors
- `tests/unit/test_orchestrator_unit.py` - Had syntax errors

## Resolution

Since these files were already removed from the codebase, no archiving action was needed. The import errors were from a stale error report that referenced tests that had already been deleted or consolidated as part of the VTT-only pipeline cleanup.

## Current State

All remaining tests in the test suite can now be collected without import errors after fixing two syntax errors in:
- `tests/integration/test_failure_recovery.py` - Fixed malformed import statement
- `tests/unit/test_schemaless_adapter_unit.py` - Fixed malformed import statement