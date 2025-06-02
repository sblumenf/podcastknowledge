# Fix Failing Tests Implementation Plan

## Executive Summary

This plan will systematically fix all 742 failing tests in the podcast knowledge seeding pipeline by aligning the codebase and tests to work together. The goal is to achieve a fully functional system with 100% test pass rate, properly implementing schemaless knowledge graph extraction from VTT transcripts.

## Technology Requirements

**No new technologies will be introduced** - this plan uses only existing dependencies and frameworks already in the project.

## Phase 1: Test Collection and Import Fixes (35 collection errors)

### Task 1.1: Analyze and Document Import Errors
- [x] Create comprehensive import error inventory
  - Purpose: Understand all missing imports to fix them systematically
  - Steps:
    1. Use context7 MCP tool to review documentation for expected imports
    2. Run `pytest --collect-only -q 2>&1 | grep "ImportError" > import_errors.txt`
    3. Parse import_errors.txt to extract:
       - Test file path
       - Missing import name
       - Expected module path
    4. Create JSON mapping of missing imports
  - Validation: JSON file exists with all 35 import errors documented

### Task 1.2: Fix CLI Module Imports
- [x] Resolve missing CLI functions
  - Purpose: Enable CLI tests to import successfully
  - Steps:
    1. Use context7 MCP tool to check CLI documentation
    2. Read `src/cli/cli.py` to understand current structure
    3. Read `tests/test_cli.py` to see expected functions
    4. Either:
       - Add missing functions to `src/cli/cli.py`: `load_podcast_configs`, `seed_podcasts`, `health_check`, `validate_config`, `schema_stats`
       - OR update tests to use existing CLI interface
    5. Verify imports work: `python -c "from src.cli.cli import main"`
  - Validation: `pytest tests/test_cli.py --collect-only` succeeds

### Task 1.3: Fix API Module Imports
- [x] Resolve missing API classes and functions
  - Purpose: Enable API tests to import successfully
  - Steps:
    1. Use context7 MCP tool to review API documentation
    2. Read `src/api/health.py` and check for `ComponentHealth`
    3. Read `src/api/v1/__init__.py` and check for `VTTKnowledgeExtractor`
    4. Read test files to understand expected API
    5. Implement missing classes or update tests
  - Validation: `pytest tests/api/ --collect-only` succeeds

### Task 1.4: Fix Remaining Import Errors
- [x] Resolve all other import issues
  - Purpose: Ensure all tests can be collected
  - Steps:
    1. Use context7 MCP tool for any relevant documentation
    2. For each remaining import error from Task 1.1:
       - Locate the test file
       - Identify missing import
       - Find or create the missing component
       - Update import statements
    3. Run full collection test
  - Validation: `pytest --collect-only` shows 742 collected items, 0 errors

## Phase 2: Model and Data Structure Alignment

### Task 2.1: Audit Model Definitions
- [x] Document all model mismatches
  - Purpose: Understand divergence between tests and implementation
  - Steps:
    1. Use context7 MCP tool to review model documentation
    2. Read `src/core/models.py` to list all current models and fields
    3. Run `pytest tests/unit/test_models.py -v` and capture output
    4. Create comparison table:
       - Model name
       - Expected fields (from tests)
       - Actual fields (from code)
       - Missing fields
  - Validation: Comparison table saved as `model_audit.json`

### Task 2.2: Fix PipelineConfig Model
- [ ] Add missing configuration fields
  - Purpose: Align configuration with test expectations
  - Steps:
    1. Use context7 MCP tool for configuration documentation
    2. Read `src/core/config.py`
    3. Add missing field: `whisper_model_size` with default "large-v3"
    4. Update `__post_init__` if needed
    5. Update `from_file` method to handle new field
  - Validation: `pytest tests/unit/test_config.py::TestPipelineConfig -v` passes

### Task 2.3: Fix Speaker Model
- [ ] Add missing Speaker fields
  - Purpose: Enable speaker-related tests to pass
  - Steps:
    1. Use context7 MCP tool for any speaker model documentation
    2. Locate Speaker model in `src/core/models.py`
    3. Add missing field: `bio: Optional[str] = None`
    4. Update `to_dict` method to include bio field
  - Validation: `pytest tests/unit/test_models.py::TestSpeaker -v` passes

### Task 2.4: Fix Remaining Models
- [ ] Update all other models with missing fields
  - Purpose: Complete model alignment
  - Steps:
    1. Use context7 MCP tool for model documentation
    2. For each model in audit from Task 2.1:
       - Add missing fields with appropriate types
       - Update constructors
       - Update `to_dict` methods
       - Ensure JSON serialization works
  - Validation: `pytest tests/unit/test_models.py -v` all pass

## Phase 3: Feature Flag System Repair

### Task 3.1: Analyze Feature Flag Requirements
- [ ] Document expected feature flags
  - Purpose: Understand schemaless system requirements
  - Steps:
    1. Use context7 MCP tool for feature flag documentation
    2. Run `grep -r "ENABLE_SCHEMALESS_EXTRACTION" tests/` to find usage
    3. Run `grep -r "SCHEMALESS_MIGRATION_MODE" tests/` to find usage
    4. Read `src/core/feature_flags.py` to see current flags
    5. Document all expected flags and their purposes
  - Validation: Feature flag requirements documented

### Task 3.2: Implement Schemaless Feature Flags
- [ ] Add required feature flag enum members
  - Purpose: Support schemaless knowledge graph system
  - Steps:
    1. Use context7 MCP tool for schemaless extraction documentation
    2. Edit `src/core/feature_flags.py`
    3. Add to FeatureFlag enum:
       - `ENABLE_SCHEMALESS_EXTRACTION = "enable_schemaless_extraction"`
       - `SCHEMALESS_MIGRATION_MODE = "schemaless_migration_mode"`
    4. Set appropriate defaults in feature flag manager
  - Validation: `pytest tests/unit/test_feature_flags.py -v` passes

## Phase 4: Integration and E2E Test Fixes

### Task 4.1: Fix VTT Processing Tests
- [ ] Ensure VTT parser and processing work correctly
  - Purpose: Core functionality for transcript processing
  - Steps:
    1. Use context7 MCP tool for VTT processing documentation
    2. Review `src/vtt/vtt_parser.py` and `src/vtt/vtt_segmentation.py`
    3. Run `pytest tests/processing/test_vtt_parser.py -v`
    4. Fix any parsing logic issues
    5. Ensure VTT samples in `tests/fixtures/vtt_samples/` are valid
  - Validation: All VTT processing tests pass

### Task 4.2: Fix Extraction Pipeline Tests
- [ ] Align extraction logic with tests
  - Purpose: Ensure knowledge extraction works properly
  - Steps:
    1. Use context7 MCP tool for extraction documentation
    2. Review `src/extraction/extraction.py`
    3. Run `pytest tests/processing/test_extraction.py -v`
    4. Fix extraction logic to match test expectations
    5. Ensure schemaless extraction is properly implemented
  - Validation: Extraction tests pass

### Task 4.3: Fix E2E Scenarios
- [ ] Ensure complete pipeline works end-to-end
  - Purpose: Validate full system functionality
  - Steps:
    1. Use context7 MCP tool for E2E test documentation
    2. Run `pytest tests/e2e/ -v` 
    3. Fix any integration issues between components
    4. Ensure Neo4j connection mocking works properly
    5. Validate complete VTT-to-knowledge-graph flow
  - Validation: All E2E tests pass

## Phase 5: Final Validation and Cleanup

### Task 5.1: Run Full Test Suite
- [ ] Execute complete test validation
  - Purpose: Ensure all 742 tests pass
  - Steps:
    1. Use context7 MCP tool to review testing documentation
    2. Run `pytest -v --tb=short > test_results.txt`
    3. If any failures:
       - Categorize by type
       - Fix systematically
       - Re-run affected tests
    4. Generate coverage report: `pytest --cov=src --cov-report=html`
  - Validation: 742 tests collected, 742 passed, 0 failed

### Task 5.2: Update Test Documentation
- [ ] Document test fixes and patterns
  - Purpose: Maintain understanding of test structure
  - Steps:
    1. Use context7 MCP tool to check existing test documentation
    2. Create `docs/testing/test-fix-summary.md` documenting:
       - Major changes made
       - Patterns for future test writing
       - Schemaless system test approach
    3. Update `README.md` test section if needed
  - Validation: Documentation created and accurate

### Task 5.3: Verify Lint and Type Checking
- [ ] Ensure code quality standards are met
  - Purpose: Maintain code quality after fixes
  - Steps:
    1. Use context7 MCP tool for linting documentation
    2. Run linting: `ruff check src tests`
    3. Run type checking if configured
    4. Fix any quality issues introduced
    5. Verify all quality checks pass
  - Validation: All linting and type checks pass

## Success Criteria

1. **Test Coverage**: 
   - All 742 tests collected successfully (0 collection errors)
   - All 742 tests pass (0 failures)
   - Code coverage maintained or improved

2. **Functionality**:
   - VTT transcript processing works correctly
   - Schemaless knowledge extraction functional
   - Neo4j graph population works (or is properly mocked in tests)
   - API endpoints respond correctly

3. **Code Quality**:
   - No linting errors
   - Type checking passes (if configured)
   - Documentation updated
   - No regression in existing functionality

4. **Schemaless System**:
   - Feature flags properly control schemaless mode
   - Extraction works without fixed schema
   - Tests validate schemaless behavior

## Risk Mitigation

1. **Test Interdependencies**: Some tests may depend on others. Fix in phases to minimize cascade effects.
2. **Mock vs Real Services**: Ensure tests properly mock external services (Neo4j, LLMs) to avoid dependencies.
3. **Performance**: Monitor test execution time. Parallelize where possible.
4. **Regression**: After each phase, run full suite to catch any regressions early.

## Notes

- Each task explicitly references using context7 MCP tool for documentation review
- No new technologies or frameworks will be introduced
- Focus is on making existing code and tests work together
- Schemaless approach is the expected behavior for knowledge graph