# Gemini Embedding Migration Guide

## Overview
This guide documents the migration from sentence-transformers (all-MiniLM-L6-v2) to Gemini text-embedding-004 model.

## Configuration Changes

### Environment Variables
You must set the following environment variable:
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

The same API key used for Gemini LLM services can be used for embeddings.

### Configuration File Updates

If using a YAML configuration file, update the following values:

```yaml
# Before
embedding_model: "all-MiniLM-L6-v2"
embedding_dimensions: 384
embedding_batch_size: 50

# After
embedding_model: "models/text-embedding-004"
embedding_dimensions: 768
embedding_batch_size: 100
```

### Code Changes

No code changes are required. The `EmbeddingsService` class now automatically uses the Gemini implementation.

If you were explicitly importing from specific modules:
```python
# Before
from src.services.embeddings import EmbeddingsService

# After (no change needed - same import works)
from src.services.embeddings import EmbeddingsService
```

## Key Differences

### Dimensions
- **Before**: 384 dimensions (all-MiniLM-L6-v2)
- **After**: 768 dimensions (text-embedding-004)

### Performance
- **Before**: Local model, ~1ms per embedding
- **After**: API-based, ~50-200ms per embedding (but better quality)

### Batch Processing
- **Before**: Unlimited batch size (memory constrained)
- **After**: Max 2048 texts per batch (API limit), recommended 100

### Cost
- **Before**: Free (local compute)
- **After**: Charged per character via Gemini API

## Migration Checklist

1. ✅ Set `GEMINI_API_KEY` environment variable
2. ✅ Update configuration files if used
3. ✅ No code changes required (backward compatible)
4. ✅ Test with small dataset first
5. ✅ Monitor API usage and costs

## Rollback Procedure

If you need to rollback to sentence-transformers:

1. The original implementation is preserved in `embeddings_backup.py`
2. Replace the content of `embeddings.py` with `embeddings_backup.py`
3. Remove Gemini-specific configuration
4. Reinstall sentence-transformers: `pip install sentence-transformers==2.2.2`

## API Rate Limits

The Gemini API has the following limits:
- 1,500 requests per minute
- 4,000,000 characters per minute
- 1,500,000 requests per day

The service includes automatic rate limiting to stay within these limits.

## Error Handling

Common errors and solutions:

1. **Rate Limit Exceeded**
   - The service will automatically retry with exponential backoff
   - Consider reducing batch size or adding delays

2. **Invalid API Key**
   - Check that GEMINI_API_KEY is set correctly
   - Verify the key has access to embedding models

3. **Network Errors**
   - The service includes retry logic for transient errors
   - Check your internet connection

## Testing

Run the embedding tests to verify the migration:
```bash
pytest tests/services/test_embeddings_gemini.py -v
```