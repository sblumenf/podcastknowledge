# Gemini Prompt Caching Documentation

## Overview

The Gemini prompt caching implementation provides 40-50% cost reduction for processing podcast transcripts by leveraging Google's native context caching feature. This documentation covers setup, usage, and monitoring.

## Architecture

### Components

1. **GeminiDirectService** (`src/services/llm_gemini_direct.py`)
   - Direct API client using `google-genai` SDK
   - Native caching support with `create_cached_content()`
   - Compatible interface with existing LLMService

2. **CacheManager** (`src/services/cache_manager.py`)
   - Tracks episode and prompt caches
   - Provides cache statistics and cost estimation
   - Manages cache TTL and eviction

3. **CachedPromptService** (`src/services/cached_prompt_service.py`)
   - Manages prompt template caching
   - Warms caches on startup
   - Integrates with extraction methods

4. **LLMServiceFactory** (`src/services/llm_factory.py`)
   - Creates services based on configuration
   - Enables gradual migration from LangChain
   - Supports three service types

## Configuration

### Environment Variables

```bash
# Service type selection
export LLM_SERVICE_TYPE=gemini_cached  # Options: langchain, gemini_direct, gemini_cached

# Model configuration
export GEMINI_MODEL=gemini-2.5-flash-001  # Use stable version for caching

# Cache settings
export CACHE_TTL=3600  # Cache lifetime in seconds (default: 1 hour)
export MIN_CACHE_SIZE=5000  # Minimum transcript size for caching (characters)
```

### Python Configuration

```python
from src.services import LLMServiceFactory, LLMServiceType

# Create cached service
service = LLMServiceFactory.create_service(
    key_rotation_manager=key_manager,
    service_type=LLMServiceType.GEMINI_CACHED,
    model_name='gemini-2.5-flash-001',
    cache_ttl=3600
)
```

## Usage Examples

### Basic Usage

```python
# Automatically uses caching based on environment
from src.services import create_llm_service_only

llm = create_llm_service_only()
response = llm.complete("Extract entities from: ...")
```

### Episode Processing with Caching

```python
from src.extraction.cached_extraction import CachedExtractionService

# Create extraction service
extraction = CachedExtractionService(
    llm_service=service,
    cache_manager=service._cache_manager
)

# Process episode - automatically caches if beneficial
results = extraction.extract_from_episode(
    episode_id="podcast-123",
    transcript=full_transcript,
    segments=transcript_segments
)

# Check cache performance
stats = extraction.get_extraction_stats()
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.1%}")
print(f"Cost savings: ${stats['cost_savings']['estimated_savings_usd']:.2f}")
```

### Manual Cache Management

```python
# Create episode cache
cache_name = service.create_cached_content(
    content=transcript,
    episode_id="ep-123",
    system_instruction="Extract knowledge from this podcast transcript"
)

# Use cached content for multiple extractions
for segment in segments:
    response = service.complete(
        prompt=f"Extract entities from: {segment.text}",
        cached_content_name=cache_name
    )
```

## Caching Strategy

### Episode-Level Caching
- **When**: Transcripts >5,000 characters (~1,250 tokens)
- **TTL**: 1 hour (sufficient for processing all segments)
- **Benefit**: 75% cost reduction on cached tokens

### Prompt Template Caching
- **What**: Common extraction prompts (entity, insight, quote)
- **TTL**: 24 hours (stable content)
- **Benefit**: Additional 5-10% cost reduction

### Cache Key Strategy
```
Episode: episode_{episode_id}
Prompt: prompt_{template_name}_v{version}
```

## Monitoring and Metrics

### Cache Statistics

```python
# Get current cache stats
stats = cache_manager.get_cache_stats()
print(f"""
Cache Performance:
- Hit Rate: {stats['hit_rate']:.1%}
- Active Episode Caches: {stats['active_episode_caches']}
- Active Prompt Caches: {stats['active_prompt_caches']}
- Total Cached Tokens: {stats['total_cached_tokens']:,}
""")
```

### Cost Tracking

```python
# Estimate savings
savings = cache_manager.estimate_cost_savings()
print(f"""
Cost Analysis:
- Cache Uses: {savings['cache_uses']}
- Tokens Saved: {savings['tokens_saved']:,}
- Estimated Savings: ${savings['estimated_savings_usd']:.2f}
- Savings Rate: {savings['savings_percentage']:.0%}
""")
```

### Performance Benchmarking

Run the benchmark script to compare implementations:

```bash
python scripts/benchmark_caching.py
```

Output example:
```
=== Benchmark Results ===

langchain:
  Average time: 2.34s
  Average cost: $0.0450

gemini_cached:
  Average time: 1.87s
  Average cost: $0.0243

Improvements (Cached vs LangChain):
  Cost reduction: 46.0%
  Speed improvement: 1.3x
```

## Best Practices

### 1. Model Selection
Always use stable model versions for caching:
- ✅ `gemini-2.5-flash-001`
- ✅ `gemini-2.5-pro-001`
- ❌ `gemini-2.5-flash` (may change)

### 2. Cache Warming
Warm prompt caches on startup:
```python
cached_service = CachedPromptService(llm_service, cache_manager)
cached_templates = cached_service.warm_caches()
```

### 3. Batch Processing
Process segments in batches to maximize cache utilization:
```python
config = CachedExtractionConfig(
    batch_size=10,  # Process 10 segments at once
    cache_ttl=3600
)
```

### 4. Error Handling
Always implement fallback for cache failures:
```python
try:
    cache_name = service.create_cached_content(...)
except Exception as e:
    logger.warning(f"Cache creation failed: {e}")
    # Continue without caching
```

## Troubleshooting

### Common Issues

1. **Cache Creation Fails**
   - Check transcript size (minimum 1024 tokens for Flash)
   - Verify stable model version is used
   - Check API quota limits

2. **Low Cache Hit Rate**
   - Increase cache TTL if processing takes longer
   - Ensure episode IDs are consistent
   - Check cache eviction in logs

3. **No Cost Savings**
   - Verify caching is enabled (`LLM_SERVICE_TYPE=gemini_cached`)
   - Check that transcripts meet minimum size
   - Monitor cache statistics

### Debug Logging

Enable detailed logging:
```python
import logging

# Enable cache manager logs
logging.getLogger('src.services.cache_manager').setLevel(logging.DEBUG)

# Enable service logs
logging.getLogger('src.services.llm_gemini_direct').setLevel(logging.DEBUG)
```

## Migration Checklist

- [ ] Set `LLM_SERVICE_TYPE=gemini_cached`
- [ ] Update model names to stable versions
- [ ] Run integration tests
- [ ] Monitor cache hit rates
- [ ] Verify cost reduction in billing
- [ ] Document any custom modifications

## API Reference

### GeminiDirectService

```python
class GeminiDirectService:
    def create_cached_content(
        content: str,
        episode_id: str, 
        system_instruction: Optional[str] = None
    ) -> Optional[str]:
        """Create cached content for episode."""
        
    def complete(
        prompt: str,
        cached_content_name: Optional[str] = None
    ) -> str:
        """Generate completion with optional cache."""
```

### CacheManager

```python
class CacheManager:
    def should_cache_transcript(
        transcript: str,
        episode_id: str
    ) -> bool:
        """Determine if transcript should be cached."""
        
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache performance statistics."""
        
    def estimate_cost_savings() -> Dict[str, float]:
        """Estimate cost savings from caching."""
```

## Future Enhancements

1. **Adaptive TTL**: Adjust cache lifetime based on processing patterns
2. **Preemptive Caching**: Cache upcoming episodes during idle time
3. **Cross-Episode Caching**: Share common contexts between related episodes
4. **Cache Persistence**: Store cache metadata for long-term analysis