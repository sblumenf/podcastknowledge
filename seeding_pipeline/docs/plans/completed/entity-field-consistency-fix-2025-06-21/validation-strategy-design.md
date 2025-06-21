# Validation Strategy Design

## Overview
This document outlines a simple, KISS-compliant validation strategy for ensuring field consistency across the pipeline. The approach prioritizes simplicity and clear error messages over complex schema validation.

## Design Principles

1. **Keep It Simple**: No external validation libraries or complex schemas
2. **Fail Fast**: Validate early to catch errors before they propagate
3. **Clear Errors**: Provide helpful error messages that specify what's wrong
4. **Lightweight**: Minimal performance impact
5. **Python Standard Library Only**: No new dependencies

## Validation Approach

### 1. Simple Field Existence Checks
```python
def validate_entity(entity: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate entity has required fields.
    Returns: (is_valid, error_message)
    """
    if not isinstance(entity, dict):
        return False, "Entity must be a dictionary"
    
    if 'value' not in entity:
        return False, "Entity missing required field: 'value'"
    
    if 'type' not in entity:
        return False, "Entity missing required field: 'type'"
    
    if not entity['value']:
        return False, "Entity 'value' cannot be empty"
    
    if not entity['type']:
        return False, "Entity 'type' cannot be empty"
    
    return True, ""
```

### 2. Where to Validate

**Option A: At Creation Points** (Recommended)
- Validate immediately after data is created
- Prevents invalid data from entering the pipeline
- Easier to trace errors to their source

**Option B: Before Storage**
- Validate just before storing to Neo4j
- Acts as a final safety check
- May be harder to trace error origins

**Decision**: Implement both for defense in depth
- Primary validation at creation points
- Secondary validation before storage as safety net

### 3. Validation Points in Pipeline

1. **After LLM Extraction** (extraction.py)
   - Validate extracted entities, quotes, insights, relationships
   - Ensure field mapping is correct (name → value)

2. **Before Deduplication** (unified_pipeline.py)
   - Validate all data structures have expected fields
   - Catch any missed mappings

3. **Before Storage** (graph_storage.py)
   - Final validation before Neo4j operations
   - Ensure all required fields exist

### 4. Error Handling Strategy

```python
# Option 1: Return validation result (RECOMMENDED)
is_valid, error_msg = validate_entity(entity)
if not is_valid:
    logger.warning(f"Invalid entity skipped: {error_msg}")
    continue  # Skip invalid data, process rest

# Option 2: Raise exceptions (NOT RECOMMENDED)
# Would halt entire pipeline for one bad entity
```

### 5. Validation Functions Structure

```python
# src/core/validation.py

def validate_entity(entity: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate entity data structure."""
    # Check required fields exist
    # Return (True, "") if valid
    # Return (False, "specific error") if invalid

def validate_quote(quote: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate quote data structure."""
    # Similar pattern

def validate_insight(insight: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate insight data structure."""
    # Similar pattern

def validate_relationship(rel: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate relationship data structure."""
    # Similar pattern

def validate_extraction_result(result: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate complete extraction result."""
    # Validate overall structure
    # Optionally validate each item
```

### 6. Logging and Metrics

- Log validation failures with context
- Count validation failures for monitoring
- Include sample of invalid data in logs (truncated)

### 7. Migration Helper

For smooth transition during fixes:
```python
def normalize_entity_fields(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize entity fields during transition period.
    Maps 'name' to 'value' if needed.
    """
    if 'name' in entity and 'value' not in entity:
        entity['value'] = entity['name']
        del entity['name']
    return entity
```

## Implementation Priority

1. **First**: Implement validate_entity() - fixes immediate issue
2. **Second**: Implement validate_quote() - prevents next error
3. **Third**: Add validation calls to critical points
4. **Fourth**: Implement remaining validators

## Success Metrics

1. No more KeyError exceptions for field access
2. Clear log messages when data is invalid
3. Pipeline continues processing valid data even with some invalid items
4. Validation adds < 1% to processing time

## What We're NOT Doing

1. ❌ Complex JSON Schema validation
2. ❌ External validation libraries (Pydantic, Marshmallow)
3. ❌ Deep type checking beyond required fields
4. ❌ Validating field content format (just existence)
5. ❌ Throwing exceptions that halt pipeline

## Next Steps

1. Implement validation.py with the four main validators
2. Add validation calls to extraction.py after processing
3. Add validation calls to unified_pipeline.py before storage
4. Test with known bad data to ensure graceful handling