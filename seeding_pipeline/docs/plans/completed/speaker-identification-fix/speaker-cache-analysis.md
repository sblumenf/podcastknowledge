# Speaker Cache Analysis

## Cache Contamination Issue Confirmed

### Current Cache Contents
The speaker cache file `speaker_cache/c80072dcf8b3.json` contains:
- **Mel Robbins (Host)** - Correctly identified
- **Jake Shane (Comedian/Guest)** - Guest from one episode
- **Dr. Judith Joseph (Psychiatrist/Guest Expert)** - Guest from another episode  
- **Dr. Ashwini Nadkarni (Psychiatrist/Guest Expert)** - Guest from another episode

### The Problem
1. **Persistent Cache**: The cache persists across all episodes of "The Mel Robbins Podcast"
2. **Guest Contamination**: All 3 guests are applied to EVERY episode, even episodes where they don't appear
3. **High Confidence**: Confidence scores (0.9-1.0) ensure cached speakers are always used
4. **No Episode Context**: Cache doesn't distinguish between different episodes

### How It Works
1. First episode identifies its speakers and caches them
2. Second episode checks cache, finds 4 speakers with high confidence
3. Cache matching logic assumes these speakers might be in new episode
4. All subsequent episodes get the same 4 speakers assigned

### Cache Location & Structure
- **Directory**: `./speaker_cache/`
- **File**: Named by hashed podcast name (e.g., `c80072dcf8b3.json`)
- **Structure**: Maps generic speaker IDs to identified names with confidence

### Solution Required
Make the cache episode-specific rather than podcast-wide to prevent guest contamination between episodes.