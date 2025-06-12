# Single to Multi-Podcast Implementation Plan

## Executive Summary

This plan implements a two-phase approach to create a podcast knowledge extraction system. Phase 1 establishes a working single-podcast pipeline where VTT transcript files are automatically processed into a Neo4j knowledge graph. Phase 2 extends this to support multiple podcasts with separate knowledge graphs, preparing for future UI and agent integration.

## Phase 1: Single Podcast Data Flow

### Overview
Create an end-to-end pipeline where the transcriber module outputs VTT files to a shared directory, and the seeding pipeline automatically processes them into a Neo4j knowledge graph.

### Prerequisites
- [x] Verify Neo4j is running and accessible
  - Purpose: Ensure database is ready for knowledge graph storage
  - Steps:
    1. Check Neo4j service status with `neo4j status`
    2. Verify connection at http://localhost:7474
    3. Test authentication with configured credentials
  - Validation: Successfully connect to Neo4j browser

- [x] Verify API keys are configured
  - Purpose: Ensure all services can authenticate
  - Steps:
    1. Check transcriber/.env for DEEPGRAM_API_KEY
    2. Check seeding_pipeline/.env for GEMINI_API_KEY
    3. Verify NEO4J_URI and credentials in seeding_pipeline/.env
  - Validation: No missing API key errors when running modules

### Task 1: Create Shared Data Directory Structure

- [x] Create the shared data directory hierarchy
  - Purpose: Establish consistent file handoff location between modules
  - Steps:
    1. Use context7 MCP tool to review directory structure best practices
    2. Create `/data` directory at project root
    3. Create `/data/transcripts` subdirectory for transcriber output
    4. Create `/data/processed` subdirectory for completed files
    5. Create `/data/logs` subdirectory for processing logs
    6. Set appropriate permissions (readable/writable by application)
  - Validation: Directory structure exists and is accessible

### Task 2: Configure Transcriber Module

- [x] Update transcriber environment configuration
  - Purpose: Direct transcriber output to shared location
  - Steps:
    1. Use context7 MCP tool to review transcriber configuration documentation
    2. Edit `transcriber/.env` file
    3. Add `PODCAST_DATA_DIR=/data`
    4. Add `TRANSCRIPT_OUTPUT_DIR=/data/transcripts`
    5. Verify no hardcoded paths in `transcriber/src/file_organizer.py`
  - Validation: Environment variables are set correctly

- [x] Update transcriber file organizer
  - Purpose: Ensure transcriber writes to shared directory
  - Steps:
    1. Use context7 MCP tool for file organizer patterns
    2. Review `transcriber/src/file_organizer.py`
    3. Modify output directory logic to use TRANSCRIPT_OUTPUT_DIR
    4. Ensure podcast subdirectory creation is maintained
    5. Add logging for output file paths
  - Validation: Transcriber creates files in `/data/transcripts/`

### Task 3: Configure Seeding Pipeline Module

- [x] Update seeding pipeline environment configuration
  - Purpose: Configure pipeline to read from shared location
  - Steps:
    1. Use context7 MCP tool to review seeding pipeline configuration
    2. Edit `seeding_pipeline/.env` file
    3. Add `PODCAST_DATA_DIR=/data`
    4. Add `VTT_INPUT_DIR=/data/transcripts`
    5. Add `PROCESSED_DIR=/data/processed`
  - Validation: Environment variables are set correctly

- [x] Update seeding pipeline input paths
  - Purpose: Ensure pipeline reads from correct location
  - Steps:
    1. Use context7 MCP tool for CLI patterns
    2. Review `seeding_pipeline/src/cli/cli.py`
    3. Update default input folder to use VTT_INPUT_DIR
    4. Add processed directory configuration
    5. Ensure recursive scanning is enabled
  - Validation: Pipeline discovers files in shared directory

### Task 4: Implement Duplicate Processing Prevention

- [x] Add processed file tracking
  - Purpose: Prevent reprocessing of completed files
  - Steps:
    1. Use context7 MCP tool for file tracking patterns
    2. Modify `seeding_pipeline/src/seeding/transcript_ingestion.py`
    3. Add check for file existence in processed directory
    4. Implement file move after successful processing
    5. Add error handling for move failures
  - Validation: Files move to processed directory after completion

- [x] Update checkpoint system
  - Purpose: Integrate with existing checkpoint mechanism
  - Steps:
    1. Review checkpoint handling in `seeding_pipeline/src/seeding/checkpoint.py`
    2. Add processed file list to checkpoint data
    3. Ensure checkpoint includes file move status
    4. Add recovery logic for partial moves
  - Validation: Checkpoints track processed files correctly

### Task 5: Create Integration Tests

- [x] Create end-to-end test with sample VTT files
  - Purpose: Verify complete data flow works
  - Steps:
    1. Use context7 MCP tool for test patterns
    2. Create `tests/integration/test_data_flow.py`
    3. Copy 4 existing VTT files to test fixtures
    4. Write test that places files in transcripts directory
    5. Verify files are processed and moved
    6. Check Neo4j for created nodes
  - Validation: Test passes with all files processed

- [x] Create error handling tests
  - Purpose: Ensure graceful failure handling
  - Steps:
    1. Use context7 MCP tool for error handling patterns
    2. Test with malformed VTT file
    3. Test with Neo4j connection failure
    4. Test with file permission errors
    5. Verify appropriate error messages and recovery
  - Validation: Errors are handled without data loss

### Task 6: Create Run Scripts

- [x] Create unified run script
  - Purpose: Simplify running both modules
  - Steps:
    1. Use context7 MCP tool for script best practices
    2. Create `run_pipeline.sh` at project root
    3. Add environment setup
    4. Add option to run transcriber only
    5. Add option to run seeding only
    6. Add option to run both sequentially
  - Validation: Script executes without errors

### Task 7: Process Test Episodes

- [ ] Run pipeline with 4 test VTT files
  - Purpose: Validate real-world functionality
  - Steps:
    1. Place 4 VTT files in `/data/transcripts`
    2. Run seeding pipeline
    3. Monitor processing logs
    4. Verify files move to processed
    5. Query Neo4j for extracted knowledge
  - Validation: All 4 files processed successfully

## Phase 2: Multi-Podcast Support

### Overview
Extend the single-podcast pipeline to support multiple podcasts with separate Neo4j databases and organized directory structures.

### Task 8: Implement Podcast-Aware Directory Structure

- [ ] Create podcast-specific directory structure
  - Purpose: Organize files by podcast for scalability
  - Steps:
    1. Use context7 MCP tool for multi-tenant patterns
    2. Modify shared directory to `/data/podcasts/{podcast_id}/`
    3. Create subdirectories: `transcripts/`, `processed/`, `checkpoints/`
    4. Update both module configurations
    5. Add podcast detection logic
  - Validation: Directories created per podcast

### Task 9: Implement Podcast Identification

- [ ] Add podcast ID extraction from VTT files
  - Purpose: Route files to correct podcast context
  - Steps:
    1. Use context7 MCP tool for metadata extraction patterns
    2. Analyze VTT file structure for podcast identifiers
    3. Implement extraction in `seeding_pipeline/src/vtt/vtt_parser.py`
    4. Add fallback to filename parsing
    5. Add podcast ID to processing context
  - Validation: Podcast ID correctly identified

### Task 10: Implement Multi-Database Support

- [ ] Add database routing configuration
  - Purpose: Support separate Neo4j databases per podcast
  - Steps:
    1. Use context7 MCP tool for database patterns
    2. Create podcast-to-database mapping config
    3. Modify `seeding_pipeline/src/storage/graph_storage.py`
    4. Add dynamic database connection logic
    5. Implement connection pooling
  - Validation: Connect to different databases per podcast

- [ ] Update storage coordinator
  - Purpose: Route data to correct database
  - Steps:
    1. Use context7 MCP tool for coordinator patterns
    2. Modify `seeding_pipeline/src/storage/storage_coordinator.py`
    3. Add podcast context to storage calls
    4. Ensure proper database selection
    5. Add connection validation
  - Validation: Data stored in correct database

### Task 11: Update Processing Pipeline

- [ ] Add podcast context throughout pipeline
  - Purpose: Maintain podcast identity during processing
  - Steps:
    1. Use context7 MCP tool for context propagation patterns
    2. Update `seeding_pipeline/src/seeding/orchestrator.py`
    3. Pass podcast ID through all processing stages
    4. Update checkpoint system for per-podcast state
    5. Modify batch processor for podcast awareness
  - Validation: Podcast context maintained throughout

### Task 12: Create Podcast Configuration System

- [ ] Implement podcast registry
  - Purpose: Manage podcast configurations
  - Steps:
    1. Use context7 MCP tool for configuration patterns
    2. Create `config/podcasts.yaml` format
    3. Include: ID, name, database URL, settings
    4. Add configuration loader
    5. Add validation for new podcasts
  - Validation: Podcasts configured via YAML

### Task 13: Update CLI for Multi-Podcast

- [ ] Add podcast selection to CLI
  - Purpose: Allow processing specific podcasts
  - Steps:
    1. Use context7 MCP tool for CLI patterns
    2. Add `--podcast` flag to seeding CLI
    3. Add `--all-podcasts` flag for batch processing
    4. Update help documentation
    5. Add podcast listing command
  - Validation: Can process individual or all podcasts

### Task 14: Create Multi-Podcast Tests

- [ ] Create multi-podcast integration test
  - Purpose: Verify podcast isolation works
  - Steps:
    1. Use context7 MCP tool for integration test patterns
    2. Create test with 2 different podcasts
    3. Process files for both podcasts
    4. Verify data separation in Neo4j
    5. Test cross-podcast query prevention
  - Validation: Complete podcast isolation verified

### Task 15: Performance Optimization

- [ ] Add concurrent podcast processing
  - Purpose: Improve throughput for multiple podcasts
  - Steps:
    1. Use context7 MCP tool for concurrency patterns
    2. Implement thread pool for podcast processing
    3. Add rate limiting per podcast
    4. Ensure database connection limits
    5. Add performance metrics
  - Validation: Multiple podcasts process concurrently

## Success Criteria

### Phase 1 Success Criteria
- VTT files placed in `/data/transcripts` are automatically discovered
- Files are processed into Neo4j knowledge graph
- Processed files move to `/data/processed`
- No duplicate processing occurs
- Integration tests pass
- 4 test VTT files successfully processed

### Phase 2 Success Criteria
- Multiple podcasts can be configured
- Each podcast has separate Neo4j database
- Files are correctly routed by podcast
- Podcast isolation is maintained
- Can process single or multiple podcasts
- Performance scales with podcast count

## Technology Requirements

### Existing Technologies (No Approval Needed)
- Python (existing)
- Neo4j (existing)
- Gemini API (existing)
- Deepgram API (existing)

### New Technologies (Requires Approval)
- None required for Phase 1 & 2

## Future Considerations

This architecture supports future additions:
- Web UI dashboard (Phase 3)
- Monitoring agents (Phase 4)
- Social media agents (Phase 5)
- Cross-podcast analytics (Phase 6)

The modular approach ensures each phase builds on the previous without breaking changes.