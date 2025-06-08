# Test Import Resolution Plan

## Executive Summary

This plan resolves all import errors in the test suite by systematically analyzing each failing test, determining if the referenced functionality still exists, and either updating imports or removing obsolete tests. The goal is to achieve a working test suite that validates the core VTT transcript knowledge extraction and Neo4j storage functionality.

## Phase 1: Analysis and Categorization

### Task 1.1: Create Import Error Inventory
- [ ] Parse import_errors.txt to extract all failing imports
  - Purpose: Create a comprehensive list of all import issues
  - Steps:
    1. Use context7 MCP tool to review documentation for current architecture
    2. Read import_errors.txt file
    3. Extract each unique import error with file location
    4. Create JSON structure mapping: test_file -> missing_imports
    5. Save to test_tracking/import_error_inventory.json
  - Validation: JSON file contains all 30+ import errors categorized by test file

### Task 1.2: Analyze Source Code Availability
- [ ] Check each missing import against current source code
  - Purpose: Determine what functionality still exists vs what was removed
  - Steps:
    1. Use context7 MCP tool to review documentation for API changes
    2. For each missing import, use Grep to search for:
       - Class/function with exact name
       - Similar names (possible renames)
       - Module relocations
    3. Create mapping: missing_import -> status (exists/renamed/moved/removed)
    4. Save to test_tracking/import_resolution_mapping.json
  - Validation: Each import error has a resolution status

### Task 1.3: Categorize Tests by Action Required
- [ ] Group tests into action categories
  - Purpose: Organize work by type of fix needed
  - Steps:
    1. Use context7 MCP tool for documentation on test categories
    2. Create categories:
       - SIMPLE_FIX: Just update import path
       - RENAME_FIX: Update to new function/class name
       - REFACTOR_NEEDED: Test needs significant updates
       - DELETE_CANDIDATE: Functionality no longer exists
    3. Assign each test file to a category
    4. Save to test_tracking/test_action_plan.json
  - Validation: Every failing test is categorized with clear action

## Phase 2: Fix Simple Import Issues

### Task 2.1: Fix Direct Import Path Updates
- [ ] Update tests with simple import path changes
  - Purpose: Quickly resolve straightforward import issues
  - Steps:
    1. Use context7 MCP tool to verify current module structure
    2. For each SIMPLE_FIX test:
       - Read the test file
       - Update import statement to correct path
       - Run test to verify fix
    3. Track fixes in test_tracking/simple_fixes_completed.json
  - Validation: Tests run without import errors

### Task 2.2: Fix Renamed Function/Class Imports
- [ ] Update tests for renamed functionality
  - Purpose: Align tests with refactored code
  - Steps:
    1. Use context7 MCP tool for naming convention documentation
    2. For each RENAME_FIX test:
       - Update import to new name
       - Search and replace old name in test body
       - Verify test logic still makes sense
    3. Track in test_tracking/rename_fixes_completed.json
  - Validation: Tests import successfully and pass

## Phase 3: Handle Complex Refactoring

### Task 3.1: Analyze EntityType and Enum Issues
- [ ] Fix enum-related import errors
  - Purpose: Resolve the multiple EntityType, InsightType import failures
  - Steps:
    1. Use context7 MCP tool for enum documentation
    2. Check src/core/extraction_interface.py for actual enum definitions
    3. Determine if enums were:
       - Converted to string literals
       - Moved to different module
       - Replaced with different pattern
    4. Update all affected tests accordingly
  - Validation: All enum import errors resolved

### Task 3.2: Fix VTTKnowledgeExtractor References
- [ ] Update tests using VTTKnowledgeExtractor
  - Purpose: Align with current extraction architecture
  - Steps:
    1. Use context7 MCP tool for extraction interface documentation
    2. Find current extraction class/function structure
    3. Update tests to use new extraction pattern
    4. Ensure extraction->Neo4j flow is tested
  - Validation: Extraction tests work with current architecture

### Task 3.3: Update CLI and API Tests
- [ ] Fix CLI function imports (load_podcast_configs, seed_podcasts, etc.)
  - Purpose: Ensure CLI functionality is properly tested
  - Steps:
    1. Use context7 MCP tool for CLI documentation
    2. Review current src/cli/cli.py for available functions
    3. Update test imports to match current CLI interface
    4. Adjust test logic for VTT-only pipeline
  - Validation: CLI tests run and validate VTT processing

## Phase 4: Remove Obsolete Tests

### Task 4.1: Identify Truly Obsolete Tests
- [ ] Determine which tests should be deleted
  - Purpose: Clean up tests for removed functionality
  - Steps:
    1. Use context7 MCP tool for feature deprecation documentation
    2. For each DELETE_CANDIDATE:
       - Confirm functionality is permanently removed
       - Check if test logic should be preserved elsewhere
       - Document reason for deletion
    3. Create test_tracking/tests_to_delete.json with justifications
  - Validation: Clear documentation of what's being removed and why

### Task 4.2: Archive and Remove Obsolete Tests
- [ ] Safely remove tests for deleted functionality
  - Purpose: Clean up test suite
  - Steps:
    1. Create archive directory tests/archived_obsolete/
    2. Move (don't delete) obsolete tests to archive
    3. Add README.md explaining why tests were archived
    4. Update test_tracking/deleted_tests.log
  - Validation: Tests moved, not deleted; audit trail maintained

## Phase 5: Validate Core Functionality

### Task 5.1: Ensure VTT Processing Tests Work
- [ ] Verify all VTT transcript processing tests
  - Purpose: Confirm core functionality is properly tested
  - Steps:
    1. Use context7 MCP tool for VTT processing documentation
    2. Run all VTT-related tests:
       - test_vtt_parser.py
       - test_vtt_extraction.py
       - test_vtt_pipeline_e2e.py
    3. Fix any remaining issues
    4. Document test coverage for VTT pipeline
  - Validation: VTT processing fully tested end-to-end

### Task 5.2: Verify Neo4j Integration Tests
- [ ] Ensure knowledge graph storage tests work
  - Purpose: Validate data persistence layer
  - Steps:
    1. Use context7 MCP tool for Neo4j integration documentation
    2. Run Neo4j-related tests
    3. Verify tests cover:
       - Connection handling
       - Entity storage
       - Relationship creation
       - Error handling
    4. Add missing test cases if needed
  - Validation: Neo4j integration fully tested

### Task 5.3: Run Full Test Suite
- [ ] Execute complete test suite and measure coverage
  - Purpose: Ensure all tests pass and meet coverage targets
  - Steps:
    1. Run pytest with coverage reporting
    2. Generate coverage report
    3. Identify any uncovered critical paths
    4. Document final test metrics
  - Validation: All tests pass, coverage meets best practices (>80% for critical components)

## Phase 6: Documentation and Cleanup

### Task 6.1: Update Test Documentation
- [ ] Document test suite changes
  - Purpose: Maintain clear test documentation
  - Steps:
    1. Use context7 MCP tool to review test documentation standards
    2. Update tests/README.md with:
       - Current test structure
       - How to run tests
       - Coverage expectations
    3. Document any testing patterns/conventions
  - Validation: New developer can understand test suite

### Task 6.2: Create Import Resolution Report
- [ ] Generate final report of all changes
  - Purpose: Provide audit trail of modifications
  - Steps:
    1. Compile all tracking JSON files
    2. Generate summary report showing:
       - Tests fixed (count by type)
       - Tests removed (with reasons)
       - Final coverage metrics
       - Any remaining issues
    3. Save as test_import_resolution_report.md
  - Validation: Complete record of all changes made

## Success Criteria

1. **No Import Errors**: `pytest` runs without any import-related failures
2. **Core Functionality Tested**: VTT processing and Neo4j storage have comprehensive tests
3. **Coverage Targets**: 
   - Critical path coverage > 90%
   - Overall coverage > 80%
   - No untested public APIs
4. **Documentation Complete**: All changes documented, test suite maintainable
5. **Clean Architecture**: No orphaned tests, clear test organization

## Technology Requirements

This plan uses only existing technologies in the project:
- Python testing with pytest
- Coverage.py for coverage reporting
- Neo4j test fixtures (already in project)
- No new frameworks or tools required

## Risk Mitigation

1. **Archived, Not Deleted**: Obsolete tests are moved to archive directory, not permanently deleted
2. **Tracking Everything**: JSON files track every change for full audit trail
3. **Incremental Validation**: Each phase validates before moving to next
4. **Documentation First**: context7 MCP tool consulted before each task