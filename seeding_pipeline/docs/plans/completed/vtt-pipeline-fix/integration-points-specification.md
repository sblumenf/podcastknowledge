# Integration Points Specification

## Required CLI to VTTKnowledgeExtractor Integration

Based on the analysis of the current architecture and available methods, here is the specification for integrating the CLI with the VTTKnowledgeExtractor.

## Current Interface Available

### VTTKnowledgeExtractor.process_vtt_files()

**Method Signature:**
```python
def process_vtt_files(self,
                     vtt_files: List[Any],
                     use_large_context: bool = True) -> Dict[str, Any]
```

**Parameters:**
- `vtt_files`: List of VTTFile objects OR Path objects (auto-converted)
- `use_large_context`: Whether to use large context models (default: True)

**Returns:** Dictionary with processing statistics
```python
{
    'start_time': str,           # ISO timestamp
    'end_time': str,            # ISO timestamp  
    'files_processed': int,      # Number successfully processed
    'files_failed': int,         # Number that failed
    'total_segments': int,       # Total VTT segments processed
    'total_insights': int,       # Insights extracted
    'total_entities': int,       # Entities extracted
    'total_relationships': int,  # Relationships found
    'discovered_types': List[str], # Entity types discovered
    'extraction_mode': str,      # 'schemaless' or 'fixed'
    'success': bool,            # Overall success status
    'errors': List[Dict]        # Error details if any
}
```

## Required CLI Modifications

### Current Code to Replace

**File:** `src/cli/cli.py` **Lines:** 682-697

```python
# ❌ REMOVE THIS SECTION
ingestion_manager = TranscriptIngestionManager(
    pipeline=pipeline,
    checkpoint=checkpoint
)

result = ingestion_manager.process_vtt_file(
    vtt_file=str(file_path),
    metadata={
        'source': 'cli',
        'file_name': file_path.name,
        'file_path': str(file_path),
        'processed_at': datetime.now().isoformat()
    }
)
```

### New Code to Implement

```python
# ✅ REPLACE WITH THIS
try:
    # Process single file through orchestrator
    result = pipeline.process_vtt_files(
        vtt_files=[file_path],  # List of Path objects
        use_large_context=True
    )
    
    # Transform orchestrator result to CLI expected format
    if result['success'] and result['files_processed'] > 0:
        cli_result = {
            'success': True,
            'segments_processed': result['total_segments'],
            'files_processed': result['files_processed'],
            'entities_extracted': result['total_entities'],
            'relationships_found': result['total_relationships']
        }
    else:
        cli_result = {
            'success': False,
            'error': '; '.join([err['error'] for err in result.get('errors', [])])
        }
        
except Exception as e:
    cli_result = {
        'success': False,
        'error': str(e)
    }
```

## Configuration Compatibility

### Current Configuration Flow
```python
config = PipelineConfig.from_file(args.config) or PipelineConfig()
pipeline = VTTKnowledgeExtractor(config)
```

### Required: No Changes
The VTTKnowledgeExtractor is already compatible with the existing configuration system.

## Checkpoint Integration

### Current Checkpoint Setup
```python
checkpoint = ProgressCheckpoint(
    checkpoint_dir=str(checkpoint_dir),
    extraction_mode='vtt'
)
```

### Required: Built-in Integration
The VTTKnowledgeExtractor already handles checkpoints internally via its `checkpoint_manager`. The external checkpoint creation can be simplified or removed.

## Input Format Compatibility

### Current CLI Input Processing
```python
vtt_files = find_vtt_files(folder, args.pattern, args.recursive)
# Returns: List[Path]
```

### VTTKnowledgeExtractor Compatibility
- ✅ **Accepts `List[Path]`** - Auto-converts to VTTFile objects
- ✅ **Accepts `List[VTTFile]`** - Direct processing
- ✅ **Handles single files** - Pass as single-item list

## Error Handling Integration

### Current CLI Error Handling
```python
if result['success']:
    print(f"  ✓ Success - {result['segments_processed']} segments processed")
    processed += 1
else:
    print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
    failed += 1
```

### Required: Enhanced Error Reporting
```python
if result['success'] and result['files_processed'] > 0:
    print(f"  ✓ Success - {result['total_segments']} segments processed")
    print(f"    - {result['total_entities']} entities extracted")
    print(f"    - {result['total_relationships']} relationships found")
    processed += 1
else:
    error_msg = '; '.join([err['error'] for err in result.get('errors', [])])
    print(f"  ✗ Failed: {error_msg}")
    failed += 1
```

## Batch Processing Integration

### Current Batch Processing
```python
if len(vtt_files) > 1 and args.parallel:
    return process_vtt_batch(vtt_files, pipeline, checkpoint, args)
```

### Required: Direct Orchestrator Call
```python
if len(vtt_files) > 1 and args.parallel:
    # Use orchestrator's built-in batch processing
    result = pipeline.process_vtt_files(
        vtt_files=vtt_files,
        use_large_context=True
    )
    return handle_batch_result(result, args)
```

## API Design Patterns Applied

### 1. **Adapter Pattern** 
Current `TranscriptIngestionManager` acts as an adapter but only to the parsing layer.

**Fix:** Remove adapter, use direct interface.

### 2. **Facade Pattern**
`VTTKnowledgeExtractor` acts as a facade to the complex pipeline.

**Implementation:** CLI calls facade method `process_vtt_files()`.

### 3. **Command Pattern**
CLI command encapsulates VTT processing request.

**Implementation:** Pass complete configuration through single method call.

## Integration Checklist

- [ ] Remove `TranscriptIngestionManager` instantiation from CLI
- [ ] Replace `ingestion_manager.process_vtt_file()` calls
- [ ] Update result processing to handle orchestrator return format
- [ ] Enhance error reporting to show knowledge extraction metrics
- [ ] Test single file processing
- [ ] Test batch processing  
- [ ] Verify checkpoint integration works correctly
- [ ] Ensure all CLI options (parallel, skip-errors) work with new integration

## Success Metrics

After integration, the CLI should:
1. **Process VTT files through full knowledge extraction pipeline**
2. **Display entity and relationship counts in output**
3. **Take significantly longer** (indicating LLM processing)
4. **Populate Neo4j database** with extracted knowledge
5. **Maintain all existing CLI functionality** (checkpoints, error handling, etc.)

## Risk Mitigation

### Backward Compatibility
- CLI interface remains unchanged for users
- Configuration system unchanged
- Output format enhanced but compatible

### Error Handling
- Comprehensive error catching at integration point
- Graceful degradation if orchestrator fails
- Clear error messages for troubleshooting

### Performance
- Use large context models by default for better quality
- Respect existing parallel processing options
- Checkpoint system prevents reprocessing