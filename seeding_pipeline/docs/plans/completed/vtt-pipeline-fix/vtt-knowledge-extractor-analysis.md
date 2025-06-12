# VTTKnowledgeExtractor Interface Analysis

## Overview

The `VTTKnowledgeExtractor` class is the master orchestrator for VTT transcript knowledge extraction. It coordinates all components of the pipeline using dependency injection and provides the main API for extracting knowledge from VTT files and seeding the knowledge graph.

## Public Methods Available for VTT Processing

### 1. `process_vtt_files(vtt_files: List[Any], use_large_context: bool = True) -> Dict[str, Any]`
**Purpose**: Process multiple VTT files into knowledge graph
**Parameters**:
- `vtt_files`: List of VTTFile objects to process
- `use_large_context`: Whether to use large context models (default: True)
**Returns**: Summary dict with processing statistics
**Status**: ✅ **RECOMMENDED FOR CLI INTEGRATION**

### 2. `process_vtt_directory(directory_path: str, pattern: str = "*.vtt", recursive: bool = False, use_large_context: bool = True) -> Dict[str, Any]`
**Purpose**: Process VTT files from a directory
**Parameters**:
- `directory_path`: Path to directory containing VTT files
- `pattern`: File pattern to match (default: "*.vtt")
- `recursive`: Whether to search subdirectories
- `use_large_context`: Whether to use large context models
**Returns**: Processing summary
**Status**: Alternative option for directory-based processing

### 3. `process_text(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`
**Purpose**: Process raw text for baseline testing
**Parameters**:
- `text`: Raw text to process
- `metadata`: Optional metadata (episode_id, podcast_name, etc.)
**Returns**: Dictionary with extraction results
**Status**: For testing only

## Key Integration Points

### Initialization
The class requires initialization before use:
```python
extractor = VTTKnowledgeExtractor(config)
# Components are auto-initialized on first process call
# Or manually: extractor.initialize_components(use_large_context=True)
```

### Configuration Requirements
- Accepts `PipelineConfig` or `SeedingConfig`
- Auto-initializes with `SeedingConfig()` if none provided
- Uses existing environment variables for API keys and Neo4j connection

### Full Knowledge Extraction Pipeline
The `process_vtt_files` method includes:
1. **VTT Parsing** via `TranscriptIngestion`
2. **Knowledge Extraction** via `pipeline_executor.process_vtt_segments()`
3. **Entity Resolution** via provider coordinator
4. **Graph Storage** via storage coordinator
5. **Checkpoint Management** for resumability

## Expected Return Format

```python
{
    'start_time': '2025-06-11T03:45:20.123456',
    'end_time': '2025-06-11T03:47:45.654321',
    'files_processed': 1,
    'files_failed': 0,
    'total_segments': 119,
    'total_insights': 45,
    'total_entities': 78,
    'total_relationships': 32,
    'discovered_types': ['Person', 'Concept', 'Event'],
    'extraction_mode': 'schemaless',
    'success': True,
    'errors': []
}
```

## Required Input Format

The `process_vtt_files` method expects either:
1. **List of VTTFile objects** (preferred)
2. **List of Path objects** (automatically converted)

## Integration with Existing CLI

### Current CLI Flow (Broken)
```
CLI → TranscriptIngestionManager → TranscriptIngestion.process_vtt_file()
↓
Only VTT parsing (no knowledge extraction)
```

### Recommended CLI Flow (Fixed)
```
CLI → VTTKnowledgeExtractor.process_vtt_files()
↓
Full pipeline: VTT parsing → Knowledge extraction → Neo4j storage
```

## Configuration Compatibility

The orchestrator is fully compatible with existing CLI configuration:
- Uses same `config` object passed to CLI
- Respects all environment variables (API keys, Neo4j connection)
- Maintains checkpoint system integration
- Supports all existing CLI options (parallel processing, error handling)

## Conclusion

**The VTTKnowledgeExtractor already has the perfect interface for CLI integration**. The `process_vtt_files` method provides exactly what we need:
- Accepts file paths or VTTFile objects
- Performs complete knowledge extraction pipeline
- Returns detailed processing results
- Integrates with checkpoint system
- Handles errors gracefully

**No new methods need to be created** - we just need to modify the CLI to call `VTTKnowledgeExtractor.process_vtt_files()` instead of the broken `TranscriptIngestionManager` approach.