# Simplified Transcription with Continuation Logic Implementation Plan

## Executive Summary

Implement a simplified transcription approach that uses only the paid API key (first key), sends minimal prompts to Gemini for full episode transcripts, automatically detects incomplete responses, requests continuations until complete coverage, and converts the final combined output to VTT format. This eliminates key rotation complexity, quota limitations, and over-engineered prompts while ensuring complete episode transcription.

## Phase 1: Simplify API Key Usage

### Task 1.1: Disable Key Rotation for Paid Tier
- [x] Modify key rotation manager to bypass rotation when first key is paid tier
- Purpose: Eliminate complexity of switching keys mid-transcription
- Steps:
  1. Use context7 MCP tool to review key_rotation_manager.py documentation
  2. Add method `use_paid_key_only()` that forces selection of first key
  3. Add detection logic for paid vs free tier keys
  4. Update `get_available_key()` to return first key when in paid mode
  5. Add configuration flag `USE_PAID_KEY_ONLY` to environment variables
- Validation: Verify only first API key is used in transcription logs

### Task 1.2: Remove Quota Checking for Paid Key
- [x] Bypass quota limits when using paid tier key
- Purpose: Allow unlimited transcription attempts without artificial limits
- Steps:
  1. Use context7 MCP tool to review quota checking logic in gemini_client.py
  2. Add `is_paid_tier()` method to detect paid keys
  3. Modify quota checking methods to return unlimited for paid keys
  4. Update usage tracking to log but not limit paid key usage
  5. Ensure quota warnings still appear for monitoring
- Validation: Confirm no quota exceeded errors with paid key during long transcriptions

## Phase 2: Implement Simple Transcription Prompt

### Task 2.1: Replace Complex Prompt with Simple Version
- [x] Update transcription prompt to minimal effective version
- Purpose: Use proven simple prompt that works better than over-engineered version
- Steps:
  1. Use context7 MCP tool to review current _build_transcription_prompt method
  2. Replace complex prompt with: "I would like a full transcript, time stamped and diarized with clear identification of speaker changes."
  3. Add minimal episode context: podcast name, episode title, and guest info from description
  4. Remove all WebVTT formatting requirements from prompt
  5. Remove segment duration constraints and line count limits
- Validation: Verify new prompt generates natural transcript format without WebVTT structure

### Task 2.2: Update Response Processing for Raw Text
- [x] Modify response handling to expect plain text instead of WebVTT
- Purpose: Handle natural text output from simplified prompt
- Steps:
  1. Use context7 MCP tool to review current response parsing in gemini_client.py
  2. Update `_parse_transcript_response()` to handle raw text format
  3. Remove WebVTT validation from initial response
  4. Implement timestamp extraction from raw text
  5. Save raw response as intermediate .txt file for debugging
- Validation: Confirm raw transcript saves correctly as .txt file with timestamps

## Phase 3: Implement Continuation Detection Logic

### Task 3.1: Create Coverage Analysis System
- [x] Build system to detect incomplete transcriptions
- Purpose: Automatically identify when transcript doesn't cover full episode
- Steps:
  1. Use context7 MCP tool to review episode duration parsing logic
  2. Create `TranscriptAnalyzer` class with `calculate_coverage()` method
  3. Implement timestamp extraction from raw text using regex patterns
  4. Calculate coverage percentage: (last_timestamp / total_episode_duration) * 100
  5. Add support for various timestamp formats (HH:MM:SS, MM:SS, etc.)
- Validation: Test coverage calculation with known partial transcripts

### Task 3.2: Implement Continuation Request Loop
- [x] Build automatic continuation system until full episode is transcribed
- Purpose: Ensure complete episode transcription regardless of token limits
- Steps:
  1. Use context7 MCP tool to review existing continuation logic for reference
  2. Create `ContinuationManager` class with `request_continuation()` method
  3. Implement loop: while coverage < 100% and attempts < max_attempts
  4. Extract last timestamp from current transcript
  5. Send continuation prompt: "Please continue the transcript from [timestamp]. Maintain the same format with timestamps and speaker identification."
  6. Append new response to existing transcript
  7. Recalculate coverage and repeat until complete
- Validation: Test with short episode to verify continuation requests work

### Task 3.3: Implement Transcript Stitching
- [x] Seamlessly combine initial and continuation responses
- Purpose: Create single coherent transcript from multiple API responses
- Steps:
  1. Use context7 MCP tool to review existing stitching logic
  2. Create `TranscriptStitcher` class with `combine_segments()` method
  3. Remove duplicate content at segment boundaries
  4. Maintain speaker continuity across segments
  5. Handle timestamp gaps and overlaps
  6. Validate combined transcript for consistency
- Validation: Verify stitched transcript has no duplicates or missing content

## Phase 4: Raw Text to VTT Conversion

### Task 4.1: Build Text-to-VTT Converter
- [x] Create converter to transform raw transcript to WebVTT format
- Purpose: Generate final VTT output from combined raw transcript
- Steps:
  1. Use context7 MCP tool to review existing VTT generation logic
  2. Create `TextToVTTConverter` class with `convert()` method
  3. Parse timestamps and speaker changes from raw text
  4. Generate WebVTT cues with proper formatting
  5. Add speaker voice tags: `<v SpeakerName>`
  6. Maintain episode metadata in VTT header
- Validation: Verify generated VTT files play correctly in media players

### Task 4.2: Integrate Conversion into Pipeline
- [x] Update orchestrator to use new conversion workflow
- Purpose: Replace existing VTT generation with new text-first approach
- Steps:
  1. Use context7 MCP tool to review orchestrator.py workflow
  2. Modify `_process_episode_full()` to use new simplified flow
  3. Remove existing VTT generation calls
  4. Add raw transcript → VTT conversion step
  5. Update checkpoint system to handle new workflow stages
- Validation: Complete episode processes successfully from audio to final VTT

## Phase 5: Error Handling and Validation

### Task 5.1: Implement Failure Conditions
- [x] Add proper error handling for incomplete transcriptions
- Purpose: Fail episodes that cannot be completed rather than accept partial results
- Steps:
  1. Use context7 MCP tool to review existing error handling patterns
  2. Add maximum continuation attempts limit (default: 10)
  3. Fail episode if coverage < 100% after max attempts
  4. Fail episode if continuation requests consistently fail
  5. Add detailed error logging for debugging
  6. Clean up temporary files on failure
- Validation: Verify episodes fail cleanly when continuation is impossible

### Task 5.2: Add Progress Monitoring
- [x] Implement detailed progress tracking for new workflow
- Purpose: Provide visibility into continuation progress and debug issues
- Steps:
  1. Use context7 MCP tool to review existing progress tracking
  2. Add continuation attempt logging
  3. Log coverage percentage after each segment
  4. Track time spent in continuation loop
  5. Add metrics for successful vs failed continuations
- Validation: Progress logs clearly show continuation workflow status

## Phase 6: Integration and Testing

### Task 6.1: Update Configuration System
- [x] Add new configuration options for simplified workflow
- Purpose: Make new system configurable and maintainable
- Steps:
  1. Use context7 MCP tool to review config.py structure
  2. Add `USE_PAID_KEY_ONLY` environment variable
  3. Add `MAX_CONTINUATION_ATTEMPTS` configuration
  4. Add `REQUIRE_FULL_COVERAGE` boolean flag
  5. Update configuration validation
- Validation: New options work correctly via environment variables

### Task 6.2: Test with Real Episode
- [ ] Validate complete workflow with actual podcast episode
- Purpose: Ensure new system works end-to-end in real conditions
- Steps:
  1. Use context7 MCP tool to review testing procedures
  2. Select short episode (< 30 minutes) for initial test
  3. Run complete transcription with new workflow
  4. Verify coverage reaches 100%
  5. Validate final VTT quality and format
  6. Test with longer episode if short test succeeds
- Validation: Complete episode transcribed successfully with proper VTT output

## Success Criteria

1. **Complete Coverage**: Episodes achieve 100% transcription coverage
2. **Quality Output**: Final VTT files have proper timestamps and speaker identification
3. **Simplified Operation**: Only first API key used, no complex rotation logic
4. **Automatic Continuation**: System handles token limits transparently
5. **Clean Failures**: Episodes that cannot be completed fail cleanly with clear error messages
6. **Performance**: Transcription completes faster due to reduced complexity

## Technology Requirements

- **No new technologies required** - uses existing Gemini API, Python libraries, and VTT format
- **Existing dependencies**: google-generativeai, pathlib, re, json
- **Configuration**: Environment variables only (no new config files)

## Implementation Notes

- All temporary .txt files are cleaned up after VTT conversion
- Continuation logic is independent of existing checkpoint system
- New workflow is backward compatible with existing episode data
- Error handling maintains existing patterns for consistency
- Progress tracking integrates with existing batch processing display