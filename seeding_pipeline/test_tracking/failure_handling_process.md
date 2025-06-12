# Test Failure Handling Process

**Phase**: 6 - Test Failure Resolution  
**Version**: 1.0  
**Last Updated**: 2025-05-31  

## Overview

This document establishes a systematic approach to handling test failures in the VTT → Knowledge Graph pipeline. The process ensures that all failures are addressed methodically, tracked consistently, and resolved efficiently.

## Failure Handling Workflow

### 1. Failure Detection

**When**: Test failures are discovered during:
- Automated CI/CD runs
- Local development testing
- Manual test execution
- Production monitoring

**Actions**:
1. **Immediate Assessment**: Determine if failure blocks critical functionality
2. **Initial Classification**: Assign preliminary error type and severity
3. **Record Failure**: Create failure record using tracking system

### 2. Failure Recording

**Tool**: Use `test_tracking/track_failure.py`

**Required Information**:
- Test name (exact test function/method name)
- Error message (from test output)
- Error type (connection, import, assertion, etc.)
- Severity level (critical, high, medium, low)
- Test category (unit, integration, e2e, etc.)
- Environment context

**Example**:
```python
from test_tracking.track_failure import FailureTracker

tracker = FailureTracker()
failure_id = tracker.record_failure(
    test_name="test_vtt_file_processing",
    error_message="ConnectionError: Neo4j unavailable",
    error_type="connection",
    severity="high",
    test_category="e2e"
)
```

### 3. Failure Triage

**Timeline**: Within 4 hours for critical, 24 hours for others

**Process**:
1. **Severity Verification**: Confirm initial severity assessment
2. **Impact Analysis**: Determine what functionality is blocked
3. **Resource Assignment**: Assign to appropriate team member
4. **Priority Setting**: Set resolution timeline based on severity

**Severity Guidelines**:
- **Critical**: Blocks all E2E functionality, prevents basic testing
- **High**: Blocks major functionality, impacts multiple test categories  
- **Medium**: Impacts specific functionality, workarounds available
- **Low**: Minor issues, cosmetic problems, edge cases

### 4. Investigation Phase

**Goal**: Identify root cause and develop fix strategy

**Steps**:
1. **Isolate Failure**: Run failing test in isolation
2. **Reproduce Locally**: Confirm failure in local environment
3. **Gather Context**: Collect logs, stack traces, environment details
4. **Analyze Dependencies**: Check for related failures or changes
5. **Document Findings**: Update failure record with investigation results

**Tools**:
- Test runner: `./scripts/run_tests.py`
- Failure viewer: `./scripts/view_test_results.py`
- Logging: Check application and test logs
- Environment: Verify `.env` and configuration

### 5. Fix Development

**Process**:
1. **Create Minimal Reproduction**: Strip down to simplest failing case
2. **Develop Fix**: Implement solution based on root cause
3. **Record Fix Attempt**: Document what was tried

**Example**:
```python
tracker.update_fix_attempt(
    failure_id,
    "Started Neo4j service and updated connection string"
)
```

### 6. Fix Verification

**Verification Loop**: Must complete all steps before considering fixed

1. **Run Test in Isolation**: `./scripts/run_tests.py` with specific test
2. **Run Related Test Suite**: Execute full category (e.g., e2e tests)
3. **Run Full Test Suite**: Ensure no regressions introduced
4. **Verify in CI**: Push changes and confirm CI passes
5. **Update Documentation**: If needed, update test or setup docs

### 7. Resolution

**Mark as Resolved**: Only after verification loop completes successfully

```python
tracker.mark_resolved(
    failure_id,
    resolution="Neo4j service was not running. Added startup check to test prerequisites.",
    lessons_learned="Always verify service dependencies before running integration tests"
)
```

## Error Type Categories

### Connection Errors
- **Description**: Database connection, network, or service connectivity issues
- **Common Causes**: Neo4j not running, wrong credentials, network issues
- **First Actions**: Check service status, verify credentials, test connectivity

### Import Errors  
- **Description**: Module import errors, missing dependencies
- **Common Causes**: Missing packages, circular imports, PYTHONPATH issues
- **First Actions**: Check requirements.txt, verify imports, check Python path

### Assertion Errors
- **Description**: Test assertion failures, unexpected results
- **Common Causes**: Logic errors, data mismatch, timing issues  
- **First Actions**: Check test expectations, verify data setup, add debugging

### Timeout Errors
- **Description**: Test execution timeouts
- **Common Causes**: Slow operations, deadlocks, resource contention
- **First Actions**: Check performance, increase timeouts, optimize queries

### Configuration Errors
- **Description**: Environment or configuration-related failures
- **Common Causes**: Missing .env, wrong settings, path issues
- **First Actions**: Verify .env file, check paths, validate configuration

## Priority Matrix

| Severity | Response Time | Resolution Target | Actions |
|----------|---------------|-------------------|---------|
| Critical | Immediate | 4 hours | Drop everything, fix immediately |
| High | 4 hours | 1 day | High priority, fix within day |
| Medium | 24 hours | 1 week | Plan in next sprint |
| Low | 1 week | As convenient | Document workarounds |

## Escalation Process

### When to Escalate
- Critical failures not resolved within 4 hours
- High severity failures not progressing within 1 day
- Repeated failures of same test (3+ times)
- Failures affecting multiple test categories

### Escalation Actions
1. **Document Current State**: Update failure record with all attempts
2. **Request Help**: Reach out to team lead or subject matter expert
3. **Consider Workarounds**: Identify temporary solutions
4. **Update Timeline**: Revise resolution target if needed

## Documentation Requirements

### For Each Failure
- [ ] Failure recorded in tracking system
- [ ] Root cause identified and documented
- [ ] Fix attempts logged with outcomes
- [ ] Resolution method documented
- [ ] Lessons learned captured

### For Fix Verification
- [ ] Test passes in isolation
- [ ] Related test suite passes
- [ ] Full test suite passes
- [ ] CI pipeline passes
- [ ] No regressions introduced

## Tools and Scripts

### Failure Tracking
- **Record**: `test_tracking/track_failure.py`
- **View**: Python API or direct JSON file inspection
- **Report**: `FailureTracker.generate_summary_report()`

### Test Execution
- **Run Tests**: `./scripts/run_tests.py [category]`
- **View Results**: `./scripts/view_test_results.py`
- **Check Status**: `./scripts/run_tests.py --help`

### Environment Validation
- **Prerequisites**: Check `TESTING_CHECKLIST.md`
- **Services**: Verify Neo4j, Python environment
- **Configuration**: Validate `.env` and settings

## Metrics and Reporting

### Daily Metrics
- Active failure count
- Critical failure count  
- Resolution rate (failures resolved per day)
- Average resolution time by severity

### Weekly Reporting
- Failure trend analysis
- Most common error types
- Test reliability metrics
- Process improvement opportunities

## Process Improvement

### Regular Reviews
- **Weekly**: Review active failures and progress
- **Monthly**: Analyze failure patterns and trends
- **Quarterly**: Review and update process documentation

### Feedback Loop
- Track resolution effectiveness
- Identify process bottlenecks
- Update documentation based on lessons learned
- Refine error categories and priorities

## Best Practices

### Do's
- ✅ Record failures immediately when discovered
- ✅ Complete full verification loop before marking resolved
- ✅ Document lessons learned for future reference
- ✅ Update test documentation if fix reveals gaps
- ✅ Check for related failures when investigating

### Don'ts  
- ❌ Skip verification steps to save time
- ❌ Mark failures as resolved without testing
- ❌ Ignore low-severity failures indefinitely
- ❌ Fix without understanding root cause
- ❌ Forget to update tracking system

## Example Workflow

### Scenario: E2E Test Failure

1. **Detection**: CI build fails on E2E test
2. **Recording**: Create failure record with error details
3. **Triage**: Assign high severity, investigate within 4 hours
4. **Investigation**: Reproduce locally, identify Neo4j connection issue
5. **Fix**: Start Neo4j service, update test prerequisites
6. **Verification**: Run test isolation → category → full suite → CI
7. **Resolution**: Mark resolved with documentation
8. **Follow-up**: Update setup documentation to prevent recurrence

This systematic approach ensures no failures are lost, all are addressed appropriately, and the team learns from each resolution to improve overall test reliability.