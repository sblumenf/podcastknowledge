# Fix Themes and Sentiments Extraction Plan

## Executive Summary

This plan fixes the critical issue where themes and sentiments are not being extracted from podcast episodes. The fix has two parts: (1) Update the pipeline to properly extract themes/sentiments for future episodes, and (2) Create a script to retroactively extract themes from existing episodes in the database. This will enable users to browse and filter episodes by theme in the UI.

**Key Principles**: KISS (Keep It Simple, Stupid) - minimal changes, no over-engineering, focus on getting it working.

## Phase 1: Fix Pipeline for Future Episodes

### Purpose
Ensure all new episodes processed through the pipeline properly extract and store themes and sentiments.

### Tasks

#### Task 1.1: Lower Sentiment Confidence Threshold
**Description**: The sentiment analyzer is currently filtering out all sentiments because its confidence threshold is set too high at 60%. We need to lower this to 50% to allow more sentiments to be stored. This is a simple configuration change that will immediately allow sentiments to be captured.

**Purpose**: Allow sentiment analysis results to be stored instead of being filtered out.

**Steps**:
1. **CHECKPOINT**: Review overall plan goal - fix sentiment extraction for future episodes only
2. Open `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/src/pipeline/unified_pipeline.py`
3. Locate the sentiment analyzer initialization (around line 152)
4. Import SentimentConfig from sentiment_analyzer module
5. Create a config with min_confidence_threshold=0.5
6. Pass this config to SentimentAnalyzer initialization
7. **CHECKPOINT**: Verify change is minimal and only affects confidence threshold

**Reference**: This aligns with the overall plan goal of fixing sentiment extraction for future episodes.

**Validation**: 
- Check that SentimentAnalyzer is initialized with custom config
- Verify in next processed episode that sentiments are created (count > 0)

#### Task 1.2: Add Logging for Theme Extraction
**Description**: Add simple logging to understand what themes are being extracted by the conversation analyzer and whether they're being stored successfully. This will help diagnose if themes are being found but not stored, or not found at all. Keep logging minimal and focused on the problem.

**Purpose**: Provide visibility into theme extraction to diagnose issues.

**Steps**:
1. **CHECKPOINT**: Review plan - add minimal logging only, no new features
2. Open `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/src/pipeline/unified_pipeline.py`
3. After conversation structure analysis (around line 462), add log showing theme count
4. In theme storage loop (around line 599-607), add logs for each theme creation attempt
5. Log both successes and failures with theme names
6. **CHECKPOINT**: Ensure logging is minimal and doesn't affect performance

**Reference**: This supports the plan's debugging goal without over-engineering.

**Validation**:
- Process a test episode and check logs show theme extraction attempts
- Verify logs clearly show which themes succeeded/failed

#### Task 1.3: Add Logging for Sentiment Processing
**Description**: Add minimal logging to track sentiment analysis success/failure rates. This will show if sentiments are being analyzed but failing, or if the analysis itself is failing. We need to know the failure rate to understand the scope of the problem.

**Purpose**: Diagnose why sentiment nodes aren't being created.

**Steps**:
1. **CHECKPOINT**: Review plan - sentiment fix is for future episodes only
2. In `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/src/pipeline/unified_pipeline.py`
3. In the knowledge extraction result processing (around line 841), add counter for successful sentiment analyses
4. After all units are processed, log the success rate (X out of Y units had sentiment analyzed)
5. Log the final count of sentiments being stored (line 1189)
6. **CHECKPOINT**: Verify logging doesn't add complexity or new dependencies

**Reference**: This aligns with the plan's goal of fixing sentiment extraction visibility.

**Validation**:
- Process a test episode and verify logs show sentiment success rate
- Confirm that stored sentiment count matches successful analyses

## Phase 2: Retroactive Theme Extraction Script

### Purpose
Extract themes from all existing episodes in the database without reprocessing the entire pipeline.

### Tasks

#### Task 2.1: Create Theme Extraction Script
**Description**: Create a Python script that reads existing MeaningfulUnits from the database and extracts themes using the LLM. The script will query episodes without themes, gather their MeaningfulUnits, send them to Gemini 2.5 Pro for theme extraction, and store the results. This follows KISS principles by reusing existing storage methods. Script must support multi-podcast architecture.

**Purpose**: Add missing themes to existing episodes for UI browsing/filtering.

**Steps**:
1. **CHECKPOINT**: Review plan goal - retroactive theme extraction only, no sentiment
2. Create new file `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/scripts/extract_themes_retroactively.py`
3. Import necessary modules: graph_storage, llm_service, logging, config
4. Initialize using existing database configuration:
   - Use the existing PodcastConfigLoader from src.config.podcast_config_loader
   - This will automatically find and load the correct configuration file
   - Do NOT hardcode config file paths, database connections, ports, or podcast names
   - Script must dynamically discover all configured podcasts
   - Each podcast configuration contains its own database connection details
5. Create main class ThemeExtractor with methods:
   - load_podcast_registry(): Use PodcastConfigLoader to read all podcast configurations
   - connect_to_podcast_db(podcast_config): Create GraphStorageService using podcast's URI and database name
   - get_episodes_without_themes(graph_storage): Query episodes missing HAS_TOPIC relationships
   - get_meaningful_units_for_episode(): Get all units for an episode
   - extract_themes_from_units(): Send units to LLM for theme extraction
   - store_themes(): Use existing create_topic_for_episode method
   - process_all_podcasts(): Iterate through ALL podcasts in registry, connect to each database
   - process_single_podcast(podcast_id): Look up podcast in registry, process its database
6. Use Gemini 2.5 Pro model (from env config)
7. Add command line arguments: 
   - --episode-id (test single episode)
   - --podcast-name (filter by specific podcast)
   - --limit (batch size)
   - --dry-run (preview without changes)
   - No arguments = process ALL episodes across ALL podcast databases
8. **CHECKPOINT**: Verify script connects to correct Neo4j instance for each podcast

**Reference**: This implements the retroactive fix requirement from the overall plan.

**Validation**:
- Script runs without errors on a single episode
- Script dynamically discovers all podcasts from config (no hardcoded names/ports)
- Script processes episodes in correct database for each podcast
- Adding a new podcast to config/podcasts.yaml works without code changes
- Themes are visible in correct database after running
- Dry-run mode shows what would be processed

#### Task 2.2: Create Theme Extraction Prompt
**Description**: Design a focused prompt that sends all MeaningfulUnit texts from an episode to the LLM and asks for 3-7 main themes. The prompt should be simple and direct, asking for theme names and brief descriptions. Include episode title and description for context.

**Purpose**: Get high-quality themes that represent the episode content.

**Steps**:
1. **CHECKPOINT**: Review plan - use Gemini 2.5 Pro for theme extraction
2. In the extract_themes_from_units method, build prompt with:
   - Podcast name (from multi-podcast architecture)
   - Episode title and description
   - All MeaningfulUnit texts (truncate if too long)
   - Clear instruction to identify 3-7 main themes/topics
   - Request JSON format: {"themes": [{"theme": "Name", "description": "Brief description"}]}
3. Set temperature to 0.3 for consistent results
4. Use json_mode=True for reliable parsing
5. **CHECKPOINT**: Keep prompt simple, avoid complex instructions

**Reference**: This follows the plan's requirement to use Pro model for better context understanding.

**Validation**:
- Test prompt with one episode manually
- Verify themes are relevant and specific (not generic)
- Confirm JSON parsing works reliably

#### Task 2.3: Test Script on Single Episode
**Description**: Before running on all episodes, test the script on one episode to verify themes are extracted correctly and stored in the database. Check that the themes make sense for the episode content and are properly linked with HAS_TOPIC relationships.

**Purpose**: Validate the approach before processing all episodes.

**Steps**:
1. **CHECKPOINT**: Review plan - this is testing phase, not implementation
2. Run script with --episode-id flag on a known episode
3. Query database to verify Topic nodes were created
4. Verify Episode -[:HAS_TOPIC]-> Topic relationships exist
5. Manually review themes for quality/relevance
6. Check logs for any errors or warnings
7. Test --dry-run mode to verify it shows correct information
8. **CHECKPOINT**: If test passes, ready for full database processing

**Reference**: This validates Phase 2 implementation before full rollout.

**Validation**:
- Neo4j query shows topics linked to test episode
- Themes are relevant to episode content
- No errors in execution logs

## Phase 3: Configuration Management

### Purpose
Make confidence thresholds configurable without code changes (minimal approach).

### Tasks

#### Task 3.1: Add Sentiment Config to Environment
**Description**: Add sentiment analysis configuration to the existing .env file so thresholds can be adjusted without code changes. This is the simplest approach that follows existing patterns in the codebase. Just add two new environment variables.

**Purpose**: Allow easy adjustment of thresholds without code deployment.

**Steps**:
1. **CHECKPOINT**: Review plan - keep configuration simple, use existing patterns
2. Add to .env file:
   - SENTIMENT_MIN_CONFIDENCE=0.5
   - SENTIMENT_EMOTION_THRESHOLD=0.3
3. Update sentiment analyzer initialization to read from env
4. Use os.getenv with defaults matching current values
5. Add comment in .env explaining what these control
6. **CHECKPOINT**: Verify no new config frameworks or complexity added

**Reference**: This implements the configuration improvement from the plan.

**Validation**:
- Change values in .env and verify they're used
- Confirm defaults work if env vars are missing

## Success Criteria

1. **Future Episodes**: New episodes show >0 themes and >0 sentiments in processing logs
2. **Existing Episodes**: All episodes in database have at least 1 theme after script runs
3. **Configuration**: Sentiment thresholds can be changed via .env file
4. **No Regressions**: Existing functionality (entities, quotes, insights) continues working

## Technology Requirements

- **No new technologies** - uses existing Neo4j, Gemini API, Python libraries
- **Models**: Gemini 2.5 Flash (existing), Gemini 2.5 Pro (existing in env)

## Important Reminders for Implementation

- **Check alignment with plan goals at each step** - don't add features not in this plan
- **KISS principle** - if a solution seems complex, find a simpler way
- **Test each change** - verify the specific fix works before moving on
- **Use existing patterns** - follow the codebase's current approaches
- **Minimal changes** - fix only what's broken, don't refactor working code