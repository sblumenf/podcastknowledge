# Gemini API Caching Research Summary

## Overview
The Google GenAI Python SDK (`google-genai`) provides native caching functionality through the `client.caches` module. This enables efficient reuse of large content pieces like transcripts, reducing API costs significantly.

## Key Findings

### 1. Cache Creation and Management
- **Create Cache**: Use `client.caches.create()` with model, content, system instruction, display name, and TTL
- **Retrieve Cache**: Use `client.caches.get(name=cached_content.name)` to get cache details
- **TTL Configuration**: Set time-to-live using format like `'3600s'` (1 hour)

### 2. Using Cached Content
- Pass cached content name in `GenerateContentConfig` when calling `generate_content()`
- Example:
```python
response = client.models.generate_content(
    model='gemini-2.0-flash-001',
    contents='Summarize the transcript',
    config=types.GenerateContentConfig(
        cached_content=cached_content.name,
    ),
)
```

### 3. Content Types for Caching
- Support for files via URIs (GCS URIs for Vertex AI, local file URIs for Developer API)
- Can cache multiple content parts in a single cache entry
- Support for various MIME types (PDFs, text files, etc.)

### 4. Cache Configuration Best Practices
- **Minimum Token Requirements**: 
  - 1024 tokens for Gemini 2.5 Flash
  - 2048 tokens for Gemini 2.5 Pro
- **Cost Savings**: 75% discount on cached tokens
- **Recommended TTL**: 3600s (1 hour) for transcript processing
- **Cache Key Strategy**: Use episode IDs for cache keys to ensure uniqueness

## Implementation Recommendations

### For Transcript Processing:
1. Cache entire transcript as prefix at episode level
2. Use cached context for all segment extractions within an episode
3. Implement cache warming for frequently used prompt templates
4. Monitor cache hit rates for optimization

### For Prompt Templates:
1. Cache common extraction prompts with longer TTL (24 hours)
2. Warm cache on service startup
3. Version cache keys to handle prompt updates

## Migration Considerations
- The SDK requires replacing LangChain-based implementation
- Direct API calls provide more control over caching behavior
- Need to handle both Vertex AI and Developer API environments
- Integration with existing key rotation manager is supported

## Next Steps
Based on this research, the implementation should:
1. Create a new service using `google-genai` SDK
2. Implement transcript-level caching for episode processing
3. Add prompt template caching for common patterns
4. Monitor and optimize based on cache hit rates