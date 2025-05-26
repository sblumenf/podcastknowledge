# Schemaless Knowledge Graph Design

## Overview

This document explains the design decisions, architecture, and implementation details of the schemaless knowledge graph extraction system for the Podcast Knowledge Pipeline.

## Design Decisions

### Why Schemaless?

1. **Domain Flexibility**: Podcasts cover diverse topics - from technology to cooking to history. A fixed schema cannot anticipate all possible entity types and relationships.

2. **Schema Evolution**: As we process more content, new types and relationships emerge naturally. Schemaless design allows the schema to evolve without code changes.

3. **Reduced Maintenance**: No need to update schema definitions when encountering new domains or content types.

4. **Better Extraction**: LLMs can identify nuanced entities and relationships that might not fit predefined categories.

### Key Design Principles

1. **Progressive Enhancement**: Start with LLM extraction, then enhance with domain-specific rules
2. **Metadata Preservation**: Never lose context (timestamps, speakers, sources)
3. **Graceful Degradation**: If components fail, core extraction continues
4. **Observable Impact**: Track what each component contributes

## Component Interactions

### Architecture Flow

```
Podcast Audio/RSS Feed
        │
        ▼
┌─────────────────┐
│   Orchestrator  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐     ┌──────────────────┐
│ Segment Processor   │────▶│  Preprocessor    │
└─────────┬───────────┘     └──────────────────┘
          │                           │
          │                           ▼
          │                  ┌──────────────────┐
          │                  │ Metadata Inject  │
          │                  └────────┬─────────┘
          │                           │
          ▼                           ▼
┌─────────────────────┐     ┌──────────────────┐
│ SimpleKGPipeline    │◀────│ Enriched Text    │
└─────────┬───────────┘     └──────────────────┘
          │
          ▼
┌─────────────────────┐
│ Raw Extraction      │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐     ┌──────────────────┐
│ Entity Resolution   │────▶│ Merge Duplicates │
└─────────┬───────────┘     └──────────────────┘
          │
          ▼
┌─────────────────────┐     ┌──────────────────┐
│ Metadata Enricher   │────▶│ Add Timestamps   │
└─────────┬───────────┘     │ Add Embeddings   │
          │                  │ Add Confidence   │
          │                  └──────────────────┘
          ▼
┌─────────────────────┐     ┌──────────────────┐
│ Quote Extractor     │────▶│ Find Quotes      │
└─────────┬───────────┘     │ Link Speakers    │
          │                  └──────────────────┘
          ▼
┌─────────────────────┐
│   Neo4j Storage     │
└─────────────────────┘
```

### Component Responsibilities

#### 1. Preprocessor (`SegmentPreprocessor`)
- **Purpose**: Inject context that LLMs need for better extraction
- **Inputs**: Raw segment text, episode metadata
- **Outputs**: Enriched text with temporal and speaker context
- **Tracking**: Records what was injected for impact analysis

#### 2. SimpleKGPipeline (External)
- **Purpose**: Core LLM-based entity and relationship extraction
- **Inputs**: Enriched text
- **Outputs**: Raw entities and relationships
- **Configuration**: Minimal - we handle specifics in post-processing

#### 3. Entity Resolution (`SchemalessEntityResolver`)
- **Purpose**: Merge duplicate entities, handle aliases
- **Inputs**: Raw entities from extraction
- **Outputs**: Deduplicated entities with merged properties
- **Strategy**: Fuzzy matching with configurable threshold

#### 4. Metadata Enricher (`SchemalessMetadataEnricher`)
- **Purpose**: Add missing metadata to extracted entities
- **Inputs**: Resolved entities, segment context
- **Outputs**: Entities with full metadata
- **Metadata Added**:
  - Temporal information (start_time, end_time)
  - Source tracking (episode_id, podcast_id)
  - Extraction metadata (timestamp, confidence)
  - Vector embeddings

#### 5. Quote Extractor (`SchemalessQuoteExtractor`)
- **Purpose**: Identify and preserve memorable quotes
- **Inputs**: Segment text, speaker information
- **Outputs**: Extracted quotes with attribution
- **Features**: Importance scoring, exact timestamp preservation

## Extension Points

### Adding New Components

Components follow a standard interface:

```python
@track_component_impact("component_name", "1.0")
def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    # Transform input_data
    # Track what was added/modified
    # Return enhanced data
```

### Custom Entity Types

While schemaless by design, you can guide extraction:

1. **Preprocessing Hints**: Add type hints in preprocessor
2. **Post-Processing Rules**: Add custom resolution rules
3. **Property Validation**: Enforce constraints in enricher

### Integration Points

1. **LLM Providers**: Swap via adapter pattern
2. **Embedding Providers**: Configurable dimensions
3. **Graph Storage**: Neo4j required but version flexible
4. **Monitoring**: OpenTelemetry-ready

## Performance Considerations

### Optimization Strategies

1. **Batch Processing**
   - Process multiple segments together
   - Batch database writes
   - Reuse LLM connections

2. **Caching**
   - Cache entity resolutions
   - Cache embeddings for common terms
   - Cache preprocessed templates

3. **Async Operations**
   - Pipeline supports async execution
   - Concurrent segment processing
   - Non-blocking database writes

### Resource Management

1. **Memory**
   - Stream large podcasts
   - Clear intermediate results
   - Monitor component memory usage

2. **LLM Tokens**
   - Optimize prompt templates
   - Compress metadata injection
   - Track token usage per component

3. **Database Connections**
   - Connection pooling
   - Batch transactions
   - Optimistic locking

### Performance Metrics

Track these metrics for optimization:
- Segments per second
- Tokens per segment
- Memory per episode
- Cache hit rates
- Component execution times

## Troubleshooting Guide

### Common Issues

1. **Low Entity Extraction**
   - Check LLM connection
   - Verify preprocessing is working
   - Increase segment size

2. **Duplicate Entities**
   - Lower resolution threshold
   - Check fuzzy matching config
   - Review resolution rules

3. **Missing Metadata**
   - Verify enricher is called
   - Check segment has required fields
   - Review enrichment config

4. **Poor Performance**
   - Enable component tracking
   - Check batch sizes
   - Review cache configuration

### Debugging Tools

1. **Component Tracking**
   ```python
   # Enable tracking
   config.enable_component_tracking = True
   
   # Analyze impact
   from src.utils.component_tracker import analyze_component_impact
   impact = analyze_component_impact("entity_resolution")
   ```

2. **Dry Run Mode**
   ```python
   # Preview without processing
   preprocessor.dry_run = True
   result = preprocessor.prepare_segment_text(segment)
   print(result['preview'])
   ```

3. **Schema Discovery**
   ```cypher
   // Find all entity types
   MATCH (n) 
   WHERE exists(n._type)
   RETURN DISTINCT n._type, count(n)
   
   // Find all relationship types
   MATCH ()-[r]->()
   WHERE exists(r._type)
   RETURN DISTINCT r._type, count(r)
   ```

## Future Enhancements

### Planned Improvements

1. **Auto-Component Removal**: Disable components with low impact
2. **Schema Inference**: Generate TypeScript/Python types from discovered schema
3. **Domain Classifiers**: Auto-detect podcast domain for better extraction
4. **Incremental Learning**: Improve extraction based on user feedback

### Research Directions

1. **Multi-Modal Integration**: Combine audio features with text
2. **Cross-Episode Learning**: Use knowledge from previous episodes
3. **Real-Time Processing**: Stream processing for live podcasts
4. **Federated Schemas**: Share schemas across deployments