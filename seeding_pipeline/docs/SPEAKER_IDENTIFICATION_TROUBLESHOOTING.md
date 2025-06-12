# Speaker Identification Troubleshooting Guide

This guide helps diagnose and resolve common issues with the speaker identification system.

## Quick Diagnostics

Run this diagnostic script to check system health:

```python
from src.extraction.speaker_identifier import SpeakerIdentifier
from src.vtt.vtt_segmentation import VTTSegmenter

def diagnose_speaker_identification(segmenter):
    """Run diagnostic checks on speaker identification system."""
    
    if not segmenter._speaker_identifier:
        print("❌ Speaker identifier not initialized")
        return
        
    identifier = segmenter._speaker_identifier
    
    # Check feature flag
    from src.core.feature_flags import is_enabled, FeatureFlag
    if not is_enabled(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION):
        print("❌ Speaker identification is disabled via feature flag")
        return
    
    print("✅ Speaker identification is enabled")
    
    # Check metrics
    metrics = identifier.get_performance_metrics()
    
    # Cache performance
    cache_stats = metrics['cache_stats']
    cache_hit_rate = cache_stats['cache_hit_rate']
    
    if cache_hit_rate < 0.5:
        print(f"⚠️  Low cache hit rate: {cache_hit_rate:.1%}")
    else:
        print(f"✅ Good cache hit rate: {cache_hit_rate:.1%}")
    
    # Error rates
    error_stats = metrics['error_stats']
    if error_stats['total_errors'] > 0:
        print(f"⚠️  Errors detected: {error_stats['error_counts']}")
        
        timeout_rate = error_stats['timeout_rate']
        if timeout_rate > 0.1:
            print(f"   - High timeout rate: {timeout_rate:.1%}")
            
        parse_rate = error_stats['parse_error_rate']
        if parse_rate > 0.05:
            print(f"   - High parse error rate: {parse_rate:.1%}")
    else:
        print("✅ No errors detected")
    
    # Speaker metrics
    speaker_metrics = metrics['speaker_metrics']['overview']
    success_rate = speaker_metrics['success_rate']
    
    if success_rate < 0.8:
        print(f"⚠️  Low success rate: {success_rate:.1%}")
    else:
        print(f"✅ Good success rate: {success_rate:.1%}")
    
    # Database stats
    db_stats = cache_stats['database_stats']
    print(f"\n📊 Database Statistics:")
    print(f"   - Podcasts cached: {db_stats['podcasts_cached']}")
    print(f"   - Total speakers: {db_stats['total_speakers']}")
    print(f"   - Average confidence: {db_stats['average_confidence']:.2f}")
```

## Common Issues and Solutions

### 1. No Speaker Names Identified

**Symptoms:**
- All speakers remain as "Speaker 0", "Speaker 1", etc.
- No speaker_identification in metadata

**Diagnostic Steps:**
```python
# Check if feature is enabled
from src.core.feature_flags import is_enabled, FeatureFlag
print(f"Feature enabled: {is_enabled(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION)}")

# Check if LLM service is provided
if segmenter.llm_service is None:
    print("❌ No LLM service configured")
```

**Solutions:**
1. Enable the feature flag:
   ```bash
   export FF_ENABLE_SPEAKER_IDENTIFICATION=true
   ```

2. Provide LLM service to VTTSegmenter:
   ```python
   segmenter = VTTSegmenter(config=config, llm_service=gemini_service)
   ```

### 2. Low Confidence Scores

**Symptoms:**
- Most speakers get descriptive roles like "Primary Speaker (Speaker 0)"
- High number of unresolved_speakers

**Example Debug:**
```python
# Analyze confidence scores
result = identifier.identify_speakers(segments, metadata)
for speaker, score in result['confidence_scores'].items():
    print(f"{speaker}: {score:.2f}")
    
# Check identification methods
for speaker, method in result['identification_methods'].items():
    print(f"{speaker}: {method}")
```

**Solutions:**
1. Lower confidence threshold:
   ```python
   config['speaker_confidence_threshold'] = 0.5  # Default is 0.7
   ```

2. Improve metadata quality:
   ```python
   metadata = {
       'podcast_name': 'The Full Podcast Name',
       'episode_title': 'Episode with Guest Dr. Jane Smith',
       'description': 'Interview with AI researcher Dr. Jane Smith about...'
   }
   ```

3. Check transcript quality for clear introductions

### 3. Timeouts

**Symptoms:**
- "LLM call timed out after 30s" errors
- Frequent fallback to descriptive roles

**Debug Script:**
```python
import time

# Time a sample identification
start = time.time()
result = identifier.identify_speakers(segments[:10], metadata)  # Test with fewer segments
duration = time.time() - start

print(f"Identification took {duration:.1f}s")
if duration > 20:
    print("⚠️  Consider reducing context size or increasing timeout")
```

**Solutions:**
1. Increase timeout:
   ```python
   config['speaker_timeout_seconds'] = 60  # Default is 30
   ```

2. Reduce context size:
   ```python
   config['max_segments_for_context'] = 25  # Default is 50
   ```

3. Check LLM service performance:
   ```python
   # Test LLM directly
   start = time.time()
   response = llm_service.complete("Test prompt")
   print(f"LLM response time: {time.time() - start:.1f}s")
   ```

### 4. Inconsistent Speaker Identification

**Symptoms:**
- Same podcast identifies speakers differently across episodes
- Cache not working effectively

**Debug Cache:**
```python
# Check cache for specific podcast
speakers = identifier.speaker_db.get_known_speakers('Your Podcast Name')
print(f"Cached speakers: {speakers}")

# Check cache key generation
key = identifier.speaker_db._get_podcast_key('Your Podcast Name')
print(f"Cache key: {key}")

# Verify cache persistence
cache_dir = Path(config['speaker_db_path'])
cache_files = list(cache_dir.glob("*.json"))
print(f"Cache files: {len(cache_files)}")
```

**Solutions:**
1. Ensure consistent podcast naming:
   ```python
   # Always use the same podcast name format
   metadata['podcast_name'] = 'The Official Podcast Name'
   ```

2. Check cache directory permissions:
   ```bash
   ls -la ./speaker_cache/
   # Should be writable by the process
   ```

3. Manually seed cache for important podcasts:
   ```python
   identifier.speaker_db.store_speakers(
       'Your Podcast',
       {'Speaker 0': 'John Smith (Host)', 'Speaker 1': 'Regular Co-host Jane'},
       {'Speaker 0': 0.95, 'Speaker 1': 0.9}
   )
   ```

### 5. High LLM Costs

**Symptoms:**
- Low cache hit rate
- Many LLM calls for same podcasts

**Cost Analysis:**
```python
# Get cost metrics
metrics = identifier.get_performance_metrics()
speaker_metrics = metrics['speaker_metrics']

total_llm_calls = speaker_metrics['llm_performance']['total_llm_calls']
cache_hits = speaker_metrics['cache_performance']['cache_hits']
saved_calls = speaker_metrics['cache_performance']['llm_calls_saved']

print(f"Total LLM calls: {total_llm_calls}")
print(f"Calls saved by cache: {saved_calls}")
print(f"Estimated savings: ${saved_calls * 0.01:.2f}")  # Adjust rate as needed
```

**Solutions:**
1. Improve cache hit rate:
   - Use consistent podcast naming
   - Increase cache TTL if appropriate
   - Pre-warm cache for frequent podcasts

2. Batch processing:
   ```python
   # Process multiple episodes of same podcast together
   for episode in episodes:
       result = segmenter.process_segments(
           episode.segments,
           {'podcast_name': 'Same Podcast Name'}  # Consistent naming
       )
   ```

### 6. Parse Errors

**Symptoms:**
- "Failed to parse LLM response" errors
- Empty speaker_mappings despite LLM call

**Debug LLM Response:**
```python
# Enable debug logging
import logging
logging.getLogger('src.extraction.speaker_identifier').setLevel(logging.DEBUG)

# Or manually check LLM response
import json

# Mock the complete method to see raw response
original_complete = identifier.llm_service.complete
def debug_complete(*args, **kwargs):
    response = original_complete(*args, **kwargs)
    print(f"Raw LLM response:\n{response}")
    try:
        parsed = json.loads(response)
        print(f"Parsed successfully: {list(parsed.keys())}")
    except json.JSONDecodeError as e:
        print(f"Parse error: {e}")
    return response

identifier.llm_service.complete = debug_complete
```

**Solutions:**
1. Update prompt template to emphasize JSON format
2. Check for LLM model changes that affect output format
3. Add response cleaning logic if needed

## Performance Optimization

### Analyze Performance Bottlenecks

```python
def analyze_performance(identifier):
    """Analyze performance characteristics."""
    metrics = identifier.get_performance_metrics()
    
    # Response time analysis
    response_times = metrics['speaker_metrics']['response_times']
    avg_time = response_times['avg_response_time_ms']
    p95_time = response_times['p95_response_time_ms']
    
    print(f"Average response time: {avg_time:.0f}ms")
    print(f"P95 response time: {p95_time:.0f}ms")
    
    if p95_time > 2000:
        print("⚠️  High P95 latency detected")
        
        # Check cache effectiveness
        cache_hit_rate = metrics['cache_stats']['cache_hit_rate']
        if cache_hit_rate < 0.7:
            print("   → Improve cache hit rate")
        
        # Check context size
        config = metrics['config']
        if config['max_segments_for_context'] > 30:
            print("   → Consider reducing context size")
```

### Optimize for Specific Use Cases

**High-Volume Processing:**
```python
# Batch process with shared cache
identifier = SpeakerIdentifier(
    llm_service=llm_service,
    speaker_db_path='./shared_cache',
    timeout_seconds=45,
    max_segments_for_context=30
)

# Pre-warm cache for known podcasts
for podcast in frequent_podcasts:
    identifier.speaker_db.get_known_speakers(podcast)
```

**Real-time Processing:**
```python
# Optimize for speed
identifier = SpeakerIdentifier(
    llm_service=llm_service,
    timeout_seconds=15,
    max_segments_for_context=20,
    confidence_threshold=0.6  # Accept more identifications
)
```

**High-Accuracy Requirements:**
```python
# Optimize for accuracy
identifier = SpeakerIdentifier(
    llm_service=llm_service,
    confidence_threshold=0.85,
    max_segments_for_context=100,  # More context
    timeout_seconds=60
)
```

## Monitoring Best Practices

### Set Up Alerts

```python
def check_health_metrics(identifier, alert_thresholds):
    """Check metrics against thresholds and alert if needed."""
    metrics = identifier.get_performance_metrics()
    alerts = []
    
    # Success rate
    success_rate = metrics['speaker_metrics']['overview']['success_rate']
    if success_rate < alert_thresholds['min_success_rate']:
        alerts.append(f"Low success rate: {success_rate:.1%}")
    
    # Error rate
    error_stats = metrics['error_stats']
    error_rate = error_stats['total_errors'] / max(1, metrics['speaker_metrics']['overview']['total_identifications'])
    if error_rate > alert_thresholds['max_error_rate']:
        alerts.append(f"High error rate: {error_rate:.1%}")
    
    # Cache performance
    cache_hit_rate = metrics['cache_stats']['cache_hit_rate']
    if cache_hit_rate < alert_thresholds['min_cache_hit_rate']:
        alerts.append(f"Low cache hit rate: {cache_hit_rate:.1%}")
    
    return alerts

# Example thresholds
thresholds = {
    'min_success_rate': 0.8,
    'max_error_rate': 0.1,
    'min_cache_hit_rate': 0.6
}
```

### Regular Health Checks

```python
# Daily health check script
def daily_health_check(identifier):
    """Run daily health check and generate report."""
    
    # Generate metrics report
    report_path = f"./reports/speaker_metrics_{datetime.now():%Y%m%d}.md"
    identifier.generate_metrics_report(report_path)
    
    # Check for issues
    alerts = check_health_metrics(identifier, thresholds)
    
    if alerts:
        print("⚠️  Health check alerts:")
        for alert in alerts:
            print(f"   - {alert}")
    else:
        print("✅ All health checks passed")
    
    # Clean old cache entries
    identifier.speaker_db.clear_cache()  # Implement cache cleanup
    
    # Reset error counters for new period
    identifier.reset_error_statistics()
```

## Emergency Procedures

### Disable Speaker Identification

If the system is causing issues:

```bash
# Disable via environment variable
export FF_ENABLE_SPEAKER_IDENTIFICATION=false

# Or in code
from src.core.feature_flags import set_flag, FeatureFlag
set_flag(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION, False)
```

### Clear Corrupted Cache

```python
# Clear all cached data
identifier.speaker_db.clear_cache()

# Or manually
import shutil
shutil.rmtree('./speaker_cache')
```

### Fallback Processing

```python
# Process without speaker identification
segmenter = VTTSegmenter(config=config)  # No llm_service
result = segmenter.process_segments(segments)
# Will use original speaker labels
```