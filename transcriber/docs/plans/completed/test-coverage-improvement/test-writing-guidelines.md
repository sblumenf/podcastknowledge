# Test Writing Guidelines for Podcast Transcriber

## Overview

This document provides guidelines for writing effective, maintainable, and memory-efficient tests for the podcast transcription pipeline. Following these guidelines ensures consistent test quality and helps maintain our 85% coverage requirement.

## Test Organization

### File Structure
```
tests/
├── conftest.py              # Shared fixtures and configuration
├── fixtures/                # Test data and mock objects
│   ├── __init__.py
│   ├── async_cleanup.py     # Async cleanup utilities
│   ├── config.py           # Test configuration fixtures
│   ├── mocks.py            # Mock objects and responses
│   └── test_config.yaml    # Test configuration file
├── test_*_unit.py          # Unit tests for individual modules
├── test_*_integration.py   # Integration tests
├── test_*_e2e.py          # End-to-end tests
└── test_performance*.py    # Performance tests
```

### Naming Conventions

1. **Test Files**: 
   - Unit tests: `test_{module_name}_unit.py`
   - Integration tests: `test_{feature}_integration.py`
   - E2E tests: `test_e2e_{scenario}.py`
   - Performance tests: `test_performance_{aspect}.py`

2. **Test Functions**:
   - Start with `test_`
   - Use descriptive names: `test_transcribe_episode_with_invalid_url`
   - Group related tests in classes: `class TestGeminiClient:`

3. **Test Classes**:
   - Use `Test` prefix: `TestTranscriptionProcessor`
   - Group by functionality or component

## Test Categories and Markers

### Required Markers
```python
@pytest.mark.unit          # No external dependencies
@pytest.mark.integration   # May use external services
@pytest.mark.e2e          # Full system tests
@pytest.mark.network      # Requires network access
@pytest.mark.slow         # Takes >5 seconds
@pytest.mark.performance  # Performance benchmarks
@pytest.mark.memory_intensive  # Uses significant memory
```

### Usage Example
```python
@pytest.mark.unit
def test_sanitize_filename():
    """Test filename sanitization removes invalid characters."""
    assert sanitize_filename("test/file:name?.mp3") == "test_file_name_.mp3"

@pytest.mark.integration
@pytest.mark.network
async def test_gemini_api_call():
    """Test actual API call to Gemini service."""
    # Test implementation
```

## Memory-Efficient Testing Practices

### 1. Fixture Scope Management
```python
# Use appropriate fixture scopes to minimize memory usage
@pytest.fixture(scope="module")  # Reuse across tests in module
def large_test_data():
    """Create expensive test data once per module."""
    data = generate_large_dataset()
    yield data
    # Cleanup after module completion
    del data

@pytest.fixture(scope="function")  # Fresh for each test
def mutable_config():
    """Create fresh config for each test."""
    return Config()
```

### 2. Explicit Resource Cleanup
```python
@pytest.fixture
async def test_client():
    """Create and cleanup test client."""
    client = GeminiClient(api_keys=["test_key"])
    yield client
    # Explicit cleanup
    await client.close()
    del client

def test_with_temporary_files(tmp_path):
    """Use pytest's tmp_path for automatic cleanup."""
    test_file = tmp_path / "test.vtt"
    test_file.write_text("test content")
    # File automatically cleaned up after test
```

### 3. Mock Heavy Operations
```python
@pytest.fixture
def mock_gemini_response():
    """Mock API responses to avoid memory-intensive operations."""
    return {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest transcript"
                }]
            }
        }]
    }

def test_transcription_processor(mocker, mock_gemini_response):
    """Test with mocked API calls."""
    mock_api = mocker.patch('src.gemini_client.GeminiClient.generate_content')
    mock_api.return_value = mock_gemini_response
    # Test implementation
```

## Testing Best Practices

### 1. Test Structure (AAA Pattern)
```python
def test_episode_processing():
    """Follow Arrange-Act-Assert pattern."""
    # Arrange: Set up test data and mocks
    episode = Episode(title="Test", audio_url="http://test.mp3")
    processor = TranscriptionProcessor()
    
    # Act: Execute the code under test
    result = processor.process_episode(episode)
    
    # Assert: Verify the results
    assert result.status == "completed"
    assert result.transcript is not None
```

### 2. Meaningful Assertions
```python
# Bad: Generic assertion
assert result is not None

# Good: Specific assertions with context
assert result is not None, "Processing should return a result"
assert result.status == "completed", f"Expected 'completed', got '{result.status}'"
assert len(result.transcript) > 0, "Transcript should not be empty"
```

### 3. Test Data Fixtures
```python
# fixtures/test_data.py
@pytest.fixture
def sample_rss_feed():
    """Provide consistent test RSS feed data."""
    return """<?xml version="1.0"?>
    <rss version="2.0">
        <channel>
            <title>Test Podcast</title>
            <item>
                <title>Episode 1</title>
                <enclosure url="http://example.com/ep1.mp3" type="audio/mpeg"/>
            </item>
        </channel>
    </rss>"""

# In test file
def test_feed_parsing(sample_rss_feed):
    """Use fixture for consistent test data."""
    episodes = parse_feed(sample_rss_feed)
    assert len(episodes) == 1
```

### 4. Parametrized Tests
```python
@pytest.mark.parametrize("input_text,expected_speaker", [
    ("John: Hello there", "John"),
    ("JANE: How are you?", "Jane"),
    ("Dr. Smith: Good morning", "Dr. Smith"),
    ("Unknown text", "SPEAKER_00"),
])
def test_speaker_extraction(input_text, expected_speaker):
    """Test multiple scenarios with parametrize."""
    result = extract_speaker(input_text)
    assert result == expected_speaker
```

### 5. Async Testing
```python
@pytest.mark.asyncio
async def test_async_processing():
    """Test async functions properly."""
    processor = AsyncProcessor()
    
    # Use async context managers
    async with processor:
        result = await processor.process_async()
        assert result.success
    
    # Ensure cleanup happened
    assert processor.closed
```

## Mocking Guidelines

### 1. Mock External Services
```python
@pytest.fixture
def mock_youtube_search(mocker):
    """Mock YouTube search to avoid network calls."""
    mock = mocker.patch('src.youtube_searcher.search_youtube')
    mock.return_value = "https://youtube.com/watch?v=test123"
    return mock

def test_with_youtube_search(mock_youtube_search):
    """Test using mocked YouTube search."""
    result = process_with_youtube("test query")
    mock_youtube_search.assert_called_once_with("test query")
```

### 2. Mock Time-Dependent Code
```python
@pytest.fixture
def fixed_time(mocker):
    """Fix time for consistent tests."""
    mock_time = mocker.patch('time.time')
    mock_time.return_value = 1234567890.0
    return mock_time

def test_rate_limiting(fixed_time):
    """Test rate limiting with fixed time."""
    limiter = RateLimiter(requests_per_minute=60)
    # Time won't advance during test
    for _ in range(60):
        assert limiter.can_proceed()
```

## Performance Testing

### 1. Memory Usage Tests
```python
@pytest.mark.performance
@pytest.mark.memory_intensive
def test_memory_usage():
    """Monitor memory usage during processing."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Perform memory-intensive operation
    result = process_large_feed(episodes=100)
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    assert memory_increase < 100, f"Memory usage increased by {memory_increase}MB"
```

### 2. Execution Time Tests
```python
@pytest.mark.performance
def test_processing_speed(benchmark):
    """Benchmark processing speed."""
    episodes = create_test_episodes(10)
    
    # pytest-benchmark will handle timing
    result = benchmark(process_episodes, episodes)
    
    assert len(result) == 10
    # Benchmark results automatically reported
```

## Error and Edge Case Testing

### 1. Exception Testing
```python
def test_invalid_input_handling():
    """Test proper exception handling."""
    with pytest.raises(ValueError, match="Invalid URL format"):
        process_episode("not-a-url")
    
    # Test exception details
    with pytest.raises(APIError) as exc_info:
        make_api_call_with_invalid_key()
    
    assert exc_info.value.status_code == 401
    assert "Invalid API key" in str(exc_info.value)
```

### 2. Edge Cases
```python
@pytest.mark.parametrize("edge_case", [
    "",                    # Empty string
    None,                  # None value
    "x" * 10000,          # Very long string
    "unicode: 你好世界",    # Unicode characters
    "special: \n\t\r",    # Special characters
])
def test_edge_cases(edge_case):
    """Test edge cases systematically."""
    result = process_text(edge_case)
    assert result is not None  # Should handle all cases gracefully
```

## Test Coverage Requirements

### Module-Specific Targets
1. **Critical Path (≥90%)**:
   - `orchestrator.py`
   - `transcription_processor.py`
   - `checkpoint_recovery.py`

2. **API Integration (≥85%)**:
   - `gemini_client.py`
   - `retry_wrapper.py`

3. **Supporting Modules (≥80%)**:
   - `file_organizer.py`
   - `metadata_index.py`
   - `state_management.py`

### Coverage Improvement Strategy
```python
# Check current coverage
pytest --cov=src.module_name --cov-report=term-missing

# Identify missing lines and add tests
def test_uncovered_edge_case():
    """Test specifically targets lines 45-48 in module.py"""
    # Test implementation
```

## Common Pitfalls to Avoid

1. **Don't Test Implementation Details**
   ```python
   # Bad: Testing private methods
   def test_private_method():
       assert obj._internal_state == expected
   
   # Good: Test public interface
   def test_public_behavior():
       result = obj.process()
       assert result == expected
   ```

2. **Avoid Time-Dependent Tests**
   ```python
   # Bad: Depends on actual time
   def test_timeout():
       time.sleep(2)
       assert thing.timed_out
   
   # Good: Mock time
   def test_timeout(mocker):
       mock_time = mocker.patch('time.time')
       mock_time.side_effect = [0, 2.1]  # Simulate time passing
       assert thing.check_timeout()
   ```

3. **Don't Hardcode Paths**
   ```python
   # Bad: Hardcoded path
   def test_file_operations():
       with open("/tmp/test.txt", "w") as f:
           f.write("test")
   
   # Good: Use tmp_path fixture
   def test_file_operations(tmp_path):
       test_file = tmp_path / "test.txt"
       test_file.write_text("test")
   ```

## Continuous Integration Considerations

1. **Mark Tests Appropriately**
   - Quick unit tests run on every commit
   - Integration tests run on PR
   - E2E tests run before merge to main

2. **Resource Limits**
   - Keep individual test execution under 5 seconds
   - Total test suite should complete in <10 minutes
   - Memory usage per test should stay under 100MB

3. **Test Isolation**
   - Each test must be independent
   - No shared state between tests
   - Clean up all resources after each test

## Maintenance Guidelines

1. **Regular Review**
   - Review test coverage weekly
   - Update tests when implementation changes
   - Remove obsolete tests
   - Refactor duplicate test code

2. **Documentation**
   - Document complex test scenarios
   - Explain non-obvious assertions
   - Keep test data fixtures updated

3. **Performance Monitoring**
   - Track test execution times
   - Monitor memory usage trends
   - Optimize slow tests

## Example: Complete Test Module

```python
"""
Test module for TranscriptionProcessor.

This module provides comprehensive testing for the transcription
processing functionality, including unit tests, integration tests,
and error scenarios.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.transcription_processor import TranscriptionProcessor
from src.models import Episode, TranscriptionResult
from tests.fixtures.mocks import mock_gemini_response

class TestTranscriptionProcessor:
    """Test suite for TranscriptionProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance for testing."""
        return TranscriptionProcessor(
            gemini_client=Mock(),
            config={"timeout": 30}
        )
    
    @pytest.fixture
    def sample_episode(self):
        """Create sample episode for testing."""
        return Episode(
            guid="test-123",
            title="Test Episode",
            audio_url="https://example.com/audio.mp3",
            pub_date=datetime.now()
        )
    
    @pytest.mark.unit
    def test_initialization(self):
        """Test processor initialization."""
        processor = TranscriptionProcessor()
        assert processor is not None
        assert processor.config["timeout"] == 300  # Default
    
    @pytest.mark.unit
    def test_process_episode_success(self, processor, sample_episode, 
                                   mock_gemini_response):
        """Test successful episode processing."""
        # Arrange
        processor.gemini_client.generate_content.return_value = mock_gemini_response
        
        # Act
        result = processor.process_episode(sample_episode)
        
        # Assert
        assert isinstance(result, TranscriptionResult)
        assert result.status == "completed"
        assert result.transcript is not None
        assert sample_episode.guid in result.transcript
    
    @pytest.mark.unit
    def test_process_episode_api_error(self, processor, sample_episode):
        """Test handling of API errors."""
        # Arrange
        processor.gemini_client.generate_content.side_effect = Exception("API Error")
        
        # Act & Assert
        with pytest.raises(Exception, match="API Error"):
            processor.process_episode(sample_episode)
    
    @pytest.mark.integration
    @pytest.mark.network
    async def test_real_api_call(self, sample_episode):
        """Test with real API call (integration test)."""
        # Skip if no API key available
        api_key = os.environ.get("GEMINI_API_KEY_1")
        if not api_key:
            pytest.skip("No API key available")
        
        processor = TranscriptionProcessor()
        result = await processor.process_episode_async(sample_episode)
        
        assert result.status == "completed"
        assert len(result.transcript) > 100
```

## Summary

Following these guidelines ensures:
1. **Consistent** test quality across the codebase
2. **Maintainable** tests that are easy to understand and update
3. **Efficient** tests that don't consume excessive resources
4. **Comprehensive** coverage of all critical functionality
5. **Reliable** CI/CD pipeline with fast feedback

Remember: Good tests are an investment in code quality and developer productivity. Take time to write them well.