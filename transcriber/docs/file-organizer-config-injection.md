# FileOrganizer Config Injection Documentation

## Overview

The `FileOrganizer` class has been updated to support optional configuration injection while maintaining full backward compatibility. This allows the component to use settings from the application's central configuration system when available, while still functioning independently when needed.

## Implementation Details

### Constructor Signature

```python
def __init__(self, base_dir: Optional[str] = None, config: Optional[Config] = None):
    """Initialize file organizer.
    
    Args:
        base_dir: Base directory for storing transcripts. If None, uses config or default.
        config: Optional configuration object. If provided, settings from config are used.
    """
```

### Priority Order

The FileOrganizer determines settings using the following priority:

1. **Explicit parameters** - Direct constructor arguments take precedence
2. **Config object** - If provided, config settings are used
3. **Default values** - Built-in defaults as fallback

### Config Settings Used

When a `Config` object is provided, the following settings are utilized:

- `config.output.default_dir` - Base directory for transcript storage
- `config.output.naming_pattern` - File naming pattern (supports placeholders)
- `config.output.sanitize_filenames` - Whether to sanitize filenames
- `config.output.max_filename_length` - Maximum length for filenames

## Usage Examples

### Basic Usage (Backward Compatible)

```python
# Without config - uses defaults
organizer = FileOrganizer()

# With explicit base directory
organizer = FileOrganizer(base_dir="/custom/path")
```

### With Config Injection

```python
from src.config import Config
from src.file_organizer import FileOrganizer

# Load configuration
config = Config()

# Create organizer with config
organizer = FileOrganizer(config=config)

# Base directory override still works
organizer = FileOrganizer(base_dir="/override/path", config=config)
```

### Custom Naming Patterns

The config supports custom naming patterns with placeholders:

```yaml
output:
  naming_pattern: "{podcast_name}/episodes/{date}_{episode_title}.vtt"
```

Available placeholders:
- `{podcast_name}` - Sanitized podcast name
- `{date}` - Publication date (YYYY-MM-DD format)
- `{episode_title}` - Sanitized episode title

### Disabling Filename Sanitization

```python
config = Config()
config.output.sanitize_filenames = False

organizer = FileOrganizer(config=config)
# Special characters in filenames will be preserved
```

## Testing

### Unit Tests

Test the config injection with mocked config:

```python
@pytest.fixture
def mock_config():
    config = Mock(spec=Config)
    config.output = Mock()
    config.output.default_dir = "/test/dir"
    config.output.naming_pattern = "{podcast_name}/{date}_{episode_title}.vtt"
    config.output.sanitize_filenames = True
    config.output.max_filename_length = 150
    return config

def test_with_config(mock_config):
    organizer = FileOrganizer(config=mock_config)
    assert str(organizer.base_dir) == "/test/dir"
```

### Integration Tests

Test with real config objects:

```python
def test_integration():
    config = Config.create_test_config()
    config.output.naming_pattern = "{date}/{podcast_name}_{episode_title}.vtt"
    
    organizer = FileOrganizer(config=config)
    # Test file organization with custom pattern
```

## Migration Guide

### For Existing Code

No changes required! Existing code will continue to work:

```python
# This still works
organizer = FileOrganizer(base_dir="data/transcripts")
```

### For New Code

Consider using config injection for consistency:

```python
# In your orchestrator or main application
config = Config()
organizer = FileOrganizer(config=config)
```

## Benefits

1. **Centralized Configuration** - All settings in one place
2. **Environment Flexibility** - Easy to override via environment variables
3. **Backward Compatible** - No breaking changes
4. **Testability** - Easy to mock config for testing
5. **Extensibility** - Easy to add new config options

## Future Enhancements

Potential future config options:
- Archive settings for old transcripts
- Backup configuration
- File permissions settings
- Compression options
- Metadata format preferences