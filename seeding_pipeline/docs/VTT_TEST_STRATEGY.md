# VTT Pipeline Test Strategy

## Overview

This document outlines the testing strategy for the VTT knowledge extraction pipeline. Our goal is to maintain high code quality, ensure reliability, and enable confident deployment of the VTT processing system.

## Test Philosophy

1. **Focus on VTT Core Functionality**: Tests should prioritize VTT parsing, segmentation, and knowledge extraction
2. **Fast Feedback Loop**: Unit tests should run in <10 seconds, integration tests in <1 minute
3. **Realistic Test Data**: Use actual VTT file structures and edge cases from production
4. **Clear Failure Messages**: Tests should clearly indicate what went wrong and how to fix it

## Test Categories

### 1. Unit Tests (`pytest -m unit`)
- **Purpose**: Test individual components in isolation
- **Target Coverage**: >80% for VTT modules
- **Key Areas**:
  - VTT parser functions
  - Segment processing logic
  - Timestamp calculations
  - Text normalization

### 2. Integration Tests (`pytest -m integration`)
- **Purpose**: Test component interactions
- **Target Coverage**: >70% for integration points
- **Key Areas**:
  - VTT parser + segmenter integration
  - Segmenter + knowledge extractor integration
  - File I/O operations
  - Error handling flows

### 3. End-to-End Tests (`pytest -m e2e`)
- **Purpose**: Validate complete workflows
- **Target Coverage**: Critical path coverage
- **Key Areas**:
  - Full VTT file processing
  - Knowledge graph generation
  - Performance benchmarks
  - Resource usage

### 4. Performance Tests (`pytest -m performance`)
- **Purpose**: Ensure system meets performance requirements
- **Benchmarks**:
  - Parse 1-hour VTT in <2 seconds
  - Process 100 segments in <5 seconds
  - Memory usage <500MB for typical files

## Test Organization

```
tests/
├── unit/                      # Fast, isolated tests
│   ├── test_vtt_parser_unit.py
│   ├── test_vtt_segmentation_unit.py
│   └── test_extraction_unit.py
├── integration/               # Component interaction tests
│   ├── test_vtt_processing.py
│   ├── test_vtt_pipeline_integration.py
│   └── test_batch_processing_core.py
├── e2e/                      # Full workflow tests
│   ├── test_critical_path.py
│   └── test_vtt_pipeline_e2e.py
├── performance/              # Performance benchmarks
│   └── test_vtt_performance_benchmarks.py
└── fixtures/                 # Shared test data
    ├── vtt_fixtures.py
    └── vtt_samples/
```

## Testing Commands

### Quick Tests
```bash
# Run only VTT-specific tests
pytest -m vtt

# Run critical path tests
pytest -m critical

# Run with coverage
pytest --cov=src.vtt --cov-report=term-missing
```

### Optimized Test Execution
```bash
# Use the optimized test runner
python scripts/run_vtt_tests.py --mode all

# Run tests in parallel
pytest -n auto -m vtt

# Run with minimal dependencies
pip install -r requirements-test-vtt.txt
pytest tests/processing/test_vtt_parser.py
```

### Continuous Monitoring
```bash
# Monitor test health
python scripts/monitor_test_health.py

# Check for flaky tests
python scripts/monitor_test_health.py --detect-flaky

# View test dashboard
python scripts/test_health_dashboard.py
```

## Mock Strategies

### 1. LLM Service Mocking
```python
class MockLLM:
    def generate(self, *args, **kwargs):
        return {
            "entities": [...],
            "relationships": [...],
            "quotes": [...]
        }
```

### 2. Neo4j Mocking
- Use `@pytest.mark.skip` for complex Neo4j tests
- Mock simple operations with return values
- Consider using in-memory graph for integration tests

### 3. File System Mocking
- Use `tmp_path` fixture for temporary files
- Create test VTT files programmatically
- Clean up after tests automatically

## Test Data Management

### Sample VTT Files
- `minimal.vtt`: Basic 2-segment file for smoke tests
- `standard.vtt`: Typical podcast transcript
- `complex.vtt`: Edge cases (overlaps, special chars, multi-line)
- `large.vtt`: Performance testing (1000+ segments)

### Generated Test Data
```python
# Use faker for realistic text
faker.text(max_nb_chars=200)

# Generate timestamps
start_time = i * 10.0
end_time = start_time + 10.0
```

## Performance Optimization

### 1. Fixture Scope
```python
@pytest.fixture(scope="session")
def vtt_parser():
    """Shared parser instance for all tests."""
    return VTTParser()
```

### 2. Parallel Execution
```ini
# pytest.ini
[tool:pytest]
addopts = -n auto --dist loadscope
```

### 3. Test Selection
```bash
# Skip slow tests during development
pytest -m "not slow"

# Run only changed test files
pytest --testmon
```

## Continuous Integration

### GitHub Actions Workflow
- Run on every PR and push to main
- Matrix testing (Python 3.9, 3.10, 3.11)
- Upload coverage to Codecov
- Comment test results on PRs

### Pre-commit Hooks
```yaml
- repo: local
  hooks:
    - id: pytest-check
      name: pytest-check
      entry: pytest -m "critical"
      language: system
      pass_filenames: false
      always_run: true
```

## Test Maintenance

### Weekly Tasks
1. Run flaky test detection
2. Review test performance metrics
3. Update test fixtures with new edge cases

### Monthly Tasks
1. Review and update test coverage goals
2. Analyze test failure patterns
3. Refactor slow or complex tests

### Quarterly Tasks
1. Benchmark against production data
2. Update performance baselines
3. Review and update test strategy

## Known Issues and Workarounds

### 1. Entity Extraction API Mismatch
- **Issue**: Entity/Insight/Quote object interfaces changed
- **Workaround**: Tests marked with `@pytest.mark.skip`
- **TODO**: Refactor extraction tests when API stabilizes

### 2. Neo4j Test Complexity
- **Issue**: Complex mocking requirements for graph operations
- **Workaround**: Focus on unit tests for business logic
- **TODO**: Consider testcontainers for integration tests

### 3. Parallel Test Conflicts
- **Issue**: Some tests conflict when run in parallel
- **Workaround**: Use `--dist loadscope` to group by module
- **TODO**: Improve test isolation

## Success Metrics

1. **Test Coverage**: Maintain >80% coverage for VTT modules
2. **Test Speed**: All unit tests complete in <10 seconds
3. **Reliability**: <1% flaky test rate
4. **Clarity**: All test failures provide actionable error messages

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [VTT Specification](https://www.w3.org/TR/webvtt1/)
- [Test Best Practices](tests/README.md)
- [Contributing Guidelines](../CONTRIBUTING.md)