# Speaker Identification Implementation Plan

## Executive Summary

This plan implements a mandatory speaker identification system for the VTT processing pipeline that uses LLM-based analysis to replace generic speaker labels (Speaker 0, 1, 2...) with actual names or descriptive roles. The system will enhance knowledge graph quality by ensuring all quotes, relationships, and entities have meaningful speaker attribution. The implementation leverages the existing Gemini prompt caching infrastructure for cost-effective processing.

## Phase 1: Infrastructure Setup and Integration Analysis

### Task 1.1: Analyze Current VTT Processing Flow
- [x] Review VTT ingestion pipeline architecture
- **Purpose**: Understand current data flow and identify optimal integration point
- **Steps**:
  1. Use context7 MCP tool to review LangChain documentation for prompt caching patterns
  2. Examine `src/seeding/transcript_ingestion.py` for VTT file handling
  3. Analyze `src/vtt/vtt_parser.py` and `src/vtt/vtt_segmentation.py` 
  4. Document the current processing flow from VTT file to knowledge extraction
  5. Identify where speaker data flows through the pipeline
- **Validation**: Create a flow diagram showing VTT processing stages

### Task 1.2: Evaluate Gemini Caching Infrastructure
- [x] Assess existing LLM service implementation for speaker identification
- **Purpose**: Ensure we can leverage existing caching for cost-effective processing
- **Steps**:
  1. Use context7 MCP tool to review Gemini prompt caching documentation
  2. Review `src/services/llm_gemini_direct.py` and caching implementation
  3. Analyze `src/services/cached_prompt_service.py` for prompt caching patterns
  4. Document cache TTL, size limits, and cost implications
  5. Calculate expected token usage for speaker identification
- **Validation**: Document caching strategy with cost projections

### Task 1.3: Design Speaker Identification Prompt Template
- [x] Create optimized prompt template for speaker identification
- **Purpose**: Develop effective prompts that maximize accuracy while minimizing tokens
- **Steps**:
  1. Use context7 MCP tool to review LangChain prompt template best practices
  2. Design prompt structure that includes:
     - Episode metadata (podcast name, description)
     - Speaker statistics (speaking time, turn counts)
     - Conversation samples (first 5-10 minutes)
  3. Create prompt variations for different confidence levels
  4. Add to `src/extraction/prompts.py` as new template
- **Validation**: Test prompt with sample VTT data

## Phase 2: Core Implementation

### Task 2.1: Create Speaker Identification Service
- [x] Implement speaker identification service class
- **Purpose**: Encapsulate speaker identification logic with caching support
- **Steps**:
  1. Use context7 MCP tool to review LangChain service patterns
  2. Create `src/extraction/speaker_identifier.py`
  3. Implement class with methods:
     - `identify_speakers(segments, metadata)` - Main identification method
     - `_calculate_speaker_statistics(segments)` - Analyze speaking patterns
     - `_prepare_context(segments, metadata)` - Prepare cached context
     - `_map_speakers(llm_response, segments)` - Apply identified names
  4. Integrate with `GeminiDirectService` for prompt caching
  5. Add confidence scoring for each identification
- **Validation**: Unit tests for each method

### Task 2.2: Integrate with VTT Segmentation
- [x] Add speaker identification to VTT processing pipeline
- **Purpose**: Process speakers after parsing but before extraction
- **Steps**:
  1. Use context7 MCP tool to review pipeline integration patterns
  2. Modify `src/vtt/vtt_segmentation.py`:
     - Add `_identify_speakers()` method to `VTTSegmenter`
     - Call speaker identifier after segment creation
     - Update segment objects with identified names
  3. Ensure backward compatibility for pre-identified speakers
  4. Add feature flag for enabling/disabling identification
- **Validation**: Integration tests with sample VTT files

### Task 2.3: Update Knowledge Extraction
- [x] Ensure extraction uses enhanced speaker information
- **Purpose**: Improve quote attribution and entity relationships
- **Steps**:
  1. Use context7 MCP tool to review knowledge extraction documentation
  2. Verify `src/extraction/extraction.py` uses updated speaker names
  3. Update entity resolution to recognize speaker names as PERSON entities
  4. Ensure relationships (SPEAKS, DISCUSSES) use proper names
  5. Add fallback for low-confidence identifications
- **Validation**: Compare knowledge graphs before/after implementation

## Phase 3: Error Handling and Optimization

### Task 3.1: Implement Graceful Degradation
- [x] Handle identification failures and edge cases
- **Purpose**: Ensure pipeline continues even when identification fails
- **Steps**:
  1. Use context7 MCP tool to review error handling patterns
  2. Implement fallback strategies:
     - Use descriptive roles when names unavailable
     - Track confidence scores in metadata
     - Log identification failures for analysis
  3. Add retry logic for transient LLM failures
  4. Implement timeout handling for long transcripts
- **Validation**: Test with problematic VTT files

### Task 3.2: Optimize Performance and Costs
- [x] Implement batching and caching optimizations
- **Purpose**: Minimize API calls and maximize cache hits
- **Steps**:
  1. Use context7 MCP tool to review batching best practices
  2. Implement episode-level caching strategy
  3. Batch multiple segments in single LLM calls
  4. Add metrics for cache hit rates
  5. Implement speaker database for recurring hosts
- **Validation**: Performance benchmarks and cost analysis

### Task 3.3: Add Monitoring and Metrics
- [x] Implement comprehensive monitoring
- **Purpose**: Track system performance and identification quality
- **Steps**:
  1. Use context7 MCP tool to review monitoring patterns
  2. Add metrics:
     - Speaker identification success rate
     - Average confidence scores
     - Cache hit rates
     - Processing time per episode
  3. Integrate with existing metrics infrastructure
  4. Create dashboard for monitoring
- **Validation**: Verify metrics collection and visualization

## Phase 4: Testing and Documentation

### Task 4.1: Comprehensive Testing
- [x] Create test suite for speaker identification
- **Purpose**: Ensure reliability across diverse podcast formats
- **Steps**:
  1. Use context7 MCP tool to review testing best practices
  2. Create unit tests for speaker identifier
  3. Add integration tests with real VTT files
  4. Test edge cases:
     - Single speaker podcasts
     - Many speakers (>5)
     - Non-English content
     - Poor quality transcripts
  5. Add performance regression tests
- **Validation**: All tests passing with >90% coverage

### Task 4.2: Documentation and Training
- [x] Create comprehensive documentation
- **Purpose**: Enable team understanding and maintenance
- **Steps**:
  1. Use context7 MCP tool to review documentation standards
  2. Document:
     - Architecture and design decisions
     - Configuration options
     - Prompt engineering guidelines
     - Troubleshooting guide
  3. Create examples of successful/failed identifications
  4. Add to existing pipeline documentation
- **Validation**: Documentation review by team

## Success Criteria

1. **Identification Accuracy**: >80% of speakers correctly identified with names or meaningful roles
2. **Performance**: <2 second additional processing time per episode
3. **Cost Efficiency**: <$0.05 per episode with caching
4. **Reliability**: 99.9% uptime with graceful degradation
5. **Knowledge Graph Quality**: 50% reduction in unattributed quotes

## Technology Requirements

**No new technologies required** - Implementation uses existing infrastructure:
- Gemini API (already integrated)
- LangChain (already in use)
- Prompt caching (already configured)

## Risk Mitigation

1. **LLM Hallucination**: Implement confidence thresholds and validation
2. **Cost Overruns**: Episode-level caching and batch processing
3. **Performance Impact**: Asynchronous processing option
4. **Privacy Concerns**: No storage of identified names outside knowledge graph