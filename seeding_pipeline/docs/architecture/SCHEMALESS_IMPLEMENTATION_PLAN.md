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
- [ ] Create new file: `src/providers/graph/schemaless_poc.py`
- [ ] Import SimpleKGPipeline from neo4j_graphrag.experimental.pipeline.kg_builder
- [ ] Write basic connection test function to Neo4j using SimpleKGPipeline
- [ ] Test SimpleKGPipeline with a simple text snippet
- [ ] Document any import errors or dependency conflicts
- [ ] Compare SimpleKGPipeline's default extraction with current system output

### 1.2 LLM Provider Adaptation
- [ ] Create adapter class for current Gemini provider to work with SimpleKGPipeline
- [ ] Map current LLM interface to neo4j-graphrag's LLMInterface
- [ ] Test token counting compatibility
- [ ] Verify rate limiting works with new interface
- [ ] Document any API differences between current and SimpleKGPipeline LLM usage

### 1.3 Embedding Provider Adaptation
- [ ] Create adapter for SentenceTransformer to work with SimpleKGPipeline
- [ ] Test embedding generation compatibility
- [ ] Verify vector dimensions match current system
- [ ] Document embedding storage differences

### 1.4 Proof of Concept Testing
- [ ] Select 5 diverse podcast episodes from different domains (tech, business, health, arts, science)
- [ ] Process each episode with SimpleKGPipeline
- [ ] Save raw extraction results to `tests/fixtures/schemaless_poc/`
- [ ] Create comparison report documenting:
  - [ ] Entity types discovered by SimpleKGPipeline
  - [ ] Relationship types created
  - [ ] Properties extracted
  - [ ] Any missing information compared to current system
- [ ] Identify gaps that need custom handling

**Claude Code Reminder**: Use context7 to research SimpleKGPipeline configuration options and customization points.

## Phase 2: Custom Component Development

### 2.1 Segment-Aware Text Preprocessor
- [ ] Create file: `src/processing/schemaless_preprocessor.py`
- [ ] Implement `SegmentPreprocessor` class with methods:
  - [ ] `prepare_segment_text(segment, episode_metadata)` - Enriches segment text with metadata
  - [ ] `inject_temporal_context(text, start_time, end_time)` - Adds timestamp information
  - [ ] `inject_speaker_context(text, speaker)` - Adds speaker identification
  - [ ] `format_for_extraction(enriched_text)` - Formats text optimally for LLM extraction
- [ ] Write unit tests for each preprocessing method
- [ ] Test with segments containing:
  - [ ] Multiple speakers
  - [ ] Technical jargon
  - [ ] Quotes within segments
  - [ ] Time references

### 2.2 Custom Entity Resolution Component
- [ ] Create file: `src/processing/schemaless_entity_resolution.py`
- [ ] Implement post-processing entity resolution that:
  - [ ] Identifies entity aliases (e.g., "AI" vs "Artificial Intelligence")
  - [ ] Merges duplicate entities with different capitalizations
  - [ ] Preserves all source properties when merging
  - [ ] Tracks entity occurrences across segments
  - [ ] Generates canonical entity names
- [ ] Create resolution rules configuration file
- [ ] Test with common alias patterns

### 2.3 Metadata Preservation Layer
- [ ] Create file: `src/providers/graph/metadata_enricher.py`
- [ ] Implement functions to add metadata to extracted nodes:
  - [ ] `add_temporal_metadata(node, segment)` - Adds timestamps
  - [ ] `add_source_metadata(node, episode, podcast)` - Adds source tracking
  - [ ] `add_extraction_metadata(node)` - Adds extraction timestamp, confidence
  - [ ] `add_embeddings(node, embedder)` - Generates and adds vector embeddings
- [ ] Ensure all current metadata fields are preserved

### 2.4 Quote Extraction Enhancement
- [ ] Create file: `src/processing/schemaless_quote_extractor.py`
- [ ] Implement custom quote extraction that:
  - [ ] Identifies memorable quotes from segments
  - [ ] Preserves exact timestamp of quote start
  - [ ] Links quotes to speakers
  - [ ] Maintains quote context
  - [ ] Calculates quote importance scores
- [ ] Integrate with SimpleKGPipeline results

**Claude Code Reminder**: Use context7 to look up best practices for extending SimpleKGPipeline with custom components.

## Phase 3: Schemaless Provider Implementation

### 3.1 Base Schemaless Provider
- [ ] Create file: `src/providers/graph/schemaless_neo4j.py`
- [ ] Implement `SchemalessNeo4jProvider` class inheriting from base GraphProvider
- [ ] Initialize SimpleKGPipeline in constructor with:
  - [ ] LLM adapter
  - [ ] Neo4j driver
  - [ ] Embedding adapter
  - [ ] Custom components
- [ ] Implement required interface methods:
  - [ ] `setup_schema()` - Now just creates indexes, no type constraints
  - [ ] `store_podcast()` - Stores podcast with flexible properties
  - [ ] `store_episode()` - Stores episode with all metadata
  - [ ] `store_segments()` - Processes segments through SimpleKGPipeline
  - [ ] `store_extraction_results()` - Handles SimpleKGPipeline output

### 3.2 Segment Processing Pipeline
- [ ] Implement `process_segment_schemaless()` method:
  - [ ] Preprocess segment text with metadata injection
  - [ ] Call SimpleKGPipeline.run_async() with enriched text
  - [ ] Post-process results to add missing metadata
  - [ ] Handle extraction errors gracefully
  - [ ] Return standardized result format
- [ ] Add batch processing support for multiple segments
- [ ] Implement progress tracking

### 3.3 Property Mapping System
- [ ] Create property mapping configuration: `config/schemaless_properties.yml`
- [ ] Define how current fixed properties map to flexible properties:
  - [ ] Entity.confidence → node["confidence"]
  - [ ] Entity.importance → node["importance_score"]
  - [ ] Segment.start_time → node["start_time"]
  - [ ] Quote.speaker → node["attributed_to"]
- [ ] Implement property validation without strict typing
- [ ] Create property documentation generator

### 3.4 Relationship Handling
- [ ] Implement dynamic relationship creation:
  - [ ] Let SimpleKGPipeline create relationship types
  - [ ] Add metadata to relationships (confidence, source segment)
  - [ ] Track relationship frequency
  - [ ] Handle bidirectional relationships
- [ ] Create relationship type normalization (e.g., "works at" → "WORKS_AT")

**Claude Code Reminder**: Use context7 to research Neo4j naming conventions and property storage best practices.

## Phase 4: Migration Compatibility Layer

### 4.1 Query Translation Layer
- [ ] Create file: `src/migration/query_translator.py`
- [ ] Implement query translation functions:
  - [ ] `translate_fixed_to_schemaless(cypher_query)` - Converts old queries
  - [ ] `build_type_agnostic_query(intent)` - Creates new flexible queries
  - [ ] `handle_property_variations(property_name)` - Manages property aliases
- [ ] Create query pattern library for common operations
- [ ] Test with all existing query patterns

### 4.2 Result Standardization
- [ ] Create file: `src/migration/result_standardizer.py`
- [ ] Implement result transformation:
  - [ ] Convert schemaless results to current expected format
  - [ ] Handle missing properties gracefully
  - [ ] Provide default values where needed
  - [ ] Log schema evolution (new types/properties discovered)
- [ ] Create result validation tests

### 4.3 Backwards Compatibility Interface
- [ ] Create file: `src/providers/graph/compatible_neo4j.py`
- [ ] Implement provider that:
  - [ ] Accepts both fixed and schemaless storage requests
  - [ ] Routes to appropriate implementation
  - [ ] Provides unified query interface
  - [ ] Handles mixed-schema graphs
- [ ] Add feature flags for gradual migration

### 4.4 Data Migration Tools
- [ ] Create migration script: `scripts/migrate_to_schemaless.py`
- [ ] Implement migration functions:
  - [ ] `export_fixed_schema_data()` - Exports current graph
  - [ ] `transform_to_schemaless()` - Converts data structure
  - [ ] `validate_migration()` - Checks data integrity
  - [ ] `rollback_migration()` - Reverts if needed
- [ ] Add progress tracking and logging
- [ ] Create migration dry-run mode

**Claude Code Reminder**: Use context7 to look up Neo4j data migration best practices and transaction handling.

## Phase 5: Testing Infrastructure

### 5.1 Unit Tests for Schemaless Components
- [ ] Create test file: `tests/providers/graph/test_schemaless_neo4j.py`
- [ ] Write tests for:
  - [ ] SimpleKGPipeline initialization
  - [ ] Segment processing with metadata
  - [ ] Entity extraction validation
  - [ ] Relationship creation
  - [ ] Property storage
  - [ ] Error handling
- [ ] Mock SimpleKGPipeline for isolated testing
- [ ] Test edge cases (empty text, special characters)

### 5.2 Integration Tests
- [ ] Create test file: `tests/integration/test_schemaless_pipeline.py`
- [ ] Write end-to-end tests:
  - [ ] Process complete episode with schemaless approach
  - [ ] Verify all metadata preserved
  - [ ] Check entity resolution works
  - [ ] Validate relationship creation
  - [ ] Test quote extraction with timestamps
- [ ] Use real Neo4j test instance
- [ ] Compare output with fixed schema results

### 5.3 Performance Benchmarks
- [ ] Create benchmark script: `tests/performance/benchmark_schemaless.py`
- [ ] Measure and compare:
  - [ ] Processing time per segment
  - [ ] Memory usage
  - [ ] LLM token consumption
  - [ ] Database write performance
  - [ ] Entity resolution speed
- [ ] Create performance regression tests
- [ ] Document optimization opportunities

### 5.4 Domain Diversity Tests
- [ ] Create test fixtures for multiple domains:
  - [ ] Technology podcast fixture
  - [ ] Cooking podcast fixture
  - [ ] History podcast fixture
  - [ ] Medical podcast fixture
  - [ ] Arts/culture podcast fixture
- [ ] Verify each domain creates appropriate entity types
- [ ] Test relationship discovery across domains
- [ ] Document emergent schema patterns

**Claude Code Reminder**: Use context7 to research pytest best practices and Neo4j test container setup.

## Phase 6: Configuration and Documentation

### 6.1 Configuration Management
- [ ] Update `src/core/config.py` to add schemaless options:
  - [ ] `use_schemaless_extraction: bool`
  - [ ] `schemaless_confidence_threshold: float`
  - [ ] `entity_resolution_threshold: float`
  - [ ] `max_properties_per_node: int`
  - [ ] `relationship_normalization: bool`
- [ ] Create example configuration: `config/schemaless.example.yml`
- [ ] Add environment variable mappings
- [ ] Create configuration validation

### 6.2 API Documentation
- [ ] Update API documentation for schemaless mode:
  - [ ] Document new parameters
  - [ ] Explain flexible return types
  - [ ] Provide schema discovery examples
  - [ ] Add migration guide section
- [ ] Create OpenAPI schema updates
- [ ] Add example requests/responses

### 6.3 Development Documentation
- [ ] Create `docs/architecture/schemaless_design.md` explaining:
  - [ ] Design decisions
  - [ ] Component interactions
  - [ ] Extension points
  - [ ] Performance considerations
- [ ] Document common customization scenarios
- [ ] Add troubleshooting guide

### 6.4 Migration Guide
- [ ] Create `docs/migration/to_schemaless.md` with:
  - [ ] Step-by-step migration process
  - [ ] Pre-migration checklist
  - [ ] Data backup procedures
  - [ ] Rollback instructions
  - [ ] FAQ section
- [ ] Include example commands
- [ ] Add decision tree for migration approach

**Claude Code Reminder**: Use context7 to look up documentation best practices and API documentation standards.

## Phase 7: Orchestrator Integration

### 7.1 Update Pipeline Orchestrator
- [ ] Modify `src/seeding/orchestrator.py`:
  - [ ] Add schemaless provider initialization
  - [ ] Update `process_episode()` to use schemaless extraction
  - [ ] Modify checkpoint handling for schemaless data
  - [ ] Update progress tracking
  - [ ] Add schema discovery logging
- [ ] Maintain backwards compatibility flag
- [ ] Test with both extraction modes

### 7.2 Batch Processing Updates
- [ ] Update `src/seeding/batch_processor.py`:
  - [ ] Handle schemaless configuration
  - [ ] Update progress reporting for dynamic types
  - [ ] Add schema evolution tracking
  - [ ] Implement extraction statistics
- [ ] Test with multiple podcast batch

### 7.3 Checkpoint Compatibility
- [ ] Update checkpoint system to handle:
  - [ ] Flexible entity types
  - [ ] Dynamic properties
  - [ ] Schema evolution between checkpoints
  - [ ] Version compatibility
- [ ] Test checkpoint recovery with schemaless data
- [ ] Add checkpoint migration utility

### 7.4 Error Handling Enhancement
- [ ] Add specific error handling for:
  - [ ] SimpleKGPipeline failures
  - [ ] Property validation errors
  - [ ] Entity resolution conflicts
  - [ ] Relationship creation errors
- [ ] Implement graceful degradation
- [ ] Add detailed error logging

**Claude Code Reminder**: Use context7 to research error handling patterns and resilience best practices.

## Phase 8: CLI and API Updates

### 8.1 CLI Enhancement
- [ ] Update `cli.py` to add:
  - [ ] `--extraction-mode [fixed|schemaless]` flag
  - [ ] `--schema-discovery` flag to show discovered types
  - [ ] `--migration-mode` flag for dual processing
  - [ ] Schema statistics command
- [ ] Update help text with examples
- [ ] Add validation for flag combinations

### 8.2 API Endpoint Updates
- [ ] Update `src/api/v1/seeding.py`:
  - [ ] Add extraction_mode parameter
  - [ ] Return discovered schema in response
  - [ ] Handle flexible result types
  - [ ] Add schema evolution endpoint
- [ ] Update API version if needed
- [ ] Maintain backwards compatibility

### 8.3 Health Check Updates
- [ ] Extend health checks to verify:
  - [ ] SimpleKGPipeline connectivity
  - [ ] Schemaless extraction capability
  - [ ] Entity resolution service
  - [ ] Schema discovery functioning
- [ ] Add detailed status reporting

### 8.4 Monitoring Integration
- [ ] Add metrics for:
  - [ ] Discovered entity types count
  - [ ] Relationship types count
  - [ ] Properties per node average
  - [ ] Entity resolution matches
  - [ ] Schema evolution rate
- [ ] Update dashboards
- [ ] Create alerts for anomalies

**Claude Code Reminder**: Use context7 to look up API versioning best practices and backwards compatibility patterns.

## Phase 9: Final Integration and Cleanup

### 9.1 Feature Flag Implementation
- [ ] Add feature flags:
  - [ ] `ENABLE_SCHEMALESS_EXTRACTION`
  - [ ] `SCHEMALESS_MIGRATION_MODE`
  - [ ] `LOG_SCHEMA_DISCOVERY`
  - [ ] `ENABLE_ENTITY_RESOLUTION_V2`
- [ ] Create flag management utilities
- [ ] Document flag usage

### 9.2 Legacy Code Cleanup
- [ ] Mark deprecated methods in fixed schema implementation
- [ ] Add deprecation warnings
- [ ] Create removal timeline
- [ ] Document migration path for each deprecated feature
- [ ] Update code comments

### 9.3 Performance Optimization
- [ ] Profile schemaless extraction pipeline
- [ ] Identify bottlenecks:
  - [ ] LLM calls
  - [ ] Entity resolution
  - [ ] Graph writes
  - [ ] Embedding generation
- [ ] Implement optimizations:
  - [ ] Batch processing
  - [ ] Caching
  - [ ] Async operations
  - [ ] Connection pooling

### 9.4 Final Validation
- [ ] Run full test suite
- [ ] Process diverse podcast set
- [ ] Verify all features work:
  - [ ] Timestamp preservation
  - [ ] Speaker tracking
  - [ ] Quote extraction
  - [ ] Entity resolution
  - [ ] Metadata storage
- [ ] Generate comparison report
- [ ] Get stakeholder sign-off

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