# VTT Processing Test Strategy

## Overview
This document outlines the comprehensive testing strategy for the VTT-based knowledge seeding pipeline, ensuring robust coverage while maintaining practical test execution times.

## Test Categories

### 1. Unit Tests (Target: 85% coverage)

#### VTT Parser Tests
```python
tests/unit/test_vtt_parser.py
- test_parse_valid_vtt_file()
- test_parse_vtt_with_speakers()
- test_parse_vtt_without_speakers()
- test_parse_malformed_vtt()
- test_parse_empty_vtt()
- test_parse_vtt_with_overlapping_timestamps()
- test_parse_vtt_with_gaps()
- test_normalize_timestamps()
- test_extract_speaker_from_cue()
- test_merge_short_segments()
```

#### VTT Validator Tests
```python
tests/unit/test_vtt_validator.py
- test_validate_correct_format()
- test_validate_missing_header()
- test_validate_invalid_timestamps()
- test_validate_empty_segments()
- test_validate_non_sequential_timestamps()
- test_validate_encoding_issues()
```

#### Folder Scanner Tests
```python
tests/unit/test_folder_scanner.py
- test_scan_directory_recursive()
- test_scan_directory_non_recursive()
- test_scan_with_pattern()
- test_group_by_podcast()
- test_load_metadata_json()
- test_handle_missing_metadata()
- test_file_hash_calculation()
```

#### Ingestion Module Tests
```python
tests/unit/test_transcript_ingestion.py
- test_process_single_file()
- test_process_directory()
- test_skip_processed_files()
- test_error_handling()
- test_checkpoint_creation()
- test_resume_from_checkpoint()
```

### 2. Integration Tests (Target: 70% coverage)

#### End-to-End VTT Processing
```python
tests/integration/test_vtt_pipeline.py
- test_complete_vtt_to_graph_flow()
- test_batch_vtt_processing()
- test_parallel_file_processing()
- test_checkpoint_recovery()
- test_error_recovery()
- test_memory_usage_limits()
```

#### Knowledge Extraction Integration
```python
tests/integration/test_vtt_extraction.py
- test_vtt_segments_to_entities()
- test_preserve_speaker_context()
- test_timestamp_metadata_preservation()
- test_multi_speaker_conversations()
```

#### Neo4j Integration
```python
tests/integration/test_vtt_graph_storage.py
- test_vtt_metadata_in_graph()
- test_episode_from_vtt_file()
- test_speaker_nodes_creation()
- test_segment_relationships()
```

### 3. Performance Tests

#### Benchmark Tests
```python
tests/performance/test_vtt_benchmarks.py
- test_parse_large_vtt_file()  # 1000+ segments
- test_batch_processing_speed()  # 100 files
- test_memory_usage_per_file()
- test_concurrent_processing_limits()
```

#### Load Tests
```python
tests/performance/test_vtt_load.py
- test_process_1000_files()
- test_memory_leak_detection()
- test_cpu_usage_patterns()
- test_neo4j_write_performance()
```

### 4. Test Data Requirements

#### Sample VTT Files
```
tests/fixtures/vtt/
├── valid/
│   ├── simple.vtt              # Basic VTT, no speakers
│   ├── with_speakers.vtt       # VTT with <v> tags
│   ├── multi_speaker.vtt       # Complex conversation
│   ├── long_episode.vtt        # 1000+ segments
│   └── with_metadata.vtt       # Rich cue settings
├── invalid/
│   ├── missing_header.vtt      # No WEBVTT header
│   ├── bad_timestamps.vtt      # Invalid time format
│   ├── empty.vtt              # Empty file
│   └── corrupted.vtt          # Binary data
└── edge_cases/
    ├── unicode_content.vtt     # Non-ASCII characters
    ├── overlapping_times.vtt   # Timestamp overlaps
    ├── huge_segments.vtt       # Very long text blocks
    └── minimal.vtt            # Single segment
```

#### Test Metadata Files
```json
// tests/fixtures/vtt/metadata.json
{
  "podcast": {
    "name": "Test Podcast",
    "description": "A test podcast for VTT processing",
    "categories": ["Technology", "AI"]
  },
  "episode": {
    "title": "Episode 1: Introduction",
    "description": "First episode",
    "date": "2024-01-01",
    "duration_seconds": 1800
  }
}
```

### 5. Mock Strategies

#### LLM Provider Mocking
```python
class MockLLMProviderForVTT:
    """Predictable LLM responses for VTT segments."""
    
    def extract_knowledge(self, segment: TranscriptSegment) -> KnowledgeResult:
        # Return deterministic entities based on segment content
        # Useful for testing extraction consistency
```

#### File System Mocking
```python
class MockFileSystem:
    """In-memory file system for testing."""
    
    def add_vtt_file(self, path: str, content: str) -> None:
        # Add VTT file to mock filesystem
        
    def scan_directory(self, path: str) -> List[str]:
        # Return mock file listings
```

### 6. Test Execution Strategy

#### Continuous Integration
```yaml
# .github/workflows/test.yml
test-vtt-processing:
  stages:
    - quick-unit-tests:     # ~2 minutes
        - parser tests
        - validator tests
        - scanner tests
    - integration-tests:    # ~5 minutes
        - pipeline tests
        - extraction tests
    - slow-tests:          # ~10 minutes
        - performance tests
        - load tests
```

#### Local Development
```bash
# Fast feedback loop (unit tests only)
pytest tests/unit/test_vtt* -v

# Pre-commit comprehensive
pytest tests/ -m "not slow"

# Full test suite
pytest tests/ --cov=src.vtt --cov-report=html
```

### 7. Coverage Targets

| Component | Unit | Integration | E2E | Total |
|-----------|------|-------------|-----|-------|
| VTT Parser | 90% | 70% | 50% | 85% |
| VTT Validator | 95% | 60% | 40% | 80% |
| Folder Scanner | 85% | 70% | 50% | 80% |
| Ingestion | 80% | 75% | 60% | 75% |
| **Overall** | **87%** | **69%** | **50%** | **80%** |

### 8. Error Scenario Testing

#### Parse Errors
- Malformed VTT syntax
- Encoding issues (UTF-8, UTF-16)
- Truncated files
- Binary files mistaken as VTT

#### Processing Errors
- LLM API failures
- Neo4j connection loss
- Out of memory conditions
- Disk space exhaustion

#### Recovery Testing
- Checkpoint corruption
- Partial file processing
- System crash recovery
- Concurrent access conflicts

### 9. Test Utilities

#### VTT Test Builder
```python
class VTTBuilder:
    """Fluent API for building test VTT files."""
    
    def with_segment(self, start: str, end: str, text: str) -> 'VTTBuilder':
        # Add segment to VTT
        
    def with_speaker(self, speaker: str) -> 'VTTBuilder':
        # Set speaker for next segments
        
    def build(self) -> str:
        # Generate VTT content
```

#### Assertion Helpers
```python
def assert_valid_vtt_structure(content: str) -> None:
    """Assert VTT file has valid structure."""

def assert_segments_equal(actual: List[TranscriptSegment], 
                         expected: List[TranscriptSegment]) -> None:
    """Compare transcript segments with helpful diffs."""

def assert_graph_contains_vtt_data(neo4j_driver, vtt_file: str) -> None:
    """Verify VTT data made it to Neo4j correctly."""
```

### 10. Regression Test Suite

#### Golden Dataset
- 10 real VTT files from different sources
- Known good extraction results
- Automated comparison after changes
- Performance baselines tracked

#### Compatibility Tests
- Test VTT files from different tools:
  - YouTube transcripts
  - Zoom transcripts
  - Manual transcription tools
  - AI transcription services

## Test Implementation Priority

1. **Phase 1**: Core unit tests (VTT parser, validator)
2. **Phase 2**: Integration tests (pipeline flow)
3. **Phase 3**: Error handling tests
4. **Phase 4**: Performance benchmarks
5. **Phase 5**: Load and stress tests

## Success Metrics

- All tests pass on CI/CD pipeline
- Test execution time < 15 minutes for full suite
- No flaky tests (100% deterministic)
- Clear error messages on failures
- Easy to add new test cases