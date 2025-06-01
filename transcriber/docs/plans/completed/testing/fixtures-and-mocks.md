# Fixtures and Mocks Documentation

This document describes the test fixtures and mocking patterns used in the Podcast Transcriber test suite.

## Core Fixtures

### File System Fixtures

#### `tmp_path` (pytest built-in)
- **Purpose**: Provides a unique temporary directory for each test
- **Cleanup**: Automatic after test completion
- **Usage**:
  ```python
  def test_file_operations(tmp_path):
      test_file = tmp_path / "test.vtt"
      test_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nTest")
  ```

#### `test_data_dir`
- **Purpose**: Creates a structured test data directory
- **Location**: `conftest.py`
- **Structure**:
  ```
  data/
  ├── transcripts/
  └── checkpoints/
  ```
- **Usage**:
  ```python
  def test_with_data_dir(test_data_dir):
      transcript_dir = test_data_dir / "transcripts"
      assert transcript_dir.exists()
  ```

### Configuration Fixtures

#### `test_config` 
- **Purpose**: Provides a complete test configuration object
- **Location**: `fixtures/config.py`
- **Features**:
  - All required fields populated
  - Test-appropriate values (short timeouts, etc.)
  - Environment variable overrides disabled

#### `test_config_minimal`
- **Purpose**: Minimal valid configuration for fast tests
- **Usage**:
  ```python
  def test_quick_config(test_config_minimal):
      assert test_config_minimal.api.timeout == 30
  ```

#### `shared_test_config` (session-scoped)
- **Purpose**: Shared configuration to avoid repeated parsing
- **Scope**: Session (created once per test run)
- **Performance**: Reduces test setup time

### Mock Data Fixtures

#### `minimal_vtt_content`
- **Purpose**: Minimal valid VTT content (<200 bytes)
- **Content**:
  ```vtt
  WEBVTT
  
  00:00:01.000 --> 00:00:03.000
  Test content.
  ```

#### `minimal_rss_feed`
- **Purpose**: Minimal RSS feed structure
- **Content**: Single podcast with one episode
- **Size**: <500 bytes

#### `minimal_episode_metadata`
- **Purpose**: Basic episode information
- **Fields**: title, podcast_name, guid, audio_url, publication_date

### Mock Objects

#### `mock_gemini_client`
- **Purpose**: Mock Gemini API client
- **Methods**:
  - `generate_content_async`: Returns AsyncMock
  - `get_usage_summary`: Returns usage dict
- **Usage**:
  ```python
  def test_transcription(mock_gemini_client):
      mock_gemini_client.generate_content_async.return_value = "Transcript"
  ```

#### `mock_logger`
- **Purpose**: In-memory logger for testing log output
- **Features**:
  - Captures all log messages
  - Provides `messages` list for assertions
  - `clear()` method to reset between tests
- **Usage**:
  ```python
  def test_logging(mock_logger):
      function_under_test()
      assert ('ERROR', 'Expected error') in mock_logger.messages
  ```

#### `in_memory_file_store`
- **Purpose**: Replaces file system operations
- **Methods**:
  - `write(path, content)`
  - `read(path)`
  - `exists(path)`
  - `list_files()`
  - `clear()`

## Mock Patterns

### Mocking Async Operations

```python
# Mock async method
mock_client.transcribe_audio = AsyncMock(return_value="transcript")

# Mock with side effects
mock_client.process = AsyncMock(side_effect=[
    "First call result",
    Exception("Second call fails"),
    "Third call result"
])
```

### Mocking File Operations

```python
# Using mock_open
from unittest.mock import mock_open

@patch('builtins.open', mock_open(read_data='file content'))
def test_file_reading():
    with open('any_file.txt') as f:
        assert f.read() == 'file content'
```

### Mocking External APIs

```python
# Mock feedparser
@patch('feedparser.parse')
def test_feed_parsing(mock_parse):
    mock_parse.return_value = {
        'feed': {'title': 'Test'},
        'entries': [{'title': 'Episode 1'}]
    }
```

### Mocking Time

```python
# Mock datetime
@patch('src.module.datetime')
def test_with_fixed_time(mock_datetime):
    mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
    mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
```

## Common Mock Scenarios

### 1. API Rate Limiting

```python
@pytest.fixture
def mock_rate_limited_client():
    client = MagicMock()
    client.transcribe_audio = AsyncMock(side_effect=[
        "Success",
        Exception("Rate limit exceeded"),
        "Success after retry"
    ])
    return client
```

### 2. Network Failures

```python
@pytest.fixture
def mock_network_error():
    import requests
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.ConnectionError("Network error")
        yield mock_get
```

### 3. Progress Tracking

```python
@pytest.fixture
def mock_progress_tracker():
    tracker = MagicMock()
    tracker.state = MagicMock(episodes={})
    tracker.mark_started = MagicMock()
    tracker.mark_completed = MagicMock()
    tracker.mark_failed = MagicMock()
    return tracker
```

### 4. Checkpoint Recovery

```python
@pytest.fixture
def mock_checkpoint_manager(tmp_path):
    manager = MagicMock()
    manager.checkpoint_dir = tmp_path / "checkpoints"
    manager.start_episode = MagicMock()
    manager.complete_stage = MagicMock()
    manager.mark_completed = MagicMock()
    return manager
```

## Testing Best Practices

### 1. Fixture Scope

- **Function** (default): Fresh fixture for each test
- **Class**: Shared within test class
- **Module**: Shared within test module
- **Session**: Created once per test run

Choose the narrowest scope that works for your use case.

### 2. Fixture Composition

```python
@pytest.fixture
def complete_test_environment(tmp_path, mock_gemini_client, test_config):
    """Composite fixture providing full test environment."""
    return {
        'data_dir': tmp_path,
        'client': mock_gemini_client,
        'config': test_config
    }
```

### 3. Parametrized Fixtures

```python
@pytest.fixture(params=['round_robin', 'random'])
def rotation_strategy(request):
    """Test with different rotation strategies."""
    return request.param

def test_key_rotation(rotation_strategy):
    manager = KeyRotationManager(strategy=rotation_strategy)
    # Test with each strategy
```

### 4. Cleanup

```python
@pytest.fixture
def resource_with_cleanup():
    """Fixture with explicit cleanup."""
    resource = create_resource()
    yield resource
    # Cleanup runs after test
    resource.close()
    cleanup_temp_files()
```

## Mock Utilities

### Custom Mock Assertions

```python
def assert_called_with_retry(mock_func, expected_args, max_attempts=3):
    """Assert function was called with retry logic."""
    assert mock_func.call_count <= max_attempts
    assert any(
        call.args == expected_args 
        for call in mock_func.call_args_list
    )
```

### Mock Context Managers

```python
@contextmanager
def mock_api_quota(limit=10):
    """Mock API with quota limit."""
    calls = 0
    
    def api_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > limit:
            raise Exception("Quota exceeded")
        return f"Result {calls}"
    
    with patch('src.api.call', side_effect=api_call):
        yield
```

## Troubleshooting Mocks

### Common Issues

1. **Mock not being used**: Ensure patch target is correct
   ```python
   # Wrong: @patch('requests.get')
   # Right: @patch('src.module.requests.get')
   ```

2. **AsyncMock not awaited**: Use AsyncMock for async methods
   ```python
   mock.async_method = AsyncMock(return_value=result)
   ```

3. **Side effects not working**: Check call count
   ```python
   # side_effect list is consumed on each call
   mock.method.side_effect = [1, 2, 3]
   ```

4. **Mock leaking between tests**: Use fixtures or context managers
   ```python
   with patch('src.module.function') as mock:
       # Mock is automatically cleaned up
   ```

## Examples

### Complete Test with Mocks

```python
@pytest.mark.asyncio
async def test_episode_processing_with_retry(
    tmp_path, 
    mock_gemini_client,
    mock_progress_tracker,
    minimal_episode_metadata
):
    """Test episode processing with retry on failure."""
    # Arrange
    mock_gemini_client.transcribe_audio = AsyncMock(
        side_effect=[
            Exception("First attempt fails"),
            "Successful transcript"
        ]
    )
    
    processor = TranscriptionProcessor(
        gemini_client=mock_gemini_client,
        progress_tracker=mock_progress_tracker,
        output_dir=tmp_path
    )
    
    # Act
    result = await processor.process_episode(minimal_episode_metadata)
    
    # Assert
    assert result == "Successful transcript"
    assert mock_gemini_client.transcribe_audio.call_count == 2
    mock_progress_tracker.mark_completed.assert_called_once()
```

This documentation should be kept up to date as new fixtures and mocking patterns are added to the test suite.