# Gemini Embedding Integration Plan

## Executive Summary
This plan outlines the complete replacement of the current sentence-transformers based embedding system with Google's text-embedding-004 model via the Gemini API. The implementation will maintain all existing functionality including single/batch embedding generation, similarity computation, and finding similar embeddings, while ensuring full compatibility with the rest of the codebase.

## Technology Requirements
**No new technologies required** - This implementation uses the existing `google-generativeai` package already in requirements.txt

## Phase 1: Analysis and Preparation

### Task 1.1: Document Current Embedding Usage
- [x] Analyze all embedding service usage in the codebase
- **Purpose**: Create a comprehensive map of all integration points
- **Steps**:
  1. Use context7 MCP tool to review embedding documentation
  2. Search for all imports of `EmbeddingsService` using grep
  3. Identify all method calls to the embeddings service
  4. Document embedding dimension dependencies
  5. Create a usage report in `docs/analysis/embedding-usage-map.md`
- **Validation**: Report contains all files using embeddings with line numbers

### Task 1.2: Research Gemini text-embedding-004 Specifications
- [x] Document Gemini embedding model capabilities and constraints
- **Purpose**: Ensure feature parity and identify implementation requirements
- **Steps**:
  1. Use context7 MCP tool to check Gemini API documentation
  2. Verify text-embedding-004 model availability in google-generativeai package
  3. Document embedding dimensions (768 for text-embedding-004)
  4. Document rate limits and pricing
  5. Identify batch processing capabilities
- **Validation**: Complete specification document created

### Task 1.3: Create Embedding Service Test Suite
- [x] Build comprehensive test suite for current embedding functionality
- **Purpose**: Ensure no regression during migration
- **Steps**:
  1. Use context7 MCP tool to review testing best practices
  2. Create `tests/services/test_embeddings_gemini.py`
  3. Write tests for:
     - Single text embedding generation
     - Batch embedding generation
     - Empty text handling
     - Similarity computation
     - Finding similar embeddings
  4. Run tests against current implementation to establish baseline
- **Validation**: All tests pass with current implementation

## Phase 2: Implementation

### Task 2.1: Create Gemini Embedding Service
- [x] Implement new GeminiEmbeddingsService class
- **Purpose**: Create drop-in replacement for current EmbeddingsService
- **Steps**:
  1. Use context7 MCP tool to review service implementation patterns
  2. Create new file `src/services/embeddings_gemini.py`
  3. Implement class with same interface as EmbeddingsService:
     ```python
     class GeminiEmbeddingsService:
         def __init__(self, api_key: str, model_name: str = 'models/text-embedding-004')
         def generate_embedding(self, text: str) -> List[float]
         def generate_embeddings(self, texts: List[str]) -> List[List[float]]
         def get_model_info(self) -> Dict[str, Any]
         def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float
         def find_similar(self, query_embedding: List[float], embeddings: List[List[float]], top_k: int = 5) -> List[Tuple[int, float]]
     ```
  4. Implement proper error handling and rate limiting
  5. Handle empty text cases (return zero vector of correct dimension)
- **Validation**: Service can be instantiated and all methods are callable

### Task 2.2: Implement Gemini API Integration
- [x] Connect GeminiEmbeddingsService to Gemini API
- **Purpose**: Enable actual embedding generation via API
- **Steps**:
  1. Use context7 MCP tool to review API integration patterns
  2. Import and configure google-generativeai client
  3. Implement generate_embedding method:
     - Clean text (remove newlines, strip)
     - Call embedding API with text-embedding-004 model
     - Convert response to List[float]
     - Handle API errors gracefully
  4. Implement batch processing with proper chunking
  5. Add logging for debugging
- **Validation**: Can generate embeddings for sample text

### Task 2.3: Implement Utility Methods
- [x] Implement similarity and search functionality
- **Purpose**: Maintain feature parity with existing service
- **Steps**:
  1. Use context7 MCP tool to review vector computation patterns
  2. Implement compute_similarity using numpy (already in requirements)
  3. Implement find_similar method with efficient sorting
  4. Ensure dimension compatibility (768 dimensions)
  5. Add proper input validation
- **Validation**: Similarity scores are between -1 and 1

### Task 2.4: Add Rate Limiting and Error Handling
- [x] Implement robust error handling and rate limiting
- **Purpose**: Ensure reliable operation within API constraints
- **Steps**:
  1. Use context7 MCP tool to review rate limiting patterns
  2. Reuse WindowedRateLimiter from utils.rate_limiting
  3. Configure appropriate limits for text-embedding-004
  4. Implement exponential backoff for retries
  5. Add comprehensive error messages
- **Validation**: Service handles rate limit errors gracefully

## Phase 3: Integration and Migration

### Task 3.1: Update Embeddings Service Factory
- [x] Modify embeddings.py to use Gemini implementation
- **Purpose**: Switch the entire codebase to new implementation
- **Steps**:
  1. Use context7 MCP tool to review service switching patterns
  2. Backup current `src/services/embeddings.py`
  3. Replace EmbeddingsService class with GeminiEmbeddingsService
  4. Update imports and initialization
  5. Ensure API key is properly passed from config
- **Validation**: Service initializes with Gemini implementation

### Task 3.2: Update Configuration
- [x] Add Gemini embedding configuration options
- **Purpose**: Allow configuration of embedding model
- **Steps**:
  1. Use context7 MCP tool to review configuration patterns
  2. Update config files to include:
     - GEMINI_EMBEDDING_MODEL (default: models/text-embedding-004)
     - EMBEDDING_DIMENSION (default: 768)
     - EMBEDDING_BATCH_SIZE (default: 100)
  3. Update environment variable documentation
  4. Ensure backward compatibility
- **Validation**: Config loads successfully with new options

### Task 3.3: Update Dimension Dependencies
- [x] Update all code that depends on embedding dimensions
- **Purpose**: Ensure compatibility with 768-dimension embeddings
- **Steps**:
  1. Use context7 MCP tool to review dimension dependencies
  2. Search for hardcoded dimension values (384 for MiniLM)
  3. Update any dimension-dependent code to use config value
  4. Update Neo4j schema if needed
  5. Update any vector operations
- **Validation**: No hardcoded dimensions remain

## Phase 4: Testing and Validation

### Task 4.1: Run Unit Tests
- [x] Execute all embedding-related unit tests
- **Purpose**: Verify functional correctness
- **Steps**:
  1. Use context7 MCP tool to review test execution patterns
  2. Run embedding service tests
  3. Run integration tests that use embeddings
  4. Fix any failing tests
  5. Document any behavior changes
- **Validation**: All tests pass

### Task 4.2: Run Integration Tests
- [x] Test full pipeline with new embeddings
- **Purpose**: Ensure end-to-end functionality
- **Steps**:
  1. Use context7 MCP tool to review integration testing patterns
  2. Run knowledge extraction pipeline with sample data
  3. Verify embeddings are generated correctly
  4. Check Neo4j storage of embeddings
  5. Test similarity search functionality
- **Validation**: Pipeline completes successfully

### Task 4.3: Performance Testing
- [x] Compare performance with previous implementation
- **Purpose**: Ensure acceptable performance
- **Steps**:
  1. Use context7 MCP tool to review performance testing patterns
  2. Measure embedding generation time for various text sizes
  3. Test batch processing performance
  4. Document API rate limit behavior
  5. Create performance comparison report
- **Validation**: Performance meets requirements

## Phase 5: Cleanup and Documentation

### Task 5.1: Remove Sentence-Transformers Dependencies
- [x] Clean up unused dependencies
- **Purpose**: Reduce package size and complexity
- **Steps**:
  1. Use context7 MCP tool to review dependency management
  2. Remove sentence-transformers from requirements.txt
  3. Update requirements-lean.txt
  4. Verify no imports remain
  5. Test installation with new requirements
- **Validation**: Project installs without sentence-transformers

### Task 5.2: Update Documentation
- [ ] Document the new embedding system
- **Purpose**: Enable future maintenance and usage
- **Steps**:
  1. Use context7 MCP tool to review documentation standards
  2. Update API documentation for embeddings service
  3. Create migration guide for developers
  4. Document configuration options
  5. Update README if needed
- **Validation**: Documentation is complete and accurate

### Task 5.3: Create Rollback Plan
- [ ] Document rollback procedure
- **Purpose**: Enable quick recovery if issues arise
- **Steps**:
  1. Use context7 MCP tool to review rollback procedures
  2. Document steps to revert to sentence-transformers
  3. Keep backup of original embeddings.py
  4. Document any data migration needs
  5. Test rollback procedure
- **Validation**: Can successfully rollback if needed

## Success Criteria

1. **Functional Completeness**
   - All existing embedding functionality works with Gemini API
   - No regression in pipeline functionality
   - All tests pass

2. **Performance**
   - Embedding generation meets performance requirements
   - Rate limiting handled gracefully
   - Batch processing works efficiently

3. **Compatibility**
   - No breaking changes to existing code
   - Embedding dimensions handled correctly throughout
   - Neo4j integration works seamlessly

4. **Maintainability**
   - Code is well-documented
   - Configuration is flexible
   - Rollback procedure exists

5. **Storage Efficiency**
   - Virtual environment remains under 500MB
   - No unnecessary dependencies

## Risk Mitigation

1. **API Rate Limits**: Implement proper rate limiting and queueing
2. **Dimension Mismatch**: Careful testing of all dimension-dependent code
3. **Cost Considerations**: Monitor API usage and implement caching if needed
4. **Network Dependency**: Add proper timeout and retry logic

## Estimated Timeline

- Phase 1: 2-3 hours (Analysis and Preparation)
- Phase 2: 4-5 hours (Implementation)
- Phase 3: 2-3 hours (Integration and Migration)
- Phase 4: 2-3 hours (Testing and Validation)
- Phase 5: 1-2 hours (Cleanup and Documentation)

Total: 11-16 hours of implementation time