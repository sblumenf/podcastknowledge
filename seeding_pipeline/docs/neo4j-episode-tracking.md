# Neo4j Episode Tracking System

## Overview

The VTT Knowledge Graph Pipeline uses Neo4j as the single source of truth for tracking episode processing status. This approach eliminates synchronization issues between different components and provides a unified view of processing progress.

## Key Principles

1. **Single Source of Truth**: Neo4j is the authoritative source for episode status
2. **Automatic Tracking**: The orchestrator automatically tracks episodes during processing
3. **No File-Based Tracking**: No separate checkpoint files or JSON tracking files
4. **Deletion Aware**: If an episode is deleted from Neo4j, it's automatically considered unprocessed

## Episode Tracking Properties

Episodes in Neo4j use the following properties for tracking:

- `processing_status`: Either 'complete' or 'failed'
- `processed_at`: DateTime when the episode was processed
- `file_hash`: MD5 hash of the VTT file for change detection
- `segment_count`: Number of segments processed
- `entity_count`: Number of entities extracted
- `vtt_path`: Original VTT file path
- `podcast_id`: Identifier of the podcast
- `error_message`: Error details if processing failed

## Usage

### Checking Episode Status

Use the CLI status command to check episode processing status:

```bash
# List all episodes with their status
python -m src.cli.cli status episodes

# List episodes for a specific podcast
python -m src.cli.cli status episodes --podcast my_podcast

# Show unprocessed VTT files
python -m src.cli.cli status pending --podcast my_podcast

# Show aggregate statistics
python -m src.cli.cli status stats
python -m src.cli.cli status stats --podcast my_podcast
```

### Force Reprocessing

To reprocess episodes that are already marked as complete:

```bash
python -m src.cli.cli process-vtt --folder transcripts/ --force
```

### Migration from File-Based Tracking

If you have existing episodes in Neo4j that need tracking properties:

```bash
# Dry run to see what would be updated
python scripts/migrate_to_neo4j_tracking.py --dry-run

# Apply migration
python scripts/migrate_to_neo4j_tracking.py
```

## Implementation Details

### Episode ID Generation

Episode IDs are generated from VTT filenames using the format:
```
{podcast_id}_{date}_{normalized_title}
```

Example: `my_podcast_2024-01-15_introduction_to_ai`

### Change Detection

The system calculates MD5 hashes of VTT files. If a file's content changes, its hash will differ from the stored hash, and the episode can be reprocessed.

### Automatic Skipping

During normal processing, the orchestrator automatically:
1. Generates episode ID from VTT filename
2. Checks if episode exists in Neo4j with `processing_status = 'complete'`
3. Skips processing if already complete
4. Processes and marks as complete if not

## Benefits

1. **Consistency**: All components query the same source
2. **Reliability**: No file corruption or sync issues
3. **Simplicity**: Fewer moving parts to manage
4. **Visibility**: Easy to query processing status with Cypher
5. **Integration**: Works naturally with the knowledge graph

## Troubleshooting

### Episodes Not Being Tracked

Check that episodes have the required properties:
```cypher
MATCH (e:Episode)
WHERE e.processing_status IS NULL
RETURN e.id, e.title
```

### Reset Episode Status

To mark an episode for reprocessing:
```cypher
MATCH (e:Episode {id: "episode_id"})
REMOVE e.processing_status, e.processed_at
```

### View Processing History

```cypher
MATCH (e:Episode)
WHERE e.processing_status = 'complete'
RETURN e.id, e.processed_at, e.segment_count
ORDER BY e.processed_at DESC
LIMIT 10
```