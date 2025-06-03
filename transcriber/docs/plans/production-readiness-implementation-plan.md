# Production Readiness Implementation Plan

## Executive Summary

This plan will fix the remaining critical issues preventing the podcast transcriber from processing real data. The system will reliably process hundreds of episodes in batches, automatically handle API quotas by waiting, track failed episodes for retry, and provide clear progress monitoring. All blocking issues (circuit breaker, async handling, state conflicts) will be resolved to ensure stable operation.

## Phase 1: Fix Critical Blocking Issues (Day 1)

### Task 1.1: Fix Circuit Breaker Recovery
- [ ] Task: Implement circuit breaker auto-recovery mechanism
  - Purpose: Prevent permanent blocking of API calls after transient failures
  - Steps:
    1. Use context7 MCP tool to review retry_wrapper.py documentation
    2. Locate circuit breaker recovery logic in src/retry_wrapper.py
    3. Add periodic check to reset circuit breaker after recovery time
    4. Implement exponential backoff reset (30min -> 1hr -> 2hr)
    5. Add force reset method for manual intervention
  - Validation: Run test that triggers circuit breaker and verify auto-recovery

### Task 1.2: Fix Async/Await Flow Issues
- [ ] Task: Ensure all async calls are properly awaited
  - Purpose: Prevent coroutine serialization errors and hanging tests
  - Steps:
    1. Use context7 MCP tool to review orchestrator.py async patterns
    2. Search for all async function calls missing await: `grep -r "search_youtube_url(" src/ | grep -v await`
    3. Add await to youtube_searcher calls in orchestrator.py
    4. Review transcription_processor for unawaited async calls
    5. Fix any AsyncMock usage in tests causing serialization issues
  - Validation: Run orchestrator tests without "cannot pickle coroutine" errors

### Task 1.3: Isolate Test and Production State
- [ ] Task: Implement state file isolation
  - Purpose: Prevent test state from affecting production runs
  - Steps:
    1. Use context7 MCP tool to review state management patterns
    2. Add STATE_DIR environment variable support to all state managers
    3. Update retry_wrapper.py to use configurable state directory
    4. Update key_rotation_manager.py to use configurable state directory
    5. Create state reset utility function
    6. Add --reset-state CLI flag to clear all state files
  - Validation: Run tests and verify no state files created in production directories

## Phase 2: Implement Robust Quota Handling (Day 1-2)

### Task 2.1: Implement Quota Wait Logic
- [ ] Task: Add automatic waiting when quota exhausted
  - Purpose: Continue processing after quota resets instead of failing
  - Steps:
    1. Use context7 MCP tool to review gemini_client quota handling
    2. Modify QuotaExceededException handling to calculate wait time
    3. Add quota_wait_enabled flag to config (default: true)
    4. Implement wait logic with progress updates every 5 minutes
    5. Add max_quota_wait_hours config (default: 25 hours)
  - Validation: Simulate quota exhaustion and verify automatic waiting

### Task 2.2: Implement Smart Key Rotation for Quotas
- [ ] Task: Rotate through all available keys before waiting
  - Purpose: Maximize throughput with multiple API keys
  - Steps:
    1. Use context7 MCP tool to review key_rotation_manager patterns
    2. Add quota tracking per key in key_rotation_manager
    3. Implement get_available_key_for_quota() method
    4. Update orchestrator to try all keys before quota wait
    5. Add daily quota reset detection
  - Validation: Test with 3 keys and verify rotation on quota

## Phase 3: Progress Monitoring and Recovery (Day 2)

### Task 3.1: Implement Real-time Progress Display
- [ ] Task: Add batch progress monitoring
  - Purpose: Show clear progress during long batch processing
  - Steps:
    1. Use context7 MCP tool to review progress tracking patterns
    2. Create BatchProgressTracker class in src/utils/batch_progress.py
    3. Add progress bar using existing progress utility
    4. Show: episodes completed/total, current episode, time elapsed, ETA
    5. Update every successful episode or every 30 seconds
  - Validation: Process 10 episodes and verify progress updates

### Task 3.2: Implement Failed Episode Recovery
- [ ] Task: Add retry command for failed episodes
  - Purpose: Easy recovery of failed episodes without reprocessing all
  - Steps:
    1. Use context7 MCP tool to review CLI patterns
    2. Add --retry-failed flag to CLI
    3. Query progress tracker for failed episodes
    4. Create new batch with only failed episodes
    5. Reset failure count on retry attempt
  - Validation: Fail 3 episodes, then retry and verify only those 3 processed

### Task 3.3: Add Batch Resume Capability
- [ ] Task: Resume interrupted batch processing
  - Purpose: Continue from interruption point without reprocessing
  - Steps:
    1. Use context7 MCP tool to review checkpoint recovery patterns
    2. Extend checkpoint to track batch state
    3. Add --resume flag to CLI
    4. Load batch checkpoint and skip completed episodes
    5. Update progress display to show resumed state
  - Validation: Interrupt batch at 50%, resume and verify continues from 50%

## Phase 4: State Management Commands (Day 2-3)

### Task 4.1: Implement State Management CLI
- [ ] Task: Add state inspection and management commands
  - Purpose: Operational control over system state
  - Steps:
    1. Use context7 MCP tool to review CLI command patterns
    2. Add `podcast-transcriber state` subcommand
    3. Implement `state show` - display all state files and status
    4. Implement `state reset` - clear all state with confirmation
    5. Implement `state export/import` - backup/restore state
  - Validation: Run each command and verify expected behavior

### Task 4.2: Add Safe State Reset
- [ ] Task: Implement safe state reset with backups
  - Purpose: Prevent accidental loss of processing history
  - Steps:
    1. Use context7 MCP tool to review file handling patterns
    2. Create state backup before reset
    3. Add timestamp to backup filenames
    4. Keep last 5 state backups
    5. Add --no-backup flag for force reset
  - Validation: Reset state and verify backup created

## Phase 5: Integration Testing and Validation (Day 3)

### Task 5.1: Create Integration Test Suite
- [ ] Task: Build end-to-end test for batch processing
  - Purpose: Validate all components work together
  - Steps:
    1. Use context7 MCP tool to review integration test patterns
    2. Create test_batch_processing_integration.py
    3. Mock RSS feed with 20 episodes
    4. Test quota exhaustion and recovery
    5. Test failure and retry scenarios
    6. Test progress monitoring output
  - Validation: All integration tests pass

### Task 5.2: Fix Remaining Test Issues
- [ ] Task: Resolve hanging tests and timeout issues
  - Purpose: Clean test suite for confidence
  - Steps:
    1. Use context7 MCP tool to review test timeout patterns
    2. Add pytest-timeout to requirements-dev.txt
    3. Set 30-second timeout on integration tests
    4. Fix async event loop issues in E2E tests
    5. Ensure all mocks properly close connections
  - Validation: Full test suite runs without hanging

### Task 5.3: Performance Testing
- [ ] Task: Validate performance with large batches
  - Purpose: Ensure system handles hundreds of episodes
  - Steps:
    1. Use context7 MCP tool to review performance patterns
    2. Create performance test with 100 mock episodes
    3. Measure memory usage during processing
    4. Verify no memory leaks in long runs
    5. Document processing rate (episodes/hour)
  - Validation: Process 100 episodes without memory issues

## Phase 6: Operational Readiness (Day 3-4)

### Task 6.1: Create Production Configuration
- [ ] Task: Set up production-ready configuration
  - Purpose: Optimal settings for real podcast processing
  - Steps:
    1. Use context7 MCP tool to review configuration patterns
    2. Create config/production.yaml
    3. Set appropriate rate limits and timeouts
    4. Configure retry attempts and backoff
    5. Set quota wait parameters
  - Validation: Load production config and verify settings

### Task 6.2: Add Operational Commands
- [ ] Task: Implement operational utilities
  - Purpose: Easy operation and troubleshooting
  - Steps:
    1. Use context7 MCP tool to review CLI utility patterns
    2. Add `podcast-transcriber validate-feed <url>` command
    3. Add `podcast-transcriber test-api` command
    4. Add `podcast-transcriber show-quota` command
    5. Add health check endpoint for monitoring
  - Validation: Run each command successfully

### Task 6.3: Create Operations Guide
- [ ] Task: Document operational procedures
  - Purpose: Smooth operation of the system
  - Steps:
    1. Use context7 MCP tool to review documentation patterns
    2. Create docs/operations-guide.md
    3. Document common commands and workflows
    4. Add troubleshooting section
    5. Include state recovery procedures
  - Validation: Follow guide to process test batch

## Success Criteria

1. **Stability**: Process 100 episodes without crashes or hangs
2. **Quota Handling**: Automatically wait and resume when quota exhausted
3. **Recovery**: Successfully retry all failed episodes
4. **Progress**: Clear, real-time progress monitoring during batch processing
5. **State Management**: Clean state reset and isolation between runs
6. **Testing**: All tests pass without hanging (excluding known orchestrator issues)
7. **Performance**: Process at least 10 episodes per hour with single API key

## Technology Requirements

All tasks use existing technologies. No new frameworks, databases, or models are required.

## Validation Checklist

- [ ] Circuit breaker recovers automatically
- [ ] No async/coroutine serialization errors
- [ ] Test and production state properly isolated
- [ ] Quota exhaustion triggers wait, not failure
- [ ] Progress bar shows accurate batch status
- [ ] Failed episodes can be retried
- [ ] State can be reset safely
- [ ] 100-episode batch processes successfully
- [ ] All commands documented and working