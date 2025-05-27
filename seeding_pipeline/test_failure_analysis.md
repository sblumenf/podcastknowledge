# Test Failure Analysis Report

Generated: 2025-05-27

## Summary

Total tests attempted to collect: ~1000+
Successfully collected: 68 (from smoke and unit tests)
Collection errors: 44

## Failure Categories

### 1. Import Errors (86 occurrences)
- **Primary Cause**: Circular import between `src/processing/extraction.py` and `src/processing/strategies/extraction_factory.py`
- **Affected Files**: Most test files cannot be imported due to cascading effect
- **Impact**: ~90% of tests cannot even be collected

### 2. Circular Import Errors (41 occurrences)
- **Specific Issue**: `extraction.py` line 1287 tries to import `ExtractionFactory` from `extraction_factory.py`, which already imports from `extraction.py`
- **Root Cause**: Poor module organization with bidirectional dependencies

### 3. Other Errors
- **Missing Module**: 1 occurrence (redis module was missing, now fixed)
- **Syntax Error**: 1 occurrence in `test_domain_diversity.py` (await outside async function)
- **Unparseable Files**: 
  - `src/migration/cli.py`
  - `src/seeding/components/pipeline_executor.py`

## Successfully Running Tests

### Smoke Tests (tests/test_smoke.py)
- 10 tests passed
- 1 test skipped
- Tests basic functionality without importing main modules

### Unit Tests (partial)
- `test_config.py`: Tests configuration loading
- `test_models.py`: Tests data models  
- `test_core_imports.py`: Tests core module imports
- `test_tracing.py`: Tests tracing functionality

## Critical Issues

1. **Circular Dependency**: The circular import between extraction.py and extraction_factory.py prevents ~90% of tests from running
2. **Module Organization**: The current module structure has too many interdependencies
3. **Test Isolation**: Tests are not properly isolated from implementation details

## Recommendations for Phase 3

1. **Fix Circular Import** (Priority 1)
   - Move shared types/interfaces to a separate module
   - Refactor extraction_factory.py to avoid importing extraction.py
   
2. **Fix Syntax Errors** (Priority 2)
   - Fix async/await usage in test_domain_diversity.py
   
3. **Fix Unparseable Files** (Priority 3)
   - Review and fix syntax in cli.py and pipeline_executor.py

## Test Execution Time

Unable to generate timing report due to import errors. Most tests fail at collection phase.