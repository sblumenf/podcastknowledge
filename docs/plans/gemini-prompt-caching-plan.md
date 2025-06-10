# Gemini Prompt Caching Implementation Plan

## Executive Summary

This plan implements Gemini's native prompt caching functionality to optimize costs for the seeding pipeline. By switching from LangChain to direct Gemini API usage and leveraging context caching for large transcript prefixes, we expect to achieve 30-50% cost reduction while maintaining or improving performance.

## Technology Requirements

- **Google GenAI Python SDK** (`google-genai>=0.8.0`) - NEW TECHNOLOGY requiring approval
- Gemini 2.5 Pro API access (paid tier)
- Removal of LangChain dependency for LLM service

## Implementation Phases

### Phase 1: Research and Setup

- [x] **Task 1.1**: Review Gemini API documentation for caching
  - Purpose: Understand caching mechanics and best practices
  - Steps:
    1. Use context7 MCP tool to review Google GenAI Python SDK documentation
    2. Research caching strategies for transcript processing
    3. Document cache TTL recommendations and token limits
  - Validation: Written summary of caching approach

- [x] **Task 1.2**: Analyze current transcript processing patterns
  - Purpose: Identify optimal caching opportunities
  - Steps:
    1. Review typical transcript sizes in the pipeline
    2. Analyze prompt reuse patterns across segments
    3. Calculate potential cost savings based on usage
  - Validation: Cost analysis document with specific numbers

### Phase 2: Direct API Integration

- [x] **Task 2.1**: Create new Gemini client wrapper
  - Purpose: Replace LangChain with direct API calls
  - Steps:
    1. Create `src/services/llm_gemini_direct.py`
    2. Implement client initialization with google-genai SDK
    3. Add configuration for model selection (2.5 Pro)
    4. Integrate with existing key rotation manager
  - Validation: Unit tests pass for client initialization

- [x] **Task 2.2**: Implement basic content generation
  - Purpose: Ensure feature parity with current implementation
  - Steps:
    1. Implement `generate_content` method
    2. Add error handling and retry logic
    3. Integrate with metrics collection
    4. Maintain compatibility with existing interface
  - Validation: All existing LLM service tests pass

### Phase 3: Context Caching Implementation

- [x] **Task 3.1**: Implement transcript prefix caching
  - Purpose: Cache large transcript contexts for segment processing
  - Steps:
    1. Create cache management logic for transcript prefixes
    2. Implement `create_cached_content` for episode transcripts
    3. Add cache key generation based on episode ID
    4. Set appropriate TTL (3600s recommended)
  - Validation: Cache creation and retrieval works correctly

- [x] **Task 3.2**: Implement prompt template caching
  - Purpose: Cache frequently used prompt templates
  - Steps:
    1. Identify common prompt patterns in `src/extraction/prompts.py`
    2. Create cached versions of extraction prompts
    3. Implement cache warming on service startup
    4. Add cache hit/miss metrics
  - Validation: Prompt caching reduces API costs

### Phase 4: Integration and Migration

- [x] **Task 4.1**: Create service factory for gradual migration
  - Purpose: Allow switching between old and new implementations
  - Steps:
    1. Create factory method in `src/services/__init__.py`
    2. Add configuration flag for service selection
    3. Ensure backward compatibility
    4. Update dependency injection points
  - Validation: Both services can be used interchangeably

- [x] **Task 4.2**: Update extraction pipeline
  - Purpose: Optimize extraction for cached contexts
  - Steps:
    1. Modify `src/extraction/extraction.py` to use cached contexts
    2. Update segment processing to leverage prefix caching
    3. Implement batch processing with shared cache
    4. Add performance logging
  - Validation: Extraction uses cached contexts effectively

### Phase 5: Testing and Optimization

- [x] **Task 5.1**: Performance benchmarking
  - Purpose: Measure cost and latency improvements
  - Steps:
    1. Create benchmark script comparing old vs new
    2. Test with various transcript sizes
    3. Measure cache hit rates
    4. Document cost per transcript
  - Validation: 30%+ cost reduction achieved

- [x] **Task 5.2**: Integration testing
  - Purpose: Ensure system stability
  - Steps:
    1. Run full pipeline tests with new service
    2. Verify checkpointing works correctly
    3. Test error recovery scenarios
    4. Validate output quality
  - Validation: All integration tests pass

### Phase 6: Cleanup and Documentation

- [x] **Task 6.1**: Remove LangChain dependency
  - Purpose: Simplify codebase and reduce dependencies
  - Steps:
    1. Remove langchain-google-genai from requirements
    2. Clean up old LLM service code
    3. Update documentation
    4. Remove unused imports
  - Validation: No LangChain references remain

- [x] **Task 6.2**: Documentation and monitoring
  - Purpose: Ensure maintainability
  - Steps:
    1. Document caching strategy in README
    2. Add cache monitoring to metrics dashboard
    3. Create troubleshooting guide
    4. Update API documentation
  - Validation: Documentation is complete and accurate

## Success Criteria

1. **Cost Reduction**: Achieve 30-50% reduction in Gemini API costs
2. **Performance**: Maintain or improve processing speed
3. **Reliability**: No increase in error rates
4. **Cache Efficiency**: >70% cache hit rate for transcript segments
5. **Code Quality**: All tests pass, no regressions

## Implementation Notes

### Caching Strategy

Based on research, the optimal approach for the seeding pipeline is:

1. **Episode-Level Caching**: Cache entire transcript as context prefix
   - Cache key: `episode_{episode_id}`
   - TTL: 3600 seconds (1 hour)
   - Use for all segment extractions within episode

2. **Prompt Template Caching**: Cache common extraction prompts
   - Cache key: `prompt_{template_name}_{version}`
   - TTL: 86400 seconds (24 hours)
   - Warm cache on service startup

3. **Cost Optimization**:
   - Minimum 1024 tokens for 2.5 Flash caching
   - Minimum 2048 tokens for 2.5 Pro caching
   - 75% discount on cached tokens
   - Prioritize caching for transcripts >5000 tokens

### Migration Path

1. Implement new service alongside existing one
2. Test with small subset of episodes
3. Compare costs and quality
4. Gradually increase usage
5. Full cutover after validation

## Risk Mitigation

- Keep existing service as fallback
- Implement comprehensive error handling
- Monitor cache performance closely
- Have manual cache invalidation capability