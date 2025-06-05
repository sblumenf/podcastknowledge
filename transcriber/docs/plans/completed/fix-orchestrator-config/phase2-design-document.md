# Phase 2: Design Document - Config Injection Pattern

## Task 2.1: Config Injection Design

### Proposed __init__ Signature
```python
def __init__(self, 
             output_dir: Path = Path("data/transcripts"), 
             enable_checkpoint: bool = True,
             resume: bool = False,
             data_dir: Optional[Path] = None,
             config: Optional[Config] = None):  # NEW PARAMETER
```

### Implementation Logic
```python
# Initialize configuration
if config is not None:
    self.config = config
else:
    self.config = Config()
```

### Benefits
1. **Backward Compatible**: Existing code continues to work without changes
2. **Test Friendly**: Tests can inject mock or custom configs
3. **Minimal Changes**: Only requires updating __init__ method
4. **Follows DI Principles**: Allows dependency injection while maintaining convenience

### Example Usage

#### Production Usage (unchanged)
```python
# Uses default Config()
orchestrator = TranscriptionOrchestrator()

# With custom paths
orchestrator = TranscriptionOrchestrator(
    output_dir=Path("custom/output"),
    enable_checkpoint=True
)
```

#### Test Usage (new capability)
```python
# Inject mock config
mock_config = Mock(spec=Config)
orchestrator = TranscriptionOrchestrator(config=mock_config)

# Use test config
test_config = Config.create_test_config(
    api={'timeout': 10},
    processing={'enable_progress_bar': False}
)
orchestrator = TranscriptionOrchestrator(config=test_config)
```

### Implementation Considerations
1. Config parameter should be last to maintain positional argument compatibility
2. Type hint as Optional[Config] for clarity
3. Document the parameter in docstring
4. No other initialization logic needs to change

## Task 2.2: Test Helper Pattern Design

### Existing Test Helper
Config already provides `Config.create_test_config(**overrides)` which:
- Sets test_mode=True
- Configures test-friendly defaults (shorter timeouts, no progress bars)
- Allows specific overrides via kwargs

### Proposed Test Fixture Enhancement
Create a reusable pytest fixture in `tests/conftest.py`:

```python
@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration with temp directories."""
    config = Config.create_test_config(
        output={'default_dir': str(tmp_path / 'output')},
        processing={
            'checkpoint_enabled': True,
            'quota_wait_enabled': False,  # Don't wait in tests
            'max_episode_length': 10  # Shorter for tests
        }
    )
    return config

@pytest.fixture
def mock_config():
    """Create a mock configuration for unit tests."""
    config = Mock(spec=Config)
    
    # Set up common config attributes
    config.api = Mock(timeout=10, max_attempts=1)
    config.processing = Mock(
        quota_wait_enabled=False,
        max_quota_wait_hours=0,
        quota_check_interval_minutes=1
    )
    config.validation = Mock(
        enabled=True,
        min_coverage_ratio=0.85,
        max_continuation_attempts=3
    )
    config.output = Mock(default_dir='test_output')
    
    # Add any methods that might be called
    config.get_api_keys = Mock(return_value=['test_key'])
    
    return config
```

### Usage in Tests

#### E2E/Integration Tests
```python
def test_full_pipeline(test_config, tmp_path):
    orchestrator = TranscriptionOrchestrator(
        output_dir=tmp_path / 'transcripts',
        config=test_config
    )
    # Test with real config but test-friendly settings
```

#### Unit Tests
```python
def test_quota_handling(mock_config):
    mock_config.processing.quota_wait_enabled = True
    orchestrator = TranscriptionOrchestrator(config=mock_config)
    # Test with fully mocked config
```

### Benefits
1. **Reduces Boilerplate**: Common test configs defined once
2. **Flexible**: Can use real Config or Mock as needed
3. **Type Safe**: Mock maintains Config interface
4. **Maintainable**: Central place for test configuration

### Migration Strategy
1. Add fixtures to conftest.py
2. Update failing tests to use fixtures
3. Gradually migrate other tests for consistency