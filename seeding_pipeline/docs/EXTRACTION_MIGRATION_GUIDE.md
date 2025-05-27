# Extraction Strategy Migration Guide

This guide helps you migrate from the legacy extraction system to the new strategy-based extraction system.

## Overview

The extraction system has been refactored to use a strategy pattern, enabling:
- Seamless switching between fixed schema and schemaless extraction
- Dual mode for comparing both approaches during migration
- Better modularity and testability
- Runtime strategy switching

## Migration Timeline

### Phase 1: Current State (v1.x)
- Legacy `KnowledgeExtractor` class in `src/processing/extraction.py`
- Fixed schema extraction only
- Marked as deprecated with warnings

### Phase 2: Transition Period (v1.5)
- New strategy-based system available
- Both systems work side-by-side
- Deprecation warnings guide migration
- Dual mode available for comparison

### Phase 3: Migration Complete (v2.0)
- Legacy extraction system removed
- Only strategy-based system remains
- Full schemaless extraction support

## Migration Steps

### Step 1: Update Imports

**Old way:**
```python
from src.processing.extraction import KnowledgeExtractor

extractor = KnowledgeExtractor(llm_provider)
result = extractor.extract_all(text)
```

**New way:**
```python
from src.processing.strategies.extraction_factory import ExtractionFactory
from src.processing.strategies import ExtractedData

# Create strategy
strategy = ExtractionFactory.create_strategy(
    mode='fixed',  # or 'schemaless' or 'dual'
    llm_provider=llm_provider
)

# Extract from segment
result = strategy.extract(segment)
```

### Step 2: Use Segment Objects

The new system works with `Segment` objects instead of raw text:

```python
from src.core.models import Segment

segment = Segment(
    id='segment_1',
    text='Your transcript text here',
    start_time=0.0,
    end_time=30.0,
    speaker='Speaker 1',
    episode_id='episode_1'
)

result = strategy.extract(segment)
```

### Step 3: Handle ExtractedData Results

The new `ExtractedData` structure is similar but more comprehensive:

```python
# Access extracted information
entities = result.entities
relationships = result.relationships  # New! Not in fixed schema
quotes = result.quotes
insights = result.insights
topics = result.topics
metadata = result.metadata

# Convert to dictionary if needed
data_dict = result.to_dict()
```

### Step 4: Try Dual Mode

During migration, use dual mode to compare results:

```python
strategy = ExtractionFactory.create_strategy(
    mode='dual',
    llm_provider=llm_provider,
    graph_provider=graph_provider,
    podcast_id='podcast_1',
    episode_id='episode_1'
)

result = strategy.extract(segment)

# Check comparison in metadata
print(f"Fixed entities: {result.metadata['entity_comparison']['fixed_count']}")
print(f"Schemaless entities: {result.metadata['entity_comparison']['schemaless_count']}")
```

### Step 5: Switch to Schemaless

Once satisfied with results, switch to schemaless:

```python
strategy = ExtractionFactory.create_strategy(
    mode='schemaless',
    graph_provider=graph_provider,
    podcast_id='podcast_1',
    episode_id='episode_1'
)
```

## Configuration-Based Creation

You can also create strategies from configuration:

```python
config = {
    'extraction': {
        'mode': 'dual',  # or 'fixed', 'schemaless'
        'use_large_context': True,
        'enable_cache': True
    },
    'podcast': {'id': 'podcast_1'},
    'episode': {'id': 'episode_1'}
}

strategy = ExtractionFactory.create_from_config(
    config,
    llm_provider=llm_provider,
    graph_provider=graph_provider
)
```

## Runtime Strategy Switching

Switch strategies during execution:

```python
# Start with fixed
strategy = ExtractionFactory.create_strategy(mode='fixed', llm_provider=llm_provider)

# Process some segments...

# Switch to dual mode
strategy = ExtractionFactory.switch_strategy(
    current_strategy=strategy,
    new_mode='dual',
    graph_provider=graph_provider,
    podcast_id='podcast_1',
    episode_id='episode_1'
)
```

## Feature Flags

The factory respects feature flags in configuration:

```python
config = {
    'ENABLE_SCHEMALESS_EXTRACTION': True,  # Uses schemaless mode
    'MIGRATION_MODE': True,  # Uses dual mode (takes precedence)
}
```

## Compatibility Notes

1. **KnowledgeExtractor still works** - It's wrapped by FixedSchemaStrategy internally
2. **ExtractionResult vs ExtractedData** - Similar structure, easy to adapt
3. **Relationships** - Only extracted in schemaless/dual modes
4. **Performance** - Dual mode runs both extractions, so it's slower

## Troubleshooting

### Import Errors
If you see import errors, ensure you're using the new import paths:
```python
# Correct
from src.processing.strategies.extraction_factory import ExtractionFactory

# Deprecated
from src.processing.extraction import create_extractor
```

### Missing Parameters
Schemaless and dual modes require additional parameters:
- `graph_provider` - Must support schemaless extraction
- `podcast_id` and `episode_id` - Required for context

### Empty Results
Check strategy mode and ensure providers are properly initialized:
```python
print(f"Mode: {strategy.get_extraction_mode()}")
```

## Support

For issues or questions:
1. Check the deprecation warnings in logs
2. Refer to test examples in `tests/processing/strategies/`
3. Use dual mode to compare extraction quality

## Next Steps

1. Start with dual mode to evaluate both approaches
2. Monitor extraction quality metrics
3. Gradually transition to schemaless for new content
4. Remove fixed schema dependencies by v2.0