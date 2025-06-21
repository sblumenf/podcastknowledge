# All Data Structures Field Analysis

## Summary of Field Naming Issues

### 1. Entity Fields
**Issue**: 'name' vs 'value' inconsistency
- Extraction creates: 'name'
- Pipeline expects: 'value'
- Storage expects: 'value', stores as 'name'

### 2. Quote Fields  
**Issue**: 'text' vs 'value' inconsistency
- Extraction creates: 'text'
- Pipeline executor expects: 'value' (pipeline_executor.py lines 363-364)
- This will cause KeyError: 'value' when storing quotes!

### 3. Insight Fields
**No Issues Found**: Consistent field naming
- Extraction creates: 'title', 'description', 'type'
- Pipeline processes: Same fields
- No inconsistencies detected

### 4. Relationship Fields
**No Issues Found**: Consistent field naming
- Expected fields: 'source', 'target', 'type'
- No alternative field names found

## Detailed Analysis

### Entities
| Component | Field Created/Expected | Line References |
|-----------|----------------------|-----------------|
| extraction.py | Creates with 'name' | Line 434 |
| unified_pipeline.py | Expects 'value' | Lines 1010, 1189, 1260 |
| pipeline_executor.py | Maps 'value' to 'name' | Line 342 |
| graph_storage.py | Expects 'value' | Line 1058 |

### Quotes
| Component | Field Created/Expected | Line References |
|-----------|----------------------|-----------------|
| extraction.py | Creates with 'text' | Line 465 |
| pipeline_executor.py | Expects 'value' | Lines 363-364 |
| validation.py | Expects 'text' | Uses quote.get('text') |

### Insights
| Component | Fields Used | Status |
|-----------|------------|--------|
| extraction.py | title, description, type | ✓ Consistent |
| All components | Same fields | ✓ No issues |

### Relationships
| Component | Fields Used | Status |
|-----------|------------|--------|
| All components | source, target, type | ✓ Consistent |

## Critical Findings

1. **Two Field Naming Issues**:
   - Entities: 'name' vs 'value' 
   - Quotes: 'text' vs 'value'

2. **Quote Issue Not Yet Causing Errors**:
   - The quote 'value' error hasn't manifested yet
   - Likely because quote processing happens after entity processing
   - Once entity error is fixed, quote error will appear next

3. **Insights and Relationships Are Clean**:
   - These structures use consistent field names
   - No fixes needed for these

## Recommendations

### Immediate Fixes Needed
1. Fix entity 'name' → 'value' in extraction.py
2. Fix quote reference in pipeline_executor.py to use 'text' instead of 'value'

### Alternative for Quotes
Either:
- Option A: Change pipeline_executor.py to use quote['text'] 
- Option B: Change extraction.py to create quotes with 'value' field

Option A is preferred to maintain consistency with extraction output.