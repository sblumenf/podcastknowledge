# Fast Knowledge Extraction Implementation Plan

## Overview
Transform the 90-minute pipeline into a 6-minute solution by consolidating 155 LLM calls into 3-5 strategic calls.

## Implementation Steps

### Step 1: Create FastExtractor Module
**File**: `src/extraction/fast_extractor.py`

```python
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class FastExtractionResult:
    entities: List[Dict[str, Any]]
    insights: List[Dict[str, Any]]
    quotes: List[Dict[str, Any]]
    topics: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class FastKnowledgeExtractor:
    def __init__(self, llm_service, graph_storage):
        self.llm = llm_service
        self.storage = graph_storage
        
    async def extract_episode(self, vtt_path: Path, metadata: Dict) -> FastExtractionResult:
        """Main entry point for fast extraction."""
        # Implementation here
```

### Step 2: Optimize Speaker Identification
**File**: `src/vtt/fast_speaker_identifier.py`

```python
class FastSpeakerIdentifier:
    """Batch speaker identification in single call."""
    
    async def identify_all_speakers(self, segments: List[Dict]) -> Dict[str, str]:
        """
        Single LLM call to identify all speakers.
        Returns mapping of generic labels to real names.
        """
        # Create consolidated prompt with first 20 segments
        # Return speaker mapping for entire transcript
```

### Step 3: Implement Consolidated Extraction
**Key Features**:
- Single prompt template for all knowledge types
- Token-efficient context representation
- Quality thresholds built into prompts
- JSON schema validation

### Step 4: Create Direct Storage Layer
**File**: `src/storage/fast_storage.py`

```python
class FastGraphStorage:
    """Optimized storage bypassing MeaningfulUnits."""
    
    async def store_episode_knowledge(self, episode_id: str, knowledge: FastExtractionResult):
        """Single transaction to store all knowledge."""
        # Batch create all nodes and relationships
        # Use UNWIND for efficient bulk operations
```

### Step 5: Add Parallel Processing Option
```python
async def extract_episode_parallel(self, vtt_path: Path, metadata: Dict):
    """Process transcript in 3 parallel chunks for extra speed."""
    segments = parse_vtt(vtt_path)
    
    # Split into chunks
    chunk_size = len(segments) // 3
    chunks = [
        segments[:chunk_size],
        segments[chunk_size:chunk_size*2],
        segments[chunk_size*2:]
    ]
    
    # Parallel extraction
    results = await asyncio.gather(*[
        self.extract_chunk(chunk, i) for i, chunk in enumerate(chunks)
    ])
    
    # Merge results
    return self.merge_extraction_results(results)
```

## Testing Strategy

### 1. Quality Validation
```python
# Compare extraction quality
old_result = await old_pipeline.process(test_episode)
new_result = await fast_extractor.extract(test_episode)

quality_metrics = {
    'entity_overlap': calculate_overlap(old_result.entities, new_result.entities),
    'insight_quality': compare_insights(old_result, new_result),
    'quote_accuracy': validate_quotes(old_result, new_result)
}
```

### 2. Performance Benchmarks
- Target: <6 minutes per episode
- Measure: Token usage, API calls, memory usage
- Compare: Cost reduction, processing time

### 3. A/B Testing Plan
- Process 10 episodes with both pipelines
- Compare knowledge graphs
- User evaluation of extraction quality

## Rollout Plan

### Week 1: Development
- [ ] Implement FastKnowledgeExtractor
- [ ] Create optimized prompts
- [ ] Build direct storage layer
- [ ] Add comprehensive logging

### Week 2: Testing
- [ ] Process 5 test episodes
- [ ] Validate extraction quality
- [ ] Tune prompts based on results
- [ ] Performance optimization

### Week 3: Integration
- [ ] Add fast mode flag to main.py
- [ ] Implement fallback to old pipeline
- [ ] Create comparison tools
- [ ] Documentation

### Week 4: Production
- [ ] Deploy with feature flag
- [ ] Monitor performance metrics
- [ ] Gather user feedback
- [ ] Plan deprecation timeline

## Risk Mitigation

1. **Quality Degradation**
   - Mitigation: Adjustable quality thresholds
   - Fallback: Hybrid approach for important episodes

2. **LLM Token Limits**
   - Mitigation: Smart truncation strategies
   - Fallback: Automatic chunking for long episodes

3. **Missing Relationships**
   - Mitigation: Post-processing relationship inference
   - Fallback: Optional detailed extraction mode

## Success Metrics

| Metric | Current | Target | Stretch Goal |
|--------|---------|--------|--------------|
| Processing Time | 90 min | 6 min | 3 min |
| LLM Calls | 155 | 5 | 3 |
| Token Usage | 500K | 50K | 30K |
| Cost per Episode | $2.50 | $0.25 | $0.15 |
| Entity Coverage | 100% | 85% | 90% |
| Insight Quality | High | Good | High |

## Configuration Options

```python
# config.py
FAST_EXTRACTION_CONFIG = {
    'mode': 'balanced',  # 'fast', 'balanced', 'quality'
    'parallel_chunks': 3,
    'quality_threshold': 0.7,
    'max_entities': 50,
    'max_insights': 20,
    'max_quotes': 10,
    'enable_caching': True,
    'batch_storage': True
}
```

## Next Steps

1. **Immediate**: Create proof-of-concept with single test episode
2. **Short-term**: Implement full FastKnowledgeExtractor
3. **Medium-term**: Deploy alongside existing pipeline
4. **Long-term**: Deprecate old pipeline if metrics met

## Command to Test

```bash
# Once implemented
python main.py input/test_episode.vtt \
  --podcast "Test Podcast" \
  --title "Test Episode" \
  --fast-mode \
  --compare-modes
```