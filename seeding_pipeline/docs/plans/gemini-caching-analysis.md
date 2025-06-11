# Gemini Caching Infrastructure Analysis

## Current Implementation

### 1. **GeminiDirectService** (`llm_gemini_direct.py`)
- Uses native Google GenAI SDK with prompt caching support
- Key features:
  - TTL-based cache management (default 3600s)
  - Response caching with `_response_cache`
  - Context caching with `_context_cache`
  - Episode-level cache support via `create_cached_content()`

### 2. **Cache Manager** (`cache_manager.py`)
- Manages both transcript and prompt caches
- Features:
  - Minimum token requirements: 1024 for Flash, 2048 for Pro
  - Token estimation for cache eligibility
  - Warm cache support on startup
  - 75% cost savings on cached tokens

### 3. **CachedPromptService** (`cached_prompt_service.py`)
- Service layer for using cached prompts
- Cacheable prompts:
  - entity_extraction_large/small
  - insight_extraction_large/small
  - quote_extraction_large
  - complexity_analysis
  - information_density

## Gemini Caching Capabilities

### Context Caching
- **Purpose**: Cache large contexts (like full episode transcripts) for reuse
- **API**: `client.caches.create()` with `CreateCachedContentConfig`
- **TTL**: Configurable (default 3600s)
- **Cost**: 75% discount on cached tokens

### Implementation Example:
```python
cached_content = client.caches.create(
    model='gemini-2.0-flash-001',
    config=types.CreateCachedContentConfig(
        contents=[
            types.Content(
                role='user',
                parts=[types.Part.from_text(transcript_text)]
            )
        ],
        system_instruction='Optional system instruction',
        display_name='episode_12345',
        ttl='3600s',
    ),
)

# Use cached content
response = client.models.generate_content(
    model='gemini-2.0-flash-001',
    contents='Extract speakers from transcript',
    config=types.GenerateContentConfig(
        cached_content=cached_content.name,
    ),
)
```

## Cost Analysis for Speaker Identification

### Scenario: Processing 100 episodes
- Average episode: ~10,000 tokens
- Speaker identification prompt: ~500 tokens
- Without caching: 100 × 10,500 = 1,050,000 tokens
- With episode caching:
  - First call per episode: 10,500 tokens (full cost)
  - Subsequent calls: 500 tokens (prompt) + 10,000 × 0.25 (cached) = 3,000 tokens
  - Total for speaker ID: 100 × 10,500 = 1,050,000 tokens (same)
  - But subsequent extraction calls benefit from cache

### Key Insight
Episode-level caching is already implemented and optimal for speaker identification because:
1. The full transcript is cached once per episode
2. All extraction operations (entities, quotes, insights, AND speaker ID) can reuse the same cache
3. 75% cost savings on the transcript portion for all operations after the first

## Token Requirements
- Gemini Flash: Minimum 1024 tokens for caching
- Gemini Pro: Minimum 2048 tokens for caching
- Most podcast episodes exceed these minimums

## Recommendation
Use the existing episode-level caching infrastructure. No new caching mechanism needed.