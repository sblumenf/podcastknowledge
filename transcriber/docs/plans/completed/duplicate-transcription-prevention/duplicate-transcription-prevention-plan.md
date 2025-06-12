# Duplicate Transcription Prevention Implementation Plan

**Status**: COMPLETED  
**Completion Date**: 2025-06-10

## Executive Summary

This plan implements automatic duplicate prevention in the podcast transcription system. The system will check for existing VTT files before transcribing episodes, skip already-transcribed content, and maintain a simple JSON tracking file. This prevents wasted compute resources and API costs from re-transcribing episodes.

## Phase 1: Progress Tracking Infrastructure

### Task 1.1: Create Progress Tracker Module
- [x] Create `src/progress_tracker.py` module
- **Purpose**: Centralize tracking of transcribed episodes
- **Steps**:
  1. Use context7 MCP tool to review documentation for any existing progress tracking patterns
  2. Create new file `src/progress_tracker.py`
  3. Implement `ProgressTracker` class with methods:
     - `__init__(self, tracking_file_path: str = "data/transcribed_episodes.json")`
     - `load_progress(self) -> Dict[str, List[str]]` - loads tracking file
     - `save_progress(self, progress: Dict[str, List[str]])` - saves tracking file
     - `is_episode_transcribed(self, podcast_name: str, episode_title: str) -> bool`
     - `mark_episode_transcribed(self, podcast_name: str, episode_title: str, date: str)`
     - `get_transcribed_episodes(self, podcast_name: str) -> List[str]`
  4. Handle file not found gracefully (create empty dict)
  5. Use file locking for concurrent access safety
- **Validation**: Unit tests pass for all methods

### Task 1.2: Add Progress Tracker Tests
- [x] Create comprehensive test suite for ProgressTracker
- **Purpose**: Ensure reliability of tracking system
- **Steps**:
  1. Use context7 MCP tool to review test patterns in codebase
  2. Create `tests/test_progress_tracker.py`
  3. Test scenarios:
     - Loading non-existent file creates empty tracker
     - Saving and loading round-trip works
     - Episode marking and checking works correctly
     - Concurrent access doesn't corrupt data
     - Invalid JSON handling
- **Validation**: All tests pass with 100% coverage

## Phase 2: Integrate Duplicate Checking

### Task 2.1: Update SimpleOrchestrator to Check Progress
- [x] Modify `simple_orchestrator.py` to skip transcribed episodes
- **Purpose**: Prevent duplicate transcription at the orchestration level
- **Steps**:
  1. Use context7 MCP tool to review SimpleOrchestrator documentation
  2. Import ProgressTracker in `simple_orchestrator.py`
  3. Add `progress_tracker` instance variable to SimpleOrchestrator.__init__
  4. In `process_episodes()` method:
     - Before processing each episode, check `progress_tracker.is_episode_transcribed()`
     - Skip episode with log message if already transcribed
     - After successful transcription, call `progress_tracker.mark_episode_transcribed()`
  5. Add progress summary at end (X episodes processed, Y skipped)
- **Validation**: Manually test that re-running skips episodes

### Task 2.2: Remove JSON Metadata File Generation
- [x] Update file organizer to only save VTT files
- **Purpose**: Simplify output as requested by user
- **Steps**:
  1. Use context7 MCP tool to review FileOrganizer documentation
  2. In `file_organizer.py`, locate `save_transcript()` method
  3. Comment out or remove JSON file writing section
  4. Update any tests that expect JSON files
  5. Remove JSON file references from manifest updates
- **Validation**: Only VTT files appear in output directory

### Task 2.3: Update FileOrganizer Tests
- [x] Fix tests that expect JSON output files
- **Purpose**: Keep test suite passing after removing JSON generation
- **Steps**:
  1. Use context7 MCP tool to review FileOrganizer test documentation
  2. Search for tests checking JSON file existence
  3. Remove or modify assertions about JSON files
  4. Ensure VTT file tests still pass
- **Validation**: All FileOrganizer tests pass

## Phase 3: CLI Integration

### Task 3.1: Add Force Re-transcription Flag
- [x] Add `--force` flag to CLI for overriding duplicate detection
- **Purpose**: Allow users to re-transcribe if needed
- **Steps**:
  1. Use context7 MCP tool to review CLI documentation
  2. In `cli.py`, add `--force` flag to argument parser
  3. Pass force flag to SimpleOrchestrator constructor
  4. Modify orchestrator to skip duplicate check when force=True
  5. Update help text to explain flag behavior
- **Validation**: `--force` flag bypasses duplicate detection

### Task 3.2: Add Progress Status Command
- [x] Add ability to check transcription progress
- **Purpose**: Let users see what's been transcribed
- **Steps**:
  1. Use context7 MCP tool to review CLI command patterns
  2. Add `--status` flag to CLI
  3. When flag is present, display:
     - Total episodes transcribed per podcast
     - List of transcribed episode titles
     - Exit without processing
  4. Format output in readable table
- **Validation**: `--status` shows accurate progress information

## Phase 4: Migration and Cleanup

### Task 4.1: Create Migration Script for Existing Transcriptions
- [x] Build initial progress file from existing VTT files
- **Purpose**: Recognize already transcribed episodes
- **Steps**:
  1. Use context7 MCP tool to review any migration patterns
  2. Create `scripts/migrate_existing_transcriptions.py`
  3. Script should:
     - Scan `output/transcripts/` directory
     - Parse existing VTT filenames
     - Build progress tracker data structure
     - Save to `data/transcribed_episodes.json`
  4. Handle edge cases (malformed filenames, etc.)
- **Validation**: Progress file accurately reflects existing transcriptions

### Task 4.2: Update Documentation
- [x] Document the duplicate prevention feature
- **Purpose**: Help users understand new behavior
- **Steps**:
  1. Use context7 MCP tool to review documentation structure
  2. Update README.md with:
     - Explanation of automatic duplicate skipping
     - How to use `--force` flag
     - How to check progress with `--status`
     - Location of progress tracking file
  3. Add docstrings to new ProgressTracker class
- **Validation**: Documentation clearly explains feature

## Success Criteria

1. **Automatic Skipping**: Running transcription twice skips already-processed episodes
2. **Progress Tracking**: `data/transcribed_episodes.json` accurately tracks completed work
3. **No JSON Output**: Only VTT files are saved to output directory
4. **Force Override**: `--force` flag allows re-transcription when needed
5. **Status Visibility**: Users can check progress with `--status` flag
6. **Backward Compatible**: Existing transcriptions are recognized via migration
7. **Performance**: Duplicate checking adds <100ms to startup time
8. **Tests Pass**: All existing and new tests pass

## Technology Requirements

No new technologies required. Uses only:
- Python standard library (json, os, threading for file locks)
- Existing project structure and patterns

## Risk Mitigation

1. **File Corruption**: Use atomic writes and file locking for progress file
2. **Performance**: Cache progress data in memory during batch processing
3. **Migration Errors**: Migration script is idempotent and can be re-run safely
4. **Backwards Compatibility**: Old behavior available via `--force` flag