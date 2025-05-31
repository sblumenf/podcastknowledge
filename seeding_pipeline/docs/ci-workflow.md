# CI/CD Workflow Guide

## What Happens Automatically

- Every push to main/develop runs all tests
- Every PR runs tests before allowing merge  
- Test failures block merging (protection)
- Coverage reports are generated and uploaded to Codecov

## How to Use

1. Make changes locally
2. Run tests locally first: `pytest`
3. Push to your branch
4. Check GitHub Actions tab for results
5. Fix any failures before merging

## Test Commands

### Running All Tests
```bash
pytest -v
```

### Running Tests with Coverage
```bash
pytest -v --cov=src --cov-report=xml --cov-report=html
```

### Running Specific Test Categories
```bash
# Unit tests only
pytest tests/unit -v

# Integration tests only  
pytest tests/integration -v

# E2E tests only
pytest tests/e2e -v
```

## Troubleshooting Common Issues

### Neo4j Connection Failures
- Ensure Neo4j is running locally on bolt://localhost:7687
- Check that NEO4J_PASSWORD environment variable is set
- Verify credentials: neo4j/password (default for local development)

### Import Errors
- Make sure virtual environment is activated: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt -r requirements-dev.txt`
- Check for circular imports or missing modules

### Test Collection Issues
- Verify test files follow naming convention: `test_*.py` or `*_test.py`
- Check that `__init__.py` files exist in test directories
- Ensure pytest can discover tests: `pytest --collect-only`

### Coverage Issues
- Coverage reports are generated in `htmlcov/` directory
- Open `htmlcov/index.html` in browser to view detailed coverage
- XML coverage report is saved as `coverage.xml` for CI systems

## CI Environment Details

### Services
- **Neo4j**: Runs in Docker container with health checks
- **Python**: Version 3.9 on Ubuntu latest
- **Coverage**: pytest-cov plugin generates XML and HTML reports

### Environment Variables
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Workflow Triggers
- Push to `main` or `develop` branches
- Pull requests targeting `main` branch

## Badge Status

Add this badge to your README.md to show CI status:

```markdown
[![CI](https://github.com/USERNAME/REPOSITORY/workflows/CI/badge.svg)](https://github.com/USERNAME/REPOSITORY/actions)
```

Replace `USERNAME` and `REPOSITORY` with actual values.

## Known Limitations

- CI currently runs on Ubuntu only
- Python 3.9 is the tested version
- Some tests may be flaky due to async operations
- Long-running tests may timeout (default: 6 hours)

## Getting Help

If CI fails and you can't determine the cause:

1. Check the Actions tab in GitHub for detailed logs
2. Look for error messages in the test output
3. Verify your changes work locally first
4. Check if main branch is also failing (infrastructure issue)
5. Consult the troubleshooting section above