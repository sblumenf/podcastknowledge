# Groq to Gemini with neo4j-graphrag Migration Plan

## Executive Summary

Replace the custom RAG implementation using Groq with neo4j-graphrag library configured for Google Gemini (gemini-2.5-pro model). This migration will eliminate approximately 230 lines of custom code, remove all Groq dependencies, and leverage the tested neo4j-graphrag library for vector search and response generation. The frontend API contract remains unchanged, ensuring zero frontend modifications.

## Phase 1: Environment and Dependencies Setup

### Task 1.1: Verify Environment Variables
- [x] **Check existing GEMINI_API_KEY availability** (3 sentences minimum)
  - Purpose: Ensure the Gemini API key from seeding pipeline .env is accessible
  - Steps:
    1. Read the UI backend .env file to check if GEMINI_API_KEY exists
    2. If not present, verify the key can be read from parent directory .env
    3. Document the exact environment variable name being used
  - Reference: This task aligns with Phase 1 of setting up the environment foundation
  - Validation: Print the first 10 characters of the API key (masked) to confirm availability

### Task 1.2: Install neo4j-graphrag with Google GenAI Support
- [x] **Update requirements.txt with proper dependencies** (3 sentences minimum)
  - Purpose: Add neo4j-graphrag and google-generativeai packages with correct versions
  - Steps:
    1. Check Context7 documentation for neo4j-graphrag latest stable version
    2. Add `neo4j-graphrag[google-genai]==1.7.0` to requirements.txt
    3. Add `google-generativeai==0.8.3` for Gemini support
    4. Remove `groq==0.11.0` line from requirements.txt
  - Reference: This task is part of Phase 1 dependency management
  - Validation: Run pip install -r requirements.txt successfully in the virtual environment

### Task 1.3: Create Configuration Module
- [x] **Design configuration structure for Gemini parameters** (3 sentences minimum)
  - Purpose: Create a maintainable configuration system following KISS principles
  - Steps:
    1. Add configuration to existing config.py or create minimal config dict
    2. Include model_name as environment variable GEMINI_MODEL with default "gemini-2.5-pro"
    3. Add generation parameters: temperature (0.7), max_tokens (1024)
  - Reference: Phase 1 configuration setup for maintainability
  - Validation: Configuration can be imported and values are accessible

## Phase 2: Remove Groq Implementation

### Task 2.1: Remove Groq Imports and Initialization
- [x] **Delete all Groq-related imports and client setup** (3 sentences minimum)
  - Purpose: Clean up imports section by removing Groq and httpx dependencies
  - Steps:
    1. Remove line 8: `from groq import Groq`
    2. Remove line 43: `import httpx` (only needed for Groq workaround)
    3. Delete lines 30 (groq_api_key) and 40-52 (entire Groq client setup)
  - Reference: Phase 2 focuses on removing all Groq code
  - Validation: No import errors when loading the module

### Task 2.2: Remove Custom RAG Methods
- [x] **Delete custom vector search and response generation methods** (3 sentences minimum)
  - Purpose: Remove all custom RAG implementation to be replaced by neo4j-graphrag
  - Steps:
    1. Delete `_embed_query` method (lines 110-136)
    2. Delete `_vector_search` method (lines 138-185)
    3. Delete `_generate_response` method (lines 187-241)
  - Reference: Phase 2 cleanup of custom implementation
  - Validation: Methods no longer exist in the file

### Task 2.3: Clean Up Groq References
- [x] **Remove all remaining Groq mentions and variables** (3 sentences minimum)
  - Purpose: Ensure complete removal of Groq from the codebase
  - Steps:
    1. Remove self.groq_client references throughout the file
    2. Update docstrings and comments that mention Groq
    3. Search entire UI project for any remaining "groq" references
  - Reference: Final cleanup task for Phase 2
  - Validation: grep -i "groq" returns no results in UI backend

## Phase 3: Implement neo4j-graphrag Integration

### Task 3.1: Initialize neo4j-graphrag Components
- [x] **Set up GraphRAG with Gemini configuration** (3 sentences minimum)
  - Purpose: Create the neo4j-graphrag pipeline with proper Gemini integration
  - Steps:
    1. Import required classes from neo4j_graphrag (check Context7 for exact imports)
    2. Initialize GoogleGenerativeAI LLM with gemini-2.5-pro model
    3. Set up VectorRetriever with existing index 'meaningfulUnitEmbeddings'
    4. Create GraphRAG instance combining retriever and LLM
  - Reference: Core implementation task in Phase 3
  - Validation: GraphRAG object initializes without errors

### Task 3.2: Configure Embeddings Consistency
- [x] **Ensure embedding compatibility with existing vectors** (3 sentences minimum)
  - Purpose: Maintain compatibility with existing 768-dimension Gemini embeddings
  - Steps:
    1. Check Context7 docs for GoogleGenerativeAIEmbeddings configuration
    2. Initialize embedder with same model used in seeding pipeline (text-embedding-004)
    3. Pass embedder to VectorRetriever for query embedding
  - Reference: Critical compatibility task in Phase 3
  - Validation: Test query produces 768-dimension embedding vector

### Task 3.3: Implement Simplified Search Method
- [x] **Replace complex search logic with neo4j-graphrag search** (3 sentences minimum)
  - Purpose: Simplify the search method to delegate to neo4j-graphrag
  - Steps:
    1. Replace entire search method body with GraphRAG search call
    2. Configure retriever_config with top_k parameter from method argument
    3. Handle response to match expected format (response text and status)
  - Reference: Simplification goal of Phase 3
  - Validation: Search method returns expected response structure

### Task 3.4: Update Error Handling
- [x] **Implement neo4j-graphrag default error handling** (3 sentences minimum)
  - Purpose: Use library's built-in error handling instead of custom logic
  - Steps:
    1. Remove custom error handling blocks
    2. Let neo4j-graphrag exceptions propagate naturally
    3. Only catch and wrap connection errors for service initialization
  - Reference: Error handling standardization in Phase 3
  - Validation: Errors are properly logged and returned

## Phase 4: Frontend Compatibility Verification

### Task 4.1: Analyze Response Format Requirements
- [x] **Ensure ChatResponse format matches frontend expectations** (3 sentences minimum)
  - Purpose: Verify the response structure maintains frontend compatibility
  - Steps:
    1. Check Context7 docs for GraphRAG response format
    2. Map GraphRAG response to ChatResponse(response=text, podcast_name=name)
    3. Remove sources array from response as not needed per requirements
  - Reference: Frontend compatibility check in Phase 4
  - Validation: Response has correct fields when tested

### Task 4.2: Test Multi-Podcast Support
- [x] **Verify podcast-specific database connections work** (3 sentences minimum)
  - Purpose: Ensure the multi-podcast architecture continues functioning
  - Steps:
    1. Test service cache maintains separate GraphRAG instances per podcast
    2. Verify each podcast connects to its specific database
    3. Confirm database names are properly passed to neo4j driver
  - Reference: Multi-podcast support verification in Phase 4
  - Validation: Different podcasts return different content

## Phase 5: Testing and Validation

### Task 5.1: Create Simple Test Script
- [x] **Write minimal test script for API endpoint** (3 sentences minimum)
  - Purpose: Validate the implementation works end-to-end
  - Steps:
    1. Create test_chat_endpoint.py that sends a query to the API
    2. Test with a simple query like "What is the 5 second rule?"
    3. Verify response contains text and no errors occur
  - Reference: Testing phase to ensure functionality
  - Validation: Test script runs successfully and returns coherent response

### Task 5.2: Verify No Groq Dependencies Remain
- [x] **Final verification of complete Groq removal** (3 sentences minimum)
  - Purpose: Ensure all traces of Groq are eliminated from the project
  - Steps:
    1. Run `pip freeze | grep -i groq` to check installed packages
    2. Search all project files for "groq" case-insensitive
    3. Verify requirements.txt has no groq package
  - Reference: Final validation task in Phase 5
  - Validation: Zero groq references found anywhere

### Task 5.3: Performance and Token Limit Testing
- [x] **Verify Gemini handles larger contexts without token errors** (3 sentences minimum)
  - Purpose: Confirm the token limit issue is resolved with Gemini
  - Steps:
    1. Test with a query that previously failed with Groq
    2. Monitor token usage in response metadata if available
    3. Verify no rate limit or token limit errors occur
  - Reference: Performance validation in Phase 5
  - Validation: Previously failing queries now succeed

## Success Criteria

1. **Complete Groq Removal**: Zero references to Groq in codebase, dependencies, or imports
2. **Functional Chat Interface**: Chat queries return appropriate responses for each podcast
3. **Frontend Compatibility**: No frontend code changes required, same API contract maintained
4. **Simplified Codebase**: RAG service reduced from ~330 lines to ~100 lines
5. **Performance Improvement**: No more token limit errors that occurred with Groq
6. **Maintainability**: Configuration uses environment variables and follows KISS principles

## Technology Requirements

### New Technologies Requiring Approval:
1. **neo4j-graphrag==1.7.0**: Official Neo4j library for GraphRAG functionality
2. **google-generativeai==0.8.3**: Google's official SDK for Gemini models

### Technologies Being Removed:
1. **groq==0.11.0**: Complete removal of Groq SDK
2. **Custom httpx client**: No longer needed without Groq

### Existing Technologies Maintained:
1. **neo4j==5.28.0**: Existing Neo4j Python driver
2. **Existing Gemini embeddings**: Same embedding model for compatibility

## Documentation Requirements

Every task must reference Context7 documentation using the MCP tool for:
- neo4j-graphrag API usage and configuration
- Google Generative AI SDK for proper Gemini setup
- GraphRAG initialization and search methods
- Embeddings configuration for consistency

## Risk Mitigation

1. **API Key Access**: Verify GEMINI_API_KEY is accessible before starting
2. **Embedding Compatibility**: Ensure same embedding model (text-embedding-004) is used
3. **Index Name Matching**: Confirm 'meaningfulUnitEmbeddings' index exists
4. **Response Format**: Map GraphRAG response to expected ChatResponse structure
5. **Multi-Podcast Isolation**: Maintain separate GraphRAG instances per podcast