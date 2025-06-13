# Neo4j Episode Tracking Implementation Plan

## Executive Summary

This plan will replace all existing tracking mechanisms (transcribed_episodes.json, vtt_processed.json, checkpoint files) with a simple Neo4j-based tracking system. Episodes in Neo4j with `processing_status = 'complete'` are considered fully processed. Any episode not in Neo4j or without complete status is considered unprocessed. This provides a single source of truth that automatically handles deletions and eliminates sync issues between components.

## Phase 1: Core Tracking Implementation

### Task 1.1: Create Episode Tracker Module
- [x] Create new file `src/tracking/episode_tracker.py`
  - Purpose: Centralize all episode tracking logic in one module
  - Steps:
    1. Use context7 MCP tool to review Neo4j Python driver documentation
    2. Create `EpisodeTracker` class with dependency injection for graph storage
    3. Implement core methods:
       - `is_episode_processed(episode_id: str) -> bool`
       - `mark_episode_complete(episode_id: str, file_hash: str, metadata: dict)`
       - `get_processed_episodes(podcast_id: str) -> List[Dict]`
       - `get_pending_episodes(podcast_id: str, vtt_files: List[str]) -> List[str]`
    4. Add logging for all database operations
  - Validation: Unit tests pass with mocked graph storage

### Task 1.2: Define Episode Node Properties
- [x] Define common Episode node properties for tracking
  - Purpose: Establish tracking properties without enforcing schema
  - Steps:
    1. Use context7 MCP tool to review Neo4j schemaless patterns
    2. Define commonly used properties for Episode nodes:
       - `id`: String (format: `{podcast_id}_{date}_{normalized_title}`)
       - `podcast_id`: String (podcast identifier)
       - `processing_status`: String (values: 'complete', 'failed')
       - `file_hash`: String (MD5 hash of VTT file)
       - `processed_at`: DateTime
       - `vtt_path`: String (original file path)
       - `segment_count`: Integer (optional)
       - `entity_count`: Integer (optional)
    3. No constraints - allow flexible property addition
    4. Document common properties in code comments
  - Validation: Episode nodes can be created with tracking properties

### Task 1.3: Create Episode ID Generator
- [x] Implement consistent episode ID generation
  - Purpose: Generate unique, readable episode IDs from VTT files
  - Steps:
    1. Use context7 MCP tool to review Python string normalization
    2. Create `generate_episode_id(vtt_path: str, podcast_id: str) -> str` function
    3. Extract date from VTT filename or content
    4. Normalize title (remove special chars, lowercase, replace spaces with underscores)
    5. Combine as `{podcast_id}_{YYYY-MM-DD}_{normalized_title}`
    6. Add collision detection and resolution
  - Validation: Generates consistent IDs for same input

## Phase 2: Integration with Existing Components

### Task 2.1: Update VTT Processing Pipeline
- [ ] Integrate tracking into orchestrator
  - Purpose: Check and update episode status during processing
  - Steps:
    1. Use context7 MCP tool to review orchestrator.py documentation
    2. Inject EpisodeTracker into orchestrator initialization
    3. Add pre-processing check: `if tracker.is_episode_processed(episode_id): skip`
    4. Add post-processing update: `tracker.mark_episode_complete(episode_id, file_hash, summary)`
    5. Remove old checkpoint save/load calls
  - Validation: Processing skips completed episodes

### Task 2.2: Update CLI Commands
- [ ] Modify process-vtt command to use new tracking
  - Purpose: Use Neo4j tracking for all CLI operations
  - Steps:
    1. Use context7 MCP tool to review Click CLI documentation
    2. Update `process_vtt` command in `cli.py`
    3. Remove file-based progress tracking
    4. Add `--force` flag to reprocess completed episodes
    5. Update progress reporting to query Neo4j
  - Validation: CLI correctly identifies processed episodes

### Task 2.3: Add Status Command
- [ ] Create new CLI command for tracking status
  - Purpose: Provide visibility into processing status
  - Steps:
    1. Use context7 MCP tool to review Click command groups
    2. Add `status` command to CLI
    3. Implement subcommands:
       - `status episodes --podcast <id>`: List all episodes with status
       - `status pending --podcast <id>`: Show unprocessed VTT files
       - `status stats`: Show aggregate statistics
    4. Format output as table with rich library
  - Validation: Commands show accurate Neo4j data

## Phase 3: Remove Old Tracking Systems

### Task 3.1: Remove File-Based Tracking
- [ ] Delete old tracking code and files
  - Purpose: Eliminate confusion from multiple tracking systems
  - Steps:
    1. Use context7 MCP tool to review safe code removal practices
    2. Remove checkpoint.py episode tracking methods
    3. Delete vtt_processed.json tracking
    4. Remove transcribed_episodes.json references
    5. Update imports in affected files
    6. Clean up unused tracking directories
  - Validation: No file-based tracking remains

### Task 3.2: Update Tests
- [ ] Modify tests to use Neo4j tracking
  - Purpose: Ensure tests reflect new tracking system
  - Steps:
    1. Use context7 MCP tool to review pytest mocking
    2. Update test fixtures to mock EpisodeTracker
    3. Remove file-based tracking assertions
    4. Add Neo4j tracking assertions
    5. Ensure all tests pass
  - Validation: Test suite passes with >90% coverage

### Task 3.3: Update Metrics Collection
- [ ] Point metrics to Neo4j queries
  - Purpose: Accurate metrics from single source of truth
  - Steps:
    1. Use context7 MCP tool to review metrics.py patterns
    2. Update episode count metrics to query Neo4j
    3. Remove file-based metric sources
    4. Add Neo4j query performance metrics
    5. Test Prometheus endpoint output
  - Validation: Metrics reflect Neo4j state

## Phase 4: Migration and Cleanup

### Task 4.1: Create Migration Script
- [ ] Build script to mark existing Neo4j episodes as complete
  - Purpose: Ensure existing data has proper tracking fields
  - Steps:
    1. Use context7 MCP tool to review Neo4j bulk update patterns
    2. Create `scripts/migrate_to_neo4j_tracking.py`
    3. Query all existing Episode nodes
    4. Set `processing_status = 'complete'` for episodes with segments
    5. Calculate and set file_hash if VTT file exists
    6. Add dry-run mode for safety
  - Validation: All existing episodes have status

### Task 4.2: Documentation Update
- [ ] Update all documentation for new tracking
  - Purpose: Ensure documentation matches implementation
  - Steps:
    1. Use context7 MCP tool to review documentation standards
    2. Update README with new tracking approach
    3. Document Neo4j as single source of truth
    4. Add troubleshooting guide
    5. Update architecture diagrams
  - Validation: Documentation review complete

## Success Criteria

1. **Single Source of Truth**: All episode tracking queries go to Neo4j only
2. **No Sync Issues**: Deleting from Neo4j automatically updates tracking
3. **Performance**: Status queries complete in <100ms
4. **Simplicity**: Total tracking code reduced by >50%
5. **Reliability**: No tracking files to corrupt or desync

## Technology Requirements

- **No new technologies required**
- Uses existing Neo4j database and Python driver
- Leverages current graph storage abstraction

## Risk Mitigation

1. **Data Loss**: Neo4j backups before migration
2. **Performance**: Index on episode.processing_status
3. **Rollback**: Tag current version before changes