# VTT Processing Flow Analysis

## Current Flow

1. **VTT File Ingestion** (`transcript_ingestion.py`)
   - Scans directories for VTT files
   - Creates VTTFile objects with metadata
   - Calculates file hash and infers podcast/episode names

2. **VTT Parsing** (`vtt_parser.py`)
   - Parses VTT format and extracts:
     - Timestamps (start/end times)
     - **Speaker information from `<v Speaker>` tags**
     - Text content
   - Returns TranscriptSegment objects with speaker field

3. **VTT Segmentation** (`vtt_segmentation.py`)
   - Post-processes segments:
     - Advertisement detection
     - Sentiment analysis
     - **Tracks unique speakers in metadata**
   - Currently no speaker enhancement

4. **Preprocessing** (`preprocessor.py`)
   - Injects metadata into text:
     - Timestamps: `[TIME: 0.0-5.2s]`
     - **Speakers: `[SPEAKER: Speaker 0]`**
     - Segment IDs
     - Episode context
   - Cleans and normalizes text
   - Has configurable `speaker_format` for injection

5. **Knowledge Extraction** (`extraction.py`)
   - Extracts entities, quotes, relationships
   - **Relies heavily on speaker attribution**
   - Creates SPEAKS relationships between speakers and quotes
   - Speaker information flows through entire pipeline

6. **Episode Flow Analysis** (`episode_flow.py`)
   - Analyzes conversation flow
   - **Tracks speaker turns and contributions**
   - Identifies conversation patterns

## Key Findings

1. **Speaker information is preserved throughout the pipeline**
2. **The VTT parser already extracts speaker tags**
3. **VTT Segmentation is the ideal integration point** - it already:
   - Post-processes segments
   - Tracks unique speakers
   - Happens before preprocessing/extraction

## Integration Strategy

The best place to add speaker identification is in `VTTSegmenter.process_segments()` method, after line 84 where segments are post-processed but before metadata calculation.