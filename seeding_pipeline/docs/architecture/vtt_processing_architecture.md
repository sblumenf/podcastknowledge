# VTT Processing Architecture

## Overview
This document defines the architecture for the VTT-based knowledge seeding pipeline, replacing the RSS/audio processing flow with direct transcript file processing.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Input Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  VTT Files Directory                                            │
│  ├── podcast1/                                                  │
│  │   ├── episode1.vtt                                          │
│  │   ├── episode2.vtt                                          │
│  │   └── metadata.json (optional)                              │
│  └── podcast2/                                                  │
│      └── *.vtt                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     VTT Ingestion Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Folder Scanner  │───▶│  VTT Validator   │                  │
│  └─────────────────┘    └──────────────────┘                  │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Batch Manager   │    │   VTT Parser     │                  │
│  └─────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │Segment Processor│───▶│Knowledge Extractor│                  │
│  └─────────────────┘    └──────────────────┘                  │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │Entity Resolution│    │ Quote Extraction │                  │
│  └─────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Storage Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Graph Builder   │───▶│  Neo4j Storage   │                  │
│  └─────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Specifications

### 1. VTT Ingestion Components

#### VTTFolderScanner
```python
class VTTFolderScanner:
    """Scans directories for VTT files and metadata."""
    
    def scan_directory(self, path: Path, recursive: bool = True) -> List[VTTFile]:
        """Scan directory for VTT files."""
        
    def group_by_podcast(self, files: List[VTTFile]) -> Dict[str, List[VTTFile]]:
        """Group VTT files by podcast/show."""
        
    def load_metadata(self, directory: Path) -> Optional[PodcastMetadata]:
        """Load optional metadata.json if present."""
```

#### VTTValidator
```python
class VTTValidator:
    """Validates VTT file format and content."""
    
    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate VTT file structure."""
        
    def validate_timestamps(self, segments: List[VTTSegment]) -> bool:
        """Ensure timestamps are sequential and valid."""
        
    def extract_speakers(self, content: str) -> List[str]:
        """Extract unique speakers from VTT."""
```

#### VTTParser
```python
class VTTParser:
    """Parses VTT files into structured segments."""
    
    def parse_file(self, file_path: Path) -> List[TranscriptSegment]:
        """Parse VTT file into segments."""
        
    def normalize_segment(self, vtt_cue: VTTCue) -> TranscriptSegment:
        """Convert VTT cue to standard segment format."""
        
    def merge_short_segments(self, segments: List[TranscriptSegment], 
                           min_duration: float = 2.0) -> List[TranscriptSegment]:
        """Optionally merge very short segments."""
```

### 2. Processing Configuration

#### VTTProcessingConfig
```yaml
vtt_processing:
  # Input configuration
  input:
    directories:
      - /path/to/transcripts
    file_pattern: "*.vtt"
    recursive: true
    
  # Parsing options
  parsing:
    merge_short_segments: true
    min_segment_duration: 2.0
    preserve_speaker_labels: true
    
  # Batch processing
  batch:
    max_files_per_batch: 50
    parallel_files: 5
    checkpoint_frequency: 10
    
  # Metadata handling
  metadata:
    use_directory_name_as_podcast: true
    metadata_file_name: "metadata.json"
    infer_episode_title_from_filename: true
```

### 3. CLI Interface Design

#### New CLI Commands
```bash
# Process single VTT file
podcast-kg process-vtt --file episode.vtt --podcast "My Podcast"

# Process directory of VTT files
podcast-kg process-vtt --directory /transcripts --recursive

# Batch process with pattern
podcast-kg process-vtt --directory /transcripts --pattern "2024*.vtt"

# Dry run to preview what will be processed
podcast-kg process-vtt --directory /transcripts --dry-run

# Resume from checkpoint
podcast-kg process-vtt --directory /transcripts --resume

# Status check
podcast-kg status --session-id abc123
```

### 4. Data Flow

#### Input Data Structure
```python
@dataclass
class VTTFile:
    """Represents a VTT file to be processed."""
    path: Path
    podcast_name: str
    episode_title: str
    file_hash: str
    size_bytes: int
    created_at: datetime

@dataclass
class VTTSegment:
    """Parsed VTT segment."""
    index: int
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str]
    metadata: Dict[str, Any]
```

#### Processing Flow
1. **Discovery Phase**
   - Scan directories for VTT files
   - Group by podcast/show
   - Load any metadata files
   - Calculate file hashes for change detection

2. **Validation Phase**
   - Validate VTT format
   - Check timestamp consistency
   - Extract speaker information
   - Report any issues

3. **Parsing Phase**
   - Parse VTT into segments
   - Normalize timestamp formats
   - Preserve speaker labels
   - Optionally merge short segments

4. **Processing Phase**
   - Feed segments to knowledge extraction
   - Maintain episode context
   - Track progress via checkpoints

### 5. Error Handling Strategy

```python
class VTTProcessingError(Exception):
    """Base exception for VTT processing errors."""

class VTTParseError(VTTProcessingError):
    """Raised when VTT file cannot be parsed."""

class VTTValidationError(VTTProcessingError):
    """Raised when VTT file fails validation."""

# Error handling approach
error_policy:
  on_parse_error: skip_and_log
  on_validation_error: skip_and_log
  on_extraction_error: retry_with_backoff
  max_retries: 3
  continue_on_error: true
```

### 6. Checkpoint System Updates

```python
@dataclass
class VTTCheckpoint:
    """Checkpoint for VTT processing session."""
    session_id: str
    started_at: datetime
    last_updated: datetime
    total_files: int
    processed_files: List[str]
    failed_files: Dict[str, str]  # file -> error
    current_file: Optional[str]
    current_segment_index: Optional[int]
```

### 7. Integration Points

#### With Existing Components
- **PipelineExecutor**: Adapt to accept VTT segments directly
- **CheckpointManager**: Extend for VTT file tracking
- **StorageCoordinator**: No changes needed
- **LLM Providers**: No changes needed
- **Graph Providers**: No changes needed

#### Removed Dependencies
- **AudioProvider**: Completely removed
- **FeedProcessor**: Completely removed
- **Downloader**: Completely removed

## Performance Considerations

1. **Memory Management**
   - Stream large VTT files instead of loading entirely
   - Process files in batches to control memory usage
   - Clear processed segments after graph storage

2. **Parallel Processing**
   - Process multiple VTT files concurrently
   - Configurable worker pool size
   - Respect system resource limits

3. **Caching Strategy**
   - Cache parsed VTT files by hash
   - Skip unchanged files on re-runs
   - Clear cache on demand

## Migration Path

1. **Existing Data**: No migration needed (fresh start)
2. **Configuration**: Provide conversion tool for old configs
3. **Checkpoints**: New checkpoint format, old ones ignored
4. **API**: Deprecate old endpoints, add new VTT endpoints