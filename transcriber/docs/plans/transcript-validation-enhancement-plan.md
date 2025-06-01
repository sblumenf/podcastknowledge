# Transcript Validation and Enhancement Implementation Plan

## Executive Summary

This plan implements four critical enhancements to ensure complete, validated transcripts with all metadata preserved. The system will automatically detect incomplete transcripts, request continuations from the LLM until complete, extract YouTube URLs for future functionality, and preserve RSS descriptions in final VTT outputs. All features work together to create a robust transcription pipeline that validates completeness and preserves all available metadata.

## Technology Requirements

**Minimal new dependencies** - Most implementations use existing libraries with one addition:
- Existing Gemini API client
- Current JSON/VTT file handling
- Existing progress tracking system
- **NEW: yt-dlp** - For YouTube URL searching (pip installable, no API keys required)
  - Requires human approval before adding to requirements.txt
  - Alternative: Use only RSS extraction if yt-dlp not approved

## Phase 1: RSS Description Preservation in VTT Files

### Task 1.1: Update VTT Metadata Structure
- [x] Modify VTTMetadata class to properly handle descriptions
- Purpose: Ensure descriptions flow through to final output
- Steps:
  1. Use context7 MCP tool to review VTT documentation standards
  2. Open `src/vtt_generator.py`
  3. Locate `VTTMetadata` class (around line 29)
  4. Verify `description` field exists and is properly typed
  5. Update `__init__` method to accept description parameter
- Validation: VTTMetadata can be instantiated with description field

### Task 1.2: Update VTT Note Block Generation
- [x] Include description in human-readable NOTE section
- Purpose: Make descriptions visible in VTT files
- Steps:
  1. Use context7 MCP tool to review NOTE block format documentation
  2. In `src/vtt_generator.py`, locate `to_note_block()` method
  3. Add description section after episode title:
     ```
     if self.description:
         lines.append(f"Description: {self.description}")
     ```
  4. Ensure proper line wrapping for long descriptions
- Validation: Generated VTT files contain description in NOTE block

### Task 1.3: Update VTT JSON Metadata
- [x] Include description in JSON metadata block
- Purpose: Preserve description for programmatic access
- Steps:
  1. Use context7 MCP tool to review JSON metadata documentation
  2. In `to_note_block()` method, modify metadata dict creation
  3. Remove the filter that excludes None values for description
  4. Explicitly include description in metadata dict
- Validation: JSON block in VTT contains description field

### Task 1.4: Update Orchestrator VTT Creation
- [x] Pass description through to VTT generator
- Purpose: Connect pipeline to preserve descriptions
- Steps:
  1. Use context7 MCP tool to review orchestrator documentation
  2. Open `src/orchestrator.py`
  3. Locate VTT file creation section
  4. Ensure episode description is passed to VTTMetadata constructor
- Validation: End-to-end test shows description in final VTT

## Phase 2: YouTube URL Extraction and Storage

### Task 2.1: Add YouTube URL Field to Episode Model
- [x] Extend Episode dataclass with youtube_url field
- Purpose: Store YouTube URLs in episode metadata
- Steps:
  1. Use context7 MCP tool to review Episode model documentation
  2. Open `src/feed_parser.py`
  3. Add to Episode dataclass:
     ```python
     youtube_url: Optional[str] = None
     ```
  4. Update `to_dict()` method to include youtube_url
- Validation: Episode objects can store YouTube URLs

### Task 2.2: Implement YouTube URL Search System
- [x] Create YouTube search functionality with fallback methods
- Purpose: Find YouTube URLs even when not in RSS feeds
- Steps:
  1. Use context7 MCP tool to review search implementation patterns
  2. Create new file `src/youtube_searcher.py`
  3. Implement search class:
     ```python
     class YouTubeSearcher:
         def __init__(self, config: Config):
             self.search_enabled = config.youtube_search.enabled
             self.method = config.youtube_search.method
             self.cache = {}
         
         def search_youtube_url(self, podcast_name: str, episode_title: str, 
                               episode_number: Optional[int] = None,
                               duration_seconds: Optional[int] = None) -> Optional[str]:
             # Try RSS extraction first
             # Then yt-dlp search if enabled
             # Cache results
     ```
  4. Implement RSS extraction method (regex patterns)
  5. Implement yt-dlp search method (if approved)
  6. Add caching layer to avoid repeated searches
  7. Add fuzzy matching for result validation
- Validation: Searcher finds correct YouTube URLs for test episodes

### Task 2.3: Add YouTube Search Configuration
- [x] Add YouTube search settings to configuration
- Purpose: Make YouTube search behavior configurable
- Steps:
  1. Use context7 MCP tool to review configuration structure
  2. In `config/default.yaml`, add:
     ```yaml
     youtube_search:
       enabled: true
       method: "rss_only"  # or "yt_dlp" if approved
       cache_results: true
       fuzzy_match_threshold: 0.85
       duration_tolerance: 0.1  # 10% tolerance
       max_search_results: 5
     ```
  3. Update Config class to load youtube_search settings
  4. Add validation for configuration values
- Validation: Config correctly loads YouTube search settings

### Task 2.4: Integrate YouTube Search in Pipeline
- [x] Call YouTube search during episode processing
- Purpose: Populate youtube_url for all episodes
- Steps:
  1. Use context7 MCP tool to review orchestrator flow
  2. In `orchestrator.py`, instantiate YouTubeSearcher
  3. After episode parsing, before transcription:
     ```python
     if self.youtube_searcher.search_enabled:
         episode.youtube_url = self.youtube_searcher.search_youtube_url(
             podcast_name=podcast.title,
             episode_title=episode.title,
             episode_number=episode.episode_number,
             duration_seconds=episode.duration
         )
     ```
  4. Log search results (found/not found)
  5. Update progress tracker with YouTube URL if found
- Validation: Episodes have YouTube URLs when available

### Task 2.5: Add YouTube URL to VTT Output
- [x] Include YouTube URL in VTT metadata
- Purpose: Preserve URL for downstream processing
- Steps:
  1. Use context7 MCP tool to review VTT metadata structure
  2. Add youtube_url to VTTMetadata class
  3. Include in both NOTE block and JSON metadata
  4. Update orchestrator to pass YouTube URL to VTT
- Validation: VTT files contain YouTube URLs when available

## Phase 3: Transcript Length Validation System

### Task 3.1: Implement Duration-Based Validation
- [x] Create validation method in GeminiClient
- Purpose: Detect incomplete transcripts
- Steps:
  1. Use context7 MCP tool to review Gemini client documentation
  2. In `src/gemini_client.py`, add method:
     ```python
     def validate_transcript_completeness(self, transcript: str, duration_seconds: int) -> Tuple[bool, float]:
         # Extract last timestamp from transcript
         # Compare to episode duration
         # Return (is_complete, coverage_percentage)
     ```
  3. Parse VTT timestamps to find last timestamp
  4. Calculate coverage as last_timestamp / duration
  5. Consider complete if coverage > 0.85
- Validation: Method correctly calculates transcript coverage

### Task 3.2: Add Validation Configuration
- [x] Add validation settings to config
- Purpose: Make validation thresholds configurable
- Steps:
  1. Use context7 MCP tool to review configuration documentation
  2. In `config/default.yaml`, add:
     ```yaml
     validation:
       min_coverage_ratio: 0.85
       max_continuation_attempts: 10
     ```
  3. Update Config class to load validation settings
- Validation: Config loads validation parameters

### Task 3.3: Integrate Validation in Transcription Flow
- [x] Call validation after each transcription
- Purpose: Trigger continuation when needed
- Steps:
  1. Use context7 MCP tool to review transcription flow
  2. In `transcribe_audio()` method, after getting response
  3. Call `validate_transcript_completeness()`
  4. If incomplete, trigger continuation logic
  5. Log validation results
- Validation: Incomplete transcripts trigger continuation

## Phase 4: LLM Continuation and Stitching System

### Task 4.1: Implement Continuation Request Method
- [x] Create method to request transcript continuation
- Purpose: Get remaining transcript from LLM
- Steps:
  1. Use context7 MCP tool to review Gemini API documentation
  2. In `src/gemini_client.py`, add:
     ```python
     def request_continuation(self, 
                            audio_file: str, 
                            existing_transcript: str,
                            last_timestamp: float) -> str:
     ```
  3. Create prompt asking for continuation from timestamp
  4. Include last few lines for context
  5. Use same model settings as original request
- Validation: Method returns continuation transcript

### Task 4.2: Implement Transcript Stitching
- [x] Create method to combine transcript segments
- Purpose: Seamlessly merge continuations
- Steps:
  1. Use context7 MCP tool to review VTT format documentation
  2. Create stitching method:
     ```python
     def stitch_transcripts(self, segments: List[str], overlap_seconds: float = 2.0) -> str:
     ```
  3. Parse timestamps from each segment
  4. Remove overlapping content based on timestamps
  5. Adjust timestamps in continuation segments
  6. Merge into single VTT format
- Validation: Stitched transcripts have continuous timestamps

### Task 4.3: Implement Full Continuation Loop
- [x] Create complete retry/continuation logic
- Purpose: Automatically get complete transcripts
- Steps:
  1. Use context7 MCP tool to review retry patterns
  2. In `transcribe_audio()`, implement loop:
     ```python
     segments = [initial_transcript]
     attempts = 0
     while not is_complete and attempts < max_attempts:
         continuation = request_continuation(...)
         segments.append(continuation)
         full_transcript = stitch_transcripts(segments)
         is_complete, coverage = validate_transcript_completeness(...)
         attempts += 1
     ```
  3. Track continuation attempts in progress
  4. Update progress tracker with continuation status
- Validation: System continues until complete or max attempts

### Task 4.4: Add Continuation Tracking
- [x] Track continuation attempts and results
- Purpose: Monitor and debug continuation behavior
- Steps:
  1. Use context7 MCP tool to review progress tracking
  2. Update progress entry to include:
     - continuation_attempts
     - final_coverage_ratio
     - segment_count
  3. Log each continuation attempt
  4. Include in final manifest
- Validation: Progress tracker shows continuation details

## Phase 5: Integration Testing and Validation

### Task 5.1: Create Integration Test Suite
- [x] Test all features working together
- Purpose: Ensure features integrate properly
- Steps:
  1. Use context7 MCP tool to review testing documentation
  2. Create `tests/test_validation_features.py`
  3. Test scenarios:
     - Short episode requiring continuation
     - Episode with YouTube URL
     - Episode with long description
     - Complete transcript on first attempt
  4. Mock Gemini responses for predictable testing
- Validation: All tests pass

### Task 5.2: Update Existing Tests
- [x] Modify tests affected by changes
- Purpose: Maintain test suite integrity
- Steps:
  1. Use context7 MCP tool to review test coverage
  2. Update tests for:
     - VTT generator with descriptions
     - Feed parser with YouTube URLs
     - Gemini client with validation
  3. Ensure backward compatibility
- Validation: All existing tests pass

### Task 5.3: End-to-End Validation
- [x] Test complete pipeline with real podcast
- Purpose: Verify production readiness
- Steps:
  1. Use context7 MCP tool to review e2e testing approach
  2. Select test podcast with:
     - Known YouTube presence
     - Rich descriptions
     - Various episode lengths
  3. Run full pipeline
  4. Verify all enhancements working
  5. Check output quality
- Validation: Real podcast processes correctly

## Success Criteria

1. **Description Preservation**: 100% of RSS descriptions appear in final VTT files
2. **YouTube URL Discovery**: Successfully finds URLs for 80%+ of episodes that have YouTube versions (RSS extraction + search if enabled)
3. **Transcript Completeness**: 95%+ of transcripts cover at least 85% of episode duration
4. **Continuation Success**: System successfully completes 90%+ of incomplete transcripts
5. **No Regressions**: All existing tests continue to pass
6. **Performance**: Processing time increases by less than 20% due to validation

## Implementation Notes

- All features designed to fail gracefully
- Validation thresholds configurable
- Continuation attempts limited to prevent infinite loops
- YouTube URL extraction is optional (doesn't fail if not found)
- Description preservation maintains backward compatibility
- Each phase can be tested independently
- No new external dependencies required