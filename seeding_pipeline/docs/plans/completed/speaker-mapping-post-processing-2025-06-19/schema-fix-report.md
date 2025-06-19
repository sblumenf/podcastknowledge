# Schema Fix Report for Speaker Mapping Post-Processing

**Date**: June 19, 2025  
**Fixed By**: /04-resolver  
**Issue**: Schema mismatch between implementation assumptions and actual Neo4j data structure

## Summary

The SpeakerMapper implementation was built with assumptions about the Neo4j schema that didn't match the actual emergent structure created by the seeding pipeline. This is expected in a schemaless database where the structure emerges from how data is actually stored.

## Issues Fixed

### 1. Relationship Direction Mismatch
- **Expected**: `Episode -[:HAS_MEANINGFUL_UNIT]-> MeaningfulUnit`
- **Actual**: `MeaningfulUnit -[:PART_OF]-> Episode`
- **Fix**: Reversed all queries to match actual direction

### 2. Relationship Type Mismatch
- **Expected**: `:HAS_MEANINGFUL_UNIT`
- **Actual**: `:PART_OF`
- **Fix**: Updated all relationship types in queries

### 3. Field Name Mismatches
- **Expected**: `speakers` field in MeaningfulUnit
- **Actual**: `speaker_distribution` field (JSON with percentages)
- **Fix**: Updated all field references and JSON parsing logic

### 4. Property Name Mismatches
| Expected | Actual | Context |
|----------|--------|---------|
| `episodeId` | `id` | Episode identifier |
| `episodeUrl` | `youtube_url` | YouTube URL |
| `content` | `text` | MeaningfulUnit text content |

### 5. Query Syntax Issues
- Fixed ORDER BY clause placement in aggregation queries
- Removed redundant secondary updates for non-existent fields

## Files Modified

1. **`src/post_processing/speaker_mapper.py`**
   - Updated all Neo4j queries to match actual schema
   - Fixed field name references throughout
   - Removed redundant speaker distribution update

2. **`src/cli/speaker_report.py`**
   - Updated list command query for correct schema
   - Updated update command query for correct schema
   - Adjusted table formatting for episode IDs

## Validation

Created comprehensive tests that verify:
- ✅ Episode data retrieval works with corrected schema
- ✅ Generic speaker identification functions properly
- ✅ Pattern matching from descriptions works
- ✅ Speaker distribution JSON parsing succeeds
- ✅ Database queries execute without errors

## Root Cause

This mismatch occurred because:
1. Neo4j is schemaless - structure emerges from usage
2. The post-processor was developed based on expected patterns rather than actual data
3. Different phases of development used slightly different naming conventions

## Lessons Learned

1. Always verify actual data structure before implementing queries
2. In schemaless databases, document the emergent schema
3. Use consistent naming conventions across all pipeline phases

## Next Steps

The speaker mapping post-processor is now ready to:
1. Process existing episodes in the database
2. Identify generic speaker names
3. Map them to real names using the 5-step process
4. Update the database with corrected names

All schema issues have been resolved and the system is functional.