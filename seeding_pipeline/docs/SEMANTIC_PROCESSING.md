# Semantic Processing for VTT Knowledge Extraction

## Overview

The semantic processing feature provides conversation-aware knowledge extraction from VTT transcript files. Unlike traditional segment-by-segment processing, semantic processing:

1. **Analyzes conversation structure** to identify natural boundaries
2. **Groups related segments** into meaningful units (topics, stories, Q&A pairs)
3. **Extracts knowledge with better context** understanding
4. **Reduces entity duplication** through cross-unit resolution
5. **Identifies conversation themes** and narrative flow

## When to Use Semantic Processing

Use semantic processing when:
- Processing long-form conversations (podcasts, interviews)
- Context is important for understanding entities and relationships
- You want to identify conversation themes and structure
- Reducing entity duplication is important
- You have sufficient LLM capacity (uses 1M token context window)

Use traditional segment processing when:
- Processing short clips or isolated segments
- Speed is more important than context understanding
- Working with limited LLM resources
- Backward compatibility is required

## CLI Usage

### Basic Semantic Processing
```bash
# Process a single VTT file with semantic analysis
vtt-kg process-vtt --folder /path/to/vtt --semantic

# Process all VTT files in a directory with semantic analysis
vtt-kg process-vtt --folder /path/to/vtt --semantic --recursive

# Parallel processing with semantic analysis
vtt-kg process-vtt --folder /path/to/vtt --semantic --parallel --workers 4
```

### Compare Processing Methods
```bash
# Compare semantic vs segment processing on the same file
vtt-kg process-vtt --folder /path/to/vtt --compare-methods
```

This will process the file twice and show:
- Number of segments vs meaningful units
- Entity count comparison
- Insight and relationship differences
- Processing efficiency metrics

### Example Output

#### Traditional Segment Processing:
```
Processing: episode_001.vtt
✓ Success - 103 segments processed
  - 412 entities extracted
  - 89 relationships found
```

#### Semantic Processing:
```
Processing: episode_001.vtt
✓ Success - 103 segments processed
  - 12 meaningful units identified
  - 3 conversation themes detected
  - 187 entities extracted (54% reduction)
  - 124 relationships found
```

## Architecture

### Components

1. **ConversationAnalyzer**: Analyzes transcript structure using LLM
   - Identifies natural conversation boundaries
   - Detects topic transitions
   - Finds incomplete thoughts due to arbitrary segmentation

2. **SegmentRegrouper**: Groups segments into meaningful units
   - Combines related segments
   - Preserves speaker information
   - Calculates unit statistics

3. **MeaningfulUnitExtractor**: Extracts knowledge from units
   - Provides full context to extraction
   - Generates unit-level insights
   - Identifies cross-segment patterns

4. **MeaningfulUnitEntityResolver**: Enhanced entity resolution
   - Resolves pronouns within unit context
   - Identifies canonical entity forms
   - Tracks entity appearances across units

5. **SemanticPipelineExecutor**: Orchestrates the semantic pipeline
   - 5-phase processing: analyze → regroup → extract → resolve → store
   - Stores conversation structure to Neo4j
   - Provides performance metrics

### Data Models

#### ConversationStructure
```python
{
    "units": [ConversationUnit, ...],    # Semantic units
    "themes": [ConversationTheme, ...],  # Major themes
    "boundaries": [ConversationBoundary, ...],  # Topic shifts
    "flow": ConversationFlow,            # Narrative arc
    "insights": StructuralInsights       # Quality observations
}
```

#### MeaningfulUnit
```python
{
    "id": "unit_001",
    "segments": [TranscriptSegment, ...],
    "unit_type": "topic_discussion",  # or story, q&a_pair, etc.
    "summary": "Discussion about AI in healthcare",
    "themes": ["AI", "Healthcare"],
    "start_time": 0.0,
    "end_time": 300.0,
    "speaker_distribution": {"Host": 40.0, "Guest": 60.0},
    "is_complete": true
}
```

## Neo4j Storage

Semantic processing adds additional nodes and relationships:

### New Node Types
- **ConversationStructure**: Overall episode structure
- **MeaningfulUnit**: Semantic units within episodes
- **Theme**: Conversation themes

### New Relationships
- Episode → HAS_STRUCTURE → ConversationStructure
- ConversationStructure → CONTAINS_UNIT → MeaningfulUnit
- ConversationStructure → CONTAINS_THEME → Theme
- MeaningfulUnit → EXPLORES_THEME → Theme
- Theme → CONNECTED_TO → Entity

## Performance Optimization

Semantic processing includes several optimizations:

1. **Conversation Structure Caching**: Analysis results are cached (60min TTL)
2. **Batch Processing**: Units processed in optimized groups
3. **Memory Management**: Automatic cleanup between processing phases
4. **Performance Monitoring**: Built-in benchmarking and metrics

### Performance Metrics
```json
{
    "conversation_analysis": 2.5,    // seconds
    "segment_regrouping": 0.3,
    "knowledge_extraction": 15.2,
    "entity_resolution": 1.8,
    "graph_storage": 3.1,
    "total_time": 22.9
}
```

## Configuration

### Environment Variables
```bash
# Enable semantic processing by default
export VTT_SEMANTIC_PROCESSING=true

# Set cache TTL (minutes)
export VTT_STRUCTURE_CACHE_TTL=60

# Set max parallel units for batch processing
export VTT_MAX_PARALLEL_UNITS=3
```

### Configuration File
```yaml
# config.yaml
semantic_processing:
  enabled: true
  cache_ttl_minutes: 60
  max_parallel_units: 3
  conversation_analyzer:
    temperature: 0.1  # Low for consistent analysis
  entity_resolver:
    similarity_threshold: 0.85
```

## Best Practices

1. **File Selection**: Process complete episodes for best results
2. **LLM Model**: Use models with 1M+ token context (e.g., Gemini 1.5)
3. **Batch Size**: Process 3-5 files in parallel for optimal throughput
4. **Monitoring**: Check performance metrics to identify bottlenecks
5. **Validation**: Use --compare-methods to validate improvements

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Solution: Reduce parallel workers or batch size
   - Monitor with performance metrics

2. **Slow Processing**
   - Check if conversation structure is being cached
   - Verify LLM API rate limits
   - Consider using parallel processing

3. **Poor Unit Boundaries**
   - Review conversation analyzer prompts
   - Check segment quality (speaker labels, timing)
   - Adjust temperature settings

### Debug Mode
```bash
# Enable verbose logging for semantic processing
vtt-kg process-vtt --folder /path/to/vtt --semantic --verbose

# Check specific phase performance
export VTT_LOG_LEVEL=DEBUG
```

## Future Enhancements

1. **Cross-Episode Analysis**: Identify recurring themes across episodes
2. **Speaker Profiles**: Build comprehensive speaker knowledge graphs
3. **Conversation Patterns**: Detect common interview structures
4. **Auto-Segmentation**: Improve unit boundary detection
5. **Streaming Support**: Process live transcripts in real-time