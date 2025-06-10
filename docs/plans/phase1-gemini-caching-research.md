# Phase 1: Gemini Caching Research Summary

## Overview

Based on the Google GenAI Python SDK documentation review, Gemini's prompt caching functionality provides significant cost savings through the `client.caches` API. Here are the key findings:

## Caching Mechanics

### 1. Cache Creation
- Use `client.caches.create()` to create cached content
- Specify model, content parts, system instructions, and TTL
- Returns a cached content object with a unique name/ID

### 2. Cache Usage
- Reference cached content via `cached_content` parameter in `GenerateContentConfig`
- Model uses cached data as context for generation
- 75% discount on cached tokens (as mentioned in the plan)

### 3. Cache Management
- Retrieve cache details with `client.caches.get(name=cached_content.name)`
- TTL specified in seconds (e.g., '3600s' for 1 hour)
- Minimum token requirements: 1024 for Flash, 2048 for Pro models

## Best Practices for Transcript Processing

### 1. Episode-Level Caching Strategy
```python
# Create cache for entire transcript
cached_content = client.caches.create(
    model='gemini-2.0-flash-001',  # or gemini-2.5-pro
    config=types.CreateCachedContentConfig(
        contents=[
            types.Content(
                role='user',
                parts=[
                    types.Part.from_text(transcript_text)
                ],
            )
        ],
        system_instruction='You are analyzing podcast transcripts for knowledge extraction...',
        display_name=f'episode_{episode_id}',
        ttl='3600s',  # 1 hour cache
    ),
)
```

### 2. Segment Processing with Cache
```python
# Use cached transcript for segment extraction
response = client.models.generate_content(
    model='gemini-2.0-flash-001',
    contents=segment_specific_prompt,
    config=types.GenerateContentConfig(
        cached_content=cached_content.name,
        max_output_tokens=2000,
        temperature=0.3,
    ),
)
```

### 3. Prompt Template Caching
- Cache frequently used extraction prompts
- Longer TTL (24 hours) for stable prompt templates
- Warm cache on service startup for better performance

## Token Limits and Recommendations

1. **Cache Size Requirements**:
   - Minimum 1024 tokens for Gemini 2.5 Flash
   - Minimum 2048 tokens for Gemini 2.5 Pro
   - Most podcast transcripts exceed these minimums

2. **TTL Recommendations**:
   - Episode transcripts: 3600s (1 hour) - enough for processing all segments
   - Prompt templates: 86400s (24 hours) - stable, reusable content

3. **Cost Optimization**:
   - Prioritize caching for transcripts >5000 tokens
   - Batch segment processing to maximize cache utilization
   - Monitor cache hit rates for optimization

## Implementation Notes

1. **Direct API Benefits**:
   - Simpler codebase without LangChain abstraction
   - Direct control over caching parameters
   - Better error handling and metrics collection

2. **Migration Path**:
   - Implement alongside existing LangChain service
   - Use feature flag for gradual rollout
   - Monitor performance and cost metrics

3. **Error Handling**:
   - Cache creation may fail if content is too small
   - Implement fallback to non-cached generation
   - Log cache hit/miss rates for monitoring

## Next Steps

With this research complete, we can proceed to Phase 1 Task 1.2 to analyze current transcript processing patterns and calculate potential cost savings based on actual usage data.