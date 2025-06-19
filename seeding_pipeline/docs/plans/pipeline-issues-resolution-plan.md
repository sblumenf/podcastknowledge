# Pipeline Issues Resolution Plan

## Executive Summary
This plan fixes 5 critical issues preventing the VTT knowledge pipeline from processing podcast episodes. The fixes prioritize simplicity and maintainability following KISS principles. After implementation, the pipeline will successfully process episodes end-to-end, accepting any speaker names from LLM and extracting knowledge without errors.

## Phase 1: Fix Knowledge Extraction Error (episode_metadata)

### Task 1.1: Locate and analyze the episode_metadata usage
- [ ] Task: Find all occurrences of episode_metadata in the knowledge extraction flow
- Purpose: Understand the scope of the undefined variable issue
- Steps:
  1. Use context7 MCP tool to review unified_pipeline.py documentation
  2. Grep for "episode_metadata" in src/pipeline/unified_pipeline.py
  3. Identify where episode_metadata should be passed but isn't
  4. Document all locations needing fixes
- Validation: List of all files and line numbers where episode_metadata is referenced

### Task 1.2: Add episode_metadata to class initialization
- [ ] Task: Store episode_metadata as instance variable in UnifiedKnowledgePipeline
- Purpose: Make episode metadata accessible throughout the pipeline execution
- Steps:
  1. In unified_pipeline.py, add self.episode_metadata = None to __init__
  2. In process_vtt_file method, add: self.episode_metadata = episode_metadata
  3. Update _extract_knowledge method to use self.episode_metadata
- Validation: Grep shows self.episode_metadata is used instead of undefined episode_metadata

### Task 1.3: Fix knowledge extraction method references
- [ ] Task: Update all knowledge extraction calls to use self.episode_metadata
- Purpose: Eliminate "name 'episode_metadata' is not defined" errors
- Steps:
  1. In _extract_knowledge method around line 631, change:
     - FROM: episode_metadata.get('podcast_name', 'Unknown')
     - TO: self.episode_metadata.get('podcast_name', 'Unknown')
  2. Repeat for episode_title on line 632
  3. Search for any other bare episode_metadata references
- Validation: Run grep "episode_metadata\." (with dot) - should find no results without "self."

## Phase 2: Remove Generic Speaker Name Rejection

### Task 2.1: Locate speaker validation logic
- [ ] Task: Find where generic speaker names are rejected
- Purpose: Identify the validation code that needs removal
- Steps:
  1. Use context7 MCP tool for speaker identification documentation
  2. Grep for "Generic speaker names detected" error message
  3. Grep for "CRITICAL.*speaker" in the codebase
  4. Document the validation logic location
- Validation: Found exact file and line number of rejection logic

### Task 2.2: Remove or bypass speaker name validation
- [ ] Task: Modify code to accept all speaker names from LLM
- Purpose: Allow "Guest", "Speaker 1", etc. to pass through to post-processing
- Steps:
  1. Locate the validation check (likely in speaker identification or post-processing)
  2. Comment out or remove the generic name check
  3. Add comment: "# Accept all speaker names - post-processing will enhance"
  4. Ensure differentiation between speakers is still maintained
- Validation: Process episode 2 that previously failed - should now complete speaker identification

## Phase 3: Fix Conversation Validation Errors

### Task 3.1: Add bounds checking to conversation analyzer
- [ ] Task: Validate theme unit references are within valid range
- Purpose: Prevent "references invalid unit index" errors
- Steps:
  1. Use context7 MCP tool for ConversationAnalyzer documentation
  2. Locate where themes reference unit indices
  3. Before returning ConversationStructure, add validation:
     ```python
     max_unit_index = len(units) - 1
     for theme in themes:
         theme.unit_indices = [idx for idx in theme.unit_indices if 0 <= idx <= max_unit_index]
     ```
  4. Add warning log for any out-of-bounds indices removed
- Validation: No more validation errors mentioning invalid unit indices

### Task 3.2: Add retry logic with index correction
- [ ] Task: Implement smart retry that fixes index issues
- Purpose: Automatically correct LLM mistakes rather than failing
- Steps:
  1. In conversation analysis retry logic, detect index errors
  2. If validation fails due to indices, adjust them to valid range
  3. Log the correction for debugging
- Validation: Episodes with index errors auto-correct and continue processing

## Phase 4: Simplify Checkpoint System

### Task 4.1: Remove ConversationStructure from checkpoints
- [ ] Task: Exclude non-serializable objects from checkpoint data
- Purpose: Fix "Object of type ConversationStructure is not JSON serializable"
- Steps:
  1. Use context7 MCP tool for checkpoint system documentation
  2. In checkpoint saving logic, exclude conversation_structure
  3. Only save essential data: segments, speaker_mappings, episode_metadata
  4. Add comment explaining the exclusion
- Validation: Checkpoint saves without serialization errors

### Task 4.2: Make checkpoint system optional
- [ ] Task: Add graceful fallback when checkpoint fails
- Purpose: Don't let checkpoint errors stop pipeline execution
- Steps:
  1. Wrap all checkpoint operations in try-except blocks
  2. Log checkpoint failures as warnings, not errors
  3. Continue pipeline execution regardless of checkpoint status
  4. Add environment variable DISABLE_CHECKPOINTS=true option
- Validation: Pipeline completes even if all checkpoint operations fail

## Phase 5: Fix Timeout Issues

### Task 5.1: Investigate timeout source
- [ ] Task: Identify where 2-minute timeout originates
- Purpose: Understand why episodes timeout despite 2-hour setting
- Steps:
  1. Check if Bash tool has default timeout
  2. Look for subprocess timeout settings
  3. Check for system-level timeout wrappers
  4. Document findings
- Validation: Identified source of 2-minute limit

### Task 5.2: Add explicit timeout configuration
- [ ] Task: Ensure pipeline respects configured timeout
- Purpose: Allow long episodes to complete processing
- Steps:
  1. Add PIPELINE_TIMEOUT environment variable check
  2. Pass timeout explicitly to all subprocess/async calls
  3. Add --timeout CLI argument option
  4. Log timeout value at pipeline start
- Validation: Episodes process beyond 2 minutes without timing out

### Task 5.3: Add progress indicators
- [ ] Task: Show pipeline is still active during long operations
- Purpose: Distinguish between hangs and long processing
- Steps:
  1. Add periodic "still processing unit X of Y" logs
  2. Log timestamp with each phase transition
  3. Add elapsed time to phase completion messages
- Validation: Can monitor pipeline progress in real-time

## Phase 6: Integration Testing

### Task 6.1: Test single episode end-to-end
- [ ] Task: Process one Mel Robbins episode completely
- Purpose: Verify all fixes work together
- Steps:
  1. Run: python3 main.py [first episode] --podcast "The Mel Robbins Podcast" --title "[title]"
  2. Monitor for any errors
  3. Verify knowledge extraction completes
  4. Check Neo4j for stored entities
- Validation: Episode processes without errors, knowledge stored in database

### Task 6.2: Test all four episodes
- [ ] Task: Process all Mel Robbins episodes
- Purpose: Ensure fixes work across different content
- Steps:
  1. Process each episode sequentially
  2. Document any errors or warnings
  3. Verify consistent behavior across episodes
- Validation: All 4 episodes complete processing

## Success Criteria
1. ✓ No "episode_metadata is not defined" errors
2. ✓ Episodes with generic speaker names (Guest, Speaker 1) process successfully  
3. ✓ No conversation validation errors about invalid unit indices
4. ✓ Checkpoint failures don't stop pipeline execution
5. ✓ Episodes process beyond 2 minutes without timeout
6. ✓ All 4 Mel Robbins episodes complete with knowledge extracted

## Technology Requirements
**No new technologies required** - all fixes use existing Python standard library and current dependencies.

## Simplification Notes
- Checkpoints become optional/best-effort rather than required
- Accept all speaker names without validation
- Focus on working pipeline over perfect error handling
- Prioritize logging/visibility over complex retry logic