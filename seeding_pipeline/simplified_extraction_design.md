# Simplified Knowledge Extraction Pipeline Design

## Problem Statement

Current pipeline takes 90-120 minutes to process a single podcast episode due to:
- 155 separate LLM calls (5 per MeaningfulUnit × 31 units)
- Over-engineered extraction with unnecessary complexity
- Sequential processing with no batching
- Schema-less discovery requiring extensive LLM reasoning

## Proposed Solution: Single-Pass Extraction

### Core Principle
**One transcript, one extraction call.** Extract all knowledge in a single, well-crafted prompt.

### Pipeline Architecture

```
VTT File → Parse → Speaker ID → Single Knowledge Extraction → Neo4j Storage
   1s        20s                      3-5 min                    30s
                            Total: ~6 minutes
```

### Implementation Design

```python
class FastKnowledgeExtractor:
    """Simplified extractor focusing on speed over granularity."""
    
    async def extract_episode(self, vtt_path: Path, metadata: Dict):
        # Step 1: Parse VTT
        segments = self.parse_vtt(vtt_path)
        
        # Step 2: Batch speaker identification
        transcript_with_speakers = await self.identify_speakers_batch(segments)
        
        # Step 3: Single extraction call
        knowledge = await self.extract_all_knowledge(transcript_with_speakers)
        
        # Step 4: Direct storage
        await self.store_to_neo4j(knowledge, metadata)
        
    async def extract_all_knowledge(self, transcript: str):
        """Single LLM call to extract everything."""
        
        prompt = f"""
        Extract knowledge from this podcast transcript.
        
        Return a JSON object with:
        1. entities: List of important people, organizations, concepts, technologies
           - Include: name, type, description, first_mention_time
        
        2. key_insights: List of main insights, learnings, or takeaways
           - Include: insight, speaker, timestamp, importance (1-5)
        
        3. quotes: Most impactful or memorable quotes (max 10)
           - Include: text, speaker, timestamp, context
        
        4. topics: Main topics discussed with time ranges
           - Include: topic, start_time, end_time, summary
        
        5. relationships: Key connections between entities
           - Include: source, target, relationship_type
        
        Focus on quality over quantity. Extract only the most important information.
        
        Transcript:
        {transcript}
        """
        
        response = await self.llm.complete(prompt, max_tokens=8000)
        return json.loads(response)
```

### Key Optimizations

1. **Batching**: Process entire transcript at once
2. **Focused Extraction**: Only extract high-value knowledge
3. **Simple Schema**: Fixed structure, no schema-less discovery
4. **Quality Threshold**: "Important" filter built into prompt
5. **Token Efficiency**: One context load instead of 155

### Storage Simplification

```cypher
// Simplified Neo4j schema
(:Episode)-[:HAS_ENTITY]->(:Entity)
(:Episode)-[:HAS_INSIGHT]->(:Insight)
(:Episode)-[:HAS_QUOTE]->(:Quote)
(:Episode)-[:DISCUSSES]->(:Topic)
(:Entity)-[:RELATES_TO]->(:Entity)
```

### Trade-offs

**What We Lose:**
- MeaningfulUnit segmentation
- Per-segment sentiment analysis  
- Granular conversation flow tracking
- Some relationship nuance
- Checkpointing capability

**What We Gain:**
- 95% faster processing (90 min → 6 min)
- 90% fewer LLM calls (155 → 3-5)
- 80% lower costs
- Simpler maintenance
- Better scalability

### Migration Path

1. **Phase 1**: Implement FastKnowledgeExtractor alongside current pipeline
2. **Phase 2**: A/B test quality vs speed trade-off
3. **Phase 3**: Optimize prompts based on results
4. **Phase 4**: Deprecate old pipeline if quality acceptable

### Advanced Optimizations

If 6 minutes is still too slow:

1. **Parallel Speaker ID**: Process speakers while parsing VTT
2. **Streaming Extraction**: Start extracting before full transcript ready
3. **Chunked Processing**: Split transcript into 3 chunks, process in parallel
4. **Caching**: Cache speaker patterns across episodes
5. **Preprocessing**: Use regex for obvious entities before LLM

### Example Output Structure

```json
{
  "entities": [
    {
      "name": "Mel Robbins",
      "type": "PERSON",
      "description": "Host of the podcast, motivation expert",
      "first_mention": 0.5
    }
  ],
  "key_insights": [
    {
      "insight": "Confidence comes from taking action, not waiting to feel ready",
      "speaker": "Mel Robbins",
      "timestamp": 245.3,
      "importance": 5
    }
  ],
  "quotes": [
    {
      "text": "The 5 Second Rule changed my life",
      "speaker": "Guest",
      "timestamp": 567.8,
      "context": "Discussing personal transformation"
    }
  ],
  "topics": [
    {
      "topic": "Body confidence strategies",
      "start_time": 120.0,
      "end_time": 890.5,
      "summary": "Four expert steps to feeling more confident"
    }
  ],
  "relationships": [
    {
      "source": "Mel Robbins",
      "target": "5 Second Rule",
      "type": "CREATED"
    }
  ]
}
```

## Recommendation

Start with the simplified approach. You can always add complexity later if needed, but you can't get back the time and money spent on over-engineering.

The goal is a **good enough** knowledge graph that enables discovery, not a perfect extraction of every detail.