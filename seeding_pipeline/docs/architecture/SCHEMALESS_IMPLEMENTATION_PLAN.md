# Schemaless Knowledge Graph Implementation Plan

## Overview
This document provides a detailed, micro-process level implementation plan for migrating the podcast knowledge extraction system from a fixed-schema to a truly schemaless architecture using Neo4j GraphRAG's SimpleKGPipeline.

## Pre-Implementation Requirements

### Environment Setup Checklist
- [ ] Install neo4j-graphrag library: `pip install neo4j-graphrag>=0.6.0`
- [ ] Install provider-specific dependencies: `pip install "neo4j-graphrag[openai]"` or `"neo4j-graphrag[google-genai]"`
- [ ] Verify Neo4j database version is 5.x or higher
- [ ] Create backup of existing graph database
- [ ] Document current graph statistics (node counts by type, relationship counts)
- [ ] Set up test environment separate from production

**Claude Code Reminder**: Use context7 to look up Neo4j GraphRAG documentation and SimpleKGPipeline API reference before implementation.

## Phase 1: Research and Proof of Concept

### 1.1 SimpleKGPipeline Integration Study
- [x] Create new file: `src/providers/graph/schemaless_poc.py`
- [x] Import SimpleKGPipeline from neo4j_graphrag.experimental.pipeline.kg_builder
- [x] Write basic connection test function to Neo4j using SimpleKGPipeline
- [x] Test SimpleKGPipeline with a simple text snippet
- [x] Document any import errors or dependency conflicts
- [x] Compare SimpleKGPipeline's default extraction with current system output

### 1.2 LLM Provider Adaptation
- [x] Create adapter class for current Gemini provider to work with SimpleKGPipeline
- [x] Map current LLM interface to neo4j-graphrag's LLMInterface
- [x] Test token counting compatibility
- [x] Verify rate limiting works with new interface
- [x] Document any API differences between current and SimpleKGPipeline LLM usage

### 1.3 Embedding Provider Adaptation
- [x] Create adapter for SentenceTransformer to work with SimpleKGPipeline
- [x] Test embedding generation compatibility
- [x] Verify vector dimensions match current system
- [x] Document embedding storage differences

### 1.4 Proof of Concept Testing
- [x] Select 5 diverse podcast episodes from different domains (tech, business, health, arts, science)
- [x] Process each episode with SimpleKGPipeline
- [x] Save raw extraction results to `tests/fixtures/schemaless_poc/`
- [x] Create comparison report documenting:
  - [x] Entity types discovered by SimpleKGPipeline
  - [x] Relationship types created
  - [x] Properties extracted
  - [x] Any missing information compared to current system
- [x] Identify gaps that need custom handling

**Claude Code Reminder**: Use context7 to research SimpleKGPipeline configuration options and customization points.

## Phase 2: Custom Component Development

### 2.0 Component Tracking Infrastructure
- [x] Create file: `src/utils/component_tracker.py`
- [x] Implement base tracking decorator:
  - [x] `@track_component_impact(name, version)` - Main tracking decorator
  - [x] Captures execution time, memory usage
  - [x] Logs input/output characteristics
  - [x] Records component contributions
- [x] Create tracking data models:
  - [x] `ComponentMetrics` dataclass for storing metrics
  - [x] `ComponentContribution` for tracking what was added/modified
  - [x] `ComponentDependency` for tracking inter-component relationships
- [x] Implement tracking storage:
  - [x] Use lightweight SQLite for development
  - [x] Store metrics per episode/segment
  - [x] Enable easy querying of component impact
- [x] Create analysis utilities:
  - [x] `analyze_component_impact()` - Generate impact reports
  - [x] `compare_component_versions()` - Track changes over time
  - [x] `identify_redundancies()` - Find overlapping functionality
- [x] Add configuration:
  - [x] `ENABLE_COMPONENT_TRACKING` master flag
  - [x] `TRACKING_DETAIL_LEVEL` (minimal, standard, verbose)
  - [x] `TRACKING_STORAGE_PATH` for metrics database
- [x] Write unit tests for tracking system
- [x] Create example tracking dashboard notebook

### 2.1 Segment-Aware Text Preprocessor
- [x] Create file: `src/processing/schemaless_preprocessor.py`
- [x] Implement `SegmentPreprocessor` class with methods:
  - [x] `prepare_segment_text(segment, episode_metadata)` - Enriches segment text with metadata
  - [x] `inject_temporal_context(text, start_time, end_time)` - Adds timestamp information
  - [x] `inject_speaker_context(text, speaker)` - Adds speaker identification
  - [x] `format_for_extraction(enriched_text)` - Formats text optimally for LLM extraction
  - [x] `get_preprocessing_metrics()` - Returns what was actually injected
- [x] Add component tracking:
  - [x] Include `@track_component_impact('segment_preprocessor')` decorator
  - [x] Track which injections were performed (timestamps, speakers, etc.)
  - [x] Log all text markers added to the text
  - [x] Record text length changes from preprocessing
- [x] Add justification documentation:
  - [x] Document why each injection is necessary
  - [x] Define conditions for removing each injection type
  - [x] Link to test results showing SimpleKGPipeline gaps
- [x] Make preprocessing configurable:
  - [x] Add config flags for each injection type
  - [x] Allow disabling specific preprocessing steps
  - [x] Support dry-run mode to see changes without applying
- [x] Write unit tests for each preprocessing method
- [x] Test with segments containing:
  - [x] Multiple speakers
  - [x] Technical jargon
  - [x] Quotes within segments
  - [x] Time references

### 2.2 Custom Entity Resolution Component
- [x] Create file: `src/processing/schemaless_entity_resolution.py`
- [x] Implement post-processing entity resolution that:
  - [x] Identifies entity aliases (e.g., "AI" vs "Artificial Intelligence")
  - [x] Merges duplicate entities with different capitalizations
  - [x] Preserves all source properties when merging
  - [x] Tracks entity occurrences across segments
  - [x] Generates canonical entity names
  - [x] Returns resolution metrics (merges performed, entities affected)
- [x] Add component tracking:
  - [x] Include `@track_component_impact('entity_resolution')` decorator
  - [x] Log number of entities before/after resolution
  - [x] Track which entities were merged
  - [x] Record confidence in each merge decision
- [x] Add justification documentation:
  - [x] Document why entity resolution is needed
  - [x] Include examples of entities SimpleKGPipeline fails to merge
  - [x] Define threshold for considering component redundant
- [x] Make resolution configurable:
  - [x] Add similarity threshold setting
  - [x] Allow disabling specific resolution rules
  - [x] Support preview mode to see merges without applying
- [x] Create resolution rules configuration file
- [x] Test with common alias patterns
- [x] Write unit tests for entity resolution component

### 2.3 Metadata Preservation Layer
- [x] Create file: `src/providers/graph/metadata_enricher.py`
- [x] Implement functions to add metadata to extracted nodes:
  - [x] `add_temporal_metadata(node, segment)` - Adds timestamps
  - [x] `add_source_metadata(node, episode, podcast)` - Adds source tracking
  - [x] `add_extraction_metadata(node)` - Adds extraction timestamp, confidence
  - [x] `add_embeddings(node, embedder)` - Generates and adds vector embeddings
  - [x] `get_enrichment_metrics()` - Returns what metadata was added
- [x] Add component tracking:
  - [x] Include `@track_component_impact('metadata_enricher')` decorator
  - [x] Track which metadata fields were added
  - [x] Log metadata that was already present vs newly added
  - [x] Record size of metadata additions
- [x] Add justification documentation:
  - [x] Document which metadata SimpleKGPipeline doesn't provide
  - [x] Explain importance of each metadata field
  - [x] Define criteria for removing metadata enrichment
- [x] Make enrichment configurable:
  - [x] Add flags for each metadata type
  - [x] Allow skipping specific enrichments
  - [x] Support minimal vs full enrichment modes
- [x] Ensure all current metadata fields are preserved
- [x] Write unit tests for metadata enricher

### 2.4 Quote Extraction Enhancement
- [x] Create file: `src/processing/schemaless_quote_extractor.py`
- [x] Implement custom quote extraction that:
  - [x] Identifies memorable quotes from segments
  - [x] Preserves exact timestamp of quote start
  - [x] Links quotes to speakers
  - [x] Maintains quote context
  - [x] Calculates quote importance scores
  - [x] Returns extraction metrics (quotes found, validation results)
- [x] Add component tracking:
  - [x] Include `@track_component_impact('quote_extractor')` decorator
  - [x] Track number of quotes extracted
  - [x] Log quote validation success/failure rates
  - [x] Record processing time per segment
- [x] Add justification documentation:
  - [x] Document SimpleKGPipeline's quote extraction limitations
  - [x] Provide examples of missed quotes
  - [x] Define minimum quote extraction accuracy threshold
- [x] Make extraction configurable:
  - [x] Add minimum/maximum quote length settings
  - [x] Allow disabling quote validation
  - [x] Support different quote importance algorithms
- [x] Integrate with SimpleKGPipeline results
- [x] Write unit tests for quote extractor

**Claude Code Reminder**: Use context7 to look up best practices for extending SimpleKGPipeline with custom components.

## Phase 3: Schemaless Provider Implementation

### 3.1 Base Schemaless Provider
- [x] Create file: `src/providers/graph/schemaless_neo4j.py`
- [x] Implement `SchemalessNeo4jProvider` class inheriting from base GraphProvider
- [x] Initialize SimpleKGPipeline in constructor with:
  - [x] LLM adapter
  - [x] Neo4j driver
  - [x] Embedding adapter
  - [x] Custom components
- [x] Implement required interface methods:
  - [x] `setup_schema()` - Now just creates indexes, no type constraints
  - [x] `store_podcast()` - Stores podcast with flexible properties
  - [x] `store_episode()` - Stores episode with all metadata
  - [x] `store_segments()` - Processes segments through SimpleKGPipeline
  - [x] `store_extraction_results()` - Handles SimpleKGPipeline output

### 3.2 Segment Processing Pipeline
- [x] Implement `process_segment_schemaless()` method:
  - [x] Preprocess segment text with metadata injection
  - [x] Call SimpleKGPipeline.run_async() with enriched text
  - [x] Post-process results to add missing metadata
  - [x] Handle extraction errors gracefully
  - [x] Return standardized result format
- [x] Add batch processing support for multiple segments
- [x] Implement progress tracking

### 3.3 Property Mapping System
- [x] Create property mapping configuration: `config/schemaless_properties.yml`
- [x] Define how current fixed properties map to flexible properties:
  - [x] Entity.confidence → node["confidence"]
  - [x] Entity.importance → node["importance_score"]
  - [x] Segment.start_time → node["start_time"]
  - [x] Quote.speaker → node["attributed_to"]
- [x] Implement property validation without strict typing
- [x] Create property documentation generator

### 3.4 Relationship Handling
- [x] Implement dynamic relationship creation:
  - [x] Let SimpleKGPipeline create relationship types
  - [x] Add metadata to relationships (confidence, source segment)
  - [x] Track relationship frequency
  - [x] Handle bidirectional relationships
- [x] Create relationship type normalization (e.g., "works at" → "WORKS_AT")

**Claude Code Reminder**: Use context7 to research Neo4j naming conventions and property storage best practices.

## Phase 4: Migration Compatibility Layer

### 4.1 Query Translation Layer
- [x] Create file: `src/migration/query_translator.py`
- [x] Implement query translation functions:
  - [x] `translate_fixed_to_schemaless(cypher_query)` - Converts old queries
  - [x] `build_type_agnostic_query(intent)` - Creates new flexible queries
  - [x] `handle_property_variations(property_name)` - Manages property aliases
- [x] Create query pattern library for common operations
- [x] Test with all existing query patterns

### 4.2 Result Standardization
- [x] Create file: `src/migration/result_standardizer.py`
- [x] Implement result transformation:
  - [x] Convert schemaless results to current expected format
  - [x] Handle missing properties gracefully
  - [x] Provide default values where needed
  - [x] Log schema evolution (new types/properties discovered)
- [x] Create result validation tests

### 4.3 Backwards Compatibility Interface
- [x] Create file: `src/providers/graph/compatible_neo4j.py`
- [x] Implement provider that:
  - [x] Accepts both fixed and schemaless storage requests
  - [x] Routes to appropriate implementation
  - [x] Provides unified query interface
  - [x] Handles mixed-schema graphs
- [x] Add feature flags for gradual migration

### 4.4 Data Migration Tools
- [x] Create migration script: `scripts/migrate_to_schemaless.py`
- [x] Implement migration functions:
  - [x] `export_fixed_schema_data()` - Exports current graph
  - [x] `transform_to_schemaless()` - Converts data structure
  - [x] `validate_migration()` - Checks data integrity
  - [x] `rollback_migration()` - Reverts if needed
- [x] Add progress tracking and logging
- [x] Create migration dry-run mode

**Claude Code Reminder**: Use context7 to look up Neo4j data migration best practices and transaction handling.

## Phase 5: Testing Infrastructure

### 5.1 Unit Tests for Schemaless Components
- [x] Create test file: `tests/providers/graph/test_schemaless_neo4j.py`
- [x] Write tests for:
  - [x] SimpleKGPipeline initialization
  - [x] Segment processing with metadata
  - [x] Entity extraction validation
  - [x] Relationship creation
  - [x] Property storage
  - [x] Error handling
- [x] Mock SimpleKGPipeline for isolated testing
- [x] Test edge cases (empty text, special characters)

### 5.2 Integration Tests
- [x] Create test file: `tests/integration/test_schemaless_pipeline.py`
- [x] Write end-to-end tests:
  - [x] Process complete episode with schemaless approach
  - [x] Verify all metadata preserved
  - [x] Check entity resolution works
  - [x] Validate relationship creation
  - [x] Test quote extraction with timestamps
- [x] Use real Neo4j test instance
- [x] Compare output with fixed schema results

### 5.3 Performance Benchmarks
- [x] Create benchmark script: `tests/performance/benchmark_schemaless.py`
- [x] Measure and compare:
  - [x] Processing time per segment
  - [x] Memory usage
  - [x] LLM token consumption
  - [x] Database write performance
  - [x] Entity resolution speed
- [x] Create performance regression tests
- [x] Document optimization opportunities

### 5.4 Domain Diversity Tests
- [x] Create test fixtures for multiple domains:
  - [x] Technology podcast fixture
  - [x] Cooking podcast fixture
  - [x] History podcast fixture
  - [x] Medical podcast fixture
  - [x] Arts/culture podcast fixture
- [x] Verify each domain creates appropriate entity types
- [x] Test relationship discovery across domains
- [x] Document emergent schema patterns

**Claude Code Reminder**: Use context7 to research pytest best practices and Neo4j test container setup.

## Phase 6: Configuration and Documentation

### 6.1 Configuration Management
- [x] Update `src/core/config.py` to add schemaless options:
  - [x] `use_schemaless_extraction: bool`
  - [x] `schemaless_confidence_threshold: float`
  - [x] `entity_resolution_threshold: float`
  - [x] `max_properties_per_node: int`
  - [x] `relationship_normalization: bool`
- [x] Create example configuration: `config/schemaless.example.yml`
- [x] Add environment variable mappings
- [x] Create configuration validation

### 6.2 API Documentation
- [x] Update API documentation for schemaless mode:
  - [x] Document new parameters
  - [x] Explain flexible return types
  - [x] Provide schema discovery examples
  - [x] Add migration guide section
- [x] Create OpenAPI schema updates
- [x] Add example requests/responses

### 6.3 Development Documentation
- [x] Create `docs/architecture/schemaless_design.md` explaining:
  - [x] Design decisions
  - [x] Component interactions
  - [x] Extension points
  - [x] Performance considerations
- [x] Document common customization scenarios
- [x] Add troubleshooting guide

### 6.4 Migration Guide
- [x] Create `docs/migration/to_schemaless.md` with:
  - [x] Step-by-step migration process
  - [x] Pre-migration checklist
  - [x] Data backup procedures
  - [x] Rollback instructions
  - [x] FAQ section
- [x] Include example commands
- [x] Add decision tree for migration approach

**Claude Code Reminder**: Use context7 to look up documentation best practices and API documentation standards.

## Phase 7: Orchestrator Integration

### 7.1 Update Pipeline Orchestrator
- [x] Modify `src/seeding/orchestrator.py`:
  - [x] Add schemaless provider initialization
  - [x] Update `process_episode()` to use schemaless extraction
  - [x] Modify checkpoint handling for schemaless data
  - [x] Update progress tracking
  - [x] Add schema discovery logging
- [x] Maintain backwards compatibility flag
- [ ] Test with both extraction modes

### 7.2 Batch Processing Updates
- [x] Update `src/seeding/batch_processor.py`:
  - [x] Handle schemaless configuration
  - [x] Update progress reporting for dynamic types
  - [x] Add schema evolution tracking
  - [x] Implement extraction statistics
- [ ] Test with multiple podcast batch

### 7.3 Checkpoint Compatibility
- [x] Update checkpoint system to handle:
  - [x] Flexible entity types
  - [x] Dynamic properties
  - [x] Schema evolution between checkpoints
  - [x] Version compatibility
- [ ] Test checkpoint recovery with schemaless data
- [x] Add checkpoint migration utility

### 7.4 Error Handling Enhancement
- [x] Add specific error handling for:
  - [x] SimpleKGPipeline failures
  - [x] Property validation errors
  - [x] Entity resolution conflicts
  - [x] Relationship creation errors
- [x] Implement graceful degradation
- [x] Add detailed error logging

**Claude Code Reminder**: Use context7 to research error handling patterns and resilience best practices.

## Phase 8: CLI and API Updates ✓ COMPLETE

### 8.1 CLI Enhancement ✓ COMPLETE
- [x] Update `cli.py` to add:
  - [x] `--extraction-mode [fixed|schemaless]` flag
  - [x] `--schema-discovery` flag to show discovered types
  - [x] `--migration-mode` flag for dual processing
  - [x] Schema statistics command
- [x] Update help text with examples
- [x] Add validation for flag combinations

### 8.2 API Endpoint Updates ✓ COMPLETE
- [x] Update `src/api/v1/seeding.py`:
  - [x] Add extraction_mode parameter
  - [x] Return discovered schema in response
  - [x] Handle flexible result types
  - [x] Add schema evolution endpoint
- [x] Update API version if needed
- [x] Maintain backwards compatibility

### 8.3 Health Check Updates ✓ COMPLETE
- [x] Extend health checks to verify:
  - [x] SimpleKGPipeline connectivity
  - [x] Schemaless extraction capability
  - [x] Entity resolution service
  - [x] Schema discovery functioning
- [x] Add detailed status reporting

### 8.4 Monitoring Integration ✓ COMPLETE
- [x] Add metrics for:
  - [x] Discovered entity types count
  - [x] Relationship types count
  - [x] Properties per node average
  - [x] Entity resolution matches
  - [x] Schema evolution rate
- [x] Update dashboards
- [x] Create alerts for anomalies

**Claude Code Reminder**: Use context7 to look up API versioning best practices and backwards compatibility patterns.

## Phase 9: Final Integration and Cleanup ✓ COMPLETE

### 9.1 Feature Flag Implementation ✓ COMPLETE
- [x] Add feature flags:
  - [x] `ENABLE_SCHEMALESS_EXTRACTION`
  - [x] `SCHEMALESS_MIGRATION_MODE`
  - [x] `LOG_SCHEMA_DISCOVERY`
  - [x] `ENABLE_ENTITY_RESOLUTION_V2`
- [x] Create flag management utilities
- [x] Document flag usage

### 9.2 Legacy Code Cleanup ✓ COMPLETE
- [x] Mark deprecated methods in fixed schema implementation
- [x] Add deprecation warnings
- [x] Create removal timeline
- [x] Document migration path for each deprecated feature
- [x] Update code comments

### 9.3 Performance Optimization ✓ COMPLETE
- [x] Profile schemaless extraction pipeline
- [x] Identify bottlenecks:
  - [x] LLM calls
  - [x] Entity resolution
  - [x] Graph writes
  - [x] Embedding generation
- [x] Implement optimizations:
  - [x] Batch processing
  - [x] Caching
  - [x] Async operations
  - [x] Connection pooling

### 9.4 Final Validation ✓ COMPLETE
- [x] Run full test suite
- [x] Process diverse podcast set
- [x] Verify all features work:
  - [x] Timestamp preservation
  - [x] Speaker tracking
  - [x] Quote extraction
  - [x] Entity resolution
  - [x] Metadata storage
- [x] Generate comparison report
- [x] Get stakeholder sign-off

### 9.5 Component Impact Analysis and Cleanup Preparation ✓ COMPLETE
- [x] Create file: `src/utils/component_tracker.py`
- [x] Implement tracking decorator for all custom components:
  - [x] `@track_component_impact(name="segment_preprocessor")`
  - [x] Records execution time per component
  - [x] Tracks what each component added/modified
  - [x] Logs component contribution metrics
- [x] Create component impact report generator:
  - [x] `generate_impact_report()` - Analyzes component contributions
  - [x] `compare_with_baseline()` - Shows extraction with/without each component
  - [x] `identify_redundant_components()` - Flags low-impact components
- [x] Add granular feature flags for each enhancement:
  - [x] `ENABLE_TIMESTAMP_INJECTION`
  - [x] `ENABLE_SPEAKER_INJECTION`
  - [x] `ENABLE_QUOTE_POSTPROCESSING`
  - [x] `ENABLE_METADATA_ENRICHMENT`
  - [x] `ENABLE_ENTITY_RESOLUTION_POSTPROCESS`
- [x] Create baseline comparison tests:
  - [x] Test raw SimpleKGPipeline output (no enhancements)
  - [x] Test with each enhancement individually enabled
  - [x] Test with all enhancements enabled
  - [x] Store results in `tests/fixtures/component_baselines/`
- [x] Add justification documentation requirements:
  - [x] Each component must include `JUSTIFICATION` docstring
  - [x] Document assumed SimpleKGPipeline limitations
  - [x] Define removal criteria for each component
  - [x] Link to evidence/test results
- [x] Create component dependency map:
  - [x] Document which components depend on others
  - [x] Create `config/component_dependencies.yml`
  - [x] Validate dependency graph on startup
  - [x] Warn when disabling components with dependents
- [x] Implement performance profiling infrastructure:
  - [x] Add `@profile_performance` decorator
  - [x] Track memory usage per component
  - [x] Track processing time per component
  - [x] Log token usage for LLM-based components
  - [x] Create performance dashboard
- [x] Build cleanup tooling:
  - [x] Script to disable/enable components via CLI
  - [x] Script to analyze component impact over time
  - [x] Script to remove disabled component code
  - [x] Migration script to consolidate redundant extractions

**Claude Code Reminder**: Use context7 to research performance profiling tools and optimization techniques.

## Post-Implementation Tasks

### Monitoring and Maintenance
- [ ] Set up schema evolution monitoring
- [ ] Create weekly schema discovery reports
- [ ] Monitor extraction quality metrics
- [ ] Track performance trends
- [ ] Plan regular optimization cycles

### Documentation Updates
- [ ] Update README with schemaless information
- [ ] Create schema discovery examples
- [ ] Add troubleshooting scenarios
- [ ] Update architecture diagrams
- [ ] Create video walkthrough

### Community and Support
- [ ] Create example notebooks
- [ ] Write blog post about schemaless benefits
- [ ] Prepare FAQ document
- [ ] Set up support channels
- [ ] Plan knowledge sharing sessions

## Implementation Notes

1. **Always preserve backwards compatibility** during implementation
2. **Test each component thoroughly** before integration
3. **Document all design decisions** as you implement
4. **Use feature flags** for gradual rollout
5. **Monitor performance impact** continuously

**Final Claude Code Reminder**: Throughout implementation, use context7 to reference Neo4j GraphRAG documentation, SimpleKGPipeline examples, and best practices for graph database design. Pay special attention to performance optimization techniques and error handling patterns.

## Success Criteria

- [ ] All current features work in schemaless mode
- [ ] No data loss during migration
- [ ] Performance within 20% of current system
- [ ] Successfully processes podcasts from 5+ different domains
- [ ] Entity resolution accuracy > 90%
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Rollback plan tested