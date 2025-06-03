# Gemini Embedding Test Execution Plan

## Test Suite Overview

This document outlines the tests that should be run to validate the Gemini embedding integration.

## Unit Tests

### 1. Embedding Service Tests
**File**: `tests/services/test_embeddings_gemini.py`

Run with:
```bash
pytest tests/services/test_embeddings_gemini.py -v
```

Expected tests:
- ✓ Service initialization with API key
- ✓ Single text embedding generation
- ✓ Batch embedding generation
- ✓ Empty text handling (returns zero vector)
- ✓ Similarity computation
- ✓ Finding similar embeddings
- ✓ Rate limit error handling
- ✓ API error handling
- ✓ Text cleaning (newlines, spaces)
- ✓ Batch with mixed empty/valid texts
- ✓ Dimension consistency (768)

### 2. Interface Tests
**File**: `tests/unit/test_interfaces_full.py`

Run with:
```bash
pytest tests/unit/test_interfaces_full.py::TestEmbeddingProvider -v
```

Expected:
- ✓ All embedding dimensions updated to 768
- ✓ Interface compliance tests pass

### 3. Mock Service Tests
**File**: `tests/utils/external_service_mocks.py`

Verify:
- ✓ Mock embedding model returns 768-dimensional vectors
- ✓ Default model name is "models/text-embedding-004"

## Integration Tests

### 1. Provider Coordinator Tests
Run tests that verify the embedding service is properly initialized with API key:
```bash
pytest tests/seeding/test_provider_coordinator.py -v
```

### 2. End-to-End Pipeline Tests
Run with environment variable set:
```bash
export GEMINI_API_KEY="your-api-key"
pytest tests/integration/test_e2e_critical_path.py -v
```

### 3. VTT Processing Tests
```bash
pytest tests/integration/test_vtt_e2e.py -v
```

## Performance Tests

### 1. Baseline Performance
**File**: `tests/performance/test_baseline_performance.py`

Measure:
- Single embedding generation time
- Batch embedding generation time
- Memory usage
- API rate limit handling

### 2. Benchmark Comparison
Create benchmark comparing:
- Old: all-MiniLM-L6-v2 (384 dims, local)
- New: text-embedding-004 (768 dims, API)

Metrics to capture:
- Latency per embedding
- Throughput (embeddings/second)
- Memory usage
- Cost per 1000 embeddings

## Manual Testing Checklist

1. **API Key Configuration**
   - [ ] Set GEMINI_API_KEY environment variable
   - [ ] Verify service initializes without errors
   - [ ] Test with invalid API key (should fail gracefully)

2. **Basic Functionality**
   - [ ] Generate embedding for simple text
   - [ ] Verify dimension is 768
   - [ ] Generate batch of 100 embeddings
   - [ ] Test empty string handling

3. **Error Handling**
   - [ ] Disconnect network and verify error handling
   - [ ] Exceed rate limit and verify retry logic
   - [ ] Test with very long text (>2048 tokens)

4. **Integration**
   - [ ] Run full pipeline with sample podcast
   - [ ] Verify embeddings stored in Neo4j
   - [ ] Check similarity search functionality

## Test Execution Order

1. **Phase 1**: Unit tests (no API key required)
   - Mock-based tests
   - Interface compliance tests
   - Configuration tests

2. **Phase 2**: Integration tests (API key required)
   - Service initialization
   - Basic functionality
   - Error handling

3. **Phase 3**: Performance tests
   - Baseline metrics
   - Comparison with previous implementation

4. **Phase 4**: Full pipeline tests
   - End-to-end processing
   - Production-like scenarios

## Success Criteria

1. All unit tests pass
2. Integration tests complete successfully with API
3. Performance is acceptable (<500ms per embedding)
4. No regression in pipeline functionality
5. Error handling works as expected

## Known Limitations

1. API-based embeddings have higher latency than local models
2. Rate limits may affect batch processing speed
3. Network connectivity is required
4. API costs apply per character processed