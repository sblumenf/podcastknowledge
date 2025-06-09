# Seeding Pipeline API Rotation Implementation Plan

## Executive Summary

This plan will implement a robust API rotation system for the seeding pipeline module by copying and adapting the proven KeyRotationManager from the transcriber module. The implementation will maintain the same sophisticated features including multi-key rotation, quota tracking, state persistence, and circuit breaker functionality, while adapting it for the seeding pipeline's specific needs. The system will support multiple Gemini model types, maintain backward compatibility with existing environment variables, and provide coordinated quota tracking between LLM and embeddings services.

## Phases

### Phase 1: Copy and Adapt KeyRotationManager
- [x] Copy KeyRotationManager to seeding pipeline
  - Purpose: Bring the proven rotation logic into the seeding pipeline module
  - Steps:
    1. Use context7 MCP tool to review KeyRotationManager documentation
    2. Copy `transcriber/src/key_rotation_manager.py` to `seeding_pipeline/src/utils/key_rotation_manager.py`
    3. Update imports to use seeding pipeline's logging utilities
    4. Ensure state file path uses seeding pipeline's data directory
    5. Preserve all core functionality (quota tracking, daily reset, circuit breaker)
  - Validation: KeyRotationManager can be imported and instantiated in seeding pipeline

- [x] Enhance KeyRotationManager for multiple model support
  - Purpose: Support different Gemini models with different rate limits
  - Steps:
    1. Add model-specific rate limit configuration to KeyRotationManager
    2. Update quota tracking to be model-aware
    3. Modify state persistence to track per-model usage
    4. Add method to get rate limits for specific model
    5. Test with different model configurations
  - Validation: KeyRotationManager correctly tracks quotas per model type

- [x] Add backward compatibility for environment variables
  - Purpose: Support both old and new API key patterns
  - Steps:
    1. Update `create_key_rotation_manager()` function to check for `GOOGLE_API_KEY` first
    2. Fall back to numbered pattern (`GEMINI_API_KEY_1`, etc.)
    3. Support mixing single key with numbered keys
    4. Add clear logging about which keys were detected
    5. Update docstrings to explain both patterns
  - Validation: Manager initializes correctly with various environment variable combinations

### Phase 2: Update LLM Service Integration
- [x] Replace fallback mechanism with rotation system
  - Purpose: Remove basic fallback and integrate sophisticated rotation
  - Steps:
    1. Use context7 MCP tool to review LLM service documentation
    2. Remove `_fallback_extraction()` method from LLMService
    3. Remove existing CircuitBreaker class (rotation manager has better one)
    4. Add KeyRotationManager as required parameter to LLMService.__init__
    5. Update error handling to work with rotation system
  - Validation: LLM service no longer uses fallback extraction

- [x] Integrate rotation with LLM API calls
  - Purpose: Use rotation manager for all Gemini API calls
  - Steps:
    1. Replace single API key usage with rotation manager key selection
    2. Update `complete()` method to get next available key
    3. Add key success/failure reporting after each API call
    4. Update token usage reporting to rotation manager
    5. Remove redundant rate limiting code
  - Validation: LLM service rotates keys and reports usage correctly

- [x] Update LLM service configuration
  - Purpose: Ensure LLM service works with shared rotation state
  - Steps:
    1. Modify LLMService initialization to accept rotation manager
    2. Update `create_gemini_client()` style factory functions
    3. Ensure model name is passed to rotation manager for quota tracking
    4. Test with multiple model configurations
    5. Document configuration changes
  - Validation: LLM service correctly initializes with rotation enabled

### Phase 3: Update Embeddings Service Integration
- [x] Add rotation support to embeddings service
  - Purpose: Extend rotation to embeddings API calls
  - Steps:
    1. Use context7 MCP tool to review embeddings service documentation
    2. Add KeyRotationManager parameter to embeddings service init
    3. Update `_get_client()` method to use rotation manager
    4. Ensure embeddings model type is tracked separately
    5. Share rotation state with LLM service instance
  - Validation: Embeddings service uses rotation for API keys

- [x] Coordinate quota tracking with LLM service
  - Purpose: Ensure both services share quota state
  - Steps:
    1. Pass same KeyRotationManager instance to both services
    2. Ensure both services report token usage accurately
    3. Test concurrent usage from both services
    4. Verify quota limits are respected across both
    5. Add logging for quota coordination
  - Validation: Combined usage from both services respects quotas

### Phase 4: Update Service Initialization
- [x] Create unified initialization pattern
  - Purpose: Ensure consistent initialization across all services
  - Steps:
    1. Create factory function in `seeding_pipeline/src/services/__init__.py`
    2. Factory creates single KeyRotationManager instance
    3. Factory initializes both LLM and embeddings with shared manager
    4. Update all service creation points to use factory
    5. Document the initialization pattern
  - Validation: Services initialize with shared rotation state

- [x] Update configuration and environment handling
  - Purpose: Ensure smooth integration with existing configuration
  - Steps:
    1. Update `env_config.py` to document new environment variables
    2. Add validation for API key availability
    3. Update service initialization in orchestrator/batch processor
    4. Ensure backward compatibility is maintained
    5. Add helpful error messages for missing keys
  - Validation: Configuration correctly detects and validates API keys

### Phase 5: State Management and Persistence
- [x] Configure state persistence for seeding pipeline
  - Purpose: Ensure rotation state persists across runs
  - Steps:
    1. Ensure `data/.key_rotation_state.json` path is used
    2. Verify state directory creation on first run
    3. Test state recovery after process restart
    4. Ensure state file permissions are appropriate
    5. Add state file to .gitignore if needed
  - Validation: State persists and recovers correctly

- [x] Integrate with checkpoint system
  - Purpose: Ensure rotation state is considered in pipeline checkpoints
  - Steps:
    1. Review checkpoint system integration points
    2. Ensure rotation state is saved with checkpoints if needed
    3. Test recovery scenarios with rotation state
    4. Document any checkpoint considerations
    5. Ensure clean recovery after failures
  - Validation: Checkpoints work correctly with rotation state

### Phase 6: Testing and Migration
- [x] Create comprehensive test suite
  - Purpose: Ensure rotation system works correctly
  - Steps:
    1. Create tests in `tests/utils/test_key_rotation_manager.py`
    2. Test multi-key rotation scenarios
    3. Test quota tracking and enforcement
    4. Test state persistence and recovery
    5. Test model-specific rate limits
  - Validation: All rotation tests pass

- [x] Update existing service tests
  - Purpose: Ensure service tests work with rotation
  - Steps:
    1. Update LLM service tests to mock rotation manager
    2. Update embeddings service tests similarly
    3. Add integration tests for rotation scenarios
    4. Test error handling and key exhaustion
    5. Verify backward compatibility scenarios
  - Validation: All existing tests pass with rotation

- [x] Migration and rollout validation
  - Purpose: Ensure smooth transition to rotation system
  - Steps:
    1. Test with single API key (backward compatibility)
    2. Test with multiple API keys
    3. Verify performance is maintained
    4. Document migration steps for users
    5. Create example environment configuration
  - Validation: System works in all deployment scenarios

## Success Criteria

1. **Independent Implementation**: Seeding pipeline has its own copy of rotation logic
2. **Feature Completeness**: All rotation features from transcriber are working
3. **Multi-Model Support**: Different Gemini models have appropriate rate limits
4. **Backward Compatibility**: Existing GOOGLE_API_KEY configurations still work
5. **Shared Quota Tracking**: LLM and embeddings services coordinate quota usage
6. **State Persistence**: Rotation state survives pipeline restarts
7. **Test Coverage**: Comprehensive tests for rotation scenarios
8. **Zero Downtime**: Existing deployments continue working during migration

## Technology Requirements

**No new technologies required** - This implementation uses:
- Existing Python standard library
- Current langchain_google_genai dependency
- Existing seeding pipeline structure
- Current environment variable patterns

**Documentation Review**: Each task requires explicit use of context7 MCP tool for documentation review before implementation.

## Implementation Notes

The rotation system will be self-contained within the seeding pipeline module, ensuring:
- Independent deployment remains possible
- No shared dependencies with transcriber module
- Consistent behavior with proven rotation logic
- Easy maintenance through code similarity with transcriber

This approach provides the benefits of the sophisticated rotation system while maintaining complete deployment independence between modules.