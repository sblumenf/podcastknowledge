# POC Files Documentation

## POC Files in src Directory

The following POC (Proof of Concept) files are temporarily kept in the src directory as they are still being used:

### 1. `src/providers/graph/schemaless_poc.py`
- **Purpose**: Original schemaless extraction proof of concept
- **Used by**: `scripts/test_integration.py`
- **Status**: To be consolidated in future phases

### 2. `src/providers/graph/schemaless_poc_integrated.py`
- **Purpose**: Integrated version of schemaless POC
- **References**: 
  - `tests/fixtures/schemaless_poc/results`
  - `tests/fixtures/schemaless_poc/test_episodes`
- **Status**: To be consolidated in future phases

## Future Consolidation Plan

These POC files will be consolidated in a later phase once:
1. The schemaless extraction is fully integrated into the main pipeline
2. All test dependencies have been migrated to use the production implementations
3. The POC code has been properly refactored into the appropriate modules

## Note
These files are kept temporarily as per the refactoring plan to avoid breaking existing functionality during the refactoring process.