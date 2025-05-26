# Migration Path for Deprecated Features

This document provides detailed migration paths for each deprecated feature in the podcast knowledge pipeline.

## Table of Contents

1. [KnowledgeExtractor Migration](#knowledgeextractor-migration)
2. [Entity Extraction Migration](#entity-extraction-migration)
3. [Insight Extraction Migration](#insight-extraction-migration)
4. [Quote Extraction Migration](#quote-extraction-migration)
5. [Topic Extraction Migration](#topic-extraction-migration)
6. [Model Migration](#model-migration)
7. [Testing Migration](#testing-migration)

## KnowledgeExtractor Migration

### What's Changing

The `KnowledgeExtractor` class uses a fixed schema approach where entity types, relationships, and properties are predefined. This is being replaced by `SimpleKGPipeline` which discovers the schema from the content.

### Migration Steps

1. **Update Imports**

```python
# Old
from src.processing.extraction import KnowledgeExtractor

# New
from neo4j_graphrag import SimpleKGPipeline
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
```

2. **Update Initialization**

```python
# Old
extractor = KnowledgeExtractor(
    llm_provider=llm,
    use_large_context=True,
    max_retries=3
)

# New
graph_provider = SchemalessNeo4jProvider(driver)
kg_pipeline = SimpleKGPipeline(
    llm=llm.get_client(),  # Get underlying LLM client
    driver=driver,
    embedder=embedding_model,
    create_lexical_graph=True,
    create_entity_graph=True
)
```

3. **Update Extraction Calls**

```python
# Old
result = extractor.extract_all(text, context)
entities = result.entities
insights = result.insights

# New
kg_result = kg_pipeline.extract(text)
# Results are now in the graph - query as needed
```

## Entity Extraction Migration

### What's Changing

Fixed entity types (PERSON, ORGANIZATION, etc.) are replaced by dynamic entity discovery.

### Migration Steps

1. **Entity Creation**

```python
# Old
entity = Entity(
    type=EntityType.PERSON,
    name="John Doe",
    description="CEO of TechCorp"
)

# New - Entities are created automatically during extraction
# Access via graph queries:
entities = graph_provider.query("""
    MATCH (e:Entity)
    WHERE e.name = 'John Doe'
    RETURN e
""")
```

2. **Entity Type Checking**

```python
# Old
if entity.type == EntityType.PERSON:
    process_person(entity)
elif entity.type == EntityType.ORGANIZATION:
    process_org(entity)

# New
entity_data = entities[0]['e']
if 'Person' in entity_data.get('labels', []):
    process_person(entity_data)
elif 'Organization' in entity_data.get('labels', []):
    process_org(entity_data)
```

3. **Entity Properties**

```python
# Old - Fixed properties
entity.confidence_score
entity.source_segment_id

# New - Flexible properties
entity_data.get('confidence', 0.0)
entity_data.get('source_segment')
entity_data.get('custom_property')  # Any property is possible
```

## Insight Extraction Migration

### What's Changing

Discrete "insights" are replaced by relationships and patterns in the knowledge graph.

### Migration Steps

1. **Insight Discovery**

```python
# Old
insights = extractor.extract_insights(text, entities)
for insight in insights:
    if insight.type == InsightType.TREND:
        handle_trend(insight)

# New - Insights are relationships
insights = graph_provider.query("""
    MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity)
    WHERE r.insight_type = 'trend'
    RETURN e1, r, e2
""")
```

2. **Creating Insights**

```python
# Old
insight = Insight(
    type=InsightType.CONNECTION,
    content="AI adoption is accelerating",
    confidence_score=0.85
)

# New - Created as graph relationships
graph_provider.query("""
    MATCH (ai:Topic {name: 'AI'})
    MATCH (adoption:Concept {name: 'adoption'})
    CREATE (ai)-[r:ACCELERATING {
        confidence: 0.85,
        discovered_at: timestamp()
    }]->(adoption)
""")
```

## Quote Extraction Migration

### What's Changing

Quote extraction is now handled by the schemaless quote extractor which provides more context.

### Migration Steps

1. **Quote Extraction**

```python
# Old
quotes = extractor.extract_quotes(text)
memorable_quotes = [q for q in quotes if q.type == QuoteType.MEMORABLE]

# New
from src.processing.schemaless_quote_extractor import SchemalessQuoteExtractor

quote_extractor = SchemalessQuoteExtractor(llm_provider)
quotes = quote_extractor.extract(text, metadata={
    'speakers': speaker_info,
    'timestamps': timestamp_info
})
```

2. **Quote Properties**

```python
# Old
quote.speaker
quote.timestamp
quote.context

# New - Richer quote information
quote['speaker_name']
quote['speaker_role']
quote['start_time']
quote['end_time']
quote['surrounding_context']
quote['significance']
```

## Topic Extraction Migration

### What's Changing

Topics are no longer explicitly extracted but emerge from the knowledge graph structure.

### Migration Steps

1. **Topic Discovery**

```python
# Old
topics = extractor.extract_topics(text, entities, insights)

# New - Topics emerge from graph analysis
topics = graph_provider.query("""
    MATCH (t:Topic)
    OPTIONAL MATCH (t)-[r]-(connected)
    RETURN t.name as topic,
           count(connected) as connections,
           collect(distinct labels(connected)) as connected_types
    ORDER BY connections DESC
""")
```

2. **Topic Relationships**

```python
# Old
topic['related_entities'] = [e.id for e in entities if e.name in topic['description']]

# New - Natural graph relationships
graph_provider.query("""
    MATCH (t:Topic {name: $topic_name})-[:DISCUSSES|:RELATES_TO]-(e:Entity)
    RETURN e
""", {'topic_name': topic_name})
```

## Model Migration

### Data Model Changes

1. **From Fixed to Flexible Schema**

```python
# Old models (src/core/models.py)
@dataclass
class Entity:
    type: EntityType
    name: str
    description: str
    # ... fixed fields

# New - No predefined model
# Entities are dictionaries with flexible properties
entity = {
    'name': 'John Doe',
    'type': 'Person',  # Discovered, not enum
    'role': 'CEO',     # Custom property
    'company': 'Tech Corp',  # Custom property
    # ... any other properties
}
```

2. **Enum Replacement**

```python
# Old
EntityType.PERSON
InsightType.TREND
QuoteType.MEMORABLE

# New - String labels
'Person'
'Trend'
'MemorableQuote'
```

## Testing Migration

### Unit Tests

```python
# Old test
def test_extract_entities():
    entities = extractor.extract_entities(text)
    assert len(entities) == 3
    assert entities[0].type == EntityType.PERSON

# New test
def test_schemaless_extraction():
    kg_pipeline.extract(text)
    
    # Query the graph
    result = driver.execute_query(
        "MATCH (e:Entity) RETURN count(e) as count"
    )
    assert result[0]['count'] == 3
    
    # Check entity types
    person = driver.execute_query(
        "MATCH (e:Person) RETURN e LIMIT 1"
    )
    assert person[0]['e']['name'] is not None
```

### Integration Tests

```python
# Old
result = extractor.extract_all(podcast_transcript)
assert len(result.entities) > 0
assert len(result.insights) > 0

# New
kg_pipeline.extract(podcast_transcript)

# Verify extraction created graph structure
stats = graph_provider.get_statistics()
assert stats['node_count'] > 0
assert stats['relationship_count'] > 0
assert 'Person' in stats['node_labels']
```

## Gradual Migration Strategy

1. **Phase 1: Enable Feature Flag**
   ```bash
   export FF_ENABLE_SCHEMALESS_EXTRACTION=true
   export FF_SCHEMALESS_MIGRATION_MODE=true
   ```

2. **Phase 2: Update Code**
   - Replace extraction calls
   - Update result handling
   - Modify tests

3. **Phase 3: Validate**
   - Compare outputs
   - Check performance
   - Verify data completeness

4. **Phase 4: Switch Over**
   ```bash
   export FF_SCHEMALESS_MIGRATION_MODE=false
   # Only schemaless now
   ```

5. **Phase 5: Cleanup**
   - Remove deprecated imports
   - Delete old test code
   - Update documentation

## Common Issues and Solutions

### Issue: Missing Entity Types

**Problem**: Fixed enum types don't exist in schemaless
**Solution**: Use string labels or check node labels

### Issue: Different Result Structure

**Problem**: Results are in graph, not objects
**Solution**: Use graph queries to retrieve data

### Issue: Performance Differences

**Problem**: Schemaless may be slower initially
**Solution**: Enable caching, optimize queries

### Issue: Test Failures

**Problem**: Tests expect fixed schema objects
**Solution**: Update tests to query graph instead

## Support

For migration help:
1. Enable debug logging: `export FF_LOG_SCHEMA_DISCOVERY=true`
2. Use migration mode to compare outputs
3. Check deprecation warnings in logs
4. File issues with specific migration problems