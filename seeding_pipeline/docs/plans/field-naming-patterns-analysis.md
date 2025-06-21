# Field Naming Patterns Analysis

## Executive Summary

The pipeline has a complex field naming issue where:
1. LLM extraction returns entities with 'name' field
2. Internal pipeline processes entities expecting 'value' field  
3. Storage layer expects 'value' but stores as 'name' in Neo4j
4. Multiple mapping points create confusion and potential for errors

## Critical Inconsistency Points

### 1. The Root Cause
- **LLM Responses**: Return entities with 'name' field
- **Extraction Layer**: Maps 'name' → 'value' (extraction.py lines 851, 1222)
- **Pipeline Layer**: Expects and uses 'value' field
- **Storage Layer**: Maps 'value' → 'name' (pipeline_executor.py line 342)

### 2. Where The Error Occurs
The current KeyError happens because:
- Some extraction paths don't perform the 'name' → 'value' mapping
- extraction.py `_process_entities()` creates entities with 'name' field (line 434)
- unified_pipeline.py tries to access entity['value'] (line 1010)

## Component Field Expectations

| Component | Expected Field | Creates Field | Notes |
|-----------|---------------|---------------|-------|
| LLM Response | - | name | Raw extraction output |
| extraction.py (_process_entities) | name | name | ⚠️ Missing mapping |
| extraction.py (other methods) | name | value | Correct mapping |
| unified_pipeline.py | value | - | Causes KeyError |
| pipeline_executor.py | value | name (for storage) | Maps for Neo4j |
| graph_storage.py | value | - | Stores as 'name' |

## Field Access Patterns Found

### Direct Access (Will Cause KeyError if Missing)
- `entity['value']`: 8 locations in pipeline processing
- `entity['name']`: 5 locations in extraction  
- `entity['type']`: 12 locations across all components

### Safe Access (Returns Default if Missing)
- `entity.get('value')`: 20+ locations
- `entity.get('name')`: 7 locations
- `entity.get('type')`: 15+ locations

### Fallback Patterns
- `entity.get('value', entity.get('name', ''))`: Used in entity resolution
- Provides compatibility but masks the underlying issue

## Other Data Structure Fields

### Common Fields Across All Structures
- `type`: Consistently used across entities, quotes, insights
- `description`: Optional field with safe access patterns
- `confidence`: Numeric field with defaults
- `importance`: Numeric field with normalization

### Structure-Specific Fields
- **Entities**: name/value (inconsistent), type, description
- **Quotes**: text, speaker, context, quote_type
- **Insights**: title, description, type, supporting_entities
- **Relationships**: source, target, type, properties

## Impact Analysis

### Current Impact
1. Pipeline fails with KeyError: 'value' 
2. Episodes cannot be processed
3. Knowledge extraction blocked

### Risk Areas
1. Any code using direct field access (entity['field'])
2. Components assuming one field name without checking
3. Mappings that may be missed in some code paths

## Recommendations

### Immediate Fix
1. Update `_process_entities()` in extraction.py to use 'value' instead of 'name'
2. Ensure all entity creation uses 'value' consistently

### Long-term Solution
1. Standardize on 'value' throughout the pipeline
2. Add validation at component boundaries
3. Use TypedDict for type hints
4. Remove all field mappings by using consistent names

### Validation Points
1. After extraction: Validate entities have 'value' field
2. Before storage: Validate required fields exist
3. Add clear error messages indicating which field is missing