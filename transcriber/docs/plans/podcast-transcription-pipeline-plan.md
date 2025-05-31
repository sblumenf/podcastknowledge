# Podcast Transcription Pipeline Implementation Plan

## Implementation Guidelines

**IMPORTANT**: Before starting any task implementation:
1. Use the Context7 MCP tool to review relevant documentation for the libraries and patterns being used
2. Check the specific Context7 Documentation section listed for each task
3. Ensure understanding of best practices before writing code

## Executive Summary

Build a standalone CLI application in the `/transcriber` folder that processes podcast RSS feeds to generate high-quality VTT transcripts with speaker identification. The tool will use Gemini 2.5 Pro Experimental for transcription and contextual speaker recognition, processing episodes sequentially with robust error handling and progress tracking. Due to free tier limitations (25 requests/day), the system will process a maximum of 12 episodes daily.

## Technology Requirements

### Approved Technologies
- Python 3.9+
- Standard library modules (argparse, json, pathlib, etc.)

### New Technologies Requiring Approval
- **feedparser** - RSS feed parsing library
- **google-generativeai** - Official Google Gemini API client
- **python-dotenv** - Environment variable management
- **tenacity** - Retry logic with exponential backoff

## Phase 1: Project Setup and Structure

### Task 1.1: Initialize Project Structure
- [x] Create transcriber directory structure
  - Purpose: Establish clean, organized codebase separate from seeding pipeline
  - Steps:
    1. Create `/transcriber/src` for source code
    2. Create `/transcriber/tests` for unit tests
    3. Create `/transcriber/data` for VTT output
    4. Create `/transcriber/logs` for error logs
    5. Create `/transcriber/config` for configuration files
  - Validation: All directories exist with proper .gitkeep files

### Task 1.2: Setup Python Environment
- [x] Create project configuration files
  - Purpose: Define dependencies and project metadata
  - Steps:
    1. Create `requirements.txt` with approved dependencies
    2. Create `setup.py` for installable package
    3. Create `.env.example` with multiple API keys template (GEMINI_API_KEY_1, GEMINI_API_KEY_2)
    4. Create `README.md` with setup instructions
  - Validation: Can run `pip install -e .` successfully

### Task 1.3: Configure Logging System
- [x] Implement structured logging
  - Purpose: Track processing progress and debug issues
  - Steps:
    1. Create `src/utils/logging.py` with console and file handlers
    2. Configure log rotation (max 10MB per file, keep 5 files)
    3. Define log levels: INFO for progress, ERROR for failures
    4. Create log formatter with timestamp, level, and message
  - Validation: Test log output to both console and file

## Phase 2: Core Components Implementation

### Task 2.1: RSS Feed Parser Module
- [x] Create RSS feed processing functionality
  - Purpose: Extract episode metadata and audio URLs from feeds
  - Context7 Documentation: Review feedparser library documentation before implementation
  - Steps:
    1. Create `src/feed_parser.py` module
    2. Implement `parse_feed(rss_url)` function
    3. Extract: title, description, audio URL, publication date, duration
    4. Handle various RSS formats (iTunes, standard)
    5. Create `Episode` dataclass for structured data
  - Validation: Successfully parse 3 different podcast RSS feeds

### Task 2.2: Progress Tracker Module
- [x] Implement episode processing state management
  - Purpose: Track which episodes are completed/failed/pending
  - Context7 Documentation: Review JSON file handling and atomic writes best practices
  - Steps:
    1. Create `src/progress_tracker.py` module
    2. Design JSON state file format in `data/.progress.json`
    3. Implement methods: mark_completed(), mark_failed(), get_pending()
    4. Add episode metadata to state (URL, title, attempt count)
    5. Implement atomic file writes to prevent corruption
  - Validation: State persists across program restarts

### Task 2.3: Gemini API Client with Rate Limiting
- [x] Create Gemini 2.5 Pro Experimental integration with strict rate limits
  - Purpose: Interface with Google's Gemini API within free tier constraints
  - Context7 Documentation: Review google-generativeai library documentation for Gemini 2.5 Pro usage
  - Steps:
    1. Create `src/gemini_client.py` module
    2. Implement multi-key authentication from environment (GEMINI_API_KEY_1, GEMINI_API_KEY_2)
    3. Create `transcribe_audio(audio_url)` method with token estimation
    4. Create `identify_speakers(transcript, metadata)` method
    5. Add per-key daily request counter (max 25 requests/day per key)
    6. Implement rate limiting: 5 RPM, 250K TPM, 1M TPD per key
    7. Add request/response logging with token usage tracking per key
  - Validation: Enforce limits per key and switch keys when quota reached

### Task 2.4: Multi-Key Rotation Manager
- [x] Implement round-robin API key rotation
  - Purpose: Distribute load evenly across API keys to avoid hitting limits
  - Context7 Documentation: Review rate limiting patterns and key rotation strategies
  - Steps:
    1. Create `src/key_rotation_manager.py` module
    2. Implement round-robin key selection:
       - Alternate keys for each episode (key1 → key2 → key1 → key2)
       - Both API calls for an episode use the same key
       - Track which key should be used next
    3. Maintain usage statistics per key (for monitoring only)
    4. Handle key failures gracefully:
       - If one key fails, try the other key
       - Mark failed keys as temporarily unavailable
    5. Support 2+ API keys with configurable rotation
    6. Display current key in use during processing
  - Validation: Keys alternate predictably between episodes

## Phase 3: Transcription Pipeline

### Task 3.1: Audio Transcription Processor
- [x] Implement core transcription logic
  - Purpose: Convert audio to diarized text with timestamps
  - Context7 Documentation: Review Gemini audio transcription capabilities and VTT format specifications
  - Steps:
    1. Create `src/transcription_processor.py` module
    2. Build prompt template for VTT-formatted output
    3. Request speaker diarization (SPEAKER_1, SPEAKER_2, etc.)
    4. Parse Gemini response into structured format
    5. Validate timestamp formatting (HH:MM:SS.mmm)
  - Validation: Produce valid VTT syntax from test audio

### Task 3.2: Speaker Identification Processor
- [x] Implement contextual speaker recognition
  - Purpose: Replace generic labels with actual names/roles
  - Context7 Documentation: Review prompt engineering best practices for speaker identification
  - Steps:
    1. Create `src/speaker_identifier.py` module
    2. Build analysis prompt with transcript + metadata
    3. Extract identification cues (introductions, references)
    4. Map SPEAKER_N to identified names/roles
    5. Apply fallback rules (HOST, GUEST_1, etc.)
  - Validation: Correctly identify speakers in test transcripts

### Task 3.3: VTT Generator
- [x] Create VTT file generation with metadata
  - Purpose: Output properly formatted WebVTT files
  - Context7 Documentation: Review WebVTT specification and formatting requirements
  - Steps:
    1. Create `src/vtt_generator.py` module
    2. Implement VTT header with NOTE metadata blocks
    3. Format cue timings and speaker voice tags
    4. Embed episode metadata as JSON in NOTE block
    5. Ensure proper escape sequences and encoding
  - Validation: Generated VTT files play in standard players

## Phase 4: Error Handling and Resilience

### Task 4.1: Retry Logic Implementation
- [x] Add exponential backoff for API failures within quota limits
  - Purpose: Handle transient errors without exceeding daily quota
  - Context7 Documentation: Review tenacity library usage and retry patterns
  - Steps:
    1. Integrate tenacity library in API calls
    2. Configure retry: 2 attempts max (to preserve daily quota)
    3. Log each retry attempt with reason
    4. Implement circuit breaker for repeated failures
    5. Add specific handling for quota exceeded errors
    6. Skip episode if retries would exceed daily limit
  - Validation: System recovers from failures without exceeding 25 RPD

### Task 4.2: Error Recovery System
- [ ] Implement checkpoint and resume functionality
  - Purpose: Continue processing after interruptions
  - Context7 Documentation: Review checkpoint recovery patterns and state management
  - Steps:
    1. Save progress after each episode completion
    2. Detect partial transcriptions on startup
    3. Implement cleanup for incomplete files
    4. Add --resume flag to CLI
    5. Log recovery actions for audit trail
  - Validation: Can interrupt and resume processing

## Phase 5: CLI Interface

### Task 5.1: Command Line Interface
- [ ] Create user-friendly CLI tool
  - Purpose: Provide simple interface for transcription tasks
  - Context7 Documentation: Review argparse best practices and CLI design patterns
  - Steps:
    1. Create `src/cli.py` using argparse
    2. Add command: `transcribe --feed-url <RSS_URL>`
    3. Add options: --output-dir, --max-episodes (max 12), --resume
    4. Implement progress bar for visual feedback
    5. Add --dry-run mode for testing
  - Validation: All CLI commands work as documented

### Task 5.2: Configuration Management
- [ ] Implement flexible configuration system
  - Purpose: Allow customization without code changes
  - Context7 Documentation: Review YAML configuration patterns and python-dotenv usage
  - Steps:
    1. Create `config/default.yaml` with settings
    2. Support environment variable overrides
    3. Add settings: API timeout, retry limits (max 2), output format, daily quota (12 episodes)
    4. Validate configuration on startup
    5. Document all configuration options
  - Validation: Can override settings via env vars

## Phase 6: Output Organization

### Task 6.1: File Naming Convention
- [ ] Implement consistent output structure
  - Purpose: Organize transcripts for easy retrieval
  - Context7 Documentation: Review file naming best practices and path sanitization
  - Steps:
    1. Create naming pattern: `{podcast_name}/{YYYY-MM-DD}_{episode_title}.vtt`
    2. Sanitize filenames (remove special characters)
    3. Handle duplicate episode titles
    4. Create podcast directories automatically
    5. Add index file with episode manifest
  - Validation: No filename conflicts across feeds

### Task 6.2: Metadata Index
- [ ] Create searchable episode index
  - Purpose: Enable quick lookup of processed episodes
  - Context7 Documentation: Review JSON indexing patterns and search optimization
  - Steps:
    1. Generate `data/index.json` with all episodes
    2. Include: file path, speakers, date, duration
    3. Update index after each transcription
    4. Add CLI command to query index
    5. Support export to CSV format
  - Validation: Can search episodes by speaker or date

## Phase 7: Testing and Validation

### Task 7.1: Unit Test Suite
- [ ] Create comprehensive test coverage
  - Purpose: Ensure reliability of core components
  - Context7 Documentation: Review Python unittest/pytest best practices and mocking strategies
  - Steps:
    1. Write tests for each module
    2. Mock external API calls
    3. Test error handling paths
    4. Validate VTT output format
    5. Achieve 80% code coverage
  - Validation: All tests pass in CI environment

### Task 7.2: Integration Tests
- [ ] Test end-to-end pipeline
  - Purpose: Verify complete workflow functions correctly
  - Context7 Documentation: Review integration testing patterns and test data management
  - Steps:
    1. Create test RSS feed with known content
    2. Test full transcription pipeline
    3. Verify speaker identification accuracy
    4. Test interrupt and resume scenarios
    5. Validate output file structure
  - Validation: Can process complete podcast feed

## Success Criteria

1. **Functional Requirements**
   - Successfully transcribe episodes from any standard RSS feed
   - Generate valid VTT files with accurate timestamps
   - Identify speakers by name/role in >80% of cases
   - Handle episodes up to 60 minutes (recommended for free tier)

2. **Performance Requirements**
   - Process episodes sequentially without memory leaks
   - Recover from API failures without data loss
   - Track progress persistently across runs
   - Complete average 1-hour episode in <5 minutes
   - Process more episodes by rotating between API keys

3. **Output Quality**
   - VTT files compatible with standard players
   - Speaker names/roles clearly identified
   - Metadata preserved for knowledge graph integration
   - Consistent file organization and naming

4. **Operational Requirements**
   - Simple CLI interface requiring only RSS URL
   - Clear error messages and logging
   - Resume capability after interruptions
   - No manual intervention required for full feed processing

## Risk Mitigation

1. **API Rate Limits**: Distribute load across keys to stay under limits
2. **Load Distribution**: Rotate keys per episode to avoid concentrated usage
3. **Large Episodes**: Recommend 60-minute max length for reliable processing
4. **Failed Episodes**: Queue system to retry failed episodes next day
5. **Speaker Ambiguity**: Fallback to role-based labels when uncertain
6. **Feed Variations**: Build robust parser handling multiple RSS formats

## Free Tier Constraints Summary

- **Gemini 2.5 Pro Experimental Limits**:
  - 25 requests per day (RPD)
  - 5 requests per minute (RPM)
  - 250,000 tokens per minute (TPM)
  - 1,000,000 tokens per day (TPD)

- **Practical Implications**:
  - Process more episodes by alternating keys (reduces per-key usage)
  - Sequential processing only (no parallelization)
  - Episodes up to 60 minutes recommended
  - Keys rotate per episode to distribute load
  - Less likely to hit rate limits with rotation
  - Graceful fallback if one key encounters issues
