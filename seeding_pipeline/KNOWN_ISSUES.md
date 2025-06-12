# Known Issues

This document tracks issues that are known but not yet fixed, providing transparency about current limitations and workarounds.

**Last Updated**: 2025-05-31  
**Phase**: 6 - Test Failure Resolution  
**Next Review**: 2025-08-31  

## How to Use This Document

- **Current Issues**: Problems affecting functionality today
- **Workarounds**: Temporary solutions to maintain productivity
- **Fix Status**: Whether a fix is planned and timeline
- **Severity**: Impact level on system functionality

## Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| 🚨 **Critical** | Blocks all E2E functionality | Fix immediately |
| 🔴 **High** | Blocks major functionality | Fix within 1 week |
| 🟡 **Medium** | Impacts some functionality | Fix within 1 month |
| 🟢 **Low** | Minor issues, workarounds available | Fix when convenient |

---

## Test Suite Issues

### Test Environment Dependencies

**Issue**: Some tests require specific environment setup that may not be available in all environments  
**Severity**: 🟡 Medium  
**Impact**: Tests may fail in clean environments or CI without proper setup  
**Workaround**: Use the `TESTING_CHECKLIST.md` to verify environment before running tests  
**Fix Planned**: Yes - Add automatic environment validation to test runner  
**Timeline**: Phase 7  

**Files Affected**: 
- All integration and E2E tests
- Tests requiring Neo4j database
- Tests requiring specific Python packages

---

## Pipeline Issues

### VTT Processing Memory Usage

**Issue**: Large VTT files (>1000 captions) may consume significant memory during processing  
**Severity**: 🟡 Medium  
**Impact**: Potential memory issues with very large podcast episodes  
**Workaround**: Process files in smaller batches or increase system memory  
**Fix Planned**: Future - Implement streaming VTT processing  
**Timeline**: Not scheduled  

**Files Affected**:
- `src/vtt/vtt_parser.py`
- `src/processing/segmentation.py`

---

## Infrastructure Issues

### Neo4j Connection Handling

**Issue**: Neo4j connection failures are not always handled gracefully in tests  
**Severity**: 🔴 High  
**Impact**: Tests may hang or fail unexpectedly when Neo4j is unavailable  
**Workaround**: Ensure Neo4j is running before executing tests, use connection retry logic  
**Fix Planned**: Yes - Improve connection error handling and timeouts  
**Timeline**: Phase 7  

**Files Affected**:
- `tests/conftest.py`
- All E2E and integration tests
- `src/storage/graph_storage.py`

---

## Documentation Issues

### API Documentation Completeness

**Issue**: Some API endpoints lack comprehensive documentation  
**Severity**: 🟢 Low  
**Impact**: Developers may need to read source code to understand API usage  
**Workaround**: Refer to source code and existing examples  
**Fix Planned**: Yes - Complete API documentation  
**Timeline**: As time permits  

**Files Affected**:
- `docs/api/` directory
- OpenAPI specifications

---

## CI/CD Considerations

### Allowed Test Failures

The following test scenarios are known to fail under specific conditions and are temporarily allowed to fail in CI:

#### Environment-Specific Tests
- Tests that require specific OS features (development only)
- Tests that depend on external services (when services are unavailable)

#### Performance Tests
- Performance benchmarks may fail on resource-constrained CI runners
- Timeout-sensitive tests may fail under high system load

### CI Configuration

To allow certain failures in CI, the following approach is used:

```yaml
# In .github/workflows/ci.yml
- name: Run tests with known issue tolerance
  run: |
    pytest -v --tb=short || echo "Some tests failed - checking against known issues"
    # Add specific known issue checking here
```

---

## Workaround Procedures

### Database Connection Issues

If you encounter Neo4j connection failures:

1. **Check Service Status**:
   ```bash
   # For Docker
   docker ps | grep neo4j
   
   # For local installation
   systemctl status neo4j  # Linux
   brew services list | grep neo4j  # macOS
   ```

2. **Restart Service**:
   ```bash
   # Docker
   docker restart <neo4j-container-id>
   
   # Local installation
   systemctl restart neo4j  # Linux
   brew services restart neo4j  # macOS
   ```

3. **Verify Connection**:
   ```bash
   python test_neo4j_connection.py
   ```

### Test Environment Issues

If tests fail due to environment setup:

1. **Run Environment Check**:
   ```bash
   ./scripts/run_smoke_tests.py
   ```

2. **Follow Setup Checklist**:
   - Review `TESTING_CHECKLIST.md`
   - Verify all prerequisites are met
   - Check `.env` file configuration

3. **Reset Environment**:
   ```bash
   # Recreate virtual environment
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements-dev.txt
   ```

### Memory Issues with Large Files

If processing large VTT files causes memory issues:

1. **Monitor Memory Usage**:
   ```bash
   # Linux/macOS
   top -p $(pgrep -f python)
   ```

2. **Process in Batches**:
   - Split large VTT files into smaller segments
   - Process episodes separately rather than in bulk

3. **Increase Memory Limits**:
   - Adjust Docker memory limits if using containers
   - Close other applications to free system memory

---

## Reporting New Issues

When you discover a new issue:

1. **Check Existing Issues**: Review this document and failure tracking system
2. **Create Failure Record**: Use `./scripts/manage_failures.py record`
3. **Document Workaround**: If you find a workaround, document it
4. **Update This Document**: Add to appropriate section with proper severity
5. **Notify Team**: Communicate critical and high-severity issues immediately

## Review Schedule

This document is reviewed and updated:

- **Monthly**: During sprint planning
- **Quarterly**: Comprehensive review of all issues
- **After Major Changes**: When significant system changes are made
- **Before Releases**: Ensure all known issues are documented

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-05-31 | 1.0 | Initial document creation |

---

## Related Documents

- [Test Failure Tracking](test_tracking/failure_handling_process.md)
- [Testing Checklist](TESTING_CHECKLIST.md)
- [CI/CD Workflow](docs/ci-workflow.md)
- [Troubleshooting Guide](docs/guides/troubleshooting.rst)