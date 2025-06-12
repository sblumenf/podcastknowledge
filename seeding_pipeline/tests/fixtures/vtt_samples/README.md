# VTT Sample Files Documentation

This directory contains VTT (WebVTT) sample files for testing the podcast knowledge extraction pipeline.

## Files and Their Purpose

### minimal.vtt
- **Captions**: 5 captions
- **Duration**: 25 seconds (00:00:00 - 00:00:25)
- **Purpose**: Basic VTT parsing and processing tests
- **Content**: Simple, straightforward text without special formatting
- **Use Cases**:
  - Testing core VTT parser functionality
  - Validating basic pipeline flow
  - Quick smoke tests
  - Performance baseline with minimal data

### standard.vtt
- **Captions**: 100 captions
- **Duration**: ~8 minutes (00:00:00 - 00:08:20)
- **Purpose**: Realistic workload testing with medium-sized content
- **Content**: Varied technology topics covering AI, ML, software development
- **Use Cases**:
  - Testing pipeline performance with realistic data volume
  - Validating knowledge extraction from substantial content
  - Testing batch processing capabilities
  - Stress testing database operations
  - Verifying memory management with larger datasets

### complex.vtt
- **Captions**: 15 captions with overlapping timings
- **Duration**: ~65 seconds (00:00:00 - 00:01:05)
- **Purpose**: Testing advanced VTT features and edge cases
- **Content**: Multi-speaker conversation with speaker identification
- **Special Features**:
  - Speaker tags (`<v Host>`, `<v Guest>`)
  - Overlapping time ranges (simulates real conversation dynamics)
  - Multi-participant dialogue
- **Use Cases**:
  - Testing speaker identification and separation
  - Validating handling of overlapping segments
  - Testing conversation flow analysis
  - Verifying entity extraction from multi-speaker content
  - Testing relationship mapping between speakers

## Usage in Tests

The `vtt_samples` fixture provides easy access to these files:

```python
def test_example(vtt_samples):
    minimal_file = vtt_samples['minimal']
    standard_file = vtt_samples['standard'] 
    complex_file = vtt_samples['complex']
    
    # Use files for testing...
```

## File Format

All files follow the WebVTT format specification:
- Start with `WEBVTT` header
- Timestamp format: `HH:MM:SS.mmm --> HH:MM:SS.mmm`
- Blank lines separate captions
- Speaker tags use `<v Speaker>` syntax (complex.vtt only)

## Maintenance

When updating these files:
1. Maintain the documented caption counts
2. Ensure timing consistency  
3. Keep content relevant to technology/AI topics
4. Test all files after modifications
5. Update this documentation if purposes change