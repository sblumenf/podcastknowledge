# YouTube URL Search Strategies for Podcast Episodes

## Overview

This document outlines practical approaches for finding YouTube URLs for podcast episodes when they're not included in the RSS feed. We'll explore various methods, their requirements, limitations, and implementation strategies.

## 1. YouTube Data API v3

### Overview
The official API provided by Google for accessing YouTube content programmatically.

### Requirements
- Google Account and Google Cloud project
- API key or OAuth 2.0 credentials
- Enable YouTube Data API v3 in Google Cloud Console

### Rate Limits
- **Default quota**: 10,000 units per day
- **Search cost**: 100 units per search query
- **Daily search limit**: ~100 searches with default quota
- **Quota reset**: Every 24 hours at midnight Pacific Time

### Implementation Approach
```python
# Pseudo-code example
def search_youtube_api(podcast_name, episode_title):
    query = f"{podcast_name} {episode_title}"
    # Use search.list() endpoint
    # Cost: 100 quota units
    return video_results
```

### Pros
- Official, reliable API
- Comprehensive metadata
- Good search accuracy
- No risk of IP blocking

### Cons
- Limited daily quota (100 searches/day by default)
- Requires API setup and authentication
- Additional quota requires audit process

## 2. yt-dlp Library

### Overview
Open-source Python library that can search and extract YouTube content without using the official API.

### Requirements
- Python 3.7+
- yt-dlp package (`pip install yt-dlp`)
- FFmpeg (for audio extraction)

### Implementation Example
```python
import yt_dlp

def search_with_ytdlp(query, max_results=5):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_query = f"ytsearch{max_results}:{query}"
        result = ydl.extract_info(search_query, download=False)
        
        videos = []
        for entry in result['entries']:
            videos.append({
                'title': entry.get('title'),
                'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                'duration': entry.get('duration'),
                'uploader': entry.get('uploader')
            })
        
        return videos
```

### Pros
- No API quota limitations
- No authentication required
- Can extract additional metadata
- Actively maintained

### Cons
- May break if YouTube changes their structure
- Slower than API for large-scale operations
- Potential rate limiting by YouTube

## 3. Web Scraping with Selenium

### Overview
Use browser automation to search YouTube and extract results from the rendered page.

### Requirements
- Selenium WebDriver
- Chrome/Firefox driver
- Optional: Proxy rotation for scale

### Pros
- Handles JavaScript-rendered content
- Can simulate human behavior
- No API limitations

### Cons
- Resource intensive
- Slower performance
- Higher complexity
- Risk of IP blocking at scale

## 4. Third-Party APIs

### Podchaser API
- Comprehensive podcast database
- May include YouTube URLs for some podcasts
- Requires subscription for full access

### Spotify Podcast API
- Can cross-reference podcast metadata
- Useful for validation but doesn't provide YouTube URLs

### Commercial Scraping Services
- Apify, ScrapingDog, Oxylabs
- Higher reliability and scale
- Cost per request

## 5. Search Strategies

### Basic Search Query Construction
```python
def build_search_query(podcast_name, episode_title, episode_number=None):
    # Remove common words that might confuse search
    clean_title = episode_title.replace("Episode", "").replace("Ep.", "")
    
    # Build query variations
    queries = [
        f"{podcast_name} {clean_title}",
        f"{podcast_name} episode {episode_number}" if episode_number else None,
        f"{podcast_name} {clean_title[:50]}"  # Truncate long titles
    ]
    
    return [q for q in queries if q]
```

### Fuzzy Matching for Result Validation

Using RapidFuzz (faster alternative to FuzzyWuzzy):

```python
from rapidfuzz import fuzz
from rapidfuzz import process

def match_episode(search_results, expected_title, threshold=85):
    titles = [r['title'] for r in search_results]
    
    # Try different matching strategies
    strategies = [
        fuzz.ratio,
        fuzz.partial_ratio,
        fuzz.token_sort_ratio,
        fuzz.token_set_ratio
    ]
    
    best_match = None
    best_score = 0
    
    for strategy in strategies:
        match = process.extractOne(expected_title, titles, scorer=strategy)
        if match and match[1] > best_score:
            best_score = match[1]
            best_match = match[0]
    
    if best_score >= threshold:
        # Return the video URL for the best match
        for result in search_results:
            if result['title'] == best_match:
                return result['url']
    
    return None
```

### Matching Accuracy Techniques

1. **Preprocessing**
   - Convert to lowercase
   - Remove punctuation
   - Normalize whitespace
   - Remove common prefixes/suffixes

2. **Multiple Search Attempts**
   - Try different query variations
   - Use episode number if available
   - Try partial title matches

3. **Validation Checks**
   - Duration comparison (if available)
   - Upload date proximity
   - Channel name verification
   - Description content matching

## 6. Fallback Strategy Implementation

```python
class YouTubeURLFinder:
    def __init__(self):
        self.methods = [
            self._search_youtube_api,
            self._search_ytdlp,
            self._search_cached_results,
            self._manual_search_prompt
        ]
    
    def find_episode_url(self, podcast_name, episode_data):
        for method in self.methods:
            try:
                url = method(podcast_name, episode_data)
                if url and self._validate_url(url, episode_data):
                    return url
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        return None
    
    def _validate_url(self, url, episode_data):
        # Implement validation logic
        # Check duration, title match, upload date, etc.
        pass
```

## 7. Caching Strategy

Implement a caching layer to avoid repeated searches:

```python
import hashlib
from datetime import datetime, timedelta

class SearchCache:
    def __init__(self, cache_duration_days=30):
        self.cache = {}  # In production, use Redis or similar
        self.duration = timedelta(days=cache_duration_days)
    
    def get_cache_key(self, podcast_name, episode_title):
        content = f"{podcast_name}:{episode_title}".lower()
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, podcast_name, episode_title):
        key = self.get_cache_key(podcast_name, episode_title)
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry['timestamp'] < self.duration:
                return entry['url']
        return None
    
    def set(self, podcast_name, episode_title, url):
        key = self.get_cache_key(podcast_name, episode_title)
        self.cache[key] = {
            'url': url,
            'timestamp': datetime.now()
        }
```

## 8. Best Practices

### Rate Limiting
- Implement exponential backoff
- Add random delays between requests
- Respect robots.txt
- Monitor for rate limit responses

### Error Handling
- Graceful degradation through fallback methods
- Log failed searches for manual review
- Implement retry logic with backoff

### Monitoring
- Track success rates per method
- Monitor API quota usage
- Alert on repeated failures

## 9. Recommended Implementation

For a production podcast transcription system, we recommend:

1. **Primary Method**: yt-dlp for flexibility and no quota limits
2. **Secondary Method**: YouTube Data API for difficult cases
3. **Caching**: Implement aggressive caching to minimize searches
4. **Validation**: Use fuzzy matching with 85%+ threshold
5. **Fallback**: Manual search queue for failed matches

## 10. Legal and Ethical Considerations

- Respect YouTube's Terms of Service
- Don't circumvent ads or monetization
- Cache results to minimize requests
- Consider podcast creator preferences
- Implement user-agent and attribution

## Conclusion

The optimal approach combines multiple methods with intelligent fallbacks. Start with yt-dlp for most searches, fall back to the official API for difficult cases, and maintain a cache to minimize repeated searches. Implement robust validation using fuzzy matching to ensure accuracy.