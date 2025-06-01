# Test Troubleshooting Guide

This guide helps resolve common issues when running tests for the Podcast Transcriber.

## Common Test Failures and Solutions

### 1. Import Errors

**Error:**
```
ImportError: No module named 'src'
```

**Solutions:**
- Run tests from the project root directory
- Ensure `pythonpath = .` is in pytest.ini
- Install the package in development mode: `pip install -e .`

### 2. Missing Environment Variables

**Error:**
```
KeyError: 'GEMINI_API_KEY_1'
```

**Solutions:**
```bash
# Option 1: Use test environment file
cp .env.test .env

# Option 2: Export test variables
export GEMINI_API_KEY_1=test_key_1
export GEMINI_API_KEY_2=test_key_2

# Option 3: Run with test environment
source .env.test && pytest
```

### 3. Async Test Issues

**Error:**
```
RuntimeWarning: coroutine 'test_function' was never awaited
```

**Solutions:**
- Add `@pytest.mark.asyncio` decorator to async tests
- Ensure `pytest-asyncio` is installed: `pip install pytest-asyncio`
- Check asyncio_mode in pytest.ini is set to `strict`

### 4. File Permission Errors

**Error:**
```
PermissionError: [Errno 13] Permission denied: '/path/to/file'
```

**Solutions:**
- Use `tmp_path` fixture for all file operations in tests
- Never write to the actual project directories in tests
- Example:
  ```python
  def test_file_creation(tmp_path):
      test_file = tmp_path / "test.txt"
      test_file.write_text("content")
  ```

### 5. Mock Configuration Issues

**Error:**
```
AttributeError: 'MagicMock' object has no attribute 'generate_content_async'
```

**Solutions:**
- Use `AsyncMock` for async methods:
  ```python
  mock_client.generate_content_async = AsyncMock(return_value="result")
  ```
- Ensure mock structure matches actual API

### 6. Test Isolation Problems

**Symptoms:**
- Tests pass individually but fail when run together
- Random test failures
- State leaking between tests

**Solutions:**
- Use fixtures with function scope (default)
- Clear any global state in test teardown
- Don't modify shared test data
- Use `pytest --randomly-dont-shuffle` to debug order dependencies

### 7. Coverage Issues

**Problem:** Coverage reports show lower than expected coverage

**Solutions:**
- Check .coveragerc configuration
- Ensure source paths are correct
- Run with: `coverage run -m pytest`
- Check for:
  - Missing `__init__.py` files
  - Excluded patterns in .coveragerc
  - Dynamic imports not being tracked

### 8. Memory Issues

**Symptoms:**
- Tests consuming excessive memory
- Tests becoming progressively slower

**Solutions:**
- Use minimal test fixtures (see conftest.py)
- Clear large objects after tests:
  ```python
  @pytest.fixture
  def large_data():
      data = create_large_dataset()
      yield data
      del data  # Explicit cleanup
  ```
- Run memory-intensive tests separately

### 9. Timeout Issues

**Error:**
```
pytest.Timeout: test_function exceeded configured timeout
```

**Solutions:**
- Increase timeout for specific tests:
  ```python
  @pytest.mark.timeout(60)  # 60 seconds
  def test_slow_operation():
      pass
  ```
- Mock slow operations instead of running them
- Use `pytest.skip` for legitimately slow tests

### 10. Platform-Specific Failures

**Symptoms:** Tests fail on Windows/Mac but pass on Linux

**Solutions:**
- Use `pathlib.Path` instead of string paths
- Use `os.path.sep` for path separators
- Mock platform-specific behavior:
  ```python
  @pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
  def test_unix_only():
      pass
  ```

## Debugging Techniques

### 1. Interactive Debugging

```bash
# Drop into debugger on failure
pytest --pdb

# Use IPython debugger
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb

# Set breakpoint in code
import pdb; pdb.set_trace()
```

### 2. Verbose Output

```bash
# Show all output
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l
```

### 3. Running Specific Tests

```bash
# Run single test
pytest tests/test_config.py::TestConfig::test_load_yaml

# Run tests matching pattern
pytest -k "config and not invalid"

# Run last failed
pytest --lf

# Run failed first, then others
pytest --ff
```

### 4. Test Order Issues

```bash
# Run tests in random order
pytest --random-order

# Run in specific order for debugging
pytest --randomly-dont-shuffle
```

## Performance Optimization

### 1. Identify Slow Tests

```bash
# Show slowest 10 tests
pytest --durations=10

# Profile test execution
pytest --profile
```

### 2. Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run on all CPU cores
pytest -n auto

# Run on 4 cores
pytest -n 4
```

### 3. Skip Slow Tests

```python
# Mark slow tests
@pytest.mark.slow
def test_integration():
    pass

# Skip slow tests
pytest -m "not slow"
```

## CI/CD Specific Issues

### 1. Different Behavior in CI

**Check:**
- Environment variables
- Python version
- Installed dependencies
- File system differences
- Network restrictions

### 2. Flaky Tests

**Solutions:**
- Add retries for network operations
- Mock time-dependent behavior
- Use fixed random seeds
- Increase timeouts in CI

### 3. Resource Constraints

**Solutions:**
- Limit parallel execution in CI
- Use smaller test datasets
- Skip resource-intensive tests in CI:
  ```python
  @pytest.mark.skipif(os.getenv("CI"), reason="Too resource intensive for CI")
  ```

## Getting Help

If you're still stuck:

1. Check test output carefully - the error is often clear
2. Run with maximum verbosity: `pytest -vvv --tb=long`
3. Search for the error message in:
   - Project issues
   - Pytest documentation
   - Stack Overflow
4. Create a minimal reproducible example
5. Ask for help with:
   - Python version
   - OS
   - Complete error traceback
   - Minimal code to reproduce