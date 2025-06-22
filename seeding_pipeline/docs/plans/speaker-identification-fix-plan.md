# Speaker Identification Fix Implementation Plan

## Overview

This plan addresses the critical issue where speakers are correctly identified but not properly stored or reported. The system currently stores only `primary_speaker` (a single string) while reports expect `speaker_distribution` (a percentage dictionary). Additionally, the speaker cache is contaminated across episodes.

## Problem Summary

1. **Data Model Mismatch**: System stores `primary_speaker` but reports expect `speaker_distribution`
2. **Cache Contamination**: Speaker cache persists across episodes, causing all guests to appear in all episodes
3. **Missing Calculation**: No code calculates speaker distribution percentages
4. **Field Mismatch**: Reports look for wrong field name

## Solution Approach

Implement a complete fix following KISS principles:
- Calculate and store speaker distribution percentages
- Make speaker cache episode-specific
- Update all components to use consistent field names
- No backward compatibility needed (user will reprocess from scratch)

## Core Objectives (Review Before Each Task)

1. **Fix Data Model**: Ensure speaker_distribution field is consistently used throughout pipeline
2. **Isolate Episodes**: Prevent speaker cache contamination between episodes
3. **Calculate Percentages**: Implement accurate speaker time percentage calculation
4. **KISS Principle**: Keep implementation simple and straightforward
5. **No Migration**: User will reprocess from scratch, no backward compatibility needed

## Implementation Phases

### Phase 1: Analysis and Planning (30 minutes)

#### Task 1.1: Map Speaker Data Flow
**Objective Review**: Before starting, remember we need to fix the data model mismatch between primary_speaker and speaker_distribution fields.

This task involves creating a comprehensive map of how speaker data flows through the entire pipeline from VTT parsing to final storage. Start by examining the VTT parser to understand how speakers are initially identified, then trace through the speaker identification service, segment regrouper, meaningful unit creation, and finally the graph storage layer. Document every location where speaker fields are read or written, paying special attention to field name inconsistencies (primary_speaker vs speaker_distribution). Create a visual or textual flow diagram showing each component and the exact field names used at each stage.

#### Task 1.2: Identify Cache Issues
**Objective Review**: Remember that cache contamination is causing all guests to appear in all episodes - we must isolate cache per episode.

Analyze the current speaker cache implementation to understand exactly how and why it persists across episodes. Look for where the cache is initialized, where it's populated with speaker data, and critically, where it should be cleared but isn't. Examine the speaker identification service and any related components that might be holding onto speaker state between episode processing runs. Document the current cache lifecycle and identify the specific points where cache clearing should occur to prevent cross-episode contamination. Pay attention to any global or class-level variables that might be retaining state.

#### Task 1.3: Find Distribution Calculation Points
**Objective Review**: We need to calculate speaker percentages - remember to keep the calculation simple per KISS principles.

Identify the optimal location in the pipeline where speaker distribution percentages should be calculated. The segment_regrouper appears to be the natural place since it already processes segments and creates meaningful units. Examine how the current primary_speaker is determined (likely by most speaking time) and plan how to extend this to calculate percentages for all speakers. Consider the data available at each pipeline stage and ensure the chosen location has access to all necessary timing information. Plan a simple algorithm that sums speaking time per speaker and converts to percentages.

### Phase 2: Core Implementation (45 minutes)

#### Task 2.1: Fix Speaker Cache
**Objective Review**: Cache isolation is critical - each episode must have its own speaker cache to prevent contamination.

Implement episode-specific speaker caching by modifying the speaker identification service to use episode_id as part of the cache key. This ensures that each episode maintains its own isolated set of speaker mappings without interference from other episodes. The implementation should include creating a new cache structure that's keyed by episode_id, modifying all cache access methods to include the episode_id parameter, and adding explicit cache cleanup calls at the end of each episode processing. Additionally, implement safeguards to prevent accidental cache sharing by validating episode_id on every cache operation and logging warnings if cross-episode access is attempted.

#### Task 2.2: Implement Speaker Distribution Calculation
**Objective Review**: Keep the percentage calculation simple and accurate - this replaces the single primary_speaker with a distribution dictionary.

Add speaker distribution calculation logic to the segment_regrouper's `_create_meaningful_unit` method where speaker data is already being processed. The implementation should calculate the total speaking time for each speaker within the meaningful unit by iterating through all segments and summing duration per speaker. Convert these absolute times to percentages by dividing each speaker's time by the total duration and multiplying by 100, rounding to one decimal place. Ensure the percentages sum to exactly 100% by adjusting the largest percentage if necessary due to rounding. Store the result as a simple dictionary mapping speaker names to percentages, following the format: {"John Doe": 65.5, "Jane Smith": 34.5}.

#### Task 2.3: Update Data Models
**Objective Review**: Ensure consistent field naming - speaker_distribution should be used everywhere, following KISS principles.

Modify the MeaningfulUnit data model to include a speaker_distribution field of type Dict[str, float] to store the percentage dictionary. Update all code that creates MeaningfulUnit instances to populate this new field with the calculated distribution. Temporarily keep the primary_speaker field during implementation to avoid breaking existing code, but mark it as deprecated in comments. Update all downstream consumers of speaker data to read from speaker_distribution instead of primary_speaker, including storage services, report generators, and any analysis components. Ensure proper validation that speaker_distribution percentages sum to 100% and all values are non-negative.

### Phase 3: Storage and Retrieval (30 minutes)

#### Task 3.1: Update Graph Storage
**Objective Review**: Ensure speaker_distribution is properly stored in Neo4j - this fixes the core issue where data exists but isn't saved correctly.

Modify the graph storage service to properly save the speaker_distribution field when creating MeaningfulUnit nodes in Neo4j. The implementation requires updating the node creation query to include speaker_distribution as a property, ensuring the dictionary is properly serialized to JSON format for storage. Add validation to confirm the field is a valid dictionary with string keys and float values before storage. Update any existing queries that retrieve MeaningfulUnit data to include the speaker_distribution field in the return properties. Test serialization and deserialization to ensure percentages maintain their precision and the dictionary structure is preserved through the storage round-trip.

#### Task 3.2: Fix Report Scripts
**Objective Review**: Reports must use speaker_distribution field - this will finally make speaker data visible to users.

Update all speaker report scripts to read from the speaker_distribution field instead of looking for the non-existent field they currently expect. Modify the data aggregation logic to work with percentage dictionaries rather than single speaker strings, calculating weighted averages when combining data across multiple meaningful units. Implement proper display formatting that shows speaker names with their percentage contributions, sorted by speaking time percentage in descending order. Add summary statistics such as total speaking time per speaker across all episodes, average percentage per episode, and episode count per speaker. Ensure reports handle edge cases like units with no speaker data or malformed distribution dictionaries gracefully.

### Phase 4: Testing and Validation (30 minutes)

#### Task 4.1: Create Test Cases
**Objective Review**: Comprehensive testing ensures our fix works correctly - focus on cache isolation and accurate percentages per KISS principles.

Develop a comprehensive test suite that validates all aspects of the speaker identification fix. Create unit tests for the speaker distribution calculation that verify percentages sum to exactly 100%, handle edge cases like single-speaker units, and maintain precision with multiple speakers. Implement integration tests that process multiple episodes sequentially to verify cache isolation, ensuring speakers from one episode never appear in another's cache. Add validation tests for the data model changes, confirming speaker_distribution field is properly populated and stored. Include boundary tests for extreme cases like very short segments, unknown speakers, and units with many different speakers.

#### Task 4.2: Process Test Episodes
**Objective Review**: Real episode testing validates the complete fix - ensure speaker data flows correctly from parsing to reports.

Execute the complete pipeline on a carefully selected set of test episodes that include various speaker configurations: single-speaker episodes, two-person interviews, panel discussions with multiple speakers, and episodes with unknown speaker segments. Monitor the pipeline execution for any errors or warnings related to speaker processing, paying special attention to cache behavior between episodes. After processing, verify the Neo4j database contains correct speaker_distribution data for all meaningful units by running direct queries. Execute all speaker report scripts and confirm they display accurate speaker information with proper percentages and no contamination between episodes. Document any edge cases discovered during testing for future reference.

### Phase 5: Cleanup and Documentation (15 minutes)

#### Task 5.1: Remove Old Code
**Objective Review**: Clean implementation following KISS principles - remove complexity and deprecated code.

Conduct a thorough code cleanup to remove deprecated primary_speaker references where they're no longer needed, keeping only those required for temporary compatibility. Remove any migration code or compatibility layers that were added during development but aren't needed for the fresh-start approach. Clean up any commented-out code blocks, temporary debugging statements, or experimental implementations that didn't make it into the final solution. Ensure all speaker-related code uses consistent field names and follows the established pattern. Review import statements and remove any unused imports that may have accumulated during development.

#### Task 5.2: Document Changes
**Objective Review**: Clear documentation ensures future maintainability - explain what was fixed and how it works.

Create comprehensive documentation for the speaker identification changes, starting with inline code comments that explain the speaker distribution calculation algorithm and cache isolation approach. Update any existing documentation files to reflect the new speaker_distribution field format and its percentage-based structure. Document the specific format of speaker_distribution as a dictionary mapping speaker names to float percentages, including examples and edge cases. Add notes about the cache isolation implementation and why it's critical for preventing cross-episode contamination. Include troubleshooting guidelines for common speaker-related issues and how to verify correct speaker data in the database.

## Technical Details

### Speaker Distribution Format
```python
speaker_distribution = {
    "John Doe": 65.5,      # Percentage of speaking time
    "Jane Smith": 34.5     # Percentages sum to 100
}
```

### Cache Implementation
- Store cache per episode_id
- Clear after each episode completes
- Use simple dictionary structure

### Calculation Method
1. Sum total speaking time for each speaker in unit
2. Calculate percentage for each speaker
3. Round to 1 decimal place
4. Ensure sum equals 100% (adjust largest if needed)

## Success Criteria

1. Speaker reports show actual speaker names and percentages
2. Each episode has only its own speakers (no contamination)
3. Percentages accurately reflect speaking time
4. All components use consistent field names
5. Pipeline processes episodes without speaker-related errors

## Risk Mitigation

1. **Data Loss**: User will clear database and reprocess
2. **Performance**: Simple percentage calculation has minimal impact
3. **Compatibility**: No backward compatibility needed
4. **Complexity**: KISS approach with straightforward implementation

## Estimated Timeline

- Total implementation time: 2.5 hours
- Can be completed in single session
- No complex dependencies or migrations

## Next Steps

1. Get user approval for this plan
2. Execute implementation phases in order
3. Test with sample episodes
4. Deploy and reprocess all episodes