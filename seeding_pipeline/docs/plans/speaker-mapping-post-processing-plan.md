# Speaker Mapping Post-Processing Implementation Plan

## Executive Summary
This plan implements an automated post-processing system that identifies and updates generic speaker names in the Neo4j database after the main seeding pipeline completes. The system uses a 3-step approach (pattern matching → YouTube API → LLM) to map generic speaker labels like "Guest Expert (Psychiatrist)" to real names like "Dr. Judith Joseph". It also provides CLI commands for viewing speaker data and manually updating speaker names when needed.

## Phase 1: Core Infrastructure Setup

### Task 1.1: Create Speaker Mapping Module Structure
- [x] Create new module `src/post_processing/speaker_mapper.py`
  - Purpose: Main module for speaker identification logic
  - Steps:
    1. Create directory `src/post_processing/` if not exists
    2. Create `__init__.py` file
    3. Create `speaker_mapper.py` with basic class structure
    4. Add logging setup using existing logger pattern
  - Validation: Module imports without errors

### Task 1.2: Create Speaker Report CLI Command
- [x] Create `src/cli/speaker_report.py`
  - Purpose: CLI interface for viewing and updating speakers
  - Steps:
    1. Create basic Click command structure
    2. Add subcommands: `list` and `update`
    3. Connect to Neo4j using existing database configuration
    4. Use context7 MCP tool to check Click documentation patterns
  - Validation: CLI commands appear in help menu

### Task 1.3: Integrate Post-Processing into Pipeline
- [x] Modify `src/pipeline/unified_pipeline.py`
  - Purpose: Automatically run speaker mapping after pipeline completion
  - Steps:
    1. Import SpeakerMapper at top of file
    2. Add new phase after KNOWLEDGE_EXTRACTION: POST_PROCESS_SPEAKERS
    3. Create method `_post_process_speakers()` that calls mapper
    4. Add to phase execution list
    5. Make it optional via config flag `enable_speaker_mapping`
  - Validation: New phase appears in pipeline logs

## Phase 2: Pattern Matching Implementation

### Task 2.1: Episode Description Analysis
- [ ] Implement `_match_from_episode_description()` method
  - Purpose: Extract guest names from episode descriptions
  - Steps:
    1. Query episode node for description field
    2. Use regex patterns to find guest names:
       - "with [Name]"
       - "featuring [Name]"
       - "guest [Name]"
    3. Match against generic speaker labels in MeaningfulUnits
    4. Return mapping dictionary
  - Validation: Test with known episodes containing guest names

### Task 2.2: Transcript Introduction Pattern Matching
- [ ] Implement `_match_from_introductions()` method
  - Purpose: Find speaker introductions in first segments
  - Steps:
    1. Query first 10 MeaningfulUnits ordered by segment index
    2. Search for patterns:
       - "I'm [Name]"
       - "My name is [Name]"
       - "Welcome [Name]"
       - "Thanks for having me, [Name]"
    3. Map speaker order to introduction order
    4. Use context7 MCP tool to check regex best practices
  - Validation: Correctly identifies speakers in test transcripts

### Task 2.3: Closing Credits Pattern Matching
- [ ] Implement `_match_from_closing_credits()` method
  - Purpose: Extract names from episode endings
  - Steps:
    1. Query last 5 MeaningfulUnits
    2. Search for credit patterns:
       - "Special thanks to [Name]"
       - "Our guest [Name]"
       - "Produced by [Name]"
    3. Map to generic speakers by role
  - Validation: Finds credits in episodes that have them

## Phase 3: YouTube API Integration

### Task 3.1: YouTube API Client Integration
- [ ] Create `src/services/youtube_description_fetcher.py`
  - Purpose: Adapter to reuse existing YouTube API client from transcriber
  - Steps:
    1. Import YouTubeAPIClient from transcriber module
    2. Create adapter class that uses existing client
    3. Implement `get_video_description(video_id)` method using client's video list API
    4. Leverage existing rate limiting and quota management
    5. Add caching layer for video descriptions
  - Validation: Successfully retrieves video descriptions using existing infrastructure

### Task 3.2: YouTube Description Parser
- [ ] Implement `_match_from_youtube()` method
  - Purpose: Extract speaker names from YouTube descriptions
  - Steps:
    1. Extract video ID from YouTube URL in episode
    2. Call YouTube API for description
    3. Parse description for guest information
    4. Look for structured guest lists, timestamps with names
    5. Match against generic speakers
  - Validation: Identifies speakers from YouTube metadata

## Phase 4: LLM-Based Identification

### Task 4.1: LLM Prompt Engineering
- [ ] Create `_generate_speaker_prompt()` method
  - Purpose: Build effective prompts for speaker identification
  - Steps:
    1. Include episode title and description
    2. Add first 10 segments of unidentified speaker
    3. Include any context clues (credentials, affiliations)
    4. Use existing LLM service from pipeline
    5. Use context7 MCP tool to check prompt engineering best practices
  - Validation: Prompts are clear and focused

### Task 4.2: LLM Integration
- [ ] Implement `_match_from_llm()` method
  - Purpose: Last resort identification using AI
  - Steps:
    1. Only call if previous methods failed
    2. Use existing Gemini Flash model for speed
    3. Parse LLM response for speaker names
    4. Validate response format
    5. Add confidence threshold check
  - Validation: Correctly identifies speakers in test cases

## Phase 5: Database Update Logic

### Task 5.1: Speaker Update Implementation
- [ ] Create `_update_speakers_in_database()` method
  - Purpose: Apply identified mappings to Neo4j
  - Steps:
    1. Begin transaction
    2. Query all MeaningfulUnits for episode with generic speaker
    3. Update speaker field and speaker_distribution JSON
    4. Log all changes made
    5. Commit transaction
  - Validation: Database reflects updated speaker names

### Task 5.2: Audit Trail
- [ ] Implement `_log_speaker_changes()` method
  - Purpose: Track all automated and manual updates
  - Steps:
    1. Create log entry with timestamp
    2. Record: episode, old name, new name, method used
    3. Store in dedicated log file
    4. Add to episode metadata in Neo4j
  - Validation: Can trace all speaker updates

## Phase 6: CLI Report and Manual Update

### Task 6.1: Speaker List Command
- [ ] Implement `speaker_report list` command
  - Purpose: View all speakers across episodes
  - Steps:
    1. Query Neo4j for all episodes and speakers
    2. Format as readable table (use tabulate library)
    3. Show: Podcast, Episode #, Title, YouTube URL, Speakers
    4. Export option to CSV for pivot tables
    5. Use context7 MCP tool to check tabulate documentation
  - Validation: Displays comprehensive speaker information

### Task 6.2: Manual Update Command
- [ ] Implement `speaker_report update` command
  - Purpose: Allow manual speaker name corrections
  - Steps:
    1. Accept parameters: episode_id, old_name, new_name
    2. Validate episode exists
    3. Show preview of changes
    4. Apply updates to all MeaningfulUnits
    5. Log manual update with user timestamp
  - Validation: Successfully updates speaker names

## Phase 7: Testing and Validation

### Task 7.1: Unit Tests
- [ ] Create `tests/test_speaker_mapper.py`
  - Purpose: Ensure each matching method works correctly
  - Steps:
    1. Test pattern matching with known patterns
    2. Mock YouTube API responses
    3. Mock LLM responses
    4. Test database update logic
    5. Use existing test patterns from project
  - Validation: All tests pass

### Task 7.2: Integration Testing
- [ ] Test end-to-end speaker mapping
  - Purpose: Verify full system works with pipeline
  - Steps:
    1. Process test VTT file with generic speakers
    2. Verify post-processing runs automatically
    3. Check speakers are correctly identified
    4. Test manual override functionality
  - Validation: Complete flow works as expected

## Success Criteria
1. Post-processing runs automatically after pipeline without breaking existing functionality
2. At least 80% of generic speakers are successfully identified
3. CLI commands provide clear, readable speaker information
4. Manual updates work reliably and are properly logged
5. No impact on pipeline performance (< 5 seconds per episode)
6. All changes are traceable through audit logs

## Technology Requirements
- **Existing Technologies**: Neo4j, Python, Click, Gemini API, YouTube Data API v3
- **No New Technologies Required**: YouTube API is already integrated in the transcriber module
  - Can reuse existing `YouTubeAPIClient` from `transcriber/src/youtube_api_client.py`
  - API key management already in place

## Implementation Notes
- Keep all logic simple and focused (KISS principle)
- Pre-filter already-identified speakers to avoid redundant processing  
- Process only episodes with generic speakers
- Updates are scoped to single episodes only
- YouTube API and LLM are fallbacks - most cases should resolve with pattern matching
- Total processing time per episode should be under 2 seconds in typical cases