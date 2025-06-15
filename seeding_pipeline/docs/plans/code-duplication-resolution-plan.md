# Code Duplication Resolution Plan

## Validation Summary (2025-06-15)

**Overall Status**: 85% COMPLETE
- ✅ Phase 1: Metrics Consolidation - COMPLETE
- ⚠️ Phase 2: Optional Dependencies - INCOMPLETE (2 files not deleted)
- ⚠️ Phase 3: Embeddings Service - INCOMPLETE (1 file not deleted)  
- ✅ Phase 4: Storage Coordination - COMPLETE
- ✅ Phase 5: Pipeline Executors - COMPLETE
- ✅ Phase 6: Logging System - COMPLETE
- ✅ Phase 7: Resource Monitoring - COMPLETE
- ✅ Phase 8: Test Utilities - COMPLETE
- ✅ Phase 9: Final Cleanup - COMPLETE

**Files Still Requiring Deletion**:
- src/utils/optional_dependencies.py
- src/utils/optional_google.py
- src/services/embeddings_gemini.py

See [code-duplication-validation-report.md](code-duplication-validation-report.md) for detailed validation results.

## Executive Summary

This plan eliminates all identified code duplication in the seeding pipeline, reducing codebase size by 15-20% while improving maintainability. The refactoring consolidates 8 major areas of duplication into clean, single-responsibility modules. Since the code is not yet deployed and has no external dependencies, we can make bold simplifications focused on long-term maintainability.

## Phase 1: Metrics Consolidation

### Objective
Merge three separate metrics systems into one unified monitoring framework.

### Tasks

- [x] **Task 1.1: Analyze existing metrics implementations**
  - Purpose: Understand all metrics functionality before consolidation
  - Steps:
    1. Use context7 MCP tool to review metrics documentation
    2. Read `/src/processing/metrics.py` and document all metric types
    3. Read `/src/utils/metrics.py` and document all metric types
    4. Read `/src/api/metrics.py` and document all metric types
    5. Create comparison table of overlapping functionality
  - Validation: Documented list of all unique metrics across all three files

- [x] **Task 1.2: Design unified metrics architecture**
  - Purpose: Create simple, extensible metrics system
  - Steps:
    1. Create new directory structure: `/src/monitoring/`
    2. Design base `Metric` class with common functionality
    3. Design specialized classes: `ContentMetric`, `PerformanceMetric`, `APIMetric`
    4. Plan migration of existing metric collections
  - Validation: Architecture diagram saved in plan directory

- [x] **Task 1.3: Implement unified metrics module**
  - Purpose: Create single source of truth for all metrics
  - Steps:
    1. Create `/src/monitoring/metrics.py` with base classes
    2. Implement `ContentMetrics` class (from processing/metrics.py)
    3. Implement `PerformanceMetrics` class (from utils/metrics.py)
    4. Implement `APIMetrics` class (from api/metrics.py)
    5. Create `/src/monitoring/__init__.py` with clean exports
  - Validation: All metrics accessible through single import

- [x] **Task 1.4: Update all metric consumers**
  - Purpose: Point all code to new unified metrics
  - Steps:
    1. Search for all imports of old metrics modules
    2. Update imports to use new `/src/monitoring/metrics.py`
    3. Adjust any API differences in consuming code
    4. Verify no broken imports with static analysis
  - Validation: No imports of old metrics modules remain

- [x] **Task 1.5: Remove old metrics modules**
  - Purpose: Clean up duplicated code
  - Steps:
    1. Delete `/src/processing/metrics.py`
    2. Delete `/src/utils/metrics.py`
    3. Delete `/src/api/metrics.py`
    4. Run full test suite to ensure nothing breaks
  - Validation: Old files deleted, all tests pass

## Phase 2: Optional Dependencies Consolidation

### Objective
Merge three optional dependency handlers into one clean module.

### Tasks

- [x] **Task 2.1: Analyze dependency handling patterns**
  - Purpose: Understand all optional dependency use cases
  - Steps:
    1. Use context7 MCP tool for dependency management documentation
    2. Read `/src/utils/optional_dependencies.py`
    3. Read `/src/utils/optional_deps.py`
    4. Read `/src/utils/optional_google.py`
    5. List all handled dependencies and their mock implementations
  - Validation: Complete list of optional dependencies and handling patterns

- [x] **Task 2.2: Create unified dependency handler**
  - Purpose: Single, consistent way to handle all optional dependencies
  - Steps:
    1. Create `/src/core/dependencies.py`
    2. Implement `OptionalDependency` class with lazy loading
    3. Create registry of all optional dependencies
    4. Implement consistent mock/fallback pattern
    5. Add clear error messages for missing dependencies
  - Validation: All dependencies accessible through single module

- [x] **Task 2.3: Migrate all dependency imports**
  - Purpose: Use new unified handler everywhere
  - Steps:
    1. Search for imports from old optional dependency modules
    2. Update to use new `/src/core/dependencies.py`
    3. Test each migration to ensure functionality preserved
    4. Update any dependency-specific logic
  - Validation: No old dependency imports remain

- [ ] **Task 2.4: Remove old dependency modules** ⚠️ INCOMPLETE - optional_dependencies.py and optional_google.py still exist
  - Purpose: Clean up duplicated code
  - Steps:
    1. Delete `/src/utils/optional_dependencies.py`
    2. Delete `/src/utils/optional_deps.py`
    3. Delete `/src/utils/optional_google.py`
    4. Verify all functionality still works
  - Validation: Old files deleted, dependency handling works

## Phase 3: Embeddings Service Simplification

### Objective
Consolidate three embeddings implementations into one.

### Tasks

- [x] **Task 3.1: Review embeddings implementations**
  - Purpose: Understand current usage and requirements
  - Steps:
    1. Use context7 MCP tool for embeddings documentation
    2. Read `/src/services/embeddings.py`
    3. Read `/src/services/embeddings_backup.py`
    4. Read `/src/services/embeddings_gemini.py`
    5. Confirm embeddings.py is just a wrapper
  - Validation: Clear understanding of which implementation is actually used

- [x] **Task 3.2: Consolidate to single embeddings service**
  - Purpose: Remove unnecessary abstraction layers
  - Steps:
    1. Move all Gemini logic into `/src/services/embeddings.py`
    2. Remove wrapper pattern if not needed
    3. Ensure clean interface for embeddings generation
    4. Add proper error handling for API failures
  - Validation: Single, clear embeddings implementation

- [ ] **Task 3.3: Clean up old implementations** ⚠️ INCOMPLETE - embeddings_gemini.py still exists
  - Purpose: Remove dead code
  - Steps:
    1. Delete `/src/services/embeddings_backup.py`
    2. Delete `/src/services/embeddings_gemini.py`
    3. Update any remaining references
    4. Test embeddings functionality
  - Validation: Only one embeddings file remains, functionality intact

## Phase 4: Storage Coordination Refactoring

### Objective
Eliminate duplication between single and multi-database storage implementations.

### Tasks

- [x] **Task 4.1: Analyze storage implementations**
  - Purpose: Understand duplication patterns
  - Steps:
    1. Use context7 MCP tool for storage documentation
    2. Compare `/src/storage/storage_coordinator.py` and `multi_database_storage_coordinator.py`
    3. Compare `/src/storage/graph_storage.py` and `multi_database_graph_storage.py`
    4. Identify common code that can be extracted
  - Validation: List of duplicated methods and logic

- [x] **Task 4.2: Create base storage classes**
  - Purpose: Share common logic through inheritance
  - Steps:
    1. Create `/src/storage/base.py`
    2. Extract common storage coordinator logic to `BaseStorageCoordinator`
    3. Extract common graph storage logic to `BaseGraphStorage`
    4. Implement connection management once in base classes
    5. Add abstract methods for specialized behavior
  - Validation: Base classes contain all common functionality

- [x] **Task 4.3: Refactor storage implementations**
  - Purpose: Use inheritance to eliminate duplication
  - Steps:
    1. Update `StorageCoordinator` to extend `BaseStorageCoordinator`
    2. Update `MultiDatabaseStorageCoordinator` to extend base
    3. Update `GraphStorage` to extend `BaseGraphStorage`
    4. Update `MultiDatabaseGraphStorage` to extend base
    5. Remove all duplicated code
  - Validation: Each class only contains unique logic

## Phase 5: Pipeline Executor Consolidation

### Objective
Extract common pipeline execution logic into shared components.

### Tasks

- [x] **Task 5.1: Analyze pipeline patterns**
  - Purpose: Identify common execution patterns
  - Steps:
    1. Use context7 MCP tool for pipeline documentation
    2. Review all pipeline executor implementations
    3. Identify common patterns: error handling, checkpointing, progress tracking
    4. Document VTT processing similarities
  - Validation: List of common patterns across all executors

- [x] **Task 5.2: Create pipeline base classes**
  - Purpose: Share common pipeline logic
  - Steps:
    1. Create `/src/pipeline/base.py`
    2. Implement `BasePipelineExecutor` with common methods
    3. Extract checkpoint management to base class
    4. Extract progress tracking to base class
    5. Create shared VTT processing utilities
  - Validation: Base class handles all common functionality

- [x] **Task 5.3: Refactor pipeline executors**
  - Purpose: Eliminate duplicated code
  - Steps:
    1. Update each executor to extend `BasePipelineExecutor`
    2. Remove duplicated error handling
    3. Remove duplicated checkpoint logic
    4. Use shared VTT processing utilities
    5. Keep only unique logic in each executor
  - Validation: No duplicated code between executors

## Phase 6: Logging System Unification

### Objective
Consolidate two logging systems into one.

### Tasks

- [x] **Task 6.1: Compare logging implementations**
  - Purpose: Understand differences and choose best approach
  - Steps:
    1. Use context7 MCP tool for logging documentation
    2. Review `/src/utils/log_utils.py`
    3. Review `/src/utils/logging_enhanced.py`
    4. Identify unique features in each
    5. Determine which patterns to keep
  - Validation: Clear decision on logging approach

- [x] **Task 6.2: Create unified logging module**
  - Purpose: Single logging configuration for entire project
  - Steps:
    1. Create `/src/core/logging.py`
    2. Implement best features from both systems
    3. Provide simple configuration interface
    4. Ensure consistent log formatting
    5. Add environment-based log level control
  - Validation: Single logging module with all needed features

- [x] **Task 6.3: Update all logging imports**
  - Purpose: Use unified logging everywhere
  - Steps:
    1. Search for all logging imports
    2. Update to use new `/src/core/logging.py`
    3. Ensure log levels are consistent
    4. Test logging output
  - Validation: All logging uses new module

- [x] **Task 6.4: Remove old logging modules**
  - Purpose: Clean up duplicated code
  - Steps:
    1. Delete `/src/utils/log_utils.py`
    2. Delete `/src/utils/logging_enhanced.py`
    3. Verify logging still works throughout
  - Validation: Old files deleted, logging functional

## Phase 7: Resource Monitoring Centralization

### Objective
Consolidate four resource monitoring implementations into one.

### Tasks

- [x] **Task 7.1: Analyze resource monitoring code**
  - Purpose: Understand all monitoring requirements
  - Steps:
    1. Use context7 MCP tool for resource monitoring documentation
    2. Review all four resource monitoring modules
    3. List all monitored resources (CPU, memory, etc.)
    4. Identify duplicated detection logic
  - Validation: Complete inventory of resource monitoring

- [x] **Task 7.2: Create unified resource monitor**
  - Purpose: Single source for all resource information
  - Steps:
    1. Create `/src/monitoring/resources.py`
    2. Implement `ResourceMonitor` class
    3. Add methods for CPU, memory, disk monitoring
    4. Integrate with optional dependencies handler
    5. Add caching to prevent repeated system calls
  - Validation: All resource data available from one module

- [x] **Task 7.3: Update resource monitoring consumers**
  - Purpose: Use centralized monitoring
  - Steps:
    1. Find all resource monitoring imports
    2. Update to use new `/src/monitoring/resources.py`
    3. Remove duplicated monitoring code
    4. Test resource constraints still work
  - Validation: All monitoring uses new module

- [x] **Task 7.4: Remove old monitoring modules**
  - Purpose: Clean up duplicated code
  - Steps:
    1. Delete old resource detection modules
    2. Remove monitoring from optional dependencies
    3. Clean up `/src/core/monitoring.py` if redundant
  - Validation: No duplicated monitoring code remains

## Phase 8: Test Utilities Organization

### Objective
Move all test utilities to proper test directory.

### Tasks

- [x] **Task 8.1: Identify test utilities in source**
  - Purpose: Find all test-only code in source tree
  - Steps:
    1. Use context7 MCP tool for testing documentation
    2. Search for mock implementations in `/src`
    3. Identify test utilities outside `/tests`
    4. List all test-only functionality
  - Validation: Complete list of misplaced test code

- [x] **Task 8.2: Consolidate test utilities**
  - Purpose: Organize all test code properly
  - Steps:
    1. Create `/tests/fixtures/` directory
    2. Move all mocks to `/tests/fixtures/mocks.py`
    3. Create `/tests/fixtures/data.py` for test data
    4. Update mock implementations for consistency
    5. Remove test code from source directories
  - Validation: All test code in `/tests` directory

- [x] **Task 8.3: Update test imports**
  - Purpose: Use relocated test utilities
  - Steps:
    1. Find all imports of test utilities
    2. Update imports to use `/tests/fixtures/`
    3. Run all tests to ensure they still work
    4. Fix any broken test imports
  - Validation: All tests pass with new structure

## Phase 9: Final Cleanup and Validation

### Objective
Ensure all duplication is removed and system works correctly.

### Tasks

- [x] **Task 9.1: Remove common utility duplication**
  - Purpose: Consolidate repeated utility functions
  - Steps:
    1. Search for duplicate functions like `clean_text`, `extract_timestamp`
    2. Create `/src/utils/common.py` for shared utilities
    3. Update all references to use common utilities
    4. Remove duplicated implementations
  - Validation: No duplicated utility functions

- [x] **Task 9.2: Run comprehensive testing**
  - Purpose: Ensure refactoring didn't break functionality
  - Steps:
    1. Run full test suite
    2. Test each major component manually
    3. Verify metrics collection works
    4. Test with missing optional dependencies
    5. Check resource monitoring under load
  - Validation: All tests pass, functionality preserved

- [x] **Task 9.3: Update documentation**
  - Purpose: Reflect new simplified structure
  - Steps:
    1. Update README with new module structure
    2. Document new import paths
    3. Create module documentation for new organization
    4. Update any setup instructions
  - Validation: Documentation matches new structure

- [x] **Task 9.4: Final code review**
  - Purpose: Ensure no duplication remains
  - Steps:
    1. Use grep/search to find any remaining duplication
    2. Review new module organization
    3. Check for consistent naming conventions
    4. Verify all TODOs are addressed
    5. Run linting and type checking
  - Validation: Clean, deduplicated codebase

## Success Criteria

1. **Code Reduction**: Codebase reduced by 15-20% through deduplication
2. **Single Responsibility**: Each functionality has exactly one implementation
3. **Clean Organization**: Logical module structure with clear purposes
4. **No Feature Loss**: All existing functionality preserved
5. **Improved Maintainability**: Easier to update and extend
6. **Test Coverage**: All refactored code has working tests
7. **No External Dependencies**: No new frameworks or technologies introduced

## Technology Requirements

This plan uses NO new technologies, frameworks, or external dependencies. All refactoring is accomplished through:
- Python standard library features
- Existing project dependencies
- Better code organization
- Inheritance and composition patterns

## Risk Mitigation

1. **Incremental Refactoring**: Each phase can be completed independently
2. **Test First**: Ensure tests exist before refactoring
3. **Version Control**: Commit after each successful phase
4. **Validation Steps**: Each task includes verification
5. **No Big Bang**: Gradual migration prevents total failure

## Estimated Timeline

- Phase 1-2: Core infrastructure (metrics, dependencies) - High priority
- Phase 3-5: Service consolidation - Medium priority  
- Phase 6-8: Utilities cleanup - Lower priority
- Phase 9: Final validation

Each phase is independent and can be paused if issues arise.