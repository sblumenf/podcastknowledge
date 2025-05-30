# Phase 1: Fixed-Schema Audit Report

## Fixed-Schema Components Identified

### 1. Core Fixed-Schema Files
- `src/processing/strategies/fixed_schema_strategy.py` - Main fixed-schema strategy implementation
- `src/processing/adapters/fixed_schema_adapter.py` - Fixed-schema adapter

### 2. Dual-Mode Strategy (to be removed)
- `src/processing/strategies/dual_mode_strategy.py` - Contains mode selection logic between fixed and schemaless

### 3. Files with Fixed-Schema Imports/References
- `src/processing/adapters/__init__.py` - Imports FixedSchemaAdapter
- `src/processing/strategies/extraction_factory.py` - Creates FixedSchemaStrategy instances
- `src/seeding/components/pipeline_executor.py` - Contains `_extract_fixed_schema` method
- `src/providers/graph/compatible_neo4j.py` - Contains `_is_fixed_schema_query` method

### 4. Test Files with Fixed-Schema References
- `scripts/migration/migrate_to_schemaless.py` - Migration script with fixed schema references
- `tests/performance/benchmark_schemaless.py` - Performance benchmarks comparing schema types
- `tests/fixtures/golden_outputs/fixed_schema_golden.json` - Golden output file (needs checking)

### 5. Configuration References
- No schema_type found in config/*.yml files (already cleaned)
- Need to verify if any Python files have hardcoded schema_type configurations

## Next Steps
1. Remove core fixed-schema files
2. Update imports in all referencing files
3. Remove dual-mode strategy
4. Clean up test fixtures and benchmarks
5. Remove schema_type references from code