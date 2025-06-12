# Deepgram Transition Implementation Plan

**Completion Date**: June 9, 2025

## Executive Summary
Complete replacement of Gemini-based podcast transcription with Deepgram API, simplifying the architecture while maintaining VTT output with speaker identification. This plan removes complex state management, implements clean Deepgram integration with mocked testing, and ensures consistent output file handling.

## Technology Requirements
**NEW TECHNOLOGY REQUIRING APPROVAL:**
- Deepgram Python SDK (`deepgram-sdk`) - Official Python client for Deepgram API
- No other new technologies introduced

## Phase 1: Environment Setup and Configuration

### Task 1.1: Update .env file with Deepgram configuration
- [x] Add Deepgram API configuration to .env file
- **Purpose**: Configure Deepgram API access and output settings
- **Steps**:
  1. Use context7 MCP tool to review current .env structure
  2. Add DEEPGRAM_API_KEY variable
  3. Add DEEPGRAM_MODEL variable (default: nova-2)
  4. Add TRANSCRIPT_OUTPUT_DIR variable for explicit output location
  5. Remove/comment out all Gemini-related API keys
  6. Add SPEAKER_MAPPING_ENABLED variable (default: true)
- **Validation**: .env file contains all Deepgram variables, Gemini keys removed

### Task 1.2: Update requirements.txt
- [x] Add Deepgram SDK and remove unnecessary dependencies
- **Purpose**: Ensure correct dependencies for Deepgram integration
- **Steps**:
  1. Use context7 MCP tool to review current requirements.txt
  2. Add `deepgram-sdk==3.0.0` (or latest stable version)
  3. Remove `google-generativeai` and related Gemini dependencies
  4. Keep essential dependencies (feedparser, pyyaml, etc.)
- **Validation**: requirements.txt updated with Deepgram SDK

## Phase 2: Core Deepgram Integration

### Task 2.1: Create deepgram_client.py
- [x] Implement core Deepgram client with mocked responses
- **Purpose**: Single responsibility client for Deepgram API calls
- **Steps**:
  1. Use context7 MCP tool to understand current gemini_client.py structure
  2. Create new file src/deepgram_client.py
  3. Implement DeepgramClient class with:
     - `__init__` method loading API key from environment
     - `transcribe_audio(audio_url)` method returning mocked response
     - Mock response structure matching Deepgram's actual format
  4. Include proper error handling for missing API key
- **Validation**: Client can be instantiated and returns mocked transcription

### Task 2.2: Create speaker_mapper.py
- [x] Implement post-processing for speaker identification
- **Purpose**: Map generic speaker labels to meaningful names
- **Steps**:
  1. Use context7 MCP tool to review speaker identification patterns
  2. Create src/speaker_mapper.py
  3. Implement SpeakerMapper class with:
     - `analyze_transcript(transcript)` to identify speakers
     - `map_speakers(transcript, mapping)` to apply names
     - Default mapping: Speaker:0 -> "Host", Speaker:1 -> "Guest 1", etc.
  4. Add configuration option for custom speaker names
- **Validation**: Can map Speaker:0, Speaker:1 to Host, Guest

### Task 2.3: Create vtt_formatter.py
- [x] Implement Deepgram response to VTT conversion
- **Purpose**: Convert Deepgram JSON to properly formatted VTT files
- **Steps**:
  1. Use context7 MCP tool to review current VTT generation logic
  2. Create src/vtt_formatter.py
  3. Implement VTTFormatter class with:
     - `format_deepgram_response(response, speaker_mapping)` method
     - Proper timestamp formatting (HH:MM:SS.mmm)
     - Speaker labels in cue text
     - VTT header and metadata
- **Validation**: Generates valid VTT from mocked Deepgram response

## Phase 3: Simplified Orchestration

### Task 3.1: Create simple_orchestrator.py
- [x] Implement simplified orchestration without state management
- **Purpose**: Clean, straightforward podcast processing pipeline
- **Steps**:
  1. Use context7 MCP tool to understand current orchestrator complexity
  2. Create src/simple_orchestrator.py
  3. Implement SimpleOrchestrator class with:
     - `process_episode(episode)` method
     - Direct flow: download → transcribe → map speakers → format VTT → save
     - No checkpoints, no state tracking, no continuation logic
  4. Add proper logging for each step
- **Validation**: Can process single episode end-to-end with mocked data

### Task 3.2: Update file_organizer.py
- [x] Ensure consistent output file handling
- **Purpose**: Fix output location inconsistencies
- **Steps**:
  1. Use context7 MCP tool to review current file_organizer.py
  2. Update to use TRANSCRIPT_OUTPUT_DIR from environment
  3. Ensure consistent path construction:
     - Base dir from env variable
     - Podcast name subdirectory
     - Episode filename with date prefix
  4. Add validation for output directory existence
- **Validation**: Files saved to correct location specified in .env

## Phase 4: CLI Update

### Task 4.1: Create simplified CLI interface
- [x] Update CLI to use new simplified orchestrator
- **Purpose**: Clean command interface for Deepgram transcription
- **Steps**:
  1. Use context7 MCP tool to review current cli.py structure
  2. Update cli.py to:
     - Remove complex state management options
     - Use SimpleOrchestrator instead of TranscriptionOrchestrator
     - Keep essential commands: transcribe, validate-feed
     - Remove: resume, retry-failed, state management commands
  3. Ensure --output-dir flag uses env variable as default
- **Validation**: CLI runs with simplified options

## Phase 5: Testing Infrastructure

### Task 5.1: Create Deepgram mock fixtures
- [x] Implement comprehensive mock responses
- **Purpose**: Enable testing without API calls
- **Steps**:
  1. Use context7 MCP tool to review test fixture patterns
  2. Create tests/fixtures/deepgram_responses.py
  3. Include mock responses for:
     - Successful transcription with multiple speakers
     - Various episode lengths
     - Edge cases (single speaker, no speech detected)
  4. Match exact Deepgram response format
- **Validation**: Mock fixtures cover common scenarios

### Task 5.2: Create integration tests
- [x] Test end-to-end flow with mocks
- **Purpose**: Ensure complete pipeline works correctly
- **Steps**:
  1. Use context7 MCP tool to review test patterns
  2. Create tests/test_deepgram_integration.py
  3. Test complete flow:
     - Feed parsing → Episode selection
     - Deepgram transcription (mocked)
     - Speaker mapping
     - VTT generation and saving
  4. Verify output file location and format
- **Validation**: All integration tests pass

## Phase 6: Cleanup

### Task 6.1: Remove Gemini-related code
- [x] Delete all Gemini-specific files and logic
- **Purpose**: Clean codebase with only Deepgram implementation
- **Steps**:
  1. Use context7 MCP tool to identify all Gemini-related files
  2. Delete:
     - src/gemini_client.py
     - src/key_rotation_manager.py
     - src/checkpoint_recovery.py
     - src/continuation_manager.py
     - src/transcript_stitcher.py
     - Complex state management files
  3. Remove Gemini imports from remaining files
  4. Delete Gemini-specific tests
- **Validation**: No Gemini references remain in codebase

### Task 6.2: Update documentation
- [x] Update README and docs for Deepgram
- **Purpose**: Accurate documentation for new implementation
- **Steps**:
  1. Use context7 MCP tool to review current documentation
  2. Update README.md with:
     - Deepgram setup instructions
     - New simplified CLI usage
     - Environment variable configuration
  3. Create docs/deepgram-setup.md with detailed config guide
  4. Update any API documentation
- **Validation**: Documentation reflects Deepgram implementation

## Success Criteria
1. ✓ Complete Gemini code removal - no references remain
2. ✓ Deepgram integration works with mocked responses
3. ✓ VTT files generated with proper speaker names (Host, Guest)
4. ✓ Output files saved to location specified in TRANSCRIPT_OUTPUT_DIR
5. ✓ Simplified architecture - no state management complexity
6. ✓ All tests pass with mock data
7. ✓ .env file updated with Deepgram configuration
8. ✓ Documentation updated for new implementation

## Risk Mitigation
- All changes tested with mocks before any real API calls
- Old code backed up in git history
- Clear rollback path if needed
- No data migration required per requirements