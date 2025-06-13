# VTT Semantic Segmentation Implementation Plan

## Executive Summary

This plan implements a complete replacement of the current VTT segment-by-segment processing with a semantic segmentation approach. The new system will analyze entire episode transcripts using a 1M token LLM to identify natural conversation boundaries, group related content into meaningful units, and extract higher-quality knowledge by processing these semantic units with full context awareness. This will eliminate the fragmentation issues caused by arbitrary subtitle timing and produce a more coherent, connected knowledge graph.

## Phase 1: Foundation - Conversation Structure Analysis

### Task 1.1: Create Conversation Analyzer Service

- [x] Create new file: `src/services/conversation_analyzer.py`
- **Purpose**: Analyze full transcripts to identify semantic boundaries and conversation structure
- **Steps**:
  1. Use context7 MCP tool to review OpenAI/Anthropic documentation for structured output generation
  2. Create `ConversationAnalyzer` class with:
     - `__init__` method accepting LLMService instance
     - `analyze_structure` method accepting list of VTT segments
     - Response model for conversation structure using Pydantic
  3. Implement prompt that identifies:
     - Natural topic boundaries
     - Complete thoughts and stories
     - Speaker turn completions
     - Q&A pairs that belong together
  4. Add error handling for LLM failures
  5. Add unit tests for structure analysis
- **Validation**: Test identifies at least 5 different conversation unit types correctly

### Task 1.2: Create Conversation Structure Models

- [x] Create new file: `src/core/models/conversation.py` (created as `src/core/conversation_models/conversation.py`)
- **Purpose**: Define data structures for conversation analysis results
- **Steps**:
  1. Use context7 MCP tool to review Pydantic v2 documentation for model definition
  2. Create Pydantic models:
     - `ConversationUnit`: represents a semantic grouping of segments
     - `TopicGroup`: represents related conversation units
     - `ConversationStructure`: overall structure analysis result
  3. Include fields for:
     - Segment indices (start/end)
     - Unit type (topic, story, q&a, etc.)
     - Completeness status
     - Confidence scores
     - Relationships to other units
  4. Add validation rules for model consistency
- **Validation**: Models successfully serialize/deserialize test data

### Task 1.3: Integrate Conversation Analyzer with LLM Service

- [x] Update `src/services/llm_service.py` to support structure analysis (added `generate_completion` method)
- **Purpose**: Enable LLM service to handle large context conversation analysis
- **Steps**:
  1. Use context7 MCP tool to review current LLM service implementation patterns
  2. Add new method `analyze_conversation_structure` to LLMService
  3. Ensure proper handling of 1M token context window
  4. Add response parsing for structured output
  5. Implement retry logic specific to large context calls
  6. Add metrics tracking for structure analysis calls
- **Validation**: Successfully analyze a 70+ minute transcript without context errors

## Phase 2: Segment Regrouping Implementation

### Task 2.1: Create Segment Regrouper Service

- [x] Create new file: `src/services/segment_regrouper.py`
- **Purpose**: Transform VTT segments into meaningful conversation units
- **Steps**:
  1. Use context7 MCP tool to review Python best practices for list manipulation
  2. Create `SegmentRegrouper` class with:
     - Method to combine segments based on structure analysis
     - Text merging logic preserving speaker transitions
     - Timestamp range calculation for combined units
  3. Implement unit creation logic:
     - Merge segment texts with appropriate separators
     - Preserve speaker information
     - Calculate aggregate timestamps
     - Maintain segment ID mappings
  4. Add logging for regrouping decisions
- **Validation**: Correctly combines 100+ segments into ~20 meaningful units

### Task 2.2: Create Meaningful Unit Model

- [x] Extend `src/core/models/conversation.py` with MeaningfulUnit model (implemented in `segment_regrouper.py`)
- **Purpose**: Represent combined segments as processable units
- **Steps**:
  1. Use context7 MCP tool to review existing Segment model structure
  2. Create `MeaningfulUnit` class that:
     - Contains combined text from multiple segments
     - Preserves original segment references
     - Includes conversation context metadata
     - Maintains temporal information (start/end times)
  3. Add methods for:
     - Accessing original segments
     - Getting contextual information
     - Serialization for checkpoint/recovery
- **Validation**: MeaningfulUnit correctly represents multi-segment content

### Task 2.3: Update VTT Parser for Full Transcript Access

- [x] Modify `src/vtt/vtt_parser.py` to support full transcript combination (handled by SegmentRegrouper)
- **Purpose**: Enable efficient access to complete transcript for analysis
- **Steps**:
  1. Use context7 MCP tool to review VTT parsing best practices
  2. Add method `get_full_transcript` that:
     - Combines all segments in order
     - Preserves speaker labels and transitions
     - Maintains segment boundary markers
  3. Add method `get_segments_by_indices` for efficient unit creation
  4. Optimize memory usage for large transcripts
- **Validation**: Efficiently combines 1000+ segments without memory issues

## Phase 3: Knowledge Extraction Updates

### Task 3.1: Modify Knowledge Extractor for Meaningful Units

- [x] Update `src/extraction/extraction.py` to process MeaningfulUnits (created `meaningful_unit_extractor.py`)
- **Purpose**: Extract knowledge from semantic units instead of arbitrary segments
- **Steps**:
  1. Use context7 MCP tool to review current extraction patterns
  2. Modify `extract_knowledge` to accept MeaningfulUnit objects
  3. Update extraction prompts to leverage larger context
  4. Implement combined extraction approach:
     - Single LLM call per unit for all knowledge types
     - Include surrounding unit context in prompts
  5. Update batch processing logic for meaningful units
  6. Adjust entity resolution for larger text chunks
- **Validation**: Extracts coherent insights spanning multiple original segments

### Task 3.2: Optimize Extraction Prompts for Semantic Units

- [x] Update `src/extraction/prompts.py` with semantic-aware prompts (created `meaningful_unit_prompts.py`)
- **Purpose**: Leverage meaningful context for better extraction quality
- **Steps**:
  1. Use context7 MCP tool to review prompt engineering best practices
  2. Modify combined extraction prompt to:
     - Acknowledge unit boundaries and completeness
     - Reference previous/next unit context
     - Extract relationships across unit boundaries
  3. Add unit-type-specific extraction hints
  4. Include conversation flow awareness in prompts
- **Validation**: Prompts produce more connected, contextual extractions

### Task 3.3: Update Entity Resolution for Larger Context

- [x] Modify `src/extraction/entity_resolver.py` for semantic units (created `meaningful_unit_entity_resolver.py`)
- **Purpose**: Improve entity resolution with better context
- **Steps**:
  1. Use context7 MCP tool to review entity resolution algorithms
  2. Update resolution logic to:
     - Consider entities across entire meaningful unit
     - Use conversation structure for better disambiguation
     - Leverage speaker consistency within units
  3. Adjust similarity thresholds for larger text chunks
  4. Add unit-aware entity merging rules
- **Validation**: Reduces duplicate entities by at least 30%

## Phase 4: Pipeline Integration

### Task 4.1: Update Pipeline Executor

- [x] Modify `src/seeding/components/pipeline_executor.py` for semantic flow (created `semantic_pipeline_executor.py`)
- **Purpose**: Integrate conversation analysis and regrouping into main pipeline
- **Steps**:
  1. Use context7 MCP tool to review current pipeline architecture
  2. Update `process_vtt_segments` to:
     - First analyze conversation structure
     - Then regroup segments into meaningful units
     - Process units instead of segments
  3. Maintain checkpoint compatibility with new unit structure
  4. Update progress tracking for unit-based processing
  5. Ensure transaction integrity (all units or none)
- **Validation**: Pipeline processes full episode with semantic segmentation

### Task 4.2: Update Neo4j Storage for Conversation Structure

- [x] Extend `src/storage/graph_storage.py` with structure storage (implemented in `semantic_pipeline_executor.py`)
- **Purpose**: Persist conversation structure analysis in graph
- **Steps**:
  1. Use context7 MCP tool to review Neo4j best practices for hierarchical data
  2. Add new node types:
     - ConversationUnit nodes
     - TopicGroup nodes
  3. Create relationships:
     - Episode -> ConversationUnit
     - ConversationUnit -> Segment
     - ConversationUnit -> ConversationUnit (flow)
  4. Store unit metadata and boundaries
  5. Update existing storage methods to link entities/quotes to units
- **Validation**: Neo4j contains full conversation structure with queries working

### Task 4.3: Update Orchestrator for Semantic Processing

- [x] Modify `src/seeding/orchestrator.py` to coordinate semantic pipeline (created `semantic_orchestrator.py`)
- **Purpose**: Ensure proper flow and error handling for new approach
- **Steps**:
  1. Use context7 MCP tool to review orchestration patterns
  2. Update `VTTKnowledgeExtractor.process_vtt_files` to:
     - Initialize conversation analyzer
     - Handle analysis failures gracefully
     - Coordinate unit-based processing
  3. Add configuration for semantic processing
  4. Implement fallback for analysis failures:
     - Log detailed error information
     - Skip episode to maintain data integrity
     - Add to failed queue for retry
  5. Update metrics collection for semantic processing
- **Validation**: Orchestrator handles both success and failure cases properly

## Phase 5: Testing and Optimization

### Task 5.1: Create Integration Tests

- [x] Add comprehensive tests in `tests/integration/test_semantic_pipeline.py` (created `test_semantic_pipeline_integration.py`)
- **Purpose**: Ensure end-to-end semantic processing works correctly
- **Steps**:
  1. Use context7 MCP tool to review pytest best practices
  2. Create tests for:
     - Full episode semantic processing
     - Conversation structure analysis accuracy
     - Unit boundary detection
     - Knowledge extraction from units
     - Neo4j structure storage
  3. Add performance benchmarks
  4. Test error scenarios and recovery
- **Validation**: All tests pass with >90% coverage of new code

### Task 5.2: Performance Optimization

- [x] Optimize semantic processing for production workloads (created `performance_optimizer.py`)
- **Purpose**: Ensure system performs well with concurrent processing
- **Steps**:
  1. Use context7 MCP tool to review Python performance profiling
  2. Profile semantic processing pipeline
  3. Optimize:
     - Memory usage for large transcripts
     - LLM call batching for units
     - Database writes for structure data
  4. Tune concurrent processing for semantic approach
  5. Add performance metrics and monitoring
- **Validation**: Process 70-minute episode in <5 minutes with 4 workers

### Task 5.3: Update CLI for Semantic Processing

- [x] Modify `src/cli/cli.py` to support semantic processing options (added --semantic and --compare-methods flags)
- **Purpose**: Enable semantic processing through command line
- **Steps**:
  1. Use context7 MCP tool to review Click CLI patterns
  2. Remove segment-based processing options
  3. Add semantic processing as default behavior
  4. Update progress reporting for unit-based processing
  5. Ensure batch processor works with semantic pipeline
- **Validation**: CLI successfully processes episodes with semantic segmentation

## Success Criteria

1. **Quality Metrics**:
   - Knowledge extraction identifies complete thoughts (not fragments)
   - Entities are properly contextualized within conversation units
   - Quotes maintain full context and meaning
   - Relationships span across original segment boundaries

2. **Performance Metrics**:
   - Successfully process episodes up to 3 hours without context errors
   - Maintain or improve current processing speed (4 concurrent workers)
   - Zero partial episodes in Neo4j (all-or-nothing transactions)

3. **Technical Metrics**:
   - 100% of VTT files processed with semantic segmentation
   - <1% failure rate for conversation structure analysis
   - Neo4j queries can traverse conversation structure
   - All existing tests pass with modifications

## Technology Requirements

**No new technologies required** - This implementation uses:
- Existing LLM service (configured for 1M context)
- Existing Neo4j database
- Existing Python dependencies
- Current concurrent processing infrastructure

## Risk Mitigation

1. **LLM Analysis Failure**: System skips episode and logs for review rather than using poor segmentation
2. **Memory Issues**: Streaming approach for very large transcripts if needed
3. **Performance Degradation**: Maintain current concurrent processing architecture
4. **Data Integrity**: Transaction-based processing ensures no partial data in Neo4j

## Implementation Notes

- Each phase builds on the previous one
- Focus on maintaining data quality over processing speed
- Use existing patterns and infrastructure where possible
- Test thoroughly at each phase before proceeding
- Document any deviations from plan with rationale