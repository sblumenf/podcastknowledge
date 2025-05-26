# Phase 2 Missing Test Files Implementation Plan

## Overview
This document outlines the implementation plan for the two missing test files in Phase 2 of the schemaless implementation.

## Test File 1: `tests/unit/test_schemaless_entity_resolution.py`

### Test Structure
```
TestSchemalessEntityResolver
├── Setup and Fixtures
├── Basic Functionality Tests
├── Matching Algorithm Tests
├── Configuration Tests
├── Integration Tests
├── Error Handling Tests
└── Performance Tests
```

### Test Categories

#### 1. Setup and Fixtures (5 tests)
- `test_init_default_config()` - Verify default thresholds and settings
- `test_init_with_custom_config()` - Test custom configuration loading
- `test_load_resolution_rules()` - Verify YAML rules file loading
- `test_invalid_config_handling()` - Test graceful handling of bad config
- `fixture: sample_entities()` - Create diverse entity test data

#### 2. Basic Entity Resolution (8 tests)
- `test_resolve_exact_duplicates()` - Same entity, different IDs
- `test_resolve_case_differences()` - "IBM" vs "ibm" vs "Ibm"
- `test_resolve_with_extra_spaces()` - " Apple Inc " vs "Apple Inc"
- `test_no_duplicates_unchanged()` - Verify unique entities remain unchanged
- `test_empty_entity_list()` - Handle empty input gracefully
- `test_single_entity()` - Single entity returns unchanged
- `test_preserve_all_properties()` - Merged entities keep all properties
- `test_cluster_id_generation()` - Verify unique cluster IDs

#### 3. Alias and Abbreviation Handling (6 tests)
- `test_resolve_known_aliases()` - "AI" → "Artificial Intelligence"
- `test_resolve_company_variations()` - "Google" vs "Google Inc." vs "Google LLC"
- `test_custom_alias_rules()` - Test user-defined aliases from YAML
- `test_abbreviation_expansion()` - "Dr." → "Doctor", "Prof." → "Professor"
- `test_acronym_handling()` - "NASA", "FBI", "CEO" recognition
- `test_partial_alias_matching()` - "ML" in "ML Engineer" → "Machine Learning Engineer"

#### 4. Fuzzy Matching Tests (7 tests)
- `test_fuzzy_match_threshold()` - Test similarity threshold behavior
- `test_levenshtein_distance_matching()` - "Microsoft" vs "Microsft" (typo)
- `test_fuzzy_match_with_numbers()` - "GPT-3" vs "GPT3" vs "GPT 3"
- `test_fuzzy_match_disabled()` - Test with fuzzy matching turned off
- `test_fuzzy_threshold_boundaries()` - Edge cases at 0.8, 0.85, 0.9
- `test_name_variations()` - "John Smith" vs "Smith, John" vs "J. Smith"
- `test_organization_suffixes()` - Handle Inc, LLC, Ltd, Corp variations

#### 5. Singular/Plural Resolution (5 tests)
- `test_simple_plural_resolution()` - "system" vs "systems"
- `test_irregular_plural_handling()` - "person" vs "people"
- `test_complex_plural_rules()` - "analysis" vs "analyses"
- `test_plural_in_compound_terms()` - "data scientist" vs "data scientists"
- `test_preserve_distinct_meanings()` - Don't merge "glass" and "glasses" (eyewear)

#### 6. Component Tracking Integration (4 tests)
- `test_tracking_decorator_called()` - Verify @track_component_impact is used
- `test_resolution_metrics_logged()` - Check entities before/after counts
- `test_merge_decisions_tracked()` - Log which entities were merged
- `test_performance_metrics()` - Track resolution time and memory

#### 7. Error Handling (5 tests)
- `test_malformed_entity_structure()` - Missing required fields
- `test_none_entity_values()` - Handle None in entity names
- `test_special_characters()` - Entities with unicode, emojis
- `test_extremely_long_names()` - Performance with long strings
- `test_circular_alias_rules()` - A→B→C→A in alias definitions

#### 8. Integration Scenarios (6 tests)
- `test_podcast_domain_entities()` - Real podcast entity examples
- `test_technical_domain_entities()` - Programming terms, frameworks
- `test_medical_domain_entities()` - Medical terminology resolution
- `test_mixed_type_entities()` - Person, Organization, Concept mix
- `test_relationship_preservation()` - Entities in relationships stay connected
- `test_large_entity_list_performance()` - 1000+ entities resolution time

### Mock Requirements
- Mock component tracker to avoid SQLite in unit tests
- Mock entity data generator for various test scenarios
- Mock configuration loader for testing different settings

---

## Test File 2: `tests/providers/graph/test_metadata_enricher.py`

### Test Structure
```
TestMetadataEnricher
├── Setup and Fixtures
├── Temporal Metadata Tests
├── Source Metadata Tests
├── Extraction Metadata Tests
├── Embedding Tests
├── Confidence Score Tests
├── Relationship Enrichment Tests
├── Batch Processing Tests
└── Integration Tests
```

### Test Categories

#### 1. Setup and Fixtures (4 tests)
- `test_init_default()` - Default initialization
- `test_init_with_embedder()` - Initialize with embedding provider
- `fixture: sample_nodes()` - Create test nodes
- `fixture: sample_segments()` - Create test segments with metadata

#### 2. Temporal Metadata Addition (6 tests)
- `test_add_temporal_basic()` - Add start/end times to nodes
- `test_add_temporal_missing_segment()` - Handle None segment gracefully
- `test_preserve_existing_timestamps()` - Don't overwrite existing times
- `test_temporal_format_consistency()` - Ensure consistent time format
- `test_duration_calculation()` - Add duration based on start/end
- `test_temporal_validation()` - Reject invalid time values

#### 3. Source Metadata Addition (7 tests)
- `test_add_episode_source()` - Add episode title, ID, URL
- `test_add_podcast_source()` - Add podcast name, author, category
- `test_nested_source_structure()` - Create source.episode.podcast hierarchy
- `test_source_url_validation()` - Validate URLs before adding
- `test_partial_source_info()` - Handle missing episode or podcast data
- `test_source_field_mapping()` - Map fields correctly from models
- `test_preserve_custom_source_fields()` - Keep non-standard source fields

#### 4. Extraction Metadata (5 tests)
- `test_add_extraction_timestamp()` - Add current timestamp
- `test_add_extraction_version()` - Add pipeline version
- `test_add_extraction_confidence()` - Default confidence if missing
- `test_extraction_method_tracking()` - Track which method extracted entity
- `test_extraction_context()` - Add segment context to extraction

#### 5. Embedding Integration (6 tests)
- `test_add_embeddings_basic()` - Generate and add embeddings
- `test_embedding_dimension_check()` - Verify correct dimensions
- `test_no_embedder_provided()` - Skip embedding if no provider
- `test_embedding_cache_behavior()` - Don't regenerate existing embeddings
- `test_batch_embedding_generation()` - Efficient batch processing
- `test_embedding_error_handling()` - Handle embedding failures gracefully

#### 6. Confidence Score Addition (5 tests)
- `test_calculate_confidence_basic()` - Base confidence calculation
- `test_confidence_factors()` - Multiple factors affect score
- `test_confidence_normalization()` - Ensure 0-1 range
- `test_existing_confidence_merge()` - Combine with existing scores
- `test_confidence_explanation()` - Add confidence factors breakdown

#### 7. Segment Context Addition (5 tests)
- `test_add_segment_context()` - Add surrounding text context
- `test_context_window_size()` - Configurable context window
- `test_speaker_context()` - Include speaker information
- `test_context_overlap_handling()` - Handle overlapping segments
- `test_context_truncation()` - Limit context length appropriately

#### 8. Relationship Enrichment (6 tests)
- `test_enrich_relationships_basic()` - Add metadata to relationships
- `test_relationship_confidence()` - Add confidence to relationships
- `test_relationship_source_tracking()` - Track which segment created relationship
- `test_bidirectional_relationships()` - Handle both directions
- `test_relationship_timestamp()` - Add temporal data to relationships
- `test_relationship_properties()` - Preserve existing properties

#### 9. Batch Processing (4 tests)
- `test_enrich_nodes_batch()` - Process multiple nodes efficiently
- `test_batch_with_mixed_types()` - Handle different node types
- `test_batch_error_recovery()` - Continue on individual failures
- `test_batch_progress_tracking()` - Track enrichment progress

#### 10. Component Tracking Integration (4 tests)
- `test_tracking_decorator_applied()` - Verify tracking is active
- `test_metadata_fields_tracked()` - Log which fields were added
- `test_enrichment_metrics()` - Track nodes enriched, fields added
- `test_performance_impact()` - Measure enrichment overhead

#### 11. Error Handling (5 tests)
- `test_invalid_node_structure()` - Handle malformed nodes
- `test_null_values_handling()` - Deal with None values gracefully
- `test_type_mismatch_handling()` - Wrong types for metadata fields
- `test_missing_required_data()` - Handle missing segment/episode data
- `test_exception_propagation()` - Proper error reporting

### Mock Requirements
- Mock embedding provider for testing embedding addition
- Mock component tracker to isolate unit tests
- Mock node/segment/episode/podcast models
- Mock timestamp generation for consistent tests

---

## Implementation Guidelines

### General Testing Principles
1. **Isolation**: Each test should be independent and not rely on others
2. **Clarity**: Test names should clearly indicate what is being tested
3. **Coverage**: Aim for >90% code coverage for both components
4. **Performance**: Mark slow tests with `@pytest.mark.slow`
5. **Mocking**: Use mocks to avoid dependencies on external systems

### Test Data Management
1. Create reusable fixtures for common test scenarios
2. Use parameterized tests for similar test cases with different inputs
3. Store large test data in separate fixture files if needed
4. Generate test data programmatically when possible

### Error Testing Strategy
1. Test both expected errors (validation) and unexpected errors (resilience)
2. Verify error messages are helpful and actionable
3. Test recovery mechanisms and partial success scenarios
4. Ensure no data corruption occurs during errors

### Integration Test Approach
1. Test interaction with component tracker
2. Verify configuration loading and validation
3. Test with realistic data volumes and complexity
4. Measure performance impact of operations

### Documentation Requirements
1. Add docstrings to all test methods explaining purpose
2. Include examples of test data in docstrings
3. Document any non-obvious test setup or assertions
4. Link tests to requirements in implementation plan

## Execution Plan

### Phase 1: Test Infrastructure (30 minutes)
1. Create test file skeletons with all test method signatures
2. Set up common fixtures and mocks
3. Configure test markers (slow, integration, etc.)
4. Add initial docstring documentation

### Phase 2: Core Functionality Tests (2 hours)
1. Implement basic functionality tests first
2. Ensure happy path scenarios work
3. Add assertions for expected behavior
4. Verify component tracking integration

### Phase 3: Edge Cases and Error Handling (1.5 hours)
1. Add tests for error scenarios
2. Test boundary conditions
3. Add malformed input tests
4. Verify graceful degradation

### Phase 4: Integration and Performance (1 hour)
1. Add integration test scenarios
2. Test with realistic data volumes
3. Add performance benchmarks
4. Test batch processing capabilities

### Phase 5: Polish and Documentation (30 minutes)
1. Review test coverage reports
2. Add missing test cases
3. Improve test documentation
4. Ensure all tests pass

## Success Criteria
- All tests pass in isolation and as a suite
- Code coverage >90% for both components
- Tests run in <30 seconds (excluding slow-marked tests)
- Clear documentation for maintenance
- No flaky tests that fail intermittently