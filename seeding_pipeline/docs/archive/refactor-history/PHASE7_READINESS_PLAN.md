# Phase 7 Readiness Plan

## Overview
This document outlines the specific tasks required to make the codebase ready for Phase 7 (Orchestrator Integration). These fixes address the integration gaps identified in the Phase 1-6 validation.

## Critical Path Items (Must Complete)

### 1. Provider Factory Integration
**Priority: CRITICAL**
**Estimated Effort: 1 hour**

#### 1.1 Update Provider Registry
- [x] Add schemaless provider to `_default_providers` in `provider_factory.py`:
  ```python
  'graph': {
      'neo4j': 'src.providers.graph.neo4j.Neo4jProvider',
      'schemaless': 'src.providers.graph.schemaless_neo4j.SchemalessNeo4jProvider',
      'compatible': 'src.providers.graph.compatible_neo4j.CompatibleNeo4jProvider',
      'memory': 'src.providers.graph.memory.InMemoryGraphProvider'
  }
  ```

#### 1.2 Add Smart Provider Selection
- [x] Modify `create_graph_provider` to check config and auto-select:
  ```python
  def create_graph_provider(cls, provider_name: str, config: Dict[str, Any]) -> GraphProvider:
      # Override provider_name based on config
      if config.get('use_schemaless_extraction', False):
          if provider_name == 'neo4j':
              provider_name = 'schemaless'
              logger.info("Config has use_schemaless_extraction=True, using schemaless provider")
      
      return cls.create_provider('graph', provider_name, config)
  ```

### 2. Fix Metadata Enricher Constructor Mismatch
**Priority: CRITICAL**
**Estimated Effort: 30 minutes**

#### 2.1 Analyze Current Usage
- [x] Determine correct constructor signature by examining:
  - How `SchemalessNeo4jProvider` creates it: `SchemalessMetadataEnricher()`
  - How tests create it: `SchemalessMetadataEnricher(embedding_provider)`
  - What the class actually expects: `__init__(self, config: Optional[MetadataEnrichmentConfig] = None)`

#### 2.2 Choose Resolution Strategy
- [x] Option B: Update implementation to accept embedding provider (chosen - made constructor accept both config and embedding provider for compatibility)

#### 2.3 Apply Fix Consistently
- [x] Update all test files to use chosen constructor pattern
- [x] Update SchemalessNeo4jProvider initialization if needed
- [x] Ensure embedding functionality still works

### 3. Component Configuration Integration
**Priority: HIGH**
**Estimated Effort: 2 hours**

#### 3.1 Entity Resolution Threshold
- [x] Update `SchemalessEntityResolver.__init__` to accept config
- [x] Use `config.entity_resolution_threshold` in resolution logic
- [x] Default to 0.85 if not provided

#### 3.2 Confidence Threshold
- [x] Pass `config.schemaless_confidence_threshold` to components
- [x] Use in entity/relationship filtering
- [x] Document where threshold is applied

#### 3.3 Property Limits
- [x] Implement `max_properties_per_node` check in:
  - [x] Storage methods (in create_node)
- [x] Add warning logs when limit is exceeded

#### 3.4 Relationship Normalization
- [x] Use `config.relationship_normalization` in:
  - [x] SchemalessNeo4jProvider._normalize_relationship_type
  - [x] Result processing

### 4. Dependency Verification
**Priority: HIGH**
**Estimated Effort: 1 hour**

#### 4.1 Create Dependency Check Script
- [x] Create `scripts/check_schemaless_deps.py` that verifies:
  - [ ] neo4j-graphrag is installed
  - [ ] Correct version (>= 0.6.0)
  - [ ] SimpleKGPipeline can be imported
  - [ ] All adapters can be instantiated

#### 4.2 Update Import Error Handling
- [ ] Make import errors more informative in:
  - [ ] schemaless_poc.py
  - [ ] schemaless_neo4j.py
  - [ ] Adapter files
- [ ] Provide clear installation instructions in error messages

#### 4.3 Add to Setup/Requirements
- [ ] Add neo4j-graphrag to requirements.txt with correct version
- [ ] Update setup.py if needed
- [ ] Document installation steps

### 5. Create Minimal Integration Test
**Priority: HIGH**
**Estimated Effort: 2 hours**

#### 5.1 End-to-End Test Path
- [x] Create `tests/integration/test_minimal_schemaless.py`:
  - [ ] Create config with `use_schemaless_extraction: true`
  - [ ] Use provider factory to create schemaless provider
  - [ ] Process single segment through full pipeline
  - [ ] Verify all components are called
  - [ ] Check final output structure

#### 5.2 Component Integration Test
- [ ] Test that components work together:
  - [ ] Preprocessor → Pipeline → Entity Resolution → Enrichment → Storage
  - [ ] Verify data flows correctly between components
  - [ ] Check metadata is preserved

#### 5.3 Config-Based Provider Selection Test
- [ ] Test provider factory selects correct provider based on config
- [ ] Test both explicit and auto-selection modes
- [ ] Verify compatible mode works

## Non-Critical but Recommended

### 6. Documentation Updates
**Priority: MEDIUM**
**Estimated Effort: 1 hour**

#### 6.1 Update README
- [x] Add schemaless mode to main README
- [x] Include quick start example
- [x] Link to detailed documentation

#### 6.2 Create Integration Guide
- [ ] Document how components connect
- [ ] Show data flow diagram
- [ ] Include troubleshooting section

### 7. Logging and Monitoring
**Priority: MEDIUM**
**Estimated Effort: 1 hour**

#### 7.1 Add Mode Logging
- [x] Log when schemaless mode is activated
- [x] Log component initialization
- [x] Log config values being used

#### 7.2 Add Metrics
- [x] Track extraction times and entity/relationship counts
- [x] Log performance metrics periodically
- [x] Include metrics in response

### 8. Error Handling Improvements
**Priority: LOW**
**Estimated Effort: 1 hour**

#### 8.1 Graceful Fallbacks
- [x] If SimpleKGPipeline fails, try fallback extraction
- [x] If components fail, continue with partial data
- [x] Added fallback LLM-only extraction method

#### 8.2 Better Error Messages
- [ ] Include config values in error messages
- [ ] Suggest fixes for common problems
- [ ] Add error codes for tracking

## Validation Checklist

After completing the above tasks, verify:

### Integration Tests Pass
- [ ] `test_minimal_schemaless.py` runs successfully
- [ ] Provider factory creates correct provider type
- [ ] Config influences component behavior

### Component Wiring
- [ ] SchemalessNeo4jProvider initializes all components
- [ ] Components can access config values
- [ ] Data flows through full pipeline

### Dependencies
- [ ] neo4j-graphrag imports successfully
- [ ] All adapters can be created
- [ ] No import errors in normal operation

### Configuration
- [ ] use_schemaless_extraction triggers schemaless mode
- [ ] Thresholds are used by components
- [ ] All config values have effect

## Success Criteria

The implementation is ready for Phase 7 when:

1. **Provider Selection Works**
   ```python
   config = {"use_schemaless_extraction": True}
   provider = ProviderFactory.create_graph_provider("neo4j", config)
   assert isinstance(provider, SchemalessNeo4jProvider)
   ```

2. **End-to-End Processing Works**
   ```python
   provider = SchemalessNeo4jProvider(config)
   result = provider.process_segment_schemaless(segment, episode, podcast)
   assert result["status"] == "success"
   assert result["entities_extracted"] > 0
   ```

3. **Components Use Config**
   ```python
   config = {"entity_resolution_threshold": 0.9}
   resolver = SchemalessEntityResolver(config)
   # Resolution uses 0.9 threshold
   ```

4. **Tests Can Run**
   - At least one integration test passes
   - No import errors
   - Components initialize correctly

## Time Estimate

- Critical Path: 6-7 hours
- Recommended Items: 3 hours
- Total: 9-10 hours of focused work

## Risk Mitigation

1. **If neo4j-graphrag not available**: 
   - Create mock SimpleKGPipeline for testing
   - Document as experimental feature

2. **If integration too complex**:
   - Start with compatible mode only
   - Phase schemaless as experimental

3. **If time constrained**:
   - Do items 1-4 only (4 hours)
   - Defer integration test

## Next Steps After Completion

Once all critical items are complete:

1. Run validation checklist
2. Execute minimal integration test
3. Update SCHEMALESS_IMPLEMENTATION_PLAN.md with any learnings
4. Proceed to Phase 7 implementation

## Notes

- This plan focuses on making existing components work together
- No new functionality is added, only integration
- Phase 7 will handle orchestrator-specific integration
- Keep changes minimal and focused on integration