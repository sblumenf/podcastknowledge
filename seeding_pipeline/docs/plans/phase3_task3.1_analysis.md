# Phase 3 Task 3.1 Analysis: Current Sequential Processing Flow

## Current Implementation

The knowledge extraction in `unified_pipeline.py` line 659 processes meaningful units SEQUENTIALLY:

```python
# Extract knowledge from each MeaningfulUnit
for idx, unit in enumerate(meaningful_units):
    # Process one unit at a time
    extraction_result = self.knowledge_extractor.extract_knowledge_combined(...)
    # Aggregate results
    # Analyze sentiment
    # Continue to next unit
```

## Processing Time Analysis

From logs:
- Combined extraction: ~35 seconds per unit
- Sentiment analysis: ~5-10 seconds per unit
- Total per unit: ~40-45 seconds

For 4 units: 4 × 45 = 180 seconds (3 minutes) sequential

## Parallelization Opportunity

Each meaningful unit is INDEPENDENT:
- No dependencies between units
- Each unit has its own text content
- Results are aggregated after processing

## Safe Parallelization Points

1. **Can Parallelize**:
   - Knowledge extraction per unit
   - Sentiment analysis per unit
   - All unit-level operations

2. **Must Remain Sequential**:
   - Episode parsing
   - Conversation analysis 
   - Entity resolution (post-processing)
   - Storage operations

## Existing Infrastructure

The codebase already has:
- `SimpleThreadPool` in `src/seeding/concurrency.py`
- `ThreadPoolExecutor` wrapper ready to use
- Pattern: `pool.map(processor_func, items)`

## Expected Performance Gain

With 5 concurrent units:
- Sequential: 180 seconds
- Parallel: ~45 seconds (limited by slowest unit)
- **4x speedup potential**