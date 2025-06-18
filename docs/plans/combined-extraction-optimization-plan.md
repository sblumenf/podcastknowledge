# Combined Extraction Optimization Implementation Plan

## Executive Summary

This plan transforms the knowledge extraction pipeline from making 155 separate LLM calls to 31 combined calls, reducing processing time from 90 minutes to approximately 40-45 minutes per podcast episode. Each MeaningfulUnit will be processed with a single, comprehensive extraction call that returns entities, quotes, insights, relationships, and sentiment analysis in one response.

## Technology Requirements

**No new technologies required** - Uses existing:
- Gemini 2.5 Flash and Pro models
- Existing Neo4j database
- Current Python dependencies

## Phase 0: Critical Pre-fixes (2 hours)

### Task 0.1: Fix Validation Constraints
- [ ] Remove unnecessary character limits that cause retries
  - **Purpose**: Eliminate validation failures that double processing time
  - **Steps**:
    1. Open `src/core/conversation_models/conversation.py`
    2. Find all Field definitions with max_length constraints
    3. Remove max_length from description and summary fields
    4. Change unit overlap validation from `>=` to `>` (adjacent units aren't overlapping)
    5. Run quick test to ensure no validation errors
  - **Validation**: Can process test transcript without validation retries

### Task 0.2: Remove MetricsCollector Errors
- [ ] Fix or remove broken metrics collection
  - **Purpose**: Clean up logs and prevent confusion
  - **Steps**:
    1. Search for `processing_duration` in codebase: `grep -r "processing_duration" src/`
    2. Comment out or fix the line causing AttributeError
    3. If metrics not critical, remove entirely (KISS principle)
  - **Validation**: No MetricsCollector errors in test run logs

### Task 0.3: Fix Speaker Identification
- [ ] Ensure real speaker names are identified
  - **Purpose**: Critical for knowledge graph value - no generic "Speaker 0"
  - **Steps**:
    1. Use context7 MCP tool to review speaker identification best practices
    2. Open `src/vtt/vtt_segmentation.py`
    3. Review speaker identification prompt
    4. Add explicit instruction: "NEVER return generic names like 'Speaker 1'. Always identify actual names or roles."
    5. Add validation to reject generic speaker names
    6. Test with sample transcript
  - **Validation**: Test returns actual names like "Mel Robbins" not "Speaker 0"

### Task 0.4: Fix Timeout Configuration
- [ ] Make pipeline timeout configurable and reasonable
  - **Purpose**: Prevent timeout failures on normal processing
  - **Steps**:
    1. Find hardcoded 20-minute timeout in pipeline
    2. Replace with environment variable: `PIPELINE_TIMEOUT = int(os.getenv('PIPELINE_TIMEOUT', 5400))  # 90 min default`
    3. Update .env.example with new variable
  - **Validation**: Pipeline can run for full 90 minutes without timeout

## Phase 1: Analysis and Preparation (Day 1)

### Task 1.1: Document Current Extraction Flow
- [ ] Map exact code paths for all 5 extraction types
  - **Purpose**: Understand every detail of current implementation
  - **Steps**:
    1. Use context7 MCP tool to review Gemini documentation for best practices
    2. Open `src/extraction/extraction.py` 
    3. Document each extraction method's inputs/outputs in a temp file
    4. Trace the call flow from `extract_knowledge()` through each sub-method
    5. Note all prompt templates currently used
  - **Validation**: Temp file contains all 5 extraction methods documented with their prompts

### Task 1.2: Analyze Current Output Formats
- [ ] Capture exact JSON structure for each extraction type
  - **Purpose**: Ensure combined extraction maintains exact output format
  - **Steps**:
    1. Run `grep -n "return.*Result" src/extraction/extraction.py` to find return points
    2. Document the exact dictionary/JSON structure for:
       - Entities structure
       - Quotes structure  
       - Insights structure
       - Relationships structure
       - Sentiment structure
    3. Create `temp/output_formats.json` with examples of each
  - **Validation**: Can recreate exact current output format from documentation

### Task 1.3: Identify Model Selection Logic
- [ ] Document how Flash vs Pro model decisions are made
  - **Purpose**: Implement smart model selection in combined approach
  - **Steps**:
    1. Search for model selection in `src/pipeline/unified_pipeline.py`
    2. Find unit type classifications (introduction, conclusion, etc.)
    3. Create decision matrix: unit_type → model mapping
    4. Document in `temp/model_selection_rules.md`
  - **Validation**: Clear rules for when to use Flash vs Pro

## Phase 2: Design Combined Extraction (Day 1-2)

### Task 2.1: Create Combined Prompt Template
- [ ] Design single prompt that extracts all 5 types efficiently
  - **Purpose**: Core of the optimization - one prompt to rule them all
  - **Steps**:
    1. Use context7 MCP tool to check Gemini prompt best practices
    2. Create prompt structure:
       ```
       - Context about the unit (type, themes, duration)
       - Clear sections for each extraction type
       - Explicit JSON schema for response
       - Examples for each type
       ```
    3. Write prompt template in `temp/combined_prompt_v1.md`
    4. Include token count estimate
  - **Validation**: Prompt clearly requests all 5 extraction types with examples

### Task 2.2: Design Response Parser
- [ ] Create parsing logic for combined JSON response
  - **Purpose**: Cleanly separate combined response into individual components
  - **Steps**:
    1. Design JSON schema that includes all 5 types
    2. Create parsing pseudocode:
       ```python
       def parse_combined_response(json_response):
           return {
               'entities': json_response.get('entities', []),
               'quotes': json_response.get('quotes', []),
               # etc...
           }
       ```
    3. Add error handling for missing sections
    4. Document in `temp/parser_design.py`
  - **Validation**: Parser handles all valid responses and common error cases

### Task 2.3: Plan Refactoring Steps
- [ ] Create detailed refactoring checklist
  - **Purpose**: Ensure smooth transition without breaking existing code
  - **Steps**:
    1. List all methods that need modification
    2. Identify integration points with pipeline
    3. Create backup strategy for existing methods
    4. Document order of changes in `temp/refactoring_steps.md`
  - **Validation**: Every current extraction call point is addressed

## Phase 3: Implementation (Day 2-3)

### Task 3.1: Create Combined Extraction Method
- [ ] Implement `_extract_all_knowledge_combined()` method
  - **Purpose**: Single method that replaces 5 separate extraction calls
  - **Steps**:
    1. Use context7 MCP tool to review async best practices for Gemini
    2. In `src/extraction/extraction.py`, add new method:
       ```python
       async def _extract_all_knowledge_combined(self, meaningful_unit, model_name='gemini-2.5-flash'):
           # Implementation here
       ```
    3. Implement prompt building with unit context
    4. Add LLM call with appropriate model
    5. Implement response parsing
    6. Add comprehensive error handling
  - **Validation**: Method successfully extracts all 5 types in test call

### Task 3.2: Create Model Selection Logic
- [ ] Implement smart Flash vs Pro selection
  - **Purpose**: Use expensive Pro model only where needed
  - **Steps**:
    1. Add method to determine model based on unit type:
       ```python
       def _select_model_for_unit(self, unit):
           important_types = ['introduction', 'conclusion', 'key_moment']
           return 'pro' if unit.unit_type in important_types else 'flash'
       ```
    2. Pass selected model to combined extraction
    3. Add logging for model selection decisions
  - **Validation**: Logs show Flash used for ~70% of units, Pro for ~30%

### Task 3.3: Modify Main Extraction Flow
- [ ] Update `extract_knowledge()` to use combined approach
  - **Purpose**: Integration point for new combined extraction
  - **Steps**:
    1. Backup current `extract_knowledge()` method (comment out)
    2. Modify method to:
       - Call `_extract_all_knowledge_combined()`
       - Parse combined response
       - Maintain existing return format
    3. Ensure all existing functionality preserved
    4. Add timing logs to measure improvement
  - **Validation**: Method returns exact same format as before

### Task 3.4: Update Pipeline Integration
- [ ] Modify pipeline to handle integrated sentiment
  - **Purpose**: Include sentiment in combined call, not separate
  - **Steps**:
    1. Use context7 MCP tool for pipeline architecture patterns
    2. In `src/pipeline/unified_pipeline.py`, find sentiment analysis call
    3. Remove separate sentiment analyzer call
    4. Ensure sentiment data flows from combined extraction
    5. Update result aggregation logic
  - **Validation**: Pipeline processes episode without calling sentiment analyzer

## Phase 4: Testing and Validation (Day 3-4)

### Task 4.1: Create Test Harness
- [ ] Build comparison testing framework
  - **Purpose**: Validate optimization maintains quality
  - **Steps**:
    1. Create `test/compare_extractions.py` script
    2. Implement side-by-side extraction comparison
    3. Add metrics for:
       - Extraction counts (entities, quotes, etc.)
       - Processing time per unit
       - Token usage
       - Model selection distribution
    4. Output results to `test/comparison_results.json`
  - **Validation**: Can run both old and new extraction on same content

### Task 4.2: Process Test Episode
- [ ] Run full pipeline on test episode
  - **Purpose**: End-to-end validation of optimization
  - **Steps**:
    1. Select test episode from `input/` directory
    2. Run extraction with detailed logging enabled
    3. Monitor for:
       - Successful completion
       - Time reduction (target: 40-45 minutes)
       - No errors or retries
       - All extraction types present
    4. Save results to `test/optimized_run_results.json`
  - **Validation**: Episode processes in <45 minutes with all data extracted

### Task 4.3: Validate Output Quality
- [ ] Spot-check extraction quality
  - **Purpose**: Ensure combined extraction maintains standards
  - **Steps**:
    1. Randomly select 5 MeaningfulUnits from test
    2. Manually review:
       - Entity coverage (80%+ of important entities)
       - Quote accuracy (exact text matches)
       - Insight quality (meaningful, not generic)
       - Relationship validity
       - Sentiment alignment with content
    3. Document findings in `test/quality_check.md`
  - **Validation**: Quality meets or exceeds current approach

## Phase 5: Cleanup and Documentation (Day 4)

### Task 5.1: Remove Old Code Paths
- [ ] Clean up superseded extraction methods
  - **Purpose**: Maintain clean, simple codebase (KISS principle)
  - **Steps**:
    1. Delete or comment out old individual extraction methods
    2. Remove unused imports
    3. Update method documentation
    4. Ensure no dead code remains
  - **Validation**: Code coverage shows no unreachable code

### Task 5.2: Update Documentation
- [ ] Document new extraction flow
  - **Purpose**: Maintain clear documentation for future maintenance
  - **Steps**:
    1. Update docstrings for all modified methods
    2. Create `docs/extraction_optimization.md` explaining:
       - What changed and why
       - Performance improvements
       - How combined extraction works
    3. Update any existing architecture diagrams
  - **Validation**: New developer can understand flow from docs

### Task 5.3: Performance Report
- [ ] Create final performance analysis
  - **Purpose**: Document achieved improvements
  - **Steps**:
    1. Analyze logs from test runs
    2. Create report showing:
       - Old: 155 calls, 90 minutes, X tokens
       - New: 31 calls, Y minutes, Z tokens
       - Cost savings calculation
    3. Save as `docs/optimization_results.md`
  - **Validation**: Shows 50%+ time reduction achieved

## Success Criteria

1. **Performance**: Pipeline processes episodes in 40-45 minutes (down from 90)
2. **Efficiency**: Exactly 31 LLM calls per episode (down from 155)
3. **Quality**: Maintains 90%+ extraction quality vs current approach
4. **Simplicity**: Codebase is simpler with fewer methods and clearer flow
5. **Cost**: 50%+ reduction in API costs due to fewer calls
6. **Reliability**: No validation retries, no timeout failures, real speaker names identified
7. **Clean Logs**: No MetricsCollector errors or unnecessary error spam

## Rollback Strategy

If issues arise:
1. Git revert to commit before optimization
2. Restart services
3. Process any failed episodes with old pipeline
4. Investigate issues before re-attempting

## Risk Mitigation

- **Risk**: Combined prompt too complex
  - **Mitigation**: Test prompt iterations on small samples first
  
- **Risk**: Response parsing failures
  - **Mitigation**: Comprehensive error handling with fallbacks

- **Risk**: Quality degradation
  - **Mitigation**: A/B test results before full deployment