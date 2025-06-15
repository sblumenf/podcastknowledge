# Missing Storage Methods Implementation Plan

## Overview

This plan addresses the critical missing storage methods required for the unified pipeline to function. These methods were assumed to exist in the original plan but need to be implemented before proceeding.

## Required Storage Methods

### 1. `create_episode(episode_metadata: Dict[str, Any]) -> str`

**Purpose**: Store or retrieve episode node in Neo4j

**Input Structure**:
```python
{
    'episode_id': str,          # Required unique identifier
    'title': str,               # Episode title
    'description': str,         # Episode description
    'published_date': str,      # Publication date
    'youtube_url': str,         # YouTube URL
    'podcast_info': {           # Podcast metadata
        'name': str,
        'host': str,
        # other fields
    }
}
```

**Implementation Requirements**:
- Create Episode node if not exists (idempotent)
- Link to Podcast node if podcast_info provided
- Return episode_id
- Handle duplicate episodes gracefully

**Neo4j Structure**:
```cypher
(e:Episode {
    id: episode_id,
    title: title,
    description: description,
    published_date: published_date,
    youtube_url: youtube_url,
    created_at: timestamp,
    updated_at: timestamp
})
-[:PART_OF]->
(p:Podcast {
    id: podcast_name,
    name: podcast_name,
    host: host
})
```

### 2. `create_entity(entity_data: Dict[str, Any], episode_id: str) -> str`

**Purpose**: Store extracted entities with schema-less type support

**Input Structure**:
```python
{
    'type': str,                # Schema-less entity type (e.g., PERSON, TECHNOLOGY, QUANTUM_RESEARCHER)
    'value': str,               # Entity name/value
    'entity_type': str,         # Lowercase version of type
    'confidence': float,        # 0.0 to 1.0
    'start_time': float,        # From MeaningfulUnit
    'end_time': float,          # From MeaningfulUnit
    'properties': {
        'extraction_method': str,
        'description': str,
        'meaningful_unit_id': str,
        # other dynamic properties
    }
}
```

**Implementation Requirements**:
- Generate unique entity ID: `f"entity_{episode_id}_{entity_type}_{hash(value)[:8]}"`
- Create Entity node with dynamic type
- Create MENTIONED_IN relationship to Episode
- Store all properties (schema-less)
- Return entity_id

**Neo4j Structure**:
```cypher
(en:Entity {
    id: generated_id,
    name: value,
    entity_type: type,
    confidence: confidence,
    // all other properties flattened
})
-[:MENTIONED_IN {confidence: confidence}]->
(e:Episode)
```

### 3. `create_quote(quote_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str`

**Purpose**: Store extracted quotes linked to MeaningfulUnits

**Input Structure**:
```python
{
    'type': 'Quote',
    'text': str,                # Quote text
    'value': str,               # Same as text (backward compat)
    'speaker': str,             # Who said it
    'quote_type': str,          # Type of quote
    'timestamp_start': float,
    'timestamp_end': float,
    'importance_score': float,
    'confidence': float,
    'properties': {
        'extraction_method': str,
        'word_count': int,
        'meaningful_unit_id': str,
        'context': str,
        # other properties
    }
}
```

**Implementation Requirements**:
- Generate unique quote ID: `f"quote_{episode_id}_{meaningful_unit_id}_{hash(text[:50])[:8]}"`
- Create Quote node
- Create EXTRACTED_FROM relationship to MeaningfulUnit
- Create PART_OF relationship to Episode
- Return quote_id

**Neo4j Structure**:
```cypher
(q:Quote {
    id: generated_id,
    text: text,
    speaker: speaker,
    quote_type: quote_type,
    importance_score: importance_score,
    // all other properties
})
-[:EXTRACTED_FROM]->
(m:MeaningfulUnit)
AND
(q)-[:PART_OF]->(e:Episode)
```

### 4. `create_insight(insight_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str`

**Purpose**: Store extracted insights linked to MeaningfulUnits

**Input Structure**:
```python
{
    'type': 'Insight',
    'text': str,                # Insight text
    'insight_type': str,        # Type of insight
    'importance': float,        # Importance score
    'confidence': float,
    'timestamp': float,         # Start time
    'properties': {
        'extraction_method': str,
        'supporting_evidence': str,
        'meaningful_unit_id': str,
        'themes': List[str],
        # other properties
    }
}
```

**Implementation Requirements**:
- Generate unique insight ID: `f"insight_{episode_id}_{meaningful_unit_id}_{hash(text[:50])[:8]}"`
- Create Insight node
- Create EXTRACTED_FROM relationship to MeaningfulUnit
- Create PART_OF relationship to Episode
- Return insight_id

**Neo4j Structure**:
```cypher
(i:Insight {
    id: generated_id,
    text: text,
    insight_type: insight_type,
    importance: importance,
    // all other properties
})
-[:EXTRACTED_FROM]->
(m:MeaningfulUnit)
AND
(i)-[:PART_OF]->(e:Episode)
```

### 5. `create_sentiment(sentiment_data: Dict[str, Any], episode_id: str, meaningful_unit_id: str) -> str`

**Purpose**: Store sentiment analysis results linked to MeaningfulUnits

**Input Structure**:
```python
{
    'unit_id': str,
    'overall_polarity': str,
    'overall_score': float,
    'emotions': Dict[str, float],
    'attitudes': Dict[str, float],
    'energy_level': float,
    'engagement_level': float,
    'speaker_sentiments': Dict[str, Dict],
    'emotional_moments': List[Dict],
    'sentiment_flow': str,
    'interaction_harmony': float,
    'discovered_sentiments': List[Dict],
    'confidence': float
}
```

**Implementation Requirements**:
- Generate unique sentiment ID: `f"sentiment_{episode_id}_{meaningful_unit_id}"`
- Create Sentiment node
- Create ANALYZED_FROM relationship to MeaningfulUnit
- Store complex properties as JSON strings
- Return sentiment_id

**Neo4j Structure**:
```cypher
(s:Sentiment {
    id: generated_id,
    polarity: overall_polarity,
    score: overall_score,
    energy_level: energy_level,
    // complex properties as JSON strings
})
-[:ANALYZED_FROM]->
(m:MeaningfulUnit)
```

## Implementation Strategy

### Phase 1: Core Infrastructure
1. Add helper methods for JSON serialization of complex properties
2. Add ID generation utilities
3. Add validation methods

### Phase 2: Episode Storage
1. Implement `create_episode()` with Podcast linking
2. Handle idempotent creation (check exists first)
3. Add proper error handling

### Phase 3: Knowledge Storage
1. Implement `create_entity()` with schema-less support
2. Implement `create_quote()` with dual relationships
3. Implement `create_insight()` with dual relationships
4. Implement `create_sentiment()` with JSON handling

### Phase 4: Testing
1. Unit tests for each method
2. Integration tests with pipeline
3. Verify relationships in Neo4j

## Critical Considerations

1. **Schema-less Support**: Entity types are dynamic - don't validate against fixed list
2. **Idempotency**: Episode creation must be idempotent
3. **Relationships**: Quotes/Insights link to BOTH MeaningfulUnit AND Episode
4. **JSON Properties**: Complex nested properties stored as JSON strings
5. **Error Handling**: Follow existing retry patterns in graph_storage.py
6. **Locking**: Use existing _lock for thread safety
7. **Logging**: Comprehensive logging for debugging

## Success Criteria

1. All storage methods implemented and working
2. Pipeline can run end-to-end without storage errors
3. All relationships properly created in Neo4j
4. Schema-less entity types working
5. Complex properties properly stored and retrievable
6. No data loss on errors (rollback support)