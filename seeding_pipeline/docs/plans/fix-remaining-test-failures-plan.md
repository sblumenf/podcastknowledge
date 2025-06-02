# Fix Remaining Test Failures Plan

## Executive Summary

The fix-failing-tests-plan achieved 74% test pass rate (550/742), falling short of the 100% success criterion. This corrective plan addresses the remaining 192 test failures to achieve full test suite compliance.

## Current State
- **Tests passing**: 550/742 (74%)
- **Tests failing**: 192
- **Collection errors**: 18
- **Root causes**: Test bugs, unmocked infrastructure, missing dependencies

## Phase 1: Fix Test Bugs (Estimated: 100+ test fixes)

### Task 1.1: Fix Non-Existent Enum Values
- **Issue**: Tests use enum values that don't exist (e.g., `EntityType.TECHNOLOGY`, `InsightType.OBSERVATION`)
- **Fix**: Update tests to use valid enum values
- **Files to modify**:
  ```
  tests/processing/test_extraction.py
  tests/unit/test_models.py
  tests/integration/test_performance_benchmarks.py
  ```
- **Validation**: Tests pass with correct enum values

### Task 1.2: Fix Method Signature Mismatches
- **Issue**: Tests call methods with wrong parameters
- **Fix**: Align test method calls with actual implementations
- **Validation**: No TypeError or AttributeError in test runs

## Phase 2: Mock Infrastructure Dependencies (Estimated: 50+ test fixes)

### Task 2.1: Mock Neo4j for E2E Tests
- **Issue**: E2E tests require live Neo4j connection
- **Fix**: Create comprehensive Neo4j mocks
- **Implementation**:
  ```python
  @patch('neo4j.GraphDatabase.driver')
  def test_e2e_scenario(mock_driver):
      mock_session = MagicMock()
      mock_driver.return_value.session.return_value = mock_session
  ```
- **Validation**: E2E tests run without Neo4j

### Task 2.2: Mock External Services
- **Issue**: Tests depend on external services (LLMs, APIs)
- **Fix**: Create service mocks for all external dependencies
- **Validation**: Tests run in isolated environment

## Phase 3: Fix Missing Dependencies (Estimated: 20+ test fixes)

### Task 3.1: Handle Missing psutil Import
- **Issue**: psutil module required but not installed
- **Fix**: Either:
  - Mock psutil in tests
  - OR make psutil optional in code
- **Implementation**: Add try/except blocks around psutil imports
- **Validation**: Tests run without psutil installed

### Task 3.2: Fix Remaining Import Errors
- **Issue**: 18 collection errors remain
- **Fix**: Add missing imports or mock them
- **Validation**: `pytest --collect-only` shows 0 errors

## Phase 4: Standardize Test Patterns

### Task 4.1: Create Test Utilities
- [x] **Create**: `tests/utils/test_helpers.py`
- [x] **Include**:
  - Standard mocks for Neo4j, LLMs, external services
  - Valid enum value constants
  - Fixture factories
- [x] **Validation**: All tests use consistent patterns

### Task 4.2: Update Test Documentation
- [x] **Update**: Test documentation with correct patterns
- [x] **Include**: Examples of proper mocking and enum usage
- [x] **Validation**: New tests follow patterns

## Success Criteria
1. **All 742 tests pass** (0 failures)
2. **0 collection errors**
3. **Tests run without external dependencies**
4. **Consistent test patterns established**

## Implementation Priority
1. **High**: Fix enum value bugs (easiest, highest impact)
2. **High**: Mock Neo4j (unblocks E2E tests)
3. **Medium**: Fix import errors
4. **Low**: Standardize patterns (nice to have)

## Estimated Effort
- **Total failing tests**: 192
- **Estimated time**: 2-3 days
- **Complexity**: Medium (mostly mechanical fixes)