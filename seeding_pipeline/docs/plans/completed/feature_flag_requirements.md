# Feature Flag Requirements Analysis

## Expected Feature Flags (from tests)

1. **ENABLE_SCHEMALESS_EXTRACTION**
   - Used extensively in tests
   - Expected to control schemaless extraction mode
   - Default: False (based on test expectations)

2. **SCHEMALESS_MIGRATION_MODE**
   - Used in feature flag tests
   - Expected to control migration from fixed to schemaless schema
   - Default: False (based on test expectations)

## Current Feature Flags

The current implementation has different flags focused on post-processing features:
- LOG_SCHEMA_DISCOVERY
- ENABLE_ENTITY_RESOLUTION_V2
- ENABLE_TIMESTAMP_INJECTION
- ENABLE_SPEAKER_INJECTION
- ENABLE_QUOTE_POSTPROCESSING
- ENABLE_METADATA_ENRICHMENT
- ENABLE_ENTITY_RESOLUTION_POSTPROCESS

## Resolution

Since the codebase has moved to schemaless as the only mode (per comments in the code), the ENABLE_SCHEMALESS_EXTRACTION flag may be obsolete. However, to make tests pass, we should add these flags even if they're always enabled.