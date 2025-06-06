# VTT-Only Pipeline Cleanup Implementation Plan

## Executive Summary

Transform the current mixed RSS/VTT pipeline into a minimal, focused VTT-only processing system. Remove all RSS/audio-related code, update tests to match actual VTT functionality, and create a clean codebase ready to process VTT files into a knowledge graph.

## Phase 1: Remove RSS/Audio Components

### Task 1.1: Remove RSS/Audio Source Files
- [x] Delete RSS/audio processing files
  - Purpose: Remove unused functionality to minimize codebase
  - Steps:
    1. Use context7 MCP tool to review current file structure
    2. Delete `src/api/v1/podcast_api.py` (RSS API)
    3. Delete `src/services/audio_*` files if they exist
    4. Delete `src/processing/rss_*` files if they exist
    5. Delete any whisper/transcription related files
  - Validation: No RSS/audio processing files remain in src/

### Task 1.2: Clean Up Imports
- [x] Remove RSS/audio imports from remaining files
  - Purpose: Prevent import errors after file deletion
  - Steps:
    1. Use context7 MCP tool to check import dependencies
    2. Run `grep -r "podcast_api\|audio_provider\|whisper\|rss" src/`
    3. Remove identified imports from files
    4. Update `__init__.py` files to remove deleted module exports
  - Validation: No import errors when running `python -m src`

### Task 1.3: Simplify Configuration
- [x] Remove RSS/audio configuration options
  - Purpose: Simplify config to VTT-only parameters
  - Steps:
    1. Use context7 MCP tool to review `src/core/config.py`
    2. Remove fields: `max_episodes`, `whisper_model_size`, `use_faster_whisper`, `audio_dir`
    3. Remove audio-related validation logic
    4. Update config tests to remove audio-related assertions
  - Validation: Config class only contains VTT-relevant parameters

## Phase 2: Update Core Pipeline

### Task 2.1: Simplify VTTKnowledgeExtractor Interface
- [x] Remove RSS methods and simplify to VTT-only
  - Purpose: Clear, minimal API surface
  - Steps:
    1. Use context7 MCP tool to review `src/seeding/orchestrator.py`
    2. Remove `seed_podcast()` method if present
    3. Remove `initialize_components()` if it initializes audio providers
    4. Keep only: `process_vtt_file()`, `process_vtt_files()`, `process_vtt_directory()`
    5. Remove provider factory references
  - Validation: VTTKnowledgeExtractor only has VTT processing methods

### Task 2.2: Remove API v1 Compatibility Layer
- [x] Delete API v1 seeding compatibility
  - Purpose: Remove unnecessary abstraction layer
  - Steps:
    1. Use context7 MCP tool to check usage of `src/api/v1/seeding.py`
    2. Delete `src/api/v1/seeding.py`
    3. Update any imports to use core orchestrator directly
    4. Delete mock_podcast_api.py test fixture
  - Validation: No references to API v1 seeding remain

## Phase 3: Transform Test Suite

### Task 3.1: Delete RSS/Audio Test Files
- [x] Remove test files for deleted functionality
  - Purpose: Clean test suite
  - Steps:
    1. Use context7 MCP tool to identify RSS/audio tests
    2. Delete test files:
       - Any `test_*audio*.py`
       - Any `test_*rss*.py`  
       - Any `test_*podcast_api*.py`
       - `tests/fixtures/mock_podcast_api.py`
    3. Remove RSS-related test fixtures
  - Validation: No RSS/audio test files exist

### Task 3.2: Transform E2E Tests
- [x] Rewrite E2E tests for VTT processing
  - Purpose: Test actual VTT functionality
  - Steps:
    1. Use context7 MCP tool to review `tests/e2e/test_e2e_scenarios.py`
    2. Rename to `test_vtt_processing_scenarios.py`
    3. Replace each RSS test with VTT equivalent:
       - `test_scenario_batch_import_multiple_podcasts` → `test_batch_process_vtt_files`
       - `test_scenario_interrupted_processing_recovery` → `test_vtt_checkpoint_recovery`
       - Remove `test_scenario_real_world_podcast` entirely
    4. Update test data to use VTT file fixtures instead of RSS URLs
  - Validation: All E2E tests use VTT files as input

### Task 3.3: Fix Integration Tests
- [ ] Update integration tests for VTT-only pipeline
  - Purpose: Test component integration without RSS/audio
  - Steps:
    1. Use context7 MCP tool to review `tests/integration/test_orchestrator.py`
    2. Rename to `test_vtt_pipeline_integration.py`
    3. Remove tests for:
       - `factory` attribute
       - `audio_provider` initialization
       - RSS feed processing
    4. Add tests for:
       - VTT parser integration
       - Knowledge extractor integration
       - Graph storage integration
  - Validation: Integration tests pass without RSS/audio mocks

### Task 3.4: Fix Unit Test Issues
- [ ] Quick fixes for failing unit tests
  - Purpose: Clean unit test suite
  - Steps:
    1. Use context7 MCP tool to review failing tests
    2. Fix `test_batch_processor_unit.py`:
       - Update progress callback expectations
       - Initialize required attributes properly
    3. Fix `test_config.py`:
       - Update `embedding_batch_size` assertion to 100
       - Remove RSS-related config tests
  - Validation: Unit tests pass

## Phase 4: Create VTT Test Fixtures

### Task 4.1: Create Reusable VTT Test Data
- [ ] Build VTT file fixtures for testing
  - Purpose: Consistent test data
  - Steps:
    1. Create `tests/fixtures/vtt_samples.py`
    2. Add helper functions:
       ```python
       def create_simple_vtt(path, duration_minutes=5)
       def create_multi_speaker_vtt(path, speakers=2)
       def create_technical_discussion_vtt(path)
       def create_corrupted_vtt(path)
       ```
    3. Create actual VTT content strings as constants
  - Validation: Test fixtures can generate various VTT scenarios

### Task 4.2: Update Mock Neo4j for VTT
- [ ] Ensure mock Neo4j handles VTT-specific queries
  - Purpose: Support VTT pipeline testing
  - Steps:
    1. Use context7 MCP tool to review `tests/utils/neo4j_mocks.py`
    2. Add query handlers for:
       - Segment creation
       - Speaker relationships
       - Timeline queries
    3. Remove any RSS/podcast-specific query handlers
  - Validation: Mock supports all VTT pipeline queries

## Phase 5: Validate Minimal Pipeline

### Task 5.1: Run Full Test Suite
- [ ] Ensure all tests pass
  - Purpose: Validate cleanup success
  - Steps:
    1. Run `pytest -v`
    2. Fix any remaining failures
    3. Check no RSS/audio references remain: `grep -r "rss\|podcast.*api\|audio" tests/`
  - Validation: All tests pass, no RSS references

### Task 5.2: Test VTT Processing
- [ ] Manual validation of VTT processing
  - Purpose: Ensure pipeline actually works
  - Steps:
    1. Create test VTT file in `test_vtt/sample.vtt`
    2. Run: `python -m src.cli.cli process-vtt test_vtt/sample.vtt`
    3. Verify output in logs
    4. Check Neo4j mock for created entities
  - Validation: VTT file processes without errors

### Task 5.3: Measure Codebase Reduction
- [ ] Document cleanup metrics
  - Purpose: Confirm minimal codebase achieved
  - Steps:
    1. Count files before/after: `find src tests -name "*.py" | wc -l`
    2. Count lines of code: `find src tests -name "*.py" -exec wc -l {} + | tail -1`
    3. List removed functionality in cleanup summary
  - Validation: Significant reduction in files and LOC

## Success Criteria

1. **No RSS/Audio Code**: Zero references to RSS feeds, audio processing, or podcast APIs
2. **All Tests Pass**: Updated test suite passes completely
3. **VTT Processing Works**: Can process sample VTT files through the pipeline
4. **Minimal Codebase**: At least 30% reduction in files and lines of code
5. **Clean Architecture**: Clear VTT → Knowledge Graph pipeline with no unnecessary abstractions

## Technology Requirements

No new technologies required. This plan only removes existing components and simplifies the codebase.

## Notes

- Each task references context7 MCP tool for documentation review as required
- Plan focuses on deletion and simplification rather than new features
- Test coverage target is "appropriate" not 100% - focus on critical paths
- All changes maintain AI agent maintainability (simple, clear code)