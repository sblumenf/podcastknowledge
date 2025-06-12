# VTT Pipeline Test Restoration Plan

## Executive Summary

This plan will restore the VTT processing pipeline to a functional state by cleaning up disk space, fixing critical tests that validate core VTT functionality, and retiring outdated tests. The end result will be a streamlined test suite that ensures the pipeline can reliably process real VTT files while maintaining best practices and efficient disk usage.

## Phase 1: Disk Space Cleanup and Assessment

### Task 1.1: Clean Temporary Files and Directories
- [ ] Task: Remove all temporary test artifacts and cache files
- Purpose: Free up disk space before starting test restoration
- Steps:
  1. Use context7 MCP tool to review TESTING_CHECKLIST.md for cleanup guidelines
  2. Run `find /tmp -name "*pytest*" -type f -mtime +1 -delete` to remove old pytest temp files
  3. Run `find . -name "__pycache__" -type d -exec rm -rf {} +` to remove Python cache
  4. Run `find . -name "*.pyc" -delete` to remove compiled Python files
  5. Run `find . -name ".pytest_cache" -type d -exec rm -rf {} +` to remove pytest cache
  6. Check and clean `test_checkpoints/`, `test_output/`, `htmlcov/` directories
  7. Remove any `.coverage` files older than 1 day
- Validation: Run `du -sh .` before and after to verify space freed

### Task 1.2: Analyze Test Distribution and Dependencies
- [ ] Task: Create a comprehensive map of test categories and their dependencies
- Purpose: Understand which tests are essential for VTT processing
- Steps:
  1. Use context7 MCP tool to review existing test documentation
  2. Run `grep -r "def test_" tests/ | grep -E "(vtt|VTT)" | wc -l` to count VTT-specific tests
  3. Create a mapping file: `tests/test_inventory.json` with categories:
     - Core VTT tests (parsing, segmentation, extraction)
     - Integration tests that use VTT
     - Unit tests for VTT components
     - Tests unrelated to VTT (candidates for removal)
  4. Identify test files with >50% failure rate from previous runs
- Validation: Verify test_inventory.json contains all 1585 tests categorized

### Task 1.3: Identify and Archive Obsolete Tests
- [ ] Task: Move outdated tests to an archive directory
- Purpose: Reduce test suite size while preserving code history
- Steps:
  1. Create `tests/archived_obsolete/` directory
  2. Move tests that reference non-existent APIs:
     - Tests calling `process_podcast()` method
     - Tests importing `feed_processing` module
     - Tests using old checkpoint APIs (`save_progress`, `get_progress`)
  3. Add `tests/archived_obsolete/README.md` explaining why tests were archived
  4. Update `.gitignore` to exclude archived tests from coverage
- Validation: Run `pytest --collect-only` and verify count reduced by at least 20%

## Phase 2: Fix Core VTT Processing Tests

### Task 2.1: Restore VTT Parser Tests
- [ ] Task: Fix all tests in `tests/processing/test_vtt_parser.py`
- Purpose: Ensure VTT parsing works correctly
- Steps:
  1. Use context7 MCP tool to review VTT parser documentation
  2. Update test imports to match current module structure
  3. Fix method signatures to match `VTTParser` class API
  4. Update assertion patterns for current return types
  5. Add proper mocking for file I/O operations
  6. Run `pytest tests/processing/test_vtt_parser.py -v`
- Validation: All VTT parser tests pass with 0 failures

### Task 2.2: Fix VTT Segmentation Tests
- [ ] Task: Restore tests in `tests/processing/test_vtt_segmentation.py`
- Purpose: Validate segment creation and time alignment
- Steps:
  1. Use context7 MCP tool for segmentation requirements
  2. Update `VTTTranscriptSegmenter` test instantiation
  3. Fix segment model assertions to match current `Segment` class
  4. Add edge case tests for malformed VTT files
  5. Ensure time overlap handling is tested
- Validation: Segmentation tests pass and cover >80% of module

### Task 2.3: Restore VTT Knowledge Extraction Tests
- [ ] Task: Fix `tests/processing/test_vtt_extraction.py`
- Purpose: Ensure knowledge extraction from VTT segments works
- Steps:
  1. Use context7 MCP tool to understand extraction pipeline
  2. Update `KnowledgeExtractor` mock setup
  3. Fix LLM service mocking to use current interface
  4. Update extraction result assertions
  5. Add timeout handling for extraction tests
- Validation: Extraction tests complete within 30s with all passing

### Task 2.4: Fix Critical E2E VTT Pipeline Tests
- [ ] Task: Restore minimal E2E tests that validate full pipeline
- Purpose: Ensure complete VTT processing flow works
- Steps:
  1. Use context7 MCP tool for E2E test patterns
  2. Simplify Neo4j mocking using in-memory structures
  3. Create `MockGraphStorage` class that doesn't require Neo4j
  4. Update `test_vtt_pipeline_e2e.py` to use mock storage
  5. Add real VTT file processing test with sample data
- Validation: Can process a sample VTT file end-to-end without Neo4j

## Phase 3: Streamline Test Infrastructure

### Task 3.1: Implement Efficient Test Fixtures
- [ ] Task: Create reusable fixtures for VTT testing
- Purpose: Reduce code duplication and improve test speed
- Steps:
  1. Use context7 MCP tool for pytest best practices
  2. Create `tests/fixtures/vtt_fixtures.py` with:
     - Sample VTT content generators
     - Mock LLM response builders
     - Lightweight storage mocks
  3. Update conftest.py to auto-use efficient mocks
  4. Remove redundant mock setups from individual tests
- Validation: Test setup time reduced by >50%

### Task 3.2: Optimize Test Execution
- [ ] Task: Configure pytest for efficient execution
- Purpose: Prevent timeouts and improve feedback loop
- Steps:
  1. Update `pyproject.toml` with optimized pytest settings:
     - Set `timeout = 10` for unit tests
     - Add markers for slow tests
     - Configure parallel execution with `-n auto`
  2. Create `tests/pytest.ini` with category-specific timeouts
  3. Add `@pytest.mark.vtt` marker to all VTT tests
  4. Setup test execution groups in CI
- Validation: Full test suite runs in <2 minutes

### Task 3.3: Implement Test Selection Strategy
- [ ] Task: Create test profiles for different scenarios
- Purpose: Run only relevant tests during development
- Steps:
  1. Create `scripts/run_vtt_tests.py` for VTT-only testing
  2. Add test categories to markers:
     - `@pytest.mark.vtt_core` (must pass)
     - `@pytest.mark.vtt_integration` (should pass)
     - `@pytest.mark.vtt_optional` (nice to have)
  3. Create make/script targets for each profile
  4. Document test running strategies in README
- Validation: Can run core VTT tests in <30 seconds

## Phase 4: Address Remaining Test Issues

### Task 4.1: Fix or Skip Remaining Integration Tests
- [ ] Task: Triage remaining integration test failures
- Purpose: Achieve stable test suite
- Steps:
  1. Use context7 MCP tool for integration test patterns
  2. For each failing integration test:
     - Attempt quick fix if <10 minutes
     - Otherwise mark with `@pytest.mark.skip(reason="...")`
  3. Document skipped tests in `tests/SKIPPED_TESTS.md`
  4. Create GitHub issues for complex fixes
- Validation: No unexpected test failures in CI

### Task 4.2: Update Test Dependencies
- [ ] Task: Modernize test dependencies
- Purpose: Use latest testing best practices
- Steps:
  1. Update `requirements-dev.txt`:
     - pytest>=7.4.0
     - pytest-asyncio>=0.21.0
     - pytest-timeout>=2.2.0
     - pytest-xdist>=3.5.0
  2. Remove unused test dependencies
  3. Add `pytest-benchmark` for performance tests
  4. Update mock libraries to latest versions
- Validation: All dependencies install without conflicts

### Task 4.3: Implement Continuous Test Health Monitoring
- [ ] Task: Set up test health tracking
- Purpose: Prevent test suite degradation
- Steps:
  1. Create `tests/test_health_report.py` script
  2. Generate weekly test reports showing:
     - Pass/fail rates by category
     - Slowest tests
     - Flaky test detection
  3. Add pre-commit hook for test validation
  4. Set up test coverage requirements
- Validation: Test health report generates successfully

## Phase 5: Validation and Documentation

### Task 5.1: Validate Real VTT Processing
- [ ] Task: Test with real-world VTT files
- Purpose: Ensure pipeline works for actual use cases
- Steps:
  1. Use context7 MCP tool for VTT processing examples
  2. Create `tests/fixtures/real_vtt_samples/` directory
  3. Add 3-5 real VTT files of varying complexity
  4. Create `tests/integration/test_real_vtt_processing.py`
  5. Run full pipeline on each sample
  6. Verify output quality and performance
- Validation: All real VTT samples process successfully

### Task 5.2: Document Test Strategy
- [ ] Task: Create comprehensive test documentation
- Purpose: Maintain test suite quality
- Steps:
  1. Create `tests/TEST_STRATEGY.md` covering:
     - Test organization principles
     - When to write new tests
     - Mocking strategies
     - Performance considerations
  2. Update main README with test running instructions
  3. Document marker meanings and usage
  4. Add troubleshooting guide for common issues
- Validation: New developer can run tests following docs

### Task 5.3: Create Test Maintenance Checklist
- [ ] Task: Establish ongoing test maintenance process
- Purpose: Prevent future test degradation
- Steps:
  1. Create `tests/MAINTENANCE_CHECKLIST.md`
  2. Include weekly tasks:
     - Run full test suite
     - Check for new slow tests
     - Review skipped test count
     - Update test fixtures
  3. Add to PR template
  4. Set up automated alerts for test failures
- Validation: Checklist integrated into workflow

## Success Criteria

1. **Functional VTT Processing**: Can process real VTT files without errors
2. **Test Suite Health**: 
   - Core VTT tests: 100% pass rate
   - Overall test suite: >80% pass rate
   - No tests timing out
   - Execution time <2 minutes
3. **Disk Space**: Test artifacts use <100MB total
4. **Maintainability**: Clear documentation and automated health checks
5. **Performance**: VTT processing tests complete in <30 seconds

## Technology Requirements

### Updates Needed (Require Approval):
- [ ] pytest-benchmark (new) - for performance testing
- [ ] pytest-mock>=3.12.0 (update) - better mock capabilities
- [ ] Remove neo4j from test dependencies (use mocks instead)

### No New Technologies Required:
- Uses existing pytest ecosystem
- Leverages current mocking patterns
- No new databases or services

## Risk Mitigation

1. **Risk**: Breaking existing functionality
   - Mitigation: Archive rather than delete tests, maintain git history

2. **Risk**: Missing critical test coverage
   - Mitigation: Focus on VTT core functionality first

3. **Risk**: Test maintenance burden
   - Mitigation: Automated health monitoring and clear documentation

## Estimated Timeline

- Phase 1: 2-3 hours (cleanup and assessment)
- Phase 2: 4-6 hours (fix core VTT tests)
- Phase 3: 3-4 hours (streamline infrastructure)
- Phase 4: 2-3 hours (address remaining issues)
- Phase 5: 2-3 hours (validation and documentation)

Total: 13-19 hours of focused work