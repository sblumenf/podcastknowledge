# Test Coverage Maintenance Guide

## Overview

This guide provides procedures and best practices for maintaining the 85% test coverage requirement for the podcast transcriber project. It covers monitoring, improving, and sustaining test coverage over time while managing memory constraints.

## Coverage Requirements

### Module-Level Requirements
| Module Category | Target Coverage | Critical Modules |
|----------------|-----------------|------------------|
| Critical Path | ≥90% | orchestrator.py, transcription_processor.py, checkpoint_recovery.py |
| API Integration | ≥85% | gemini_client.py, retry_wrapper.py, key_rotation_manager.py |
| Data Management | ≥85% | metadata_index.py, state_management.py |
| Supporting | ≥80% | file_organizer.py, vtt_generator.py, progress_tracker.py |
| UI/CLI | ≥60% | cli.py |

### Overall Project Target
- **Minimum**: 85% overall coverage
- **Threshold**: Allow 2% temporary drop during active development
- **Recovery**: Must return to 85% within 2 pull requests

## Daily Maintenance Tasks

### 1. Monitor Coverage Status
```bash
# Check current coverage locally
pytest --cov=src --cov-report=term-missing

# Generate detailed HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Check specific module coverage
pytest --cov=src.orchestrator --cov-report=term-missing
```

### 2. Review CI/CD Reports
- Check GitHub Actions for coverage status
- Review codecov.io dashboard for trends
- Monitor coverage badges in README

### 3. Address Coverage Drops
```bash
# Identify uncovered lines
pytest --cov=src.module_name --cov-report=term-missing

# Run only failed tests to save memory
pytest --lf --cov=src

# Run tests for specific markers to isolate issues
pytest -m unit --cov=src
```

## Weekly Maintenance Tasks

### 1. Coverage Trend Analysis
```python
# Script to analyze coverage trends
import json
import pandas as pd
from datetime import datetime, timedelta

def analyze_coverage_trend():
    """Analyze weekly coverage trends."""
    with open('.coverage-history/coverage_history.json', 'r') as f:
        history = json.load(f)
    
    df = pd.DataFrame(history)
    df['date'] = pd.to_datetime(df['date'])
    
    # Get last week's data
    last_week = df[df['date'] > datetime.now() - timedelta(days=7)]
    
    print(f"Average coverage last week: {last_week['total_coverage'].mean():.2f}%")
    print(f"Coverage variance: {last_week['total_coverage'].std():.2f}%")
    
    # Identify concerning trends
    if last_week['total_coverage'].iloc[-1] < last_week['total_coverage'].iloc[0]:
        print("⚠️  WARNING: Coverage is trending downward!")
```

### 2. Module Health Check
```bash
# Generate module-level coverage report
coverage run -m pytest
coverage report --skip-covered --show-missing

# Export detailed report for analysis
coverage json -o coverage_detailed.json
```

### 3. Test Suite Performance Review
```bash
# Check test execution times
pytest --durations=20

# Identify slow tests that may need optimization
pytest --durations=0 -m "not slow" | grep -E "([5-9]\.|[0-9]{2,}\.) seconds"

# Memory usage analysis
pytest -m unit --memprof
```

## Monthly Maintenance Tasks

### 1. Comprehensive Coverage Audit
```bash
# Full test suite with detailed reporting
pytest --cov=src --cov-report=html --cov-report=xml --cov-report=term

# Generate coverage diff report
git diff main...HEAD -- '*.py' | coverage-diff
```

### 2. Test Quality Review
- Review test assertions for meaningfulness
- Check for redundant tests
- Ensure edge cases are covered
- Verify mock quality

### 3. Update Coverage Goals
- Review module-specific targets
- Adjust based on code complexity changes
- Update CI/CD thresholds if needed

## Improving Coverage

### 1. Identify Coverage Gaps
```python
# Script to find low-coverage modules
import subprocess
import json

def find_low_coverage_modules(threshold=80):
    """Find modules below coverage threshold."""
    result = subprocess.run(
        ['coverage', 'json', '-o', '-'],
        capture_output=True,
        text=True
    )
    
    coverage_data = json.loads(result.stdout)
    low_coverage = []
    
    for file, data in coverage_data['files'].items():
        if 'src/' in file:
            coverage = data['summary']['percent_covered']
            if coverage < threshold:
                low_coverage.append({
                    'file': file,
                    'coverage': coverage,
                    'missing_lines': data['missing_lines']
                })
    
    return sorted(low_coverage, key=lambda x: x['coverage'])
```

### 2. Strategic Test Addition
```python
# Template for adding tests to improve coverage
def test_uncovered_scenario():
    """
    Test for lines 45-52 in module.py
    Addresses: Error handling for invalid input
    """
    # Arrange
    module = Module()
    invalid_input = {"bad": "data"}
    
    # Act & Assert
    with pytest.raises(ValidationError):
        module.process(invalid_input)
```

### 3. Coverage Sprint Planning
1. **Identify Target**: Select 3-5 low-coverage modules
2. **Set Goals**: Define specific coverage increases
3. **Time Box**: Allocate 2-4 hours per module
4. **Review**: Ensure new tests are meaningful

## Memory-Efficient Coverage Practices

### 1. Batch Test Execution
```bash
# Run tests in batches to manage memory
pytest -m unit --cov=src --cov-append
pytest -m integration --cov=src --cov-append
pytest -m e2e --cov=src --cov-append
coverage report
```

### 2. Selective Coverage Collection
```bash
# Only collect coverage for changed files
CHANGED_FILES=$(git diff --name-only main...HEAD | grep "\.py$")
pytest --cov=$(echo $CHANGED_FILES | tr ' ' ',')
```

### 3. Coverage Data Cleanup
```bash
# Clean old coverage data
find . -name ".coverage*" -mtime +7 -delete
rm -rf htmlcov/
rm -f coverage.xml

# Compress historical data
tar -czf coverage_archive_$(date +%Y%m).tar.gz .coverage-history/
```

## Troubleshooting Coverage Issues

### 1. Coverage Not Increasing
```bash
# Check if tests are actually running
pytest -v --collect-only | grep -c "test_"

# Verify coverage is being collected
pytest --cov=src --cov-report=term --no-cov-on-fail

# Check for coverage configuration issues
coverage debug sys
```

### 2. Inconsistent Coverage Reports
```bash
# Clear all coverage data and regenerate
coverage erase
rm -rf .pytest_cache/
pytest --cov=src --cov-report=term-missing

# Check for parallel execution issues
pytest -n 1 --cov=src  # Force single-threaded
```

### 3. Memory Issues During Coverage
```python
# Memory-efficient test configuration
# pytest.ini additions
[tool:pytest]
addopts = 
    --maxfail=3  # Stop after 3 failures
    -p no:cacheprovider  # Disable cache
    --tb=short  # Shorter tracebacks
    
[coverage:run]
parallel = True  # Enable parallel coverage
concurrency = multiprocessing
```

## CI/CD Coverage Maintenance

### 1. GitHub Actions Optimization
```yaml
# Optimize workflow for coverage
- name: Run tests with coverage
  run: |
    # Run tests in groups to avoid OOM
    pytest -m "unit" --cov=src --cov-report=xml:coverage-unit.xml
    pytest -m "integration" --cov=src --cov-report=xml:coverage-integration.xml
    
    # Combine coverage reports
    coverage combine
    coverage xml
```

### 2. Coverage Gate Configuration
```yaml
# Enforce coverage requirements
- name: Check coverage threshold
  run: |
    coverage report --fail-under=85
    
    # Check critical modules
    coverage report --include="src/orchestrator.py" --fail-under=90
    coverage report --include="src/transcription_processor.py" --fail-under=90
```

### 3. PR Coverage Checks
```yaml
# Automated PR comment with coverage
- uses: py-cov-action/python-coverage-comment-action@v3
  with:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    MINIMUM_GREEN: 85
    MINIMUM_ORANGE: 70
    ANNOTATE_MISSING_LINES: true
```

## Coverage Reporting

### 1. Weekly Status Report Template
```markdown
## Coverage Status Report - Week of [DATE]

### Overall Metrics
- Current Coverage: X.X%
- Change from Last Week: +/-X.X%
- Target: 85%
- Status: ✅ Meeting Target / ⚠️ Below Target

### Module Breakdown
| Module | Coverage | Change | Status |
|--------|----------|--------|--------|
| orchestrator.py | XX% | +X% | ✅ |
| transcription_processor.py | XX% | -X% | ⚠️ |

### Action Items
1. Add tests for uncovered lines in module X
2. Review failing tests in module Y
3. Optimize slow tests in module Z

### Trends
[Include coverage trend chart]
```

### 2. Dashboard Creation
```python
# Script to generate coverage dashboard
import matplotlib.pyplot as plt
import json
from datetime import datetime

def generate_coverage_dashboard():
    """Generate visual coverage dashboard."""
    # Load coverage data
    with open('coverage.json', 'r') as f:
        data = json.load(f)
    
    # Create dashboard
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
    
    # Overall coverage gauge
    ax1.text(0.5, 0.5, f"{data['totals']['percent_covered']:.1f}%",
             ha='center', va='center', fontsize=48)
    ax1.set_title('Overall Coverage')
    
    # Module breakdown
    modules = [(f, d['summary']['percent_covered']) 
               for f, d in data['files'].items() 
               if 'src/' in f]
    modules.sort(key=lambda x: x[1])
    
    # Save dashboard
    plt.tight_layout()
    plt.savefig('coverage_dashboard.png')
```

## Best Practices

### 1. Proactive Coverage Maintenance
- Run coverage checks before committing
- Add tests when adding new features
- Review coverage in code reviews
- Set up IDE coverage indicators

### 2. Sustainable Testing
- Focus on meaningful tests, not just coverage
- Maintain test quality over quantity
- Regular test refactoring
- Document complex test scenarios

### 3. Team Collaboration
- Share coverage responsibilities
- Celebrate coverage improvements
- Learn from coverage drops
- Regular coverage review meetings

## Emergency Procedures

### 1. Rapid Coverage Recovery
```bash
# When coverage drops below 83%
# 1. Identify biggest gaps
coverage report --skip-covered --sort=cover

# 2. Generate missing line report
coverage report --show-missing > missing_coverage.txt

# 3. Create recovery plan
python analyze_coverage_gaps.py > recovery_plan.md
```

### 2. Coverage Hotfix Process
1. Create hotfix branch
2. Add minimal tests to reach 85%
3. Fast-track PR review
4. Deploy with monitoring

### 3. Rollback Procedures
```bash
# If new tests cause issues
git revert --no-commit HEAD~1
pytest --lf  # Run last failed
git commit -m "Revert problematic tests"
```

## Automation Scripts

### 1. Coverage Monitor
```python
#!/usr/bin/env python3
"""coverage_monitor.py - Monitor and alert on coverage changes"""

import subprocess
import json
import sys

def check_coverage():
    """Check current coverage and alert if below threshold."""
    result = subprocess.run(
        ['coverage', 'json', '-o', '-'],
        capture_output=True,
        text=True
    )
    
    data = json.loads(result.stdout)
    coverage = data['totals']['percent_covered']
    
    if coverage < 85:
        print(f"⚠️  Coverage below threshold: {coverage:.2f}%")
        sys.exit(1)
    else:
        print(f"✅ Coverage healthy: {coverage:.2f}%")
        sys.exit(0)

if __name__ == "__main__":
    check_coverage()
```

### 2. Coverage Report Generator
```bash
#!/bin/bash
# generate_coverage_report.sh

# Run tests with coverage
echo "Running tests with coverage..."
pytest --cov=src --cov-report=html --cov-report=json

# Generate summary
echo "Coverage Summary:"
coverage report

# Open HTML report
if [[ "$OSTYPE" == "darwin"* ]]; then
    open htmlcov/index.html
else
    xdg-open htmlcov/index.html
fi
```

## Summary

Maintaining test coverage requires:
1. **Regular monitoring** - Daily checks, weekly reviews
2. **Proactive improvement** - Add tests with new features
3. **Memory efficiency** - Smart test execution strategies
4. **Team commitment** - Shared responsibility for coverage
5. **Automation** - CI/CD enforcement and reporting

Remember: Coverage is a tool for ensuring code quality, not a goal in itself. Focus on writing meaningful tests that provide confidence in your code's behavior.