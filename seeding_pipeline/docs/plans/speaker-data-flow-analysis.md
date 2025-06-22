# Speaker Data Flow Analysis

## Current State Analysis

### Data Flow Summary

1. **VTT Parser** (`src/vtt/vtt_parser.py`)
   - Extracts speaker from `<v Speaker>` tags
   - Field: `TranscriptSegment.speaker` (Optional[str])
   - Contains raw names like "Speaker 1", "Speaker 2"

2. **Speaker Identifier** (`src/extraction/speaker_identifier.py`)
   - Maps generic IDs to real names using LLM
   - Updates `segment.speaker` with identified names
   - Returns mappings and confidence scores

3. **Segment Regrouper** (`src/services/segment_regrouper.py`)
   - Creates MeaningfulUnits from segments
   - Field: `MeaningfulUnit.primary_speaker` (str)
   - Calculates primary speaker by most speaking time
   - **No speaker_distribution field exists**

4. **Graph Storage** (`src/storage/graph_storage.py`)
   - Stores `primary_speaker` as string property
   - No `speaker_distribution` field in Neo4j

5. **Post Processing** (`src/post_processing/speaker_mapper.py`)
   - Enhances speaker names after storage
   - Updates `primary_speaker` field in database

## Key Finding

The system consistently uses `primary_speaker` (single string) throughout the pipeline. The reports are looking for `speaker_distribution` which was never implemented. This is why reports show "No speakers identified" even though speakers are correctly stored.

## Field Name Consistency

- **Current**: `primary_speaker` (string) - used everywhere
- **Expected by reports**: `speaker_distribution` (dict) - doesn't exist
- **Solution needed**: Add `speaker_distribution` calculation and storage