# Process Episode Implementation

## Overview

The `process_episode` function in `process_single_vtt.py` is now a fully functional implementation that processes podcast episode transcripts through the semantic knowledge extraction pipeline.

## Location

- **File**: `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/process_single_vtt.py`
- **Function**: `process_episode(vtt_file_path: Path, podcast_name: str, episode_title: str) -> Dict[str, Any]`

## What It Does

The function implements the complete semantic knowledge extraction pipeline:

1. **Parse VTT File**: Converts VTT transcript files into structured segments
2. **Analyze Conversation Structure**: Uses AI to identify themes, narrative flow, and conversation patterns
3. **Create Semantic Units**: Groups related segments into meaningful units (topics, Q&A pairs, stories)
4. **Extract Knowledge**: 
   - Entities (people, organizations, concepts, etc.)
   - Quotes (important statements with context)
   - Insights (key learnings and observations)
   - Relationships (connections between entities)
5. **Resolve Entities**: Creates canonical entities by merging duplicates across the episode
6. **Store in Neo4j**: Creates a rich knowledge graph with all extracted information

## Usage Example

```python
from pathlib import Path
from process_single_vtt import process_episode

# Process an episode
results = process_episode(
    vtt_file_path=Path("/path/to/transcript.vtt"),
    podcast_name="My Podcast",
    episode_title="Episode Title"
)

# Check results
if results['status'] == 'success':
    print(f"Extracted {results['entities_extracted']} entities")
    print(f"Found {results['quotes_extracted']} quotes")
    print(f"Created {results['meaningful_units']} semantic units")
```

## Return Value

The function returns a dictionary with:

- `status`: 'success' or 'error'
- `processing_type`: Usually 'semantic'
- `segments_processed`: Number of VTT segments processed
- `meaningful_units`: Number of semantic units created
- `entities_extracted`: Number of entities found
- `quotes_extracted`: Number of quotes extracted
- `insights_extracted`: Number of insights generated
- `relationships_discovered`: Number of relationships found
- `themes_identified`: List of themes discovered
- `processing_time`: Time taken in seconds
- `graph_nodes_created`: Number of Neo4j nodes created
- `graph_relationships_created`: Number of Neo4j relationships created
- `file_hash`: SHA256 hash of the VTT file
- `episode_id`: Unique identifier for the episode
- `conversation_structure`: Details about narrative arc and coherence

## Under the Hood

The function uses:

- **MultiPodcastVTTKnowledgeExtractor**: Main orchestrator class
- **SemanticPipelineExecutor**: Processes segments using semantic analysis
- **ConversationAnalyzer**: Analyzes conversation structure
- **SegmentRegrouper**: Groups segments into meaningful units
- **MeaningfulUnitExtractor**: Extracts knowledge from semantic units
- **MeaningfulUnitEntityResolver**: Resolves entities across units
- **GraphStorageService**: Stores everything in Neo4j

## Requirements

- Neo4j database running and accessible
- Gemini API key configured
- Python dependencies installed
- VTT transcript file to process

## Error Handling

The function includes comprehensive error handling:
- Returns error status with details if processing fails
- Cleans up resources in finally block
- Logs errors for debugging

This implementation represents the real processing logic used by the seeding pipeline, not a dummy placeholder.