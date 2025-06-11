# Episode Title Normalization Implementation Plan

## Executive Summary

This plan will create a robust title normalization system that ensures consistent episode identification across the entire transcription pipeline. By implementing a single `normalize_title()` function and applying it consistently throughout the codebase, we will eliminate title matching failures that cause re-transcription of existing episodes.

The solution will rebuild the progress tracker from existing VTT files using normalized titles, ensuring all future podcast additions work correctly without over-complicating the existing codebase.

## Phase 1: Create Title Normalization Function

### Task 1.1: Implement Core Normalization Function
**Purpose**: Create a single source of truth for title normalization across all components

**Steps**:
- [x] Use context7 MCP tool to review existing title handling patterns in the codebase
- [x] Create `src/utils/title_utils.py` with `normalize_title(title: str) -> str` function
- [x] Function should:
  - Remove colons, semicolons, quotes, and other problematic punctuation
  - Convert `&` to `and` and handle HTML entities like `&amp;`
  - Replace multiple spaces with single spaces
  - Strip leading/trailing whitespace
  - Handle Unicode normalization
- [x] Add comprehensive unit tests in `tests/test_title_utils.py`

**Validation**: Unit tests pass and function handles all edge cases from existing episode titles

### Task 1.2: Test with Current Episode Data
**Purpose**: Verify normalization works with real episode titles

**Steps**:
- [x] Use context7 MCP tool to review existing episode data formats
- [x] Extract sample titles from current VTT files and RSS feed
- [x] Test normalization function against these real titles
- [x] Verify that different versions of same episode normalize to identical strings

**Validation**: All variations of existing episode titles normalize to matching strings

## Phase 2: Update Core Components

### Task 2.1: Update Progress Tracker
**Purpose**: Ensure progress tracker uses normalized titles for all operations

**Steps**:
- [x] Use context7 MCP tool to review progress tracker implementation
- [x] Modify `src/progress_tracker.py` to import and use `normalize_title()`
- [x] Update `mark_episode_transcribed()` to normalize title before storage
- [x] Update `is_episode_transcribed()` to normalize title before comparison
- [x] Update `get_transcribed_episodes()` to return normalized titles

**Validation**: Progress tracker operations work with both normalized and raw titles

### Task 2.2: Update Episode Matching Logic
**Purpose**: Ensure episode identification uses normalized titles

**Steps**:
- [x] Use context7 MCP tool to review episode matching in orchestrator
- [x] Update `src/simple_orchestrator.py` to use normalized titles in episode checks
- [x] Update any episode comparison logic to use normalized titles
- [x] Ensure YouTube URL matching also uses normalized titles

**Validation**: Orchestrator correctly identifies already-transcribed episodes

### Task 2.3: Update File Organization
**Purpose**: Ensure file naming uses normalized titles for consistency

**Steps**:
- [x] Use context7 MCP tool to review file organization logic
- [x] Update filename generation in `src/file_organizer_simple.py` to use normalized titles
- [x] Ensure filesystem-safe character conversion still works
- [x] Update filename parsing logic to normalize extracted titles

**Validation**: Generated filenames are consistent and parsing works correctly

## Phase 3: Update Discovery Tools

### Task 3.1: Update find_next_episodes.py
**Purpose**: Ensure episode discovery uses normalized title matching

**Steps**:
- [ ] Use context7 MCP tool to review current find_next_episodes implementation
- [ ] Update `find_next_episodes.py` to use normalized titles when:
  - Extracting titles from VTT filenames
  - Comparing with progress tracker data
  - Comparing with RSS feed episode titles
- [ ] Ensure both filesystem and progress tracker checks use normalization

**Validation**: Script correctly identifies already-transcribed episodes and shows accurate counts

## Phase 4: Rebuild Progress Tracker

### Task 4.1: Create Migration Script
**Purpose**: Rebuild progress tracker with normalized titles from existing VTT files

**Steps**:
- [ ] Use context7 MCP tool to review existing migration script functionality
- [ ] Update or create new migration script that:
  - Scans all existing VTT files
  - Extracts episode titles and normalizes them
  - Rebuilds progress tracker with normalized titles
  - Clears any existing "Unknown Podcast" entries
- [ ] Add dry-run mode to preview changes

**Validation**: Migration script correctly processes all existing VTT files

### Task 4.2: Execute Migration
**Purpose**: Clean up current progress tracker data

**Steps**:
- [ ] Use context7 MCP tool to review current progress tracker state
- [ ] Backup current progress tracker file
- [ ] Run migration script to rebuild with normalized titles
- [ ] Verify all existing episodes are properly tracked

**Validation**: Progress tracker contains all existing episodes with normalized titles

## Phase 5: Integration Testing

### Task 5.1: End-to-End Testing
**Purpose**: Verify complete system works with normalization

**Steps**:
- [ ] Use context7 MCP tool to review testing patterns in the codebase
- [ ] Test complete transcription workflow:
  - Run find_next_episodes.py to verify correct episode identification
  - Attempt to transcribe already-done episodes (should skip)
  - Transcribe one new episode to verify new normalization works
- [ ] Test with multiple title variations to ensure matching works

**Validation**: System correctly skips existing episodes and processes only new ones

### Task 5.2: Multi-Podcast Testing
**Purpose**: Ensure solution works for future podcast additions

**Steps**:
- [ ] Use context7 MCP tool to review multi-podcast support patterns
- [ ] Test normalization with various title formats common in different podcasts
- [ ] Verify file organization and progress tracking work for multiple podcasts
- [ ] Test edge cases like very long titles or special characters

**Validation**: System handles diverse podcast title formats correctly

## Success Criteria

1. **No Re-transcription**: Running transcription on the same feed skips all existing episodes
2. **Accurate Discovery**: find_next_episodes.py shows correct counts and identifies proper next episodes
3. **Multi-Podcast Ready**: System can handle any podcast feed without title matching issues
4. **Clean Progress Tracking**: Progress tracker contains only normalized titles with no duplicates
5. **Backward Compatibility**: All existing VTT files remain accessible and properly tracked

## Technology Requirements

- **No new technologies required** - uses existing Python standard library functions
- **No new dependencies** - leverages current codebase structure
- **No database changes** - continues using JSON file for progress tracking

This plan maintains simplicity while thoroughly addressing the root cause of title matching failures across the entire system.