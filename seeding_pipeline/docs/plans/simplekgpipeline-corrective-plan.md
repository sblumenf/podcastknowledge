# Corrective Plan: Fix SimpleKGPipeline Entity Extraction

**Date**: June 14, 2025  
**Status**: Corrective Action Required  
**Priority**: HIGH - Core functionality broken  
**Original Plan**: simplekgpipeline-integration-plan.md

## Problem Summary

Entity extraction returns 0 entities because it uses hardcoded test data instead of AI extraction. This breaks the entire system since no features can work without entities.

## Minimal Corrective Actions Required

### Task 1: Fix Entity Extraction Method

**Current Problem**: `_extract_basic_entities` uses hardcoded data
**Fix Required**: Use the existing Gemini LLM to extract entities

```python
# Replace hardcoded entities with actual LLM extraction
async def _extract_basic_entities(self, text: str) -> List[Dict]:
    prompt = f"""Extract all entities from this text.
    Return as JSON list with 'name' and 'type' fields.
    Types: PERSON, ORGANIZATION, TOPIC, CONCEPT, EVENT, PRODUCT
    
    Text: {text}
    """
    
    response = await self.llm_adapter.ainvoke(prompt)
    entities = parse_json_response(response)
    return entities
```

### Task 2: Fix SimpleKGPipeline Integration

**Current Problem**: SimpleKGPipeline fails due to APOC dependency
**Fix Required**: Either install APOC or bypass SimpleKGPipeline temporarily

Option A - Install APOC:
```bash
# Add to Neo4j Docker or installation
neo4j-admin plugin install apoc
```

Option B - Direct Entity Creation:
```python
# If SimpleKGPipeline fails, create entities directly
for entity in extracted_entities:
    query = f"""
    MERGE (e:{entity['type']} {{name: $name}})
    SET e.created = timestamp()
    """
    session.run(query, name=entity['name'])
```

### Task 3: Verify Entity Creation

**Test Required**: Process one VTT file and verify entities exist

```bash
# After processing, check Neo4j:
MATCH (n) WHERE n:Person OR n:Organization OR n:Topic RETURN count(n)
# Should return 50+ entities, not 0
```

## Success Criteria

1. **Entity Count**: 50+ entities extracted from test transcript (not 0)
2. **Dynamic Types**: Person, Organization, Topic nodes in Neo4j
3. **Features Work**: Quotes link to speakers, insights link to entities

## Implementation Priority

1. **Fix extraction first** - Without entities, nothing else works
2. **Test with one file** - Verify entities are created
3. **Then test features** - Ensure they connect to entities

## Validation

Run this test:
```python
# Process VTT file
result = pipeline.process_vtt_file("test.vtt")
print(f"Entities created: {result.entities_created}")
# Should print 50+, not 0
```

## Note

All the advanced features are already built and integrated. They just need entities to work with. Fix the entity extraction and the entire system will function as designed.