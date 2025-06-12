# YouTube Episode Matcher API Documentation

## Overview

The YouTube Episode Matcher is a sophisticated system for automatically finding YouTube videos that correspond to podcast episodes. It uses the YouTube Data API v3 to search for and validate matches based on multiple criteria.

## Core Components

### YouTubeEpisodeMatcher

The main orchestrator class that coordinates the matching process.

```python
from src.youtube_episode_matcher import YouTubeEpisodeMatcher
from src.config import Config

config = Config()
matcher = YouTubeEpisodeMatcher(config)
```

#### Methods

##### `match_episode()`

Finds YouTube URL for a podcast episode.

```python
async def match_episode(
    podcast_name: str,
    episode_title: str,
    episode_guid: Optional[str] = None,
    episode_number: Optional[int] = None,
    episode_duration: Optional[int] = None,
    episode_date: Optional[datetime] = None
) -> Optional[str]
```

**Parameters:**
- `podcast_name` (str): Name of the podcast
- `episode_title` (str): Title of the episode
- `episode_guid` (str, optional): Unique episode identifier
- `episode_number` (int, optional): Episode number if available
- `episode_duration` (int, optional): Duration in seconds
- `episode_date` (datetime, optional): Publication date

**Returns:**
- `str`: YouTube URL if confident match found
- `None`: If no match meets confidence threshold

**Raises:**
- `YouTubeAPIError`: If API errors occur
- `QuotaExceededError`: If daily quota is exceeded

**Example:**
```python
youtube_url = await matcher.match_episode(
    podcast_name="The Tim Ferriss Show",
    episode_title="Episode 123: Dr. Jane Smith on Longevity",
    episode_duration=7200,
    episode_date=datetime(2024, 1, 15)
)
```

##### `get_metrics()`

Get current metrics and statistics.

```python
def get_metrics() -> Dict[str, Any]
```

**Returns:**
```python
{
    'searches_performed': 150,
    'matches_found': 120,
    'matches_above_threshold': 110,
    'quota_used': 15000,
    'cache_hits': 45,
    'average_confidence': 0.92,
    'total_episodes': 125,
    'quota_status': {...},
    'known_podcast_channels': 25,
    'success_rate': 0.88
}
```

##### `clear_channel_cache()`

Clear the channel associations cache.

```python
def clear_channel_cache() -> None
```

### YouTubeAPIClient

Handles communication with YouTube Data API v3.

```python
from src.youtube_api_client import YouTubeAPIClient

client = YouTubeAPIClient(api_key="your-api-key")
```

#### Methods

##### `search_videos()`

Search for videos on YouTube.

```python
def search_videos(
    query: str,
    max_results: int = 10,
    order: str = 'relevance',
    published_after: Optional[datetime] = None,
    channel_id: Optional[str] = None
) -> List[Dict[str, Any]]
```

**Parameters:**
- `query` (str): Search query string
- `max_results` (int): Maximum results to return (default: 10, max: 50)
- `order` (str): Sort order - 'relevance', 'date', 'rating', 'title', 'viewCount'
- `published_after` (datetime, optional): Only return videos after this date
- `channel_id` (str, optional): Restrict search to specific channel

**Returns:**
```python
[
    {
        'video_id': 'abc123',
        'title': 'Episode Title',
        'channel_id': 'channel123',
        'channel_title': 'Channel Name',
        'published_at': '2024-01-15T10:00:00Z',
        'description': 'Episode description',
        'thumbnail_url': 'https://...'
    }
]
```

##### `get_video_details()`

Get detailed information for videos.

```python
def get_video_details(video_ids: List[str]) -> List[Dict[str, Any]]
```

**Parameters:**
- `video_ids` (List[str]): List of video IDs (max 50 per request)

**Returns:**
```python
[
    {
        'video_id': 'abc123',
        'duration_seconds': 3600,
        'view_count': 10000,
        'like_count': 500,
        'comment_count': 100
    }
]
```

##### `get_quota_status()`

Get current quota usage status.

```python
def get_quota_status() -> Dict[str, Any]
```

**Returns:**
```python
{
    'used': 5000,
    'limit': 10000,
    'remaining': 5000,
    'reset_time': '2024-01-16T08:00:00Z',
    'hours_until_reset': 12.5
}
```

### QueryBuilder

Generates search query variations.

```python
from src.youtube_query_builder import QueryBuilder

builder = QueryBuilder()
queries = builder.build_queries(
    podcast_name="My Podcast",
    episode_title="Episode 123: Great Interview"
)
```

#### Methods

##### `build_queries()`

Build multiple search query variations ranked by expected accuracy.

```python
def build_queries(
    podcast_name: str,
    episode_title: str,
    episode_number: Optional[int] = None
) -> List[Tuple[str, int]]
```

**Returns:**
```python
[
    ('"My Podcast" "Episode 123: Great Interview"', 1),  # Exact match
    ('"My Podcast" (episode 123 OR ep 123 OR #123)', 2),  # Episode number
    ('"My Podcast" "Guest Name"', 3),  # Guest name
    ('"My Podcast" great interview', 4),  # Fuzzy match
]
```

### MatchScorer

Scores and ranks search results.

```python
from src.youtube_match_scorer import MatchScorer

scorer = MatchScorer(duration_tolerance=0.10)
scored_results = scorer.score_results(results, episode_title, podcast_name)
```

#### Scoring Factors

1. **Title Similarity (40%)**: How closely the video title matches the episode title
2. **Duration Match (30%)**: How close the video duration is to expected duration
3. **Channel Verification (20%)**: Whether the channel is known or matches podcast name
4. **Upload Date Proximity (10%)**: How close the upload date is to publication date

## Configuration

### Required Settings

```yaml
youtube_api:
  api_key: "your-youtube-api-key"  # Required
  confidence_threshold: 0.90        # Default: 0.90
  max_results_per_search: 10        # Default: 10
  search_quota_per_episode: 500     # Default: 500 units
```

### Environment Variables

```bash
# YouTube API key (required)
YOUTUBE_API_KEY=your-youtube-api-key

# Confidence threshold (optional)
YOUTUBE_CONFIDENCE_THRESHOLD=0.90
```

## Error Handling

### Exception Types

- `YouTubeAPIError`: Base exception for YouTube API errors
- `QuotaExceededError`: Raised when daily quota (10,000 units) is exceeded
- `NoConfidentMatchError`: Raised when no match meets confidence threshold

### Error Recovery

The system automatically:
- Retries failed requests with exponential backoff
- Falls back to broader searches when initial attempts fail
- Gracefully handles missing or invalid data
- Logs detailed error information for debugging

## Integration Example

```python
import asyncio
from datetime import datetime
from src.youtube_episode_matcher import YouTubeEpisodeMatcher
from src.config import Config

async def find_youtube_urls_for_podcast(feed_url: str):
    """Find YouTube URLs for all episodes in a podcast feed."""
    config = Config()
    matcher = YouTubeEpisodeMatcher(config)
    
    # Parse podcast feed (example)
    episodes = parse_podcast_feed(feed_url)
    
    results = []
    for episode in episodes:
        try:
            youtube_url = await matcher.match_episode(
                podcast_name=episode['podcast_name'],
                episode_title=episode['title'],
                episode_duration=episode['duration'],
                episode_date=episode['published_date']
            )
            
            if youtube_url:
                results.append({
                    'episode': episode['title'],
                    'youtube_url': youtube_url
                })
                print(f"Found: {episode['title']} -> {youtube_url}")
            else:
                print(f"No match: {episode['title']}")
                
        except QuotaExceededError:
            print("Daily quota exceeded, stopping...")
            break
        except Exception as e:
            print(f"Error processing {episode['title']}: {e}")
            
    # Print metrics
    metrics = matcher.get_metrics()
    print(f"\nProcessed {metrics['total_episodes']} episodes")
    print(f"Success rate: {metrics['success_rate']:.1%}")
    print(f"Quota used: {metrics['quota_used']} / 10000")
    
    return results

# Run the example
asyncio.run(find_youtube_urls_for_podcast("https://example.com/feed.xml"))
```

## Performance Considerations

### API Quota Management

- Each search costs 100 quota units
- Daily limit is 10,000 units (approximately 100 searches)
- Video details requests cost 1 unit per request
- The system tracks quota usage and prevents exceeding limits

### Optimization Tips

1. **Enable Channel Learning**: The system learns channel associations to improve accuracy and reduce searches
2. **Provide Episode Numbers**: Including episode numbers significantly improves matching accuracy
3. **Include Duration**: Duration matching helps eliminate false positives
4. **Batch Processing**: Process episodes sequentially to maximize channel learning benefits

### Performance Metrics

- Average search time: 1-3 seconds per episode
- Cache hit rate: 20-40% after initial learning
- Memory usage: ~50MB for typical operation
- Concurrent processing: Supported but limited by API rate limits

## Troubleshooting

### Common Issues

1. **No matches found**
   - Verify the podcast is available on YouTube
   - Check if episode titles match between podcast and YouTube
   - Try lowering confidence threshold (not recommended below 0.85)

2. **Quota exceeded errors**
   - Wait for quota reset (midnight Pacific Time)
   - Reduce max_results_per_search
   - Process fewer episodes per day

3. **Incorrect matches**
   - Increase confidence threshold
   - Provide episode duration for better validation
   - Clear channel cache if associations are incorrect

### Debug Logging

Enable debug logging for detailed information:

```python
import logging
logging.getLogger('youtube_episode_matcher').setLevel(logging.DEBUG)
logging.getLogger('youtube_api_client').setLevel(logging.DEBUG)
```

## Best Practices

1. **Always Handle Exceptions**: Wrap API calls in try-except blocks
2. **Monitor Quota Usage**: Check quota status regularly
3. **Cache Results**: The system automatically caches results and channel associations
4. **Validate Inputs**: Ensure episode titles and dates are accurate
5. **Test with Known Episodes**: Verify the system works with episodes you know are on YouTube
6. **Regular Maintenance**: Periodically clear old cache entries if needed