# LangChain Migration Guide

## Overview

This guide documents how to migrate from LangChain to the direct Gemini API implementation with caching support.

## Migration Path

### 1. Current State
- LangChain is still available as the default service type
- New implementations are available via `LLM_SERVICE_TYPE` environment variable
- Both implementations share the same interface for compatibility

### 2. Gradual Migration

#### Step 1: Test with Direct API (No Caching)
```bash
export LLM_SERVICE_TYPE=gemini_direct
python your_script.py
```

#### Step 2: Test with Full Caching
```bash
export LLM_SERVICE_TYPE=gemini_cached
python your_script.py
```

#### Step 3: Monitor Performance
- Check logs for cache hit rates
- Monitor API costs in Google Cloud Console
- Compare processing times

### 3. Code Changes Required

#### For Basic Usage
No code changes needed - the factory handles service selection:

```python
from src.services import create_llm_service_only

# Works with any service type
llm_service = create_llm_service_only()
response = llm_service.complete("Your prompt")
```

#### For Advanced Caching
To leverage episode-level caching:

```python
from src.services import LLMServiceFactory, LLMServiceType
from src.extraction.cached_extraction import CachedExtractionService

# Create cached service
service = LLMServiceFactory.create_service(
    key_rotation_manager=key_manager,
    service_type=LLMServiceType.GEMINI_CACHED
)

# Use for extraction
extraction = CachedExtractionService(
    llm_service=service,
    cache_manager=service._cache_manager
)

results = extraction.extract_from_episode(
    episode_id="ep-123",
    transcript=transcript,
    segments=segments
)
```

## Dependency Removal Plan

### Phase 1: Validation (Current)
- Run parallel tests with both implementations
- Validate output quality matches
- Confirm cost savings

### Phase 2: Default Switch
- Change default from `langchain` to `gemini_direct`
- Keep LangChain as fallback option
- Update documentation

### Phase 3: Deprecation
- Mark LangChain service as deprecated
- Add deprecation warnings
- Set removal date (3-6 months)

### Phase 4: Removal
- Remove `langchain-google-genai` from requirements
- Remove `LLMService` class (keep interface)
- Clean up imports and unused code

## Current Dependencies

### Can Be Removed (Eventually)
```
langchain==0.1.0
langchain-google-genai==0.0.5
```

### Must Keep
```
google-genai>=1.0.0  # New direct API
google-generativeai==0.3.2  # For embeddings (until migrated)
```

## Monitoring During Migration

### Key Metrics
1. **Cache Hit Rate**: Target >70% for transcript processing
2. **Cost Reduction**: Should see 40-50% reduction
3. **Error Rate**: Should remain <1%
4. **Processing Time**: Should improve 10-20%

### Logging
Enable debug logging to monitor caching:
```python
import logging
logging.getLogger('src.services.cache_manager').setLevel(logging.DEBUG)
```

## Rollback Plan

If issues arise, rollback is simple:
```bash
export LLM_SERVICE_TYPE=langchain
```

No code changes required - the factory pattern ensures compatibility.

## Timeline

- **Month 1**: Testing and validation
- **Month 2**: Switch default to direct API
- **Month 3**: Deprecation notices
- **Month 4-6**: Support both implementations
- **Month 7**: Remove LangChain dependency

## Support

For issues during migration:
1. Check cache statistics: `cache_manager.get_cache_stats()`
2. Review cost savings: `cache_manager.estimate_cost_savings()`
3. Enable debug logging for troubleshooting
4. Use `langchain` service type as fallback