# Fix Failing Tests Report

## Summary
Successfully fixed all 6 failing orchestrator integration tests. All tests now pass except for 1 skipped test (which was intentionally skipped).

## Issues Found and Fixed

### 1. **Orchestrator Workflow Tests (3 failures)**
**Problem**: Tests were mocking `gemini_client.transcribe_audio` directly, but the orchestrator actually calls `transcription_processor.transcribe_episode`. This caused "not enough values to unpack (expected 2, got 0)" errors because the transcription processor expects a tuple from the key manager.

**Solution**:
- Added proper mocking for `transcription_processor.transcribe_episode`
- Added proper mocking for `key_rotation_manager.get_next_key` to return a tuple `(key, index)`
- Mocked the transcription processor on the orchestrator instance

### 2. **Progress Tracker State Sharing**
**Problem**: All tests were sharing the same progress tracker state file (`data/.progress.json`), causing tests to see episodes from previous test runs.

**Solution**:
- Mocked the `ProgressTracker` class to use isolated instances for each test
- Created proper mock progress states for resume functionality tests

### 3. **CLI Integration Tests (3 failures)**
**Problem**: 
- Missing `'podcast-transcriber'` in sys.argv for one test
- Mock return values were incomplete (missing required fields like 'status', 'episodes')
- Asyncio.run mock wasn't configured properly for dry-run mode

**Solution**:
- Fixed sys.argv to include the program name
- Updated mock return values to include all required fields
- Properly configured asyncio.run mock to return appropriate exit codes

### 4. **Import Issues**
**Problem**: Test was trying to import `EpisodeState` but the actual class name is `EpisodeProgress`.

**Solution**:
- Fixed imports to use correct class names from `progress_tracker` module

### 5. **Missing API Keys in Mock**
**Problem**: Mock gemini client didn't have `api_keys` attribute, causing quota check to fail.

**Solution**:
- Added `api_keys` attribute to all mock gemini client instances

### 6. **Report vs Manifest File**
**Problem**: Test was checking for `manifest.json` but orchestrator creates `{podcast_name}_report.json`.

**Solution**:
- Updated test to check for the correct report file

## Test Results
```
=================== 9 passed, 1 skipped, 4 warnings in 1.64s ===================
```

All orchestrator integration tests are now passing!