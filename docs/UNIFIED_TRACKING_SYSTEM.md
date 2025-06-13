# Unified Episode Tracking System

## Overview

The Unified Episode Tracking System provides a single source of truth for tracking podcast episode processing across both the transcriber and seeding pipeline modules. It uses Neo4j as the golden source of truth, ensuring that episodes are never processed twice and preventing duplicate transcription costs.

## Architecture

### Components

1. **Shared Module** (`/shared/`)
   - `episode_id.py`: Consistent episode ID generation
   - `tracking_bridge.py`: Cross-module tracking interface
   - `__init__.py`: Public API exports

2. **Transcriber Integration**
   - `simple_orchestrator.py`: Pre-transcription Neo4j checks
   - `progress_tracker.py`: Neo4j-aware progress tracking

3. **Seeding Pipeline Integration**
   - `episode_tracker.py`: Neo4j episode tracking
   - `orchestrator.py`: Archive handling after processing

4. **Neo4j Database**
   - Stores episode processing status
   - Tracks archive locations
   - Provides multi-podcast support

## Key Features

### 1. Single Source of Truth
- Neo4j database is the authoritative source for episode processing status
- File-based tracking serves as a fallback in independent mode
- Prevents duplicate processing across modules

### 2. Episode ID Consistency
- Standardized episode ID format: `{podcast_id}_{date}_{normalized_title}`
- Consistent normalization across modules
- Example: `tech_talk_2024-01-15_introductiontopodcasting`

### 3. Multi-Podcast Support
- Each podcast has its own Neo4j database
- Automatic database routing based on podcast ID
- Configuration via `podcasts.yaml`

### 4. Smart Mode Detection
- Automatically detects combined vs independent mode
- Environment variable: `PODCAST_PIPELINE_MODE`
- Fallback to module availability detection

### 5. Archive Management
- Processed VTT files are archived to `/data/podcasts/{podcast_id}/processed/`
- Archive locations stored in Neo4j
- CLI commands for archive management

## Usage

### Combined Mode (Default)

Run both transcriber and seeding pipeline together:

```bash
./run_pipeline.sh
# or
./run_pipeline.sh --both
```

In this mode:
- Transcriber checks Neo4j before transcribing
- Seeding pipeline archives processed files
- Full cross-module tracking enabled

### Independent Mode

Run modules separately:

```bash
# Transcriber only
./run_pipeline.sh --transcriber

# Seeding pipeline only
./run_pipeline.sh --seeding
```

In this mode:
- Modules run independently
- File-based tracking used by transcriber
- Neo4j tracking still used by seeding pipeline

### Archive Management

List archived files:
```bash
python -m src.cli.cli archive list --podcast-id tech_talk
```

Locate a specific episode's archive:
```bash
python -m src.cli.cli archive locate tech_talk_2024-01-15_episode1
```

Restore an archived file:
```bash
python -m src.cli.cli archive restore /data/podcasts/tech_talk/processed/2024-01-15_Episode_1.vtt
```

## Configuration

### Podcast Configuration (`seeding_pipeline/config/podcasts.yaml`)

```yaml
podcasts:
- id: tech_talk
  name: Tech Talk Podcast
  database:
    uri: neo4j://localhost:7687
    database_name: tech_talk
```

### Environment Variables

- `PODCAST_PIPELINE_MODE`: Set to "combined" or "independent"
- `TRANSCRIPT_OUTPUT_DIR`: Directory for transcriber output
- `VTT_INPUT_DIR`: Directory for seeding pipeline input
- `PROCESSED_DIR`: Directory for archived files
- `PODCAST_DATA_DIR`: Base data directory

## Episode Processing Flow

1. **Transcription Phase**
   - Check file-based tracking
   - Check Neo4j (if in combined mode)
   - Skip if already processed
   - Transcribe and save VTT file

2. **Seeding Pipeline Phase**
   - Parse VTT file
   - Extract knowledge graph
   - Store in Neo4j
   - Archive VTT file
   - Update tracking with archive path

3. **Subsequent Runs**
   - Episodes marked as complete are skipped
   - Archive paths available for retrieval
   - No duplicate processing

## Neo4j Schema

### Episode Node Properties

- `id`: Unique episode identifier
- `podcast_id`: Associated podcast
- `title`: Episode title
- `processing_status`: 'pending', 'in_progress', 'complete', 'failed'
- `processed_at`: Timestamp of completion
- `file_hash`: MD5 hash of VTT file
- `segment_count`: Number of segments processed
- `entity_count`: Number of entities extracted
- `vtt_path`: Original VTT file path
- `archive_path`: Archive location after processing

## API Reference

### Shared Module

```python
from shared import generate_episode_id, get_tracker

# Generate consistent episode ID
episode_id = generate_episode_id("2024-01-15_Episode_Title.vtt", "podcast_id")

# Get tracking bridge
tracker = get_tracker()

# Check if episode should be transcribed
should_transcribe = tracker.should_transcribe("Podcast Name", "Episode Title", "2024-01-15")
```

### Episode Tracker

```python
from src.tracking import EpisodeTracker

# Check if episode is processed
is_processed = tracker.is_episode_processed(episode_id)

# Mark episode as complete
tracker.mark_episode_complete(episode_id, file_hash, metadata)

# Get processed episodes
episodes = tracker.get_processed_episodes(podcast_id)
```

## Troubleshooting

### Neo4j Connection Issues
- Ensure Neo4j is running on port 7687
- Check database credentials in environment variables
- Verify podcast database configuration

### Episode ID Mismatches
- Ensure consistent date format (YYYY-MM-DD)
- Check title normalization rules
- Verify podcast ID mapping

### Archive Issues
- Check directory permissions
- Ensure sufficient disk space
- Verify podcast directory structure

## Benefits

1. **Cost Savings**: Prevents duplicate transcription of episodes
2. **Data Integrity**: Single source of truth in Neo4j
3. **Flexibility**: Supports both combined and independent modes
4. **Scalability**: Multi-podcast support with separate databases
5. **Auditability**: Complete tracking of processing history
6. **Recovery**: Archive management for processed files

## Future Enhancements

1. **Metrics Dashboard**: Track cost savings and processing statistics
2. **Bulk Operations**: Process multiple podcasts in parallel
3. **Content Deduplication**: Detect similar content across episodes
4. **Automatic Recovery**: Resume from failures automatically
5. **API Integration**: RESTful API for tracking queries