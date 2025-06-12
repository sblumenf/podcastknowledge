# YouTube Search Integration Setup Guide

## Overview

The seeding pipeline now includes optional YouTube search functionality to automatically find YouTube URLs for podcast episodes when they're not included in the VTT metadata.

## Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   The `google-api-python-client` package is required for YouTube search functionality.

2. **YouTube Data API v3 Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable YouTube Data API v3
   - Create credentials (API Key)
   - Note: Free tier provides 10,000 units/day (approximately 100 searches)

## Configuration

### 1. Environment Variables

Set the following environment variables:

```bash
# Required for YouTube search
export YOUTUBE_API_KEY="your-youtube-api-key-here"

# Optional: Control YouTube search behavior
export YOUTUBE_SEARCH_ENABLED="true"  # Enable/disable YouTube search (default: true)
export YOUTUBE_SEARCH_MAX_RESULTS="5"  # Number of results to consider (default: 5)
export YOUTUBE_SEARCH_CONFIDENCE_THRESHOLD="0.7"  # Matching confidence (default: 0.7)
export YOUTUBE_SEARCH_RATE_LIMIT_DELAY="1.0"  # Seconds between API calls (default: 1.0)
```

### 2. Using .env File

Create a `.env` file in the seeding_pipeline directory:

```env
# YouTube Search Configuration
YOUTUBE_API_KEY=your-youtube-api-key-here
YOUTUBE_SEARCH_ENABLED=true

# Other required variables
NEO4J_PASSWORD=your-neo4j-password
GOOGLE_API_KEY=your-google-api-key
```

### 3. Configuration File (config/seeding.yaml)

The YAML configuration is already set up with defaults:

```yaml
youtube_search:
  enabled: true
  max_results: 5
  confidence_threshold: 0.7
  rate_limit_delay: 1.0
```

## How It Works

1. **Automatic Detection**: When processing VTT files, the pipeline checks if a YouTube URL exists in the metadata
2. **Smart Search**: If no URL is found and YouTube search is enabled, it searches using:
   - Podcast name
   - Episode title
   - Optional: Published date
3. **Validation**: Results are validated by checking:
   - Podcast name appears in channel title or video title
   - At least 3 words (or 50%) from episode title match the video title
4. **Rate Limiting**: Automatic 1-second delay between searches to respect API limits

## Usage

### Basic Usage

Process VTT files normally - YouTube search happens automatically:

```python
from src.seeding.transcript_ingestion import TranscriptIngestion
from src.core.config import PipelineConfig

config = PipelineConfig()
ingestion = TranscriptIngestion(config)

# Process a single file
result = ingestion.process_file("path/to/episode.vtt")

# Check if YouTube URL was found
if result['episode']['youtube_url']:
    print(f"Found YouTube URL: {result['episode']['youtube_url']}")
```

### Batch Processing

```python
# Process entire directory
results = ingestion.process_directory(
    directory=Path("./transcripts"),
    pattern="*.vtt",
    recursive=True
)

# Summary of YouTube URLs found
youtube_found = sum(1 for r in results['files'] 
                   if r['status'] == 'success' 
                   and r['episode'].get('youtube_url'))
print(f"Found YouTube URLs for {youtube_found}/{results['processed']} episodes")
```

### Disabling YouTube Search

To disable YouTube search temporarily:

```bash
export YOUTUBE_SEARCH_ENABLED=false
```

Or in code:

```python
config = PipelineConfig()
config.youtube_search_enabled = False
ingestion = TranscriptIngestion(config)
```

## Monitoring and Debugging

### Check Configuration

Run the test script to verify setup:

```bash
python test_youtube_search_integration.py
```

### Log Output

The system logs all YouTube search attempts:

```
INFO: YouTube search enabled for missing URLs
INFO: Searching for YouTube URL for episode: Episode Title Here
INFO: Found YouTube URL via search: https://www.youtube.com/watch?v=xxxxx
```

### Common Issues

1. **Module Import Error**: Install `google-api-python-client`
2. **API Key Invalid**: Check your YouTube Data API key is correct
3. **Quota Exceeded**: YouTube API has daily quotas (10,000 units)
4. **No Results Found**: Episode might not be on YouTube or title mismatch

## API Quotas and Limits

- **Daily Quota**: 10,000 units (default)
- **Search Cost**: 100 units per search
- **Daily Searches**: ~100 searches per day
- **Rate Limit**: 1 request per second (configurable)

## Best Practices

1. **Cache Results**: Consider implementing a local cache to avoid redundant searches
2. **Batch Processing**: Process episodes in batches to track API usage
3. **Error Handling**: The system gracefully handles search failures
4. **Monitoring**: Log and track successful vs failed searches

## Security

- Never commit API keys to version control
- Use environment variables or secure key management
- Rotate API keys periodically
- Monitor usage in Google Cloud Console