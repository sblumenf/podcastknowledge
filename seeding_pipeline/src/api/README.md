# Podcast Knowledge Graph Pipeline API

## Overview

The Podcast Knowledge Graph Pipeline provides versioned APIs for seeding knowledge graphs from podcast data. 

## API Versions

### v1 (Current Stable)

- **Version**: 1.0.0
- **Status**: Stable
- **Import**: `from src.api.v1 import seed_podcast, seed_podcasts`

## Usage Examples

### Basic Usage (Recommended)

```python
from src.api.v1 import seed_podcast, seed_podcasts

# Seed a single podcast
result = seed_podcast({
    'name': 'My Podcast',
    'rss_url': 'https://example.com/feed.xml'
}, max_episodes=5)

# Seed multiple podcasts
results = seed_podcasts([
    {'name': 'Podcast 1', 'rss_url': 'https://example1.com/feed.xml'},
    {'name': 'Podcast 2', 'rss_url': 'https://example2.com/feed.xml'}
], max_episodes_each=10)
```

### With Custom Configuration

```python
from src.api.v1 import PodcastKnowledgePipeline
from src.core.config import Config

# Create custom configuration
config = Config.from_file('config/prod.yml')

# Initialize pipeline
pipeline = PodcastKnowledgePipeline(config)

try:
    # Process podcasts
    result = pipeline.seed_podcast({
        'name': 'Tech Talk',
        'rss_url': 'https://techtalk.example.com/feed.xml'
    })
finally:
    # Always cleanup
    pipeline.cleanup()
```

## Version Compatibility

### Checking Version

```python
from src.api.v1 import get_api_version, check_api_compatibility

# Get current version
version = get_api_version()  # "1.0.0"

# Check compatibility
is_compatible = check_api_compatibility("1.0")  # True
```

### Handling Deprecations

The API uses deprecation warnings to notify about functions that will be removed:

```python
import warnings

# Show deprecation warnings
warnings.filterwarnings('default', category=DeprecationWarning)

# This will show a warning if the function is deprecated
from src.api.v1 import some_deprecated_function
```

## Response Schema (v1)

All v1 API functions return a dictionary with the following guaranteed fields:

```python
{
    'start_time': str,              # ISO format timestamp
    'end_time': str,                # ISO format timestamp  
    'podcasts_processed': int,      # Number of podcasts processed
    'episodes_processed': int,      # Total episodes processed
    'episodes_failed': int,         # Number of failed episodes
    'processing_time_seconds': float,  # Total processing time
    'api_version': str,             # API version used ("1.0")
    # ... additional fields may be present
}
```

## Migration Guide

### Future Versions

When new API versions are released, they will:

1. Maintain backward compatibility within major versions
2. Provide clear migration guides
3. Support running multiple versions simultaneously
4. Give deprecation warnings before removing features

### Best Practices

1. **Always import from versioned API**: Use `from src.api.v1 import ...`
2. **Handle cleanup properly**: Use try/finally or context managers
3. **Check version compatibility**: Especially for library consumers
4. **Monitor deprecation warnings**: Update code before deprecations are removed
5. **Use keyword arguments**: For better forward compatibility

## Changelog

See [API_CHANGELOG.md](./API_CHANGELOG.md) for detailed version history.