# Value-Preserving Pipeline Optimization Plan

## Goal
Reduce processing time from 90 minutes to 15-20 minutes while maintaining ALL current functionality.

## Strategy: Optimize, Don't Eliminate

### 1. Parallel Processing Within MeaningfulUnits
Instead of 5 sequential calls per unit, make them parallel:

```python
async def extract_from_meaningful_unit(self, unit: MeaningfulUnit):
    # Current: 5 sequential calls (3-4 minutes)
    entities = await extract_entities(unit)  # 1 min
    quotes = await extract_quotes(unit)      # 1 min
    insights = await extract_insights(unit)  # 1 min
    relationships = await extract_relationships(unit)  # 30s
    sentiment = await analyze_sentiment(unit)  # 30s
    
    # Optimized: 5 parallel calls (1-1.5 minutes)
    results = await asyncio.gather(
        extract_entities(unit),
        extract_quotes(unit),
        extract_insights(unit),
        extract_relationships(unit),
        analyze_sentiment(unit)
    )
```

**Time savings: 60-70% per unit**

### 2. Batch MeaningfulUnit Processing
Process multiple units concurrently:

```python
async def process_meaningful_units(self, units: List[MeaningfulUnit]):
    # Process 5 units at a time to stay within rate limits
    batch_size = 5
    results = []
    
    for i in range(0, len(units), batch_size):
        batch = units[i:i + batch_size]
        batch_results = await asyncio.gather(*[
            self.extract_from_meaningful_unit(unit) for unit in batch
        ])
        results.extend(batch_results)
    
    return results
```

**Time savings: 31 units in 7 batches = 10-15 minutes total**

### 3. Shared Context Optimization
Create a shared context cache for each MeaningfulUnit:

```python
class ContextCache:
    """Cache processed unit data to avoid redundant processing."""
    
    def __init__(self, meaningful_unit: MeaningfulUnit):
        self.unit = meaningful_unit
        self.embeddings = None
        self.key_phrases = None
        self.entity_candidates = None
        
    async def prepare(self):
        """Pre-process unit once for all extractors."""
        self.embeddings = await generate_embeddings(self.unit.text)
        self.key_phrases = extract_key_phrases(self.unit.text)
        self.entity_candidates = identify_entity_candidates(self.unit.text)

# Use in extractors
async def extract_entities(unit: MeaningfulUnit, cache: ContextCache):
    # Use pre-processed data instead of processing again
    candidates = cache.entity_candidates
    # ... continue with LLM extraction
```

### 4. Smart Batching for LLM Calls
Combine related extractions into single prompts:

```python
async def extract_entities_and_relationships(unit: MeaningfulUnit):
    """Single LLM call for related extractions."""
    prompt = f"""
    Extract from this text:
    1. All entities (people, organizations, concepts, technologies)
    2. All relationships between entities
    3. Entity properties and descriptions
    
    Return as JSON with both entities and relationships.
    
    Text: {unit.text}
    """
    
    response = await llm.complete(prompt)
    result = json.loads(response)
    return result['entities'], result['relationships']
```

**Reduces 2 calls to 1 per unit**

### 5. Progressive Enhancement Strategy
Start with fast, basic extraction then enhance:

```python
async def progressive_extraction(unit: MeaningfulUnit):
    # Fast first pass (30 seconds)
    basic_knowledge = await quick_extract(unit)
    
    # Parallel enhancement (1 minute)
    enhanced = await asyncio.gather(
        enhance_entities(basic_knowledge.entities),
        enhance_relationships(basic_knowledge.relationships),
        extract_additional_insights(unit, basic_knowledge)
    )
    
    return merge_results(basic_knowledge, enhanced)
```

### 6. Optimize Conversation Analysis
Cache conversation structure for reuse:

```python
class ConversationAnalysisCache:
    def __init__(self):
        self.structure = None
        self.speaker_patterns = {}
        self.topic_boundaries = []
        
    async def analyze_once(self, segments):
        """Analyze conversation structure once, reuse everywhere."""
        if not self.structure:
            self.structure = await analyze_structure(segments)
            self.speaker_patterns = await identify_patterns(segments)
            self.topic_boundaries = await find_boundaries(segments)
        return self.structure
```

## Implementation Priorities

### Phase 1: Quick Wins (1-2 days)
1. Implement parallel extraction within MeaningfulUnits
2. Add batch processing for units
3. Expected improvement: 50-60% faster

### Phase 2: Smart Optimizations (3-5 days)
1. Implement shared context caching
2. Combine related LLM calls
3. Expected improvement: 70-80% faster

### Phase 3: Advanced Features (1 week)
1. Progressive enhancement
2. Conversation analysis caching
3. Expected improvement: 85% faster

## Performance Projections

| Component | Current Time | Optimized Time | Method |
|-----------|--------------|----------------|--------|
| Speaker ID | 11s | 11s | No change needed |
| Conversation Analysis | 112s | 60s | Caching + optimization |
| Knowledge Extraction | 75 min | 12-15 min | Parallel + batching |
| Storage | 5 min | 2 min | Batch operations |
| **Total** | **90 min** | **15-20 min** | **80% reduction** |

## What We Keep

✅ All MeaningfulUnits and their structure  
✅ Complete conversation analysis  
✅ Full sentiment tracking per unit  
✅ Detailed speaker dynamics  
✅ Rich relationship extraction  
✅ Checkpoint/resume capability  
✅ Schema-less discovery  
✅ All graph relationships  

## Configuration for Testing

```python
# config.py
OPTIMIZATION_CONFIG = {
    'parallel_extraction': True,
    'batch_size': 5,  # Units to process concurrently
    'use_context_cache': True,
    'combine_related_calls': True,
    'max_concurrent_llm_calls': 25,  # Well under rate limit
    'progressive_enhancement': False,  # Enable after testing
}
```

## Monitoring and Rollback

```python
class OptimizationMonitor:
    def track_extraction_quality(self, original, optimized):
        return {
            'entity_overlap': calculate_overlap(original, optimized),
            'relationship_coverage': compare_relationships(original, optimized),
            'insight_quality': score_insights(original, optimized),
            'processing_time': {
                'original': original.time,
                'optimized': optimized.time,
                'improvement': (1 - optimized.time/original.time) * 100
            }
        }
```

## Next Steps

1. **Immediate**: Implement parallel extraction for one MeaningfulUnit as proof of concept
2. **Day 2**: Add batch processing for multiple units
3. **Day 3-4**: Implement context caching
4. **Day 5**: Test on full episode, measure quality
5. **Week 2**: Full rollout with monitoring

This approach gives you 80% speed improvement while keeping 100% of your application's value.