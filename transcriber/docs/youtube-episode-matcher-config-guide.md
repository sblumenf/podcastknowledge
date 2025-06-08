# YouTube Episode Matcher Configuration Guide

## Overview

This guide covers all configuration options for the YouTube Episode Matcher system. Configuration can be done through YAML files, environment variables, or programmatically.

## Quick Start

### Minimum Configuration

1. **Set YouTube API Key** (Required)

   In `.env` file:
   ```bash
   YOUTUBE_API_KEY=your-youtube-api-key-here
   ```

   Or in `config/default.yaml`:
   ```yaml
   youtube_api:
     api_key: "your-youtube-api-key-here"
   ```

2. **Run with defaults**
   ```python
   from src.config import Config
   from src.youtube_episode_matcher import YouTubeEpisodeMatcher
   
   config = Config()
   matcher = YouTubeEpisodeMatcher(config)
   ```

## Getting a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable YouTube Data API v3:
   - Go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click and enable it
4. Create credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Optionally restrict the key to YouTube Data API v3

## Configuration Options

### YouTube API Configuration

```yaml
youtube_api:
  # YouTube Data API v3 key (REQUIRED)
  api_key: "your-api-key"
  
  # Minimum confidence score to accept a match (0.0-1.0)
  # Higher values = more strict matching
  # Default: 0.90
  confidence_threshold: 0.90
  
  # Maximum search results per query
  # Lower values = faster but might miss matches
  # Higher values = better coverage but uses more quota
  # Default: 10, Max: 50
  max_results_per_search: 10
  
  # Maximum quota units to spend per episode
  # Prevents runaway quota usage
  # Default: 500 (allows ~5 searches per episode)
  search_quota_per_episode: 500
```

### YouTube Search Configuration

```yaml
youtube_search:
  # Enable/disable YouTube search
  # Default: true
  enabled: true
  
  # Search method (currently only 'rss_only' implemented)
  # Future: 'rss_and_search', 'search_only'
  # Default: "rss_only"
  method: "rss_only"
  
  # Cache search results to disk
  # Default: true
  cache_results: true
  
  # Fuzzy match threshold for title similarity (0.0-1.0)
  # Default: 0.85
  fuzzy_match_threshold: 0.85
  
  # Duration tolerance for matching (0.0-1.0)
  # 0.1 = 10% tolerance (e.g., 60min ± 6min)
  # Default: 0.10
  duration_tolerance: 0.10
  
  # Maximum results for initial searches
  # Default: 5
  max_search_results: 5
```

### Output Configuration

```yaml
output:
  # Base directory for output files and caches
  # Default: "data"
  base_dir: "data"
  
  # Default output directory for transcripts
  # Default: "data/transcripts"
  default_dir: "data/transcripts"
```

## Environment Variables

All YouTube-specific settings can be configured via environment variables:

```bash
# YouTube API key (required)
YOUTUBE_API_KEY=your-api-key

# Confidence threshold (optional)
# Default: 0.90
YOUTUBE_CONFIDENCE_THRESHOLD=0.90

# Standard output directory
# Used for cache files
PODCAST_OUTPUT_DIR=data/transcripts
```

## Configuration Precedence

Configuration values are applied in this order (later overrides earlier):
1. Default values in code
2. Values from YAML configuration file
3. Environment variables
4. Programmatic configuration

Example:
```python
# Programmatic override
config = Config()
config.youtube_api.confidence_threshold = 0.95  # Overrides all other sources
```

## Performance Tuning

### For High Accuracy

Optimize for finding the best matches:

```yaml
youtube_api:
  confidence_threshold: 0.95        # Very strict matching
  max_results_per_search: 20        # Search more results
  search_quota_per_episode: 1000    # Allow more searches

youtube_search:
  fuzzy_match_threshold: 0.90       # Stricter title matching
  duration_tolerance: 0.05          # Tighter duration match (5%)
```

### For Quota Conservation

Minimize API usage:

```yaml
youtube_api:
  confidence_threshold: 0.85        # Accept good-enough matches
  max_results_per_search: 5         # Fewer results per search
  search_quota_per_episode: 300     # Limit searches per episode

youtube_search:
  cache_results: true               # Always cache
  duration_tolerance: 0.15          # More flexible matching
```

### For Speed

Optimize for fast processing:

```yaml
youtube_api:
  max_results_per_search: 3         # Minimal results
  search_quota_per_episode: 200     # Stop early if no match

youtube_search:
  method: "rss_only"                # Don't use external search
```

## Cache Management

### Channel Associations Cache

Location: `{output.base_dir}/.channel_associations.json`

The system automatically learns which YouTube channels host which podcasts:

```json
{
  "The Tim Ferriss Show": ["UC1yBKRuGpC1tSM73A0ZjYjQ"],
  "The Daily": ["UC2ZO3QgQ5p5r0VIRuQPpW5w"]
}
```

To clear the cache:
```python
matcher.clear_channel_cache()
```

### Search Results Cache

Location: `{output.base_dir}/.youtube_cache.json`

Caches YouTube search results to avoid repeated searches:

```json
{
  "Episode 123_guid-12345": "https://youtube.com/watch?v=abc123",
  "Episode 124_guid-12346": "NOT_FOUND"
}
```

## Common Configurations

### Development/Testing

```yaml
youtube_api:
  api_key: "test-api-key"
  confidence_threshold: 0.80    # More lenient for testing

development:
  test_mode: true
  mock_api_calls: true          # Don't make real API calls
```

### Production - Conservative

```yaml
youtube_api:
  api_key: "${YOUTUBE_API_KEY}"  # From environment
  confidence_threshold: 0.92      # High accuracy
  max_results_per_search: 10
  search_quota_per_episode: 400

youtube_search:
  cache_results: true
  duration_tolerance: 0.08        # 8% tolerance
```

### Production - Aggressive

```yaml
youtube_api:
  api_key: "${YOUTUBE_API_KEY}"
  confidence_threshold: 0.88      # Accept more matches
  max_results_per_search: 15
  search_quota_per_episode: 800   # More thorough search

youtube_search:
  cache_results: true
  fuzzy_match_threshold: 0.80     # More flexible
  duration_tolerance: 0.12
```

## Integration with Transcriber

To integrate YouTube matching with the podcast transcriber:

```yaml
# config/default.yaml
youtube_api:
  api_key: "${YOUTUBE_API_KEY}"
  confidence_threshold: 0.90

youtube_search:
  enabled: true
  extract_from_rss: true        # First try RSS feeds
  use_yt_dlp: false            # Future: external search
  cache_results: true
```

## Monitoring Configuration

### Logging

Configure logging for YouTube matcher:

```yaml
logging:
  console_level: "INFO"
  file_level: "DEBUG"
  
# In code:
import logging
logging.getLogger('youtube_episode_matcher').setLevel(logging.DEBUG)
logging.getLogger('youtube_api_client').setLevel(logging.INFO)
```

### Metrics

Access metrics programmatically:

```python
metrics = matcher.get_metrics()
print(f"Success rate: {metrics['success_rate']:.1%}")
print(f"Quota remaining: {metrics['quota_status']['remaining']}")
```

## Security Best Practices

1. **Never commit API keys**
   ```yaml
   # Bad - don't do this
   youtube_api:
     api_key: "AIzaSyD..."  # Never commit actual keys
   
   # Good - use environment variable
   youtube_api:
     api_key: "${YOUTUBE_API_KEY}"
   ```

2. **Restrict API key usage**
   - In Google Cloud Console, restrict key to:
     - YouTube Data API v3 only
     - Specific IP addresses or referrers if applicable

3. **Monitor quota usage**
   - Set up alerts in Google Cloud Console
   - Check metrics regularly
   - Implement quota tracking in your application

4. **Rotate keys periodically**
   - Generate new keys every few months
   - Keep old keys active during transition
   - Update configuration without downtime

## Troubleshooting Configuration

### API Key Issues

```python
# Test API key validity
from src.youtube_api_client import YouTubeAPIClient

client = YouTubeAPIClient("your-api-key")
try:
    client._validate_api_key()
    print("API key is valid")
except Exception as e:
    print(f"API key error: {e}")
```

### Configuration Validation

```python
# Validate configuration
config = Config()

# Check required settings
assert config.youtube_api.api_key, "API key not set"
assert 0 < config.youtube_api.confidence_threshold <= 1, "Invalid threshold"

# Print active configuration
print(f"API Key: {'set' if config.youtube_api.api_key else 'missing'}")
print(f"Confidence: {config.youtube_api.confidence_threshold}")
print(f"Max results: {config.youtube_api.max_results_per_search}")
```

### Debug Configuration Loading

```python
# See what configuration is being used
import json

config = Config()
print(json.dumps(config.to_dict(), indent=2))
```

## Migration Guide

### From RSS-only to YouTube Matching

1. Obtain YouTube API key
2. Update configuration:
   ```yaml
   youtube_api:
     api_key: "${YOUTUBE_API_KEY}"
   
   youtube_search:
     enabled: true
     extract_from_rss: true
   ```
3. Test with known episodes first
4. Monitor quota usage
5. Adjust confidence threshold based on results

### Upgrading Configuration

When upgrading, new configuration options use sensible defaults:

```python
# Old configuration continues to work
config = Config("config/old-config.yaml")

# New options use defaults
print(config.youtube_api.confidence_threshold)  # 0.90 (default)
```