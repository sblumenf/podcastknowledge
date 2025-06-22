# Speaker Distribution Implementation Summary

## Overview

This document summarizes the implementation of speaker distribution functionality to fix the issue where speakers were correctly identified but not properly reported.

## Problem Fixed

1. **Data Model Mismatch**: System was storing only `primary_speaker` but reports expected `speaker_distribution`
2. **Cache Contamination**: Speaker cache persisted across episodes, causing all guests to appear in all episodes
3. **Missing Calculation**: No code calculated speaker distribution percentages

## Solution Implemented

### 1. Speaker Cache Disabled

**File**: `src/extraction/speaker_identifier.py`

- Disabled speaker cache lookup (lines 111-121)
- Disabled speaker cache storage (lines 178-186)
- Each episode now identifies speakers independently
- Removed contaminated cache file

**Rationale**: The cache was designed to share speakers across episodes of the same podcast, but this caused guest contamination where all guests appeared in every episode.

### 2. Speaker Distribution Calculation

**File**: `src/services/segment_regrouper.py`

- Renamed `_get_primary_speaker` to `_calculate_speaker_info` (line 187)
- Now returns both primary speaker and distribution percentages
- Calculates percentage of speaking time for each speaker
- Ensures percentages sum to exactly 100% with rounding adjustment

**Example Output**:
```python
speaker_distribution = {
    "Mel Robbins": 65.5,
    "Guest Name": 34.5
}
```

### 3. Data Model Updates

**File**: `src/services/segment_regrouper.py`

- Added `speaker_distribution: Dict[str, float]` field to MeaningfulUnit (line 26)
- Kept `primary_speaker` for compatibility (marked as deprecated)
- Updated `_create_meaningful_unit` to populate both fields

### 4. Storage Updates

**Files**: 
- `src/pipeline/unified_pipeline.py` (line 610)
- `src/storage/graph_storage.py` (lines 815-817, 833, 844)

- Added speaker_distribution to unit_data passed to storage
- Convert dictionary to JSON string for Neo4j storage
- Added field to CREATE and MATCH SET clauses

### 5. Report Scripts

**Files**: `scripts/speaker_table_report.py`, `scripts/speaker_summary_report.py`

- Reports already updated to look for `speaker_distribution` field
- Parse JSON string back to dictionary for analysis
- Display speaker names with percentages

## Technical Details

### Speaker Distribution Format
- Dictionary mapping speaker names to percentages
- Percentages are floats rounded to 1 decimal place
- Sum of all percentages equals exactly 100.0
- Stored as JSON string in Neo4j

### Cache Behavior
- No longer caches speakers between episodes
- Each episode gets fresh speaker identification
- Prevents cross-episode contamination

### Calculation Method
1. Sum total speaking time for each speaker in unit
2. Calculate percentage: (speaker_time / total_time * 100)
3. Round to 1 decimal place
4. Adjust largest percentage if needed to ensure sum = 100

## Testing

Created comprehensive test suite in `tests/test_speaker_distribution.py`:
- Tests single, two, and multiple speaker distributions
- Verifies percentage calculations and rounding
- Tests empty segments and unknown speakers
- Confirms cache is disabled

## Usage

After reprocessing episodes with the updated pipeline:
- Run `scripts/speaker_table_report.py` to see speakers by episode
- Run `scripts/speaker_summary_report.py` for detailed speaker statistics
- Speaker data will show actual names and percentages

## Migration Notes

- No backward compatibility needed (user will reprocess from scratch)
- Clear database before reprocessing to ensure clean data
- Speaker cache directory can be deleted entirely

## Future Considerations

1. Could re-enable episode-specific caching if needed for performance
2. Consider adding speaker role detection (host, guest, etc.)
3. Could enhance with voice fingerprinting for better accuracy