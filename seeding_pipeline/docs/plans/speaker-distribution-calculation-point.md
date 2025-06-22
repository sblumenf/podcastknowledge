# Speaker Distribution Calculation Point Analysis

## Optimal Location Identified

### Current Implementation
The `segment_regrouper.py` has the perfect infrastructure for calculating speaker distribution:

1. **Method**: `_get_primary_speaker` (lines 187-211)
   - Already calculates total speaking time for each speaker
   - Currently only returns the speaker with most time
   - Has all the data needed for percentage calculation

2. **Called From**: `_create_meaningful_unit` (line 149)
   - This is where MeaningfulUnits are created
   - Perfect place to add speaker_distribution field

3. **Available Data**:
   - `speaker_times` dictionary with speaker names and durations
   - Total duration can be calculated by summing all times
   - Easy to convert to percentages

### Proposed Changes

1. **Rename Method**: `_get_primary_speaker` → `_calculate_speaker_info`
2. **Return Type**: Change from `str` to `Tuple[str, Dict[str, float]]`
   - First element: primary_speaker (for compatibility)
   - Second element: speaker_distribution (percentages)

3. **Calculation Logic**:
   ```python
   total_time = sum(speaker_times.values())
   speaker_distribution = {
       speaker: round((time / total_time * 100), 1)
       for speaker, time in speaker_times.items()
   }
   ```

4. **Integration Point**: Update `_create_meaningful_unit` to:
   - Call the renamed method
   - Unpack both primary_speaker and speaker_distribution
   - Add speaker_distribution to MeaningfulUnit creation

## Note
There's a comment on line 185 mentioning a removed `_calculate_speaker_distribution` method. We're essentially re-implementing this functionality but with proper integration into the pipeline.