# Graph Provider Implementations

This directory contains different Neo4j provider implementations for the Podcast Knowledge Graph Pipeline.

## Active Implementations

### neo4j.py
- **Purpose**: Original implementation with fixed schema
- **Status**: Default provider
- **Usage**: Standard knowledge extraction with predefined entity types
- **When to use**: When you need consistent, structured extraction with known entity types

### schemaless_neo4j.py
- **Purpose**: Schemaless/flexible extraction implementation
- **Status**: Active (experimental)
- **Usage**: Enable with `use_schemaless_extraction: true` in config
- **When to use**: When processing diverse content that doesn't fit predefined schemas

### compatible_neo4j.py
- **Purpose**: Migration compatibility layer
- **Status**: Temporary - will be removed after full migration
- **Usage**: Bridges between old and new data models during migration
- **When to remove**: After all data has been migrated to the new schema

## Provider Selection

The system automatically selects the appropriate provider based on configuration:

```yaml
# config/config.yml
extraction:
  use_schemaless_extraction: false  # false = neo4j.py, true = schemaless_neo4j.py
```

## Future Plans

- Once migration is complete, `compatible_neo4j.py` will be removed
- `schemaless_neo4j.py` may become the default as it matures
- Provider interfaces will remain stable for backward compatibility