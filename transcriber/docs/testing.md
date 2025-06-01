# Testing Guide for Podcast Transcriber

This guide covers everything you need to know about running and writing tests for the Podcast Transcriber project.

## Table of Contents
- [Quick Start](#quick-start)
- [Test Environment Setup](#test-environment-setup)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Mocking and Fixtures](#mocking-and-fixtures)
- [Troubleshooting](#troubleshooting)
- [CI/CD Integration](#cicd-integration)

## Quick Start

```bash
# Set up test environment
./scripts/setup_test_env.sh

# Run all tests
make test

# Run with coverage
make coverage

# Run only fast tests
make test-fast
```

## Test Environment Setup

### Prerequisites
- Python 3.8 or higher
- Virtual environment activated
- Test dependencies installed

### Automatic Setup
The easiest way to set up the test environment:

```bash
chmod +x scripts/setup_test_env.sh
./scripts/setup_test_env.sh
```

This script will:
- Create a virtual environment if needed
- Install all test dependencies
- Set up test directories
- Copy test environment variables
- Clean existing test artifacts
- Verify the setup

### Manual Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-mock pytest-cov pytest-timeout
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.test .env
   # Or set manually:
   export GEMINI_API_KEY_1=test_key_1
   export GEMINI_API_KEY_2=test_key_2
   ```

## Running Tests

### Using Make Commands

```bash
make test              # Run all tests
make test-unit         # Run only unit tests
make test-integration  # Run only integration tests
make test-fast         # Skip slow tests
make test-parallel     # Run tests in parallel
make coverage          # Generate coverage report
make test-failed       # Re-run only failed tests
```

### Using Pytest Directly

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run specific test class or method
pytest tests/test_config.py::TestConfig::test_load_from_yaml

# Run tests matching a pattern
pytest -k "config or parser"

# Run tests with specific marker
pytest -m unit
pytest -m "not slow"

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Show test durations
pytest --durations=10
```

### Test Markers

The project uses several test markers to categorize tests:

- `unit`: Fast, isolated unit tests
- `integration`: Tests requiring multiple components
- `slow`: Tests taking >1 second
- `network`: Tests requiring network access
- `asyncio`: Asynchronous tests
- `mock_heavy`: Tests with extensive mocking

Example usage:
```bash
# Run only unit tests
pytest -m unit

# Run everything except slow tests
pytest -m "not slow"

# Run unit and integration tests
pytest -m "unit or integration"
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures and configuration
├── fixtures/            # Reusable test fixtures
│   ├── __init__.py
│   ├── config.py       # Configuration fixtures
│   └── mocks.py        # Mock objects
├── test_config.py       # Configuration tests
├── test_feed_parser.py  # Feed parser tests
├── test_file_organizer.py
├── test_gemini_client.py
├── test_integration.py  # Integration tests
├── test_key_rotation_manager.py
├── test_logging.py
├── test_orchestrator_integration.py
├── test_progress_tracker.py
└── test_vtt_generator.py
```

## Writing Tests

### Best Practices

1. **Use descriptive test names:**
   ```python
   def test_config_loads_from_yaml_file_successfully():
       # Good: describes what is being tested
   
   def test_config():
       # Bad: too vague
   ```

2. **Arrange-Act-Assert pattern:**
   ```python
   def test_episode_marked_as_completed(self, tracker, episode_data):
       # Arrange
       tracker.mark_started(episode_data)
       
       # Act
       tracker.mark_completed(episode_data['guid'], '/output.vtt', 60.0)
       
       # Assert
       episode = tracker.state.episodes[episode_data['guid']]
       assert episode.status == EpisodeStatus.COMPLETED
   ```

3. **Use fixtures for common setup:**
   ```python
   @pytest.fixture
   def episode_data():
       return {
           'guid': 'test-ep-1',
           'title': 'Test Episode',
           'audio_url': 'https://example.com/audio.mp3'
       }
   ```

4. **Keep tests isolated:**
   - Use `tmp_path` for file operations
   - Mock external dependencies
   - Clean up after tests

### Async Tests

For testing async functions:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected_value
```

### Using tmp_path

Always use `tmp_path` fixture for file operations:

```python
def test_file_creation(tmp_path):
    # tmp_path is automatically cleaned up
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    assert test_file.exists()
    assert test_file.read_text() == "content"
```

## Mocking and Fixtures

### Common Fixtures

The project provides several fixtures in `conftest.py`:

- `tmp_path`: Temporary directory (pytest built-in)
- `minimal_vtt_content`: Minimal VTT test data
- `minimal_rss_feed`: Minimal RSS feed structure
- `mock_gemini_client`: Mock Gemini API client
- `in_memory_file_store`: In-memory file storage
- `shared_test_config`: Session-scoped configuration

### Mocking External Services

```python
def test_with_mock_api(mock_gemini_client):
    # Mock is automatically injected
    mock_gemini_client.transcribe_audio.return_value = "Transcript"
    
    # Use in test
    result = process_audio(mock_gemini_client)
    assert result == "Transcript"
```

### Creating Custom Fixtures

```python
@pytest.fixture
def custom_podcast_data():
    """Fixture providing test podcast data."""
    return {
        'title': 'Test Podcast',
        'episodes': [
            {'title': 'Episode 1', 'url': 'http://example.com/1.mp3'}
        ]
    }
```

## Troubleshooting

### Common Issues

1. **ImportError: No module named 'src'**
   - Ensure you're running tests from the project root
   - Check that `pythonpath = .` is in pytest.ini

2. **Tests failing with "API key not found"**
   - Set test environment variables: `export GEMINI_API_KEY_1=test_key_1`
   - Or use: `cp .env.test .env`

3. **Async test warnings**
   - Add `@pytest.mark.asyncio` decorator to async tests
   - Ensure `pytest-asyncio` is installed

4. **File permission errors**
   - Use `tmp_path` fixture instead of creating files in project directory
   - Check file permissions in test directories

5. **Memory issues with large tests**
   - Use minimal test fixtures (see conftest.py)
   - Run tests in smaller batches
   - Use `pytest -k` to run specific tests

### Debugging Tests

```bash
# Run with Python debugger
pytest --pdb

# Run with IPython debugger
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb

# Show print statements
pytest -s

# Verbose output with full tracebacks
pytest -vv --tb=long
```

### Performance Issues

If tests are running slowly:

1. **Check for slow tests:**
   ```bash
   pytest --durations=10
   ```

2. **Skip slow tests:**
   ```bash
   pytest -m "not slow"
   ```

3. **Run tests in parallel:**
   ```bash
   pip install pytest-xdist
   pytest -n auto
   ```

## CI/CD Integration

### GitHub Actions

Tests are automatically run on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

### Local CI Testing

Simulate CI environment locally:

```bash
# Run tests as CI would
make test-ci

# Use tox for multi-version testing
tox

# Test specific Python version
tox -e py311
```

### Coverage Requirements

- Minimum coverage: 80%
- Coverage reports generated in `htmlcov/`
- View report: `make coverage-html`

## Best Practices Summary

1. **Keep tests fast** - Use minimal fixtures and mock external calls
2. **Keep tests isolated** - Each test should be independent
3. **Use descriptive names** - Test names should explain what they test
4. **Mock external dependencies** - Don't make real API calls in tests
5. **Use tmp_path for files** - Automatic cleanup and isolation
6. **Group related tests** - Use classes to organize tests
7. **Add markers** - Categorize tests for selective running
8. **Document complex tests** - Add docstrings explaining test purpose

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Best Practices](https://docs.pytest.org/en/latest/explanation/goodpractices.html)
- [Python Testing 101](https://realpython.com/python-testing/)
- [Effective Python Testing](https://effectivepython.com/)