# Storage Requirements Analysis

## Overview
This document details the exact field requirements for the Neo4j storage layer (graph_storage.py) and compares them with what the extraction layer produces.

## Storage Layer Field Requirements

### 1. Entity Storage (create_entity method)
**Required Fields**:
- `type`: Entity type (used as node label)
- `value`: Entity name/value

**Stored as Neo4j Properties**:
- `id`: Generated from episode_id, type, and value hash
- `name`: Mapped from input 'value' field
- `entity_type`: Mapped from input 'type' field
- `confidence`: Float, defaults to 0.85
- `start_time`: Float, defaults to 0
- `end_time`: Float, defaults to 0
- `extraction_method`: From properties, defaults to 'unknown'
- `description`: From properties, defaults to ''
- `meaningful_unit_id`: From properties, defaults to ''

**Mismatch**: Extraction creates 'name', storage expects 'value'

### 2. Quote Storage (create_quote method)
**Required Fields**:
- `text`: Quote text content

**Stored as Neo4j Properties**:
- `id`: Generated from episode_id, unit_id, and text hash
- `text`: Direct mapping
- `speaker`: Defaults to 'Unknown'
- `quote_type`: Defaults to 'general'
- `importance_score`: Float, defaults to 0.7
- `confidence`: Float, defaults to 0.85
- `timestamp_start`: Float, defaults to 0
- `timestamp_end`: Float, defaults to 0
- `word_count`: Calculated from text
- `context`: From properties, defaults to ''

**Mismatch**: Pipeline executor expects 'value', storage expects 'text'

### 3. Insight Storage (create_insight method)
**Required Fields**:
- `text`: Insight text content

**Stored as Neo4j Properties**:
- `id`: Generated from episode_id, unit_id, and text hash
- `text`: Direct mapping
- Additional properties mapped from input

**Major Mismatch**: 
- Extraction creates: 'title' and 'description'
- Storage expects: 'text'
- This will cause ValueError: "insight_data must contain 'text'"

### 4. Relationship Storage (create_relationship method)
**Required Parameters**:
- `source_id`: Source node ID
- `target_id`: Target node ID
- `rel_type`: Relationship type
- `properties`: Optional dict of properties

**No field mismatches** - Uses IDs directly

## Summary of Mismatches

| Data Type | Extraction Creates | Storage Expects | Pipeline Uses | Status |
|-----------|-------------------|-----------------|---------------|---------|
| Entity | name | value | value | ❌ Error |
| Quote | text | text | value | ❌ Error in pipeline |
| Insight | title, description | text | title, description | ❌ Will error in storage |
| Relationship | source, target, type | IDs | IDs | ✅ OK |

## Critical Issues

1. **Entity Issue (Active)**: Causes KeyError: 'value' in pipeline
2. **Quote Issue (Hidden)**: Pipeline executor uses wrong field name
3. **Insight Issue (Hidden)**: Storage expects different field than extraction provides

## Storage Patterns

### ID Generation
All nodes use consistent ID patterns:
- Entity: `entity_{episode_id}_{type}_{hash}`
- Quote: `quote_{episode_id}_{unit_id}_{hash}`
- Insight: `insight_{episode_id}_{unit_id}_{hash}`

### Common Fields
All node types include:
- `id`: Unique identifier
- `confidence`: Confidence score
- Timestamps or timing information

### Relationship Pattern
All relationships include:
- Source and target node IDs
- Relationship type (e.g., MENTIONED_IN, EXTRACTED_FROM)
- Optional properties dict

## Recommendations

1. **Align Field Names**: 
   - Entities: Use 'value' consistently
   - Quotes: Use 'text' consistently
   - Insights: Either change extraction to produce 'text' or storage to accept 'title'/'description'

2. **Add Validation**:
   - Validate required fields before storage attempt
   - Provide clear error messages indicating expected fields

3. **Document Contract**:
   - Create TypedDict definitions for each data structure
   - Use these as the contract between components