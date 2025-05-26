# Feature Flags Documentation

This document describes the feature flag system for the Podcast Knowledge Pipeline and how to use it.

## Overview

Feature flags allow you to enable or disable specific functionality without changing code. They're useful for:
- Gradual rollouts of new features
- A/B testing
- Quick rollback of problematic features
- Development and testing of experimental features

## Available Feature Flags

### Schemaless Extraction Flags

#### `ENABLE_SCHEMALESS_EXTRACTION`
- **Description**: Enable schemaless knowledge extraction using Neo4j GraphRAG
- **Default**: `false`
- **Environment Variable**: `FF_ENABLE_SCHEMALESS_EXTRACTION`
- **Usage**: Set to `true` to use the new schemaless extraction pipeline instead of the fixed schema

#### `SCHEMALESS_MIGRATION_MODE`
- **Description**: Run both fixed and schemaless extraction for comparison
- **Default**: `false`
- **Environment Variable**: `FF_SCHEMALESS_MIGRATION_MODE`
- **Usage**: Set to `true` to run both extraction modes in parallel (requires `ENABLE_SCHEMALESS_EXTRACTION=true`)

#### `LOG_SCHEMA_DISCOVERY`
- **Description**: Log discovered schema types during schemaless extraction
- **Default**: `true`
- **Environment Variable**: `FF_LOG_SCHEMA_DISCOVERY`
- **Usage**: Set to `false` to disable schema discovery logging

#### `ENABLE_ENTITY_RESOLUTION_V2`
- **Description**: Use improved entity resolution algorithm
- **Default**: `false`
- **Environment Variable**: `FF_ENABLE_ENTITY_RESOLUTION_V2`
- **Usage**: Set to `true` to use the new entity resolution algorithm (requires `ENABLE_SCHEMALESS_EXTRACTION=true`)

### Component Enhancement Flags

#### `ENABLE_TIMESTAMP_INJECTION`
- **Description**: Inject timestamps into extracted entities
- **Default**: `true`
- **Environment Variable**: `FF_ENABLE_TIMESTAMP_INJECTION`
- **Usage**: Set to `false` to disable timestamp injection

#### `ENABLE_SPEAKER_INJECTION`
- **Description**: Inject speaker information into extracted entities
- **Default**: `true`
- **Environment Variable**: `FF_ENABLE_SPEAKER_INJECTION`
- **Usage**: Set to `false` to disable speaker injection

#### `ENABLE_QUOTE_POSTPROCESSING`
- **Description**: Enable quote extraction post-processing
- **Default**: `true`
- **Environment Variable**: `FF_ENABLE_QUOTE_POSTPROCESSING`
- **Usage**: Set to `false` to disable quote post-processing

#### `ENABLE_METADATA_ENRICHMENT`
- **Description**: Enrich extracted entities with metadata
- **Default**: `true`
- **Environment Variable**: `FF_ENABLE_METADATA_ENRICHMENT`
- **Usage**: Set to `false` to disable metadata enrichment

#### `ENABLE_ENTITY_RESOLUTION_POSTPROCESS`
- **Description**: Enable entity resolution post-processing
- **Default**: `true`
- **Environment Variable**: `FF_ENABLE_ENTITY_RESOLUTION_POSTPROCESS`
- **Usage**: Set to `false` to disable entity resolution post-processing

## Setting Feature Flags

### Via Environment Variables

The preferred method is to set environment variables:

```bash
# Enable schemaless extraction
export FF_ENABLE_SCHEMALESS_EXTRACTION=true

# Enable migration mode
export FF_SCHEMALESS_MIGRATION_MODE=true

# Disable a component
export FF_ENABLE_QUOTE_POSTPROCESSING=false
```

### Via .env File

Add feature flags to your `.env` file:

```env
# Schemaless extraction
FF_ENABLE_SCHEMALESS_EXTRACTION=true
FF_SCHEMALESS_MIGRATION_MODE=false
FF_LOG_SCHEMA_DISCOVERY=true

# Component flags
FF_ENABLE_TIMESTAMP_INJECTION=true
FF_ENABLE_SPEAKER_INJECTION=true
```

### Programmatically

In your Python code:

```python
from src.core.feature_flags import FeatureFlag, set_flag, is_enabled

# Enable a flag
set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)

# Check if a flag is enabled
if is_enabled(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION):
    # Use schemaless extraction
    pass
```

### Using the Decorator

```python
from src.core.feature_flags import FeatureFlag, requires_flag

@requires_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION)
def schemaless_only_function():
    """This function only runs if schemaless extraction is enabled."""
    pass
```

## CLI Commands

The CLI provides commands for managing feature flags:

```bash
# List all feature flags and their current values
python cli.py feature-flags list

# Export feature flags to a file
python cli.py feature-flags export --output flags.json --format json
python cli.py feature-flags export --output flags.yaml --format yaml

# Generate .env template
python cli.py feature-flags env-template --output .env.template

# Validate feature flag combinations
python cli.py feature-flags validate
```

## Flag Dependencies

Some flags have dependencies:

1. **SCHEMALESS_MIGRATION_MODE** requires **ENABLE_SCHEMALESS_EXTRACTION**
2. **ENABLE_ENTITY_RESOLUTION_V2** requires **ENABLE_SCHEMALESS_EXTRACTION**

The validation command will check these dependencies.

## Best Practices

1. **Use Environment Variables**: Set flags via environment variables for easy configuration management
2. **Document Changes**: When adding new flags, update this documentation
3. **Validate Combinations**: Run `feature-flags validate` to ensure flag combinations are valid
4. **Monitor Impact**: Use monitoring and metrics to track the impact of enabled features
5. **Gradual Rollout**: Start with flags disabled in production, enable gradually
6. **Clean Up**: Remove flags and their code once features are stable and universally adopted

## Integration with Monitoring

Feature flag states are exposed via metrics:

- `podcast_kg_extraction_mode`: Current extraction mode (0=fixed, 1=schemaless)
- Component-specific metrics track usage when flags are enabled

## Troubleshooting

### Flag Not Taking Effect

1. Check environment variable is set correctly:
   ```bash
   echo $FF_ENABLE_SCHEMALESS_EXTRACTION
   ```

2. Verify the flag name matches exactly

3. Check for typos in boolean values (use `true`/`false`, not `True`/`False`)

4. Clear any programmatic overrides

### Validation Failures

Run validation to identify issues:
```bash
python cli.py feature-flags validate
```

This will report any invalid flag combinations.