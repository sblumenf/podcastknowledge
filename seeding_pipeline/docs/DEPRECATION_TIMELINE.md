# Deprecation Timeline

This document outlines the deprecation timeline for features being replaced by the schemaless extraction system.

## Version 1.1.0 (Current)

### Deprecated Classes

#### `KnowledgeExtractor` 
- **Status**: Deprecated
- **Removal**: Version 2.0.0
- **Alternative**: Use `SimpleKGPipeline` with `ENABLE_SCHEMALESS_EXTRACTION=true`
- **Migration Path**: See migration guide below

### Deprecated Methods

#### `extract_entities()`
- **Status**: Deprecated
- **Removal**: Version 2.0.0
- **Alternative**: `SimpleKGPipeline.extract()` for flexible entity discovery
- **Notes**: Schemaless extraction discovers entity types automatically

#### `extract_insights()`
- **Status**: Deprecated
- **Removal**: Version 2.0.0
- **Alternative**: `SimpleKGPipeline.extract()` for flexible knowledge discovery
- **Notes**: Insights are discovered as relationships in the knowledge graph

#### `extract_quotes()`
- **Status**: Deprecated
- **Removal**: Version 2.0.0
- **Alternative**: `SimpleKGPipeline.extract()` with quote post-processing
- **Notes**: Quote extraction is handled by the schemaless quote extractor

#### `extract_topics()`
- **Status**: Deprecated
- **Removal**: Version 2.0.0
- **Alternative**: `SimpleKGPipeline.extract()` discovers topics automatically
- **Notes**: Topics emerge naturally from the knowledge graph structure

## Version 1.2.0 (Planned)

### To Be Deprecated

- Fixed schema models (Entity, Insight, Quote enums)
- Hardcoded entity types
- Static relationship types

## Version 2.0.0 (Future)

### Removals

All deprecated items from version 1.1.0 will be removed:
- `KnowledgeExtractor` class
- All `extract_*` methods
- Fixed schema infrastructure

## Migration Guide

### Before (Fixed Schema)

```python
from src.processing.extraction import KnowledgeExtractor
from src.providers.llm import get_llm_provider

# Initialize
llm = get_llm_provider()
extractor = KnowledgeExtractor(llm)

# Extract knowledge
result = extractor.extract_all(text)
entities = result.entities
insights = result.insights
quotes = result.quotes
```

### After (Schemaless)

```python
from neo4j_graphrag import SimpleKGPipeline
from src.core.feature_flags import FeatureFlag, set_flag

# Enable schemaless extraction
set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)

# Initialize
kg_pipeline = SimpleKGPipeline(
    llm=llm_instance,
    driver=neo4j_driver,
    embedder=embedding_model
)

# Extract knowledge
kg_pipeline.extract(text)

# Query the graph for extracted knowledge
# Entities, insights, and quotes are all nodes/relationships in the graph
```

### Feature Flag Migration

During the transition period, you can use feature flags to control which extraction method is used:

```bash
# Use fixed schema extraction (default)
export FF_ENABLE_SCHEMALESS_EXTRACTION=false

# Use schemaless extraction
export FF_ENABLE_SCHEMALESS_EXTRACTION=true

# Run both for comparison
export FF_ENABLE_SCHEMALESS_EXTRACTION=true
export FF_SCHEMALESS_MIGRATION_MODE=true
```

### Code Changes Required

1. **Replace KnowledgeExtractor instantiation**
   - Remove: `extractor = KnowledgeExtractor(llm_provider)`
   - Add: `kg_pipeline = SimpleKGPipeline(...)`

2. **Update extraction calls**
   - Remove: `result = extractor.extract_all(text)`
   - Add: `kg_pipeline.extract(text)`

3. **Update result handling**
   - Fixed schema returns typed objects
   - Schemaless returns graph nodes/relationships
   - Use graph queries to retrieve results

4. **Update entity type checks**
   - Remove: `if entity.type == EntityType.PERSON:`
   - Add: `if entity.get('type') == 'Person':`

### Testing During Migration

1. Enable migration mode to run both extractors
2. Compare results using the comparison tools
3. Validate that all required information is captured
4. Monitor performance metrics

### Timeline Summary

- **Now - v1.2.0**: Both extraction methods available, fixed schema deprecated
- **v1.2.0 - v2.0.0**: Transition period, migrate all code
- **v2.0.0+**: Fixed schema removed, schemaless only

## Questions?

For migration assistance:
1. Check the feature flags documentation
2. Use migration mode to test changes
3. Monitor deprecation warnings in logs
4. File issues for migration problems