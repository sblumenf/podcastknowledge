# Neo4j Unified Tracking Implementation Plan

**Status**: DRAFT  
**Created**: January 13, 2025

## Executive Summary

This plan implements a unified tracking system where Neo4j serves as the single source of truth for processed episodes across both transcription and seeding workflows. The transcriber will check Neo4j before transcribing to prevent duplicate API costs, with automatic detection of combined mode operation. VTT files will be archived in podcast-specific processed directories after successful knowledge extraction. The implementation maintains the multi-podcast architecture with separate Neo4j databases per podcast.

## Phase 1: Cross-Module Integration Foundation

### Task 1.1: Create Shared Tracking Interface
- [ ] Create shared tracking module accessible by both transcriber and seeding_pipeline
- Purpose: Enable transcriber to check Neo4j without tight coupling
- Steps:
  1. Use context7 MCP tool to review Python module import patterns
  2. Create `/shared/tracking_bridge.py` at repository root
  3. Implement `TranscriptionTracker` class with minimal interface:
     - `should_transcribe(podcast_id: str, episode_title: str, date: str) -> bool`
     - `get_neo4j_tracker(podcast_id: str) -> Optional[EpisodeTracker]`
  4. Add logic to handle multi-podcast database routing
  5. Implement fallback when Neo4j unavailable
- Validation: Import works from both transcriber and seeding_pipeline

### Task 1.2: Add Neo4j Connection to Transcriber
- [ ] Enable transcriber to connect to Neo4j when available
- Purpose: Allow transcriber to check episode status before processing
- Steps:
  1. Use context7 MCP tool to review Neo4j Python driver connection patterns
  2. Add optional Neo4j import to transcriber requirements
  3. Create connection factory in tracking_bridge that:
     - Reads podcast config from `seeding_pipeline/config/podcasts.yaml`
     - Returns appropriate database connection per podcast
     - Returns None if Neo4j unavailable (graceful degradation)
  4. Add connection pooling to avoid creating multiple connections
- Validation: Transcriber can optionally connect to Neo4j

### Task 1.3: Implement Episode ID Consistency
- [ ] Ensure episode IDs match between transcriber filename generation and seeding tracker
- Purpose: Consistent episode identification across modules
- Steps:
  1. Use context7 MCP tool to review string normalization best practices
  2. Extract episode ID generation logic to shared module
  3. Update transcriber's `file_organizer_simple.py` to use shared logic
  4. Verify `generate_episode_id` produces same output for same input
  5. Add unit tests for edge cases (special characters, dates)
- Validation: Same episode generates identical ID in both modules

## Phase 2: Transcriber Neo4j Checking

### Task 2.1: Add Pre-Transcription Check
- [ ] Implement Neo4j lookup before transcription
- Purpose: Skip transcription if episode already fully processed
- Steps:
  1. Use context7 MCP tool to review transcriber's main processing loop
  2. Modify `simple_orchestrator.py` process_episode method:
     ```python
     # After episode discovery, before transcription
     if tracking_bridge.should_transcribe(podcast_id, episode.title, episode.date):
         # Proceed with transcription
     else:
         logger.info(f"Episode already in knowledge graph, skipping transcription")
     ```
  3. Ensure check happens after RSS parsing but before Deepgram API call
  4. Add metrics for skipped episodes
- Validation: Episodes in Neo4j skip transcription

### Task 2.2: Update Progress Tracking Logic
- [ ] Modify transcriber's progress tracker to be Neo4j-aware
- Purpose: Maintain backwards compatibility while adding Neo4j checking
- Steps:
  1. Use context7 MCP tool to review progress_tracker.py patterns
  2. Update `is_episode_transcribed` to also check Neo4j when available
  3. Keep existing JSON tracking for transcriber-only mode
  4. Add logging to show which tracking source made decision
  5. Ensure --force flag bypasses both checks
- Validation: Both tracking systems work harmoniously

### Task 2.3: Handle Multi-Podcast Context
- [ ] Ensure transcriber uses correct Neo4j database per podcast
- Purpose: Support multi-podcast architecture
- Steps:
  1. Use context7 MCP tool to review multi-podcast handling in seeding_pipeline
  2. Pass podcast_id from RSS feed metadata through to tracking checks
  3. Use PodcastDirectoryManager patterns for consistency
  4. Test with multiple podcast configurations
- Validation: Each podcast checks its own Neo4j database

## Phase 3: Auto-Detection of Combined Mode

### Task 3.1: Implement Smart Mode Detection
- [ ] Auto-detect when running in combined vs independent mode
- Purpose: No manual configuration needed
- Steps:
  1. Use context7 MCP tool to review environment detection patterns
  2. Add detection logic to tracking_bridge:
     - Check if called from `run_pipeline.sh` (via env variable)
     - Check if Neo4j is available and accessible
     - Check if seeding_pipeline config exists
  3. Set `combined_mode = True` when all conditions met
  4. Log detected mode for transparency
- Validation: Correct mode detected automatically

### Task 3.2: Update run_pipeline.sh
- [ ] Add environment marker for combined execution
- Purpose: Help modules detect combined mode
- Steps:
  1. Use context7 MCP tool to review bash scripting best practices
  2. Add to run_pipeline.sh before calling modules:
     ```bash
     export PODCAST_PIPELINE_MODE="combined"
     ```
  3. Clear variable when running individual modules
  4. Document in script comments
- Validation: Environment variable set correctly

## Phase 4: VTT Archive Implementation

### Task 4.1: Modify Seeding Pipeline File Handling
- [ ] Change from deletion to archiving after successful processing
- Purpose: Keep VTT files for future reprocessing
- Steps:
  1. Use context7 MCP tool to review file movement patterns in Python
  2. Update `transcript_ingestion.py` post-processing:
     - Current: Moves to flat processed directory
     - New: Maintains podcast directory structure
  3. Update archive path to: `/data/podcasts/{podcast_id}/processed/`
  4. Preserve original filename and directory structure
  5. Add file permissions to prevent accidental deletion
- Validation: VTT files archived with structure preserved

### Task 4.2: Update Episode Tracking with Archive Path
- [ ] Store archive location in Neo4j
- Purpose: Track where original VTT file is archived
- Steps:
  1. Use context7 MCP tool to review Neo4j property update patterns
  2. Add to episode completion metadata:
     ```python
     metadata['archive_path'] = str(archive_path)
     metadata['archived_at'] = datetime.now()
     ```
  3. Update `mark_episode_complete` to include archive info
  4. Add method to retrieve archive path by episode_id
- Validation: Neo4j contains archive location

### Task 4.3: Add Archive Management Commands
- [ ] Create CLI commands for archive management
- Purpose: Easy access to archived VTT files
- Steps:
  1. Use context7 MCP tool to review Click CLI command patterns
  2. Add to seeding pipeline CLI:
     - `archive list --podcast <id>`: List archived files
     - `archive path <episode_id>`: Get archive path for episode
  3. Include file size and date information
  4. Format output as table using rich library
- Validation: Commands show archived file information

## Phase 5: Testing and Validation

### Task 5.1: Create Integration Tests
- [ ] Test cross-module tracking functionality
- Purpose: Ensure system works as designed
- Steps:
  1. Use context7 MCP tool to review pytest integration test patterns
  2. Create `tests/integration/test_unified_tracking.py`
  3. Test scenarios:
     - Episode not in Neo4j → transcribes normally
     - Episode in Neo4j → skips transcription
     - Neo4j unavailable → falls back to JSON tracking
     - Force flag → transcribes regardless
  4. Mock external services (Deepgram, Neo4j)
- Validation: All test scenarios pass

### Task 5.2: Add Monitoring and Metrics
- [ ] Track unified pipeline performance
- Purpose: Monitor cost savings and system health
- Steps:
  1. Use context7 MCP tool to review metrics collection patterns
  2. Add metrics for:
     - Episodes skipped due to Neo4j check
     - Transcription costs saved
     - Archive storage used per podcast
  3. Update Prometheus metrics endpoint
  4. Add to CLI status command
- Validation: Metrics show cost savings

### Task 5.3: Update Documentation
- [ ] Document the unified tracking system
- Purpose: Maintain clear system documentation
- Steps:
  1. Use context7 MCP tool to review documentation standards
  2. Update README.md with new architecture
  3. Add sequence diagram for combined workflow
  4. Document environment variables and auto-detection
  5. Add troubleshooting section
- Validation: Documentation review complete

## Success Criteria

1. **Cost Savings**: No duplicate transcription API calls when episode exists in Neo4j
2. **Zero Configuration**: System auto-detects combined mode without manual setup
3. **Archive Completeness**: All processed VTT files archived in podcast-specific directories
4. **Performance**: Neo4j checks complete in <100ms per episode
5. **Backwards Compatibility**: Independent module operation still works

## Technology Requirements

**No new technologies required**
- Uses existing Neo4j Python driver
- Uses existing file system operations
- Leverages current multi-podcast architecture
- Minimal new dependencies (already available)

## Risk Mitigation

1. **Cross-Module Imports**: Use try/except for optional imports
2. **Neo4j Availability**: Graceful fallback to file-based tracking
3. **Archive Storage**: Monitor disk space, implement rotation if needed
4. **Performance**: Connection pooling and caching for Neo4j queries