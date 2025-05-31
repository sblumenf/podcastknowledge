# Configuration Guide

The Podcast Transcription Pipeline uses a flexible configuration system that combines YAML files with environment variable overrides for deployment flexibility.

## Configuration File Location

The default configuration is loaded from `config/default.yaml`. You can specify a custom configuration file when initializing the application.

## Configuration Sections

### API Configuration

Controls settings related to the Gemini API usage and rate limiting.

```yaml
api:
  timeout: 300                    # API request timeout in seconds
  retry:
    max_attempts: 2               # Maximum retry attempts (recommended: 2 to preserve quota)
    backoff_multiplier: 2         # Exponential backoff multiplier
    max_backoff: 30              # Maximum backoff time in seconds
  quota:
    max_episodes_per_day: 12      # Maximum episodes to process per day
    max_requests_per_key: 25      # Maximum API requests per key per day
    max_tokens_per_key: 1000000   # Maximum tokens per key per day
```

**Environment Variable Overrides:**
- `PODCAST_API_TIMEOUT` - Override API timeout
- `PODCAST_API_MAX_ATTEMPTS` - Override max retry attempts
- `PODCAST_API_MAX_EPISODES` - Override max episodes per day

### Processing Configuration

Controls how episodes are processed and tracked.

```yaml
processing:
  parallel_workers: 1             # Number of parallel workers (recommended: 1 due to rate limits)
  enable_progress_bar: true       # Show progress bar in CLI
  checkpoint_enabled: true        # Enable checkpoint/resume functionality
  max_episode_length: 60          # Maximum episode length in minutes
```

**Environment Variable Overrides:**
- `PODCAST_MAX_EPISODE_LENGTH` - Override max episode length
- `PODCAST_ENABLE_PROGRESS` - Override progress bar setting (true/false)

### Output Configuration

Controls output file generation and formatting.

```yaml
output:
  default_dir: "data/transcripts"          # Default output directory
  naming:
    pattern: "{podcast_name}/{date}_{episode_title}.vtt"  # File naming pattern
    sanitize_filenames: true               # Remove special characters from filenames
    max_filename_length: 200               # Maximum filename length
  vtt:
    include_metadata: true                 # Include episode metadata in VTT files
    speaker_voice_tags: true               # Use voice tags for speakers
    timestamp_precision: 3                 # Decimal places for timestamps (0-3)
```

**File Naming Pattern Variables:**
- `{podcast_name}` - Sanitized podcast name
- `{date}` - Episode publication date (YYYY-MM-DD)
- `{episode_title}` - Sanitized episode title

**Environment Variable Overrides:**
- `PODCAST_OUTPUT_DIR` - Override default output directory
- `PODCAST_OUTPUT_PATTERN` - Override file naming pattern

### Logging Configuration

Controls application logging behavior.

```yaml
logging:
  console_level: "INFO"           # Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  file_level: "DEBUG"             # File log level
  max_file_size_mb: 10           # Maximum log file size in MB
  backup_count: 5                # Number of backup log files to keep
  log_dir: "logs"                # Log file directory
```

**Environment Variable Overrides:**
- `PODCAST_LOG_LEVEL` - Override console log level
- `PODCAST_LOG_DIR` - Override log directory

### Security Configuration

Controls API key management and rotation.

```yaml
security:
  api_key_vars:                   # Environment variable names for API keys
    - "GEMINI_API_KEY_1"
    - "GEMINI_API_KEY_2"
  rotation:
    strategy: "round_robin"       # Key rotation strategy (round_robin, random)
    fail_over_enabled: true       # Enable automatic failover between keys
```

**Required Environment Variables:**
- `GEMINI_API_KEY_1` - Primary Gemini API key
- `GEMINI_API_KEY_2` - Secondary Gemini API key (optional but recommended)

### Development Configuration

Controls development and debugging features.

```yaml
development:
  dry_run: false                  # Enable dry run mode (no actual API calls)
  debug_mode: false               # Enable debug mode
  save_raw_responses: false       # Save raw API responses for debugging
  test_mode: false                # Enable test mode
  mock_api_calls: false           # Use mock API responses
```

**Environment Variable Overrides:**
- `PODCAST_DRY_RUN` - Override dry run mode (true/false)
- `PODCAST_DEBUG_MODE` - Override debug mode (true/false)

## Environment Variable Override Pattern

Environment variables follow the pattern `PODCAST_<SECTION>_<SETTING>`:

- `PODCAST_` - Prefix for all configuration overrides
- `<SECTION>` - Configuration section (API, OUTPUT, etc.)
- `<SETTING>` - Specific setting name

## Configuration Validation

The configuration system automatically validates all settings on startup:

- **API Settings**: Validates timeouts, retry limits, and quota values
- **Processing Settings**: Validates episode length and worker counts
- **Output Settings**: Validates directory paths and naming patterns
- **Logging Settings**: Validates log levels and file settings
- **Security Settings**: Validates API key availability and rotation strategy

Invalid configurations will prevent the application from starting with detailed error messages.

## Usage Examples

### Loading Configuration in Python

```python
from src.config import get_config

# Load default configuration
config = get_config()

# Load custom configuration file
config = get_config('path/to/custom/config.yaml')

# Access configuration values
timeout = config.api.timeout
output_dir = config.output.default_dir
api_keys = config.get_api_keys()
```

### Environment Variable Examples

```bash
# Override API timeout
export PODCAST_API_TIMEOUT=600

# Override output directory
export PODCAST_OUTPUT_DIR="/custom/output/path"

# Enable dry run mode
export PODCAST_DRY_RUN=true

# Set API keys
export GEMINI_API_KEY_1="your-primary-api-key"
export GEMINI_API_KEY_2="your-secondary-api-key"
```

### Docker Environment File

```bash
# .env file for Docker deployment
PODCAST_API_TIMEOUT=600
PODCAST_OUTPUT_DIR=/app/data/transcripts
PODCAST_LOG_LEVEL=INFO
GEMINI_API_KEY_1=your-primary-api-key
GEMINI_API_KEY_2=your-secondary-api-key
```

## Best Practices

1. **API Keys**: Always use multiple API keys to increase daily quota
2. **Rate Limiting**: Keep `max_attempts` low (2) to preserve daily quota
3. **Episode Length**: Stay within 60 minutes for reliable processing
4. **Output Directory**: Use absolute paths in production
5. **Logging**: Use INFO level for production, DEBUG for development
6. **Environment Variables**: Use environment variables for sensitive data and deployment-specific settings

## Troubleshooting

### Common Configuration Errors

1. **"No API keys found"**: Ensure environment variables are set correctly
2. **"API timeout must be positive"**: Check timeout values in configuration
3. **"Invalid log level"**: Use valid log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
4. **"Output directory cannot be empty"**: Ensure output directory is specified

### Validation Debugging

Enable debug mode to see detailed configuration loading and validation:

```bash
export PODCAST_DEBUG_MODE=true
```

This will log all configuration loading steps and validation results.