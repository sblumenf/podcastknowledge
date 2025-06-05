# Fix TranscriptionOrchestrator Configuration Plan

## Executive Summary

This plan will modify the TranscriptionOrchestrator to accept an optional config parameter, allowing tests to inject mock configurations while maintaining clean production usage. All existing tests will be updated to pass, following best practices for dependency injection and testability.

## Phase 1: Analyze Current Implementation

### Task 1.1: Document Current State
- [x] Document current TranscriptionOrchestrator initialization
  - Purpose: Understand the existing implementation before making changes
  - Steps:
    1. Use context7 MCP tool to check for any orchestrator documentation
    2. Read src/orchestrator.py focusing on __init__ method
    3. Identify all places where self.config is used
    4. Document which config values are accessed
  - Validation: List of all config dependencies documented

### Task 1.2: Inventory Test Usage
- [x] Find all tests using TranscriptionOrchestrator
  - Purpose: Know the full scope of changes needed
  - Steps:
    1. Use grep to find "TranscriptionOrchestrator" in tests/
    2. For each test file found, identify how it instantiates the orchestrator
    3. Note which tests pass config parameter
    4. Note which tests use the current parameter pattern
  - Validation: Complete list of test files and their instantiation patterns

### Task 1.3: Analyze Config Class
- [x] Understand Config class structure
  - Purpose: Design the best way to make it injectable
  - Steps:
    1. Use context7 MCP tool for Config documentation
    2. Read src/config.py to understand Config class
    3. Identify if Config can be easily mocked
    4. Check if Config has any side effects in __init__
  - Validation: Clear understanding of Config class capabilities

## Phase 2: Design Solution

### Task 2.1: Design Config Injection Pattern
- [x] Create design for optional config parameter
  - Purpose: Enable dependency injection while maintaining backward compatibility
  - Steps:
    1. Design __init__ signature with optional config: Optional[Config] = None
    2. Plan logic for: if config is None: config = Config()
    3. Consider if any other initialization needs adjustment
    4. Document the new initialization flow
  - Validation: Clear design documented with example usage

### Task 2.2: Design Test Helper Pattern
- [x] Create pattern for test configuration
  - Purpose: Simplify test setup and reduce boilerplate
  - Steps:
    1. Design a test fixture or helper for creating test configs
    2. Plan how to override specific config values for tests
    3. Consider using a builder pattern or factory for test configs
    4. Document the test helper pattern
  - Validation: Test helper design that reduces duplication

## Phase 3: Implement Core Changes

### Task 3.1: Modify TranscriptionOrchestrator
- [x] Update __init__ to accept optional config
  - Purpose: Allow dependency injection for testing
  - Steps:
    1. Use context7 MCP tool to check for any relevant patterns
    2. Open src/orchestrator.py
    3. Add config: Optional[Config] = None to __init__ parameters
    4. Add logic: self.config = config if config is not None else Config()
    5. Ensure all existing parameters still work
    6. Run type checking to ensure no type errors
  - Validation: Orchestrator can be instantiated with or without config

### Task 3.2: Create Test Configuration Builder
- [x] Implement test helper for configurations
  - Purpose: Simplify test configuration setup
  - Steps:
    1. Create tests/fixtures/config_builder.py if not exists
    2. Implement a TestConfigBuilder class or factory function
    3. Add methods to override common test values (paths, limits, etc.)
    4. Add documentation for test authors
  - Validation: Test helper can create configs with custom values

## Phase 4: Update Failing Tests

### Task 4.1: Fix test_e2e_comprehensive.py
- [x] Update all TranscriptionOrchestrator instantiations
  - Purpose: Make e2e tests pass
  - Steps:
    1. Use context7 MCP tool for test documentation
    2. Open tests/test_e2e_comprehensive.py
    3. Find all TranscriptionOrchestrator(config=...) calls
    4. Update to pass config as parameter: TranscriptionOrchestrator(config=mock_config)
    5. Or remove config= and pass other params from config
    6. Run the specific test file to verify fixes
  - Validation: All tests in test_e2e_comprehensive.py pass

### Task 4.2: Fix test_performance_comprehensive.py
- [x] Update performance test instantiations
  - Purpose: Ensure performance tests work correctly
  - Steps:
    1. Open tests/test_performance_comprehensive.py
    2. Find all TranscriptionOrchestrator instantiations
    3. Apply same pattern as in e2e tests
    4. Ensure performance test configs are appropriate
    5. Run the specific test file to verify
  - Validation: All tests in test_performance_comprehensive.py pass

### Task 4.3: Update Other Affected Tests
- [x] Find and fix any other tests using old pattern
  - Purpose: Ensure all tests pass
  - Steps:
    1. Use grep to find any remaining config= usage
    2. Check each test file for TranscriptionOrchestrator usage
    3. Update instantiation patterns as needed
    4. Consider if tests need the new test helper
  - Validation: No remaining config= usage in tests

## Phase 5: Comprehensive Testing

### Task 5.1: Run Full Test Suite
- [x] Execute all tests to ensure nothing broken
  - Purpose: Verify all changes work correctly
  - Steps:
    1. Use context7 MCP tool for test running documentation
    2. Run: pytest -v --tb=short
    3. Document any failures
    4. Fix any unexpected failures
    5. Re-run until all pass
  - Validation: All tests pass (or only expected failures)

### Task 5.2: Run Coverage Report
- [x] Generate coverage report
  - Purpose: Ensure test coverage maintained
  - Steps:
    1. Run: pytest --cov=src --cov-report=term-missing
    2. Document coverage percentage
    3. Identify any coverage regressions
    4. Note areas needing more tests
  - Validation: Coverage report generated and documented

### Task 5.3: Run Type Checking
- [x] Verify type safety
  - Purpose: Ensure no type errors introduced
  - Steps:
    1. Run: mypy src/ if configured
    2. Or run any configured type checking
    3. Fix any type errors found
    4. Document type checking results
  - Validation: No type errors in modified code

## Phase 6: Documentation and Cleanup

### Task 6.1: Update Code Documentation
- [ ] Add/update docstrings for changes
  - Purpose: Maintain code documentation quality
  - Steps:
    1. Update TranscriptionOrchestrator.__init__ docstring
    2. Document the config parameter usage
    3. Add examples if helpful
    4. Update any relevant class documentation
  - Validation: Clear documentation for config injection

### Task 6.2: Update Test Documentation
- [ ] Document test patterns
  - Purpose: Help future test authors
  - Steps:
    1. Add comments to test files explaining config usage
    2. Document test helper usage if created
    3. Consider adding a tests/README.md if not exists
    4. Document any test best practices discovered
  - Validation: Test patterns clearly documented

### Task 6.3: Clean Up and Verify
- [ ] Final verification and cleanup
  - Purpose: Ensure production-ready code
  - Steps:
    1. Remove any debug print statements
    2. Remove any TODO comments addressed
    3. Run linting: make lint or configured linter
    4. Run final test suite one more time
    5. Create summary of changes made
  - Validation: Clean, tested, production-ready code

## Success Criteria

1. All tests pass without errors
2. TranscriptionOrchestrator accepts optional config parameter
3. Production usage (without config) still works correctly
4. Test code is cleaner and more maintainable
5. No regression in functionality or test coverage
6. Code follows project conventions and best practices

## Technology Requirements

No new technologies required. This plan uses only existing frameworks and libraries already in the project.

## Risk Mitigation

1. **Risk**: Breaking existing functionality
   - **Mitigation**: Optional parameter maintains backward compatibility
   
2. **Risk**: Missing test updates
   - **Mitigation**: Comprehensive grep search for all usage patterns
   
3. **Risk**: Type safety issues
   - **Mitigation**: Run type checking after changes

## Notes

- All file modifications should preserve existing code style
- Use context7 MCP tool for documentation checks before each phase
- Run tests incrementally to catch issues early
- Consider creating a feature branch for these changes