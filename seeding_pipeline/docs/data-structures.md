# Data Structure Standards

This document defines the canonical data structures used throughout the knowledge extraction pipeline. All components MUST use these field names exactly as defined here.

## Overview

The pipeline uses four main data structures:
1. **Entities** - People, organizations, technologies, concepts
2. **Quotes** - Notable statements from speakers
3. **Insights** - Key takeaways and learnings
4. **Relationships** - Connections between entities

## Entity Structure

Entities represent any notable person, organization, technology, or concept mentioned in the podcast.

### Required Fields
- **`value`** (string): The entity name/value (e.g., "Elon Musk", "artificial intelligence")
- **`type`** (string): Entity type in UPPERCASE (e.g., "PERSON", "TECHNOLOGY", "ORGANIZATION")

### Optional Fields
- **`confidence`** (float): Confidence score from 0.0 to 1.0
- **`description`** (string): Brief description of the entity
- **`importance`** (float): Importance score from 0.0 to 1.0
- **`frequency`** (int): Number of mentions in the content
- **`has_citation`** (boolean): Whether entity has supporting citations
- **`start_time`** (float): Start timestamp in seconds
- **`end_time`** (float): End timestamp in seconds
- **`properties`** (dict): Additional properties

### Example
```python
{
    "value": "Elon Musk",
    "type": "PERSON",
    "confidence": 0.95,
    "description": "CEO of Tesla and SpaceX",
    "importance": 0.9,
    "frequency": 5,
    "has_citation": true,
    "start_time": 120.5,
    "end_time": 125.3,
    "properties": {
        "extraction_method": "llm_extraction",
        "meaningful_unit_id": "unit_1"
    }
}
```

### Common Mistakes
- ❌ Using `"name"` instead of `"value"`
- ❌ Using lowercase types like `"person"`
- ✅ Always use `"value"` for the entity name
- ✅ Always use UPPERCASE for types

## Quote Structure

Quotes capture notable statements from podcast speakers.

### Required Fields
- **`text`** (string): The quote text content

### Optional Fields
- **`speaker`** (string): Name of the speaker
- **`context`** (string): Context around the quote
- **`quote_type`** (string): Type of quote (e.g., "general", "key_point")
- **`importance`** (float): Importance score from 0.0 to 1.0
- **`confidence`** (float): Confidence score from 0.0 to 1.0
- **`timestamp_start`** (float): Start timestamp in seconds
- **`timestamp_end`** (float): End timestamp in seconds
- **`properties`** (dict): Additional properties

### Example
```python
{
    "text": "The future is going to be wild.",
    "speaker": "Elon Musk",
    "context": "Discussing AI advancement",
    "quote_type": "key_point",
    "importance": 0.8,
    "confidence": 0.9,
    "timestamp_start": 145.2,
    "timestamp_end": 148.7,
    "properties": {
        "meaningful_unit_id": "unit_2"
    }
}
```

### Common Mistakes
- ❌ Using `"value"` instead of `"text"`
- ❌ Using `"content"` instead of `"text"`
- ✅ Always use `"text"` for the quote content

## Insight Structure

Insights represent key learnings or takeaways from the content.

### Required Fields
- **`title`** (string): Brief title of the insight
- **`description`** (string): Detailed description

### Optional Fields
- **`type`** (string): Insight type (e.g., "conceptual", "practical")
- **`confidence`** (float): Confidence score from 0.0 to 1.0
- **`supporting_entities`** (list[string]): List of related entity values
- **`properties`** (dict): Additional properties

### Example
```python
{
    "title": "AI Revolution Impact",
    "description": "Artificial intelligence will fundamentally transform how we work and live within the next decade",
    "type": "conceptual",
    "confidence": 0.85,
    "supporting_entities": ["artificial intelligence", "Elon Musk"],
    "properties": {
        "meaningful_unit_id": "unit_3"
    }
}
```

### Storage Note
When storing insights in Neo4j, the storage layer requires a `text` field. The pipeline automatically creates this by combining title and description:
```python
storage_insight["text"] = f"{insight['title']}: {insight['description']}"
```

## Relationship Structure

Relationships define connections between entities.

### Required Fields
- **`source`** (string): Source entity value
- **`target`** (string): Target entity value
- **`type`** (string): Relationship type (e.g., "WORKS_FOR", "CREATED_BY")

### Optional Fields
- **`confidence`** (float): Confidence score from 0.0 to 1.0
- **`properties`** (dict): Additional properties

### Example
```python
{
    "source": "Elon Musk",
    "target": "Tesla",
    "type": "FOUNDED",
    "confidence": 0.95,
    "properties": {
        "year": 2003,
        "role": "Co-founder and CEO"
    }
}
```

## Extraction Result Structure

The complete extraction result contains all extracted knowledge:

```python
{
    "entities": [...],      # List of Entity structures
    "quotes": [...],        # List of Quote structures
    "insights": [...],      # List of Insight structures
    "relationships": [...], # List of Relationship structures
    "conversation_structure": {...}  # Optional conversation metadata
}
```

## Validation

All data structures are validated at two points:
1. **After extraction** - Immediately after LLM processing
2. **Before storage** - Just before writing to Neo4j

Validation functions are available in `src/core/validation.py`:
- `validate_entity(entity)`
- `validate_quote(quote)`
- `validate_insight(insight)`
- `validate_relationship(relationship)`

## Migration Support

During the transition period, normalization functions help convert old formats:
- `normalize_entity_fields(entity)` - Converts `name` → `value`
- `normalize_insight_for_storage(insight)` - Creates `text` field for storage

## Best Practices

1. **Always validate** - Use validation functions before processing
2. **Use TypedDict** - Reference `src/core/data_structures.py` for type hints
3. **Log invalid data** - Don't silently drop invalid structures
4. **Preserve original fields** - Keep all fields from extraction
5. **Use consistent casing** - Entity types in UPPERCASE, field names in lowercase

## Common Integration Points

### LLM Output → Extraction
- LLM returns entities with `name` field
- Extraction maps to `value` for pipeline

### Pipeline → Storage
- Pipeline uses standard field names
- Storage may require additional mappings

### Error Handling
When field access fails:
1. Log the error with full context
2. Show which field is missing
3. List available fields
4. Continue processing other items

## Version History

- **v1.0** (2025-06-21): Initial standardization
  - Fixed entity name/value inconsistency
  - Fixed quote text/value inconsistency
  - Added insight text normalization for storage