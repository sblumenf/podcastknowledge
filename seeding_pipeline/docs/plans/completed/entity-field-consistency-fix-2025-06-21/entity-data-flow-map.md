# Entity Data Flow Map

## Overview
This document maps the complete flow of entity data through the knowledge extraction pipeline, revealing field naming inconsistencies.

## Key Finding: Field Naming Mismatch
- **Extraction Layer**: Creates entities with 'name' field
- **Storage Layer**: Expects entities with 'value' field
- **Pipeline Layer**: Accesses entities using 'value' field

## Entity Data Flow

### 1. Entity Creation (Extraction Layer)
**File**: `src/extraction/extraction.py`
**Method**: `_process_entities()` (lines 423-452)
**Fields Created**:
```python
{
    'name': entity['name'],  # ⚠️ Using 'name' field
    'type': entity.get('type', 'Unknown'),
    'description': entity.get('description', ''),
    'importance': float(entity.get('importance', 5)) / 10,
    'frequency': entity.get('frequency', 1),
    'has_citation': entity.get('has_citation', False),
    'confidence': self.config.entity_confidence_threshold + 0.2
}
```

### 2. Entity Processing (Pipeline Layer)
**File**: `src/pipeline/unified_pipeline.py`
**Locations**:
- Line 831: `entity['type']` - Accessing type field
- Line 1010: `entity['value']` - ⚠️ Expecting 'value' field (will cause KeyError)
- Lines 1188-1189: Accessing both `entity['type']` and `entity['value']`

### 3. Entity Storage (Storage Layer)
**File**: `src/storage/graph_storage.py`
**Method**: `create_entity()` (lines 1038-1087)
**Required Fields**:
- `type`: Entity type (line 1058)
- `value`: Entity name/value (line 1058) ⚠️ Expects 'value', not 'name'

### 4. Additional Entity Access Points
Found through grep searches:
- **Files expecting 'name'**: 11 files including extraction modules
- **Files expecting 'value'**: 9 files including pipeline and storage modules

## Root Cause
The extraction layer creates entities with a 'name' field, but both the pipeline and storage layers expect a 'value' field. This mismatch causes a KeyError when the pipeline tries to access `entity['value']` before storing it.

## Impact
- Episode processing fails with KeyError: 'value'
- Entities cannot be stored in Neo4j
- Pipeline cannot complete successfully

## Next Steps
- Continue with Task 1.2: Identify all field naming patterns
- Task 1.3: Check similar issues in other data structures
- Task 1.4: Document storage requirements